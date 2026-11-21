#!/usr/bin/env python3
"""Two-session barrier runner for B-030 concurrency SEQ.

Modes: a_first | b_first | simultaneous
Uses threading.Barrier so both workers reach the critical call together
(or staggered by --delay-ms for ordered races).

Example:
  python3 barrier_runner.py --seq SEQ-01 --mode simultaneous \\
    --a-cmd 'curl ...' --b-cmd 'curl ...'
"""
from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs"


def run_worker(name: str, cmd: str, barrier: threading.Barrier, delay_ms: int, results: dict):
    try:
        barrier.wait(timeout=60)
        if delay_ms:
            time.sleep(delay_ms / 1000.0)
        started = time.time()
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        results[name] = {
            "returncode": p.returncode,
            "stdout": p.stdout[-4000:],
            "stderr": p.stderr[-2000:],
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except Exception as e:
        results[name] = {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--mode", choices=["a_first", "b_first", "simultaneous"], required=True)
    ap.add_argument("--a-cmd", required=True)
    ap.add_argument("--b-cmd", required=True)
    ap.add_argument("--delay-ms", type=int, default=50, help="stagger for a_first/b_first")
    args = ap.parse_args()

    delay_a = delay_b = 0
    if args.mode == "a_first":
        delay_b = args.delay_ms
    elif args.mode == "b_first":
        delay_a = args.delay_ms

    barrier = threading.Barrier(2)
    results: dict = {}
    t1 = threading.Thread(target=run_worker, args=("A", args.a_cmd, barrier, delay_a, results))
    t2 = threading.Thread(target=run_worker, args=("B", args.b_cmd, barrier, delay_b, results))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.seq}-{args.mode}.json"
    payload = {
        "seq": args.seq,
        "mode": args.mode,
        "results": results,
        "note": "Compare against concurrency/SEQ.md expected outcomes; do not mark pass without DB check",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", path)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "stdout"} for k, v in results.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
