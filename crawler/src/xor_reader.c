// Transparent XOR-deobfuscating FILE* wrapper for Bitcoin Core blk*.dat files.
//
// Bitcoin Core v28+ stores an 8-byte XOR key in blocks/xor.dat and obfuscates
// every byte written to the blk*.dat files with it. We wrap the underlying file
// in a custom stream (via glibc fopencookie) that reverses the XOR on read,
// keyed by the absolute byte offset, so the parser sees plaintext and never
// needs to know obfuscation happened.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include "xor_reader.h"

typedef struct {
    FILE *inner;          // the real, obfuscated file
    uint8_t key[64];      // obfuscation key
    size_t key_len;       // number of key bytes (0 => passthrough)
    int passthrough;      // 1 if no transformation should be applied
    uint64_t pos;         // absolute offset of the next byte read from inner
} xor_cookie;

// XOR `n` bytes of `buf`, which start at absolute file offset `pos`, with the
// repeating key. The parser seeks backwards very often (compact sizes), and every
// seek makes the stream refill its whole buffer through xor_read, so this loop
// runs over far more bytes than the file holds and must be fast: no per-byte
// modulo, and 8 bytes at a time for Bitcoin Core's 8-byte key.
static void xor_buffer(const xor_cookie *ck, uint8_t *buf, size_t n, uint64_t pos)
{
    size_t klen = ck->key_len;
    size_t k = (size_t) (pos % klen);
    size_t i = 0;

    if (klen == 8) {
        uint8_t rotated[8];
        for (size_t j = 0; j < 8; j++) rotated[j] = ck->key[(k + j) & 7];
        uint64_t key64;
        memcpy(&key64, rotated, 8);
        for (; i + 8 <= n; i += 8) {
            uint64_t word;
            memcpy(&word, buf + i, 8);
            word ^= key64;
            memcpy(buf + i, &word, 8);
        }
        k = (k + i) & 7;   // i is a multiple of 8, so k is unchanged
    }

    for (; i < n; i++) {
        buf[i] ^= ck->key[k];
        if (++k == klen) k = 0;
    }
}

static ssize_t xor_read(void *c, char *buf, size_t size)
{
    xor_cookie *ck = (xor_cookie *) c;

    size_t n = fread(buf, 1, size, ck->inner);
    if (n == 0) {
        if (ferror(ck->inner)) return -1;
        return 0; // EOF
    }

    if (!ck->passthrough && ck->key_len > 0) {
        xor_buffer(ck, (uint8_t *) buf, n, ck->pos);
    }
    ck->pos += n;

    return (ssize_t) n;
}

static int xor_seek(void *c, off64_t *offset, int whence)
{
    xor_cookie *ck = (xor_cookie *) c;
    if (fseek(ck->inner, (long) *offset, whence) != 0) {
        return -1;
    }
    long pos = ftell(ck->inner);
    if (pos < 0) return -1;
    ck->pos = (uint64_t) pos;
    *offset = (off64_t) pos;   // report the resulting absolute position
    return 0;
}

static int xor_close(void *c)
{
    xor_cookie *ck = (xor_cookie *) c;
    int rc = 0;
    if (ck->inner) rc = fclose(ck->inner);
    free(ck);
    return rc;
}

FILE *xor_fopen(const char *path, const uint8_t *key, size_t key_len)
{
    xor_cookie *ck = (xor_cookie *) calloc(1, sizeof(xor_cookie));
    if (ck == NULL) return NULL;

    ck->inner = fopen(path, "rb");
    if (ck->inner == NULL) {
        free(ck);
        return NULL;
    }

    // A bigger buffer on the inner file keeps physical reads large/sequential.
    setvbuf(ck->inner, NULL, _IOFBF, 8 * 1024 * 1024);

    ck->key_len = 0;
    ck->passthrough = 1;
    if (key != NULL && key_len > 0 && key_len <= sizeof(ck->key)) {
        // If every key byte is zero, obfuscation is effectively off.
        int all_zero = 1;
        for (size_t i = 0; i < key_len; i++) {
            if (key[i] != 0) { all_zero = 0; break; }
        }
        if (!all_zero) {
            memcpy(ck->key, key, key_len);
            ck->key_len = key_len;
            ck->passthrough = 0;
        }
    }

    cookie_io_functions_t io = {
        .read = xor_read,
        .write = NULL,
        .seek = xor_seek,
        .close = xor_close,
    };

    FILE *f = fopencookie(ck, "rb", io);
    if (f == NULL) {
        fclose(ck->inner);
        free(ck);
        return NULL;
    }
    return f;
}

// Build the path to blocks/xor.dat given a path to a blk*.dat file, i.e. replace
// the final path component with "xor.dat".
static void sibling_xor_path(const char *dat_path, char *out, size_t out_sz)
{
    const char *slash = strrchr(dat_path, '/');
    if (slash == NULL) {
        snprintf(out, out_sz, "xor.dat");
    } else {
        size_t dir_len = (size_t) (slash - dat_path) + 1; // include the slash
        if (dir_len >= out_sz) dir_len = out_sz - 1;
        memcpy(out, dat_path, dir_len);
        out[dir_len] = '\0';
        strncat(out, "xor.dat", out_sz - strlen(out) - 1);
    }
}

int xor_load_key_for(const char *dat_path, uint8_t *key_out, size_t *key_len)
{
    char xor_path[4096];
    sibling_xor_path(dat_path, xor_path, sizeof(xor_path));

    FILE *f = fopen(xor_path, "rb");
    if (f == NULL) {
        // No xor.dat -> not an error; caller treats as "no obfuscation".
        *key_len = 0;
        return 1;
    }

    size_t cap = *key_len;
    size_t n = fread(key_out, 1, cap, f);
    fclose(f);

    *key_len = n;
    return (n > 0) ? 0 : -1;
}
