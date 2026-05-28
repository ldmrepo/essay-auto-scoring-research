"""Tests for pipelines.train_ensemble — M6 OOF Ridge stacking.

Prior implementation fit and predicted on the same (X, y), producing in-sample
metrics. These tests verify the new OOF protocol:
- meta-learner trained on folds != k, evaluated on held-out fold k
- OOF metrics differ from (and are typically worse than) in-sample fit
- per-fold weights are recorded; final weights are fit on all OOF base predictions
"""

from __future__ import annotations

import numpy as np
import pytest

from pipelines.train_ensemble import train_ensemble


def _synth_fold_predictions(n_per_fold: int, n_folds: int, seed: int) -> dict[str, list[dict]]:
    rng = np.random.default_rng(seed)
    out: dict[str, list[dict]] = {"M4": [], "M5": []}
    for fold in range(n_folds):
        y_true = rng.uniform(0, 30, size=n_per_fold)
        m4 = y_true + rng.normal(0, 2.0, size=n_per_fold)
        m5 = y_true + rng.normal(0, 1.0, size=n_per_fold)
        out["M4"].append({"fold": fold, "y_true": y_true, "y_pred": m4})
        out["M5"].append({"fold": fold, "y_true": y_true.copy(), "y_pred": m5})
    return out


class TestTrainEnsembleOof:
    def test_oof_predictions_length_matches_total_samples(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        result = train_ensemble(fold_preds, seed=42)
        assert len(result["oof_predictions"]) == 60
        assert len(result["oof_y_true"]) == 60

    def test_metrics_keys_present(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        result = train_ensemble(fold_preds, seed=42)
        assert "oof_metrics" in result
        assert "mae" in result["oof_metrics"]
        assert "rmse" in result["oof_metrics"]

    def test_per_fold_weights_one_entry_per_fold(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        result = train_ensemble(fold_preds, seed=42)
        assert set(result["per_fold_weights"].keys()) == {0, 1, 2}
        for w in result["per_fold_weights"].values():
            assert set(w.keys()) == {"M4", "M5"}

    def test_final_weights_keyed_by_model_id(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        result = train_ensemble(fold_preds, seed=42)
        assert set(result["final_weights"].keys()) == {"M4", "M5"}

    def test_oof_mae_no_better_than_insample(self):
        """OOF stacking honest metric: cannot be better than naive in-sample fit.

        Regression guard for prior in-sample bug — that bug reported the train-fit
        MAE as the ensemble valid metric, overstating performance.
        """
        fold_preds = _synth_fold_predictions(n_per_fold=25, n_folds=4, seed=7)
        result = train_ensemble(fold_preds, seed=42)

        from sklearn.linear_model import Ridge

        X = np.column_stack(
            [
                np.concatenate([entry["y_pred"] for entry in fold_preds[m]])
                for m in ["M4", "M5"]
            ]
        )
        y = np.concatenate([entry["y_true"] for entry in fold_preds["M4"]])
        naive = Ridge(alpha=1.0, fit_intercept=True, random_state=42)
        naive.fit(X, y)
        insample_mae = float(np.mean(np.abs(y - naive.predict(X))))

        assert result["oof_metrics"]["mae"] >= insample_mae - 1e-9

    def test_single_fold_raises(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=1, seed=0)
        with pytest.raises(ValueError, match="requires >=2 folds"):
            train_ensemble(fold_preds, seed=42)

    def test_missing_fold_in_one_model_raises(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        del fold_preds["M5"][1]
        with pytest.raises(ValueError, match="missing base predictions"):
            train_ensemble(fold_preds, seed=42)

    def test_y_true_mismatch_between_models_raises(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        fold_preds["M5"][0]["y_true"] = fold_preds["M5"][0]["y_true"] + 1.0
        with pytest.raises(ValueError, match="y_true mismatch"):
            train_ensemble(fold_preds, seed=42)

    def test_folds_and_model_ids_sorted_in_result(self):
        fold_preds = _synth_fold_predictions(n_per_fold=20, n_folds=3, seed=0)
        result = train_ensemble(fold_preds, seed=42)
        assert result["folds"] == [0, 1, 2]
        assert result["model_ids"] == ["M4", "M5"]
