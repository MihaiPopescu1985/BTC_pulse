from __future__ import annotations

from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent
STATISTICS_DIR = SRC_DIR.parent
DATA_DIR = STATISTICS_DIR / "data"
OUT_DIR = STATISTICS_DIR / "out"
MODELS_DIR = OUT_DIR / "models"

DEFAULT_PRICE_JSON_PATH = DATA_DIR / "daily_price.json"
DEFAULT_AMOUNTS_JSON_PATH = DATA_DIR / "daily_amounts.json"
DEFAULT_TX_SIZE_JSON_PATH = DATA_DIR / "daily_tx_size.json"

DEFAULT_FEATURES_CSV_PATH = OUT_DIR / "features.csv"
DEFAULT_ONCHAIN_FEATURES_CSV_PATH = OUT_DIR / "onchain_features.csv"
DEFAULT_HMM_PACK_PATH = MODELS_DIR / "hmm_pack.joblib"
DEFAULT_HAZARD_PACK_PATH = MODELS_DIR / "hazard_pack.joblib"
