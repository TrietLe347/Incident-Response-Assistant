"""
ARIA Cost Analysis
==================
Compares serverless (pay-per-request) vs always-on (min-instances=1)
deployment cost under two traffic patterns:

  Pattern A — Low daily: ~20 queries/day spread across business hours
  Pattern B — Bursty:    ~200 queries/day concentrated in 2-hour windows
                          (move-in weekends, emergencies)

Pricing as of April 2026 (us-central1). Update if rates change.
Source: https://cloud.google.com/vertex-ai/pricing
        https://cloud.google.com/run/pricing

Usage:
  python cost_analysis.py
  python cost_analysis.py --queries-per-day 50 --days 30 --export results.json
"""

import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ---------------------------------------------------------------------------
# Pricing constants
# ---------------------------------------------------------------------------

@dataclass
class Pricing:
    # Cloud Run (per vCPU-second and GiB-second allocated)
    cloud_run_vcpu_second: float = 0.00002400   # $0.000024 / vCPU-second
    cloud_run_gib_second:  float = 0.00000250   # $0.0000025 / GiB-second
    cloud_run_request:     float = 0.00000040   # $0.0000004 / request
    cloud_run_free_reqs:   int   = 2_000_000    # 2M free requests / month

    # Vertex AI — text-embedding-004
    embedding_per_1k_chars: float = 0.000025    # $0.000025 / 1000 chars

    # Vertex AI — gemini-2.5-flash
    gemini_input_per_1m_tokens:  float = 0.15   # $0.15 / 1M input tokens
    gemini_output_per_1m_tokens: float = 0.60   # $0.60 / 1M output tokens

    # Cloud Storage
    gcs_storage_per_gb_month: float = 0.020     # $0.020 / GB-month (standard)
    gcs_class_a_per_10k:      float = 0.050     # Class A ops (writes)
    gcs_class_b_per_10k:      float = 0.004     # Class B ops (reads)

    # Cloud Logging (ingestion beyond free tier)
    logging_per_gib:          float = 0.50      # $0.50 / GiB ingested


# ---------------------------------------------------------------------------
# Per-request cost model
# ---------------------------------------------------------------------------

@dataclass
class RequestProfile:
    """Estimated resource consumption for one user query."""
    # Query embedding
    query_chars: int = 120               # avg query length in chars

    # Retrieval (Cloud Run)
    retrieval_vcpu_s: float = 0.3        # vCPU-seconds per retrieval call
    retrieval_gib_s:  float = 0.15       # GiB-seconds (512MB instance)

    # Answer generation
    context_tokens: int  = 2000          # retrieved chunk tokens (~8 chunks × 250 tokens)
    output_tokens:  int  = 300           # avg answer length
    answer_vcpu_s:  float = 4.0          # vCPU-seconds (waiting on Gemini + post-proc)
    answer_gib_s:   float = 2.0          # GiB-seconds (512MB instance)

    # Storage reads per query (embeddings loaded on cold start, amortized)
    gcs_reads_per_query: int = 0         # in-memory after warm start


@dataclass
class InfraProfile:
    """Static infrastructure assumptions."""
    # Embedding index size
    documents: int       = 50            # number of policy documents
    chunks_per_doc: int  = 40            # avg chunks per doc
    embedding_json_kb: float = 12.0      # ~12KB per embedding JSON (768-dim vector)

    # Logging
    log_bytes_per_request: int = 2048    # ~2KB of structured logs per query


# ---------------------------------------------------------------------------
# Traffic patterns
# ---------------------------------------------------------------------------

@dataclass
class TrafficPattern:
    name: str
    queries_per_day: float
    peak_hours_per_day: float            # hours when queries arrive
    description: str


PATTERNS = {
    "low_daily": TrafficPattern(
        name="Low daily (RA routine)",
        queries_per_day=20,
        peak_hours_per_day=8,
        description="Typical weekday: 20 queries spread across an 8-hour shift",
    ),
    "bursty": TrafficPattern(
        name="Bursty (move-in / emergency)",
        queries_per_day=200,
        peak_hours_per_day=2,
        description="Move-in weekend: 200 queries in a 2-hour window",
    ),
}


