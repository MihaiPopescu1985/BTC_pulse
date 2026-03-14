#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "export_block_recorder.h"

int REC_MAGIC_CALLS = 0;
int REC_BLOCK_SIZE_CALLS = 0;
int REC_HEADER_VERSION_CALLS = 0;
int REC_PREV_HASH_CALLS = 0;
int REC_MERKLE_ROOT_CALLS = 0;
int REC_BLOCK_TIME_CALLS = 0;
int REC_NBYTES_CALLS = 0;
int REC_NONCE_CALLS = 0;
int REC_BLOCK_HASH_CALLS = 0;
int REC_TRANSACTION_COUNT_CALLS = 0;
int REC_TX_VERSION_CALLS = 0;
int REC_FLAG_CALLS = 0;
int REC_TX_IN_COUNT_CALLS = 0;
int REC_TX_ID_CALLS = 0;
int REC_INPUT_VOUT_CALLS = 0;
int REC_SCRIPT_SIG_SIZE_CALLS = 0;
int REC_SCRIPT_SIG_CALLS = 0;
int REC_TX_IN_SEQUENCE_CALLS = 0;
int REC_TX_OUT_COUNT_CALLS = 0;
int REC_AMOUNT_CALLS = 0;
int REC_PUB_KEY_SIZE_CALLS = 0;
int REC_SCRIPT_PUB_KEY_CALLS = 0;
int REC_STACK_ITEMS_COUNT_CALLS = 0;
int REC_STACK_ITEM_SIZE_CALLS = 0;
int REC_TO_STACK_CALLS = 0;
int REC_WITNESS_CALLS = 0;
int REC_LOCK_TIME_CALLS = 0;
int REC_TX_HASH_CALLS = 0;

uint8_t REC_MAGIC[4] = {0};
uint8_t REC_BLOCK_SIZE[4] = {0};
uint8_t REC_HEADER_VERSION[4] = {0};
uint8_t REC_PREV_HASH[32] = {0};
uint8_t REC_MERKLE_ROOT[32] = {0};
uint8_t REC_BLOCK_TIME[4] = {0};
uint8_t REC_NBYTES[4] = {0};
uint8_t REC_NONCE[4] = {0};
uint8_t REC_BLOCK_HASH[32] = {0};
uint64_t REC_TRANSACTION_COUNT = 0;
uint8_t REC_TX_VERSION[4] = {0};
uint8_t REC_FLAG = 0;
uint64_t REC_TX_IN_COUNT = 0;
uint8_t REC_TX_ID[32] = {0};
uint8_t REC_INPUT_VOUT[4] = {0};
uint64_t REC_SCRIPT_SIG_SIZE = 0;
uint8_t *REC_SCRIPT_SIG = NULL;
uint8_t REC_TX_IN_SEQUENCE[4] = {0};
uint64_t REC_TX_OUT_COUNT = 0;
uint8_t REC_AMOUNT[8] = {0};
uint64_t REC_PUB_KEY_SIZE = 0;
uint8_t *REC_SCRIPT_PUB_KEY = NULL;
uint64_t REC_STACK_ITEMS_COUNT = 0;
uint64_t REC_STACK_ITEM_SIZE = 0;
uint8_t *REC_TO_STACK = NULL;
uint8_t *REC_WITNESS = NULL;
uint64_t REC_WITNESS_SIZE = 0;
uint8_t REC_LOCK_TIME[4] = {0};
uint8_t REC_TX_HASH[32] = {0};

static void set_blob(uint8_t **dst, size_t size, const uint8_t *src)
{
    if (*dst != NULL)
    {
        free(*dst);
        *dst = NULL;
    }

    if (size == 0)
    {
        return;
    }

    *dst = (uint8_t *) malloc(size * sizeof(uint8_t));
    if (*dst == NULL)
    {
        return;
    }
    memcpy(*dst, src, size);
}

