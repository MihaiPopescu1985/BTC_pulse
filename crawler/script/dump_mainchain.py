#!/usr/bin/env python3
"""
Dump the main-chain block hashes (height 0 .. tip) to a text file, one hash per
line, index = height. Talks directly to bitcoind's JSON-RPC over the .cookie
auth, using a persistent HTTP connection and batched requests for speed.

The node must be running with its RPC server enabled: bitcoind enables it by
default, bitcoin-qt needs `server=1` in bitcoin.conf (or `-server`). Core writes
the .cookie at startup and deletes it on shutdown.

Usage:
    # datadir taken from ~/.bitcoin/bitcoin.conf, or ~/.bitcoin
    python3 dump_mainchain.py --out mainchain_hashes.txt

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
import os
import json
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


class RpcError(Exception):
    pass


class BitcoinRPC:
    def __init__(self, url, user, password, timeout=300):
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 8332
        import base64
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic " + token,
        }
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)

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


DEFAULT_CONF = Path.home() / ".bitcoin" / "bitcoin.conf"
DEFAULT_DATADIR = Path.home() / ".bitcoin"


def read_bitcoin_conf(conf_path):
    """Top-level settings from a bitcoin.conf, as a dict.

    Network sections ([main], [test], ...) are ignored: datadir and
    rpccookiefile are top-level-only options, so reading past the first section
    header would be wrong.
    """
    settings = {}
    try:
        lines = Path(conf_path).read_text().splitlines()
    except OSError:
        return settings
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            break
        if "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    return settings


def resolve_cookie_path(cookie_arg, datadir_arg):
    """Locate the .cookie. Explicit flags win, then bitcoin.conf, then the
    default datadir. Returns (path, where-it-came-from) for reporting."""
    if cookie_arg:
        return Path(cookie_arg), "--cookie"
    if datadir_arg:
        return Path(datadir_arg) / ".cookie", "--datadir"

    conf_path = Path(os.environ.get("BITCOIN_CONF", DEFAULT_CONF))
    settings = read_bitcoin_conf(conf_path)
    datadir = Path(settings["datadir"]) if "datadir" in settings else DEFAULT_DATADIR

    if "rpccookiefile" in settings:
        cookie = Path(settings["rpccookiefile"])
        if not cookie.is_absolute():
            cookie = datadir / cookie
        return cookie, f"rpccookiefile in {conf_path}"
    if "datadir" in settings:
        return datadir / ".cookie", f"datadir in {conf_path}"
    return datadir / ".cookie", "default datadir"


def read_cookie(cookie_path):
    try:
        text = Path(cookie_path).read_text().strip()
    except FileNotFoundError:
        raise RpcError(
            f"No cookie file at {cookie_path}.\n"
            "Bitcoin Core writes it at startup and removes it on shutdown, so the\n"
            "node must be running with its RPC server enabled:\n"
            "  bitcoind   enables RPC by default\n"
            "  bitcoin-qt needs server=1 in bitcoin.conf, or -server on the command line\n"
            "Pass --cookie/--datadir if the cookie lives somewhere else."
        )
    except OSError as exc:
        raise RpcError(f"Cannot read cookie file {cookie_path}: {exc}")
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
    ap.add_argument("--timeout", type=int, default=300,
                    help="seconds to wait per RPC request. A syncing node holds "
                         "cs_main while validating, so chain calls can queue for "
                         "minutes (default 300)")
    args = ap.parse_args()

    cookie_path, source = resolve_cookie_path(args.cookie, args.datadir)
    sys.stderr.write(f"Using cookie {cookie_path} (from {source})\n")

    try:
        user, password = read_cookie(cookie_path)
    except RpcError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1)

    rpc = BitcoinRPC(args.rpc, user, password, timeout=args.timeout)

    try:
        tip = args.end if args.end >= 0 else rpc.call_single("getblockcount")
    except socket.timeout:
        sys.stderr.write(
            f"No reply from {args.rpc} within {args.timeout}s.\n"
            "The RPC server is listening but busy: a node in initial block download\n"
            "holds cs_main while it validates, so getblockcount/getblockhash queue\n"
            "behind it (check `uptime`, which needs no lock, to confirm RPC is up).\n"
            "Either wait for the sync to finish, pause it with\n"
            "`bitcoin-cli setnetworkactive false` while you dump, or raise --timeout.\n"
        )
        raise SystemExit(1)
    except OSError as exc:
        sys.stderr.write(
            f"Cannot reach the RPC server at {args.rpc}: {exc}\n"
            "Nothing is listening there. bitcoin-qt only serves RPC with server=1 in\n"
            "bitcoin.conf (or -server); check rpcport/rpcbind too.\n"
        )
        raise SystemExit(1)
    except RpcError as exc:
        sys.stderr.write(
            f"RPC call failed: {exc}\n"
            "A 503 here means the node is still loading the block index; retry once\n"
            "it finishes starting up.\n"
        )
        raise SystemExit(1)
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