#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "export_block_recorder.h"

void reset(void);
uint16_t to_big_endian_16(uint8_t first, uint8_t second);
uint32_t to_big_endian_32(uint8_t first, uint8_t second, uint8_t third, uint8_t fourth);
uint64_t to_big_endian_64(uint8_t first, uint8_t second, uint8_t third, uint8_t fourth,
                          uint8_t fifth, uint8_t sixth, uint8_t seventh, uint8_t eigth);
uint64_t get_compact_size(FILE *dat_file);
int reverse_compact_size(uint64_t size);
void get_double_sha256(unsigned char *data, size_t data_len, unsigned char *out_hash);
int resize_transaction(size_t amount);
void set_block_hash(void);
int parse_magic_bytes(FILE *dat_file);
void parse_block_size(FILE *dat_file);
void parse_header_version(FILE *dat_file);
void parse_prev_hash(FILE *dat_file);
void parse_merkle_root(FILE *dat_file);
void parse_header_timestamp(FILE *dat_file);
void parse_nbytes(FILE *dat_file);
void parse_nonce(FILE *dat_file);
int parse_header(FILE *dat_file);
void parse_transaction_count(FILE *dat_file);
int parse_tx_version(FILE *dat_file);
int parse_input_count(FILE *dat_file, bool *is_witness);
int parse_input_txid(FILE *dat_file);
int parse_input_vout(FILE *dat_file);
int parse_scriptsig_size(FILE *dat_file);
int parse_scriptsig(FILE *dat_file);
int parse_input_sequence(FILE *dat_file);
int parse_out_count(FILE *dat_file);
int parse_amount(FILE *dat_file);
int parse_pubkey_size(FILE *dat_file);
int parse_script_pubkey(FILE *dat_file);
int parse_witness(FILE *dat_file);
int parse_lock_time(FILE *dat_file);
int parse_transactions(FILE *dat_file);
int parse_dat_file(FILE *dat_file);

static int failures = 0;

static void expect_int(const char *label, uint64_t expected, uint64_t actual)
{
    if (expected != actual)
    {
        fprintf(stderr, "[FAIL] %s: expected %llu got %llu\n",
                label,
                (unsigned long long) expected,
                (unsigned long long) actual);
        failures++;
    }
}

static void expect_mem(const char *label, const uint8_t *expected, const uint8_t *actual, size_t len)
{
    if (memcmp(expected, actual, len) != 0)
    {
        fprintf(stderr, "[FAIL] %s: byte arrays differ\n", label);
        failures++;
    }
}

static FILE *stream_from_bytes(const uint8_t *bytes, size_t len)
{
    FILE *fp = tmpfile();
    if (fp == NULL)
    {
        perror("tmpfile");
        exit(2);
    }

    if (fwrite(bytes, 1, len, fp) != len)
    {
        perror("fwrite");
        fclose(fp);
        exit(2);
    }

    rewind(fp);
    return fp;
}

static uint8_t hex_nibble(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t) (c - '0');
    if (c >= 'a' && c <= 'f') return (uint8_t) (10 + (c - 'a'));
    if (c >= 'A' && c <= 'F') return (uint8_t) (10 + (c - 'A'));
    return 0;
}

static void hex_to_bytes(const char *hex, uint8_t *out, size_t out_len)
{
    for (size_t i = 0; i < out_len; i++)
    {
        out[i] = (uint8_t) ((hex_nibble(hex[i * 2]) << 4) | hex_nibble(hex[i * 2 + 1]));
    }
}

