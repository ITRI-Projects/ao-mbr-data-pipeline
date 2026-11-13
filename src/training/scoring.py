"""Regression metrics and conversion from model outputs to forecasts."""

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .settings import PREDICTION_MODES


def metrics(y, prediction):
    return {"n": len(y), "MAE": mean_absolute_error(y, prediction),
            "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
            "R2": float(r2_score(y, prediction)) if len(y) > 1 and np.ptp(y) > 0 else np.nan,
            "constant_target": bool(np.ptp(y) == 0)}

def prediction_offset(arrays, target, mode):
    """Return the level added to raw model output to obtain absolute forecasts."""
    if mode not in PREDICTION_MODES:
        raise ValueError(f"Unknown prediction mode: {mode}")
    if mode == "absolute":
        return np.zeros(len(arrays["y"]), dtype=float)
    names = [str(name) for name in arrays["feature_names"]]
    if target not in names:
        raise ValueError(f"Delta prediction requires target history for {target}.")
    index = names.index(target)
    offset = (arrays["X"][:, -1, index].astype(float) * arrays["scale"][index]
              + arrays["center"][index])
    if not np.isfinite(offset).all():
        raise ValueError(f"Delta prediction has non-finite origin values for {target}.")
    return offset
