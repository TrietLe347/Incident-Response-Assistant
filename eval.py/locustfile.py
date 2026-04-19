"""
ARIA Load Test — Locust
=======================
Tests both the retrieval and answer services under realistic RA usage.

Install:
  pip install locust

Run (50 users, 5-min test, target P95 ≤ 3s):
  locust -f locustfile.py \
    --host https://answer-service-571628338947.us-central1.run.app \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless \
    --html load_test_report.html \
    --csv load_test_results

Two user classes:
  - RAUser         (85% of traffic) — typical RA querying the answer service
  - AdminUser      (15% of traffic) — admin reloading embeddings, checking retrieval directly
"""

import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner

# ---------------------------------------------------------------------------
# Realistic RA queries sampled during each test run
# ---------------------------------------------------------------------------

RA_QUERIES = [
    "What should I do when a resident reports a gas leak?",
    "A resident is threatening self-harm. What is the protocol?",
    "How do I handle an unauthorized guest found in the building?",
    "What are the quiet hours for weeknights?",
    "A fire alarm is going off. What are my responsibilities?",
    "A resident appears intoxicated in the hallway. What do I do?",
    "How do I fill out an incident report after a conflict?",
    "What is the procedure for a resident lockout at night?",
    "A resident reports their roommate is being physically aggressive.",
    "There is water leaking from the ceiling. Who do I contact?",
    "Can residents have candles in their rooms?",
    "A resident has a pet but pets are not allowed. What is the procedure?",
    "A resident discloses they are being stalked. What should I do?",
    "What is the escalation process for repeated quiet hours violations?",
    "A resident has not been seen in several days. What are the steps?",
    "How should I respond if I smell smoke from a resident's room?",
    "A resident wants to switch rooms. What is the process?",
    "There is a power outage. What is the emergency procedure?",
    "A resident's parent is demanding information about their child.",
    "What do I do during an active threat or lockdown situation?",
    "A resident reports sexual harassment. What is the protocol?",
    "How many overnight guests can a resident have?",
    "A resident has a prohibited appliance like a hot plate.",
    "Two roommates are in a conflict about cleanliness.",
    "A resident is grieving a death in the family. What resources are available?",
]


# ---------------------------------------------------------------------------
# RA User — queries the full answer service (retrieval + Gemini)
# ---------------------------------------------------------------------------

class RAUser(HttpUser):
    """
    Simulates a Resident Advisor submitting incident queries.
    Wait time models realistic think-time between questions.
    """
    weight = 85
    wait_time = between(3, 10)           # RAs don't spam — 3-10s between queries

    @task(10)
    def ask_incident_question(self):
        query = random.choice(RA_QUERIES)
        with self.client.post(
            "/",
            json={"query": query, "stream": False},
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /answer (non-streaming)",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "answer" not in data:
                    resp.failure("Response missing 'answer' field")
                elif not data["answer"] or data["answer"] == "No relevant policy information found for your query.":
                    resp.failure("Empty or no-result answer")
                else:
                    resp.success()
            elif resp.status_code == 502:
                resp.failure("Retrieval service downstream error")
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def ask_repeated_common_query(self):
        """Simulates RAs asking the same common questions — tests caching behavior."""
        query = "What should I do during a fire alarm?"
        with self.client.post(
            "/",
            json={"query": query, "stream": False},
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /answer (hot query)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")


# ---------------------------------------------------------------------------
# Admin User — calls retrieval directly, triggers embedding reload
# ---------------------------------------------------------------------------

RETRIEVAL_URL = "https://retrieval-service-571628338947.us-central1.run.app"


class AdminUser(HttpUser):
    """
    Simulates housing admins checking retrieval health or reloading embeddings.
    Less frequent than RA traffic.
    """
    weight = 15
    wait_time = between(15, 45)          # admins check less frequently

    @task(5)
    def test_retrieval_directly(self):
        query = random.choice(RA_QUERIES[:10])
        with self.client.post(
            RETRIEVAL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /retrieval (direct)",
            timeout=15,
        ) as resp:
            if resp.status_code == 200:
                chunks = resp.json()
                if not isinstance(chunks, list):
                    resp.failure("Expected a list of chunks")
                elif len(chunks) == 0:
                    resp.failure("No chunks returned")
                else:
                    resp.success()
            else:
                resp.failure(f"Retrieval returned {resp.status_code}")

    @task(1)
    def reload_embeddings(self):
        """Simulates an admin-triggered reload after uploading new documents."""
        with self.client.get(
            f"{RETRIEVAL_URL}/reload",
            catch_response=True,
            name="GET /retrieval/reload",
            timeout=30,
        ) as resp:
            if resp.status_code in (200, 204):
                resp.success()
            else:
                resp.failure(f"Reload returned {resp.status_code}")


# ---------------------------------------------------------------------------
# Event hooks — print summary thresholds after run
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.runner.stats
    total = stats.total

    if total.num_requests == 0:
        print("\nNo requests completed.")
        return

    p95 = total.get_response_time_percentile(0.95) / 1000  # ms → s
    failure_rate = total.num_failures / total.num_requests * 100

    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"  Total requests : {total.num_requests:,}")
    print(f"  Failures       : {total.num_failures:,}  ({failure_rate:.1f}%)")
    print(f"  P50 latency    : {total.get_response_time_percentile(0.50)/1000:.2f}s")
    print(f"  P95 latency    : {p95:.2f}s  (target ≤ 3.0s)  {'✓ PASS' if p95 <= 3.0 else '✗ FAIL'}")
    print(f"  RPS (avg)      : {total.current_rps:.2f}")
    print("=" * 60)

    if p95 > 3.0:
        environment.process_exit_code = 1