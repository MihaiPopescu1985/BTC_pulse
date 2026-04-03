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
DEFAULT_TARGETS_CSV_PATH = OUT_DIR / "targets.csv"
DEFAULT_STATES_CSV_PATH = OUT_DIR / "states.csv"
DEFAULT_STATE_OUTCOMES_CSV_PATH = OUT_DIR / "state_outcomes.csv"
DEFAULT_CALIBRATION_CSV_PATH = OUT_DIR / "calibration.csv"
DEFAULT_DECISION_ANALYSIS_CSV_PATH = OUT_DIR / "decision_analysis.csv"
DEFAULT_DECISION_VALIDATION_CSV_PATH = OUT_DIR / "decision_validation.csv"
DEFAULT_POLICY_BACKTEST_CSV_PATH = OUT_DIR / "policy_backtest.csv"
DEFAULT_DECISION_ANALYSIS_WALKFORWARD_CSV_PATH = OUT_DIR / "decision_analysis_walkforward.csv"
DEFAULT_POLICY_BACKTEST_WALKFORWARD_CSV_PATH = OUT_DIR / "policy_backtest_walkforward.csv"
DEFAULT_POLICY_REFINEMENT_WALKFORWARD_CSV_PATH = OUT_DIR / "policy_refinement_walkforward.csv"
DEFAULT_POLICY_STRESS_WALKFORWARD_CSV_PATH = OUT_DIR / "policy_stress_walkforward.csv"
DEFAULT_HMM_PACK_PATH = MODELS_DIR / "hmm_pack.joblib"
DEFAULT_HAZARD_PACK_PATH = MODELS_DIR / "hazard_pack.joblib"
