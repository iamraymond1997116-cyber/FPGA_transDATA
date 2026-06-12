"""查所有数据的帧间稳定性，找电源虚接的特征"""
import csv, pathlib, numpy as np

base = pathlib.Path("logs/0612_4state_10sensers")
files = sorted(base.glob("v60_*.csv"))

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

print(f"{'File':50s} {'CH1_mean':9s} {'CH1_std':9s} {'CH1_peak':8s} {'CH1_frmVar':9s} {'CH2_frmVar':9s} {'CMR_std':7s} {'Flag':8s}")
print("="*110)

suspicious = []
for fp in files:
    with open(fp, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    # 只取NCUT模式
    ncut = [r for r in rows if r["mode"] == "NCUT"]
    if len(ncut) < 3:
        continue

    ch1_all, ch2_all = [], []
    for row in ncut:
        ch1 = np.array([h2s(row[f"CH1_{i:03d}"]) for i in range(128)], dtype=np.float64)
        ch2 = np.array([h2s(row[f"CH2_{i:03d}"]) for i in range(128)], dtype=np.float64)
        ch1_all.append(ch1)
        ch2_all.append(ch2)

    ch1_all = np.array(ch1_all)
    ch2_all = np.array(ch2_all)

    ch1_mean = ch1_all.mean()
    ch1_std = ch1_all.std()
    ch1_peak = np.abs(ch1_all).max()

    # 帧间波动 = 各帧同一采样点的标准差均值
    ch1_frmVar = np.std(ch1_all, axis=0).mean()
    ch2_frmVar = np.std(ch2_all, axis=0).mean()

    cmr = ch1_all - ch2_all
    cmr_std = cmr.std()

    # 判断：帧间波动 > 10 就是有问题的（正常约0.8）
    is_unstable = ch1_frmVar > 10 or ch2_frmVar > 10
    is_flat = ch1_peak < 1000  # 信号基本平了
    flag = "OK"
    if is_flat:
        flag = "!!FLAT"
        suspicious.append((fp.name, "FLAT", ch1_frmVar, ch1_peak))
    elif is_unstable:
        flag = "!!UNSTABLE"
        suspicious.append((fp.name, "UNSTABLE", ch1_frmVar, ch1_peak))

    print(f"{fp.name:50s} {ch1_mean:9.1f} {ch1_std:9.1f} {ch1_peak:8.0f} {ch1_frmVar:9.2f} {ch2_frmVar:9.2f} {cmr_std:7.2f} {flag:8s}")

print(f"\nSUSPICIOUS ({len(suspicious)} files):")
for name, reason, var, peak in suspicious:
    print(f"  {name}: {reason} frmVar={var:.2f} peak={peak:.0f}")
print(f"\n正常参考：帧间波动 ~0.78，峰值 ~11000")