void recorder_reset(void)
{
    if (REC_SCRIPT_SIG != NULL) { free(REC_SCRIPT_SIG); REC_SCRIPT_SIG = NULL; }
    if (REC_SCRIPT_PUB_KEY != NULL) { free(REC_SCRIPT_PUB_KEY); REC_SCRIPT_PUB_KEY = NULL; }
    if (REC_TO_STACK != NULL) { free(REC_TO_STACK); REC_TO_STACK = NULL; }
    if (REC_WITNESS != NULL) { free(REC_WITNESS); REC_WITNESS = NULL; }

    REC_MAGIC_CALLS = 0;
    REC_BLOCK_SIZE_CALLS = 0;
    REC_HEADER_VERSION_CALLS = 0;
    REC_PREV_HASH_CALLS = 0;
    REC_MERKLE_ROOT_CALLS = 0;
    REC_BLOCK_TIME_CALLS = 0;
    REC_NBYTES_CALLS = 0;
    REC_NONCE_CALLS = 0;
    REC_BLOCK_HASH_CALLS = 0;
    REC_TRANSACTION_COUNT_CALLS = 0;
    REC_TX_VERSION_CALLS = 0;
    REC_FLAG_CALLS = 0;
    REC_TX_IN_COUNT_CALLS = 0;
    REC_TX_ID_CALLS = 0;
    REC_INPUT_VOUT_CALLS = 0;
    REC_SCRIPT_SIG_SIZE_CALLS = 0;
    REC_SCRIPT_SIG_CALLS = 0;
    REC_TX_IN_SEQUENCE_CALLS = 0;
    REC_TX_OUT_COUNT_CALLS = 0;
    REC_AMOUNT_CALLS = 0;
    REC_PUB_KEY_SIZE_CALLS = 0;
    REC_SCRIPT_PUB_KEY_CALLS = 0;
    REC_STACK_ITEMS_COUNT_CALLS = 0;
    REC_STACK_ITEM_SIZE_CALLS = 0;
    REC_TO_STACK_CALLS = 0;
    REC_WITNESS_CALLS = 0;
    REC_LOCK_TIME_CALLS = 0;
    REC_TX_HASH_CALLS = 0;

    memset(REC_MAGIC, 0, sizeof(REC_MAGIC));
    memset(REC_BLOCK_SIZE, 0, sizeof(REC_BLOCK_SIZE));
    memset(REC_HEADER_VERSION, 0, sizeof(REC_HEADER_VERSION));
    memset(REC_PREV_HASH, 0, sizeof(REC_PREV_HASH));
    memset(REC_MERKLE_ROOT, 0, sizeof(REC_MERKLE_ROOT));
    memset(REC_BLOCK_TIME, 0, sizeof(REC_BLOCK_TIME));
    memset(REC_NBYTES, 0, sizeof(REC_NBYTES));
    memset(REC_NONCE, 0, sizeof(REC_NONCE));
    memset(REC_BLOCK_HASH, 0, sizeof(REC_BLOCK_HASH));
    memset(REC_TX_VERSION, 0, sizeof(REC_TX_VERSION));
    memset(REC_TX_ID, 0, sizeof(REC_TX_ID));
    memset(REC_INPUT_VOUT, 0, sizeof(REC_INPUT_VOUT));
    memset(REC_TX_IN_SEQUENCE, 0, sizeof(REC_TX_IN_SEQUENCE));
    memset(REC_AMOUNT, 0, sizeof(REC_AMOUNT));
    memset(REC_LOCK_TIME, 0, sizeof(REC_LOCK_TIME));
    memset(REC_TX_HASH, 0, sizeof(REC_TX_HASH));

    REC_TRANSACTION_COUNT = 0;
    REC_FLAG = 0;
    REC_TX_IN_COUNT = 0;
    REC_SCRIPT_SIG_SIZE = 0;
    REC_TX_OUT_COUNT = 0;
    REC_PUB_KEY_SIZE = 0;
    REC_STACK_ITEMS_COUNT = 0;
    REC_STACK_ITEM_SIZE = 0;
    REC_WITNESS_SIZE = 0;
}

void export_magic_number(uint8_t magic_bytes[4])
{
    REC_MAGIC_CALLS++;
    memcpy(REC_MAGIC, magic_bytes, sizeof(REC_MAGIC));
}

void export_block_size(uint8_t block_size[4])
{
    REC_BLOCK_SIZE_CALLS++;
    memcpy(REC_BLOCK_SIZE, block_size, sizeof(REC_BLOCK_SIZE));
}

void export_header_version(uint8_t header_version[4])
{
    REC_HEADER_VERSION_CALLS++;
    memcpy(REC_HEADER_VERSION, header_version, sizeof(REC_HEADER_VERSION));
}

void export_prev_hash(uint8_t prev_hash[32])
{
    REC_PREV_HASH_CALLS++;
    memcpy(REC_PREV_HASH, prev_hash, sizeof(REC_PREV_HASH));
}

void export_merkle_root(uint8_t merkle_root[32])
{
    REC_MERKLE_ROOT_CALLS++;
    memcpy(REC_MERKLE_ROOT, merkle_root, sizeof(REC_MERKLE_ROOT));
}

void export_block_time(uint8_t block_time[4])
{
    REC_BLOCK_TIME_CALLS++;
    memcpy(REC_BLOCK_TIME, block_time, sizeof(REC_BLOCK_TIME));
}