static void test_helpers(void)
{
    uint8_t expected[32];
    uint8_t out_hash[32];
    uint8_t abc[] = {'a', 'b', 'c'};
    static const char expected_hex[] = "58636c3ec08c12d55aedda056d602d5bcca72d8df6a69b519b72d32dc2428b4f";

    expect_int("to_big_endian_16", 0x1234u, to_big_endian_16(0x34u, 0x12u));
    expect_int("to_big_endian_32", 0x12345678u, to_big_endian_32(0x78u, 0x56u, 0x34u, 0x12u));
    expect_int("to_big_endian_64",
               0x0102030405060708ULL,
               to_big_endian_64(0x08u, 0x07u, 0x06u, 0x05u, 0x04u, 0x03u, 0x02u, 0x01u));

    expect_int("reverse_compact_size(252)", 1u, (uint64_t) reverse_compact_size(252u));
    expect_int("reverse_compact_size(253)", 3u, (uint64_t) reverse_compact_size(253u));
    expect_int("reverse_compact_size(65536)", 5u, (uint64_t) reverse_compact_size(65536u));
    expect_int("reverse_compact_size(4294967296)", 9u, (uint64_t) reverse_compact_size(4294967296ULL));

    {
        uint8_t bytes[] = {0xFCu};
        FILE *fp = stream_from_bytes(bytes, sizeof(bytes));
        expect_int("compact_size direct", 252u, get_compact_size(fp));
        fclose(fp);
    }
    {
        uint8_t bytes[] = {0xFDu, 0x34u, 0x12u};
        FILE *fp = stream_from_bytes(bytes, sizeof(bytes));
        expect_int("compact_size 16-bit", 0x1234u, get_compact_size(fp));
        fclose(fp);
    }
    {
        uint8_t bytes[] = {0xFEu, 0x78u, 0x56u, 0x34u, 0x12u};
        FILE *fp = stream_from_bytes(bytes, sizeof(bytes));
        expect_int("compact_size 32-bit", 0x12345678u, get_compact_size(fp));
        fclose(fp);
    }
    {
        uint8_t bytes[] = {0xFFu, 0x08u, 0x07u, 0x06u, 0x05u, 0x04u, 0x03u, 0x02u, 0x01u};
        FILE *fp = stream_from_bytes(bytes, sizeof(bytes));
        expect_int("compact_size 64-bit", 0x0102030405060708ULL, get_compact_size(fp));
        fclose(fp);
    }

    hex_to_bytes(expected_hex, expected, sizeof(expected));
    memset(out_hash, 0, sizeof(out_hash));
    get_double_sha256(abc, sizeof(abc), out_hash);
    expect_mem("get_double_sha256", expected, out_hash, sizeof(expected));
}

static void test_magic_and_block_size(void)
{
    uint8_t magic_and_size[] = {
        0xF9u, 0xBEu, 0xB4u, 0xD9u,
        0x11u, 0x22u, 0x33u, 0x44u
    };
    FILE *fp = stream_from_bytes(magic_and_size, sizeof(magic_and_size));

    recorder_reset();
    expect_int("parse_magic_bytes ok", 0u, (uint64_t) parse_magic_bytes(fp));
    parse_block_size(fp);

    expect_int("export_magic_number count", 1u, (uint64_t) REC_MAGIC_CALLS);
    expect_mem("export_magic_number value", (uint8_t *) "\xF9\xBE\xB4\xD9", REC_MAGIC, 4u);
    expect_int("export_block_size count", 1u, (uint64_t) REC_BLOCK_SIZE_CALLS);
    expect_mem("export_block_size value", (uint8_t *) "\x11\x22\x33\x44", REC_BLOCK_SIZE, 4u);

    fclose(fp);

    {
        uint8_t bad_magic[] = {0x00u, 0xBEu, 0xB4u, 0xD9u};
        FILE *bad_fp = stream_from_bytes(bad_magic, sizeof(bad_magic));
        recorder_reset();
        expect_int("parse_magic_bytes bad", 1u, (uint64_t) parse_magic_bytes(bad_fp));
        expect_int("export_magic_number bad count", 0u, (uint64_t) REC_MAGIC_CALLS);
        fclose(bad_fp);
    }
}

