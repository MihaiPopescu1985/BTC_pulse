#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "blk_dat_parser.h"
#include "export_block.h"
#include "xor_reader.h"

// Parse a hex string like "92790676bfcf3f03" into bytes. Returns the number of
// bytes written, or -1 on a malformed string.
static int parse_hex_key(const char *hex, uint8_t *out, size_t out_cap)
{
    size_t len = strlen(hex);
    if (len % 2 != 0) return -1;
    size_t nbytes = len / 2;
    if (nbytes > out_cap) return -1;

    for (size_t i = 0; i < nbytes; i++) {
        char c1 = hex[2 * i];
        char c2 = hex[2 * i + 1];
        int hi, lo;
        if      (c1 >= '0' && c1 <= '9') hi = c1 - '0';
        else if (c1 >= 'a' && c1 <= 'f') hi = c1 - 'a' + 10;
        else if (c1 >= 'A' && c1 <= 'F') hi = c1 - 'A' + 10;
        else return -1;
        if      (c2 >= '0' && c2 <= '9') lo = c2 - '0';
        else if (c2 >= 'a' && c2 <= 'f') lo = c2 - 'a' + 10;
        else if (c2 >= 'A' && c2 <= 'F') lo = c2 - 'A' + 10;
        else return -1;
        out[i] = (uint8_t) ((hi << 4) | lo);
    }
    return (int) nbytes;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: %s <path-to-dat-file> [sql|debug|stats] [--xor <hexkey>|--no-xor]\n",
            argv[0]);
        return 1;
    }

    const char *export_mode = getenv("CRAWL_EXPORT_MODE");
    if (argc >= 3 && argv[2][0] != '-') export_mode = argv[2];
    if (export_set_mode_from_string(export_mode) != 0) {
        fprintf(stderr, "Unsupported export mode '%s'. Use sql, debug or stats.\n", export_mode);
        return 1;
    }

    // Determine the obfuscation key.
    //   default : auto-load from blocks/xor.dat next to the .dat file
    //   --xor H : use the explicit hex key H
    //   --no-xor: force no de-obfuscation (read the file as-is)
    uint8_t key[64];
    size_t key_len = 0;
    int force_no_xor = 0;
    const char *explicit_hex = NULL;

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--no-xor") == 0) {
            force_no_xor = 1;
        } else if (strcmp(argv[i], "--xor") == 0 && i + 1 < argc) {
            explicit_hex = argv[i + 1];
            i++;
        }
    }

    if (force_no_xor) {
        key_len = 0;
    } else if (explicit_hex != NULL) {
        int n = parse_hex_key(explicit_hex, key, sizeof(key));
        if (n < 0) {
            fprintf(stderr, "Invalid --xor hex key '%s'.\n", explicit_hex);
            return 1;
        }
        key_len = (size_t) n;
    } else {
        // Auto-load from blocks/xor.dat. Absent file => no obfuscation.
        key_len = sizeof(key);
        int rc = xor_load_key_for(argv[1], key, &key_len);
        if (rc < 0) {
            fprintf(stderr, "Failed to read xor.dat key.\n");
            return 1;
        }
        // rc == 1 (no xor.dat) leaves key_len = 0 => passthrough.
    }

    // Open the file through the transparent de-obfuscating wrapper.
    FILE *dat_file = xor_fopen(argv[1], key_len > 0 ? key : NULL, key_len);
    if (dat_file == NULL) {
        fprintf(stderr, "Dat file could not be opened\n");
        return 1;
    }

    int result = parse_dat_file(dat_file);
    fclose(dat_file);

    if (result != 0) fprintf(stderr, "Parsing failed. Error code %d\n", result);
    return result;
}
