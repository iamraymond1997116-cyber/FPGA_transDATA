"""V6.5 cycle-aware UART capture parser.

Captures UART frames from the FPGA and writes:
  <stem>.csv          per-frame metadata (no ADC payload)
  <stem>.npy          ADC payload, int16, shape=[N_samples, 5, 2, 128]
  <stem>_samples.csv  per-sample validity summary
  <stem>_session.json provenance (git hash, RTL version, env)
  <stem>_errors.log   parse errors with raw bytes (only if any)

Also supports legacy V6.0~V6.4 frames (back-fills sample_id by index//5).
"""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict

import numpy as np

try:
    import serial
except ImportError:
    serial = None

# ── Frame regexes ──
HEADER_RE_V65 = re.compile(
    r"^V6\.5,SID=(\d{5}),MID=([0-4]),(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$"
)
HEADER_RE_LEGACY = re.compile(
    r"^V6\.[0-4],MODE=(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$"
)
RAW_RE = re.compile(r"^CH([12]),RAW,128,([0-9A-F]{4}(?:,[0-9A-F]{4}){127})$")

MODES = ["FULL", "PCUT", "NCUT", "EXTR", "FCYC"]
MODE_TO_IDX = {m: i for i, m in enumerate(MODES)}
EXPECTED_MODES = set(range(5))

# ADC saturation marks (16-bit signed boundary)
SATURATION_VALUES = {0x7FFE, 0x7FFF, 0x8000, 0x8001}


def hex_to_int16(v):
    x = int(v, 16)
    return x - 0x10000 if x >= 0x8000 else x


def count_saturated(ch1_hex, ch2_hex):
    return sum(1 for v in ch1_hex if int(v, 16) in SATURATION_VALUES) + sum(
        1 for v in ch2_hex if int(v, 16) in SATURATION_VALUES
    )


def parse_header(line):
    m = HEADER_RE_V65.match(line)
    if m:
        return {
            "protocol": "V65_RAW",
            "sample_id": int(m.group(1)),
            "mode_idx": int(m.group(2)),
            "mode": m.group(3),
        }, None
    m = HEADER_RE_LEGACY.match(line)
    if m:
        mode = m.group(1)
        return {
            "protocol": "V60_RAW",
            "sample_id": None,
            "mode_idx": MODE_TO_IDX[mode],
            "mode": mode,
        }, None
    return None, f"bad header: {line!r}"


def parse_frame(lines):
    if len(lines) != 3:
        return None, f"expected 3 lines, got {len(lines)}"
    header, err = parse_header(lines[0])
    if err:
        return None, err
    ch1 = RAW_RE.match(lines[1])
    ch2 = RAW_RE.match(lines[2])
    if not ch1 or ch1.group(1) != "1":
        return None, f"bad CH1 line: {lines[1]!r}"
    if not ch2 or ch2.group(1) != "2":
        return None, f"bad CH2 line: {lines[2]!r}"
    if header["mode_idx"] != MODE_TO_IDX[header["mode"]]:
        return None, f"MID/mode mismatch: MID={header['mode_idx']} mode={header['mode']}"
    ch1_hex = ch1.group(2).split(",")
    ch2_hex = ch2.group(2).split(",")
    header["ch1"] = [hex_to_int16(x) for x in ch1_hex]
    header["ch2"] = [hex_to_int16(x) for x in ch2_hex]
    header["saturated"] = count_saturated(ch1_hex, ch2_hex)
    return header, None


def assign_legacy_sample_ids(frames):
    """V6.0~V6.4 frames have no SID; back-fill by index//5."""
    legacy_idx = 0
    for f in frames:
        if f.get("sample_id") is None:
            f["sample_id"] = legacy_idx // 5
            legacy_idx += 1


def group_by_sample(frames):
    by = defaultdict(list)
    for f in frames:
        by[f["sample_id"]].append(f)
    return by


def trim_boundary_samples(frames):
    """Drop the leading and trailing samples if they're missing modes.

    Returns (kept_frames, dropped_count, dropped_sample_ids).
    """
    if not frames:
        return frames, 0, []
    by = group_by_sample(frames)
    sids = sorted(by)
    drop = set()
    # Leading partial
    if sids:
        first = sids[0]
        mids = sorted(f["mode_idx"] for f in by[first])
        if mids != [0, 1, 2, 3, 4]:
            drop.add(first)
    # Trailing partial
    if sids and sids[-1] not in drop:
        last = sids[-1]
        mids = sorted(f["mode_idx"] for f in by[last])
        if mids != [0, 1, 2, 3, 4]:
            drop.add(last)
    if not drop:
        return frames, 0, []
    kept = [f for f in frames if f["sample_id"] not in drop]
    return kept, len(drop), sorted(drop)


