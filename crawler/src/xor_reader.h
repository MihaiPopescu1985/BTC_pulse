#ifndef XOR_READER_H
#define XOR_READER_H

#include <stdio.h>
#include <stdint.h>

// Bitcoin Core (v28+) XOR-obfuscates the blk*.dat files in the blocks
// directory with an 8-byte key stored in blocks/xor.dat. This wrapper returns
// a FILE* that transparently de-obfuscates every byte as it is read, so the
// existing parser can consume it unchanged.
//
// The de-obfuscation is: plaintext_byte = file_byte XOR key[absolute_offset % 8]
//
// key/key_len: the obfuscation key bytes (typically 8). If key_len == 0 or all
// key bytes are zero, no transformation is applied (the file is read as-is).
//
// Returns a readable FILE* on success (fclose it normally), or NULL on error.
FILE *xor_fopen(const char *path, const uint8_t *key, size_t key_len);

// Load the obfuscation key from a blocks/xor.dat file next to the given .dat
// file path. Writes up to *key_len bytes into key_out and updates *key_len to
// the number of bytes actually read. Returns 0 on success (key found and read),
// 1 if no xor.dat exists (caller should treat as "no obfuscation"), negative on
// a real error.
int xor_load_key_for(const char *dat_path, uint8_t *key_out, size_t *key_len);

#endif
