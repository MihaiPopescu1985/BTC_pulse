#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_parse_called = 0;
static int g_parse_return = 0;
static int g_mode_called = 0;
static char g_last_mode[32];

int parse_dat_file(FILE *dat_file)
{
    g_parse_called++;
    if (dat_file == NULL)
    {
        return 99;
    }
    return g_parse_return;
}

int export_set_mode_from_string(const char *mode)
{
    g_mode_called++;
    if (mode == NULL) {
        g_last_mode[0] = '\0';
    } else {
        strncpy(g_last_mode, mode, sizeof(g_last_mode) - 1);
        g_last_mode[sizeof(g_last_mode) - 1] = '\0';
    }
    return 0;
}

#define main crawler_main
#include "../src/main.c"
#undef main

static int failures = 0;

static void expect_int(const char *label, int expected, int actual)
{
    if (expected != actual)
    {
        fprintf(stderr, "[FAIL] %s: expected %d got %d\n", label, expected, actual);
        failures++;
    }
}

static void test_main_without_arg(void)
{
    char *argv[] = {(char *) "crawl", NULL};
    g_parse_called = 0;
    g_parse_return = 0;
    g_mode_called = 0;
    g_last_mode[0] = '\0';

    expect_int("main without arg return", 1, crawler_main(1, argv));
    expect_int("main without arg parse call", 0, g_parse_called);
    expect_int("main without arg mode call", 0, g_mode_called);
}

static void test_main_with_missing_file(void)
{
    char *argv[] = {(char *) "crawl", (char *) "tests/does-not-exist.dat", NULL};
    g_parse_called = 0;
    g_parse_return = 0;
    g_mode_called = 0;
    g_last_mode[0] = '\0';

    expect_int("main missing file return", 1, crawler_main(2, argv));
    expect_int("main missing file parse call", 0, g_parse_called);
    expect_int("main missing file mode call", 1, g_mode_called);
}

static void test_main_with_existing_file(void)
{
    char *argv[] = {(char *) "crawl", (char *) "tests/blk01985.dat", NULL};
    g_parse_called = 0;
    g_parse_return = 7;
    g_mode_called = 0;
    g_last_mode[0] = '\0';

    expect_int("main existing file return", 7, crawler_main(2, argv));
    expect_int("main existing file parse call", 1, g_parse_called);
    expect_int("main existing file mode call", 1, g_mode_called);
}

static void test_main_with_explicit_mode(void)
{
    char *argv[] = {(char *) "crawl", (char *) "tests/blk01985.dat", (char *) "debug", NULL};
    g_parse_called = 0;
    g_parse_return = 0;
    g_mode_called = 0;
    g_last_mode[0] = '\0';

    expect_int("main explicit mode return", 0, crawler_main(3, argv));
    expect_int("main explicit mode parse call", 1, g_parse_called);
    expect_int("main explicit mode mode call", 1, g_mode_called);
    if (strcmp(g_last_mode, "debug") != 0) {
        fprintf(stderr, "[FAIL] main explicit mode value: expected debug got %s\n", g_last_mode);
        failures++;
    }
}

int main(void)
{
    test_main_without_arg();
    test_main_with_missing_file();
    test_main_with_existing_file();
    test_main_with_explicit_mode();

    if (failures != 0)
    {
        fprintf(stderr, "test_main: %d failure(s)\n", failures);
        return 1;
    }

    printf("test_main: all tests passed\n");
    return 0;
}
