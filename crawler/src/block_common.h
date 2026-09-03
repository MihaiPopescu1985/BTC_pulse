#ifndef BLOCK_COMMON_H
#define BLOCK_COMMON_H

#include <stdint.h>
#include <stddef.h>

extern char *PARSED_BLOCK;
extern uint64_t PARSED_BLOCK_INDEX;

void _hex_conversion(uint8_t byte, char *as_hex, uint32_t index);
void _append_hex(uint8_t *data, size_t size);
void _append_char(char *message, uint64_t size);
void _append_int(uint64_t number);
void _resize_block(uint64_t new_size);
void _reset(void);

#endif
