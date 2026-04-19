"""
ARIA Evaluation Script
======================
Measures:
  1. Retrieval accuracy  — does at least one returned chunk contain expected keywords?
  2. Answer faithfulness — does the answer stay grounded in the retrieved chunks?
  3. Latency            — end-to-end P50 / P95 response times

Usage:
  python eval.py \
    --retrieval-url https://retrieval-service-571628338947.us-central1.run.app \
    --answer-url    https://answer-service-571628338947.us-central1.run.app \
    --queries       eval_queries.json \
    --top-k         5 \
    --output        eval_results.json
"""

import argparse
import json
import time
import sys
import statistics
import requests
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_retrieval_hit(chunks: list[dict], expected_keywords: list[str]) -> dict:
    """
    Returns hit info: whether any chunk contains >= 1 expected keyword.
    Keyword matching is case-insensitive substring search.
    """
    all_text = " ".join(c.get("text", "").lower() for c in chunks)
    matched = [kw for kw in expected_keywords if kw.lower() in all_text]
    hit = len(matched) > 0
    return {
        "hit": hit,
        "matched_keywords": matched,
        "missing_keywords": [kw for kw in expected_keywords if kw.lower() not in all_text],
        "chunks_returned": len(chunks),
    }


def check_faithfulness(answer: str, chunks: list[dict]) -> dict:
    """
    Heuristic faithfulness check:
    - Splits answer into sentences
    - Checks what % of content words in the answer appear in the source chunks
    - Flags phrases that appear grounded vs. potentially hallucinated

    Note: A proper LLM-based faithfulness check would call an evaluation model.
    This heuristic is a fast proxy for scoring at scale.
    """
    if not answer or not chunks:
        return {"faithful": False, "score": 0.0, "reason": "empty answer or no chunks"}

    chunk_text = " ".join(c.get("text", "").lower() for c in chunks)

    # Extract content words from answer (skip stopwords)
    stopwords = {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for",
        "of", "and", "or", "but", "not", "this", "that", "with", "as",
        "be", "are", "was", "were", "will", "would", "can", "could",
        "should", "have", "has", "had", "do", "does", "did", "if",
        "then", "their", "they", "them", "what", "how", "when", "where",
        "who", "which", "your", "you", "we", "our", "any", "all",
    }
    answer_words = [
        w.strip(".,;:!?\"'()").lower()
        for w in answer.split()
        if w.strip(".,;:!?\"'()").lower() not in stopwords and len(w) > 3
    ]

    if not answer_words:
        return {"faithful": True, "score": 1.0, "reason": "no content words to check"}

    grounded = sum(1 for w in answer_words if w in chunk_text)
    score = round(grounded / len(answer_words), 3)

    return {
        "faithful": score >= 0.5,
        "score": score,
        "grounded_word_ratio": f"{grounded}/{len(answer_words)}",
        "reason": "heuristic word-overlap check",
    }


def call_retrieval(url: str, query: str, timeout: int = 30) -> tuple[list, float]:
    t0 = time.perf_counter()
    r = requests.post(url, json={"query": query}, timeout=timeout)
    latency = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), latency


