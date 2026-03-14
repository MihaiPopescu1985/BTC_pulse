import json
from pathlib import Path
import pandas as pd

def load_daily_price_json(path: str) -> pd.DataFrame:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    # Caz 1: dict { "YYYY-MM-DD": price, ... }
    if isinstance(raw, dict):
        # poate fi direct date->price, sau nested
        # încercăm să găsim un mapping de date
        if all(isinstance(k, str) for k in raw.keys()):
            # dacă valorile sunt numere
            if all(isinstance(v, (int, float)) for v in raw.values()):
                df = pd.DataFrame({"date": list(raw.keys()), "close": list(raw.values())})
            else:
                # dacă e nested, caută un key evident
                for key in ["prices", "data", "close", "series", "daily"]:
                    if key in raw and isinstance(raw[key], (list, dict)):
                        raw = raw[key]
                        return load_daily_price_json_like(raw)
                raise ValueError("Dict JSON nerecunoscut. Trimite un eșantion din fișier.")
        else:
            raise ValueError("Dict JSON cu chei non-string. Trimite un eșantion.")
        return finalize_df(df)

    # Caz 2: listă de înregistrări
    if isinstance(raw, list):
        return load_daily_price_json_like(raw)

    raise ValueError(f"Tip JSON nerecunoscut: {type(raw)}")


def load_daily_price_json_like(obj) -> pd.DataFrame:
    # obj poate fi list sau dict (ex: {"data":[...]})
    if isinstance(obj, dict):
        for key in ["prices", "data", "close", "series", "daily"]:
            if key in obj:
                return load_daily_price_json_like(obj[key])
        raise ValueError("Dict nested nerecunoscut. Trimite un eșantion.")

    if not isinstance(obj, list) or len(obj) == 0:
        raise ValueError("Lista e goală sau format invalid.")

    first = obj[0]

    # Caz 2.1: listă de perechi [timestamp, price]
    if isinstance(first, list) and len(first) >= 2 and isinstance(first[1], (int, float)):
        df = pd.DataFrame(obj, columns=["date", "close"] + [f"extra_{i}" for i in range(len(first)-2)])

    # Caz 2.2: listă de dict-uri {date:..., close/price:...}
    elif isinstance(first, dict):
        # detectează numele coloanelor
        # date-like keys
        date_keys = ["date", "time", "timestamp", "t", "day"]
        price_keys = ["close", "price", "p", "value", "c"]

        dk = next((k for k in date_keys if k in first), None)
        pk = next((k for k in price_keys if k in first), None)

        if dk is None or pk is None:
            raise ValueError(f"Nu găsesc chei date/price în dict. Chei disponibile: {list(first.keys())}")

        df = pd.DataFrame({
            "date": [row.get(dk) for row in obj],
            "close": [row.get(pk) for row in obj],
        })

    else:
        raise ValueError(f"Elemente listă nerecunoscute: {type(first)}")

    return finalize_df(df)


def finalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Parse date robust (acceptă: YYYY-MM-DD, epoch sec/ms, ISO)
    df = df.copy()

    # dacă date e numeric (epoch)
    if pd.api.types.is_numeric_dtype(df["date"]):
        # heuristica: > 1e12 -> ms
        s = df["date"].astype("int64")
        unit = "ms" if s.median() > 10**12 else "s"
        df["date"] = pd.to_datetime(df["date"], unit=unit, utc=True).dt.date
    else:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.date

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")

    # index pe date pentru rolling
    df = df.set_index(pd.to_datetime(df["date"])).drop(columns=["date"])
    df.index.name = "date"
    return df


if __name__ == "__main__":
    df = load_daily_price_json("daily_price.json")
    print(df.head(10))
    print(df.tail(10))
    print("Rows:", len(df), "Start:", df.index.min().date(), "End:", df.index.max().date())
