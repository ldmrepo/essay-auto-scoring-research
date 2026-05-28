"""Tests for pipelines.evaluate — Phase 2 spec (score_band Hard Rule #14, M5/M6).

Regression coverage of external review findings:
- score_band uses Hard Rule #14 boundaries (low_0_9/mid_10_19/high_20_30)
- DEFAULT_MODEL_CODES includes M1..M6
- --cycle-id accepts string (e.g. "M1")
- expected_n is optional (no 342 hardcode)
- fairness_gate produces required keys per Hard Rule #14
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipelines.evaluate import (
    DEFAULT_MODEL_CODES,
    FAIRNESS_GATE_RATIO,
    SCORE_BAND_HIGH,
    SCORE_BAND_LOW,
    SCORE_BAND_LOW_MIN_N,
    SCORE_BAND_MID,
    fairness_gate,
    parse_args,
    score_band,
)


class TestScoreBand:
    def test_boundary_0_returns_low(self):
        assert score_band(0.0) == SCORE_BAND_LOW

    def test_just_below_10_returns_low(self):
        assert score_band(9.999) == SCORE_BAND_LOW

    def test_10_returns_mid(self):
        assert score_band(10.0) == SCORE_BAND_MID

    def test_just_below_20_returns_mid(self):
        assert score_band(19.999) == SCORE_BAND_MID

    def test_20_returns_high(self):
        assert score_band(20.0) == SCORE_BAND_HIGH

    def test_30_returns_high(self):
        assert score_band(30.0) == SCORE_BAND_HIGH

    def test_band_names_match_hard_rule_14(self):
        assert SCORE_BAND_LOW == "low_0_9"
        assert SCORE_BAND_MID == "mid_10_19"
        assert SCORE_BAND_HIGH == "high_20_30"


class TestDefaultModelCodes:
    def test_includes_m1_through_m6(self):
        assert DEFAULT_MODEL_CODES == ["M1", "M2", "M3", "M4", "M5", "M6"]


class TestParseArgsPhase2:
    def test_cycle_id_accepts_string_m1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["evaluate.py", "--cycle-id", "M1"])
        args = parse_args()
        assert args.cycle_id == "M1"

    def test_expected_n_optional_default_none(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["evaluate.py"])
        args = parse_args()
        assert args.expected_n is None

    def test_models_subset(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["evaluate.py", "--models", "M4", "M5", "M6"])
        args = parse_args()
        assert args.models == ["M4", "M5", "M6"]


class TestFairnessGate:
    def _make_predictions(self, model_code: str, per_band: dict[str, tuple[int, float]]):
        """per_band: {band: (n, noise_std)}.

        Generates n samples per band with y_true uniform inside the band and
        y_pred = y_true + N(0, noise_std). Higher noise → lower QWK.
        """
        rng = np.random.default_rng(42)
        ranges = {
            SCORE_BAND_LOW: (0.0, 9.999),
            SCORE_BAND_MID: (10.0, 19.999),
            SCORE_BAND_HIGH: (20.0, 30.0),
        }
        rows = []
        for band, (n, noise) in per_band.items():
            lo, hi = ranges[band]
            y_true = rng.uniform(lo, hi, size=n)
            y_pred = y_true + rng.normal(0.0, noise, size=n)
            for yt, yp in zip(y_true, y_pred):
                rows.append(
                    {
                        "model_code": model_code,
                        "score_band": band,
                        "y_true": float(yt),
                        "y_pred": float(yp),
                    }
                )
        return pd.DataFrame(rows)

    def test_required_keys_per_model(self):
        df = self._make_predictions(
            "M4", {SCORE_BAND_LOW: (20, 0.5), SCORE_BAND_MID: (30, 0.5), SCORE_BAND_HIGH: (50, 0.5)}
        )
        result = fairness_gate(df, np.random.default_rng(0), bootstrap_b=50)
        m4 = result["by_model"]["M4"]
        for key in [
            "per_band",
            "macro_qwk",
            "worst_band_qwk",
            "worst_band_name",
            "low_band_status",
            "acceptance_pass",
        ]:
            assert key in m4

    def test_low_band_below_min_n_marks_skip_unstable(self):
        df = self._make_predictions(
            "M4",
            {SCORE_BAND_LOW: (3, 0.5), SCORE_BAND_MID: (40, 0.5), SCORE_BAND_HIGH: (50, 0.5)},
        )
        result = fairness_gate(df, np.random.default_rng(0), bootstrap_b=50)
        m4 = result["by_model"]["M4"]
        assert m4["low_band_status"] == "SKIP_UNSTABLE"
        # macro_qwk should NOT include the unstable low band
        assert m4["per_band"][SCORE_BAND_LOW]["n"] == 3
        assert m4["per_band"][SCORE_BAND_LOW]["n"] < SCORE_BAND_LOW_MIN_N

    def test_acceptance_pass_when_balanced(self):
        df = self._make_predictions(
            "M_balanced",
            {SCORE_BAND_LOW: (30, 1.0), SCORE_BAND_MID: (30, 1.0), SCORE_BAND_HIGH: (30, 1.0)},
        )
        result = fairness_gate(df, np.random.default_rng(0), bootstrap_b=50)
        m = result["by_model"]["M_balanced"]
        assert m["acceptance_pass"] is True
        assert m["worst_band_qwk"] >= m["macro_qwk"] * FAIRNESS_GATE_RATIO

    def test_acceptance_fail_when_one_band_collapsed(self):
        # Mid band has very high noise → near-zero QWK; high band low noise
        df = self._make_predictions(
            "M_imbalanced",
            {
                SCORE_BAND_LOW: (30, 0.3),
                SCORE_BAND_MID: (30, 50.0),  # crushed QWK
                SCORE_BAND_HIGH: (30, 0.3),
            },
        )
        result = fairness_gate(df, np.random.default_rng(0), bootstrap_b=50)
        m = result["by_model"]["M_imbalanced"]
        # Worst-band picks min of mid/high → mid is crushed
        assert m["worst_band_name"] == SCORE_BAND_MID
        assert m["acceptance_pass"] is False

    def test_metadata_keys_present(self):
        df = self._make_predictions(
            "M", {SCORE_BAND_MID: (30, 0.5), SCORE_BAND_HIGH: (40, 0.5)}
        )
        result = fairness_gate(df, np.random.default_rng(0), bootstrap_b=20)
        assert result["acceptance_threshold_ratio"] == FAIRNESS_GATE_RATIO
        assert result["low_band_min_n"] == SCORE_BAND_LOW_MIN_N
        assert result["bootstrap_b"] == 20