def validate_samples(frames):
    """Returns (rows, errors). Used after trimming, so all surviving samples
    should validate; rows still emitted for audit."""
    by = group_by_sample(frames)
    rows = []
    errs = []
    for sid in sorted(by):
        fs = by[sid]
        mids = [f["mode_idx"] for f in fs]
        missing = sorted(EXPECTED_MODES - set(mids))
        dup = sorted(m for m in EXPECTED_MODES if mids.count(m) > 1)
        order_ok = mids == [0, 1, 2, 3, 4]
        valid = not missing and not dup and order_ok and len(fs) == 5
        sat_total = sum(f.get("saturated", 0) for f in fs)
        rows.append({
            "sample_id": sid,
            "valid": int(valid),
            "order_ok": int(order_ok),
            "frame_count": len(fs),
            "missing_mode_idx": "|".join(map(str, missing)),
            "duplicate_mode_idx": "|".join(map(str, dup)),
            "saturated_total": sat_total,
            "modes": "|".join(f["mode"] for f in fs),
        })
        if not valid:
            errs.append(f"sample {sid}: frame_count={len(fs)} mids={mids} missing={missing} dup={dup}")
    return rows, errs


# ── Output writers ──

def build_meta_csv_rows(frames, sensor, condition):
    """One row per frame, no ADC payload."""
    rows = []
    for fr in frames:
        rows.append([
            fr["_ts"],
            fr["protocol"],
            sensor or "",
            condition or "",
            fr["sample_id"],
            fr["mode_idx"],
            fr["mode"],
            fr.get("saturated", 0),
        ])
    return rows


def write_meta_csv(path, frames, sensor, condition):
    with path.open("w", newline="", encoding="ascii") as f:
        w = csv.writer(f)
        w.writerow([
            "pc_time_iso", "protocol", "sensor_id", "condition",
            "sample_id", "mode_idx", "mode", "saturated",
        ])
        w.writerows(build_meta_csv_rows(frames, sensor, condition))


def write_npy_payload(path, frames):
    """Pack frames into [N_samples, 5, 2, 128] int16."""
    by = group_by_sample(frames)
    sids = sorted(by)
    if not sids:
        np.save(path, np.zeros((0, 5, 2, 128), dtype=np.int16))
        return 0
    X = np.zeros((len(sids), 5, 2, 128), dtype=np.int16)
    for i, sid in enumerate(sids):
        for fr in by[sid]:
            mid = fr["mode_idx"]
            X[i, mid, 0, :] = fr["ch1"]
            X[i, mid, 1, :] = fr["ch2"]
    np.save(path, X)
    return X.shape[0]


def write_samples_csv(path, frames):
    rows, errs = validate_samples(frames)
    if rows:
        with path.open("w", newline="", encoding="ascii") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return errs


