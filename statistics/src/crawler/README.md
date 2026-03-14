# Query Script Guide

## Purpose

`query.py` is the orchestration script for the data pipeline that starts from raw Bitcoin `blk*.dat` files and produces:

- per-file SQLite databases (`blkNNNNN.db`)
- aggregated on-chain features (`btc_amounts.db`, daily tx-size distribution)
- frontend-ready JSON files
- derived statistics artifacts in the `statistics` project

`binance.py` is used by `query.py` to fetch daily BTC/USDT candles from Binance.

## Files

- `script/query.py`: main pipeline
- `script/binance.py`: Binance REST fetch helper

## End-to-end workflow

Running `python3 script/query.py` executes:

1. `prepare_data()`
2. `export_data()`
3. `publish_changes()`

### 1) prepare_data()

- Parses `blk*.dat` files from `DAT_FILES`
- Creates missing per-file databases in `DATABASE_FOLDER`
- Imports crawler SQL output into SQLite (`block`, `tx`, `out`)
- Detects duplicate block hashes across DB files
- Updates daily BTC amount aggregate database (`btc_amounts.db`)

### 2) export_data()

- Exports daily amount JSON
- Exports daily transaction-size bucket JSON
- Updates daily price JSON from Binance
- Copies generated JSON files to:
  - `frontend/_data`
  - `statistics/data`
- Runs `statistics/generate_statistics.sh`
- Copies generated features back to `frontend/_data`

### 3) publish_changes()

- Runs `git add`, `git commit`, `git push` in the frontend repository.

## Runtime dependencies

Python packages/modules:

- stdlib: `sqlite3`, `datetime`, `pathlib`, `json`, `subprocess`, `os`, `shutil`
- third-party: `requests` (via `binance.py`)

External commands:

- `sqlite3`
- crawler binary (`crawl`)
- `git`

## Current configured paths (hardcoded)

From `script/query.py`:

- dat files: `/media/mihai/BTC/bitcoin-data/blocks`
- database folder: `/media/mihai/BTC/db`
- crawler binary: `/media/mihai/BTC/db/crawl`
- query config: `/media/mihai/BTC/bitcoin-data/.btc_query_config`
- frontend data output: `/home/mihai/Documents/BTC_pulse/frontend/_data`
- statistics repo: `/home/mihai/Documents/BTC_pulse/statistics`

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
5. Bootstrap:
   - `.btc_query_config` file
   - `btc_amounts.db` with table `days(date PRIMARY KEY, amount)`

## Moving to `statistics` repository

If you migrate `query.py` and `binance.py` to `/home/mihai/Documents/BTC_pulse/statistics`, recommended next refactor:

1. Replace hardcoded paths with env vars or CLI args.
2. Separate pipeline stages into explicit commands:
   - parse on-chain
   - export JSON
   - generate statistics
   - publish
3. Make `publish_changes()` optional (default off).
4. Keep a small migration note in `statistics/README.md` pointing to this file.
