#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT_DIR/build/crawl"
FIXTURE="$ROOT_DIR/tests/blk01985.dat"
# Core v28+ obfuscates blk*.dat; the 8-byte key lives in blocks/xor.dat, which
# must be copied next to the fixture. Tied to the current fixture: re-baseline
# with `./build/crawl tests/blk01985.dat | sha256sum` if the fixture changes.
KEY_FILE="$ROOT_DIR/tests/xor.dat"
EXPECTED_HASH="9d67c41aa09cd7592f53e0aef8e3f63a13eef5d3b5f01f620aced5f1f86c5ffc"

if [ ! -x "$BIN" ]; then
    echo "Integration test failed: binary not found at $BIN" >&2
    exit 1
fi

if [ ! -f "$FIXTURE" ]; then
    echo "Integration test failed: fixture not found at $FIXTURE" >&2
    exit 1
fi

# Each pass writes ~200 MB of SQL here; set TMPDIR to move it off /tmp.
TMP_BASE="${TMPDIR:-/tmp}"
OUT_FILE="$(mktemp "$TMP_BASE/crawler-integration-out.XXXXXX")"
ERR_FILE="$(mktemp "$TMP_BASE/crawler-integration-err.XXXXXX")"
TRUNCATED_DIR="$(mktemp -d "$TMP_BASE/crawler-integration-truncated.XXXXXX")"
TRUNCATED_FILE="$TRUNCATED_DIR/blk-truncated.dat"
TRUNCATED_OUT="$(mktemp "$TMP_BASE/crawler-integration-truncated-out.XXXXXX")"
TRUNCATED_ERR="$(mktemp "$TMP_BASE/crawler-integration-truncated-err.XXXXXX")"

cleanup() {
    rm -rf "$OUT_FILE" "$ERR_FILE" "$TRUNCATED_DIR" "$TRUNCATED_OUT" "$TRUNCATED_ERR"
}
trap cleanup EXIT

FIXTURE_MIB=$(( $(stat -c %s "$FIXTURE") / 1024 / 1024 ))
echo "integration: parsing fixture (${FIXTURE_MIB} MiB) in sql mode, takes a few minutes..."

set +e
"$BIN" "$FIXTURE" > "$OUT_FILE" 2> "$ERR_FILE"
RC=$?
set -e

# Surface the crawler's own diagnostics; set -e alone would abort silently and
# the stderr file is deleted on exit.
if [ "$RC" -ne 0 ]; then
    echo "Integration test failed: crawl exited $RC on the fixture." >&2
    sed 's/^/  /' "$ERR_FILE" >&2
    exit 1
fi

ACTUAL_HASH="$(sha256sum "$OUT_FILE" | awk '{print $1}')"

if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
    echo "Integration test failed: output hash mismatch." >&2
    echo "  expected: $EXPECTED_HASH" >&2
    echo "  actual:   $ACTUAL_HASH" >&2
    exit 1
fi

echo "integration: sql output hash matches"
echo "integration: parsing a truncated copy, expecting a non-zero exit..."

cp "$FIXTURE" "$TRUNCATED_FILE"
# The key is loaded from xor.dat next to the .dat file, so the copy needs its
# own. Without it the run would fail on the very first magic number and this
# check would pass without ever exercising truncated block data.
if [ -f "$KEY_FILE" ]; then
    cp "$KEY_FILE" "$TRUNCATED_DIR/xor.dat"
fi
truncate -s -100000 "$TRUNCATED_FILE"

set +e
"$BIN" "$TRUNCATED_FILE" > "$TRUNCATED_OUT" 2> "$TRUNCATED_ERR"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
    echo "Integration test failed: truncated dat should fail but returned 0." >&2
    exit 1
fi

# It must fail on the truncated block data, not on byte 1: a failure there means
# the copy was read without its obfuscation key, which would make the check above
# pass for the wrong reason.
if grep -qx "At byte 1" "$TRUNCATED_ERR"; then
    echo "Integration test failed: truncated run stopped on the first magic number, so truncated block data was never parsed." >&2
    sed 's/^/  /' "$TRUNCATED_ERR" >&2
    exit 1
fi

echo "integration: all tests passed"
