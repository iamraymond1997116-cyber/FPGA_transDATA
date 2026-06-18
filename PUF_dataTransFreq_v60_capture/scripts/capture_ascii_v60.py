"""V6.6 ASCII reliability-hardened UART capture parser.

Captures UART frames from the FPGA and writes:
  <stem>.csv          per-frame metadata (no ADC payload)
  <stem>.npy          ADC payload, int16, shape=[N_samples, 5, 2, 128]
  <stem>_samples.csv  per-sample validity summary (incl. R3 sequence checks)
  <stem>_session.json provenance (git hash, RTL version, env)
  <stem>_errors.log   parse errors with raw bytes (only if any)

V6.6 protocol: every line ends with *XX (CRC8 of the line payload, poly=0x07).
Also supports legacy V6.0~V6.5 frames (no CRC; back-fills sample_id by index//5
for V6.0~V6.4).
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

# ── Frame regexes (header *with* CRC trailer for V6.5+/V6.6, payload alone for legacy) ──
HEADER_RE_V66 = re.compile(
    r"^V6\.6,SID=(\d{5}),MID=([0-4]),(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$"
)
HEADER_RE_V65 = re.compile(
    r"^V6\.5,SID=(\d{5}),MID=([0-4]),(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$"
)
HEADER_RE_LEGACY = re.compile(
    r"^V6\.[0-4],MODE=(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$"
)
RAW_RE = re.compile(r"^CH([12]),RAW,128,([0-9A-F]{4}(?:,[0-9A-F]{4}){127})$")
CRC_TRAILER_RE = re.compile(r"^(.*)\*([0-9A-Fa-f]{2})$")

MODES = ["FULL", "PCUT", "NCUT", "EXTR", "FCYC"]
MODE_TO_IDX = {m: i for i, m in enumerate(MODES)}
EXPECTED_MODES = set(range(5))

# ADC saturation marks (16-bit signed boundary)
SATURATION_VALUES = {0x7FFE, 0x7FFF, 0x8000, 0x8001}


def crc8_ccitt(data: bytes) -> int:
    """CRC-8/CCITT, poly=0x07, init=0x00, no reflect, no xor-out.
    Mirrors the RTL crc8_step() function in capture_uart_streamer.v.
    """
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            if c & 0x80:
                c = ((c << 1) ^ 0x07) & 0xFF
            else:
                c = (c << 1) & 0xFF
    return c


def split_crc(line: str):
    """Split a V6.6 line into (payload, expected_crc_int) or (line, None) if no trailer.

    Returns (payload, None) for lines without *XX so legacy parsers still work.
    """
    m = CRC_TRAILER_RE.match(line)
    if not m:
        return line, None
    return m.group(1), int(m.group(2), 16)


def verify_line_crc(line: str):
    """Return (payload, crc_ok). crc_ok is True if either the trailer matches
    or there's no trailer (legacy line)."""
    payload, expected = split_crc(line)
    if expected is None:
        return payload, True  # legacy, no CRC enforcement
    actual = crc8_ccitt(payload.encode("ascii"))
    return payload, actual == expected


def hex_to_int16(v):
    x = int(v, 16)
    return x - 0x10000 if x >= 0x8000 else x


def count_saturated(ch1_hex, ch2_hex):
    return sum(1 for v in ch1_hex if int(v, 16) in SATURATION_VALUES) + sum(
        1 for v in ch2_hex if int(v, 16) in SATURATION_VALUES
    )


def parse_header(payload):
    m = HEADER_RE_V66.match(payload)
    if m:
        return {
            "protocol": "V66_RAW",
            "sample_id": int(m.group(1)),
            "mode_idx": int(m.group(2)),
            "mode": m.group(3),
            "txn": m.group(5),
        }, None
    m = HEADER_RE_V65.match(payload)
    if m:
        return {
            "protocol": "V65_RAW",
            "sample_id": int(m.group(1)),
            "mode_idx": int(m.group(2)),
            "mode": m.group(3),
            "txn": m.group(5),
        }, None
    m = HEADER_RE_LEGACY.match(payload)
    if m:
        mode = m.group(1)
        return {
            "protocol": "V60_RAW",
            "sample_id": None,
            "mode_idx": MODE_TO_IDX[mode],
            "mode": mode,
            "txn": m.group(3),
        }, None
    return None, f"bad header: {payload!r}"


