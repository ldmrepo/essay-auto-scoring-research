"""M6 ensemble: stack M4 + M5 predictions via Ridge meta-learner.

Reads predictions as a dict[model_id, np.ndarray] and fits a small linear
meta-learner (no intercept, non-negative-leaning via L2 regularisation).
Returns final predictions + per-model contribution weights for reporting.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


def train_ensemble(
    predictions: dict[str, np.ndarray],
    y_true: np.ndarray,
    seed: int = 42,
    alpha: float = 1.0,
) -> dict[str, Any]:
    """Fit Ridge meta-learner on stacked predictions.

    Returns: predictions (ndarray), weights (per model_id), metrics (mae, rmse).
    """
    model_ids = sorted(predictions.keys())
    X = np.column_stack([predictions[m] for m in model_ids])
    y = np.asarray(y_true, dtype=float)

    meta = Ridge(alpha=alpha, fit_intercept=True, random_state=seed)
    meta.fit(X, y)
    y_pred = meta.predict(X)

    weights = {m: float(c) for m, c in zip(model_ids, meta.coef_)}
    metrics = {
        "mae": float(mean_absolute_error(y, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y, y_pred))),
        "intercept": float(meta.intercept_),
    }
    return {"predictions": y_pred, "weights": weights, "metrics": metrics}