static void test_header_parts_and_set_block_hash(void)
{
    uint8_t version[4] = {0x01u, 0x00u, 0x00u, 0x00u};
    uint8_t prev_hash[32];
    uint8_t merkle_root[32];
    uint8_t block_time[4] = {0xAAu, 0xBBu, 0xCCu, 0xDDu};
    uint8_t nbytes[4] = {0x1Du, 0x00u, 0xFFu, 0xEEu};
    uint8_t nonce[4] = {0x11u, 0x22u, 0x33u, 0x44u};
    uint8_t header_fields[80];
    FILE *fp;

    for (size_t i = 0; i < 32; i++)
    {
        prev_hash[i] = (uint8_t) i;
        merkle_root[i] = (uint8_t) (255u - i);
    }

    memcpy(header_fields, version, 4);
    memcpy(header_fields + 4, prev_hash, 32);
    memcpy(header_fields + 36, merkle_root, 32);
    memcpy(header_fields + 68, block_time, 4);
    memcpy(header_fields + 72, nbytes, 4);
    memcpy(header_fields + 76, nonce, 4);

    fp = stream_from_bytes(header_fields, sizeof(header_fields));
    recorder_reset();

    parse_header_version(fp);
    parse_prev_hash(fp);
    parse_merkle_root(fp);
    parse_header_timestamp(fp);
    parse_nbytes(fp);
    parse_nonce(fp);
    set_block_hash();

    expect_int("header_version count", 1u, (uint64_t) REC_HEADER_VERSION_CALLS);
    expect_mem("header_version value", version, REC_HEADER_VERSION, sizeof(version));
    expect_int("prev_hash count", 1u, (uint64_t) REC_PREV_HASH_CALLS);
    expect_mem("prev_hash value", prev_hash, REC_PREV_HASH, sizeof(prev_hash));
    expect_int("merkle_root count", 1u, (uint64_t) REC_MERKLE_ROOT_CALLS);
    expect_mem("merkle_root value", merkle_root, REC_MERKLE_ROOT, sizeof(merkle_root));
    expect_int("block_time count", 1u, (uint64_t) REC_BLOCK_TIME_CALLS);
    expect_mem("block_time value", block_time, REC_BLOCK_TIME, sizeof(block_time));
    expect_int("nbytes count", 1u, (uint64_t) REC_NBYTES_CALLS);
    expect_mem("nbytes value", nbytes, REC_NBYTES, sizeof(nbytes));
    expect_int("nonce count", 1u, (uint64_t) REC_NONCE_CALLS);
    expect_mem("nonce value", nonce, REC_NONCE, sizeof(nonce));

    fclose(fp);
    reset();
}

static void test_parse_header(void)
{
    uint8_t raw[88];
    uint8_t header[80];
    uint8_t expected_hash[32];
    uint8_t prev_hash[32];
    uint8_t merkle[32];
    FILE *fp;

    for (size_t i = 0; i < 32; i++)
    {
        prev_hash[i] = (uint8_t) (i + 1u);
        merkle[i] = (uint8_t) (100u + i);
    }

    raw[0] = 0xF9u;
    raw[1] = 0xBEu;
    raw[2] = 0xB4u;
    raw[3] = 0xD9u;
    raw[4] = 0xAAu;
    raw[5] = 0xBBu;
    raw[6] = 0xCCu;
    raw[7] = 0xDDu;

    header[0] = 0x02u;
    header[1] = 0x00u;
    header[2] = 0x00u;
    header[3] = 0x00u;
    memcpy(header + 4, prev_hash, 32);
    memcpy(header + 36, merkle, 32);
    header[68] = 0x10u;
    header[69] = 0x20u;
    header[70] = 0x30u;
    header[71] = 0x40u;
    header[72] = 0x50u;
    header[73] = 0x60u;
    header[74] = 0x70u;
    header[75] = 0x80u;
    header[76] = 0x90u;
    header[77] = 0xA0u;
    header[78] = 0xB0u;
    header[79] = 0xC0u;

    memcpy(raw + 8, header, sizeof(header));
    get_double_sha256(header, sizeof(header), expected_hash);

    fp = stream_from_bytes(raw, sizeof(raw));
    recorder_reset();
    expect_int("parse_header", 0u, (uint64_t) parse_header(fp));

    expect_int("parse_header export_magic", 1u, (uint64_t) REC_MAGIC_CALLS);
    expect_int("parse_header export_block_size", 1u, (uint64_t) REC_BLOCK_SIZE_CALLS);
    expect_int("parse_header export_block_hash", 1u, (uint64_t) REC_BLOCK_HASH_CALLS);
    expect_mem("parse_header hash", expected_hash, REC_BLOCK_HASH, sizeof(expected_hash));

    fclose(fp);
    reset();
}

