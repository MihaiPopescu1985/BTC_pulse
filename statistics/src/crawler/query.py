import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import json
import subprocess
import os
from shutil import copyfile

import binance

GENESIS_DATE = "03-01-2009 20:15:05"
DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
DAT_FILES = Path("/media/mihai/BTC/bitcoin-data/blocks")
DATABASE_FOLDER = Path("/media/mihai/BTC/db")
BTC_AMOUNT_DB = DATABASE_FOLDER / "btc_amounts.db"
BTC_QUERY_CONFIG = Path("/media/mihai/BTC/bitcoin-data/.btc_query_config")
DEFAULT_DAY_PARSE_CONFIG = {
            "last_day_amount_db_parse": "/media/mihai/BTC/db/blk00000.db",
            "last_day_amount_datetime_parse": 1231006505,
            "last_dat_file_parsed": "/media/mihai/BTC/bitcoin-data/blocks/blk04753.dat"
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
            GROUP BY t.hash
        )
        SELECT date(block_time, 'unixepoch') AS day,
               {bucket_sql}
        FROM tx_totals
        GROUP BY day
        ORDER BY day;
    """

def get_day_btc_amount(database="blk*.db", verbose=True):
    """Update the btc_amount database with data collected from the other databases.

    Args:
        database: The sqlite database to traverse.
    """

    dbs = sorted(DATABASE_FOLDER.rglob(database))
    config = json.loads(BTC_QUERY_CONFIG.read_text())

    last_path = Path(config['last_day_amount_db_parse'])
    if last_path in dbs:
        index = dbs.index(last_path)
        dbs = dbs[index:]
        last_time = config['last_day_amount_datetime_parse']

    for in_db in dbs:
        if verbose:
            print(f"Handling {in_db}")

        conn = sqlite3.connect(in_db)
        cursor = conn.cursor()

        if last_time:
            min_time = int(last_time)
            last_time = 0
        else:
            min_time = cursor.execute("SELECT min(time) FROM block;").fetchone()[0]
        max_time = cursor.execute("SELECT max(time) FROM block;").fetchone()[0]
        conn.close()

        min_date = datetime.fromtimestamp(min_time)
        max_date = datetime.fromtimestamp(max_time)

        amounts = get_btc_amount(
            in_db,
            datetime.strftime(min_date, DATE_FORMAT),
            datetime.strftime(max_date, DATE_FORMAT),
            'day'
        )
        os.chmod(BTC_AMOUNT_DB, 0o666)
        conn = sqlite3.connect(str(BTC_AMOUNT_DB))
        cursor = conn.cursor()

        command = """
            INSERT INTO days (date, amount) 
            VALUES (?, ?) 
            ON CONFLICT(date) 
            DO UPDATE SET amount = amount + ?;
        """

        for date, amount in amounts.items():
            config["last_day_amount_db_parse"] = str(in_db)
            config["last_day_amount_datetime_parse"] = max_time+1

            date = datetime.strptime(date, DATE_FORMAT).date()

            if verbose:
                print(f"Upserting {date}, {amount} into days.")
            cursor.execute(command, (date, amount, amount))

        conn.commit()
        conn.close()

        os.chmod(BTC_AMOUNT_DB, 0o444)
        os.chmod(BTC_QUERY_CONFIG, 0o666)
        BTC_QUERY_CONFIG.write_text(json.dumps(config))
        os.chmod(BTC_QUERY_CONFIG, 0o444)

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

def get_btc_amount(database: str, start: str, end: str, interval='day'):

    # Validate parameters
    intervals = ['hour', 'day', 'week', 'month', 'year']
    if interval not in intervals:
        raise ValueError(f'Invalid interval. Expect one of {intervals}')

    try:
        # To Unix Epoch time
        start_date = int(datetime.strptime(start, DATE_FORMAT).timestamp())
        end_date = int(datetime.strptime(end, DATE_FORMAT).timestamp())

    except ValueError as e:
        raise ValueError(f"Date format error: {e}")

    # Query the database
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    command = """
        SELECT b.time, o.amount
        FROM out AS o JOIN tx AS t ON o.tx_hash = t.hash
        JOIN block AS b ON t.block_hash = b.hash
        WHERE b.time >= ? AND b.time <= ?;
    """
    cursor.execute(command, (start_date, end_date))

    out = {}
    amount_sum = 0
    high_end = round_datetime(datetime.strptime(start, DATE_FORMAT), interval, 'up')
    high_end = int(high_end.timestamp())

    for row in cursor:
        current_datetime = int(row[0])

        if current_datetime < high_end:
            amount_sum += row[1]
        else:
            key = round_datetime(datetime.fromtimestamp(high_end), interval, 'down')
            key = key.strftime(DATE_FORMAT)
            out[key] = amount_sum / 100000000
            amount_sum = row[1]

            while high_end < current_datetime:
                high_end = round_datetime(datetime.fromtimestamp(high_end), interval, 'up')
                high_end = high_end.timestamp()

    key = round_datetime(datetime.fromtimestamp(high_end), interval, 'down')
    key = key.strftime(DATE_FORMAT)
    out[key] = amount_sum / 100000000

    conn.close()
    return out

def parse_dat_file(dat_file="blk*.dat", verbose=True):
    """
    This function is parsing the dat files and stores the data in the databases.
    """

    # Get the dat files to read
    dat_files = sorted(DAT_FILES.rglob(dat_file))

    # Parse the configuration file to get the last dat file parsed
    config = json.loads(BTC_QUERY_CONFIG.read_text())
    last_path = Path(config['last_dat_file_parsed'])

    # Start parsing from the latest dat file stored in the config file
    if last_path in dat_files:
        index = dat_files.index(last_path)
        dat_files = dat_files[index:]
        last_parsed_file = config['last_dat_file_parsed']

    # Start parsing the dat files
    for file in dat_files:
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

        try:
            crawl_process = subprocess.run(
                ["/media/mihai/BTC/db/crawl", str(file)],
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(e)

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

        config['last_dat_file_parsed'] = str(file)
        os.chmod(BTC_QUERY_CONFIG, 0o666)
        BTC_QUERY_CONFIG.write_text(json.dumps(config))
        os.chmod(BTC_QUERY_CONFIG, 0o444)

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
        conn = sqlite3.connect(db_path)
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

def get_block_duplicates():
    # Get the databases sorted
    databases = sorted(DATABASE_FOLDER.rglob("blk*.db")) 
    hashes = set()

    # Loop through the databases
    for db in databases:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Get the the times from the current database
        db_hashes = set()
        result = cursor.execute("SELECT hex(hash) FROM block;").fetchall()
        db_hashes.update(result)

        # Check if time exists in the set
        intersection = hashes.intersection(db_hashes)
        if len(intersection) > 0:
            print(f"{db} already contains {intersection}")
            exit(1)
        hashes.update(result)

        # Close the database connection
        conn.close()

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
    config = json.loads(BTC_QUERY_CONFIG.read_text())

    dbs = sorted(DATABASE_FOLDER.rglob(database_pattern))
    start_db = Path(config.get("last_tx_size_db_parsed", "")) if config.get("last_tx_size_db_parsed") else None
    if start_db and start_db in dbs:
        dbs = dbs[dbs.index(start_db):]

    latest_day_seen = last_recorded_day
    seen_existing_last_day = last_recorded_day is None
    updated_db_pointer = None

    for db in dbs:
        print(f"Query {db} for tx sizes.")
        with sqlite3.connect(db) as conn:
            for row in conn.execute(_build_tx_size_query()):
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
        os.chmod(BTC_QUERY_CONFIG, 0o666)
        BTC_QUERY_CONFIG.write_text(json.dumps(config))
        os.chmod(BTC_QUERY_CONFIG, 0o444)

    print(f"Daily transaction sizes exported to {output_path}")

def prepare_data():
    parse_dat_file()
    get_block_duplicates()
    get_day_btc_amount()

# TODO: this must be refactored. Lots of hardcoded paths.
# Consider having a settings file with all the paths included.
# Consider using the BTC_QUERY_CONFIG file for all the settings.
def export_data():
    # Export daily amounts
    data_location = Path("/home/mihai/Documents/BTC_pulse/frontend/_data")
    daily_amounts_path = data_location / "daily_amounts.json"
    export_days_amount(BTC_AMOUNT_DB, daily_amounts_path)

    # Export daily transaction sizes
    daily_tx_size_output_path = data_location / "daily_tx_size.json"
    export_daily_tx_sizes(daily_tx_size_output_path)

    # Update daily prices
    daily_price_path = data_location / "daily_price.json"
    update_daily_price(daily_price_path)

    # Update statistics
    statistics_path = Path("/home/mihai/Documents/BTC_pulse/statistics")
    copyfile(daily_price_path, statistics_path / "data/daily_price.json")
    copyfile(daily_amounts_path, statistics_path / "data/daily_amounts.json")
    copyfile(daily_tx_size_output_path, statistics_path / "data/daily_tx_size.json")
    os.chdir(statistics_path)
    subprocess.run(["./generate_statistics.sh"])
    features_file_path = statistics_path / "out/btc/features.json"
    onchain_features_file_path = statistics_path / "out/btc/onchain_features.json"
    copyfile(features_file_path, data_location / "features.json")
    copyfile(onchain_features_file_path, data_location / "onchain_features.json")

def publish_changes():
    # Commit and push the changes
    os.chdir('/home/mihai/Documents/BTC_pulse/frontend')

    subprocess.run(["git", "add", "_data/*"])
    subprocess.run(["git", "commit", "-m", "Automated commit"])
    subprocess.run(["git", "push", "origin", "main"])

if __name__ == "__main__":
    prepare_data()
    export_data()
    publish_changes()
