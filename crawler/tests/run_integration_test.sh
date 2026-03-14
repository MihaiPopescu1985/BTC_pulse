#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT_DIR/build/crawl"
FIXTURE="$ROOT_DIR/tests/blk01985.dat"
EXPECTED_HASH="78070080e4ccf544040086e706d537be6e4bb14debf3f5088561e87c879a88ab"

if [ ! -x "$BIN" ]; then
    echo "Integration test failed: binary not found at $BIN" >&2
    exit 1
fi

if [ ! -f "$FIXTURE" ]; then
    echo "Integration test failed: fixture not found at $FIXTURE" >&2
    exit 1
fi

OUT_FILE="$(mktemp /tmp/crawler-integration-out.XXXXXX)"
ERR_FILE="$(mktemp /tmp/crawler-integration-err.XXXXXX)"
TRUNCATED_FILE="$(mktemp /tmp/crawler-integration-truncated.XXXXXX.dat)"
TRUNCATED_OUT="$(mktemp /tmp/crawler-integration-truncated-out.XXXXXX)"
TRUNCATED_ERR="$(mktemp /tmp/crawler-integration-truncated-err.XXXXXX)"

cleanup() {
    rm -f "$OUT_FILE" "$ERR_FILE" "$TRUNCATED_FILE" "$TRUNCATED_OUT" "$TRUNCATED_ERR"
}
trap cleanup EXIT

"$BIN" "$FIXTURE" > "$OUT_FILE" 2> "$ERR_FILE"
ACTUAL_HASH="$(sha256sum "$OUT_FILE" | awk '{print $1}')"

if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
    echo "Integration test failed: output hash mismatch." >&2
    echo "  expected: $EXPECTED_HASH" >&2
    echo "  actual:   $ACTUAL_HASH" >&2
    exit 1
fi

cp "$FIXTURE" "$TRUNCATED_FILE"
truncate -s -100000 "$TRUNCATED_FILE"

set +e
"$BIN" "$TRUNCATED_FILE" > "$TRUNCATED_OUT" 2> "$TRUNCATED_ERR"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
    echo "Integration test failed: truncated dat should fail but returned 0." >&2
    exit 1
fi

echo "integration: all tests passed"
