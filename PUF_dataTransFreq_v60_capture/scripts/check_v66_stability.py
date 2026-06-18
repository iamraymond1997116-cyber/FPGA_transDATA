"""快速扫描 V6.6 数据集的 NCUT 帧间稳定性 + 峰值。

用法：
    python scripts/check_v66_stability.py logs/0618_4state_10sensors_v66
    python scripts/check_v66_stability.py logs/0618_4state_10sensors_v66 --sensor B2-1
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

NCUT_IDX = 2  # MID=2


def scan_dir(base: pathlib.Path, sensor_filter=None):
    csvs = sorted(base.glob("v66_*.csv"))
    csvs = [c for c in csvs if not c.name.endswith("_samples.csv")
            and not c.name.endswith("_metadata_cycles.csv")]
    if sensor_filter:
        csvs = [c for c in csvs if f"_{sensor_filter}_" in c.name]
    if not csvs:
        print(f"no v66_*.csv under {base}")
        return 1

    hdr = f"{'File':60s} {'samp':>4s} {'NCUT_mean':>9s} {'NCUT_std':>8s} {'NCUT_peak':>9s} {'CH1_frmVar':>10s} {'CH2_frmVar':>10s} {'CMR_std':>7s}  Flag"
    print(hdr)
    print("=" * len(hdr))

    suspicious = []
    for csv_path in csvs:
        npy_path = csv_path.with_suffix(".npy")
        if not npy_path.exists():
            print(f"{csv_path.name:60s} (no .npy companion)")
            continue
        X = np.load(npy_path)  # [N, 5, 2, 128]
        if X.shape[0] == 0:
            print(f"{csv_path.name:60s} (empty)")
            continue
        ncut = X[:, NCUT_IDX, :, :].astype(np.float64)  # [N, 2, 128]
        ch1 = ncut[:, 0, :]
        ch2 = ncut[:, 1, :]

        ncut_mean = ch1.mean()
        ncut_std = ch1.std()
        ncut_peak = float(np.abs(ch1).max())
        ch1_frmVar = float(np.std(ch1, axis=0).mean())
        ch2_frmVar = float(np.std(ch2, axis=0).mean())
        cmr_std = float((ch1 - ch2).std())

        is_flat = ncut_peak < 1000
        is_unstable = ch1_frmVar > 10 or ch2_frmVar > 10
        flag = "OK"
        if is_flat:
            flag = "!!FLAT"
            suspicious.append((csv_path.name, "FLAT", ch1_frmVar, ncut_peak))
        elif is_unstable:
            flag = "!!UNSTABLE"
            suspicious.append((csv_path.name, "UNSTABLE", ch1_frmVar, ncut_peak))

        print(f"{csv_path.name:60s} {X.shape[0]:>4d} {ncut_mean:>9.1f} {ncut_std:>8.1f} "
              f"{ncut_peak:>9.0f} {ch1_frmVar:>10.2f} {ch2_frmVar:>10.2f} {cmr_std:>7.2f}  {flag}")

    if suspicious:
        print(f"\nSUSPICIOUS ({len(suspicious)} files):")
        for name, reason, var, peak in suspicious:
            print(f"  {name}: {reason} frmVar={var:.2f} peak={peak:.0f}")
        return 1
    print(f"\nALL {len(csvs)} files OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="V6.6 dataset NCUT stability scan")
    ap.add_argument("dataset_dir", type=pathlib.Path)
    ap.add_argument("--sensor", default=None, help="filter by sensor id, e.g. B2-1")
    args = ap.parse_args()
    return scan_dir(args.dataset_dir, args.sensor)


if __name__ == "__main__":
    sys.exit(main())
