#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>

#include "block_common.h"
#include <unistd.h>


uint64_t BLOCK_TIME = 0;
uint8_t BLOCK_HASH[32];

typedef struct
{
    uint64_t amount;
    uint64_t pub_key_size;
    uint8_t *script_pub_key;
} out;

out *OUTPUTS = NULL;
uint32_t LAST_OUT_INDEX = 0;
static const size_t FLUSH_THRESHOLD = 4 * 1024 * 1024;

static void write_all(const char *buffer, size_t length)
{
    size_t offset = 0;
    while (offset < length)
    {
        ssize_t written = write(STDOUT_FILENO, buffer + offset, length - offset);
        if (written <= 0)
        {
            break;
        }
        offset += (size_t) written;
    }
}


// Header
void block_export_magic_number(uint8_t magic_bytes[4]) {};

void block_export_block_size(uint8_t block_size[4]) {};
void block_export_header_version(uint8_t header_version[4]) {};
void block_export_prev_hash(uint8_t prev_hash[32]) {};
void block_export_merkle_root(uint8_t merkle_root[32]) {};

void block_export_block_time(uint8_t block_time[4])
{
    uint64_t time = block_time[3];
    time = time << 8 | block_time[2];
    time = time << 8 | block_time[1];
    time = time << 8 | block_time[0];

    BLOCK_TIME = time;
};

void block_export_nbytes(uint8_t nbyes[4]) {};
void block_export_nonce(uint8_t nonce[4]) {};

void block_export_block_hash(unsigned char block_hash[32])
{
    memcpy(BLOCK_HASH, block_hash, 32);

    _resize_block(131);
    char *command = "insert into block (hash, time) values (X'";
    _append_char(command, 41);
    _append_hex(BLOCK_HASH, 32);
    _append_char("', ", 3);
    _append_int(BLOCK_TIME);
    _append_char(");\n", 3);
};

// Transaction count
void block_export_transaction_count(uint64_t tx_count) {};

// Transaction
void block_export_tx_version(uint8_t tx_version[4]) {};

// Transaction input
void block_export_flag(uint8_t flag) {};
void block_export_tx_in_count(uint64_t tx_in_count) {};

void block_export_tx_id(uint8_t tx_id[32]) {};
void block_export_input_vout(uint8_t vout[4]) {};
void block_export_script_sig_size(uint64_t script_sig_size) {};
void block_export_script_sig(uint8_t *script_sig) {};
void block_export_tx_in_sequence(uint8_t tx_in_sequence[4]) {};

// Transaction output
void block_export_tx_out_count(uint64_t tx_out_count)
{
    LAST_OUT_INDEX = 0;
    OUTPUTS = malloc(tx_out_count * sizeof(out));
    if (OUTPUTS == NULL)
    {
        perror("Error assigning memory for outputs.");
        exit(1);
    }
};

void block_export_amount(uint8_t amount[8])
{
    uint64_t amt = amount[7];
    amt = amt << 8 | amount[6];
    amt = amt << 8 | amount[5];
    amt = amt << 8 | amount[4];
    amt = amt << 8 | amount[3];
    amt = amt << 8 | amount[2];
    amt = amt << 8 | amount[1];
    amt = amt << 8 | amount[0];

    OUTPUTS[LAST_OUT_INDEX].amount = amt;
};

void block_export_pub_key_size(uint64_t pub_key_size)
{
    OUTPUTS[LAST_OUT_INDEX].pub_key_size = pub_key_size;
};

void block_export_script_pub_key(uint8_t *script_pub_key)
{
    OUTPUTS[LAST_OUT_INDEX].script_pub_key = malloc(
        OUTPUTS[LAST_OUT_INDEX].pub_key_size * sizeof(uint8_t));

    if (OUTPUTS[LAST_OUT_INDEX].script_pub_key == NULL)
    {
        perror("Error allocating memory to OUTPUTS.");
        exit(1);
    }

    memcpy(OUTPUTS[LAST_OUT_INDEX].script_pub_key,
           script_pub_key,
           OUTPUTS[LAST_OUT_INDEX].pub_key_size);

    LAST_OUT_INDEX++;
};

// Transaction witness
void block_export_stack_items_count(uint64_t stack_items) {};
void block_export_stack_item_size(uint64_t size) {};
void block_export_to_stack(uint8_t *to_stack) {};
void block_export_witness(uint8_t *witness, uint64_t witness_size) {};
void block_export_lock_time(uint8_t lock_time[4]) {};

void block_export_tx_hash(uint8_t tx_hash[32])
{
    _resize_block(295);
    char *message = "insert into tx (block_hash, hash) values (X'";
    _append_char(message, 44);
    _append_hex(BLOCK_HASH, 32);
    _append_char("', X'", 5);
    _append_hex(tx_hash, 32);
    _append_char("');\n", 4);

    for (size_t i = 0; i < LAST_OUT_INDEX; i++)
    {
        _resize_block(60 + 64 + 3 + 20 + 2 + 20 + 4 + (2 * OUTPUTS[i].pub_key_size) + 4);

        char *command = "insert into out (tx_hash, count, amount, pub_key) values (X'";
        _append_char(command, 60);
        _append_hex(tx_hash, 32);
        _append_char("', ", 3);
        _append_int(i);
        _append_char(", ", 2);
        _append_int(OUTPUTS[i].amount);
        _append_char(", X'", 4);
        _append_hex(OUTPUTS[i].script_pub_key,
                    OUTPUTS[i].pub_key_size);
        _append_char("');\n", 4);
    }

    for (size_t i = 0; i < LAST_OUT_INDEX; i++)
    {
        free(OUTPUTS[i].script_pub_key);
        OUTPUTS[i].script_pub_key = NULL;
    }
    free(OUTPUTS);
    OUTPUTS = NULL;

    if (PARSED_BLOCK_INDEX >= FLUSH_THRESHOLD)
    {
        write_all(PARSED_BLOCK, (size_t) PARSED_BLOCK_INDEX);
        _reset();
    }
};

void block_export_flush(void)
{
    if (PARSED_BLOCK_INDEX == 0) return;
    write_all(PARSED_BLOCK, (size_t) PARSED_BLOCK_INDEX);
    _reset();
}