def collect_provenance():
    """Best-effort env capture for session sidecar."""
    info = {
        "captured_at": dt.datetime.now().isoformat(),
        "host": platform.node(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if head.returncode == 0:
            info["git_hash"] = head.stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if branch.returncode == 0:
            info["git_branch"] = branch.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--short"],
            capture_output=True, text=True, timeout=5,
        )
        if dirty.returncode == 0:
            info["git_dirty"] = bool(dirty.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    # RTL version from top file
    rtl = repo_root / "PUF_dataTransFreq_v60_capture" / "rtl" / "transient_puf_v60_top.v"
    if rtl.exists():
        try:
            txt = rtl.read_text(encoding="utf-8", errors="ignore")
            major = re.search(r"VERSION_MAJOR\s*=\s*\d+'d(\d+)", txt)
            minor = re.search(r"VERSION_MINOR\s*=\s*\d+'d(\d+)", txt)
            if major and minor:
                info["rtl_version"] = f"V{major.group(1)}.{minor.group(1)}"
        except OSError:
            pass
    return info


def write_session_json(path, args, info, summary):
    payload = {
        "tool": "capture_ascii_v60.py",
        "tool_version": "v65-pc-revamp",
        "args": {
            "port": args.port,
            "baud": args.baud,
            "samples": args.samples,
            "frames": args.frames,
            "sensor": args.sensor,
            "condition": args.condition,
            "timeout": args.timeout,
            "out_dir": args.out_dir,
        },
        "env": info,
        "summary": summary,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_errors_log(path, errors_with_raw):
    if not errors_with_raw:
        return
    with path.open("w", encoding="utf-8") as f:
        for entry in errors_with_raw:
            f.write(f"[{entry['ts']}] {entry['err']}\n")
            for line in entry["raw"]:
                f.write(f"    {line!r}\n")
            f.write("\n")


# ── Self-test ──

def make_test_frames():
    vals1 = ",".join(f"{i & 0xffff:04X}" for i in range(128))
    vals2 = ",".join(f"{(i + 0x100) & 0xffff:04X}" for i in range(128))
    out = []
    for sid in range(2):
        for mid, mode in enumerate(MODES):
            out.append([
                f"V6.5,SID={sid:05d},MID={mid},{mode},SPWR=1,TXN={(sid * 5 + mid) & 0xff:02X}",
                f"CH1,RAW,128,{vals1}",
                f"CH2,RAW,128,{vals2}",
            ])
    return out


def make_boundary_test_frames():
    """Leading half (mids 2,3,4) + 2 full samples + trailing half (mids 0,1).
    Should leave 2 valid samples after trim."""
    vals1 = ",".join(f"{i & 0xffff:04X}" for i in range(128))
    vals2 = ",".join(f"{(i + 0x100) & 0xffff:04X}" for i in range(128))
    out = []
    # Leading: SID=10, MID 2..4
    for mid in [2, 3, 4]:
        out.append([
            f"V6.5,SID=00010,MID={mid},{MODES[mid]},SPWR=1,TXN={mid:02X}",
            f"CH1,RAW,128,{vals1}", f"CH2,RAW,128,{vals2}",
        ])
    # 2 full samples
    for sid in [11, 12]:
        for mid, mode in enumerate(MODES):
            out.append([
                f"V6.5,SID={sid:05d},MID={mid},{mode},SPWR=1,TXN={(sid * 5 + mid) & 0xff:02X}",
                f"CH1,RAW,128,{vals1}", f"CH2,RAW,128,{vals2}",
            ])
    # Trailing: SID=13, MID 0..1
    for mid in [0, 1]:
        out.append([
            f"V6.5,SID=00013,MID={mid},{MODES[mid]},SPWR=1,TXN={mid:02X}",
            f"CH1,RAW,128,{vals1}", f"CH2,RAW,128,{vals2}",
        ])
    return out


def run_self_test():
    # Test 1: basic parse + sample completeness
    frames = []
    for lines in make_test_frames():
        fr, err = parse_frame(lines)
        if err:
            raise SystemExit(f"basic parse failed: {err}")
        fr["_ts"] = "2026-01-01T00:00:00"
        frames.append(fr)
    rows, errs = validate_samples(frames)
    assert not errs and len(rows) == 2 and all(r["valid"] == 1 for r in rows), \
        f"basic validate failed: {errs} rows={rows}"

    # Test 2: boundary trimming
    raw_frames = []
    for lines in make_boundary_test_frames():
        fr, err = parse_frame(lines)
        if err:
            raise SystemExit(f"boundary parse failed: {err}")
        fr["_ts"] = "2026-01-01T00:00:00"
        raw_frames.append(fr)
    kept, dropped, drop_ids = trim_boundary_samples(raw_frames)
    assert dropped == 2 and drop_ids == [10, 13], f"trim failed: dropped={dropped} ids={drop_ids}"
    rows2, errs2 = validate_samples(kept)
    assert not errs2 and len(rows2) == 2, f"post-trim validate failed: {errs2} rows={rows2}"

    # Test 3: ADC saturation count
    sat_lines = [
        "V6.5,SID=00099,MID=0,FULL,SPWR=1,TXN=00",
        "CH1,RAW,128," + ",".join(["7FFF"] + ["0000"] * 127),
        "CH2,RAW,128," + ",".join(["8000", "8001"] + ["0000"] * 126),
    ]
    fr, err = parse_frame(sat_lines)
    assert err is None, f"sat parse failed: {err}"
    assert fr["saturated"] == 3, f"saturated count wrong: {fr['saturated']}"

    print("SELFTEST PASS: parse + sample validate + boundary trim + saturation count")
    return 0


# ── Main ──

def make_stem(sensor, condition, ts_str, suffix):
    parts = ["v65"]
    if sensor:
        parts.append(sensor)
    if condition:
        parts.append(condition)
    parts.append(ts_str)
    parts.append(suffix)
    return "_".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Capture V6.5 cycle-aware UART frames.")
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--samples", type=int, default=None,
                    help="Complete 5-mode samples to capture; maps to frames=samples*5")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out-dir", default="logs")
    ap.add_argument("--sensor", default=None)
    ap.add_argument("--condition", default=None)
    ap.add_argument("--no-trim", action="store_true",
                    help="Keep boundary half-samples (default: drop them)")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    if args.test:
        return run_self_test()
    if serial is None:
        raise SystemExit("pyserial is required for capture: pip install pyserial")
    if args.samples is not None:
        args.frames = args.samples * 5
    if args.frames is None:
        args.frames = 200

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    stem = make_stem(args.sensor, args.condition, ts_str, suffix)
    csv_path = out / f"{stem}.csv"
    npy_path = out / f"{stem}.npy"
    samples_path = out / f"{stem}_samples.csv"
    session_path = out / f"{stem}_session.json"
    errors_path = out / f"{stem}_errors.log"

    print(f"Sensor: {args.sensor or 'N/A'}  Condition: {args.condition or 'N/A'}  "
          f"Target: {args.frames} frames  Timeout: {args.timeout}s  Stem: {stem}")

    ser = serial.Serial(args.port, args.baud, timeout=0.01)
    try:
        ser.set_buffer_size(rx_size=256 * 1024)
    except AttributeError:
        pass

    frames = []
    errors_with_raw = []
    deadline = time.time() + args.timeout
    pending = []
    buf = b""
    recv_bytes = 0
    t0 = time.time()
    try:
        while len(frames) < args.frames and time.time() < deadline:
            chunk = ser.read(ser.in_waiting or 65536)
            if not chunk:
                continue
            buf += chunk
            recv_bytes += len(chunk)
            if len(buf) > 256 * 1024:
                buf = buf[-65536:]
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("ascii", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("V6."):
                    pending = [line]
                elif pending:
                    pending.append(line)
                    if len(pending) == 3:
                        fr, err = parse_frame(pending)
                        if err:
                            errors_with_raw.append({
                                "ts": dt.datetime.now().isoformat(),
                                "err": err,
                                "raw": list(pending),
                            })
                        else:
                            fr["_ts"] = dt.datetime.now().isoformat()
                            frames.append(fr)
                            if len(frames) >= args.frames:
                                buf = b""
                                break
                        pending = []
            n = len(frames)
            if n > 0 and n % 50 == 0:
                elapsed = time.time() - t0
                rate = n / elapsed if elapsed > 0 else 0
                eta = (args.frames - n) / rate if rate > 0 else 0
                print(f"  {n}/{args.frames} frames  {recv_bytes / 1024:.0f} KB  "
                      f"{rate:.0f} fps  ETA {eta:.0f}s")
    finally:
        ser.close()

    elapsed = time.time() - t0
    raw_frame_count = len(frames)

    # Back-fill legacy SIDs (no-op for pure V6.5)
    assign_legacy_sample_ids(frames)

    # Trim boundary half-samples by default
    if args.no_trim:
        kept, dropped, drop_ids = frames, 0, []
    else:
        kept, dropped, drop_ids = trim_boundary_samples(frames)

    # Write outputs
    write_meta_csv(csv_path, kept, args.sensor, args.condition)
    n_samples = write_npy_payload(npy_path, kept)
    sample_errors = write_samples_csv(samples_path, kept)
    write_errors_log(errors_path, errors_with_raw)

    counts = Counter(f["mode"] for f in kept)
    mode_str = "  ".join(f"{m}={counts.get(m, 0)}" for m in MODES)
    summary = {
        "raw_frames": raw_frame_count,
        "kept_frames": len(kept),
        "samples_written": n_samples,
        "boundary_dropped_samples": dropped,
        "boundary_dropped_sample_ids": drop_ids,
        "parse_errors": len(errors_with_raw),
        "sample_errors": len(sample_errors),
        "elapsed_seconds": round(elapsed, 2),
        "fps": round(raw_frame_count / elapsed, 1) if elapsed else 0,
        "saturated_total": sum(f.get("saturated", 0) for f in kept),
        "stem": stem,
    }
    write_session_json(session_path, args, collect_provenance(), summary)

    print(
        f"\nDONE  {raw_frame_count} frames in {elapsed:.1f}s  "
        f"{summary['fps']:.0f} fps  {mode_str}\n"
        f"  samples kept={n_samples}  dropped(boundary)={dropped}  "
        f"parse_errors={len(errors_with_raw)}  sample_errors={len(sample_errors)}  "
        f"saturated={summary['saturated_total']}"
    )
    print(f"CSV:     {csv_path}")
    print(f"NPY:     {npy_path}  shape=[{n_samples}, 5, 2, 128]")
    print(f"Samples: {samples_path}")
    print(f"Session: {session_path}")
    if errors_with_raw:
        print(f"Errors:  {errors_path}  ({len(errors_with_raw)} entries)")
    return 0 if (n_samples > 0 and not sample_errors) else 1


if __name__ == "__main__":
    sys.exit(main())
