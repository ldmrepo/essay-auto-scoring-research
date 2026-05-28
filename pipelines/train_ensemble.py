"""M6 ensemble: out-of-fold (OOF) Ridge stacking of base model predictions.

Prior implementation fit and predicted on the same (X, y), producing in-sample
metrics that overstate ensemble valid performance (external review High #4).
This module now performs proper OOF stacking:

  For each outer fold k:
    train meta on base predictions of folds != k
    predict on base predictions of fold k → fold k OOF ensemble prediction

OOF predictions are concatenated across folds and used for honest valid metrics.
A final meta-learner is also fit on all OOF base predictions for downstream use.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


def _stack_base_predictions(
    fold_predictions: dict[str, list[dict[str, Any]]], folds: list[int]
) -> tuple[np.ndarray, np.ndarray, dict[int, slice]]:
    """Align per-model fold predictions into a single (N, M) base matrix + y vector.

    Returns X (rows ordered fold0 then fold1...), y (matching order), and
    a {fold_id: slice} mapping into X/y for fold-wise OOF splitting.
    """
    model_ids = sorted(fold_predictions.keys())
    per_fold_lookup: dict[str, dict[int, dict[str, Any]]] = {
        m: {entry["fold"]: entry for entry in fold_predictions[m]} for m in model_ids
    }

    blocks: list[np.ndarray] = []
    y_blocks: list[np.ndarray] = []
    fold_slices: dict[int, slice] = {}
    offset = 0
    for fold in folds:
        entries = [per_fold_lookup[m].get(fold) for m in model_ids]
        if any(e is None for e in entries):
            missing = [m for m, e in zip(model_ids, entries) if e is None]
            raise ValueError(f"fold {fold} missing base predictions for models: {missing}")
        y_fold = np.asarray(entries[0]["y_true"], dtype=float)
        for m, entry in zip(model_ids[1:], entries[1:]):
            other_y = np.asarray(entry["y_true"], dtype=float)
            if other_y.shape != y_fold.shape or not np.allclose(other_y, y_fold):
                raise ValueError(
                    f"fold {fold} y_true mismatch between {model_ids[0]} and {m}"
                )
        X_fold = np.column_stack(
            [np.asarray(entry["y_pred"], dtype=float) for entry in entries]
        )
        if X_fold.shape[0] != y_fold.shape[0]:
            raise ValueError(f"fold {fold} y_true/y_pred length mismatch")
        blocks.append(X_fold)
        y_blocks.append(y_fold)
        n = X_fold.shape[0]
        fold_slices[fold] = slice(offset, offset + n)
        offset += n

    X = np.vstack(blocks) if blocks else np.zeros((0, len(model_ids)), dtype=float)
    y = np.concatenate(y_blocks) if y_blocks else np.zeros(0, dtype=float)
    return X, y, fold_slices


def train_ensemble(
    fold_predictions: dict[str, list[dict[str, Any]]],
    seed: int = 42,
    alpha: float = 1.0,
) -> dict[str, Any]:
    """Out-of-fold Ridge stacking of base model predictions.

    Args:
        fold_predictions: {model_id: [{"fold": int, "y_true": ndarray, "y_pred": ndarray}, ...]}.
            All models must report the same set of folds and matching y_true per fold.
        seed: random seed for Ridge solver (deterministic for this estimator).
        alpha: L2 regularisation strength for the meta-learner.

    Returns:
        oof_predictions: ndarray of OOF ensemble predictions (concatenated by fold order).
        oof_y_true: ndarray of OOF targets matching oof_predictions order.
        oof_metrics: {mae, rmse} computed honestly from OOF.
        per_fold_weights: {fold: {model_id: coef}} weights learned on folds != k.
        final_weights: {model_id: coef} from meta-learner fit on all OOF base predictions.
        final_intercept: float.
        folds: sorted list of fold ids used.
        model_ids: sorted base model ids.
    """
    model_ids = sorted(fold_predictions.keys())
    if not model_ids:
        raise ValueError("fold_predictions must contain at least one base model")
    folds = sorted({entry["fold"] for entries in fold_predictions.values() for entry in entries})
    if not folds:
        raise ValueError("no folds found in fold_predictions")
    if len(folds) < 2:
        raise ValueError(
            f"OOF stacking requires >=2 folds; got {len(folds)}. "
            "With 1 fold the held-out fold has no training data."
        )

    X, y, fold_slices = _stack_base_predictions(fold_predictions, folds)

    oof_predictions = np.empty_like(y, dtype=float)
    per_fold_weights: dict[int, dict[str, float]] = {}
    for fold in folds:
        valid_slice = fold_slices[fold]
        train_mask = np.ones(len(y), dtype=bool)
        train_mask[valid_slice] = False
        meta = Ridge(alpha=alpha, fit_intercept=True, random_state=seed)
        meta.fit(X[train_mask], y[train_mask])
        oof_predictions[valid_slice] = meta.predict(X[valid_slice])
        per_fold_weights[fold] = {m: float(c) for m, c in zip(model_ids, meta.coef_)}

    final_meta = Ridge(alpha=alpha, fit_intercept=True, random_state=seed)
    final_meta.fit(X, y)
    final_weights = {m: float(c) for m, c in zip(model_ids, final_meta.coef_)}

    oof_metrics = {
        "mae": float(mean_absolute_error(y, oof_predictions)),
        "rmse": float(np.sqrt(mean_squared_error(y, oof_predictions))),
    }

    return {
        "oof_predictions": oof_predictions,
        "oof_y_true": y,
        "oof_metrics": oof_metrics,
        "per_fold_weights": per_fold_weights,
        "final_weights": final_weights,
        "final_intercept": float(final_meta.intercept_),
        "folds": folds,
        "model_ids": model_ids,
    }
