#ifndef EXPORT_BLOCK_RECORDER_H
#define EXPORT_BLOCK_RECORDER_H

#include <stdint.h>
#include <stddef.h>

extern int REC_MAGIC_CALLS;
extern int REC_BLOCK_SIZE_CALLS;
extern int REC_HEADER_VERSION_CALLS;
extern int REC_PREV_HASH_CALLS;
extern int REC_MERKLE_ROOT_CALLS;
extern int REC_BLOCK_TIME_CALLS;
extern int REC_NBYTES_CALLS;
extern int REC_NONCE_CALLS;
extern int REC_BLOCK_HASH_CALLS;
extern int REC_TRANSACTION_COUNT_CALLS;
extern int REC_TX_VERSION_CALLS;
extern int REC_FLAG_CALLS;
extern int REC_TX_IN_COUNT_CALLS;
extern int REC_TX_ID_CALLS;
extern int REC_INPUT_VOUT_CALLS;
extern int REC_SCRIPT_SIG_SIZE_CALLS;
extern int REC_SCRIPT_SIG_CALLS;
extern int REC_TX_IN_SEQUENCE_CALLS;
extern int REC_TX_OUT_COUNT_CALLS;
extern int REC_AMOUNT_CALLS;
extern int REC_PUB_KEY_SIZE_CALLS;
extern int REC_SCRIPT_PUB_KEY_CALLS;
extern int REC_STACK_ITEMS_COUNT_CALLS;
extern int REC_STACK_ITEM_SIZE_CALLS;
extern int REC_TO_STACK_CALLS;
extern int REC_WITNESS_CALLS;
extern int REC_LOCK_TIME_CALLS;
extern int REC_TX_HASH_CALLS;

extern uint8_t REC_MAGIC[4];
extern uint8_t REC_BLOCK_SIZE[4];
extern uint8_t REC_HEADER_VERSION[4];
extern uint8_t REC_PREV_HASH[32];
extern uint8_t REC_MERKLE_ROOT[32];
extern uint8_t REC_BLOCK_TIME[4];
extern uint8_t REC_NBYTES[4];
extern uint8_t REC_NONCE[4];
extern uint8_t REC_BLOCK_HASH[32];
extern uint64_t REC_TRANSACTION_COUNT;
extern uint8_t REC_TX_VERSION[4];
extern uint8_t REC_FLAG;
extern uint64_t REC_TX_IN_COUNT;
extern uint8_t REC_TX_ID[32];
extern uint8_t REC_INPUT_VOUT[4];
extern uint64_t REC_SCRIPT_SIG_SIZE;
extern uint8_t *REC_SCRIPT_SIG;
extern uint8_t REC_TX_IN_SEQUENCE[4];
extern uint64_t REC_TX_OUT_COUNT;
extern uint8_t REC_AMOUNT[8];
extern uint64_t REC_PUB_KEY_SIZE;
extern uint8_t *REC_SCRIPT_PUB_KEY;
extern uint64_t REC_STACK_ITEMS_COUNT;
extern uint64_t REC_STACK_ITEM_SIZE;
extern uint8_t *REC_TO_STACK;
extern uint8_t *REC_WITNESS;
extern uint64_t REC_WITNESS_SIZE;
extern uint8_t REC_LOCK_TIME[4];
extern uint8_t REC_TX_HASH[32];

void recorder_reset(void);

#endif
