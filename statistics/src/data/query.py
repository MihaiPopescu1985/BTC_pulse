import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import subprocess
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import binance

STATISTICS_DIR = Path(__file__).resolve().parents[2]
STATISTICS_DATA_DIR = STATISTICS_DIR / "data"
# All dates are UTC, exactly as the block timestamps are on the blockchain.
GENESIS_DATE = "03-01-2009 18:15:05"
DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
# The node and its blk*.dat files live on the HDD; the databases on the SSD.
# The node writes continuously, the databases are written once and then only read.
DAT_FILES = Path("/media/mihai/Expansion/bitcoin-data/blocks")
DATABASE_FOLDER = Path("/media/mihai/BTC/db")
CRAWL_BIN = DATABASE_FOLDER / "crawl"
BTC_AMOUNT_DB = DATABASE_FOLDER / "btc_amounts.db"
CHAIN_DB = DATABASE_FOLDER / "chain.db"
BTC_QUERY_CONFIG = DATABASE_FOLDER / ".btc_query_config"
# Blocks closer than this to the tip are left out of the main chain: two competing
# blocks at the tip are only settled once more blocks are built on top of them.
MIN_CONFIRMATIONS = 6
# Thermal guard for the database SSD (composite temperature, the value the drive
# itself uses; this drive warns at 75 °C and is critical at 80 °C). Long runs
# pause between files at THERMAL_PAUSE_AT and continue below THERMAL_RESUME_AT.
THERMAL_PAUSE_AT = 68
THERMAL_RESUME_AT = 55
THERMAL_POLL_SECONDS = 30
DEFAULT_DAY_PARSE_CONFIG = {
            "last_day_amount_db_parse": str(DATABASE_FOLDER / "blk00000.db"),
            "last_day_amount_datetime_parse": 1231006505,
            "last_dat_file_parsed": str(DAT_FILES / "blk00000.dat")
        }
TX_SIZE_BUCKETS = [
    ("0-0.001 BTC", 0, 100_000),
    ("0.001-0.01 BTC", 100_000, 1_000_000),
    ("0.01-0.1 BTC", 1_000_000, 10_000_000),
    ("0.1-1 BTC", 10_000_000, 100_000_000),
    ("1-10 BTC", 100_000_000, 1_000_000_000),
    ("10-100 BTC", 1_000_000_000, 10_000_000_000),
    ("100-1000 BTC", 10_000_000_000, 100_000_000_000),
    ("1000+ BTC", 100_000_000_000, None)
]


def utc_from_timestamp(timestamp) -> datetime:
    """Block timestamp (Unix seconds) -> timezone-aware UTC datetime."""
    return datetime.fromtimestamp(timestamp, timezone.utc)

def parse_utc(text: str) -> datetime:
    """A DATE_FORMAT string, read as UTC (never as the machine's local time)."""
    return datetime.strptime(text, DATE_FORMAT).replace(tzinfo=timezone.utc)

def _nvme_hwmon_dir(path, sys_root="/sys"):
    """hwmon directory of the NVMe drive holding `path`, or None if not found.

    Follows /sys/dev/block/<major>:<minor> of the filesystem up through its
    parent devices until one has an hwmon whose name is "nvme" (kernels put it
    on the controller or on its PCI device).
    """
    dev = os.stat(path).st_dev
    block = os.path.join(sys_root, "dev", "block", f"{os.major(dev)}:{os.minor(dev)}")
    if not os.path.exists(block):
        return None
    current = os.path.realpath(block)
    root = os.path.realpath(sys_root)
    while current.startswith(root) and current != root:
        for hwmon in sorted(Path(current).glob("hwmon*/hwmon*")) + sorted(Path(current).glob("hwmon*")):
            name = hwmon / "name"
            if name.is_file() and name.read_text().strip() == "nvme" and (hwmon / "temp1_input").is_file():
                return hwmon
        current = os.path.dirname(current)
    return None

_SSD_HWMON = None
_SSD_HWMON_SEARCHED = False