# ---------------------------------------------------------------------------
# Cost calculators
# ---------------------------------------------------------------------------

def cost_serverless(
    queries: int,
    profile: RequestProfile,
    infra: InfraProfile,
    pricing: Pricing,
) -> dict:
    """
    Serverless: min-instances=0, pay only for actual request execution.
    No idle costs between requests.
    """
    # Embedding (query only — doc embeddings are pre-computed)
    embed_cost = (queries * profile.query_chars / 1000) * pricing.embedding_per_1k_chars

    # Retrieval Cloud Run
    retrieval_vcpu = queries * profile.retrieval_vcpu_s * pricing.cloud_run_vcpu_second
    retrieval_mem  = queries * profile.retrieval_gib_s  * pricing.cloud_run_gib_second
    retrieval_reqs = max(0, queries - pricing.cloud_run_free_reqs) * pricing.cloud_run_request

    # Answer Cloud Run
    answer_vcpu = queries * profile.answer_vcpu_s * pricing.cloud_run_vcpu_second
    answer_mem  = queries * profile.answer_gib_s  * pricing.cloud_run_gib_second

    # Gemini
    gemini_input  = (queries * (profile.context_tokens + 500)) / 1_000_000 * pricing.gemini_input_per_1m_tokens
    gemini_output = (queries * profile.output_tokens) / 1_000_000 * pricing.gemini_output_per_1m_tokens

    # Storage (static — independent of traffic)
    total_chunks = infra.documents * infra.chunks_per_doc
    storage_gb   = (total_chunks * infra.embedding_json_kb) / (1024 * 1024)
    gcs_storage  = storage_gb * pricing.gcs_storage_per_gb_month

    # Logging
    log_gb = (queries * infra.log_bytes_per_request) / (1024 ** 3)
    logging_cost = max(0, log_gb - 50 / 1024) * pricing.logging_per_gib  # 50GiB free

    total = (
        embed_cost
        + retrieval_vcpu + retrieval_mem + retrieval_reqs
        + answer_vcpu + answer_mem
        + gemini_input + gemini_output
        + gcs_storage
        + logging_cost
    )

    return {
        "mode": "serverless",
        "embedding": round(embed_cost, 6),
        "retrieval_compute": round(retrieval_vcpu + retrieval_mem + retrieval_reqs, 6),
        "answer_compute": round(answer_vcpu + answer_mem, 6),
        "gemini": round(gemini_input + gemini_output, 6),
        "storage": round(gcs_storage, 6),
        "logging": round(logging_cost, 6),
        "total_usd": round(total, 4),
    }


