#!/usr/bin/env python3
"""
Drive `crawl <file> stats` over every blk*.dat file and combine the per-file
partial JSON outputs into a single daily_tx_size.json.

Resumable: progress is checkpointed after every file, so if the run is
interrupted (Ctrl+C, power loss, crash) it can be restarted and picks up where
it left off instead of re-parsing everything.

crawl auto-loads the XOR obfuscation key from blocks/xor.dat, so no extra flags
are needed for Bitcoin Core v28+ obfuscated block files.

Usage:
    python3 build_daily_tx_size.py --crawl ./build/crawl \
        --blocks /media/mihai/Expansion/bitcoin-data/blocks \
        --out daily_tx_size.json

To force a clean run (ignore any existing checkpoint):
    python3 build_daily_tx_size.py ... --restart
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BUCKET_LABELS = [
    "0-0.001 BTC", "0.001-0.01 BTC", "0.01-0.1 BTC", "0.1-1 BTC",
    "1-10 BTC", "10-100 BTC", "100-1000 BTC", "1000+ BTC",
]
NUM_BUCKETS = len(BUCKET_LABELS)


def process_file(crawl_bin, dat_file):
    """Run crawl in stats mode on one .dat file, return {day: [counts...]}."""
    proc = subprocess.run([crawl_bin, str(dat_file), "stats"], capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(
            f"\ncrawl failed on {dat_file} (exit {proc.returncode}):\n"
            f"{proc.stderr.decode(errors='replace')}\n"
        )
        raise SystemExit(1)
    try:
        rows = json.loads(proc.stdout.decode())
    except json.JSONDecodeError as e:
        sys.stderr.write(f"\nBad JSON from crawl on {dat_file}: {e}\n")
        raise SystemExit(1)
    return {row[0]: row[1:] for row in rows[1:]}


def checkpoint_path(out_path):
    return str(out_path) + ".checkpoint.json"


def load_checkpoint(cp_path):
    """Return (daily_dict, set_of_done_filenames) or (None, None) if absent/unreadable."""
    if not os.path.exists(cp_path):
        return None, None
    try:
        with open(cp_path) as f:
            state = json.load(f)
        daily = {day: list(counts) for day, counts in state["daily"].items()}
        done = set(state["done"])
        return daily, done
    except (json.JSONDecodeError, KeyError, OSError) as e:
        sys.stderr.write(f"Warning: could not read checkpoint ({e}); starting fresh.\n")
        return None, None


def save_checkpoint_atomic(cp_path, daily, done):
    """Write the checkpoint atomically: temp file + os.replace (crash-safe)."""
    tmp = cp_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"daily": daily, "done": sorted(done)}, f)
        f.flush()
        os.fsync(f.fileno())          # force to disk before the rename
    os.replace(tmp, cp_path)          # atomic on the same filesystem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", default="./build/crawl")
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--out", default="daily_tx_size.json")
    ap.add_argument("--pattern", default="blk*.dat")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--restart", action="store_true",
                    help="ignore any existing checkpoint and start over")
    ap.add_argument("--checkpoint-every", type=int, default=1,
                    help="save progress every N files (default: 1)")
    args = ap.parse_args()

    dat_files = sorted(Path(args.blocks).glob(args.pattern))
    if args.limit > 0:
        dat_files = dat_files[: args.limit]
    if not dat_files:
        sys.stderr.write(f"No files matching {args.pattern} in {args.blocks}\n")
        raise SystemExit(1)

    cp_path = checkpoint_path(args.out)

    # Resume from checkpoint unless told to restart.
    if args.restart and os.path.exists(cp_path):
        os.remove(cp_path)
        sys.stderr.write("Removed existing checkpoint (--restart).\n")

    daily, done = load_checkpoint(cp_path)
    if daily is None:
        daily, done = {}, set()
    else:
        sys.stderr.write(
            f"Resuming from checkpoint: {len(done)} files already processed.\n"
        )

    total = len(dat_files)
    processed_this_run = 0

    for i, dat_file in enumerate(dat_files, 1):
        name = dat_file.name
        if name in done:
            continue  # already accounted for in a previous run

        partial = process_file(args.crawl, dat_file)
        for day, counts in partial.items():
            acc = daily.setdefault(day, [0] * NUM_BUCKETS)
            for b in range(NUM_BUCKETS):
                acc[b] += counts[b]

        done.add(name)
        processed_this_run += 1

        if processed_this_run % args.checkpoint_every == 0:
            save_checkpoint_atomic(cp_path, daily, done)

        if i % 50 == 0 or i == total:
            sys.stderr.write(f"\rProcessed {len(done)}/{total} files...")
            sys.stderr.flush()

    sys.stderr.write("\n")

    # Final save of the checkpoint (covers the tail if checkpoint_every > 1).
    save_checkpoint_atomic(cp_path, daily, done)

    # Write the final, sorted output.
    header = ["date"] + BUCKET_LABELS
    data = [header] + [[day] + daily[day] for day in sorted(daily)]
    # Atomic write of the final file too.
    tmp_out = str(args.out) + ".tmp"
    Path(tmp_out).write_text(json.dumps(data, indent=4))
    os.replace(tmp_out, args.out)

    sys.stderr.write(f"Wrote {args.out} with {len(daily)} days.\n")

    # Success: the checkpoint is no longer needed.
    if os.path.exists(cp_path):
        os.remove(cp_path)
        sys.stderr.write("Run complete; checkpoint removed.\n")


if __name__ == "__main__":
    main()
