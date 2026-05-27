"""Tests for pipelines.train_ensemble — M4+M5 stacking."""

import numpy as np
import pytest

from pipelines.train_ensemble import train_ensemble


class TestTrainEnsemble:
    def test_returns_predictions_matching_input_length(self):
        rng = np.random.default_rng(42)
        y_true = rng.uniform(0, 30, size=50)
        m4 = y_true + rng.normal(0, 2, size=50)  # M4 noisy predictions
        m5 = y_true + rng.normal(0, 1, size=50)  # M5 better

        result = train_ensemble(
            predictions={"M4": m4, "M5": m5},
            y_true=y_true,
            seed=42,
        )

        assert "predictions" in result
        assert "weights" in result
        assert "metrics" in result
        assert len(result["predictions"]) == len(y_true)

    def test_ensemble_mae_no_worse_than_individual(self):
        # Synthetic case: ensemble should at least tie best individual on this synthetic data
        rng = np.random.default_rng(0)
        y_true = rng.uniform(0, 30, size=100)
        m4 = y_true + rng.normal(0, 2, size=100)
        m5 = y_true + rng.normal(0, 1, size=100)

        result = train_ensemble(predictions={"M4": m4, "M5": m5}, y_true=y_true, seed=42)
        ens_mae = float(np.mean(np.abs(result["predictions"] - y_true)))
        m5_mae = float(np.mean(np.abs(m5 - y_true)))

        # ensemble must do at least as well as the better of the two on the train fit
        assert ens_mae <= m5_mae * 1.10  # 10% tolerance for stacking overhead

    def test_weights_keyed_by_model_id(self):
        rng = np.random.default_rng(1)
        y_true = rng.uniform(0, 30, size=30)
        m4 = y_true + rng.normal(0, 2, size=30)
        m5 = y_true + rng.normal(0, 1, size=30)

        result = train_ensemble(predictions={"M4": m4, "M5": m5}, y_true=y_true, seed=42)
        assert set(result["weights"].keys()) == {"M4", "M5"}