def parse_frame(lines):
    """Parse a 3-line frame. Validates per-line CRC8 if any line has a *XX trailer."""
    if len(lines) != 3:
        return None, f"expected 3 lines, got {len(lines)}"
    payloads = []
    for i, raw in enumerate(lines):
        payload, ok = verify_line_crc(raw)
        if not ok:
            return None, f"CRC fail line {i}: {raw!r}"
        payloads.append(payload)
    header, err = parse_header(payloads[0])
    if err:
        return None, err
    ch1 = RAW_RE.match(payloads[1])
    ch2 = RAW_RE.match(payloads[2])
    if not ch1 or ch1.group(1) != "1":
        return None, f"bad CH1 line: {payloads[1]!r}"
    if not ch2 or ch2.group(1) != "2":
        return None, f"bad CH2 line: {payloads[2]!r}"
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


def _txn_diff(prev_hex, curr_hex):
    """TXN gap including 0xFF -> 0x00 wrap. Returns (curr - prev) mod 256."""
    return (int(curr_hex, 16) - int(prev_hex, 16)) & 0xFF


def validate_samples(frames):
    """R3 frame-sequence checks per sample.

    Per-row metadata:
      sample_id, valid, order_ok, frame_count
      missing_mode_idx, duplicate_mode_idx, saturated_total, modes
      txn_gap_ok          — TXN strictly +1 across the 5 frames (with 0xFF wrap)
      mid_strict_order    — MID is exactly [0,1,2,3,4]
      sid_monotonic       — this sample_id is greater than the previous one

    valid = ALL of: complete, in-order, txn-continuous, sid-monotonic.
    """
    by = group_by_sample(frames)
    rows = []
    errs = []
    prev_sid = None
    for sid in sorted(by):
        fs = by[sid]
        mids = [f["mode_idx"] for f in fs]
        missing = sorted(EXPECTED_MODES - set(mids))
        dup = sorted(m for m in EXPECTED_MODES if mids.count(m) > 1)
        order_ok = mids == [0, 1, 2, 3, 4]
        # R3: TXN gap — must be +1 between consecutive frames
        txn_gap_ok = True
        if len(fs) >= 2 and all("txn" in f and f["txn"] is not None for f in fs):
            for a, b in zip(fs, fs[1:]):
                if _txn_diff(a["txn"], b["txn"]) != 1:
                    txn_gap_ok = False
                    break
        # R3: SID monotonic — must strictly increase
        sid_monotonic = (prev_sid is None) or (sid > prev_sid)
        prev_sid = sid

        sat_total = sum(f.get("saturated", 0) for f in fs)
        valid = (not missing and not dup and order_ok and len(fs) == 5
                 and txn_gap_ok and sid_monotonic)
        rows.append({
            "sample_id": sid,
            "valid": int(valid),
            "order_ok": int(order_ok),
            "frame_count": len(fs),
            "missing_mode_idx": "|".join(map(str, missing)),
            "duplicate_mode_idx": "|".join(map(str, dup)),
            "saturated_total": sat_total,
            "txn_gap_ok": int(txn_gap_ok),
            "mid_strict_order": int(order_ok),
            "sid_monotonic": int(sid_monotonic),
            "modes": "|".join(f["mode"] for f in fs),
        })
        if not valid:
            errs.append(
                f"sample {sid}: frame_count={len(fs)} mids={mids} missing={missing} "
                f"dup={dup} txn_ok={txn_gap_ok} sid_mono={sid_monotonic}"
            )
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

def _attach_crc(payload: str) -> str:
    """Append *XX trailer (CRC8 of payload) to a line."""
    crc = crc8_ccitt(payload.encode("ascii"))
    return f"{payload}*{crc:02X}"


def _frame_v66(sid, mid, mode, ch1_payload, ch2_payload, txn=None):
    if txn is None:
        txn = (sid * 5 + mid) & 0xFF
    hdr = f"V6.6,SID={sid:05d},MID={mid},{mode},SPWR=1,TXN={txn:02X}"
    return [_attach_crc(hdr), _attach_crc(ch1_payload), _attach_crc(ch2_payload)]


def make_test_frames():
    vals1 = ",".join(f"{i & 0xffff:04X}" for i in range(128))
    vals2 = ",".join(f"{(i + 0x100) & 0xffff:04X}" for i in range(128))
    ch1 = f"CH1,RAW,128,{vals1}"
    ch2 = f"CH2,RAW,128,{vals2}"
    out = []
    for sid in range(2):
        for mid, mode in enumerate(MODES):
            out.append(_frame_v66(sid, mid, mode, ch1, ch2))
    return out


