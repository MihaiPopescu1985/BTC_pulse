// Version 2


#include <unistd.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#include "block_common.h"

static uint64_t SCRIPT_SIG_SIZE = 0;
static uint64_t PUB_KEY_SIZE = 0;
static uint64_t ITEM_SIZE = 0;

static void write_all(const char *buffer, size_t length) {
    size_t offset = 0;
    while (offset < length) {
        ssize_t written = write(STDOUT_FILENO, buffer + offset, length - offset);
        if (written <= 0) {
            break;
        }
        offset += (size_t) written;
    }
}

void debug_export_magic_number(uint8_t magic_bytes[4]) {
    _reset();

    // message size + 2 * magic_bytes size + new line char
    _resize_block(31);

    char message[] = "Parsed magic number: ";
    _append_char(message, 21);
    _append_hex(magic_bytes, 4);
    _append_char("\n", 1);
}

void debug_export_block_size(uint8_t block_size[4]) {
    // message size + 2 * block_size size + new line char
    _resize_block(28);

    char message[] = "Parsed block size: ";
    _append_char(message, 19);
    _append_hex(block_size, 4);
    _append_char("\n", 1);
}

void debug_export_header_version(uint8_t header_version[4]) {
    // message size + 2 * header_version size + new line char
    _resize_block(32);

    char message[] = "Parsed header version: ";
    _append_char(message, 23);
    _append_hex(header_version, 4);
    _append_char("\n", 1);
}

void debug_export_prev_hash(uint8_t prev_hash[32]) {
    // message size + 2 * prev_hash size + new line char
    _resize_block(93);

    char message[] = "Parsed previous block hash: ";
    _append_char(message, 28);
    _append_hex(prev_hash, 32);
    _append_char("\n", 1);
}

void debug_export_merkle_root(uint8_t merkle_root[32]) {
    // message size + 2 * merkle_root size + new line char
    _resize_block(85);

    char message[] = "Parsed merkle root: ";
    _append_char(message, 20);
    _append_hex(merkle_root, 32);
    _append_char("\n", 1);
}

void debug_export_block_time(uint8_t block_time[4]) {
    // message size + 2 * block_time + new line char
    _resize_block(28);

    char message[] = "Parsed block time: ";
    _append_char(message, 19);
    _append_hex(block_time, 4);
    _append_char("\n", 1);
}

void debug_export_nbytes(uint8_t nbyes[4]) {
    // message size + 2 * nbytes + new line char
    _resize_block(24);

    char message[] = "Parsed nbytes: ";
    _append_char(message, 15);
    _append_hex(nbyes, 4);
    _append_char("\n", 1);
}

void debug_export_nonce(uint8_t nonce[4]) {
    // message size + 2 * nonce size + new line char
    _resize_block(23);
    
    char message[] = "Parsed nonce: ";
    _append_char(message, 14);
    _append_hex(nonce, 4);
    _append_char("\n", 1);
}

void debug_export_block_hash(unsigned char block_hash[32]) {
    // message size + 2 * block_hash size + new line char
    _resize_block(84);
    
    char message[] = "Parsed block hash: ";
    _append_char(message, 19);
    _append_hex(block_hash, 32);
    _append_char("\n", 1);
}

void debug_export_transaction_count(uint64_t tx_count) {
    // message size + 20 (tx_count size) + new line char
    _resize_block(47);
    
    char message[] = "Parsed transaction count: ";
    _append_char(message, 26);
    _append_int(tx_count);
    _append_char("\n", 1);
}

void debug_export_tx_version(uint8_t tx_version[4]) {
    // message size + 2 * tx_version size + new line char
    _resize_block(37);
    
    char message[] = "Parsed transaction version: ";
    _append_char(message, 28);
    _append_hex(tx_version, 4);
    _append_char("\n", 1);
}

void debug_export_flag(uint8_t flag) {
    // message size + size of flag (hex) + new line char
    _resize_block(18);

    char message[] = "Parsed flag: ";
    _append_char(message, 13);

    uint8_t flag_array[] = { flag };
    _append_hex(flag_array, 1);

    _append_char("\n", 1);
}

void debug_export_tx_in_count(uint64_t tx_in_count) {
    // message size + 20 (tx_in_count size) + new line char
    _resize_block(53);

    char message[] = "Parsed transaction input count: ";
    _append_char(message, 32);
    _append_int(tx_in_count);
    _append_char("\n", 1);
}

void debug_export_tx_id(uint8_t tx_id[32]) {
    // message size + 2 * tx_id size + new line char
    _resize_block(88);

    char message[] = "Parsed transaction id: ";
    _append_char(message, 23);
    _append_hex(tx_id, 32);
    _append_char("\n", 1);
}

