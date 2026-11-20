#!/usr/bin/env python3
"""
Dump the main-chain block hashes (height 0 .. tip) to a text file, one hash per
line, index = height. Talks directly to bitcoind's JSON-RPC over the .cookie
auth, using a persistent HTTP connection and batched requests for speed.

Usage:
    python3 dump_mainchain.py \
        --datadir /media/mihai/Expansion/bitcoin-data \
        --out mainchain_hashes.txt

    # or give an explicit rpc endpoint / auth:
    python3 dump_mainchain.py --rpc http://127.0.0.1:8332 \
        --cookie /media/mihai/Expansion/bitcoin-data/.cookie --out mainchain_hashes.txt

Options:
    --batch N     how many getblockhash calls per RPC round-trip (default 2000)
    --start H     first height to fetch (default 0)
    --end H       last height (default: getblockcount)
"""
import argparse
import http.client
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


class RpcError(Exception):
    pass


class BitcoinRPC:
    def __init__(self, url, user, password):
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 8332
        import base64
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic " + token,
        }
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=120)

    def call_single(self, method, params=None):
        payload = json.dumps({
            "jsonrpc": "1.0", "id": "poc", "method": method,
            "params": params or [],
        })
        self.conn.request("POST", "/", payload, self.headers)
        resp = self.conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise RpcError(f"HTTP {resp.status}: {body[:200]!r}")
        data = json.loads(body)
        if data.get("error"):
            raise RpcError(str(data["error"]))
        return data["result"]

    def call_batch(self, method, params_list):
        """Send many calls in one HTTP request. Returns results in order."""
        batch = [
            {"jsonrpc": "1.0", "id": i, "method": method, "params": p}
            for i, p in enumerate(params_list)
        ]
        payload = json.dumps(batch)
        self.conn.request("POST", "/", payload, self.headers)
        resp = self.conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise RpcError(f"HTTP {resp.status}: {body[:200]!r}")
        data = json.loads(body)
        # Responses can come back out of order; sort by id.
        out = [None] * len(params_list)
        for item in data:
            if item.get("error"):
                raise RpcError(str(item["error"]))
            out[item["id"]] = item["result"]
        return out

    def close(self):
        self.conn.close()


def read_cookie(cookie_path):
    text = Path(cookie_path).read_text().strip()
    if ":" not in text:
        raise RpcError(f"Malformed cookie file: {cookie_path}")
    user, password = text.split(":", 1)
    return user, password


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", help="bitcoin datadir (to find .cookie)")
    ap.add_argument("--cookie", help="explicit path to .cookie")
    ap.add_argument("--rpc", default="http://127.0.0.1:8332", help="RPC endpoint")
    ap.add_argument("--out", default="mainchain_hashes.txt")
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=-1)
    args = ap.parse_args()

    # Resolve cookie
    cookie_path = args.cookie
    if not cookie_path and args.datadir:
        cookie_path = str(Path(args.datadir) / ".cookie")
    if not cookie_path:
        sys.stderr.write("Need --cookie or --datadir to authenticate.\n")
        raise SystemExit(1)

    user, password = read_cookie(cookie_path)
    rpc = BitcoinRPC(args.rpc, user, password)

    tip = args.end if args.end >= 0 else rpc.call_single("getblockcount")
    start = args.start
    sys.stderr.write(f"Fetching main-chain hashes for heights {start}..{tip} "
                     f"(batch={args.batch})\n")

    t0 = time.time()
    hashes = [None] * (tip - start + 1)
    h = start
    while h <= tip:
        hi = min(h + args.batch - 1, tip)
        params_list = [[height] for height in range(h, hi + 1)]
        results = rpc.call_batch("getblockhash", params_list)
        for offset, res in enumerate(results):
            hashes[h - start + offset] = res
        h = hi + 1
        elapsed = time.time() - t0
        done = h - start
        rate = done / elapsed if elapsed > 0 else 0
        sys.stderr.write(f"\r{done}/{tip - start + 1} hashes  "
                         f"({rate:.0f}/s, {elapsed:.1f}s elapsed)")
        sys.stderr.flush()
    sys.stderr.write("\n")

    rpc.close()

    # Write one hash per line; line number (0-based) == height.
    with open(args.out, "w") as f:
        f.write("\n".join(hashes))
        f.write("\n")

    total = time.time() - t0
    sys.stderr.write(f"Wrote {len(hashes)} hashes to {args.out} in {total:.1f}s\n")


if __name__ == "__main__":
    main()