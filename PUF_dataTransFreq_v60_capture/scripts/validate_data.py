"""Quick validation: check all captured CSV files for anomalous data."""
import csv, pathlib, sys

base = pathlib.Path("logs/0611_4state_10sensers")
files = sorted(base.glob("v60_*.csv"))

total = 0
all_issues = []
for f in files:
    with open(f) as fh:
        reader = csv.DictReader(fh)
        row_count = 0
        file_issues = []
        for row in reader:
            row_count += 1
            ch1 = [int(row[f"CH1_{i:03d}"], 16) for i in range(128)]
            ch2 = [int(row[f"CH2_{i:03d}"], 16) for i in range(128)]

            # All zeros
            if all(v == 0 for v in ch1) and all(v == 0 for v in ch2):
                file_issues.append(f"  row {row_count}: CH1+CH2 all zeros")
            elif all(v == 0 for v in ch1):
                file_issues.append(f"  row {row_count}: CH1 all zeros")
            elif all(v == 0 for v in ch2):
                file_issues.append(f"  row {row_count}: CH2 all zeros")

            # Clipped high
            if all(v == 0xFFFF for v in ch1):
                file_issues.append(f"  row {row_count}: CH1 all 0xFFFF")
            if all(v == 0xFFFF for v in ch2):
                file_issues.append(f"  row {row_count}: CH2 all 0xFFFF")

        total += row_count
        status = "OK" if not file_issues else f"Issues: {len(file_issues)}"
        print(f"  {f.name}: {row_count} rows  {status}")
        all_issues.extend([f"{f.name}{i[1:]}" for i in file_issues])

print(f"\nTotal files: {len(files)}  Total frames: {total}")

if all_issues:
    print(f"\n[WARN] {len(all_issues)} anomaly(ies) found:")
    for i in all_issues:
        print(f"  {i}")
    sys.exit(1)
else:
    print("[OK] All data clean - no zero/clip anomalies")