static void test_transaction_parts_no_witness(void)
{
    uint8_t tx_version[4] = {0x01u, 0x00u, 0x00u, 0x00u};
    uint8_t txid[32];
    uint8_t vout[4] = {0x02u, 0x00u, 0x00u, 0x00u};
    uint8_t script_sig[1] = {0xAAu};
    uint8_t sequence[4] = {0xFFu, 0xFFu, 0xFFu, 0xFFu};
    uint8_t amount[8] = {0x10u, 0x32u, 0x54u, 0x76u, 0x98u, 0xBAu, 0xDCu, 0xFEu};
    uint8_t script_pub_key[2] = {0x51u, 0xACu};
    uint8_t lock_time[4] = {0x00u, 0x00u, 0x00u, 0x00u};
    uint8_t bytes[63];
    size_t idx = 0;
    FILE *fp;
    bool is_witness = false;

    for (size_t i = 0; i < 32; i++) txid[i] = (uint8_t) i;

    memcpy(bytes + idx, tx_version, 4); idx += 4;
    bytes[idx++] = 0x01u;
    memcpy(bytes + idx, txid, 32); idx += 32;
    memcpy(bytes + idx, vout, 4); idx += 4;
    bytes[idx++] = 0x01u;
    memcpy(bytes + idx, script_sig, 1); idx += 1;
    memcpy(bytes + idx, sequence, 4); idx += 4;
    bytes[idx++] = 0x01u;
    memcpy(bytes + idx, amount, 8); idx += 8;
    bytes[idx++] = 0x02u;
    memcpy(bytes + idx, script_pub_key, 2); idx += 2;
    memcpy(bytes + idx, lock_time, 4); idx += 4;

    fp = stream_from_bytes(bytes, idx);
    recorder_reset();

    expect_int("parse_tx_version", 0u, (uint64_t) parse_tx_version(fp));
    expect_int("resize_transaction direct", 0u, (uint64_t) resize_transaction(3u));
    expect_int("parse_input_count", 0u, (uint64_t) parse_input_count(fp, &is_witness));
    expect_int("is_witness false", 0u, (uint64_t) is_witness);
    expect_int("parse_input_txid", 0u, (uint64_t) parse_input_txid(fp));
    expect_int("parse_input_vout", 0u, (uint64_t) parse_input_vout(fp));
    expect_int("parse_scriptsig_size", 0u, (uint64_t) parse_scriptsig_size(fp));
    expect_int("parse_scriptsig", 0u, (uint64_t) parse_scriptsig(fp));
    expect_int("parse_input_sequence", 0u, (uint64_t) parse_input_sequence(fp));
    expect_int("parse_out_count", 0u, (uint64_t) parse_out_count(fp));
    expect_int("parse_amount", 0u, (uint64_t) parse_amount(fp));
    expect_int("parse_pubkey_size", 0u, (uint64_t) parse_pubkey_size(fp));
    expect_int("parse_script_pubkey", 0u, (uint64_t) parse_script_pubkey(fp));
    expect_int("parse_lock_time", 0u, (uint64_t) parse_lock_time(fp));

    expect_int("tx_version count", 1u, (uint64_t) REC_TX_VERSION_CALLS);
    expect_mem("tx_version value", tx_version, REC_TX_VERSION, sizeof(tx_version));
    expect_int("tx_in_count value", 1u, REC_TX_IN_COUNT);
    expect_int("flag count on non-witness", 0u, (uint64_t) REC_FLAG_CALLS);
    expect_mem("txid value", txid, REC_TX_ID, sizeof(txid));
    expect_mem("vout value", vout, REC_INPUT_VOUT, sizeof(vout));
    expect_int("script_sig_size value", 1u, REC_SCRIPT_SIG_SIZE);
    if (REC_SCRIPT_SIG != NULL) expect_mem("script_sig value", script_sig, REC_SCRIPT_SIG, 1u);
    expect_mem("sequence value", sequence, REC_TX_IN_SEQUENCE, sizeof(sequence));
    expect_int("tx_out_count value", 1u, REC_TX_OUT_COUNT);
    expect_mem("amount value", amount, REC_AMOUNT, sizeof(amount));
    expect_int("pub_key_size value", 2u, REC_PUB_KEY_SIZE);
    if (REC_SCRIPT_PUB_KEY != NULL) expect_mem("script_pub_key value", script_pub_key, REC_SCRIPT_PUB_KEY, 2u);
    expect_mem("lock_time value", lock_time, REC_LOCK_TIME, sizeof(lock_time));

    fclose(fp);
    reset();
}

