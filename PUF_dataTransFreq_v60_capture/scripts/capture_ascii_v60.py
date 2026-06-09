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


def main():
    parser = argparse.ArgumentParser(description="Capture V6.1 ASCII UART frames.")
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

    frames = []
    errors = []
    pending = []
    deadline = time.time() + args.timeout

    print(f"Sensor: {args.sensor or 'N/A'}  Target: {args.frames} frames  Timeout: {args.timeout}s")
    ser = serial.Serial(args.port, args.baud, timeout=0.1)
    ser.set_buffer_size(rx_size=65536)
    try:
        leftover = ""
        while len(frames) < args.frames and time.time() < deadline:
            raw = ser.read(ser.in_waiting or 4096)
            if not raw:
                continue
            text = leftover + raw.decode("ascii", errors="replace")
            lines = text.split("\n")
            # last element may be incomplete — keep for next read
            leftover = lines.pop()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("V6."):
                    pending = [line]
                elif pending:
                    pending.append(line)
                    if len(pending) == 3:
                        frame, err = parse_frame(pending)
                        if err:
                            errors.append(err)
                        else:
                            frames.append(frame)
                        pending = []
    finally:
        ser.close()

        # Write CSV
        with csv_path.open("w", newline="", encoding="ascii") as f:
            writer = csv.writer(f)
            ch1_cols = [f"CH1_{i:03d}" for i in range(128)]
            ch2_cols = [f"CH2_{i:03d}" for i in range(128)]
            writer.writerow(["pc_time_iso", "type", "txn", "mode", "spwr"] + ch1_cols + ch2_cols)
            for frame in frames:
                row = [
                    dt.datetime.now().isoformat(),
                    "V60_RAW",
                    frame["txn"],
                    frame["mode"],
                    frame["sensor_power"],
                ] + [f"{v:04X}" for v in frame["ch1"]] + [f"{v:04X}" for v in frame["ch2"]]
                writer.writerow(row)

    from collections import Counter
    mode_counts = Counter(f["mode"] for f in frames)
    mode_str = "  ".join(f"{m}={c}" for m, c in sorted(mode_counts.items()))

    print(f"DONE: {len(frames)} frames  {mode_str}  errors={len(errors)}")
    print(f"CSV: {csv_path}")
    if errors:
        for err in errors[:3]:
            print(f"  skip: {err}")
    return 0 if frames else 1


if __name__ == "__main__":
    sys.exit(main())
