"""Phase 3 Stage 1 WIRE-UP tests — multi-task evaluator 분기 검증.

Spec: docs/multi_task_채점모델_구현_스펙_v_1_1.md v1.1.5 § 6, § 12.4, § 14
ACCEPTANCE: stages.mid_multitask (score_band_cutoffs, fairness_gate, auto_continue)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipelines.evaluate import (
    ALL_DIMENSIONS,
    PER_RUBRIC_DIMENSIONS,
    SCORE_BAND_PR_HIGH,
    SCORE_BAND_PR_LOW,
    SCORE_BAND_PR_MID,
    auto_continue_check,
    fairness_gate_per_rubric,
    score_band_per_rubric,
)


# =====================================================================
# 1. score_band_per_rubric — native 0~3 cutoff (T1-04)
# =====================================================================


class TestScoreBandPerRubric:
    def test_low_band_inclusive_upper(self):
        assert score_band_per_rubric(0.0) == SCORE_BAND_PR_LOW
        assert score_band_per_rubric(0.5) == SCORE_BAND_PR_LOW
        assert score_band_per_rubric(1.0) == SCORE_BAND_PR_LOW

    def test_mid_band_exclusive_lower_inclusive_upper(self):
        assert score_band_per_rubric(1.01) == SCORE_BAND_PR_MID
        assert score_band_per_rubric(1.5) == SCORE_BAND_PR_MID
        assert score_band_per_rubric(2.0) == SCORE_BAND_PR_MID

    def test_high_band_exclusive_lower(self):
        assert score_band_per_rubric(2.01) == SCORE_BAND_PR_HIGH
        assert score_band_per_rubric(2.5) == SCORE_BAND_PR_HIGH
        assert score_band_per_rubric(3.0) == SCORE_BAND_PR_HIGH


# =====================================================================
# 2. fairness_gate_per_rubric — 4 dimension acceptance
# =====================================================================


def _build_per_rubric_predictions(
    model_code: str,
    n_per_band: int = 20,
    per_dim_perfect: bool = True,
) -> pd.DataFrame:
    """각 차원(exp/org/cont) per-band 균등 + overall raw 균등 dummy predictions."""
    rng = np.random.default_rng(seed=42)
    rows = []
    for dim_low_anchor in [0.5, 1.5, 2.5]:  # low/mid/high 각 band
        for _ in range(n_per_band):
            row = {"model_code": model_code}
            for dim in PER_RUBRIC_DIMENSIONS:
                yt = dim_low_anchor + rng.normal(0, 0.05)
                yt = float(np.clip(yt, 0.0, 3.0))
                yp = yt if per_dim_perfect else yt + rng.normal(0, 0.3)
                yp = float(np.clip(yp, 0.0, 3.0))
                row[f"y_true_{dim}"] = yt
                row[f"y_pred_{dim}"] = yp
            # overall raw 0~30
            yt_raw = dim_low_anchor * 10.0 + rng.normal(0, 0.5)
            yt_raw = float(np.clip(yt_raw, 0.0, 30.0))
            yp_raw = yt_raw if per_dim_perfect else yt_raw + rng.normal(0, 3.0)
            yp_raw = float(np.clip(yp_raw, 0.0, 30.0))
            row["y_true_overall_raw"] = yt_raw
            row["y_pred_overall_raw"] = yp_raw
            rows.append(row)
    return pd.DataFrame(rows)


class TestFairnessGatePerRubric:
    def test_returns_4_dimensions(self):
        df = _build_per_rubric_predictions("M5", n_per_band=30)
        rng = np.random.default_rng(seed=42)
        result = fairness_gate_per_rubric(df, rng, bootstrap_b=100)
        assert "by_model" in result
        assert "M5" in result["by_model"]
        for dim in ALL_DIMENSIONS:
            assert dim in result["by_model"]["M5"], f"{dim} missing"

    def test_all_dimensions_pass_perfect_predictions(self):
        df = _build_per_rubric_predictions("M5", n_per_band=30, per_dim_perfect=True)
        rng = np.random.default_rng(seed=42)
        result = fairness_gate_per_rubric(df, rng, bootstrap_b=100)
        per_dim = result["by_model"]["M5"]
        # 모든 차원 acceptance pass
        for dim in ALL_DIMENSIONS:
            assert per_dim[dim].get("acceptance_pass") is True, (
                f"{dim} acceptance_pass should be True for perfect predictions"
            )
        assert per_dim["all_dimensions_pass"] is True

    def test_single_target_fallback_to_overall(self):
        # M4 single-target compat — y_true / y_pred + score_band 컬럼만
        df = pd.DataFrame({
            "model_code": ["M4"] * 30,
            "y_true": list(np.linspace(5, 25, 30)),
            "y_pred": list(np.linspace(5, 25, 30)),
            "score_band": (
                ["low_0_9"] * 10 + ["mid_10_19"] * 10 + ["high_20_30"] * 10
            ),
        })
        rng = np.random.default_rng(seed=42)
        result = fairness_gate_per_rubric(df, rng, bootstrap_b=100)
        per_dim = result["by_model"]["M4"]
        # overall은 평가, per-rubric은 SKIP_MISSING_COLUMN
        assert per_dim["overall"].get("acceptance_pass") is True
        for dim in PER_RUBRIC_DIMENSIONS:
            assert per_dim[dim].get("status") == "SKIP_MISSING_COLUMN"

    def test_returns_cutoff_metadata(self):
        df = _build_per_rubric_predictions("M5", n_per_band=15)
        rng = np.random.default_rng(seed=42)
        result = fairness_gate_per_rubric(df, rng, bootstrap_b=100)
        assert result["per_rubric_cutoffs"]["low_0_1"] == "<=1.0"
        assert result["per_rubric_cutoffs"]["mid_1_2"] == "1.0<x<=2.0"
        assert result["per_rubric_cutoffs"]["high_2_3"] == ">2.0"
        assert result["overall_cutoffs"]["low_0_9"] == "<10"
        assert result["acceptance_threshold_ratio"] == 0.7


# =====================================================================
# 3. auto_continue_check — 7 조건 + grace_cycles + evolution_progress
# =====================================================================


def _pass_cycle(idx: int, qwk: float = 0.45) -> dict:
    """기본 PASS_CANDIDATE cycle dict."""
    return {
        "cycle_id": f"M{idx + 1}",
        "judgement": "PASS_CANDIDATE",
        "fairness_gate_pass_per_rubric": True,
        "cost_circuit_breaker": False,
        "monotone_evolution_violations": 0,
        "per_rubric_monotone_regressions": 0,
        "evaluator_wire_up_completed": True,
        "m5_overall_qwk_lower95": qwk,
    }


class TestAutoContinueCheck:
    def test_empty_history_rejects(self):
        ok, reason = auto_continue_check([], current_cycle_idx=1)
        assert not ok
        assert reason == "no_cycle_history"

    def test_fail_judgement_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["judgement"] = "FAIL_CHANGE_MODEL"
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "judgement" in reason

    def test_fairness_gate_fail_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["fairness_gate_pass_per_rubric"] = False
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "fairness_gate" in reason

    def test_evaluator_wire_up_not_completed_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["evaluator_wire_up_completed"] = False
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "wire_up" in reason

    def test_consecutive_pass_candidate_max_2_rejects_on_3rd(self):
        # PASS_CANDIDATE 3 cycle 연속 → escalation (>2)
        h = [_pass_cycle(i) for i in range(3)]
        ok, reason = auto_continue_check(h, current_cycle_idx=3)
        assert not ok
        assert "consecutive_pass_candidate" in reason

    def test_grace_cycles_skips_evolution_check_m2_m4(self):
        # M2(idx=1), M3(idx=2), M4(idx=3) — grace_cycles=3 면제
        # PASS_CANDIDATE 2회 연속까지는 통과
        h = [_pass_cycle(0, qwk=0.30), _pass_cycle(1, qwk=0.30)]
        ok, reason = auto_continue_check(h, current_cycle_idx=2)
        assert ok, f"M2~M3 should pass grace_cycles, got reason: {reason}"

    def test_evolution_progress_required_after_grace(self):
        # consecutive_pass_candidate_max=2 한계 준수 위해 M2/M3는 PASS_FINAL
        # M4/M5 PASS_CANDIDATE 2회 (consec=2, max=2 == OK)
        # evolution_progress: window=2, recent=M3/M4/M5, baseline M3=0.40, current M5=0.40 → improvement=0 < 0.02 → reject
        h = [
            {**_pass_cycle(0, qwk=0.30), "judgement": "PASS_FINAL"},  # M2
            {**_pass_cycle(1, qwk=0.40), "judgement": "PASS_FINAL"},  # M3 baseline
            _pass_cycle(2, qwk=0.40),  # M4 PASS_CANDIDATE consec=1
            _pass_cycle(3, qwk=0.40),  # M5 PASS_CANDIDATE consec=2 (OK). 개선 0
        ]
        ok, reason = auto_continue_check(h, current_cycle_idx=4)
        assert not ok
        assert "evolution_progress" in reason

    def test_evolution_progress_passes_with_sufficient_improvement(self):
        # 동일 패턴, M3=0.40 baseline → M5=0.45 current, +0.05 ≥ 0.02 required → pass
        h = [
            {**_pass_cycle(0, qwk=0.30), "judgement": "PASS_FINAL"},
            {**_pass_cycle(1, qwk=0.40), "judgement": "PASS_FINAL"},  # M3 baseline
            _pass_cycle(2, qwk=0.42),  # M4 consec=1
            _pass_cycle(3, qwk=0.45),  # M5 consec=2. baseline 0.40 → 0.45, +0.05 > 0.02 → OK
        ]
        ok, reason = auto_continue_check(h, current_cycle_idx=4)
        assert ok, f"evolution_progress should pass with 0.05 improvement, got: {reason}"

    def test_cost_circuit_breaker_breach_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["cost_circuit_breaker"] = True
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "cost_circuit_breaker" in reason

    def test_monotone_evolution_violations_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["monotone_evolution_violations"] = 1
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "monotone_evolution_violations" in reason

    def test_per_rubric_monotone_regressions_rejects(self):
        h = [_pass_cycle(0)]
        h[0]["per_rubric_monotone_regressions"] = 1
        ok, reason = auto_continue_check(h, current_cycle_idx=1)
        assert not ok
        assert "per_rubric_monotone_regressions" in reason
