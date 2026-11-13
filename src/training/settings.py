"""Forecast windows, sequence defaults, and supported algorithms."""

DEFAULT_TRAIN_START = "2026-04-04"
DEFAULT_TRAIN_END = "2026-04-18"
DEFAULT_TEST_START = "2026-04-21"
DEFAULT_HORIZON_MINUTES = 10
DEFAULT_STEP_MINUTES = 10
DEFAULT_SEQUENCE_STEPS = 7

PREDICTION_MODES = ("absolute", "delta")
DEFAULT_PREDICTION_MODE = "absolute"

ALGORITHMS = {"ridge": "Ridge", "random_forest": "Random Forest", "xgboost": "XGBoost", "lstm": "LSTM"}
ALGORITHM_ORDER = tuple(ALGORITHMS.values())