def read_ssd_temperature():
    """Composite temperature (°C) of the database SSD, or None if unavailable."""
    global _SSD_HWMON, _SSD_HWMON_SEARCHED
    if not _SSD_HWMON_SEARCHED:
        _SSD_HWMON_SEARCHED = True
        try:
            _SSD_HWMON = _nvme_hwmon_dir(DATABASE_FOLDER)
        except OSError:
            _SSD_HWMON = None
        if _SSD_HWMON is None:
            print(f"Warning: no NVMe temperature sensor found for {DATABASE_FOLDER}; "
                  "thermal guard disabled.")
    if _SSD_HWMON is None:
        return None
    try:
        return int((_SSD_HWMON / "temp1_input").read_text()) / 1000
    except (OSError, ValueError):
        return None

def thermal_guard(verbose=True):
    """Wait while the database SSD is too hot. Call between files of a long run."""
    temperature = read_ssd_temperature()
    if temperature is None or temperature < THERMAL_PAUSE_AT:
        return
    print(f"{datetime.now():%H:%M:%S} SSD at {temperature:.0f} °C, pausing until it is "
          f"below {THERMAL_RESUME_AT} °C...", flush=True)
    while temperature is not None and temperature >= THERMAL_RESUME_AT:
        time.sleep(THERMAL_POLL_SECONDS)
        temperature = read_ssd_temperature()
        if verbose:
            print(f"{datetime.now():%H:%M:%S}   {temperature:.0f} °C", flush=True)
    print(f"{datetime.now():%H:%M:%S} SSD at {temperature:.0f} °C, continuing.", flush=True)

def load_config() -> dict:
    """Read the query config, creating it with the defaults if it does not exist."""
    if not BTC_QUERY_CONFIG.exists():
        save_config(dict(DEFAULT_DAY_PARSE_CONFIG))
    return json.loads(BTC_QUERY_CONFIG.read_text())

def save_config(config: dict):
    if BTC_QUERY_CONFIG.exists():
        os.chmod(BTC_QUERY_CONFIG, 0o666)
    BTC_QUERY_CONFIG.write_text(json.dumps(config))
    os.chmod(BTC_QUERY_CONFIG, 0o444)

def connect_readonly(database) -> sqlite3.Connection:
    """Open a per-file database for queries without writing anything to disk.

    mode=ro&immutable=1: no journal, no locks, no writes (the databases are
    read-only once loaded). temp_store=MEMORY keeps sort/GROUP BY temp files in
    RAM instead of on the SSD. chain.db is attached, also read-only, so queries
    can keep only main-chain blocks (see MAIN_CHAIN_JOIN).
    """
    conn = sqlite3.connect(f"file:{database}?mode=ro&immutable=1", uri=True)
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("ATTACH DATABASE ? AS chain;", (f"file:{CHAIN_DB}?mode=ro&immutable=1",))
    return conn

# Keeps a block only if it is on the main chain AND this database is the file the
# block was first stored in. That drops stale (orphan) blocks and counts a block
# that was written to two blk*.dat files only once. Bind :db_file to the
# database's file name, e.g. "blk00012.db".
MAIN_CHAIN_JOIN = "JOIN chain.main_chain AS m ON m.hash = b.hash AND m.db_file = :db_file"

def _build_tx_size_query() -> str:
    """
    Returns the SQL query that aggregates transactions into the predefined size buckets by day.
    """
    bucket_cases = []
    for idx, (_, lower, upper) in enumerate(TX_SIZE_BUCKETS):
        if upper is None:
            bucket_cases.append(
                f"SUM(CASE WHEN total_amount >= {lower} THEN 1 ELSE 0 END) AS bucket_{idx}"
            )
        else:
            bucket_cases.append(
                f"SUM(CASE WHEN total_amount >= {lower} AND total_amount < {upper} THEN 1 ELSE 0 END) AS bucket_{idx}"
            )
    bucket_sql = ",\n               ".join(bucket_cases)
    return f"""
        WITH tx_totals AS (
            SELECT t.hash AS tx_hash,
                   SUM(o.amount) AS total_amount,
                   b.time AS block_time
            FROM tx AS t
            JOIN out AS o ON o.tx_hash = t.hash
            JOIN block AS b ON t.block_hash = b.hash
            {MAIN_CHAIN_JOIN}
            GROUP BY t.hash
        )
        SELECT date(block_time, 'unixepoch') AS day,
               {bucket_sql}
        FROM tx_totals
        GROUP BY day
        ORDER BY day;
    """

