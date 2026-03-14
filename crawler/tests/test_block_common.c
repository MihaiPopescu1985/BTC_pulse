#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern char *PARSED_BLOCK;
extern uint64_t PARSED_BLOCK_INDEX;

void _append_hex(uint8_t *data, size_t size);
void _append_char(char *message, uint64_t size);
void _append_int(uint64_t number);
void _resize_block(uint64_t new_size);
void _reset(void);

static int failures = 0;

static void expect_int(const char *label, uint64_t expected, uint64_t actual)
{
    if (expected != actual)
    {
        fprintf(stderr, "[FAIL] %s: expected %llu got %llu\n",
                label,
                (unsigned long long) expected,
                (unsigned long long) actual);
        failures++;
    }
}

static void expect_mem(const char *label, const char *expected, const char *actual, size_t len)
{
    if (memcmp(expected, actual, len) != 0)
    {
        fprintf(stderr, "[FAIL] %s: content mismatch\n", label);
        failures++;
    }
}

static void test_append_hex(void)
{
    uint8_t bytes[] = {0x00u, 0xAFu, 0x10u};
    const char expected[] = "00AF10";

    _reset();
    _resize_block(6u);
    _append_hex(bytes, sizeof(bytes));

    expect_int("append_hex index", 6u, PARSED_BLOCK_INDEX);
    expect_mem("append_hex output", expected, PARSED_BLOCK, 6u);
    _reset();
}

static void test_append_int_fixed_width(void)
{
    const char expected[] = "00000000000000012345";

    _reset();
    _resize_block(20u);
    _append_int(12345u);

    expect_int("append_int index", 20u, PARSED_BLOCK_INDEX);
    expect_mem("append_int output", expected, PARSED_BLOCK, 20u);
    _reset();
}

static void test_reset_clears_state(void)
{
    _reset();
    _resize_block(4u);
    _append_char("ABCD", 4u);

    _reset();
    expect_int("reset index", 0u, PARSED_BLOCK_INDEX);
    _append_char("WXYZ", 4u);
    expect_int("append after reset", 4u, PARSED_BLOCK_INDEX);
}

int main(void)
{
    test_append_hex();
    test_append_int_fixed_width();
    test_reset_clears_state();

    if (failures != 0)
    {
        fprintf(stderr, "test_block_common: %d failure(s)\n", failures);
        return 1;
    }

    printf("test_block_common: all tests passed\n");
    return 0;
}
