# Data Retrieval Guide

## Purpose

`query.py` is the orchestration script for the BTC data-retrieval pipeline that starts from raw Bitcoin `blk*.dat` files and produces:

- per-file SQLite databases (`blkNNNNN.db`)
- aggregated on-chain features (`btc_amounts.db`, daily tx-size distribution)
- BTC data inputs for the local `statistics/data` directory

`binance.py` is used by `query.py` to fetch daily BTC/USDT candles from Binance.

## Files

- `src/data/query.py`: main retrieval pipeline
- `src/data/binance.py`: Binance REST fetch helper

## End-to-end workflow

Running `python3 src/data/query.py` executes:

1. `prepare_data()`
2. `export_data()`

### 1) prepare_data()

Runs three steps in order:

1. `parse_dat_file()`
   - Parses `blk*.dat` files from `DAT_FILES`
   - Creates missing per-file databases in `DATABASE_FOLDER`
   - Imports crawler SQL output into SQLite (`block`, `tx`, `out`)
2. `build_main_chain()`
   - Copies every per-file database's blocks into `chain.db`; a block written to
     two `blk*.dat` files keeps the first file it was seen in, which becomes its
     canonical database
   - Rebuilds `chain.main_chain` (height, hash, db_file) by walking the
     `prev_hash` links forward from genesis, then back from the highest block
   - Leaves out the newest `MIN_CONFIRMATIONS` (6) blocks until they are settled,
     and skips blocks after a gap until the gap is filled
   - Stale (orphan) blocks stay out of `main_chain`, so the aggregates below
     count main-chain blocks only
3. `get_day_btc_amount()`
   - Updates daily BTC amount aggregate database (`btc_amounts.db`)

### 2) export_data()

- Exports daily amount JSON
- Exports daily transaction-size bucket JSON
- Updates daily price JSON from Binance
- Writes all three files directly into `statistics/data`
- Does not copy data into any sibling project under `BTC_PULSE`

## Runtime dependencies

Python packages/modules:

- stdlib: `sqlite3`, `datetime`, `pathlib`, `json`, `subprocess`, `os`, `shutil`
- third-party: `requests` (via `binance.py`)

External commands:

- `sqlite3`
- crawler binary (`crawl`)

## Current configured paths (hardcoded)

From `src/data/query.py`:

- dat files: `/media/mihai/Expansion/bitcoin-data/blocks`
- database folder: `/media/mihai/BTC/db`
- crawler binary: `/media/mihai/BTC/db/crawl`
- main-chain database: `/media/mihai/BTC/db/chain.db`
- amounts database: `/media/mihai/BTC/db/btc_amounts.db`
- query config: `/media/mihai/BTC/db/.btc_query_config`
- statistics data output: `<repo>/statistics/data`

The split is deliberate: the node and its `blk*.dat` files live on the HDD
because the node writes continuously, while the databases live on the SSD
because they are written once and then only read.

## Configuration file expectations

The config JSON (`.btc_query_config`) tracks incremental processing pointers, including:

- `last_dat_file_parsed`
- `last_day_amount_db_parse`
- `last_day_amount_datetime_parse`
- `last_tx_size_db_parsed` (added when tx-size export runs)

## Reproducibility on another machine (from only `.dat` files)

Minimum needed:

1. Build `crawl` from [this repository](https://github.com/MihaiPopescu1985/Bitcoin-crawler/tree/main).
2. Place `crawl` where `query.py` expects it, or update path constant.
3. Ensure `sqlite3` and Python dependencies are installed.
4. Provide writable dat/db/config locations.

No manual bootstrap is needed: `.btc_query_config`, `btc_amounts.db` and
`chain.db` are each created on first use with their expected schema.

## Further cleanup

1. Replace hardcoded paths with env vars or CLI args.
2. Keep retrieval logic scoped to local `statistics/data` only.
3. Preserve independence from any sibling project in the BTC_PULSE repository.