def get_day_btc_amount(database="blk*.db", verbose=True):
    """Update btc_amounts.db with the daily output totals of every per-file database.

    Safe to interrupt and re-run at any point: each per-file database's daily
    totals are stored separately (table db_days) and replaced, never added, when
    that database is processed again; the progress record is written in the same
    transaction. A database is (re)processed when its number of main-chain blocks
    changed since last time, so new blocks, newly confirmed blocks and blocks that
    left the main chain are all picked up. The `days` view sums db_days per day.

    Args:
        database: Glob pattern of the per-file databases to traverse.
    """
    ensure_amount_db()

    chain = sqlite3.connect(f"file:{CHAIN_DB}?mode=ro&immutable=1", uri=True)
    main_blocks = dict(chain.execute("SELECT db_file, count(*) FROM main_chain GROUP BY db_file;"))
    chain.close()

    os.chmod(BTC_AMOUNT_DB, 0o666)
    out = sqlite3.connect(str(BTC_AMOUNT_DB))
    try:
        done = dict(out.execute("SELECT db_file, main_blocks FROM db_progress;"))

        for in_db in sorted(DATABASE_FOLDER.rglob(database)):
            blocks = main_blocks.get(in_db.name, 0)
            if done.get(in_db.name) == blocks:
                continue  # unchanged since it was last processed

            thermal_guard(verbose)
            if verbose:
                print(f"Handling {in_db} ({blocks} main-chain blocks)")

            conn = connect_readonly(in_db)
            rows = conn.execute(f"""
                SELECT date(b.time, 'unixepoch') AS day, SUM(o.amount)
                FROM out AS o JOIN tx AS t ON o.tx_hash = t.hash
                JOIN block AS b ON t.block_hash = b.hash
                {MAIN_CHAIN_JOIN}
                GROUP BY day;
            """, {"db_file": in_db.name}).fetchall()
            conn.close()

            # One transaction per database: its old rows out, new rows and the
            # progress record in. An interruption leaves either all or nothing.
            with out:
                out.execute("DELETE FROM db_days WHERE db_file = ?;", (in_db.name,))
                out.executemany(
                    "INSERT INTO db_days (db_file, date, amount) VALUES (?, ?, ?);",
                    [(in_db.name, day, amount) for day, amount in rows],
                )
                out.execute(
                    "INSERT OR REPLACE INTO db_progress (db_file, main_blocks) VALUES (?, ?);",
                    (in_db.name, blocks),
                )
    finally:
        out.close()
        os.chmod(BTC_AMOUNT_DB, 0o444)

def ensure_amount_db():
    """Create btc_amounts.db if it does not exist yet.

    db_days:     daily output totals (satoshi) per per-file database
    db_progress: main-chain block count of each database when it was processed
    days:        view with the daily totals in BTC, used by export_days_amount
    """
    if BTC_AMOUNT_DB.exists():
        conn = sqlite3.connect(f"file:{BTC_AMOUNT_DB}?mode=ro", uri=True)
        old = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'days';"
        ).fetchone()
        conn.close()
        if old:
            raise RuntimeError(
                f"{BTC_AMOUNT_DB} has the old format (a 'days' table). "
                "Delete it and run get_day_btc_amount() again to rebuild it."
            )
        return
    conn = sqlite3.connect(str(BTC_AMOUNT_DB))
    conn.executescript("""
        CREATE TABLE db_days (
            db_file TEXT NOT NULL,
            date TEXT NOT NULL,
            amount INTEGER NOT NULL,
            PRIMARY KEY (db_file, date)
        );
        CREATE TABLE db_progress (
            db_file TEXT PRIMARY KEY,
            main_blocks INTEGER NOT NULL
        );
        CREATE VIEW days AS
            SELECT date, SUM(amount) / 100000000.0 AS amount
            FROM db_days GROUP BY date ORDER BY date;
    """)
    conn.close()
    os.chmod(BTC_AMOUNT_DB, 0o444)

