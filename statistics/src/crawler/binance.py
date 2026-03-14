import json
from datetime import datetime

import requests

EARLIEST_BTCUSDT_DATE = datetime(2017, 8, 17)
BINANCE_DATE_FORMAT = "%Y-%m-%d"


def fetch_daily_candles(symbol="BTCUSDT", start_date=None, end_date=None):
    """
    Retrieves daily OHLCV candles from Binance REST API.

    Args:
        symbol (str): The symbol to query (e.g., "BTCUSDT").
        start_date (datetime|str): Start date (inclusive). "YYYY-MM-DD" strings supported.
        end_date (datetime|str|None): End date (inclusive). Defaults to now (UTC).

    Returns:
        list: A list of dictionaries with timestamp, open, high, low, close, volume.
              Returns None on error.
    """
    if start_date is None:
        start_date = EARLIEST_BTCUSDT_DATE
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, BINANCE_DATE_FORMAT)
    if end_date is None:
        end_date = datetime.utcnow()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, BINANCE_DATE_FORMAT)

    base_url = "https://api.binance.com/api/v3/klines"
    interval = "1d"
    limit = 1000
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    rows = []

    while start_ms <= end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Binance API: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

        if not data:
            break

        for kline in data:
            timestamp = datetime.utcfromtimestamp(kline[0] / 1000)
            rows.append({
                "timestamp": timestamp.strftime(BINANCE_DATE_FORMAT),
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5]),
            })

        last_open_time_ms = data[-1][0]
        if last_open_time_ms >= end_ms or len(data) < limit:
            break
        start_ms = last_open_time_ms + 1

    return rows
