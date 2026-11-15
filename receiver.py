"""Receive local UDP packets, print interval counts, and save a CSV log."""
import argparse
import csv
from datetime import datetime
from pathlib import Path
import socket
import time

def run(port=9999):
    result_dir = Path(__file__).resolve().parent / "results"
    result_dir.mkdir(exist_ok=True)
    file_path = result_dir / ("receiver_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")
    print("=" * 62, flush=True)
    print("UDP RECEIVER | listening on 127.0.0.1:%d" % port, flush=True)
    print("Press Ctrl+C to stop.  Log: %s" % file_path, flush=True)
    print("=" * 62, flush=True)
    total = count = valid = 0
    begin = last = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, \
         file_path.open("w", encoding="utf-8-sig", newline="") as f:
        sock.bind(("127.0.0.1", port))
        sock.settimeout(.2)
        writer = csv.writer(f)
        writer.writerow(["elapsed_s", "received_pps", "cumulative_packets", "valid_project_packets"])
        try:
            while True:
                try:
                    data, addr = sock.recvfrom(2048)
                    count += 1
                    total += 1
                    if data.startswith(b"NTG1|"): valid += 1
                except socket.timeout:
                    pass
                now = time.monotonic()
                if now - last >= 1.0:
                    elapsed = round(now - begin, 1)
                    print(f"t={elapsed:5.1f}s | received={count:4d} pps | total={total:6d} | valid={valid:6d}", flush=True)
                    writer.writerow([elapsed, count, total, valid])
                    f.flush()
                    count = 0
                    last = now
        except KeyboardInterrupt:
            writer.writerow([round(time.monotonic()-begin,1), count, total, valid])
            print("\nReceiver stopped. Total received:", total, "Valid:", valid, flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    try:
        run(args.port)
    except OSError as exc:
        print("Cannot bind UDP port. Is another receiver already running?", exc)