def round_datetime(date: datetime, interval: str, direction: str):
    """Rounds a datetime object to the nearest specified interval.

    Args:
        date: The datetime object to round.
        interval: The interval to round to ('hour', 'day', 'week', 'month', 'year').
        direction: Round up or down, increasing or decreasing the value.
    Returns:
        The rounded datetime object.
        Raises ValueError for invalid interval.
    """

    intervals = ['hour', 'day', 'week', 'month', 'year']
    if interval not in intervals:
        raise ValueError(f'Invalid interval. Expect one of {intervals}')
    directions = ['up', 'down']
    if direction not in directions:
        raise ValueError(f'Invalid direction. Expected one of {directions}')
    
    round_date_time = date.replace(minute=0, second=0, microsecond=0)  # Reset minutes, seconds, microseconds

    if interval == 'hour':
        if direction == directions[0]:
            round_date_time += timedelta(hours=1)
        else:
            round_date_time -= timedelta(hours=1)
    elif interval == 'day':
        round_date_time = round_date_time.replace(hour=0)
        if direction == directions[0]:
            round_date_time += timedelta(days=1)
        else:
            round_date_time -= timedelta(days=1)
    elif interval == 'week':
        round_date_time = round_date_time.replace(hour=0)
        # Python's week starts on Monday (0), so this logic is correct
        while round_date_time.weekday() != 0:
            if direction == directions[0]:
                round_date_time += timedelta(days=1)
            else:
                round_date_time -= timedelta(days=1)
    elif interval == 'month':
        round_date_time = round_date_time.replace(hour=0)
        if direction == directions[0]:
            round_date_time += timedelta(days=1)
            while round_date_time.day != 1:
                round_date_time += timedelta(days=1)
        else:
            round_date_time -= timedelta(days=1)
            while round_date_time.day != 1:
                round_date_time -= timedelta(days=1)
    elif interval == 'year':
        round_date_time = round_date_time.replace(month=1, day=1, hour=0)  # Set to Jan 1st
        if direction == directions[0]:
            round_date_time = round_date_time.replace(year=round_date_time.year + 1)
        else:
            round_date_time = round_date_time.replace(year=round_date_time.year -1)

    return round_date_time

# Start of the period containing b.time, in DATE_FORMAT, UTC (SQLite's
# 'unixepoch' is UTC). Weeks start on Monday.
_PERIOD_SQL = {
    'hour': "strftime('%d-%m-%Y %H:00:00', b.time, 'unixepoch')",
    'day': "strftime('%d-%m-%Y 00:00:00', b.time, 'unixepoch')",
    'week': "strftime('%d-%m-%Y 00:00:00', b.time, 'unixepoch', '-6 days', 'weekday 1')",
    'month': "strftime('01-%m-%Y 00:00:00', b.time, 'unixepoch')",
    'year': "strftime('01-01-%Y 00:00:00', b.time, 'unixepoch')",
}

def get_btc_amount(database: str, start: str, end: str, interval='day'):

    # Validate parameters
    intervals = ['hour', 'day', 'week', 'month', 'year']
    if interval not in intervals:
        raise ValueError(f'Invalid interval. Expect one of {intervals}')

    try:
        # To Unix Epoch time
        start_date = int(parse_utc(start).timestamp())
        end_date = int(parse_utc(end).timestamp())

    except ValueError as e:
        raise ValueError(f"Date format error: {e}")

    # Each output goes to the period that contains its block's timestamp, computed
    # by SQLite in UTC. Unlike a running "end of the current day" over the rows,
    # this does not depend on row order: blocks are stored in download order and
    # block timestamps are not monotonic.
    conn = connect_readonly(database)
    command = f"""
        SELECT {_PERIOD_SQL[interval]} AS period, SUM(o.amount)
        FROM out AS o JOIN tx AS t ON o.tx_hash = t.hash
        JOIN block AS b ON t.block_hash = b.hash
        {MAIN_CHAIN_JOIN}
        WHERE b.time >= :start AND b.time <= :end
        GROUP BY period;
    """
    rows = conn.execute(
        command, {"db_file": Path(database).name, "start": start_date, "end": end_date}
    ).fetchall()
    conn.close()

    # Keys: start of each period in DATE_FORMAT (UTC); values in BTC.
    return {period: total / 100000000 for period, total in rows}

