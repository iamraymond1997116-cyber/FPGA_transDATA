import argparse, csv, datetime as dt, pathlib, re, sys, time

try:
    import serial
except ImportError as exc:
    raise SystemExit("pyserial is required: pip install pyserial") from exc

HEADER_RE = re.compile(r"^V6\.[0-9],MODE=(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$")
RAW_RE = re.compile(r"^CH([12]),RAW,128,([0-9A-F]{4}(?:,[0-9A-F]{4}){127})$")


def parse_frame(lines):
    if len(lines) != 3:
        return None, f"expected 3 lines, got {len(lines)}"
    header_match = HEADER_RE.match(lines[0])
    if not header_match:
        return None, f"bad header: {lines[0]!r}"
    ch1_match = RAW_RE.match(lines[1])
    ch2_match = RAW_RE.match(lines[2])
    if not ch1_match or ch1_match.group(1) != "1":
        return None, f"bad CH1 line: {lines[1]!r}"
    if not ch2_match or ch2_match.group(1) != "2":
        return None, f"bad CH2 line: {lines[2]!r}"
    ch1_values = [int(x, 16) for x in ch1_match.group(2).split(",")]
    ch2_values = [int(x, 16) for x in ch2_match.group(2).split(",")]
    return {
        "mode": header_match.group(1),
        "sensor_power": int(header_match.group(2)),
        "txn": header_match.group(3),
        "ch1": ch1_values,
        "ch2": ch2_values,
    }, None


def write_csv(path, frames):
    with path.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        ch1_cols = [f"CH1_{i:03d}" for i in range(128)]
        ch2_cols = [f"CH2_{i:03d}" for i in range(128)]
        writer.writerow(["pc_time_iso", "type", "txn", "mode", "spwr"] + ch1_cols + ch2_cols)
        for i in range(0, len(frames), 100):
            batch = frames[i : i + 100]
            for frame in batch:
                row = [
                    frame["_ts"],
                    "V60_RAW",
                    frame["txn"],
                    frame["mode"],
                    frame["sensor_power"],
                ] + [f"{v:04X}" for v in frame["ch1"]] + [f"{v:04X}" for v in frame["ch2"]]
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Capture V6.3 ASCII UART frames (optimised).")
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out-dir", default="logs")
    parser.add_argument("--sensor", default=None, help="Sensor ID, e.g. B2-1")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sensor_tag = f"_{args.sensor}" if args.sensor else ""
    csv_path = out_dir / f"v60{sensor_tag}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    print(f"Sensor: {args.sensor or 'N/A'}  Target: {args.frames} frames  Timeout: {args.timeout}s")

    ser = serial.Serial(args.port, args.baud, timeout=0.005)
    ser.set_buffer_size(rx_size=256 * 1024)

    frames = []
    errors = []
    deadline = time.time() + args.timeout
    pending = []
    recv_bytes = 0
    t0 = time.time()

    try:
        while len(frames) < args.frames and time.time() < deadline:
            line = ser.read_until(b"\n")
            if not line:
                continue
            recv_bytes += len(line)
            try:
                line_str = line.decode("ascii").strip()
            except UnicodeDecodeError:
                continue
            if not line_str:
                continue

            if line_str.startswith("V6."):
                pending = [line_str]
            elif pending:
                pending.append(line_str)
                if len(pending) == 3:
                    frame, err = parse_frame(pending)
                    if err:
                        errors.append(err)
                    else:
                        frame["_ts"] = dt.datetime.now().isoformat()
                        frames.append(frame)
                    pending = []

            n = len(frames)
            if n > 0 and n % 50 == 0:
                elapsed = time.time() - t0
                rate = n / elapsed if elapsed > 0 else 0
                eta = (args.frames - n) / rate if rate > 0 else 0
                print(f"  {n}/{args.frames} frames  {recv_bytes/1024:.0f} KB  "
                      f"{rate:.0f} fps  ETA {eta:.0f}s")
    finally:
        ser.close()

    elapsed = time.time() - t0
    from collections import Counter
    mode_counts = Counter(f["mode"] for f in frames)
    mode_str = "  ".join(f"{m}={c}" for m, c in sorted(mode_counts.items()))

    write_csv(csv_path, frames)

    print(f"\nDONE  {len(frames)} frames in {elapsed:.1f}s  "
          f"{len(frames)/elapsed:.0f} fps  {mode_str}  errors={len(errors)}")
    print(f"CSV: {csv_path}")
    if errors:
        print(f"  first 3 errors:")
        for err in errors[:3]:
            print(f"    {err}")
    return 0 if frames else 1


if __name__ == "__main__":
    sys.exit(main())
