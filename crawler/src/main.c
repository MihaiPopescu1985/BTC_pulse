#include <stdlib.h>
#include <stdio.h>

#include "blk_dat_parser.h"
#include "export_block.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <path-to-dat-file> [sql|debug]\n", argv[0]);
        return 1;
    }

    const char *export_mode = getenv("CRAWL_EXPORT_MODE");
    if (argc >= 3) export_mode = argv[2];
    if (export_set_mode_from_string(export_mode) != 0) {
        fprintf(stderr, "Unsupported export mode '%s'. Use sql or debug.\n", export_mode);
        return 1;
    }

    // Read the file
    FILE *dat_file = fopen(argv[1], "rb");
    if (dat_file == NULL) {
        fprintf(stderr, "Dat file could not be opened\n");
        return 1;
    }
    setvbuf(dat_file, NULL, _IOFBF, 8 * 1024 * 1024);

    int result = parse_dat_file(dat_file);
    fclose(dat_file);

    if(result != 0) fprintf(stderr, "Parsing failed. Error code %d\n", result);
    return result;
}
