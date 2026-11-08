import argparse
import asyncio
import json
import time
from pathlib import Path

from app.db import init_db, log_request
from app.pricing import calculate_cost
from app.providers.groq_provider import ProviderError, call_groq
from app.providers.mock_provider import call_mock
from app.routing.policies import choose_model
from evals.scorers import score

DATASET = Path("evals/dataset.jsonl")
RESULTS = Path("results")


def load_dataset(limit=None):
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    return items[:limit] if limit else items


def load_results(path: Path) -> dict:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    return {r["id"]: r for r in (json.loads(l) for l in lines if l.strip())}


def save_results(path: Path, records: dict, items: list):
    RESULTS.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            if item["id"] in records:
                f.write(json.dumps(records[item["id"]]) + "\n")


async def run(policy: str, delay: float, limit, mock: bool):
    init_db()
    items = load_dataset(limit)
    path = RESULTS / f"{'mock_' if mock else ''}{policy}.jsonl"

    # resume: keep earlier successes, retry earlier errors
    records = {i: r for i, r in load_results(path).items() if r["status"] == "success"}
    call = call_mock if mock else call_groq

    try:
        for n, item in enumerate(items, 1):
            if item["id"] in records:
                continue

            model, reason = choose_model(policy, item["prompt"])
            start = time.perf_counter()
            try:
                res = await call(model, item["prompt"])
                latency = (time.perf_counter() - start) * 1000
                cost = calculate_cost(model, res.input_tokens, res.output_tokens)
                passed = score(item, res.answer)
                rec = {
                    "id": item["id"], "policy": policy, "prompt": item["prompt"],
                    "difficulty": item["difficulty"], "model": model, "reason": reason,
                    "answer": res.answer, "passed": passed, "status": "success",
                    "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                    "latency_ms": round(latency, 1), "cost_usd": cost,
                }
                log_request(policy, model, reason, res.input_tokens,
                            res.output_tokens, latency, cost, "success")
            except ProviderError as e:
                latency = (time.perf_counter() - start) * 1000
                rec = {
                    "id": item["id"], "policy": policy, "prompt": item["prompt"],
                    "difficulty": item["difficulty"], "model": model, "reason": reason,
                    "answer": "", "passed": False, "status": f"error: {e}"[:200],
                    "input_tokens": 0, "output_tokens": 0,
                    "latency_ms": round(latency, 1), "cost_usd": 0.0,
                }
                log_request(policy, model, reason, 0, 0, latency, 0.0, rec["status"])

            records[item["id"]] = rec
            flag = "PASS" if rec["passed"] else "FAIL"
            print(f"[{n}/{len(items)}] {flag} {model} | {reason}")
            await asyncio.sleep(0 if mock else delay)
    finally:
        save_results(path, records, items)

    done = list(records.values())
    ok = sum(r["passed"] for r in done)
    errs = sum(r["status"] != "success" for r in done)
    print(f"\n{policy}: {ok}/{len(done)} passed, {errs} errors -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True,
                    choices=["always_cheap", "always_strong", "router"])
    ap.add_argument("--delay", type=float, default=2.5, help="seconds between calls")
    ap.add_argument("--limit", type=int, default=None, help="only first N questions")
    ap.add_argument("--mock", action="store_true", help="dry run, no real API calls")
    args = ap.parse_args()
    asyncio.run(run(args.policy, args.delay, args.limit, args.mock))