static void test_witness_path(void)
{
    uint8_t bytes[] = {
        0x01u, 0x00u, 0x00u, 0x00u,
        0x00u, 0x01u, 0x01u,
        0x01u, 0x02u, 0xCAu, 0xFEu
    };
    uint8_t expected_witness[] = {0x01u, 0x02u, 0xCAu, 0xFEu};
    uint8_t expected_stack[] = {0xCAu, 0xFEu};
    FILE *fp = stream_from_bytes(bytes, sizeof(bytes));
    bool is_witness = false;

    recorder_reset();

    expect_int("parse_tx_version witness", 0u, (uint64_t) parse_tx_version(fp));
    expect_int("parse_input_count witness", 0u, (uint64_t) parse_input_count(fp, &is_witness));
    expect_int("is_witness true", 1u, (uint64_t) is_witness);
    expect_int("parse_witness", 0u, (uint64_t) parse_witness(fp));

    expect_int("flag count", 1u, (uint64_t) REC_FLAG_CALLS);
    expect_int("flag value", 1u, (uint64_t) REC_FLAG);
    expect_int("stack_items_count", 1u, REC_STACK_ITEMS_COUNT);
    expect_int("stack_item_size", 2u, REC_STACK_ITEM_SIZE);
    expect_int("witness_size", 4u, REC_WITNESS_SIZE);
    if (REC_TO_STACK != NULL) expect_mem("to_stack value", expected_stack, REC_TO_STACK, sizeof(expected_stack));
    if (REC_WITNESS != NULL) expect_mem("witness value", expected_witness, REC_WITNESS, sizeof(expected_witness));

    fclose(fp);
    reset();
}

static void test_parse_transactions(void)
{
    uint8_t tx_bytes[63];
    uint8_t expected_tx_hash[32];
    uint8_t full_stream[64];
    size_t idx = 0;
    FILE *fp;

    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x01u;
    for (size_t i = 0; i < 32; i++) tx_bytes[idx++] = (uint8_t) (0xA0u + i);
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x99u;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x88u;
    tx_bytes[idx++] = 0x77u;
    tx_bytes[idx++] = 0x66u;
    tx_bytes[idx++] = 0x55u;
    tx_bytes[idx++] = 0x44u;
    tx_bytes[idx++] = 0x33u;
    tx_bytes[idx++] = 0x22u;
    tx_bytes[idx++] = 0x11u;
    tx_bytes[idx++] = 0x02u;
    tx_bytes[idx++] = 0xAAu;
    tx_bytes[idx++] = 0xBBu;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;

    full_stream[0] = 0x01u;
    memcpy(full_stream + 1, tx_bytes, sizeof(tx_bytes));

    get_double_sha256(tx_bytes, sizeof(tx_bytes), expected_tx_hash);

    fp = stream_from_bytes(full_stream, sizeof(full_stream));
    recorder_reset();

    parse_transaction_count(fp);
    expect_int("parse_transactions", 0u, (uint64_t) parse_transactions(fp));

    expect_int("transaction_count", 1u, REC_TRANSACTION_COUNT);
    expect_int("tx_hash count", 1u, (uint64_t) REC_TX_HASH_CALLS);
    expect_mem("tx_hash value", expected_tx_hash, REC_TX_HASH, sizeof(expected_tx_hash));

    fclose(fp);
    reset();
}

