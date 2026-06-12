import csv, pathlib, numpy as np
base = pathlib.Path("logs/0612_4state_10sensers")
fp = list(base.glob("*.csv"))[0]
rows = list(csv.DictReader(open(fp)))

print(f"File: {fp.name}")
print(f"spwr values: {set(r['spwr'] for r in rows)}")
print(f"mode values: {set(r['mode'] for r in rows)}")

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

ncut = [r for r in rows if r["mode"] == "NCUT"]
ch1 = np.array([[h2s(r[f"CH1_{i:03d}"]) for i in range(128)] for r in ncut[:5]])
ch2 = np.array([[h2s(r[f"CH2_{i:03d}"]) for i in range(128)] for r in ncut[:5]])

print(f"\nCH1: mean={ch1.mean():.1f} std={ch1.std():.1f} min={ch1.min():.0f} max={ch1.max():.0f}")
print(f"CH2: mean={ch2.mean():.1f} std={ch2.std():.1f} min={ch2.min():.0f} max={ch2.max():.0f}")
print(f"frmVar CH1={np.std(ch1,axis=0).mean():.2f}")

# First frame shape
print(f"\nFirst frame CH1: {[f'{x:.0f}' for x in ch1[0]]}")
print(f"Last frame CH1:  {[f'{x:.0f}' for x in ch1[-1]]}")