def call_answer(url: str, query: str, timeout: int = 60) -> tuple[dict, float]:
    t0 = time.perf_counter()
    r = requests.post(
        url,
        json={"query": query, "stream": False},
        timeout=timeout,
    )
    latency = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), latency


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_eval(args):
    queries_path = Path(args.queries)
    if not queries_path.exists():
        print(f"ERROR: queries file not found: {queries_path}")
        sys.exit(1)

    with open(queries_path) as f:
        queries = json.load(f)

    print(f"\nARIA Evaluation — {len(queries)} queries")
    print(f"  Retrieval URL : {args.retrieval_url}")
    print(f"  Answer URL    : {args.answer_url}")
    print(f"  Top-K         : {args.top_k}")
    print("=" * 60)

    results = []
    retrieval_hits = 0
    faithful_count = 0
    retrieval_latencies = []
    answer_latencies = []

    for i, q in enumerate(queries):
        qid = q["id"]
        query = q["query"]
        expected = q.get("expected_keywords", [])
        print(f"\n[{i+1:02d}/{len(queries)}] {qid}: {query[:60]}...")

        result = {
            "id": qid,
            "query": query,
            "category": q.get("category"),
            "severity": q.get("severity"),
        }

        # --- Retrieval ---
        try:
            chunks, ret_lat = call_retrieval(args.retrieval_url, query)
            filtered = [c for c in chunks if c.get("score", 0) > 0.55][: args.top_k]
            retrieval_latencies.append(ret_lat)

            hit_info = check_retrieval_hit(filtered, expected)
            result["retrieval"] = {
                "latency_s": round(ret_lat, 3),
                "chunks_total": len(chunks),
                "chunks_filtered": len(filtered),
                **hit_info,
            }

            if hit_info["hit"]:
                retrieval_hits += 1
                print(f"  ✓ Retrieval HIT  | matched: {hit_info['matched_keywords']}")
            else:
                print(f"  ✗ Retrieval MISS | missing: {hit_info['missing_keywords']}")

        except Exception as e:
            result["retrieval"] = {"error": str(e)}
            print(f"  ! Retrieval ERROR: {e}")
            results.append(result)
            continue

        # --- Answer + faithfulness ---
        if args.answer_url:
            try:
                answer_data, ans_lat = call_answer(args.answer_url, query)
                answer_latencies.append(ans_lat)

                answer_text = answer_data.get("answer", "")
                faith = check_faithfulness(answer_text, filtered)

                result["answer"] = {
                    "latency_s": round(ans_lat, 3),
                    "text_preview": answer_text[:200] + ("..." if len(answer_text) > 200 else ""),
                    "sources": answer_data.get("sources", []),
                    **faith,
                }

                if faith["faithful"]:
                    faithful_count += 1
                    print(f"  ✓ Faithfulness   | score={faith['score']} ({faith['grounded_word_ratio']} words grounded)")
                else:
                    print(f"  ✗ Faithfulness   | score={faith['score']} — may be hallucinating")

            except Exception as e:
                result["answer"] = {"error": str(e)}
                print(f"  ! Answer ERROR: {e}")

        results.append(result)

        # Small delay to avoid rate limiting
        if i < len(queries) - 1:
            time.sleep(0.5)

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    n = len(queries)
    answered = len([r for r in results if "answer" in r and "error" not in r["answer"]])

    def percentile(data, p):
        if not data:
            return None
        data = sorted(data)
        idx = int(len(data) * p / 100)
        return round(data[min(idx, len(data) - 1)], 3)

    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_queries": n,
        "retrieval": {
            "hits": retrieval_hits,
            "misses": n - retrieval_hits,
            "accuracy_pct": round(retrieval_hits / n * 100, 1),
            "target_pct": 80.0,
            "passed": (retrieval_hits / n * 100) >= 80.0,
            "latency_p50_s": percentile(retrieval_latencies, 50),
            "latency_p95_s": percentile(retrieval_latencies, 95),
        },
        "faithfulness": {
            "faithful": faithful_count,
            "total_answered": answered,
            "score_pct": round(faithful_count / answered * 100, 1) if answered else 0,
            "target_pct": 90.0,
            "passed": (faithful_count / answered * 100 >= 90.0) if answered else False,
        },
        "latency": {
            "retrieval_p50_s": percentile(retrieval_latencies, 50),
            "retrieval_p95_s": percentile(retrieval_latencies, 95),
            "answer_p50_s": percentile(answer_latencies, 50),
            "answer_p95_s": percentile(answer_latencies, 95),
            "end_to_end_p95_s": round(
                (percentile(retrieval_latencies, 95) or 0)
                + (percentile(answer_latencies, 95) or 0),
                3,
            ),
            "target_p95_s": 3.0,
            "passed": (
                (percentile(retrieval_latencies, 95) or 999)
                + (percentile(answer_latencies, 95) or 999)
            ) <= 3.0,
        },
        "per_category": {},
    }

    # Per-category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"hits": 0, "total": 0}
        categories[cat]["total"] += 1
        if r.get("retrieval", {}).get("hit"):
            categories[cat]["hits"] += 1

    for cat, stats in categories.items():
        summary["per_category"][cat] = {
            "accuracy_pct": round(stats["hits"] / stats["total"] * 100, 1),
            "hits": stats["hits"],
            "total": stats["total"],
        }

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Retrieval accuracy : {summary['retrieval']['accuracy_pct']}%  (target ≥80%)  {'✓ PASS' if summary['retrieval']['passed'] else '✗ FAIL'}")
    print(f"  Answer faithfulness: {summary['faithfulness']['score_pct']}%  (target ≥90%)  {'✓ PASS' if summary['faithfulness']['passed'] else '✗ FAIL'}")
    print(f"  End-to-end P95     : {summary['latency']['end_to_end_p95_s']}s (target ≤3s)   {'✓ PASS' if summary['latency']['passed'] else '✗ FAIL'}")
    print()
    print("Per-category retrieval accuracy:")
    for cat, stats in sorted(summary["per_category"].items(), key=lambda x: -x[1]["accuracy_pct"]):
        bar = "█" * int(stats["accuracy_pct"] / 10)
        print(f"  {cat:<25} {stats['accuracy_pct']:5.1f}%  {bar}")

    output = {
        "summary": summary,
        "results": results,
    }

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to: {output_path}")

    return 0 if (summary["retrieval"]["passed"] and summary["faithfulness"]["passed"]) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARIA evaluation script")
    parser.add_argument("--retrieval-url", required=True, help="Retrieval service URL")
    parser.add_argument("--answer-url", default=None, help="Answer service URL (optional)")
    parser.add_argument("--queries", default="eval_queries.json", help="Path to queries JSON")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K chunks to evaluate")
    parser.add_argument("--output", default="eval_results.json", help="Output file path")
    args = parser.parse_args()
    sys.exit(run_eval(args))