void export_nbytes(uint8_t nbyes[4])
{
    REC_NBYTES_CALLS++;
    memcpy(REC_NBYTES, nbyes, sizeof(REC_NBYTES));
}

void export_nonce(uint8_t nonce[4])
{
    REC_NONCE_CALLS++;
    memcpy(REC_NONCE, nonce, sizeof(REC_NONCE));
}

void export_block_hash(unsigned char block_hash[32])
{
    REC_BLOCK_HASH_CALLS++;
    memcpy(REC_BLOCK_HASH, block_hash, sizeof(REC_BLOCK_HASH));
}

void export_transaction_count(uint64_t tx_count)
{
    REC_TRANSACTION_COUNT_CALLS++;
    REC_TRANSACTION_COUNT = tx_count;
}

void export_tx_version(uint8_t tx_version[4])
{
    REC_TX_VERSION_CALLS++;
    memcpy(REC_TX_VERSION, tx_version, sizeof(REC_TX_VERSION));
}

void export_flag(uint8_t flag)
{
    REC_FLAG_CALLS++;
    REC_FLAG = flag;
}

void export_tx_in_count(uint64_t tx_in_count)
{
    REC_TX_IN_COUNT_CALLS++;
    REC_TX_IN_COUNT = tx_in_count;
}

void export_tx_id(uint8_t tx_id[32])
{
    REC_TX_ID_CALLS++;
    memcpy(REC_TX_ID, tx_id, sizeof(REC_TX_ID));
}

void export_input_vout(uint8_t vout[4])
{
    REC_INPUT_VOUT_CALLS++;
    memcpy(REC_INPUT_VOUT, vout, sizeof(REC_INPUT_VOUT));
}

void export_script_sig_size(uint64_t script_sig_size)
{
    REC_SCRIPT_SIG_SIZE_CALLS++;
    REC_SCRIPT_SIG_SIZE = script_sig_size;
}

void export_script_sig(uint8_t *script_sig)
{
    REC_SCRIPT_SIG_CALLS++;
    set_blob(&REC_SCRIPT_SIG, (size_t) REC_SCRIPT_SIG_SIZE, script_sig);
}

void export_tx_in_sequence(uint8_t tx_in_sequence[4])
{
    REC_TX_IN_SEQUENCE_CALLS++;
    memcpy(REC_TX_IN_SEQUENCE, tx_in_sequence, sizeof(REC_TX_IN_SEQUENCE));
}

void export_tx_out_count(uint64_t tx_out_count)
{
    REC_TX_OUT_COUNT_CALLS++;
    REC_TX_OUT_COUNT = tx_out_count;
}

void export_amount(uint8_t amount[8])
{
    REC_AMOUNT_CALLS++;
    memcpy(REC_AMOUNT, amount, sizeof(REC_AMOUNT));
}

void export_pub_key_size(uint64_t pub_key_size)
{
    REC_PUB_KEY_SIZE_CALLS++;
    REC_PUB_KEY_SIZE = pub_key_size;
}

void export_script_pub_key(uint8_t *script_pub_key)
{
    REC_SCRIPT_PUB_KEY_CALLS++;
    set_blob(&REC_SCRIPT_PUB_KEY, (size_t) REC_PUB_KEY_SIZE, script_pub_key);
}

void export_stack_items_count(uint64_t stack_items)
{
    REC_STACK_ITEMS_COUNT_CALLS++;
    REC_STACK_ITEMS_COUNT = stack_items;
}

void export_stack_item_size(uint64_t size)
{
    REC_STACK_ITEM_SIZE_CALLS++;
    REC_STACK_ITEM_SIZE = size;
}

void export_to_stack(uint8_t *to_stack)
{
    REC_TO_STACK_CALLS++;
    set_blob(&REC_TO_STACK, (size_t) REC_STACK_ITEM_SIZE, to_stack);
}

void export_witness(uint8_t *witness, uint64_t witness_size)
{
    REC_WITNESS_CALLS++;
    REC_WITNESS_SIZE = witness_size;
    set_blob(&REC_WITNESS, (size_t) witness_size, witness);
}

void export_lock_time(uint8_t lock_time[4])
{
    REC_LOCK_TIME_CALLS++;
    memcpy(REC_LOCK_TIME, lock_time, sizeof(REC_LOCK_TIME));
}

void export_tx_hash(uint8_t tx_hash[32])
{
    REC_TX_HASH_CALLS++;
    memcpy(REC_TX_HASH, tx_hash, sizeof(REC_TX_HASH));
}

void export_flush(void)
{
}
