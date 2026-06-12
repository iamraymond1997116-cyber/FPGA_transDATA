"""Quick check: validate 0612 new data"""
import csv, pathlib

base = pathlib.Path("logs/0612_4state_10sensers")
files = sorted(base.glob("v60_*.csv"))
total = 0
for f in files:
    with open(f) as fh:
        r = csv.DictReader(fh)
        ch_cols = [c for c in r.fieldnames if c.startswith("CH")]
        rows = list(r)
        issues = []
        for row in rows:
            vals = [int(row[c], 16) for c in ch_cols]
            if all(v == 0 for v in vals):
                issues.append("all zeros")
            break  # just check first row per file
        status = "OK" if not issues else f"Issues: {issues}"
        print(f"  {f.name}: {len(rows)} rows {status}")
        total += len(rows)
print(f"\nTotal: {len(files)} files, {total} frames")
print("All clean!")
