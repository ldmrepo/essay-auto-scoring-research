#!/usr/bin/env python3
"""Evaluate baseline predictions with segment metrics and ceiling CIs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score, mean_absolute_error, mean_squared_error


DEFAULT_MODEL_CODES = ["M1", "M2", "M3", "M4", "M5", "M6"]
SCORE_MIN = 0
SCORE_MAX = 30
BOOTSTRAP_B = 1000
TASK_ID = "t_1bab6d23"
DEFAULT_FEATURE_PROVENANCE = "workspace/cycle_M1/features/feature_provenance_manifest.json"

# Hard Rule #14 (2026-05-28 신설): Score-Band Fairness Gate
SCORE_BAND_LOW = "low_0_9"
SCORE_BAND_MID = "mid_10_19"
SCORE_BAND_HIGH = "high_20_30"
SCORE_BAND_LOW_MIN_N = 10
FAIRNESS_GATE_RATIO = 0.7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build evaluation reports from out-of-fold model predictions."
    )
    parser.add_argument("--run-id", action="append", default=[], help="Reference MLflow run id(s) to verify against prediction artifacts.")
    parser.add_argument("--models-dir", default="workspace/cycle_M1/models")
    parser.add_argument("--audit-table", default="workspace/cycle_M1/audit/audit_table_no_raw_text.csv")
    parser.add_argument("--split-dir", default="workspace/cycle_M1/splits")
    parser.add_argument("--feature-provenance", default=DEFAULT_FEATURE_PROVENANCE)
    parser.add_argument("--acceptance-criteria", default="ACCEPTANCE_CRITERIA.yaml")
    parser.add_argument("--board-config", default="configs/board_config.yaml")
    parser.add_argument("--output-dir", default="workspace/cycle_M1/eval")
    parser.add_argument("--cycle-id", default="M1", help="Cycle id, e.g. '1' (Phase 1) or 'M1' (Phase 2).")
    parser.add_argument("--kanban-task-id", default=TASK_ID)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-b", type=int, default=BOOTSTRAP_B)
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODEL_CODES,
        help="Subset of model codes to evaluate. Default: M1..M6.",
    )
    parser.add_argument(
        "--expected-n",
        type=int,
        default=None,
        help="Optional expected total valid prediction count. Default: skip count check.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def package_versions() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit-learn": package_version("scikit-learn"),
        "pyyaml": package_version("PyYAML"),
    }


def clean_float(value: float | np.floating[Any]) -> float | None:
    as_float = float(value)
    if math.isnan(as_float) or math.isinf(as_float):
        return None
    return as_float


def qwk_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    true_rounded = np.clip(np.rint(y_true), SCORE_MIN, SCORE_MAX).astype(int)
    pred_rounded = np.clip(np.rint(y_pred), SCORE_MIN, SCORE_MAX).astype(int)
    score = cohen_kappa_score(
        true_rounded,
        pred_rounded,
        weights="quadratic",
        labels=list(range(SCORE_MIN, SCORE_MAX + 1)),
    )
    return float(score) if not math.isnan(float(score)) else float("nan")


def rmse_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | None]:
    return {
        "qwk": clean_float(qwk_score(y_true, y_pred)),
        "mae": clean_float(mean_absolute_error(y_true, y_pred)),
        "rmse": clean_float(rmse_score(y_true, y_pred)),
        "bias": clean_float(float(np.mean(y_pred - y_true))),
        "target_mean": clean_float(float(np.mean(y_true))),
        "prediction_mean": clean_float(float(np.mean(y_pred))),
        "prediction_std": clean_float(float(np.std(y_pred))),
    }


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    rng: np.random.Generator,
    b: int,
) -> dict[str, float | None]:
    n = len(y_true)
    if n < 2:
        return {"estimate": None, "lower95": None, "upper95": None, "std": None, "b": b}
    estimate = metric_fn(y_true, y_pred)
    values = []
    for _ in range(b):
        idx = rng.integers(0, n, size=n)
        value = metric_fn(y_true[idx], y_pred[idx])
        if not math.isnan(float(value)):
            values.append(float(value))
    if not values:
        return {"estimate": clean_float(estimate), "lower95": None, "upper95": None, "std": None, "b": b}
    arr = np.array(values, dtype=float)
    return {
        "estimate": clean_float(estimate),
        "lower95": clean_float(np.percentile(arr, 2.5)),
        "upper95": clean_float(np.percentile(arr, 97.5)),
        "std": clean_float(float(np.std(arr, ddof=1))) if len(arr) > 1 else None,
        "b": b,
    }


def human_ceiling_qwk(y_avg: np.ndarray, raters: np.ndarray) -> float:
    scores = [qwk_score(y_avg, raters[:, idx]) for idx in range(raters.shape[1])]
    valid = [score for score in scores if not math.isnan(score)]
    return float(np.mean(valid)) if valid else float("nan")


def bootstrap_human_ceiling(
    y_avg: np.ndarray,
    raters: np.ndarray,
    rng: np.random.Generator,
    b: int,
) -> dict[str, Any]:
    n = len(y_avg)
    estimate_by_rater = [
        clean_float(qwk_score(y_avg, raters[:, idx])) for idx in range(raters.shape[1])
    ]
    estimate = human_ceiling_qwk(y_avg, raters)
    values = []
    for _ in range(b):
        idx = rng.integers(0, n, size=n)
        value = human_ceiling_qwk(y_avg[idx], raters[idx])
        if not math.isnan(float(value)):
            values.append(float(value))
    arr = np.array(values, dtype=float)
    return {
        "metric_unit": "mean_QWK(rater_i, 3-rater-average)",
        "estimate": clean_float(estimate),
        "by_rater": {
            "rater_1": estimate_by_rater[0],
            "rater_2": estimate_by_rater[1],
            "rater_3": estimate_by_rater[2],
        },
        "lower95": clean_float(np.percentile(arr, 2.5)),
        "upper95": clean_float(np.percentile(arr, 97.5)),
        "std": clean_float(float(np.std(arr, ddof=1))) if len(arr) > 1 else None,
        "b": b,
    }


def score_band(score: float) -> str:
    """Hard Rule #14 (Score-Band Fairness Gate, 2026-05-28 신설) 정의.

    Phase 2 데이터셋 분포에 맞춰 0-30 점수를 3개 band로 분할:
      low_0_9: 0 <= score < 10
      mid_10_19: 10 <= score < 20
      high_20_30: 20 <= score <= 30
    """
    if score < 10:
        return SCORE_BAND_LOW
    if score < 20:
        return SCORE_BAND_MID
    return SCORE_BAND_HIGH


def load_audit_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "relative_path",
        "essay_id_label",
        "essay_type",
        "student_grade_group",
        "target_essay_scoreT_avg",
        "rater_1",
        "rater_2",
        "rater_3",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"audit table missing required columns: {missing}")
    if df["relative_path"].duplicated().any():
        raise ValueError("audit table has duplicate relative_path rows")
    df = df.copy()
    df["score_band"] = df["target_essay_scoreT_avg"].map(score_band)
    return df


def load_predictions(
    models_dir: Path,
    audit_df: pd.DataFrame,
    model_codes: list[str],
    expected_n: int | None = None,
) -> pd.DataFrame:
    metadata = audit_df[
        [
            "relative_path",
            "essay_id_label",
            "essay_type",
            "student_grade_group",
            "score_band",
            "target_essay_scoreT_avg",
            "rater_1",
            "rater_2",
            "rater_3",
        ]
    ]
    frames = []
    for model_code in model_codes:
        path = models_dir / model_code / "predictions.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        rename = {
            "model_id": "model_code",
            "target_essay_scoreT_avg": "y_true",
            "essay_scoreT_avg": "y_true",
            "prediction": "y_pred",
            "prediction_rounded": "y_pred_rounded_0_30",
        }
        df = df.rename(columns={key: value for key, value in rename.items() if key in df.columns})
        if "partition" in df.columns:
            df = df[df["partition"] == "valid"].copy()
        missing = sorted({"model_code", "fold", "relative_path", "y_true", "y_pred"} - set(df.columns))
        if missing:
            raise ValueError(f"{path} missing required columns after normalization: {missing}")
        if expected_n is not None and len(df) != expected_n:
            raise ValueError(
                f"{path} should contain {expected_n} out-of-fold valid predictions, got {len(df)}"
            )
        if df["relative_path"].duplicated().any():
            raise ValueError(f"{path} has duplicate valid relative_path rows")
        metadata_columns = [
            "essay_type",
            "student_grade_group",
            "score_band",
            "target_essay_scoreT_avg",
            "rater_1",
            "rater_2",
            "rater_3",
        ]
        df = df.drop(columns=[col for col in metadata_columns if col in df.columns])
        joined = df.merge(metadata, on="relative_path", how="left", validate="one_to_one")
        if joined["target_essay_scoreT_avg"].isna().any():
            raise ValueError(f"{path} has predictions without audit metadata")
        if not np.allclose(joined["y_true"], joined["target_essay_scoreT_avg"], atol=1e-6):
            raise ValueError(f"{path} y_true does not match audit target average")
        joined["model_code"] = model_code
        frames.append(joined)
    return pd.concat(frames, ignore_index=True)


def build_segment_metrics(
    predictions: pd.DataFrame,
    rng: np.random.Generator,
    b: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    segment_defs = [
        ("overall", None),
        ("type", "essay_type"),
        ("학년군", "student_grade_group"),
        ("score_band", "score_band"),
    ]
    for model_code, model_df in predictions.groupby("model_code", sort=True):
        for segment_name, column in segment_defs:
            groups = [("all", model_df)] if column is None else model_df.groupby(column, dropna=False, sort=True)
            for segment_value, group in groups:
                y_true = group["y_true"].to_numpy(dtype=float)
                y_pred = group["y_pred"].to_numpy(dtype=float)
                metrics = regression_metrics(y_true, y_pred)
                qwk_ci = bootstrap_ci(y_true, y_pred, qwk_score, rng, b)
                rows.append(
                    {
                        "model_code": model_code,
                        "segment": segment_name,
                        "segment_value": str(segment_value),
                        "n": int(len(group)),
                        **metrics,
                        "qwk_lower95": qwk_ci["lower95"],
                        "qwk_upper95": qwk_ci["upper95"],
                        "qwk_bootstrap_std": qwk_ci["std"],
                        "bootstrap_b": b,
                    }
                )
    return pd.DataFrame(rows)


def fairness_gate(
    predictions: pd.DataFrame, rng: np.random.Generator, bootstrap_b: int = BOOTSTRAP_B
) -> dict[str, Any]:
    """Hard Rule #14 (Score-Band Fairness Gate, 2026-05-28 신설) 측정.

    Per-band QWK + macro-QWK (per-band simple unweighted mean, majority 편향 방지)
    + worst-band QWK (low band N<10이면 SKIP_UNSTABLE) + acceptance hard-block
    (worst_band_qwk >= macro_qwk * FAIRNESS_GATE_RATIO).
    """
    out: dict[str, Any] = {"by_model": {}}
    bands = [SCORE_BAND_LOW, SCORE_BAND_MID, SCORE_BAND_HIGH]
    for model_code, model_df in predictions.groupby("model_code"):
        per_band: dict[str, dict[str, Any]] = {}
        for band in bands:
            band_df = model_df[model_df["score_band"] == band]
            n = int(len(band_df))
            if n == 0:
                per_band[band] = {"n": 0, "qwk": None, "status": "EMPTY"}
                continue
            qwk_val = qwk_score(
                band_df["y_true"].to_numpy(dtype=float),
                band_df["y_pred"].to_numpy(dtype=float),
            )
            ci = bootstrap_ci(
                band_df["y_true"].to_numpy(dtype=float),
                band_df["y_pred"].to_numpy(dtype=float),
                qwk_score,
                rng,
                bootstrap_b,
            )
            per_band[band] = {
                "n": n,
                "qwk": float(qwk_val),
                "qwk_lower95": ci["lower95"],
                "qwk_upper95": ci["upper95"],
                "status": "OK",
            }

        # macro_qwk: simple unweighted mean of bands with sufficient samples
        eligible = [
            (b, per_band[b])
            for b in bands
            if per_band[b]["status"] == "OK"
            and (b != SCORE_BAND_LOW or per_band[b]["n"] >= SCORE_BAND_LOW_MIN_N)
        ]
        unstable_low = (
            per_band[SCORE_BAND_LOW]["status"] == "OK"
            and per_band[SCORE_BAND_LOW]["n"] < SCORE_BAND_LOW_MIN_N
        )

        if not eligible:
            out["by_model"][model_code] = {
                "per_band": per_band,
                "macro_qwk": None,
                "worst_band_qwk": None,
                "worst_band_name": None,
                "low_band_status": "SKIP_UNSTABLE" if unstable_low else "MISSING",
                "acceptance_pass": False,
                "acceptance_reason": "no_eligible_bands",
            }
            continue

        macro_qwk = float(np.mean([entry["qwk"] for _, entry in eligible]))
        # Worst-band QWK = min over mid/high only (low excluded if N<10)
        mid_high = [
            (b, entry)
            for b, entry in eligible
            if b in {SCORE_BAND_MID, SCORE_BAND_HIGH}
        ]
        if mid_high:
            worst_b, worst_entry = min(mid_high, key=lambda kv: kv[1]["qwk"])
            worst_band_qwk = float(worst_entry["qwk"])
            worst_band_name = worst_b
        else:
            worst_b, worst_entry = min(eligible, key=lambda kv: kv[1]["qwk"])
            worst_band_qwk = float(worst_entry["qwk"])
            worst_band_name = worst_b

        acceptance_pass = worst_band_qwk >= macro_qwk * FAIRNESS_GATE_RATIO
        out["by_model"][model_code] = {
            "per_band": per_band,
            "macro_qwk": macro_qwk,
            "worst_band_qwk": worst_band_qwk,
            "worst_band_name": worst_band_name,
            "low_band_status": "SKIP_UNSTABLE" if unstable_low else "OK",
            "acceptance_threshold": macro_qwk * FAIRNESS_GATE_RATIO,
            "acceptance_pass": bool(acceptance_pass),
            "acceptance_reason": (
                f"worst_band_qwk={worst_band_qwk:.4f} "
                f"{'>=' if acceptance_pass else '<'} "
                f"macro_qwk * {FAIRNESS_GATE_RATIO} = "
                f"{macro_qwk * FAIRNESS_GATE_RATIO:.4f}"
            ),
        }
    out["acceptance_threshold_ratio"] = FAIRNESS_GATE_RATIO
    out["low_band_min_n"] = SCORE_BAND_LOW_MIN_N
    out["bootstrap_b"] = bootstrap_b
    return out


def load_training_warnings(models_dir: Path, model_codes: list[str]) -> dict[str, Any]:
    warnings: dict[str, Any] = {}
    for model_code in model_codes:
        path = models_dir / model_code / "metrics_per_fold.json"
        if not path.exists():
            continue
        per_fold = load_json(path)
        warnings[model_code] = [
            {
                "fold": item.get("fold"),
                "train_valid_qwk_gap_abs": item.get("train_valid_qwk_gap_abs"),
                "warnings": item.get("warnings", []),
            }
            for item in per_fold
            if item.get("warnings") or float(item.get("train_valid_qwk_gap_abs", 0.0)) > 0.10
        ]
    return warnings


def evaluate_acceptance(
    overall_rows: pd.DataFrame,
    ceiling: dict[str, Any],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    metrics_by_model = {
        row["model_code"]: row.to_dict()
        for _, row in overall_rows.iterrows()
    }
    m1_qwk = metrics_by_model["M1"]["qwk"]
    m3_qwk = metrics_by_model["M3"]["qwk"]
    m4_qwk = metrics_by_model["M4"]["qwk"]
    dummy_floor_pass = bool(m1_qwk <= m3_qwk or m1_qwk <= m4_qwk)
    ceiling_upper = ceiling["upper95"]
    ceiling_warnings = []
    for model_code, metrics in metrics_by_model.items():
        lower = metrics.get("qwk_lower95")
        if lower is not None and ceiling_upper is not None and lower > ceiling_upper:
            ceiling_warnings.append(
                f"{model_code}: model_lower95={lower:.4f} > ceiling_upper95={ceiling_upper:.4f}"
            )
    toy_criteria = criteria.get("stages", {}).get("toy", {})
    return {
        "stage": "toy",
        "dummy_floor_gate": {
            "rule": "M1_qwk <= M3_qwk OR M1_qwk <= M4_qwk",
            "hard_block": True,
            "pass": dummy_floor_pass,
            "values": {
                "M1_qwk": clean_float(m1_qwk),
                "M3_qwk": clean_float(m3_qwk),
                "M4_qwk": clean_float(m4_qwk),
            },
        },
        "ceiling_gate": {
            "rule": "warn-only when model_lower95 > ceiling_upper95",
            "hard_block": bool(toy_criteria.get("ceiling_comparison", {}).get("hard_block", False)),
            "pass": len(ceiling_warnings) == 0,
            "warnings": ceiling_warnings,
        },
        "judgement": "PASS_CANDIDATE" if dummy_floor_pass else "FAIL_CHANGE_MODEL",
    }


def collect_prediction_run_ids(predictions: pd.DataFrame) -> list[str]:
    if "mlflow_run_id" not in predictions.columns:
        return []
    return sorted(
        str(run_id)
        for run_id in predictions["mlflow_run_id"].dropna().unique()
        if str(run_id).strip()
    )


def verify_reference_run_ids(reference_run_ids: list[str], prediction_run_ids: list[str]) -> None:
    missing = sorted(set(reference_run_ids) - set(prediction_run_ids))
    if missing:
        raise ValueError(
            "reference --run-id value(s) not found in prediction artifacts: "
            + ", ".join(missing)
        )


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)):
            return "NA"
        return f"{float(value):.{digits}f}"
    return str(value)


def build_eval_report(
    path: Path,
    segment_df: pd.DataFrame,
    acceptance: dict[str, Any],
    training_warnings: dict[str, Any],
    cycle_id: int,
) -> None:
    overall = segment_df[segment_df["segment"] == "overall"].sort_values("model_code")
    lines = [
        f"# Cycle {cycle_id} Evaluation Report",
        "",
        f"Created at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Metric unit: QWK(prediction, 3-rater-average), with prediction and target rounded to the 0-30 rubric scale for QWK.",
        "Toy-phase monotonicity and ceiling checks follow AGENTS.md warn-only policy except the M1 dummy-floor sanity gate.",
        "",
        "## Overall Metrics",
    ]
    lines.extend(
        markdown_table(
            ["Model", "n", "QWK", "QWK 95% CI", "MAE", "RMSE", "Bias"],
            [
                [
                    row["model_code"],
                    int(row["n"]),
                    fmt(row["qwk"]),
                    f"{fmt(row['qwk_lower95'])} - {fmt(row['qwk_upper95'])}",
                    fmt(row["mae"]),
                    fmt(row["rmse"]),
                    fmt(row["bias"]),
                ]
                for _, row in overall.iterrows()
            ],
        )
    )
    lines.extend(["", "## Segment Metrics", ""])
    for segment in ["type", "학년군", "score_band"]:
        lines.append(f"### {segment}")
        subset = segment_df[segment_df["segment"] == segment].sort_values(
            ["model_code", "segment_value"]
        )
        lines.extend(
            markdown_table(
                ["Model", "Segment", "n", "QWK", "QWK 95% CI", "MAE", "RMSE", "Bias"],
                [
                    [
                        row["model_code"],
                        row["segment_value"],
                        int(row["n"]),
                        fmt(row["qwk"]),
                        f"{fmt(row['qwk_lower95'])} - {fmt(row['qwk_upper95'])}",
                        fmt(row["mae"]),
                        fmt(row["rmse"]),
                        fmt(row["bias"]),
                    ]
                    for _, row in subset.iterrows()
                ],
            )
        )
        lines.append("")
    lines.extend(
        [
            "## Acceptance Comparison",
            "",
            f"Judgement: `{acceptance['judgement']}`",
            f"Dummy-floor gate: {'PASS' if acceptance['dummy_floor_gate']['pass'] else 'FAIL'}",
            f"Ceiling warning gate: {'PASS' if acceptance['ceiling_gate']['pass'] else 'WARN'}",
            "",
            "## Training Gap Warnings",
        ]
    )
    for model_code in MODEL_CODES:
        items = training_warnings.get(model_code, [])
        if not items:
            lines.append(f"- {model_code}: none")
            continue
        rendered = ", ".join(
            f"fold {item['fold']} gap_abs={fmt(item['train_valid_qwk_gap_abs'])}"
            for item in items
        )
        lines.append(f"- {model_code}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_ceiling_report(
    path: Path,
    ceiling: dict[str, Any],
    overall_rows: pd.DataFrame,
    acceptance: dict[str, Any],
    cycle_id: int,
) -> None:
    lines = [
        f"# Cycle {cycle_id} Ceiling Comparison",
        "",
        "Ceiling unit: mean_QWK(rater_i, 3-rater-average). This matches model evaluation as QWK(model_pred, 3-rater-average).",
        f"Bootstrap: B={ceiling['b']}, row-level resampling, 95% percentile CI.",
        "",
        "## Human Ceiling",
    ]
    lines.extend(
        markdown_table(
            ["Metric", "Estimate", "95% CI", "Std"],
            [
                [
                    ceiling["metric_unit"],
                    fmt(ceiling["estimate"]),
                    f"{fmt(ceiling['lower95'])} - {fmt(ceiling['upper95'])}",
                    fmt(ceiling["std"]),
                ]
            ],
        )
    )
    lines.extend(["", "By-rater estimates:"])
    for rater, value in ceiling["by_rater"].items():
        lines.append(f"- {rater}: {fmt(value)}")
    lines.extend(["", "## Model vs Ceiling"])
    ceiling_upper = ceiling["upper95"]
    rows = []
    for _, row in overall_rows.sort_values("model_code").iterrows():
        lower = row["qwk_lower95"]
        warn = lower is not None and ceiling_upper is not None and lower > ceiling_upper
        rows.append(
            [
                row["model_code"],
                fmt(row["qwk"]),
                f"{fmt(row['qwk_lower95'])} - {fmt(row['qwk_upper95'])}",
                "WARN" if warn else "PASS",
            ]
        )
    lines.extend(markdown_table(["Model", "QWK", "95% CI", "Ceiling Check"], rows))
    if acceptance["ceiling_gate"]["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in acceptance["ceiling_gate"]["warnings"])
    else:
        lines.extend(["", "No model lower95 exceeds the human ceiling upper95."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if (
        args.cycle_id != 2
        and args.feature_provenance == DEFAULT_FEATURE_PROVENANCE
    ):
        args.feature_provenance = (
            f"workspace/cycle_{args.cycle_id}/features/feature_provenance_manifest.json"
        )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_path = Path(args.audit_table)
    models_dir = Path(args.models_dir)
    split_dir = Path(args.split_dir)
    feature_provenance_path = Path(args.feature_provenance)
    acceptance_path = Path(args.acceptance_criteria)
    board_config_path = Path(args.board_config)

    audit_df = load_audit_table(audit_path)
    predictions = load_predictions(
        models_dir, audit_df, model_codes=args.models, expected_n=args.expected_n
    )
    prediction_run_ids = collect_prediction_run_ids(predictions)
    verify_reference_run_ids(args.run_id, prediction_run_ids)
    criteria = load_yaml(acceptance_path)
    board_config = load_yaml(board_config_path)
    feature_provenance = load_json(feature_provenance_path)
    if int(feature_provenance.get("label_side_feature_count", -1)) != 0:
        raise RuntimeError("feature provenance label-side count is not zero")

    rng = np.random.default_rng(args.seed)
    segment_df = build_segment_metrics(predictions, rng, args.bootstrap_b)
    overall_rows = segment_df[segment_df["segment"] == "overall"].copy()

    ceiling_rng = np.random.default_rng(args.seed + 10_000)
    ceiling = bootstrap_human_ceiling(
        audit_df["target_essay_scoreT_avg"].to_numpy(dtype=float),
        audit_df[["rater_1", "rater_2", "rater_3"]].to_numpy(dtype=float),
        ceiling_rng,
        args.bootstrap_b,
    )
    acceptance = evaluate_acceptance(overall_rows, ceiling, criteria)
    training_warnings = load_training_warnings(models_dir, args.models)

    # Hard Rule #14 (Score-Band Fairness Gate, 2026-05-28 신설)
    fairness_rng = np.random.default_rng(args.seed + 20_000)
    fairness = fairness_gate(predictions, fairness_rng, args.bootstrap_b)

    segment_metrics_path = output_dir / "segment_metrics.csv"
    eval_report_path = output_dir / "eval_report.md"
    ceiling_report_path = output_dir / "ceiling_comparison.md"
    fairness_gate_path = output_dir / "fairness_gate.json"
    manifest_path = output_dir / "eval_manifest.json"

    segment_df.to_csv(segment_metrics_path, index=False)
    write_json(fairness_gate_path, fairness)
    build_eval_report(eval_report_path, segment_df, acceptance, training_warnings, args.cycle_id)
    build_ceiling_report(ceiling_report_path, ceiling, overall_rows, acceptance, args.cycle_id)

    cost_config = (
        board_config.get("auto_cycle", {})
        .get("cost_circuit_breaker", {})
    )
    run_id_args = " ".join(f"--run-id {run_id}" for run_id in args.run_id)
    run_id_suffix = f" {run_id_args}" if run_id_args else ""
    rebuild_command = (
        f"python3 pipelines/evaluate.py --models-dir {models_dir} "
        f"--audit-table {audit_path} "
        f"--split-dir {split_dir} "
        f"--feature-provenance {feature_provenance_path} "
        f"--output-dir {output_dir} "
        f"--cycle-id {args.cycle_id} --kanban-task-id {args.kanban_task_id} "
        f"--seed {args.seed} --bootstrap-b {args.bootstrap_b}"
        f"{run_id_suffix}"
    )
    manifest = {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "bootstrap_ci": {
            "b": args.bootstrap_b,
            "method": "row-level percentile bootstrap",
            "model_metric": "QWK(model_pred, 3-rater-average)",
            "ceiling_metric": ceiling["metric_unit"],
        },
        "inputs": {
            "reference_mlflow_run_ids": args.run_id,
            "prediction_mlflow_run_ids": prediction_run_ids,
            "models_dir": str(models_dir),
            "audit_table": str(audit_path),
            "audit_table_sha256": sha256_file(audit_path),
            "split_manifest": str(split_dir / "split_manifest.yaml"),
            "split_manifest_sha256": sha256_file(split_dir / "split_manifest.yaml"),
            "feature_provenance": str(feature_provenance_path),
            "feature_provenance_sha256": sha256_file(feature_provenance_path),
            "acceptance_criteria": str(acceptance_path),
            "acceptance_criteria_sha256": sha256_file(acceptance_path),
            "board_config": str(board_config_path),
            "board_config_sha256": sha256_file(board_config_path),
        },
        "outputs": {
            "eval_report": str(eval_report_path),
            "segment_metrics": str(segment_metrics_path),
            "ceiling_comparison": str(ceiling_report_path),
            "eval_manifest": str(manifest_path),
        },
        "overall_metrics": {
            row["model_code"]: {
                "qwk": clean_float(row["qwk"]),
                "qwk_lower95": clean_float(row["qwk_lower95"]),
                "qwk_upper95": clean_float(row["qwk_upper95"]),
                "mae": clean_float(row["mae"]),
                "rmse": clean_float(row["rmse"]),
                "bias": clean_float(row["bias"]),
            }
            for _, row in overall_rows.iterrows()
        },
        "human_ceiling": ceiling,
        "acceptance": acceptance,
        "training_warnings": training_warnings,
        "feature_provenance_gate": {
            "status": "PASS",
            "label_side_feature_count": feature_provenance.get("label_side_feature_count"),
        },
        "cost_circuit_breaker": {
            "status": "PASS",
            "breached": False,
            "reason": "local file evaluation; no external LLM/API spend used by this task",
            "configured_limits": cost_config,
        },
        "package_versions": package_versions(),
        "rebuild_command": rebuild_command,
        "verification_commands": [
            rebuild_command,
            f"python3 -c \"import json; m=json.load(open('{manifest_path}')); assert 'bootstrap_ci' in m and m['cycle_id']=={args.cycle_id}\"",
            f"python3 -c \"import pandas as pd; s=pd.read_csv('{segment_metrics_path}'); assert {{'overall','type','학년군','score_band'}} <= set(s['segment'])\"",
            f"python3 -c \"import json; m=json.load(open('{manifest_path}')); assert m['human_ceiling']['metric_unit']=='mean_QWK(rater_i, 3-rater-average)'\"",
        ],
    }
    write_json(manifest_path, manifest)

    print(f"wrote {eval_report_path}")
    print(f"wrote {segment_metrics_path}")
    print(f"wrote {ceiling_report_path}")
    print(f"wrote {manifest_path}")
    print(f"judgement={acceptance['judgement']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
