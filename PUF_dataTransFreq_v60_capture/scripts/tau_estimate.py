"""Estimate OFF-state discharge tau from NCUT data"""
import csv, pathlib, numpy as np

base = pathlib.Path("logs/0612_4state_10sensers")
fp = base / "v60_B2-1_NTNP_20260612_105352.csv"

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

rows = list(csv.DictReader(open(fp)))
ncut = [r for r in rows if r["mode"] == "NCUT"]
ch1 = np.array([h2s(r["CH1_000"]) for r in ncut[:10]], dtype=np.float64)

# First frame
row = ncut[0]
sig = np.array([h2s(row[f"CH1_{i:03d}"]) for i in range(128)], dtype=np.float64)

dt_us = 1e6 / 170000  # ~5.88 us per sample

# Find the peak overshoot and fit exponential decay to the envelope
# The signal has ringing - find envelope peaks
# After initial transient, find where signal decays to baseline

# For OFF-state discharge: sensor power cut -> parasitic C discharges through R
# Model: V(t) = V0 * exp(-t/tau) + V_offset

# Find the first major peak after the initial undershoot
# Signal: goes down, up (over shoot), then decays to baseline
peak_idx = np.argmax(sig[10:50]) + 10  # search in 10-50 range
peak_val = sig[peak_idx]
baseline = np.mean(sig[-20:])  # last 20 points as settled value

# After peak, fit exponential to decay portion (peak to baseline)
decay = sig[peak_idx:] - baseline
# Find where decay crosses zero (settled)
settle_idx = peak_idx + np.argmin(np.abs(decay[:60]))
if settle_idx <= peak_idx:
    settle_idx = min(peak_idx + 40, len(sig) - 1)

# Take the positive portion of decay
decay_segment = sig[peak_idx:settle_idx] - baseline
t = np.arange(len(decay_segment)) * dt_us

# Fit log: ln(V) = -t/tau + ln(V0)
if len(decay_segment) > 3 and np.all(decay_segment > 0):
    log_v = np.log(decay_segment)
    coeffs = np.polyfit(t, log_v, 1)
    tau_us = -1.0 / coeffs[0]  # tau in us
    print(f"=== B2-1 NTNP NCUT OFF-state discharge ===")
    print(f"Sampling rate: 170 kSPS ({dt_us:.2f} us/pt)")
    print(f"Peak index: {peak_idx}, value: {peak_val:.0f}")
    print(f"Baseline: {baseline:.0f}")
    print(f"Settle index: {settle_idx}, points in fit: {len(decay_segment)}")
    print(f"Time constant tau = {tau_us:.1f} us")
    print(f"Fitted V0 = {np.exp(coeffs[1]):.0f}")
    print()

# Also try: 63% method (time from peak to 36.8% of peak)
v63 = baseline + (peak_val - baseline) * 0.368
cross_idx = peak_idx + np.argmin(np.abs(sig[peak_idx:peak_idx+60] - v63))
tau63_us = (cross_idx - peak_idx) * dt_us
print(f"63% method tau = {tau63_us:.1f} us")
