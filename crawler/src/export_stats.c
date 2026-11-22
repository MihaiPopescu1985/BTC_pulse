// Stats export backend.
//
// Emits one row per block: the block hash, the block's UTC day, and how many of
// the block's transactions fall into each output-total size bucket. Rows are
// written as a JSON document on flush (end of the .dat file):
//
//   [
//       ["block_hash", "date", "0-0.001 BTC", ... , "1000+ BTC"],
//       ["000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f", "2009-01-03", 0, 0, 0, 0, 0, 1, 0, 0],
//       ...
//   ]
//
// The block hash is printed exactly like bitcoind's RPC prints it (lowercase hex,
// display byte order), so it can be matched against the main-chain hash list
// produced by dump_mainchain.py. Per-day aggregation, de-duplication and
// filtering out blocks that are not on the main chain happen in
// build_daily_tx_size.py.
//
// The size of a transaction is the sum of its output amounts in satoshi, the
// same definition as _build_tx_size_query in the old Python pipeline. The day is
// date(block_time, 'unixepoch'), the UTC calendar day of the block timestamp.

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

#include "block_common.h"

#define NUM_BUCKETS 8

// Bucket lower bounds in satoshi; a bucket ends where the next one starts and
// the last bucket is open-ended. Mirrors TX_SIZE_BUCKETS in query.py.
static const uint64_t BUCKET_LOWER[NUM_BUCKETS] = {
    0ULL,
    100000ULL,
    1000000ULL,
    10000000ULL,
    100000000ULL,
    1000000000ULL,
    10000000000ULL,
    100000000000ULL
};

static const char *BUCKET_LABELS[NUM_BUCKETS] = {
    "0-0.001 BTC",
    "0.001-0.01 BTC",
    "0.01-0.1 BTC",
    "0.1-1 BTC",
    "1-10 BTC",
    "10-100 BTC",
    "100-1000 BTC",
    "1000+ BTC"
};

// --- Per-block state ---------------------------------------------------------

static uint64_t CURRENT_BLOCK_TIME = 0;
static uint8_t CURRENT_BLOCK_HASH[32];
static uint64_t CURRENT_BLOCK_TX_COUNT = 0;     // transactions the block declares
static uint64_t CURRENT_BLOCK_TX_DONE = 0;      // transactions parsed so far
static uint64_t CURRENT_BLOCK_COUNTS[NUM_BUCKETS];

// Running total of the current transaction's output amounts, in satoshi.
static uint64_t CURRENT_TX_TOTAL = 0;

// Whether the JSON header row has been written for this file.
static int HEADER_WRITTEN = 0;

static int bucket_for_amount(uint64_t total)
{
    for (int i = NUM_BUCKETS - 1; i >= 0; i--) {
        if (total >= BUCKET_LOWER[i]) {
            return i;
        }
    }
    return 0;
}

static void write_all(const char *buffer, size_t length)
{
    size_t offset = 0;
    while (offset < length) {
        ssize_t written = write(STDOUT_FILENO, buffer + offset, length - offset);
        if (written <= 0) break;
        offset += (size_t) written;
    }
}

static void append_str(const char *s)
{
    size_t len = strlen(s);
    _resize_block(len);
    _append_char((char *) s, len);
}

static void write_header_row(void)
{
    append_str("[\n    [\"block_hash\", \"date\"");
    for (int b = 0; b < NUM_BUCKETS; b++) {
        append_str(", \"");
        append_str(BUCKET_LABELS[b]);
        append_str("\"");
    }
    append_str("]");
    HEADER_WRITTEN = 1;
}

// Append the finished block's row to the output buffer.
static void emit_block_row(void)
{
    static const char HEX[] = "0123456789abcdef";

    if (!HEADER_WRITTEN) write_header_row();

    char hash_hex[65];
    for (int i = 0; i < 32; i++) {
        hash_hex[2 * i] = HEX[(CURRENT_BLOCK_HASH[i] >> 4) & 0x0F];
        hash_hex[2 * i + 1] = HEX[CURRENT_BLOCK_HASH[i] & 0x0F];
    }
    hash_hex[64] = '\0';

    time_t t = (time_t) CURRENT_BLOCK_TIME;
    struct tm tm_utc;
    gmtime_r(&t, &tm_utc);
    char day[11];
    strftime(day, sizeof(day), "%Y-%m-%d", &tm_utc);

    append_str(",\n    [\"");
    append_str(hash_hex);
    append_str("\", \"");
    append_str(day);
    append_str("\"");

    char num[24];
    for (int b = 0; b < NUM_BUCKETS; b++) {
        snprintf(num, sizeof(num), ", %llu",
                 (unsigned long long) CURRENT_BLOCK_COUNTS[b]);
        append_str(num);
    }
    append_str("]");
}

