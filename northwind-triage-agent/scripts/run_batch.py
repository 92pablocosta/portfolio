# scripts/run_batch.py
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.triage import triage_message

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HARD_FIELDS = ["category", "priority", "route_to", "needs_human_review"]


def load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def score_route_to(agent_val: str, bench_val: str) -> float:
    """
    Exact match = 1.0
    Partial credit (0.5) if the agent's value is fully contained in the
    benchmark string, or vice-versa — handles cases like 'Customer Care'
    vs 'Customer Care + Accounts'.
    """
    if agent_val == bench_val:
        return 1.0
    a = agent_val.strip().lower()
    b = bench_val.strip().lower()
    if a in b or b in a:
        return 0.5
    return 0.0


def score_result(agent: dict, bench: dict) -> dict[str, float]:
    scores = {}
    for field in HARD_FIELDS:
        agent_val = agent.get(field)
        bench_val = bench.get(field)

        # Normalise bool → string so comparisons are type-safe
        if isinstance(agent_val, bool):
            agent_val = str(agent_val).lower()
        if isinstance(bench_val, bool):
            bench_val = str(bench_val).lower()

        if field == "route_to":
            scores[field] = score_route_to(str(agent_val), str(bench_val))
        else:
            scores[field] = 1.0 if str(agent_val) == str(bench_val) else 0.0

    return scores


def fmt(score: float) -> str:
    if score == 1.0:
        return "✓"
    if score == 0.5:
        return "½"
    return "✗"


def run_batch() -> list[dict]:
    messages = load_json("messages.json")["messages"]
    benchmark_index = {d["id"]: d for d in load_json("benchmark.json")["decisions"]}

    results = []

    for i, msg in enumerate(messages, start=1):
        msg_id = msg["id"]
        print(f"[{i:02d}/20] Processing {msg_id}...", end=" ", flush=True)

        try:
            output = triage_message(msg)
        except RuntimeError as e:
            print(f"ERROR — {e}")
            continue

        bench = benchmark_index.get(msg_id, {})
        scores = score_result(output.model_dump(), bench)

        results.append({
            "id": msg_id,
            "agent": output.model_dump(),
            "benchmark": bench,
            "scores": scores,
        })

        row = "  ".join(f"{f}={fmt(scores[f])}" for f in HARD_FIELDS)
        print(row)
        time.sleep(0.3)

    return results


def print_summary(results: list[dict]) -> None:
    total = len(results)
    print("\n" + "─" * 56)

    field_totals: dict[str, float] = {f: 0.0 for f in HARD_FIELDS}
    strict_correct = 0

    for r in results:
        s = r["scores"]
        for f in HARD_FIELDS:
            field_totals[f] += s[f]
        if all(s[f] == 1.0 for f in HARD_FIELDS):
            strict_correct += 1

    for field, total_score in field_totals.items():
        pct = (total_score / total) * 100
        print(f"{field:<22} {total_score:>4.1f}/{total}   {pct:.1f}%")

    print("─" * 56)
    strict_pct = (strict_correct / total) * 100
    print(f"{'Strict accuracy (all 4 fields)':<22} {strict_correct:>4}/{total}   {strict_pct:.1f}%")
    print("─" * 56)


if __name__ == "__main__":
    results = run_batch()

    output_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved → {output_path}")
    print_summary(results)