def cost_always_on(
    queries: int,
    hours_in_period: float,
    profile: RequestProfile,
    infra: InfraProfile,
    pricing: Pricing,
    min_instances: int = 1,
) -> dict:
    """
    Always-on: min-instances=1, two services (retrieval + answer) keep one
    instance warm 24/7. Billed for idle time even with no traffic.
    """
    # Idle compute: 2 services × 1 vCPU × hours × 3600 s/hr
    # Cloud Run still bills CPU + memory for min-instance warm containers
    idle_vcpu_s = 2 * min_instances * hours_in_period * 3600
    idle_gib_s  = 2 * min_instances * 0.5 * hours_in_period * 3600  # 512MB each
    idle_cost   = (
        idle_vcpu_s * pricing.cloud_run_vcpu_second
        + idle_gib_s  * pricing.cloud_run_gib_second
    )

    # Per-request costs are the same as serverless for actual requests
    serverless = cost_serverless(queries, profile, infra, pricing)

    # Add idle cost on top
    total = serverless["total_usd"] + idle_cost

    return {
        "mode": "always_on",
        "idle_compute": round(idle_cost, 4),
        "request_costs": round(serverless["total_usd"], 4),
        "embedding": serverless["embedding"],
        "retrieval_compute": serverless["retrieval_compute"],
        "answer_compute": serverless["answer_compute"],
        "gemini": serverless["gemini"],
        "storage": serverless["storage"],
        "logging": serverless["logging"],
        "total_usd": round(total, 4),
    }


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def run_analysis(args):
    pricing = Pricing()
    request_profile = RequestProfile()
    infra = InfraProfile()

    days = args.days
    hours_in_period = days * 24

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "assumptions": {
            "analysis_period_days": days,
            "pricing_region": "us-central1",
            "pricing_date": "2026-04",
            "embedding_model": "text-embedding-004",
            "llm_model": "gemini-2.5-flash",
            "cloud_run_memory_mb": 512,
            "cloud_run_vcpu": 1,
        },
        "patterns": {},
    }

    header = f"\n{'='*62}\nARIA Cost Analysis — {days}-day period\n{'='*62}"
    print(header)

    for pattern_key, pattern in PATTERNS.items():
        total_queries = int(pattern.queries_per_day * days)

        sv = cost_serverless(total_queries, request_profile, infra, pricing)
        ao = cost_always_on(total_queries, hours_in_period, request_profile, infra, pricing)

        savings_usd = ao["total_usd"] - sv["total_usd"]
        savings_pct = (savings_usd / ao["total_usd"] * 100) if ao["total_usd"] > 0 else 0

        print(f"\n{pattern.name}")
        print(f"  {pattern.description}")
        print(f"  Total queries  : {total_queries:,}")
        print(f"  Serverless cost: ${sv['total_usd']:.4f}")
        print(f"  Always-on cost : ${ao['total_usd']:.4f}")
        print(f"  Savings        : ${savings_usd:.4f}  ({savings_pct:.1f}%)  {'✓ ≥30% target' if savings_pct >= 30 else '✗ below 30% target'}")

        print(f"\n  Serverless cost breakdown:")
        for k, v in sv.items():
            if k not in ("mode", "total_usd"):
                print(f"    {k:<22} ${v:.6f}")

        print(f"\n  Always-on cost breakdown:")
        for k, v in ao.items():
            if k not in ("mode", "total_usd"):
                print(f"    {k:<22} ${v:.6f}")

        report["patterns"][pattern_key] = {
            "name": pattern.name,
            "total_queries": total_queries,
            "queries_per_day": pattern.queries_per_day,
            "serverless": sv,
            "always_on": ao,
            "savings_usd": round(savings_usd, 4),
            "savings_pct": round(savings_pct, 1),
            "meets_30pct_target": savings_pct >= 30,
        }

    # Custom pattern from CLI args
    if args.queries_per_day:
        total_queries = int(args.queries_per_day * days)
        sv = cost_serverless(total_queries, request_profile, infra, pricing)
        ao = cost_always_on(total_queries, hours_in_period, request_profile, infra, pricing)
        savings_pct = (ao["total_usd"] - sv["total_usd"]) / ao["total_usd"] * 100 if ao["total_usd"] > 0 else 0

        print(f"\nCustom pattern ({args.queries_per_day} queries/day × {days} days)")
        print(f"  Serverless: ${sv['total_usd']:.4f}")
        print(f"  Always-on : ${ao['total_usd']:.4f}")
        print(f"  Savings   : {savings_pct:.1f}%")

        report["patterns"]["custom"] = {
            "queries_per_day": args.queries_per_day,
            "total_queries": total_queries,
            "serverless": sv,
            "always_on": ao,
            "savings_pct": round(savings_pct, 1),
        }

    print(f"\n{'='*62}")
    print("Key finding: Serverless saves most when traffic is sparse or bursty.")
    print("Break-even point is roughly when idle compute ≈ per-request costs.")
    print(f"{'='*62}\n")

    if args.export:
        with open(args.export, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Full report written to: {args.export}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARIA cost analysis")
    parser.add_argument("--days", type=int, default=30, help="Analysis period in days")
    parser.add_argument("--queries-per-day", type=float, default=None, help="Custom queries/day pattern")
    parser.add_argument("--export", default=None, help="Export JSON report to file")
    args = parser.parse_args()
    run_analysis(args)