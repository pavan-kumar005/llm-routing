import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.config import STRONG_MODEL

RESULTS = Path("results")
POLICIES = ["always_cheap", "always_strong", "router"]


def load(policy: str):
    path = RESULTS / f"{policy}.jsonl"
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    return pd.DataFrame([json.loads(l) for l in lines if l.strip()])


def main():
    frames, rows = {}, []
    for p in POLICIES:
        df = load(p)
        if df is None:
            print(f"missing results for {p}, run it first")
            continue
        frames[p] = df
        n = len(df)
        rows.append({
            "policy": p,
            "questions": n,
            "errors": int((df["status"] != "success").sum()),
            "pass_rate_pct": round(df["passed"].mean() * 100, 1),
            "cost_per_1k_usd": round(df["cost_usd"].sum() / n * 1000, 4),
            "avg_latency_ms": int(df["latency_ms"].mean()),
            "strong_share_pct": int((df["model"] == STRONG_MODEL).mean() * 100),
        })

    if not rows:
        return
    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))
    summary.to_csv(RESULTS / "summary.csv", index=False)

    s = summary.set_index("policy")
    if {"always_strong", "router"} <= set(s.index):
        strong_cost = s.loc["always_strong", "cost_per_1k_usd"]
        if strong_cost > 0:
            saved = (1 - s.loc["router", "cost_per_1k_usd"] / strong_cost) * 100
            delta = s.loc["router", "pass_rate_pct"] - s.loc["always_strong", "pass_rate_pct"]
            print(f"\nRouter vs always_strong: {saved:.1f}% cheaper, "
                  f"{delta:+.1f} points pass rate")

        # questions the router got wrong but the strong model got right
        merged = frames["router"].merge(
            frames["always_strong"][["id", "passed"]], on="id", suffixes=("", "_strong"))
        bad = merged[(~merged["passed"]) & (merged["passed_strong"])]
        if len(bad):
            print("\nMisroutes (router failed, strong passed):")
            for _, r in bad.iterrows():
                print(f"  #{r['id']} [{r['reason']}] {r['prompt'][:70]}")

    plt.figure(figsize=(6, 4))
    for _, r in summary.iterrows():
        plt.scatter(r["cost_per_1k_usd"], r["pass_rate_pct"], s=80)
        plt.annotate(r["policy"], (r["cost_per_1k_usd"], r["pass_rate_pct"]),
                     textcoords="offset points", xytext=(6, 6))
    plt.xlabel("Cost per 1,000 requests (USD)")
    plt.ylabel("Pass rate (%)")
    plt.title("Cost vs accuracy by routing policy")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULTS / "cost_vs_accuracy.png", dpi=150)
    print(f"\nSaved {RESULTS / 'cost_vs_accuracy.png'}")


if __name__ == "__main__":
    main()