void debug_export_input_vout(uint8_t vout[4]) {
    // message size + 2 * vout size + new line char
    _resize_block(22);

    char message[] = "Parsed vout: ";
    _append_char(message, 13);
    _append_hex(vout, 4);
    _append_char("\n", 1);
}

void debug_export_script_sig_size(uint64_t script_sig_size) {
    // message size + 20 (script_sig_size size) + new line char
    _resize_block(44);

    char message[] = "Parsed scriptSig size: ";
    _append_char(message, 23);
    _append_int(script_sig_size);
    _append_char("\n", 1);

    SCRIPT_SIG_SIZE = script_sig_size;
}

void debug_export_script_sig(uint8_t *script_sig) {
    // message size + 2 * SCRIPT_SIG_SIZE + new line char
    _resize_block(19 + 2 * SCRIPT_SIG_SIZE + 1);

    char message[] = "Parsed script sig: ";
    _append_char(message, 19);
    _append_hex(script_sig, SCRIPT_SIG_SIZE);
    _append_char("\n", 1);
}

void debug_export_tx_in_sequence(uint8_t tx_in_sequence[4]) {
    // message size + 2 * tx_in_sequence size + new line char
    _resize_block(32);

    char message[] = "Parsed tx in sequence: ";
    _append_char(message, 23);
    _append_hex(tx_in_sequence, 4);
    _append_char("\n", 1);
}

void debug_export_tx_out_count(uint64_t tx_out_count) {
    // message size + 20 (tx_out_count size) + new line char
    _resize_block(42);

    char message[] = "Parsed tx out count: ";
    _append_char(message, 21);
    _append_int(tx_out_count);
    _append_char("\n", 1);
}

void debug_export_amount(uint8_t amount[8]) {
    // message size + 2 * amount size + new line char
    _resize_block(32);

    char message[] = "Parsed amount: ";
    _append_char(message, 15);
    _append_hex(amount, 8);
    _append_char("\n", 1);
}

void debug_export_pub_key_size(uint64_t pub_key_size) {
    // message size + 20 (pub_key_size size) + new line char
    _resize_block(45);

    char message[] = "Parsed public key size: ";
    _append_char(message, 24);
    _append_int(pub_key_size);
    _append_char("\n", 1);

    PUB_KEY_SIZE = pub_key_size;
}

void debug_export_script_pub_key(uint8_t *script_pub_key) {
    // message size + 2 * PUB_KEY_SIZE + new line char
    _resize_block(26 + 2 * PUB_KEY_SIZE + 1);

    char message[] = "Parsed script public key: ";
    _append_char(message, 26);
    _append_hex(script_pub_key, PUB_KEY_SIZE);
    _append_char("\n", 1);
}

void debug_export_stack_items_count(uint64_t stack_item_count) {
    // message size + 20 (stack_item_count size) + new line char
    _resize_block(46);

    char message[] = "Parsed stack item count: ";
    _append_char(message, 25);
    _append_int(stack_item_count);
    _append_char("\n", 1);
}

void debug_export_stack_item_size(uint64_t item_size) {
    // message size + 20 (item_size size) + new line char
    _resize_block(39);

    char message[] = "Parsed item size: ";
    _append_char(message, 18);
    _append_int(item_size);
    _append_char("\n", 1);

    ITEM_SIZE = item_size;
}

void debug_export_to_stack(uint8_t *to_stack) {
    // message size + 2 * ITEM_SIZE + new line char
    _resize_block(17 + 2 * ITEM_SIZE + 1);

    char message[] = "Parsed to stack: ";
    _append_char(message, 17);
    _append_hex(to_stack, ITEM_SIZE);
    _append_char("\n", 1);
}

void debug_export_witness(uint8_t *witness, uint64_t witness_size) {
    // message size + 2 * witness_size + new line char
    _resize_block(17 + 2 * witness_size + 1);

    char message[] = "Parsed witness: ";
    _append_char(message, 17);
    _append_hex(witness, witness_size);
    _append_char("\n", 1);
}

void debug_export_lock_time(uint8_t lock_time[4]) {
    // message size + 2 * lock_time size + new line char
    _resize_block(27);

    char message[] = "Parsed lock time: ";
    _append_char(message, 18);
    _append_hex(lock_time, 4);
    _append_char("\n", 1);
}

void debug_export_tx_hash(uint8_t tx_hash[32]) {
    // message size + 2 * tx_hash size + new line char
    _resize_block(90);

    char message[] = "Parsed transaction hash: ";
    _append_char(message, 25);
    _append_hex(tx_hash, 32);
    _append_char("\n", 1);

    write_all(PARSED_BLOCK, (size_t) PARSED_BLOCK_INDEX);

    _reset();
}

void debug_export_flush(void) {
}