def parse_dat_file(dat_file="blk*.dat", verbose=True):
    """
    This function is parsing the dat files and stores the data in the databases.
    """

    # Get the dat files to read
    dat_files = sorted(DAT_FILES.rglob(dat_file))

    # Parse the configuration file to get the last dat file parsed
    config = load_config()
    last_path = Path(config['last_dat_file_parsed'])

    # Start parsing from the latest dat file stored in the config file
    if last_path in dat_files:
        index = dat_files.index(last_path)
        dat_files = dat_files[index:]
        last_parsed_file = config['last_dat_file_parsed']

    # Start parsing the dat files
    for file in dat_files:
        thermal_guard(verbose)
        if verbose:
            now = datetime.now()
            print(f"{now} parsing {file}")

        # Set the database to store the data
        database = DATABASE_FOLDER / f"{file.stem}.db"

        if not database.exists():
            conn = sqlite3.connect(str(database))
            cursor = conn.cursor()

            command = """
                CREATE TABLE IF NOT EXISTS block (
                    hash BLOB PRIMARY KEY ON CONFLICT IGNORE,
                    prev_hash BLOB,
                    time INTEGER
                );
            """
            cursor.execute(command)

            command = """
                CREATE TABLE IF NOT EXISTS tx (
                    block_hash BLOB REFERENCES block(hash),
                    hash BLOB PRIMARY KEY ON CONFLICT IGNORE
                );
            """
            cursor.execute(command)

            command = """
                CREATE TABLE IF NOT EXISTS out (
                    tx_hash BLOB REFERENCES tx(hash),
                    count INTEGER,
                    amount INTEGER,
                    pub_key BLOB,
                    UNIQUE(tx_hash, count) ON CONFLICT IGNORE
                );
            """
            cursor.execute(command)

            conn.commit()
            conn.close()

        crawl_process = subprocess.run(
            [str(CRAWL_BIN), str(file)],
            capture_output=True,
            text=True,
        )
        if crawl_process.returncode != 0:
            # Do not load partial output: stop here, the next run resumes at this file.
            raise RuntimeError(
                f"crawl failed on {file} (exit {crawl_process.returncode}):\n{crawl_process.stderr}"
            )

        sql_commands = crawl_process.stdout

        command = "BEGIN TRANSACTION;\n"
        command += "PRAGMA foreign_keys = ON;\n"
        command += sql_commands + "\n" #Add the sql commands from the crawl process.
        command += "COMMIT;"

        os.chmod(database, 0o666)
        subprocess.run(
            ["sqlite3", str(database)],
            input=command.encode(),
            check=True,
        )
        os.chmod(database, 0o444)

        add_blocks_to_chain(database)

        config['last_dat_file_parsed'] = str(file)
        save_config(config)

def add_blocks_to_chain(database: Path):
    """Copy a per-file database's blocks into chain.db.

    A block written to two blk*.dat files keeps the first file it was seen in
    (PRIMARY KEY ON CONFLICT IGNORE), which becomes its canonical database.
    """
    chain = sqlite3.connect(str(CHAIN_DB))
    chain.execute("""
        CREATE TABLE IF NOT EXISTS block (
            hash BLOB PRIMARY KEY ON CONFLICT IGNORE,
            prev_hash BLOB NOT NULL,
            time INTEGER,
            db_file TEXT NOT NULL
        );
    """)
    chain.execute("CREATE INDEX IF NOT EXISTS block_prev ON block(prev_hash);")
    chain.execute("ATTACH DATABASE ? AS f;", (str(database),))
    chain.execute(
        "INSERT INTO block (hash, prev_hash, time, db_file) "
        "SELECT hash, prev_hash, time, ? FROM f.block;",
        (database.name,),
    )
    chain.commit()
    chain.execute("DETACH DATABASE f;")
    chain.close()

