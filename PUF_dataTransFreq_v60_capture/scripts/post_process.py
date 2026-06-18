"""V6.5 cycle-aware CSV/NPY -> analysis-ready npz pipeline.

Modes:
  Single file: post_process.py logs/v65_B2-1_NTNP_*.csv
  Batch:       post_process.py --glob "logs/v65_*.csv" [--merged-out all_dataset.npz]

For each input CSV the script writes:
  <stem>_X_cycles.npz             X.shape == [N, 5, 2, 128] + metadata
  <stem>_metadata_cycles.csv      per-sample row (sensor_id, condition, valid, ...)

In batch mode it also writes a merged dataset (default name all_dataset.npz)
covering every input file, plus manifest.json listing the sources.

Supports both V6.5 (new schema: sensor_id+condition columns, separate .npy)
and V6.0~V6.4 legacy (filename-tagged, payload in CSV).
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Optional, Tuple

import numpy as np
import pandas as pd

MODES = ["FULL", "PCUT", "NCUT", "EXTR", "FCYC"]
MODE_TO_IDX = {m: i for i, m in enumerate(MODES)}
CH1_COLS = [f"CH1_{i:03d}" for i in range(128)]
CH2_COLS = [f"CH2_{i:03d}" for i in range(128)]


def hex_to_int16(v):
    x = int(str(v), 16)
    return x - 0x10000 if x >= 0x8000 else x


def tags_from_filename(path: pathlib.Path) -> Tuple[Optional[str], Optional[str]]:
    """Fallback when CSV has no sensor_id/condition columns."""
    m = re.search(r"v6[0-9]_(B2-\d+)_(NTNP|NTHP|HTNP|HTHP)_", path.name)
    return (m.group(1), m.group(2)) if m else (None, None)


def find_companion_npy(csv_path: pathlib.Path) -> Optional[pathlib.Path]:
    candidate = csv_path.with_suffix(".npy")
    return candidate if candidate.exists() else None


def find_session_json(csv_path: pathlib.Path) -> Optional[pathlib.Path]:
    candidate = csv_path.parent / f"{csv_path.stem}_session.json"
    return candidate if candidate.exists() else None


def load_v65_with_npy(csv_path: pathlib.Path, npy_path: pathlib.Path):
    """V6.5 fast path: payload already in .npy."""
    df = pd.read_csv(csv_path, dtype=str)
    X = np.load(npy_path)
    if X.ndim != 4 or X.shape[1:] != (5, 2, 128):
        raise SystemExit(f"{npy_path}: expected shape [N,5,2,128], got {X.shape}")

    # Per-sample metadata: take first row of each sample group
    fname_sensor, fname_cond = tags_from_filename(csv_path)
    grouped = df.groupby("sample_id", sort=True).first().reset_index()
    if "sensor_id" in df.columns:
        sensor_arr = grouped["sensor_id"].fillna(fname_sensor or "").to_numpy()
    else:
        sensor_arr = np.array([fname_sensor or ""] * len(grouped))
    if "condition" in df.columns:
        cond_arr = grouped["condition"].fillna(fname_cond or "").to_numpy()
    else:
        cond_arr = np.array([fname_cond or ""] * len(grouped))
    sample_id_arr = grouped["sample_id"].astype(int).to_numpy()
    timestamp_arr = grouped["pc_time_iso"].to_numpy() if "pc_time_iso" in df.columns else np.array([""] * len(grouped))
    if "saturated" in df.columns:
        sat_per_sample = df.groupby("sample_id", sort=True)["saturated"].apply(
            lambda s: sum(int(x) for x in s)
        ).to_numpy()
    else:
        sat_per_sample = np.zeros(len(grouped), dtype=np.int32)

    if X.shape[0] != len(grouped):
        raise SystemExit(
            f"{csv_path}: npy has {X.shape[0]} samples but CSV has {len(grouped)} groups"
        )

    return {
        "X": X,
        "sample_id": sample_id_arr.astype(np.int32),
        "sensor_id": sensor_arr.astype(str),
        "condition": cond_arr.astype(str),
        "timestamp": timestamp_arr.astype(str),
        "saturated": sat_per_sample.astype(np.int32),
        "valid": np.ones(len(grouped), dtype=np.int8),  # capture already trimmed
        "source_csv": np.array([csv_path.name] * len(grouped)),
    }


def load_legacy(csv_path: pathlib.Path):
    """V6.0~V6.4 path: ADC payload still in CSV columns."""
    df = pd.read_csv(csv_path, dtype=str)
    if "sample_id" not in df.columns:
        df["sample_id"] = (np.arange(len(df)) // 5).astype(int)
    else:
        df["sample_id"] = df["sample_id"].astype(int)
    if "mode_idx" not in df.columns:
        df["mode_idx"] = df["mode"].map(MODE_TO_IDX)
    df["mode_idx"] = df["mode_idx"].astype(int)

    fname_sensor, fname_cond = tags_from_filename(csv_path)

    samples_X = []
    sample_ids = []
    sensors = []
    conds = []
    valids = []
    timestamps = []
    saturated = []

    for sid, g in df.groupby("sample_id", sort=True):
        arr = np.zeros((5, 2, 128), dtype=np.int16)
        present = set()
        for _, r in g.iterrows():
            mid = int(r["mode_idx"])
            mode = r["mode"]
            if mid < 0 or mid > 4 or MODE_TO_IDX.get(mode) != mid:
                continue
            arr[mid, 0, :] = [hex_to_int16(r[c]) for c in CH1_COLS]
            arr[mid, 1, :] = [hex_to_int16(r[c]) for c in CH2_COLS]
            present.add(mid)
        valid = (len(g) == 5 and present == set(range(5)))
        samples_X.append(arr)
        sample_ids.append(int(sid))
        sensors.append(g.iloc[0]["sensor_id"] if "sensor_id" in g.columns else (fname_sensor or ""))
        conds.append(g.iloc[0]["condition"] if "condition" in g.columns else (fname_cond or ""))
        valids.append(int(valid))
        timestamps.append(g.iloc[0]["pc_time_iso"] if "pc_time_iso" in g.columns else "")
        saturated.append(0)

    if not samples_X:
        empty = np.zeros((0, 5, 2, 128), dtype=np.int16)
        return {
            "X": empty,
            "sample_id": np.zeros(0, dtype=np.int32),
            "sensor_id": np.array([], dtype=str),
            "condition": np.array([], dtype=str),
            "timestamp": np.array([], dtype=str),
            "saturated": np.zeros(0, dtype=np.int32),
            "valid": np.zeros(0, dtype=np.int8),
            "source_csv": np.array([], dtype=str),
        }
    return {
        "X": np.stack(samples_X, axis=0),
        "sample_id": np.array(sample_ids, dtype=np.int32),
        "sensor_id": np.array(sensors, dtype=str),
        "condition": np.array(conds, dtype=str),
        "timestamp": np.array(timestamps, dtype=str),
        "saturated": np.array(saturated, dtype=np.int32),
        "valid": np.array(valids, dtype=np.int8),
        "source_csv": np.array([csv_path.name] * len(samples_X), dtype=str),
    }


def load_one(csv_path: pathlib.Path):
    """Auto-detect V6.5 (companion .npy) vs legacy (payload in CSV)."""
    npy_path = find_companion_npy(csv_path)
    if npy_path is not None:
        return load_v65_with_npy(csv_path, npy_path), "v65"
    return load_legacy(csv_path), "legacy"


def write_per_file_outputs(payload, csv_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = csv_path.stem
    npz_path = out_dir / f"{stem}_X_cycles.npz"
    meta_path = out_dir / f"{stem}_metadata_cycles.csv"

    extras = {}
    session = find_session_json(csv_path)
    if session is not None:
        try:
            sess = json.loads(session.read_text(encoding="utf-8"))
            env = sess.get("env", {})
            extras["git_hash"] = np.array(env.get("git_hash", ""))
            extras["git_branch"] = np.array(env.get("git_branch", ""))
            extras["rtl_version"] = np.array(env.get("rtl_version", ""))
            extras["captured_at"] = np.array(env.get("captured_at", ""))
            extras["host"] = np.array(env.get("host", ""))
        except (OSError, json.JSONDecodeError):
            pass

    np.savez_compressed(
        npz_path,
        X=payload["X"],
        mode_names=np.array(MODES),
        channel_names=np.array(["CH1", "CH2"]),
        sample_id=payload["sample_id"],
        sensor_id=payload["sensor_id"],
        condition=payload["condition"],
        timestamp=payload["timestamp"],
        saturated=payload["saturated"],
        valid=payload["valid"],
        source_csv=payload["source_csv"],
        **extras,
    )

    pd.DataFrame({
        "sample_id": payload["sample_id"],
        "sensor_id": payload["sensor_id"],
        "condition": payload["condition"],
        "timestamp": payload["timestamp"],
        "saturated": payload["saturated"],
        "valid": payload["valid"],
        "source_csv": payload["source_csv"],
    }).to_csv(meta_path, index=False)

    return npz_path, meta_path


def merge_payloads(payloads):
    if not payloads:
        return None
    return {
        "X": np.concatenate([p["X"] for p in payloads], axis=0),
        "sample_id": np.concatenate([p["sample_id"] for p in payloads]),
        "sensor_id": np.concatenate([p["sensor_id"] for p in payloads]),
        "condition": np.concatenate([p["condition"] for p in payloads]),
        "timestamp": np.concatenate([p["timestamp"] for p in payloads]),
        "saturated": np.concatenate([p["saturated"] for p in payloads]),
        "valid": np.concatenate([p["valid"] for p in payloads]),
        "source_csv": np.concatenate([p["source_csv"] for p in payloads]),
    }


def expand_inputs(args) -> list:
    paths = []
    if args.csv:
        paths.append(pathlib.Path(args.csv))
    if args.glob:
        base = pathlib.Path(".")
        # split off any leading directory in the glob pattern
        paths.extend(sorted(base.glob(args.glob)))
    if not paths:
        raise SystemExit("no input CSV(s); provide a path or --glob PATTERN")
    # Skip helper CSVs emitted alongside the payload CSV
    skip_suffixes = ("_samples.csv", "_metadata_cycles.csv", "_errors.csv")
    return [p for p in paths if p.suffix == ".csv"
            and not any(p.name.endswith(s) for s in skip_suffixes)]


def main():
    ap = argparse.ArgumentParser(
        description="Convert V6.5/legacy capture CSV(s) into analysis-ready npz."
    )
    ap.add_argument("csv", nargs="?", help="Single CSV path")
    ap.add_argument("--glob", help='Glob pattern, e.g. "logs/v65_*.csv"')
    ap.add_argument("--out-dir", type=pathlib.Path, default=None,
                    help="Output dir (default: <input>/processed)")
    ap.add_argument("--merged-out", default="all_dataset.npz",
                    help="Merged dataset filename in batch mode")
    ap.add_argument("--no-merge", action="store_true",
                    help="In batch mode, skip writing a merged dataset")
    args = ap.parse_args()

    paths = expand_inputs(args)
    if not paths:
        raise SystemExit("no CSV files matched")

    print(f"Processing {len(paths)} file(s)")
    payloads = []
    summaries = []
    for csv_path in paths:
        out_dir = args.out_dir or (csv_path.parent / "processed")
        try:
            payload, mode = load_one(csv_path)
        except Exception as exc:
            print(f"  [SKIP] {csv_path.name}: {exc}")
            continue
        npz_path, meta_path = write_per_file_outputs(payload, csv_path, out_dir)
        n = payload["X"].shape[0]
        valid_n = int(payload["valid"].sum())
        sat_n = int(payload["saturated"].sum())
        print(f"  [{mode}] {csv_path.name} -> {npz_path.name}  "
              f"shape={payload['X'].shape}  valid={valid_n}/{n}  saturated={sat_n}")
        payloads.append(payload)
        summaries.append({
            "source_csv": csv_path.name,
            "mode": mode,
            "samples": n,
            "valid": valid_n,
            "saturated": sat_n,
            "npz": npz_path.name,
            "metadata_csv": meta_path.name,
        })

    if not payloads:
        return 1

    if len(payloads) > 1 and not args.no_merge:
        out_dir = args.out_dir or (paths[0].parent / "processed")
        out_dir.mkdir(parents=True, exist_ok=True)
        merged = merge_payloads(payloads)
        merged_path = out_dir / args.merged_out
        np.savez_compressed(
            merged_path,
            X=merged["X"],
            mode_names=np.array(MODES),
            channel_names=np.array(["CH1", "CH2"]),
            sample_id=merged["sample_id"],
            sensor_id=merged["sensor_id"],
            condition=merged["condition"],
            timestamp=merged["timestamp"],
            saturated=merged["saturated"],
            valid=merged["valid"],
            source_csv=merged["source_csv"],
        )
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps({
            "generated_at": dt.datetime.now().isoformat(),
            "merged_npz": merged_path.name,
            "total_samples": int(merged["X"].shape[0]),
            "total_valid": int(merged["valid"].sum()),
            "files": summaries,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nMerged: {merged_path}  shape={merged['X'].shape}  "
              f"valid={int(merged['valid'].sum())}/{int(merged['X'].shape[0])}")
        print(f"Manifest: {manifest_path}")

    bad = [s for s in summaries if s["valid"] != s["samples"]]
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
