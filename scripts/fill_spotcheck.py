"""Interactive filling of the human_* columns of spotcheck.csv (saves after each item)."""
import json
import sys

import pandas as pd

f = f"results/runs/{sys.argv[1]}/spotcheck.csv"
df = pd.read_csv(f, dtype=str).fillna("")
dims = ["factual", "grounded", "reasoning", "calibration"]
for i, r in df.iterrows():
    if all(r[f"human_{d}"] for d in ("factual", "grounded", "calibration")):
        continue
    print("\n" + "=" * 78 + f"\nitem {r['item']}  {r['qid']}: {r['question']}\n" + "-" * 78)
    print("REFERENCE:\n" + json.dumps(json.loads(r["reference"]), indent=1, ensure_ascii=False))
    print("-" * 78 + "\nANSWER:\n" + r["answer"] + "\n" + "-" * 78)
    for d in dims:
        df.at[i, f"human_{d}"] = input(f"  {d} (1-5, blank = n/a): ").strip()
    df.to_csv(f, index=False)
print("saved", f)
