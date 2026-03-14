# BTC Crawler

## What this project does

`crawler` parses Bitcoin `blk*.dat` files and streams parsed data to `stdout`.

The parser reads block headers and transactions, computes hashes, and emits one of two output formats:

- `sql` mode (default): SQL `INSERT` statements for `block`, `tx`, and `out`
- `debug` mode: verbose human-readable parsed fields

This is intended for fast offline ingestion/inspection of raw blockchain block files.

## Core flow

1. `src/main.c` opens a `.dat` file and selects exporter mode.
2. `src/blk_dat_parser.c` parses blocks and transactions from the binary stream.
3. `src/export_dispatch.c` routes each `export_*` callback to the active backend.
4. Backend writes formatted output to `stdout`.

## Runtime exporter selection

The same `crawl` binary supports both backends at runtime.

- CLI argument: `./build/crawl <dat-file> [sql|debug]`
- Environment variable: `CRAWL_EXPORT_MODE=sql|debug`

Examples:

```bash
./build/crawl tests/blk01985.dat
./build/crawl tests/blk01985.dat debug
CRAWL_EXPORT_MODE=debug ./build/crawl tests/blk01985.dat
```

If both are set, the CLI argument takes precedence.

## Build

Requirements:

- `gcc`
- OpenSSL development headers/libs (`libcrypto`)
- POSIX environment (Linux/macOS shell)

Build:

```bash
make
```

Output binary:

- `build/crawl`

## Typical SQL usage

Generate SQL from a dat file:

```bash
./build/crawl /path/to/blk01985.dat > blk01985.sql
```

Pipe directly into SQLite:

```bash
(
  echo "BEGIN TRANSACTION;"
  echo "PRAGMA foreign_keys = ON;"
  ./build/crawl /path/to/blk01985.dat
  echo "COMMIT;"
) | sqlite3 blk01985.db
```

## Benchmark snapshot

This benchmark is only a reference point. Runtime depends on CPU, storage speed, kernel, compiler, and current system load.

Benchmark fixture:

- Input file: `tests/blk01985.dat`
- Input size: `133,521,047 bytes` (~128 MiB)

Command profile:

- Build flags: `-O3 -march=native -DNDEBUG -flto`
- Runtime command:
`./build/crawl tests/blk01985.dat [sql|debug]`
- Timing method: shell `time`, 5 runs, output redirected to `/dev/null`

Measured output volume:

- SQL mode: `932,915` lines, `199,899,261` bytes
- Debug mode: `8,686,021` lines, `604,436,703` bytes

Measured runtime (this machine):

- SQL mode average: `2.697 s` (runs: `2.759, 2.737, 2.639, 2.683, 2.669`)
- Debug mode average: `3.019 s` (runs: `3.104, 3.069, 2.977, 2.968, 2.977`)

Reference machine info:

- OS: `Linux 6.1.0-42-amd64 x86_64`
- CPU: `Intel(R) Core(TM) i5-8300H CPU @ 2.30GHz` (4 cores / 8 threads, up to 4.00 GHz)
- RAM: `15 GiB`

How to extend benchmarks:

- Add more fixtures under `tests/` (small, medium, large)
- Add a script that runs each fixture in both modes and logs:
  - input size
  - output size
  - average/median runtime across N runs
  - output hash for SQL mode regression stability

## Tests

Testing requires the presence of the file `tests/blk01985.dat`.  
This is the `.dat` file from the blockchain, not included in the repo because of its size.  

Run unit tests:

```bash
make unit-test
```

Unit test binaries:

- `build/test_blk_dat_parser`
- `build/test_block_common`
- `build/test_main`

Run integration test:

```bash
make integration-test
```

Integration test checks:

- SQL output hash for `tests/blk01985.dat`
- non-zero exit on a truncated fixture

Run full test suite:

```bash
make test
```

Clean build artifacts:

```bash
make clean
```

## Project structure

- `src/main.c`: CLI entrypoint and mode selection
- `src/blk_dat_parser.c`, `src/blk_dat_parser.h`: block/transaction parser core
- `src/export_dispatch.c`: runtime dispatch to active exporter backend
- `src/export_block.c`: SQL exporter backend
- `src/export_debug.c`: debug-text exporter backend
- `src/export_block.h`: shared exporter API
- `src/block_common.c`, `src/block_common.h`: shared output-buffer utilities
- `tests/`: unit and integration tests plus test fixtures