def build_main_chain(min_confirmations=MIN_CONFIRMATIONS, verbose=True):
    """Rebuild chain.main_chain (height, hash, db_file) from the prev_hash links.

    Heights are computed walking forward from genesis (prev_hash = 32 zero bytes);
    the main chain is the path walked back from the highest block. Blocks not on
    that path are stale (orphan) blocks. The newest `min_confirmations` blocks are
    left out until they are settled. Blocks after a gap (a parent not loaded yet)
    get no height and join the main chain once the gap is filled.
    """
    conn = sqlite3.connect(str(CHAIN_DB))
    conn.executescript(f"""
        PRAGMA temp_store = MEMORY;
        BEGIN;
        DROP TABLE IF EXISTS main_chain;
        CREATE TEMP TABLE heights AS
        WITH RECURSIVE h(hash, height) AS (
            SELECT hash, 0 FROM block WHERE prev_hash = zeroblob(32)
            UNION ALL
            SELECT b.hash, h.height + 1 FROM block AS b JOIN h ON b.prev_hash = h.hash
        ) SELECT * FROM h;
        CREATE TABLE main_chain AS
        WITH RECURSIVE m(hash, height) AS (
            SELECT * FROM (SELECT hash, height FROM heights ORDER BY height DESC, hash LIMIT 1)
            UNION ALL
            SELECT b.prev_hash, m.height - 1 FROM m JOIN block AS b ON b.hash = m.hash
            WHERE m.height > 0
        )
        SELECT m.height, m.hash, b.db_file FROM m JOIN block AS b ON b.hash = m.hash
        WHERE m.height <= (SELECT max(height) FROM heights) - {int(min_confirmations)};
        CREATE UNIQUE INDEX main_chain_hash ON main_chain(hash);
        CREATE INDEX main_chain_file ON main_chain(db_file);
        COMMIT;
    """)
    if verbose:
        blocks, = conn.execute("SELECT count(*) FROM block;").fetchone()
        main, top = conn.execute("SELECT count(*), max(height) FROM main_chain;").fetchone()
        tip, = conn.execute("SELECT max(height) FROM heights;").fetchone()
        print(f"Main chain: {main} blocks (height 0..{top}, tip {tip}); "
              f"{blocks} blocks stored; {blocks - main} not counted "
              f"(stale, duplicates' extra copies are not stored, or < {min_confirmations} confirmations)")
    conn.close()