static void test_parse_dat_file(void)
{
    uint8_t header[80];
    uint8_t tx_bytes[62];
    uint8_t dat[151];
    uint8_t expected_block_hash[32];
    uint8_t expected_tx_hash[32];
    size_t idx = 0;
    FILE *fp;

    header[0] = 0x02u;
    header[1] = 0x00u;
    header[2] = 0x00u;
    header[3] = 0x00u;
    for (size_t i = 0; i < 32; i++) header[4 + i] = (uint8_t) i;
    for (size_t i = 0; i < 32; i++) header[36 + i] = (uint8_t) (0xFFu - i);
    header[68] = 0xAAu; header[69] = 0xBBu; header[70] = 0xCCu; header[71] = 0xDDu;
    header[72] = 0x11u; header[73] = 0x22u; header[74] = 0x33u; header[75] = 0x44u;
    header[76] = 0x55u; header[77] = 0x66u; header[78] = 0x77u; header[79] = 0x88u;

    idx = 0;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x01u;
    for (size_t i = 0; i < 32; i++) tx_bytes[idx++] = (uint8_t) (0x10u + i);
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x42u;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0xFFu;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x02u;
    tx_bytes[idx++] = 0x03u;
    tx_bytes[idx++] = 0x04u;
    tx_bytes[idx++] = 0x05u;
    tx_bytes[idx++] = 0x06u;
    tx_bytes[idx++] = 0x07u;
    tx_bytes[idx++] = 0x08u;
    tx_bytes[idx++] = 0x01u;
    tx_bytes[idx++] = 0x51u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;
    tx_bytes[idx++] = 0x00u;

    get_double_sha256(header, sizeof(header), expected_block_hash);
    get_double_sha256(tx_bytes, sizeof(tx_bytes), expected_tx_hash);

    idx = 0;
    dat[idx++] = 0xF9u;
    dat[idx++] = 0xBEu;
    dat[idx++] = 0xB4u;
    dat[idx++] = 0xD9u;
    dat[idx++] = 0x3Du;
    dat[idx++] = 0x00u;
    dat[idx++] = 0x00u;
    dat[idx++] = 0x00u;
    memcpy(dat + idx, header, sizeof(header)); idx += sizeof(header);
    dat[idx++] = 0x01u;
    memcpy(dat + idx, tx_bytes, sizeof(tx_bytes)); idx += sizeof(tx_bytes);

    fp = stream_from_bytes(dat, idx);
    recorder_reset();
    expect_int("parse_dat_file valid", 0u, (uint64_t) parse_dat_file(fp));
    expect_int("parse_dat_file block_hash call", 1u, (uint64_t) REC_BLOCK_HASH_CALLS);
    expect_int("parse_dat_file tx_hash call", 1u, (uint64_t) REC_TX_HASH_CALLS);
    expect_mem("parse_dat_file block_hash value", expected_block_hash, REC_BLOCK_HASH, sizeof(expected_block_hash));
    expect_mem("parse_dat_file tx_hash value", expected_tx_hash, REC_TX_HASH, sizeof(expected_tx_hash));
    fclose(fp);

    {
        uint8_t bad[] = {0x00u, 0xBEu, 0xB4u, 0xD9u};
        FILE *bad_fp = stream_from_bytes(bad, sizeof(bad));
        recorder_reset();
        expect_int("parse_dat_file invalid", 1u, (uint64_t) parse_dat_file(bad_fp));
        fclose(bad_fp);
    }
}

static void test_reset_function(void)
{
    uint8_t tx_version[] = {0x01u, 0x00u, 0x00u, 0x00u};
    FILE *fp = stream_from_bytes(tx_version, sizeof(tx_version));
    recorder_reset();

    expect_int("parse_tx_version for reset", 0u, (uint64_t) parse_tx_version(fp));
    reset();
    reset();

    fclose(fp);
}

int main(void)
{
    test_helpers();
    test_magic_and_block_size();
    test_header_parts_and_set_block_hash();
    test_parse_header();
    test_transaction_parts_no_witness();
    test_witness_path();
    test_parse_transactions();
    test_parse_dat_file();
    test_reset_function();

    recorder_reset();
    reset();

    if (failures != 0)
    {
        fprintf(stderr, "test_blk_dat_parser: %d failure(s)\n", failures);
        return 1;
    }

    printf("test_blk_dat_parser: all tests passed\n");
    return 0;
}
