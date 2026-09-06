// Stats export backend.
//
// Instead of emitting SQL, this backend accumulates, per UTC day, the number of
// transactions falling into each predefined output-total size bucket, then emits
// a partial JSON document on flush (end of the .dat file).
//
// The size of a transaction is defined exactly as in the old Python pipeline's
// _build_tx_size_query: the sum of that transaction's output amounts, in satoshi.
// The day is date(block_time, 'unixepoch') -> the UTC calendar day of the block
// timestamp.
//
// Output format matches export_daily_tx_sizes exactly:
//   [
//       ["date", "0-0.001 BTC", "0.001-0.01 BTC", ... , "1000+ BTC"],
//       ["2009-01-03", 1, 0, 0, 0, 0, 0, 0, 0],
//       ...
//   ]
// Because one .dat file may contain days that also appear in a neighbouring file,
// these partials are combined afterwards by a small Python script (sum per day).

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

#include "block_common.h"

#define NUM_BUCKETS 8

// Bucket lower bounds in satoshi (upper bound is the next bucket's lower bound;
// the last bucket has no upper bound). Mirrors TX_SIZE_BUCKETS in query.py.
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

// --- Per-day accumulator -----------------------------------------------------

typedef struct {
    int32_t day;                     // days since the Unix epoch (UTC)
    uint64_t counts[NUM_BUCKETS];    // tx counts per bucket for that day
} day_entry;

static day_entry *DAYS = NULL;
static size_t DAYS_LEN = 0;
static size_t DAYS_CAP = 0;

// Current block timestamp (set by stats_export_block_time).
static uint64_t CURRENT_BLOCK_TIME = 0;

// Running total of the current transaction's output amounts, in satoshi.
static uint64_t CURRENT_TX_TOTAL = 0;

// Find or create the accumulator entry for a given UTC day index.
// DAYS is kept sorted by day, so we can binary-search and insert in order.
static day_entry *get_day_entry(int32_t day)
{
    // Binary search for `day`.
    size_t lo = 0;
    size_t hi = DAYS_LEN;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (DAYS[mid].day < day) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    if (lo < DAYS_LEN && DAYS[lo].day == day) {
        return &DAYS[lo];
    }

    // Need to insert a new entry at position `lo`.
    if (DAYS_LEN == DAYS_CAP) {
        size_t new_cap = (DAYS_CAP == 0) ? 64 : DAYS_CAP * 2;
        day_entry *grown = (day_entry *) realloc(DAYS, new_cap * sizeof(day_entry));
        if (grown == NULL) {
            perror("Error resizing DAYS accumulator");
            exit(1);
        }
        DAYS = grown;
        DAYS_CAP = new_cap;
    }

    memmove(&DAYS[lo + 1], &DAYS[lo], (DAYS_LEN - lo) * sizeof(day_entry));
    DAYS[lo].day = day;
    memset(DAYS[lo].counts, 0, sizeof(DAYS[lo].counts));
    DAYS_LEN++;

    return &DAYS[lo];
}

static int bucket_for_amount(uint64_t total)
{
    // Highest bucket whose lower bound is <= total. Buckets are contiguous and
    // ascending, so walk from the top.
    for (int i = NUM_BUCKETS - 1; i >= 0; i--) {
        if (total >= BUCKET_LOWER[i]) {
            return i;
        }
    }
    return 0; // total == 0 lands in bucket 0 ([0, 100000))
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
void stats_export_block_hash(unsigned char block_hash[32]) { (void) block_hash; }

// Transaction count
void stats_export_transaction_count(uint64_t tx_count) { (void) tx_count; }

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
    // A new transaction's outputs are about to be parsed: reset the running total.
    CURRENT_TX_TOTAL = 0;
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
    // End of a transaction: CURRENT_TX_TOTAL now holds the sum of its outputs.
    // Attribute it to the block's UTC day and the appropriate size bucket.
    int32_t day = (int32_t) (CURRENT_BLOCK_TIME / 86400ULL);
    day_entry *entry = get_day_entry(day);
    int bucket = bucket_for_amount(CURRENT_TX_TOTAL);
    entry->counts[bucket]++;
}

// Convert a day index (days since epoch) to "YYYY-MM-DD" (UTC), matching
// SQLite's date(..., 'unixepoch').
static void format_day(int32_t day, char *out /* at least 11 bytes */)
{
    time_t t = (time_t) day * 86400;
    struct tm tm_utc;
    gmtime_r(&t, &tm_utc);
    // strftime is safe here; small fixed output.
    strftime(out, 11, "%Y-%m-%d", &tm_utc);
}

void stats_export_flush(void)
{
    // Emit the partial JSON document to stdout.
    // Header row.
    _reset();

    // Rough upper bound per line; _resize_block grows as needed anyway.
    _resize_block(256);
    _append_char("[\n    [\"date\"", 13);
    for (int b = 0; b < NUM_BUCKETS; b++) {
        _append_char(", \"", 3);
        size_t len = strlen(BUCKET_LABELS[b]);
        _resize_block(len + 8);
        _append_char((char *) BUCKET_LABELS[b], len);
        _append_char("\"", 1);
    }
    _append_char("]", 1);

    char daybuf[11];
    for (size_t i = 0; i < DAYS_LEN; i++) {
        format_day(DAYS[i].day, daybuf);

        // ",\n    [\"YYYY-MM-DD\"" + 8 * (", " + up to 20 digits) + "]"
        _resize_block(32 + NUM_BUCKETS * 24);
        _append_char(",\n    [\"", 8);
        _append_char(daybuf, 10);
        _append_char("\"", 1);

        for (int b = 0; b < NUM_BUCKETS; b++) {
            _append_char(", ", 2);
            // Write the count as a decimal without fixed-width padding.
            char numbuf[21];
            int n = snprintf(numbuf, sizeof(numbuf), "%llu",
                             (unsigned long long) DAYS[i].counts[b]);
            _append_char(numbuf, (uint64_t) n);
        }
        _append_char("]", 1);
    }

    _resize_block(4);
    _append_char("\n]\n", 3);

    // Write everything out.
    size_t offset = 0;
    while (offset < PARSED_BLOCK_INDEX) {
        ssize_t written = write(STDOUT_FILENO, PARSED_BLOCK + offset,
                                (size_t) PARSED_BLOCK_INDEX - offset);
        if (written <= 0) break;
        offset += (size_t) written;
    }

    _reset();

    // Free the accumulator so a subsequent run in the same process starts clean.
    free(DAYS);
    DAYS = NULL;
    DAYS_LEN = 0;
    DAYS_CAP = 0;
}