def export_data_to_json(db_path, output_path, query):
    """
    Exports data from an SQLite database to a JSON file based on a provided query.

    Args:
        db_path (str): The path to the SQLite database file.
        output_path (str): The path to the JSON output file.
        query (str): The SQL query to execute. This query should return a single
                     row with a single column containing a JSON string.
                     Examples:
                       "select json_group_object(date, amount) as amounts from days;"
                       "select json_group_object(timestamp, close) from data;"
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        cursor.execute(query)
        result = cursor.fetchone()[0]  # Get the JSON string
        conn.close()

        with open(output_path, "w") as outfile:
            json.dump(json.loads(result), outfile, indent=4)  # Convert to Python object, then back to JSON

        print(f"SQLite query executed successfully. Output written to {output_path}")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except FileNotFoundError:
        print("Error: Database not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def export_days_amount(db_path, output_path):
    query = "select json_group_object(date, amount) as amounts from days;"
    export_data_to_json(db_path, output_path, query)

def export_price_close(db_path, output_path):
    query = "select json_group_object(timestamp, close) from data order by timestamp;"
    export_data_to_json(db_path, output_path, query)

def update_daily_price(output_path, symbol="BTCUSDT"):
    """
    Updates daily price data from Binance, rewriting the latest candle and filling gaps.
    """
    output_file = Path(output_path)
    existing = []
    if output_file.exists():
        try:
            existing = json.loads(output_file.read_text())
        except json.JSONDecodeError:
            existing = []

    last_timestamp = None
    if existing:
        last_timestamp = existing[-1].get("timestamp")

    if last_timestamp:
        start_date = datetime.strptime(last_timestamp, "%Y-%m-%d")
    else:
        start_date = binance.EARLIEST_BTCUSDT_DATE

    new_candles = binance.fetch_daily_candles(symbol=symbol, start_date=start_date)
    if not new_candles:
        print("No Binance candles returned; daily price not updated.")
        return

    first_new_timestamp = new_candles[0]["timestamp"]
    if existing:
        existing = [row for row in existing if row.get("timestamp") < first_new_timestamp]

    updated = existing + new_candles
    output_file.write_text(json.dumps(updated, indent=4))
    print(f"Daily price updated at {output_path}")

def export_daily_tx_sizes(output_path, database_pattern="blk*.db"):
    """
    Exports daily transaction count distributions across predefined BTC amount buckets.
    """

    header = ["date"] + [bucket[0] for bucket in TX_SIZE_BUCKETS]

    # Load existing data, keeping every fully processed day and removing the last one.
    existing_data = {}
    last_recorded_day = None
    last_recorded_counts = None
    output_file = Path(output_path)
    if output_file.exists():
        stored = json.loads(output_file.read_text())
        if stored and len(stored) > 1:
            for row in stored[1:]:
                day = row[0]
                counts = row[1:]
                existing_data[day] = counts
            last_recorded_day = stored[-1][0]
            last_recorded_counts = existing_data.pop(last_recorded_day, None)
            if last_recorded_counts is not None:
                last_recorded_counts = list(last_recorded_counts)
    
    # Prepare the accumulator with the already finalized days.
    daily_counts = {day: list(counts) for day, counts in existing_data.items()}
    config = load_config()

    dbs = sorted(DATABASE_FOLDER.rglob(database_pattern))
    start_db = Path(config.get("last_tx_size_db_parsed", "")) if config.get("last_tx_size_db_parsed") else None
    if start_db and start_db in dbs:
        dbs = dbs[dbs.index(start_db):]

    latest_day_seen = last_recorded_day
    seen_existing_last_day = last_recorded_day is None
    updated_db_pointer = None

    for db in dbs:
        print(f"Query {db} for tx sizes.")
        conn = connect_readonly(db)
        try:
            rows = conn.execute(_build_tx_size_query(), {"db_file": db.name}).fetchall()
        finally:
            conn.close()
        for row in rows:
            day = row[0]
            bucket_values = row[1:]

            if last_recorded_day and day < last_recorded_day:
                continue

            if last_recorded_day and day == last_recorded_day:
                seen_existing_last_day = True

            day_totals = daily_counts.setdefault(day, [0] * len(TX_SIZE_BUCKETS))
            for idx, value in enumerate(bucket_values):
                day_totals[idx] += value

            if latest_day_seen is None or day > latest_day_seen:
                latest_day_seen = day
                updated_db_pointer = str(db)

    if last_recorded_day and not seen_existing_last_day and last_recorded_counts:
        # The previous day was not rebuilt (likely no new data); restore it.
        daily_counts[last_recorded_day] = last_recorded_counts
        print(f"Warning: {last_recorded_day} was not reconstructed; restored previous values.")

    data = [header] + [[day] + counts for day, counts in sorted(daily_counts.items())]
    output_file.write_text(json.dumps(data, indent=4))

    if updated_db_pointer:
        config["last_tx_size_db_parsed"] = updated_db_pointer
        save_config(config)

    print(f"Daily transaction sizes exported to {output_path}")

def prepare_data():
    parse_dat_file()
    build_main_chain()
    get_day_btc_amount()

def export_data():
    """Export crawler outputs into the local statistics data directory only."""
    STATISTICS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    daily_amounts_path = STATISTICS_DATA_DIR / "daily_amounts.json"
    export_days_amount(BTC_AMOUNT_DB, daily_amounts_path)

    daily_tx_size_output_path = STATISTICS_DATA_DIR / "daily_tx_size.json"
    export_daily_tx_sizes(daily_tx_size_output_path)

    daily_price_path = STATISTICS_DATA_DIR / "daily_price.json"
    update_daily_price(daily_price_path)

if __name__ == "__main__":
    prepare_data()
    export_data()
