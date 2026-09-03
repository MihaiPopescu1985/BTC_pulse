#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>


char *PARSED_BLOCK = NULL;
uint64_t PARSED_BLOCK_INDEX = 0;
static uint64_t PARSED_BLOCK_CAPACITY = 0;


void _hex_conversion(uint8_t byte, char *as_hex, uint32_t index) {
    // writes the hex representation of <byte> to as_hex[index]
    static const char hex_char_map[16] = "0123456789ABCDEF";
    as_hex[index] = hex_char_map[(byte >> 4) & 0x0F];
    as_hex[index + 1] = hex_char_map[byte & 0x0F];
}

void _append_hex(uint8_t *data, size_t size) {
    // Every uint8_t is occupying 2 bytes
    for (size_t i = 0; i < size; ++i) {
        _hex_conversion(data[i], PARSED_BLOCK, PARSED_BLOCK_INDEX);
        PARSED_BLOCK_INDEX+=2;
    }
}

void _append_char(char *message, uint64_t size) {
    memcpy(PARSED_BLOCK + PARSED_BLOCK_INDEX, message, size);
    PARSED_BLOCK_INDEX += size;
}

void _append_int(uint64_t number) {
    for (int i = 19; i >= 0; i--) {
        PARSED_BLOCK[PARSED_BLOCK_INDEX + i] = 48 + (number % 10); // the char 0 + reminder
        number = number / 10;
    }
    PARSED_BLOCK_INDEX += 20;
}

void _resize_block(uint64_t new_size) {
    uint64_t needed = PARSED_BLOCK_INDEX + new_size;
    if (needed <= PARSED_BLOCK_CAPACITY) {
        return;
    }

    uint64_t new_capacity = PARSED_BLOCK_CAPACITY == 0 ? 4096 : PARSED_BLOCK_CAPACITY;
    while (new_capacity < needed) {
        new_capacity *= 2;
    }

    void *new_block = realloc(PARSED_BLOCK, new_capacity);

    if (new_block == NULL) {
        if (PARSED_BLOCK != NULL) {
            free(PARSED_BLOCK);
            perror("Error resizing PARSED_BLOCK");
            exit(-2);
        }
    }
    PARSED_BLOCK = new_block;
    PARSED_BLOCK_CAPACITY = new_capacity;
}

void _reset() {
    PARSED_BLOCK_INDEX = 0;
}
