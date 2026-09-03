#include <stdint.h>
#include <string.h>

#include "export_block.h"

#define EXPORT_CALLBACKS(X) \
    X(magic_number, (uint8_t magic_bytes[4]), (magic_bytes)) \
    X(block_size, (uint8_t block_size[4]), (block_size)) \
    X(header_version, (uint8_t header_version[4]), (header_version)) \
    X(prev_hash, (uint8_t prev_hash[32]), (prev_hash)) \
    X(merkle_root, (uint8_t merkle_root[32]), (merkle_root)) \
    X(block_time, (uint8_t block_time[4]), (block_time)) \
    X(nbytes, (uint8_t nbyes[4]), (nbyes)) \
    X(nonce, (uint8_t nonce[4]), (nonce)) \
    X(block_hash, (unsigned char block_hash[32]), (block_hash)) \
    X(transaction_count, (uint64_t tx_count), (tx_count)) \
    X(tx_version, (uint8_t tx_version[4]), (tx_version)) \
    X(flag, (uint8_t flag), (flag)) \
    X(tx_in_count, (uint64_t tx_in_count), (tx_in_count)) \
    X(tx_id, (uint8_t tx_id[32]), (tx_id)) \
    X(input_vout, (uint8_t vout[4]), (vout)) \
    X(script_sig_size, (uint64_t script_sig_size), (script_sig_size)) \
    X(script_sig, (uint8_t *script_sig), (script_sig)) \
    X(tx_in_sequence, (uint8_t tx_in_sequence[4]), (tx_in_sequence)) \
    X(tx_out_count, (uint64_t tx_out_count), (tx_out_count)) \
    X(amount, (uint8_t amount[8]), (amount)) \
    X(pub_key_size, (uint64_t pub_key_size), (pub_key_size)) \
    X(script_pub_key, (uint8_t *script_pub_key), (script_pub_key)) \
    X(stack_items_count, (uint64_t stack_items), (stack_items)) \
    X(stack_item_size, (uint64_t size), (size)) \
    X(to_stack, (uint8_t *to_stack), (to_stack)) \
    X(witness, (uint8_t *witness, uint64_t witness_size), (witness, witness_size)) \
    X(lock_time, (uint8_t lock_time[4]), (lock_time)) \
    X(tx_hash, (uint8_t tx_hash[32]), (tx_hash)) \
    X(flush, (void), ())

#define DECLARE_BLOCK(name, args, call) void block_export_##name args;
#define DECLARE_DEBUG(name, args, call) void debug_export_##name args;
EXPORT_CALLBACKS(DECLARE_BLOCK)
EXPORT_CALLBACKS(DECLARE_DEBUG)
#undef DECLARE_BLOCK
#undef DECLARE_DEBUG

typedef struct export_backend {
#define BACKEND_FIELD(name, args, call) void (*name) args;
    EXPORT_CALLBACKS(BACKEND_FIELD)
#undef BACKEND_FIELD
} export_backend_t;

static const export_backend_t BLOCK_BACKEND = {
#define ASSIGN_BLOCK(name, args, call) .name = block_export_##name,
    EXPORT_CALLBACKS(ASSIGN_BLOCK)
#undef ASSIGN_BLOCK
};

static const export_backend_t DEBUG_BACKEND = {
#define ASSIGN_DEBUG(name, args, call) .name = debug_export_##name,
    EXPORT_CALLBACKS(ASSIGN_DEBUG)
#undef ASSIGN_DEBUG
};

static const export_backend_t *ACTIVE_BACKEND = &BLOCK_BACKEND;

void export_set_mode(export_mode_t mode)
{
    ACTIVE_BACKEND = (mode == EXPORT_MODE_DEBUG) ? &DEBUG_BACKEND : &BLOCK_BACKEND;
}

int export_set_mode_from_string(const char *mode)
{
    if (mode == NULL) return 0;
    if (strcmp(mode, "sql") == 0 || strcmp(mode, "block") == 0) {
        export_set_mode(EXPORT_MODE_SQL);
        return 0;
    }
    if (strcmp(mode, "debug") == 0) {
        export_set_mode(EXPORT_MODE_DEBUG);
        return 0;
    }
    return 1;
}

#define DISPATCH(name, args, call) \
    void export_##name args { ACTIVE_BACKEND->name call; }
EXPORT_CALLBACKS(DISPATCH)
#undef DISPATCH
#undef EXPORT_CALLBACKS
