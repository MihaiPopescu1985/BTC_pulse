CC ?= gcc
CFLAGS ?= -O3 -march=native -DNDEBUG -Wall
LDFLAGS ?= -flto
LDLIBS ?= -lcrypto -lpthread

BUILD_DIR := build
APP := $(BUILD_DIR)/crawl
TEST_PARSER := $(BUILD_DIR)/test_blk_dat_parser
TEST_COMMON := $(BUILD_DIR)/test_block_common
TEST_MAIN := $(BUILD_DIR)/test_main

APP_SOURCES := src/main.c src/blk_dat_parser.c src/export_dispatch.c src/export_block.c src/export_debug.c src/block_common.c
TEST_RECORDER := tests/export_block_recorder.c

.PHONY: all unit-test integration-test test clean

all: $(APP)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(APP): $(APP_SOURCES) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(APP_SOURCES) $(LDLIBS)

$(TEST_PARSER): tests/test_blk_dat_parser.c src/blk_dat_parser.c $(TEST_RECORDER) tests/export_block_recorder.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(LDFLAGS) -Isrc -Itests -o $@ tests/test_blk_dat_parser.c src/blk_dat_parser.c $(TEST_RECORDER) $(LDLIBS)

$(TEST_COMMON): tests/test_block_common.c src/block_common.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(LDFLAGS) -Isrc -o $@ tests/test_block_common.c src/block_common.c

$(TEST_MAIN): tests/test_main.c src/main.c src/blk_dat_parser.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(LDFLAGS) -Isrc -o $@ tests/test_main.c

unit-test: $(TEST_PARSER) $(TEST_COMMON) $(TEST_MAIN)
	./$(TEST_PARSER)
	./$(TEST_COMMON)
	./$(TEST_MAIN)

integration-test: $(APP)
	bash tests/run_integration_test.sh

test: unit-test integration-test

clean:
	rm -f $(APP) $(TEST_PARSER) $(TEST_COMMON) $(TEST_MAIN)
