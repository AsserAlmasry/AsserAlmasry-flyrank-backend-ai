"""Run the 8 hand-labelled cases through the running endpoint and score the key field (category).

Start the API first (uvicorn src.main:app --port 8000), then:  python evals/run_eval.py [--url http://localhost:8000]
On OpenRouter's free tier this costs 8-16 of your 50 daily calls (16 if every case needs a repair).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import httpx

CASES = Path(__file__).with_name("cases.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()
    cases = json.loads(CASES.read_text("utf-8"))
    hits, failures = 0, []
    with httpx.Client(timeout=120) as http:
        for case in cases:
            r = http.post(f"{args.url}/enrich", json=case["input"])
            got = r.json().get("category") if r.status_code == 200 else f"HTTP {r.status_code}"
            ok = got == case["expected_category"]
            hits += ok
            print(f"{'PASS' if ok else 'FAIL'}  #{case['id']:<2} expected={case['expected_category']:<16} got={got:<16} "
                  f"{case['input']['title'][:45]}")
            if not ok:
                failures.append(case["id"])
    pct = 100 * hits / len(cases)
    print(f"\n{date.today()}  category accuracy: {hits}/{len(cases)} = {pct:.0f}%   failed cases: {failures or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