// --- Callbacks ---------------------------------------------------------------

// Header
void stats_export_magic_number(uint8_t magic_bytes[4]) { (void) magic_bytes; }
void stats_export_block_size(uint8_t block_size[4]) { (void) block_size; }
void stats_export_header_version(uint8_t header_version[4]) { (void) header_version; }
void stats_export_prev_hash(uint8_t prev_hash[32]) { (void) prev_hash; }
void stats_export_merkle_root(uint8_t merkle_root[32]) { (void) merkle_root; }

void stats_export_block_time(uint8_t block_time[4])
{
    uint64_t time = block_time[3];
    time = time << 8 | block_time[2];
    time = time << 8 | block_time[1];
    time = time << 8 | block_time[0];

    CURRENT_BLOCK_TIME = time;
}

void stats_export_nbytes(uint8_t nbyes[4]) { (void) nbyes; }
void stats_export_nonce(uint8_t nonce[4]) { (void) nonce; }

void stats_export_block_hash(unsigned char block_hash[32])
{
    // A new block starts: remember its hash and reset its counters.
    memcpy(CURRENT_BLOCK_HASH, block_hash, 32);
    memset(CURRENT_BLOCK_COUNTS, 0, sizeof(CURRENT_BLOCK_COUNTS));
    CURRENT_BLOCK_TX_COUNT = 0;
    CURRENT_BLOCK_TX_DONE = 0;
}

// Transaction count
void stats_export_transaction_count(uint64_t tx_count)
{
    CURRENT_BLOCK_TX_COUNT = tx_count;
}

// Transaction
void stats_export_tx_version(uint8_t tx_version[4]) { (void) tx_version; }

// Transaction input
void stats_export_flag(uint8_t flag) { (void) flag; }
void stats_export_tx_in_count(uint64_t tx_in_count) { (void) tx_in_count; }
void stats_export_tx_id(uint8_t tx_id[32]) { (void) tx_id; }
void stats_export_input_vout(uint8_t vout[4]) { (void) vout; }
void stats_export_script_sig_size(uint64_t script_sig_size) { (void) script_sig_size; }
void stats_export_script_sig(uint8_t *script_sig) { (void) script_sig; }
void stats_export_tx_in_sequence(uint8_t tx_in_sequence[4]) { (void) tx_in_sequence; }

// Transaction output
void stats_export_tx_out_count(uint64_t tx_out_count)
{
    (void) tx_out_count;
    CURRENT_TX_TOTAL = 0;   // a new transaction's outputs follow
}

void stats_export_amount(uint8_t amount[8])
{
    uint64_t amt = amount[7];
    amt = amt << 8 | amount[6];
    amt = amt << 8 | amount[5];
    amt = amt << 8 | amount[4];
    amt = amt << 8 | amount[3];
    amt = amt << 8 | amount[2];
    amt = amt << 8 | amount[1];
    amt = amt << 8 | amount[0];

    CURRENT_TX_TOTAL += amt;
}

void stats_export_pub_key_size(uint64_t pub_key_size) { (void) pub_key_size; }
void stats_export_script_pub_key(uint8_t *script_pub_key) { (void) script_pub_key; }

// Transaction witness
void stats_export_stack_items_count(uint64_t stack_items) { (void) stack_items; }
void stats_export_stack_item_size(uint64_t size) { (void) size; }
void stats_export_to_stack(uint8_t *to_stack) { (void) to_stack; }
void stats_export_witness(uint8_t *witness, uint64_t witness_size) { (void) witness; (void) witness_size; }
void stats_export_lock_time(uint8_t lock_time[4]) { (void) lock_time; }

void stats_export_tx_hash(uint8_t tx_hash[32])
{
    (void) tx_hash;
    // End of a transaction: CURRENT_TX_TOTAL holds the sum of its outputs.
    CURRENT_BLOCK_COUNTS[bucket_for_amount(CURRENT_TX_TOTAL)]++;
    CURRENT_BLOCK_TX_DONE++;

    // Last transaction of the block: the block's row is complete.
    if (CURRENT_BLOCK_TX_DONE == CURRENT_BLOCK_TX_COUNT) {
        emit_block_row();
    }
}

void stats_export_flush(void)
{
    // Always produce valid JSON, even for a file with no complete block.
    if (!HEADER_WRITTEN) write_header_row();
    append_str("\n]\n");

    write_all(PARSED_BLOCK, (size_t) PARSED_BLOCK_INDEX);
    _reset();
    HEADER_WRITTEN = 0;
}
