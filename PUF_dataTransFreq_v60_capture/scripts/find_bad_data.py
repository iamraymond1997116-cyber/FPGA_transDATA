"""找异常数据：电源线断了的特征是信号幅度极小/全零"""
import csv, pathlib, numpy as np
from scipy.fft import fft

base = pathlib.Path("logs/0612_4state_10sensers")
files = sorted(base.glob("v60_*.csv"))

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

print(f"{'File':45s} {'Rows':6s} {'CH1_peak':8s} {'CH1_rms':8s} {'CH2_peak':8s} {'CH2_rms':8s} {'power':8s} {'Status':10s}")
print("="*95)

bad_files = []
for fp in files:
    with fp.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    ch1_all, ch2_all = [], []
    for row in rows[:10]:  # sample first 10 rows
        ch1 = np.array([h2s(row[f"CH1_{i:03d}"]) for i in range(128)], dtype=np.float64)
        ch2 = np.array([h2s(row[f"CH2_{i:03d}"]) for i in range(128)], dtype=np.float64)
        ch1_all.append(ch1)
        ch2_all.append(ch2)

    ch1_all = np.array(ch1_all)
    ch2_all = np.array(ch2_all)

    ch1_peak = np.max(np.abs(ch1_all))
    ch2_peak = np.max(np.abs(ch2_all))
    ch1_rms = np.sqrt(np.mean(ch1_all**2))
    ch2_rms = np.sqrt(np.mean(ch2_all**2))

    # Detect bad: very low signal amplitude
    is_bad = ch1_peak < 100 or ch2_peak < 100
    status = "!!BAD" if is_bad else "OK"

    # Check spwr
    spwrs = set(row["spwr"] for row in rows[:10])
    power_info = ",".join(sorted(spwrs))

    if is_bad:
        bad_files.append((fp.name, ch1_peak, ch2_peak))

    print(f"{fp.name:45s} {len(rows):6d} {ch1_peak:8.0f} {ch1_rms:8.1f} {ch2_peak:8.0f} {ch2_rms:8.1f} {power_info:8s} {status:10s}")

print(f"\n{'='*95}")
print(f"\n!! BAD FILES ({len(bad_files)}):")
for name, p1, p2 in bad_files:
    parts = name.split("_")
    print(f"  {name}: CH1_peak={p1:.0f}, CH2_peak={p2:.0f}")