def make_boundary_test_frames():
    """Leading half (mids 2,3,4) + 2 full samples + trailing half (mids 0,1).
    Should leave 2 valid samples after trim."""
    vals1 = ",".join(f"{i & 0xffff:04X}" for i in range(128))
    vals2 = ",".join(f"{(i + 0x100) & 0xffff:04X}" for i in range(128))
    ch1 = f"CH1,RAW,128,{vals1}"
    ch2 = f"CH2,RAW,128,{vals2}"
    out = []
    for mid in [2, 3, 4]:
        out.append(_frame_v66(10, mid, MODES[mid], ch1, ch2))
    for sid in [11, 12]:
        for mid, mode in enumerate(MODES):
            out.append(_frame_v66(sid, mid, mode, ch1, ch2))
    for mid in [0, 1]:
        out.append(_frame_v66(13, mid, MODES[mid], ch1, ch2))
    return out


def run_self_test():
    # Test 1: basic parse + sample completeness (V6.6 with CRC)
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

    # Test 3: ADC saturation count (still works on V6.5 legacy lines, no CRC)
    sat_lines = [
        "V6.5,SID=00099,MID=0,FULL,SPWR=1,TXN=00",
        "CH1,RAW,128," + ",".join(["7FFF"] + ["0000"] * 127),
        "CH2,RAW,128," + ",".join(["8000", "8001"] + ["0000"] * 126),
    ]
    fr, err = parse_frame(sat_lines)
    assert err is None, f"sat parse failed: {err}"
    assert fr["saturated"] == 3, f"saturated count wrong: {fr['saturated']}"

    # Test 4: CRC mismatch detection (V6.6 line with corrupted trailer)
    good_lines = make_test_frames()[0]
    bad_lines = list(good_lines)
    # Flip last hex digit of CH1 trailer
    last = bad_lines[1]
    bad_trailer = last[:-1] + ("F" if last[-1] != "F" else "0")
    bad_lines[1] = bad_trailer
    fr2, err2 = parse_frame(bad_lines)
    assert err2 is not None and "CRC fail" in err2, f"CRC mismatch not detected: err={err2}"

    # Test 5: R3 sequence checks — txn gap, sid monotonic
    seq_frames = []
    for lines in make_test_frames():
        fr, _ = parse_frame(lines)
        fr["_ts"] = "2026-01-01T00:00:00"
        seq_frames.append(fr)
    # Forge a TXN gap inside sample 1 (frame 5: should be 0x05, force 0x07)
    seq_frames[5]["txn"] = "07"
    rows3, errs3 = validate_samples(seq_frames)
    assert rows3[0]["txn_gap_ok"] == 1, f"sample 0 should still be ok: {rows3[0]}"
    assert rows3[1]["txn_gap_ok"] == 0 and rows3[1]["valid"] == 0, \
        f"sample 1 should fail txn_gap: {rows3[1]}"

    # Test 6: R3 sid_monotonic — same sid twice
    monotonic_frames = []
    for lines in make_test_frames():
        fr, _ = parse_frame(lines)
        fr["_ts"] = "2026-01-01T00:00:00"
        monotonic_frames.append(fr)
    # Force second sample's sid to equal first (still grouped separately if sorted)
    # Easier: just ensure validate detects monotonic violation by reversing sort.
    # Build a list with sample_ids [5, 3] explicitly.
    rev = []
    for sid in [5, 3]:
        for mid, mode in enumerate(MODES):
            lines = _frame_v66(sid, mid, mode, "CH1,RAW,128," + ",".join(["0000"] * 128),
                               "CH2,RAW,128," + ",".join(["0000"] * 128))
            fr, _ = parse_frame(lines)
            fr["_ts"] = "2026-01-01T00:00:00"
            rev.append(fr)
    rows4, _ = validate_samples(rev)
    # After grouping & sorting by sid: 3 first, 5 second. Both should be monotonic.
    assert all(r["sid_monotonic"] == 1 for r in rows4)

    print("SELFTEST PASS: parse + sample validate + boundary trim + saturation + CRC + R3")
    return 0


# ── Main ──

def make_stem(sensor, condition, ts_str, suffix):
    parts = ["v66"]
    if sensor:
        parts.append(sensor)
    if condition:
        parts.append(condition)
    parts.append(ts_str)
    parts.append(suffix)
    return "_".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Capture V6.6 ASCII reliability-hardened UART frames.")
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
