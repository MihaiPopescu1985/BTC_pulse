#!/usr/bin/env python3
"""
Build daily_tx_size.json from the raw blk*.dat files, counting only blocks that
are on the main chain.

Steps:
  1. Run `crawl <file> stats` on every blk*.dat file. crawl prints one row per
     block: block hash, UTC day, transaction counts per size bucket. Each file's
     result is cached in <out>.cache/, so an interrupted run resumes where it
     stopped and later runs only parse new or grown files. (Finished blk files
     never change; the newest one grows while the node syncs, so a file is
     re-parsed when its size changes.)
  2. Load the main-chain hashes (mainchain_hashes.txt from dump_mainchain.py).
  3. Sum the bucket counts per day, using each main-chain block exactly once.
     Blocks that are not on the main chain (stale/orphan blocks) and repeated
     copies of the same block are skipped.

Usage:
    python3 build_daily_tx_size.py --crawl ./build/crawl \\
        --blocks /media/mihai/Expansion/bitcoin-data/blocks \\
        --mainchain mainchain_hashes.txt \\
        --out daily_tx_size.json

    --rebuild   ignore the cache and re-parse every file
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
CACHE_FORMAT = 1   # bump if the cached row format changes


def parse_file(crawl_bin, dat_file):
    """Run crawl in stats mode on one file. Returns a list of
    [block_hash, day, c0..c7] rows."""
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
    if not rows or rows[0][:2] != ["block_hash", "date"]:
        sys.stderr.write(
            f"\nUnexpected output from crawl on {dat_file}. "
            f"Is crawl rebuilt with the per-block stats backend?\n"
        )
        raise SystemExit(1)
    return rows[1:]


def write_json_atomic(path, obj, indent=None):
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_cached(cache_file, size):
    """Return cached rows if the cache entry matches the file's current size."""
    try:
        with open(cache_file) as f:
            entry = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if entry.get("format") != CACHE_FORMAT or entry.get("size") != size:
        return None
    return entry["rows"]


def load_mainchain(path):
    """Load main-chain hashes (one per line, line number = height)."""
    with open(path) as f:
        hashes = [line.strip().lower() for line in f if line.strip()]
    return hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", default="./build/crawl")
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--mainchain", required=True,
                    help="mainchain_hashes.txt produced by dump_mainchain.py")
    ap.add_argument("--out", default="daily_tx_size.json")
    ap.add_argument("--pattern", default="blk*.dat")
    ap.add_argument("--limit", type=int, default=0,
                    help="process only the first N files (testing)")
    ap.add_argument("--rebuild", action="store_true",
                    help="ignore the cache and re-parse every file")
    args = ap.parse_args()

    dat_files = sorted(Path(args.blocks).glob(args.pattern))
    if args.limit > 0:
        dat_files = dat_files[: args.limit]
    if not dat_files:
        sys.stderr.write(f"No files matching {args.pattern} in {args.blocks}\n")
        raise SystemExit(1)

    cache_dir = Path(str(args.out) + ".cache")
    cache_dir.mkdir(exist_ok=True)

    # --- 1. Parse (or load from cache) every file ----------------------------
    per_file = []   # list of row lists, in file order
    parsed = 0
    total = len(dat_files)
    for i, dat_file in enumerate(dat_files, 1):
        size = dat_file.stat().st_size
        cache_file = cache_dir / (dat_file.name + ".json")
        rows = None if args.rebuild else load_cached(cache_file, size)
        if rows is None:
            rows = parse_file(args.crawl, dat_file)
            write_json_atomic(cache_file, {"format": CACHE_FORMAT, "size": size, "rows": rows})
            parsed += 1
        per_file.append(rows)
        sys.stderr.write(f"\rFiles: {i}/{total} ({parsed} parsed, {i - parsed} from cache)  last: {dat_file.name}")
        sys.stderr.flush()
    sys.stderr.write("\n")

    # --- 2. Main chain --------------------------------------------------------
    mainchain = load_mainchain(args.mainchain)
    main_set = set(mainchain)

    # --- 3. Aggregate main-chain blocks, each exactly once -------------------
    daily = {}
    counted = set()
    seen_rows = orphan_rows = duplicate_rows = 0
    for rows in per_file:
        for row in rows:
            seen_rows += 1
            block_hash, day, counts = row[0], row[1], row[2:]
            if block_hash not in main_set:
                orphan_rows += 1
                continue
            if block_hash in counted:
                duplicate_rows += 1
                continue
            counted.add(block_hash)
            acc = daily.setdefault(day, [0] * NUM_BUCKETS)
            for b in range(NUM_BUCKETS):
                acc[b] += counts[b]

    missing = [h for h, block_hash in enumerate(mainchain) if block_hash not in counted]

    header = ["date"] + BUCKET_LABELS
    data = [header] + [[day] + daily[day] for day in sorted(daily)]
    write_json_atomic(args.out, data, indent=4)

    # --- Report ---------------------------------------------------------------
    sys.stderr.write(
        f"Blocks found in files : {seen_rows}\n"
        f"Counted (main chain)  : {len(counted)} of {len(mainchain)}\n"
        f"Skipped, not main     : {orphan_rows}\n"
        f"Skipped, duplicate    : {duplicate_rows}\n"
    )
    if missing:
        preview = ", ".join(str(h) for h in missing[:10])
        more = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
        sys.stderr.write(
            f"WARNING: {len(missing)} main-chain blocks were not found in the files.\n"
            f"         Heights: {preview}{more}\n"
            f"         Heights near the tip usually mean mainchain_hashes.txt is newer\n"
            f"         than the parsed files; anything else needs a look.\n"
        )
    sys.stderr.write(f"Wrote {args.out} with {len(daily)} days.\n")


if __name__ == "__main__":
    main()
