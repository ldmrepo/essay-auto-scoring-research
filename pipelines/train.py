#!/usr/bin/env python3
"""Train leakage-free toy baselines and register MLflow runs.

The training pipeline consumes feature matrices produced by build_features.py.
Label JSON is read only for the supervised target and reporting segments; no
label-side fields are joined into the model feature matrices.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMRegressor
from scipy import sparse
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import cohen_kappa_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TARGET_NAME = "essay_scoreT_avg"
SCORE_MIN = 0
SCORE_MAX = 30
SENTENCE_SEPARATOR = "#@문장구분#"
MODEL_SPECS: dict[str, dict[str, Any]] = {
    "M1": {
        "model_name": "dummy_mean",
        "model_type": "DummyRegressor",
        "feature_set": "none",
        "assumption": "Predict the fold-train target mean for every row.",
    },
    "M2": {
        "model_name": "length_ridge",
        "model_type": "RidgeCV",
        "feature_set": "essay_char_count_only",
        "assumption": "Essay length carries weak signal but uses no label-side fields.",
        "alphas": [0.1, 1.0, 10.0, 100.0, 1000.0],
    },
    "M3": {
        "model_name": "tfidf_ridge",
        "model_type": "RidgeCV",
        "feature_set": "word_char_tfidf",
        "assumption": "Train-fold TF-IDF n-grams capture lexical signal.",
        "alphas": [1.0, 10.0, 100.0, 1000.0],
    },
    "M4": {
        "model_name": "lightgbm_all_features",
        "model_type": "LGBMRegressor",
        "feature_set": "word_char_tfidf_plus_derived_numeric",
        "assumption": "A small tree ensemble can use sparse text features and derived numeric features.",
        "params": {
            "objective": "regression",
            "n_estimators": 80,
            "learning_rate": 0.05,
            "num_leaves": 7,
            "min_child_samples": 5,
            "subsample": 0.9,
            "colsample_bytree": 0.7,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "n_jobs": 1,
            "verbosity": -1,
        },
    },
    "M5": {
        "model_name": "klue_roberta_regression",
        "model_type": "KLUE-RoBERTa",
        "feature_set": "raw_text",
        "assumption": "Pretrained transformer captures semantic + lexical signal far beyond TF-IDF.",
        "default_hparams": {
            "learning_rate": 2e-5,
            "per_device_train_batch_size": 16,
            "num_train_epochs": 3,
            "weight_decay": 0.01,
            "warmup_ratio": 0.06,
        },
    },
    "M6": {
        "model_name": "m4_m5_stacking",
        "model_type": "RidgeStackingEnsemble",
        "feature_set": "stacked_predictions",
        "assumption": "Linear stacking of M4 (LightGBM) + M5 (RoBERTa) reduces individual errors when uncorrelated.",
        "depends_on": ["M4", "M5"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train M1-M4 leakage-free toy baselines.")
    parser.add_argument("--config", default="all", help="YAML config path or 'all'.")
    parser.add_argument("--split-dir", "--split", default="workspace/cycle_1/splits")
    parser.add_argument("--feature-dir", default="workspace/cycle_1/features")
    parser.add_argument("--label-dir", default="dataset/sample/라벨링데이터")
    parser.add_argument("--output-dir", default="workspace/cycle_1/models")
    parser.add_argument("--mlflow-uri", default="sqlite:///mlflow.db")
    parser.add_argument("--experiment-name", default="cycle_1")
    parser.add_argument("--cycle-id", default="1", help="Cycle id, e.g. '1' (Phase 1) or 'M1' (Phase 2).")
    parser.add_argument("--kanban-task-id", default="t_fe88cfdb")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--model",
        default=None,
        help="HuggingFace model id for M5 (e.g. klue/roberta-small). Required for M5.",
    )
    parser.add_argument(
        "--hpo-trials",
        type=int,
        default=0,
        help=(
            "Deprecated in train.py. HPO runs in pipelines.run_hpo. "
            "Use --hparams-json to inject HPO best_params into final training."
        ),
    )
    parser.add_argument(
        "--hparams-json",
        default=None,
        help=(
            "Optional path to a JSON file containing HPO best_params for the "
            "trained model. Falls back to MODEL_SPECS default_hparams/params if "
            "absent. Expected schema: {\"best_params\": {...}} or {...} directly."
        ),
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["M1", "M2", "M3", "M4"],
        help="Subset of model IDs to train. Accepts space-separated or comma-separated IDs.",
    )
    return parser.parse_args()


def load_hparams_override(path: str | None) -> dict[str, Any] | None:
    """Load HPO best_params from a JSON file.

    Accepts either a top-level dict (treated as hparams directly) or a dict
    with a "best_params" key (matches pipelines.run_hpo study_summary output).
    Returns None when path is None or empty.
    """
    if not path:
        return None
    payload = load_json(Path(path))
    if isinstance(payload, dict) and "best_params" in payload:
        return dict(payload["best_params"])
    if isinstance(payload, dict):
        return dict(payload)
    raise ValueError(f"hparams JSON at {path} must be a dict, got {type(payload).__name__}")


def normalize_model_ids(model_args: list[str]) -> list[str]:
    model_ids: list[str] = []
    for token in model_args:
        model_ids.extend(part.strip() for part in token.split(",") if part.strip())
    unknown = sorted(set(model_ids) - set(MODEL_SPECS))
    if unknown:
        raise ValueError(f"unknown model ids: {unknown}; valid={sorted(MODEL_SPECS)}")
    if not model_ids:
        raise ValueError("at least one model id is required")
    return model_ids


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_folds(feature_dir: Path) -> list[int]:
    folds = []
    for path in feature_dir.glob("fold_*_row_manifest.json"):
        parts = path.stem.split("_")
        if len(parts) >= 3 and parts[0] == "fold" and parts[1].isdigit():
            folds.append(int(parts[1]))
    if not folds:
        raise FileNotFoundError(f"no fold_*_row_manifest.json files under {feature_dir}")
    missing = sorted(set(range(max(folds) + 1)) - set(folds))
    if missing:
        raise ValueError(f"non-contiguous fold manifests under {feature_dir}: missing {missing}")
    return sorted(folds)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def rounded_score(values: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(values, SCORE_MIN, SCORE_MAX)).astype(int)


def qwk(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    value = cohen_kappa_score(
        rounded_score(y_true),
        rounded_score(y_pred),
        labels=list(range(SCORE_MIN, SCORE_MAX + 1)),
        weights="quadratic",
    )
    if value is None or math.isnan(float(value)):
        return 0.0
    return float(value)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "qwk": qwk(y_true, y_pred),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
    }


def score_band(score: float) -> str:
    if score < 10:
        return "low_0_9"
    if score < 20:
        return "mid_10_19"
    return "high_20_30"


def load_training_config(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    if args.config == "all" or not config_path.exists():
        return {
            "cycle_id": args.cycle_id,
            "kanban_task_id": args.kanban_task_id,
            "seed": args.seed,
            "target_name": TARGET_NAME,
            "models": {model_id: MODEL_SPECS[model_id] for model_id in args.models},
        }

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if "models" not in loaded:
        selected = loaded.get("model_id") or loaded.get("model") or config_path.stem
        loaded["models"] = {selected: MODEL_SPECS[selected]}
    return loaded


def enforce_feature_provenance(feature_dir: Path) -> dict[str, Any]:
    provenance_path = feature_dir / "feature_provenance_manifest.json"
    provenance = load_json(provenance_path)
    label_side_count = int(provenance.get("label_side_feature_count", -1))
    if label_side_count != 0:
        raise RuntimeError(
            f"label-side features are blocked by Hard Rule #9: count={label_side_count}"
        )
    for feature in provenance.get("features", []):
        if feature.get("label_side") is True or feature.get("provenance") == "label-side":
            raise RuntimeError(f"label-side feature blocked: {feature.get('name')}")
    return provenance


def load_label(label_dir: Path, relative_path: str, essay_id: str) -> dict[str, Any]:
    label_path = label_dir / relative_path
    label = load_json(label_path)
    target = label.get("score", {}).get(TARGET_NAME)
    if target is None:
        raise ValueError(f"missing {TARGET_NAME} in {label_path}")
    essay_type = label.get("rubric", {}).get("essay_type", "unknown")
    grade_group = label.get("student", {}).get("student_grade_group", "unknown")
    rater_scores = label.get("score", {}).get("essay_scoreT", [])
    return {
        "essay_id": essay_id,
        "relative_path": relative_path,
        "label_path": str(label_path),
        TARGET_NAME: float(target),
        "essay_type": essay_type,
        "student_grade_group": grade_group,
        "score_band": score_band(float(target)),
        "rater_score_count": len(rater_scores) if isinstance(rater_scores, list) else 0,
    }


def extract_model_text(doc: dict[str, Any], path: Path) -> tuple[str, str]:
    """Return only model-visible essay text from supported source/label layouts."""
    essay_id = doc.get("essay_id")
    raw_text = doc.get("essay_txt")
    if isinstance(essay_id, str) and isinstance(raw_text, str) and raw_text.strip():
        return essay_id, raw_text

    info = doc.get("info") if isinstance(doc.get("info"), dict) else {}
    essay_id = info.get("essay_id")
    paragraph = doc.get("paragraph", [])
    paragraph_texts = [
        item.get("paragraph_txt", "")
        for item in paragraph
        if isinstance(item, dict) and isinstance(item.get("paragraph_txt"), str)
    ] if isinstance(paragraph, list) else []
    raw_text = "\n".join(paragraph_texts)
    if isinstance(essay_id, str) and raw_text.strip():
        return essay_id, raw_text

    raise ValueError(f"missing model-visible essay text in {path}")


def normalize_text(raw_text: str) -> str:
    text = raw_text.replace(SENTENCE_SEPARATOR, " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_model_text(label_dir: Path, relative_path: str, essay_id: str) -> str:
    label_path = label_dir / relative_path
    doc = load_json(label_path)
    source_essay_id, raw_text = extract_model_text(doc, label_path)
    if source_essay_id != essay_id:
        raise ValueError(
            f"essay_id mismatch for {relative_path}: manifest={essay_id} source={source_essay_id}"
        )
    return normalize_text(raw_text)


def load_fold_data(
    fold: int, feature_dir: Path, label_dir: Path
) -> tuple[sparse.csr_matrix, pd.DataFrame, dict[str, Any]]:
    row_manifest = load_json(feature_dir / f"fold_{fold}_row_manifest.json")
    matrix = sparse.load_npz(feature_dir / f"X_{fold}.npz").tocsr()
    if matrix.shape[0] != len(row_manifest["rows"]):
        raise ValueError(f"fold {fold}: matrix rows do not match row manifest")

    label_rows = [
        load_label(label_dir, row["relative_path"], row["essay_id"])
        | {"row_index": int(row["row_index"]), "partition": row["partition"]}
        for row in row_manifest["rows"]
    ]
    labels = pd.DataFrame(label_rows).sort_values("row_index").reset_index(drop=True)
    return matrix, labels, row_manifest


def select_features(
    model_id: str, matrix: sparse.csr_matrix, row_manifest: dict[str, Any]
) -> sparse.csr_matrix | None:
    blocks = row_manifest["feature_blocks"]
    if model_id == "M1":
        return None
    if model_id == "M2":
        numeric = blocks["derived_numeric"]
        length_index = numeric["names"].index("essay_char_count")
        column = int(numeric["start"]) + length_index
        return matrix[:, column : column + 1]
    if model_id == "M3":
        start = int(blocks["word_tfidf"]["start"])
        end = int(blocks["char_tfidf"]["end"])
        return matrix[:, start:end]
    if model_id == "M4":
        return matrix
    raise ValueError(f"unknown model_id: {model_id}")


def build_estimator(
    model_id: str, seed: int, hparams: dict[str, Any] | None = None
) -> Any:
    spec = MODEL_SPECS[model_id]
    if model_id == "M1":
        return DummyRegressor(strategy="mean")
    if model_id in {"M2", "M3"}:
        return make_pipeline(
            StandardScaler(with_mean=False),
            RidgeCV(alphas=spec["alphas"], scoring="neg_mean_absolute_error", cv=3),
        )
    if model_id == "M4":
        params = dict(spec["params"])
        if hparams:
            params.update(hparams)
        return LGBMRegressor(random_state=seed, **params)
    raise ValueError(f"unknown model_id: {model_id}")


def estimator_params(estimator: Any, model_id: str) -> dict[str, Any]:
    if model_id in {"M2", "M3"}:
        ridge = estimator.named_steps["ridgecv"]
        return {"selected_alpha": float(ridge.alpha_)}
    if model_id == "M4":
        return estimator.get_params()
    return {}


def segment_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for segment_name in ["essay_type", "student_grade_group", "score_band"]:
        for segment_value, group in predictions.groupby(segment_name, dropna=False):
            y_true = group[TARGET_NAME].to_numpy(dtype=float)
            y_pred = group["prediction"].to_numpy(dtype=float)
            metrics = regression_metrics(y_true, y_pred)
            rows.append(
                {
                    "segment": segment_name,
                    "value": segment_value,
                    "n": int(len(group)),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def mlflow_log_common(
    model_id: str,
    fold: int,
    args: argparse.Namespace,
    config_hash: str,
    split_hash: str,
    feature_provenance_hash: str,
    train_metrics: dict[str, float],
    valid_metrics: dict[str, float],
    train_time_seconds: float,
    feature_set: str,
    artifact_paths: list[Path],
    estimator_extra_params: dict[str, Any],
) -> str:
    spec = MODEL_SPECS[model_id]
    run_name = f"{model_id}_{spec['model_name']}_fold_{fold}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags(
            {
                "cycle_id": str(args.cycle_id),
                "kanban_task_id": args.kanban_task_id,
                "feature_provenance": feature_provenance_hash,
                "dataset_version": str(Path(args.label_dir).parent),
                "split_version": split_hash,
                "rubric_version": "label_json_embedded_rubrics_not_model_inputs",
                "fold": str(fold),
                "model_id": model_id,
            }
        )
        mlflow.log_params(
            {
                "model_type": spec["model_type"],
                "model_name": spec["model_name"],
                "feature_set": feature_set,
                "target_name": TARGET_NAME,
                "split_version": split_hash,
                "random_seed": args.seed,
                "config_hash": config_hash,
                **estimator_extra_params,
            }
        )
        mlflow.log_metrics(
            {
                "train_qwk": train_metrics["qwk"],
                "train_mae": train_metrics["mae"],
                "train_rmse": train_metrics["rmse"],
                "qwk": valid_metrics["qwk"],
                "mae": valid_metrics["mae"],
                "rmse": valid_metrics["rmse"],
                "train_valid_qwk_gap": train_metrics["qwk"] - valid_metrics["qwk"],
                "train_valid_qwk_gap_abs": abs(train_metrics["qwk"] - valid_metrics["qwk"]),
                "train_time_seconds": train_time_seconds,
            }
        )
        for artifact_path in artifact_paths:
            mlflow.log_artifact(str(artifact_path), artifact_path=f"{model_id}/fold_{fold}")
        return run.info.run_id


def train_model(
    model_id: str,
    args: argparse.Namespace,
    output_dir: Path,
    config_hash: str,
    split_hash: str,
    feature_provenance_hash: str,
    folds: list[int],
) -> dict[str, Any]:
    model_dir = output_dir / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    per_fold_metrics: list[dict[str, Any]] = []
    all_valid_predictions: list[pd.DataFrame] = []
    run_ids: dict[str, str] = {}
    hparams_override = load_hparams_override(getattr(args, "hparams_json", None))

    for fold in folds:
        matrix, labels, row_manifest = load_fold_data(
            fold=fold, feature_dir=Path(args.feature_dir), label_dir=Path(args.label_dir)
        )
        train_mask = labels["partition"] == "train"
        valid_mask = labels["partition"] == "valid"
        y_train = labels.loc[train_mask, TARGET_NAME].to_numpy(dtype=float)
        y_valid = labels.loc[valid_mask, TARGET_NAME].to_numpy(dtype=float)
        selected = select_features(model_id, matrix, row_manifest)
        # build_estimator ignores hparams for M1-M3; only M4 honours the override.
        estimator = build_estimator(model_id, args.seed, hparams=hparams_override)

        start = time.perf_counter()
        if selected is None:
            estimator.fit(np.zeros((len(y_train), 1)), y_train)
            train_pred = estimator.predict(np.zeros((len(y_train), 1)))
            valid_pred = estimator.predict(np.zeros((len(y_valid), 1)))
        else:
            x_train = selected[train_mask.to_numpy()]
            x_valid = selected[valid_mask.to_numpy()]
            estimator.fit(x_train, y_train)
            train_pred = estimator.predict(x_train)
            valid_pred = estimator.predict(x_valid)
        train_time_seconds = float(time.perf_counter() - start)

        train_metrics = regression_metrics(y_train, np.asarray(train_pred, dtype=float))
        valid_metrics = regression_metrics(y_valid, np.asarray(valid_pred, dtype=float))
        gap_abs = abs(train_metrics["qwk"] - valid_metrics["qwk"])
        warnings = []
        if gap_abs > 0.10:
            warnings.append(
                "train_valid_qwk_gap_abs_gt_0.10"
            )

        valid_predictions = labels.loc[valid_mask].copy()
        valid_predictions.insert(0, "fold", fold)
        valid_predictions.insert(0, "model_id", model_id)
        valid_predictions["prediction"] = np.clip(valid_pred, SCORE_MIN, SCORE_MAX)
        valid_predictions["prediction_rounded"] = rounded_score(
            valid_predictions["prediction"].to_numpy(dtype=float)
        )
        valid_predictions["mlflow_run_id"] = ""
        valid_predictions = valid_predictions[
            [
                "model_id",
                "fold",
                "essay_id",
                "relative_path",
                "partition",
                TARGET_NAME,
                "prediction",
                "prediction_rounded",
                "essay_type",
                "student_grade_group",
                "score_band",
                "mlflow_run_id",
            ]
        ]

        fold_predictions_path = model_dir / f"fold_{fold}_predictions.csv"
        fold_metrics_path = model_dir / f"fold_{fold}_metrics.json"
        fold_segment_path = model_dir / f"fold_{fold}_segment_metrics.csv"
        valid_predictions.to_csv(fold_predictions_path, index=False)
        segment_metrics(valid_predictions).to_csv(fold_segment_path, index=False)

        fold_metrics = {
            "model_id": model_id,
            "model_name": MODEL_SPECS[model_id]["model_name"],
            "fold": fold,
            "train_n": int(train_mask.sum()),
            "valid_n": int(valid_mask.sum()),
            "feature_set": MODEL_SPECS[model_id]["feature_set"],
            "assumption": MODEL_SPECS[model_id]["assumption"],
            "train_time_seconds": train_time_seconds,
            "train_metrics": train_metrics,
            "valid_metrics": valid_metrics,
            "train_valid_qwk_gap": train_metrics["qwk"] - valid_metrics["qwk"],
            "train_valid_qwk_gap_abs": gap_abs,
            "prediction_distribution": {
                "train_mean": float(np.mean(train_pred)),
                "train_std": float(np.std(train_pred)),
                "valid_mean": float(np.mean(valid_pred)),
                "valid_std": float(np.std(valid_pred)),
                "valid_min": float(np.min(valid_pred)),
                "valid_max": float(np.max(valid_pred)),
            },
            "warnings": warnings,
        }
        write_json(fold_metrics_path, fold_metrics)

        run_id = mlflow_log_common(
            model_id=model_id,
            fold=fold,
            args=args,
            config_hash=config_hash,
            split_hash=split_hash,
            feature_provenance_hash=feature_provenance_hash,
            train_metrics=train_metrics,
            valid_metrics=valid_metrics,
            train_time_seconds=train_time_seconds,
            feature_set=MODEL_SPECS[model_id]["feature_set"],
            artifact_paths=[fold_predictions_path, fold_metrics_path, fold_segment_path],
            estimator_extra_params=estimator_params(estimator, model_id),
        )
        run_ids[str(fold)] = run_id
        valid_predictions["mlflow_run_id"] = run_id
        valid_predictions.to_csv(fold_predictions_path, index=False)
        all_valid_predictions.append(valid_predictions)
        fold_metrics["mlflow_run_id"] = run_id
        write_json(fold_metrics_path, fold_metrics)
        per_fold_metrics.append(fold_metrics)

    predictions = pd.concat(all_valid_predictions, ignore_index=True)
    predictions_path = model_dir / "predictions.csv"
    metrics_path = model_dir / "metrics_per_fold.json"
    segment_path = model_dir / "segment_metrics.csv"
    manifest_path = model_dir / "manifest.json"
    predictions.to_csv(predictions_path, index=False)
    write_json(metrics_path, per_fold_metrics)
    segment_metrics(predictions).to_csv(segment_path, index=False)

    overall_metrics = regression_metrics(
        predictions[TARGET_NAME].to_numpy(dtype=float),
        predictions["prediction"].to_numpy(dtype=float),
    )
    manifest = {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "model_name": MODEL_SPECS[model_id]["model_name"],
        "target_name": TARGET_NAME,
        "seed": args.seed,
        "config_hash_algorithm": "sha256",
        "config_hash": config_hash,
        "feature_provenance_hash": feature_provenance_hash,
        "split_manifest_sha256": split_hash,
        "mlflow_experiment": args.experiment_name,
        "mlflow_run_ids": run_ids,
        "folds": folds,
        "fold_count": len(folds),
        "valid_prediction_count": int(len(predictions)),
        "overall_valid_metrics": overall_metrics,
        "artifact_paths": {
            "predictions": str(predictions_path),
            "metrics_per_fold": str(metrics_path),
            "segment_metrics": str(segment_path),
            "manifest": str(manifest_path),
        },
        "package_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": package_version("scipy"),
            "scikit-learn": package_version("scikit-learn"),
            "lightgbm": package_version("lightgbm"),
            "mlflow": package_version("mlflow"),
            "pyyaml": package_version("PyYAML"),
        },
        "verification_command": (
            f"python3 -c \"import json, pandas as pd; "
            f"m=json.load(open('{manifest_path}')); "
            f"p=pd.read_csv('{predictions_path}'); "
            f"assert len(m['mlflow_run_ids']) == m['fold_count']; "
            f"assert len(p) == m['valid_prediction_count']\""
        ),
    }
    write_json(manifest_path, manifest)
    return manifest


def train_transformer_model(
    model_id: str,
    args: argparse.Namespace,
    output_dir: Path,
    config_hash: str,
    split_hash: str,
    feature_provenance_hash: str,
    folds: list[int],
) -> dict[str, Any]:
    if model_id != "M5":
        raise ValueError(f"train_transformer_model only supports M5, got {model_id}")
    if not args.model:
        raise ValueError("--model is required when training M5")

    from pipelines.train_transformer import train_transformer

    model_dir = output_dir / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    per_fold_metrics: list[dict[str, Any]] = []
    all_valid_predictions: list[pd.DataFrame] = []
    run_ids: dict[str, str] = {}
    hparams = dict(MODEL_SPECS[model_id]["default_hparams"])
    override = load_hparams_override(getattr(args, "hparams_json", None))
    if override:
        hparams.update(override)

    for fold in folds:
        _, labels, _ = load_fold_data(
            fold=fold, feature_dir=Path(args.feature_dir), label_dir=Path(args.label_dir)
        )
        labels["text"] = [
            load_model_text(Path(args.label_dir), row.relative_path, row.essay_id)
            for row in labels.itertuples(index=False)
        ]

        train_mask = labels["partition"] == "train"
        valid_mask = labels["partition"] == "valid"
        train_df = labels.loc[train_mask, ["text", TARGET_NAME]].rename(
            columns={TARGET_NAME: "score"}
        )
        valid_df = labels.loc[valid_mask, ["text", TARGET_NAME]].rename(
            columns={TARGET_NAME: "score"}
        )
        y_train = train_df["score"].to_numpy(dtype=float)
        y_valid = valid_df["score"].to_numpy(dtype=float)

        fold_output_dir = model_dir / f"fold_{fold}_trainer"
        start = time.perf_counter()
        transformer_result = train_transformer(
            train_df=train_df,
            valid_df=valid_df,
            hparams=hparams,
            output_dir=str(fold_output_dir),
            text_col="text",
            label_col="score",
            model_name=args.model,
            tokenizer_name=args.model,
            max_length=256,
            seed=args.seed,
        )
        train_time_seconds = float(time.perf_counter() - start)
        train_pred = np.asarray(transformer_result["train_predictions"], dtype=float)
        valid_pred = np.asarray(transformer_result["valid_predictions"], dtype=float)

        train_metrics = regression_metrics(y_train, train_pred)
        valid_metrics = regression_metrics(y_valid, valid_pred)
        gap_abs = abs(train_metrics["qwk"] - valid_metrics["qwk"])
        warnings = []
        if gap_abs > 0.10:
            warnings.append("train_valid_qwk_gap_abs_gt_0.10")

        valid_predictions = labels.loc[valid_mask].copy()
        valid_predictions.insert(0, "fold", fold)
        valid_predictions.insert(0, "model_id", model_id)
        valid_predictions["prediction"] = np.clip(valid_pred, SCORE_MIN, SCORE_MAX)
        valid_predictions["prediction_rounded"] = rounded_score(
            valid_predictions["prediction"].to_numpy(dtype=float)
        )
        valid_predictions["mlflow_run_id"] = ""
        valid_predictions = valid_predictions[
            [
                "model_id",
                "fold",
                "essay_id",
                "relative_path",
                "partition",
                TARGET_NAME,
                "prediction",
                "prediction_rounded",
                "essay_type",
                "student_grade_group",
                "score_band",
                "mlflow_run_id",
            ]
        ]

        fold_predictions_path = model_dir / f"fold_{fold}_predictions.csv"
        fold_metrics_path = model_dir / f"fold_{fold}_metrics.json"
        fold_segment_path = model_dir / f"fold_{fold}_segment_metrics.csv"
        fold_run_path = model_dir / f"M5_run_fold_{fold}.json"
        valid_predictions.to_csv(fold_predictions_path, index=False)
        segment_metrics(valid_predictions).to_csv(fold_segment_path, index=False)

        fold_metrics = {
            "model_id": model_id,
            "model_name": MODEL_SPECS[model_id]["model_name"],
            "hf_model": args.model,
            "fold": fold,
            "train_n": int(train_mask.sum()),
            "valid_n": int(valid_mask.sum()),
            "feature_set": MODEL_SPECS[model_id]["feature_set"],
            "assumption": MODEL_SPECS[model_id]["assumption"],
            "hparams": hparams,
            "train_time_seconds": train_time_seconds,
            "train_metrics": train_metrics,
            "valid_metrics": valid_metrics,
            "train_valid_qwk_gap": train_metrics["qwk"] - valid_metrics["qwk"],
            "train_valid_qwk_gap_abs": gap_abs,
            "prediction_distribution": {
                "train_mean": float(np.mean(train_pred)),
                "train_std": float(np.std(train_pred)),
                "valid_mean": float(np.mean(valid_pred)),
                "valid_std": float(np.std(valid_pred)),
                "valid_min": float(np.min(valid_pred)),
                "valid_max": float(np.max(valid_pred)),
            },
            "model_path": transformer_result["model_path"],
            "warnings": warnings,
        }
        write_json(fold_metrics_path, fold_metrics)

        run_id = mlflow_log_common(
            model_id=model_id,
            fold=fold,
            args=args,
            config_hash=config_hash,
            split_hash=split_hash,
            feature_provenance_hash=feature_provenance_hash,
            train_metrics=train_metrics,
            valid_metrics=valid_metrics,
            train_time_seconds=train_time_seconds,
            feature_set=MODEL_SPECS[model_id]["feature_set"],
            artifact_paths=[fold_predictions_path, fold_metrics_path, fold_segment_path],
            estimator_extra_params={"hf_model": args.model, **hparams},
        )
        run_ids[str(fold)] = run_id
        valid_predictions["mlflow_run_id"] = run_id
        valid_predictions.to_csv(fold_predictions_path, index=False)
        fold_metrics["mlflow_run_id"] = run_id
        write_json(fold_metrics_path, fold_metrics)
        write_json(
            fold_run_path,
            {
                "model_id": model_id,
                "fold": fold,
                "mlflow_run_id": run_id,
                "metrics_path": str(fold_metrics_path),
                "predictions_path": str(fold_predictions_path),
                "model_path": transformer_result["model_path"],
            },
        )
        all_valid_predictions.append(valid_predictions)
        per_fold_metrics.append(fold_metrics)

    predictions = pd.concat(all_valid_predictions, ignore_index=True)
    predictions_path = model_dir / "predictions.csv"
    metrics_path = model_dir / "metrics_per_fold.json"
    segment_path = model_dir / "segment_metrics.csv"
    manifest_path = model_dir / "manifest.json"
    predictions.to_csv(predictions_path, index=False)
    write_json(metrics_path, per_fold_metrics)
    segment_metrics(predictions).to_csv(segment_path, index=False)

    overall_metrics = regression_metrics(
        predictions[TARGET_NAME].to_numpy(dtype=float),
        predictions["prediction"].to_numpy(dtype=float),
    )
    manifest = {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "model_name": MODEL_SPECS[model_id]["model_name"],
        "hf_model": args.model,
        "target_name": TARGET_NAME,
        "seed": args.seed,
        "config_hash_algorithm": "sha256",
        "config_hash": config_hash,
        "feature_provenance_hash": feature_provenance_hash,
        "split_manifest_sha256": split_hash,
        "mlflow_experiment": args.experiment_name,
        "mlflow_run_ids": run_ids,
        "folds": folds,
        "fold_count": len(folds),
        "valid_prediction_count": int(len(predictions)),
        "overall_valid_metrics": overall_metrics,
        "artifact_paths": {
            "predictions": str(predictions_path),
            "metrics_per_fold": str(metrics_path),
            "segment_metrics": str(segment_path),
            "manifest": str(manifest_path),
            "fold_run_json_glob": str(model_dir / "M5_run_fold_*.json"),
        },
        "package_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": package_version("scipy"),
            "scikit-learn": package_version("scikit-learn"),
            "transformers": package_version("transformers"),
            "torch": package_version("torch"),
            "mlflow": package_version("mlflow"),
            "pyyaml": package_version("PyYAML"),
        },
        "verification_command": (
            f"python3 -c \"import json, pandas as pd; "
            f"m=json.load(open('{manifest_path}')); "
            f"p=pd.read_csv('{predictions_path}'); "
            f"assert len(m['mlflow_run_ids']) == m['fold_count']; "
            f"assert len(p) == m['valid_prediction_count']\""
        ),
    }
    write_json(manifest_path, manifest)
    return manifest


def build_summary(
    output_dir: Path, manifests: list[dict[str, Any]], cycle_id: str
) -> Path:
    path = output_dir / "model_training_summary.md"
    metrics_by_model = {
        manifest["model_id"]: manifest["overall_valid_metrics"] for manifest in manifests
    }
    gate_status = "PASS_DIAGNOSTIC"
    gate_details: list[str] = []
    ordered_present = [model_id for model_id in ["M1", "M2", "M3", "M4", "M5", "M6"] if model_id in metrics_by_model]
    for previous, challenger in zip(ordered_present, ordered_present[1:]):
        if metrics_by_model[previous]["qwk"] <= metrics_by_model[challenger]["qwk"]:
            gate_details.append(
                f"{previous} <= {challenger}: PASS "
                f"({metrics_by_model[previous]['qwk']:.4f} <= {metrics_by_model[challenger]['qwk']:.4f})"
            )
        else:
            gate_status = "FAIL_DIAGNOSTIC_REQUIRES_EVAL_CI"
            gate_details.append(
                f"{previous} <= {challenger}: FAIL "
                f"({metrics_by_model[previous]['qwk']:.4f} > {metrics_by_model[challenger]['qwk']:.4f})"
            )

    lines = [
        f"# Cycle {cycle_id} Model Training Summary",
        "",
        f"Created at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overall Valid Metrics",
        "",
        "| Model | Assumption | QWK | MAE | RMSE | Train seconds | Prediction distribution | Warnings | MLflow runs |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for manifest in manifests:
        metrics = manifest["overall_valid_metrics"]
        per_fold_metrics = load_json(Path(manifest["artifact_paths"]["metrics_per_fold"]))
        predictions = pd.read_csv(manifest["artifact_paths"]["predictions"])
        train_seconds = sum(float(row["train_time_seconds"]) for row in per_fold_metrics)
        warning_count = sum(len(row.get("warnings", [])) for row in per_fold_metrics)
        pred_dist = (
            f"mean={predictions['prediction'].mean():.3f}, "
            f"std={predictions['prediction'].std(ddof=0):.3f}, "
            f"min={predictions['prediction'].min():.3f}, "
            f"max={predictions['prediction'].max():.3f}"
        )
        lines.append(
            "| {model_id} {model_name} | {assumption} | {qwk:.4f} | {mae:.4f} | {rmse:.4f} | {train_seconds:.3f} | {pred_dist} | {warning_count} | {runs} |".format(
                model_id=manifest["model_id"],
                model_name=manifest["model_name"],
                assumption=MODEL_SPECS[manifest["model_id"]]["assumption"],
                qwk=metrics["qwk"],
                mae=metrics["mae"],
                rmse=metrics["rmse"],
                train_seconds=train_seconds,
                pred_dist=pred_dist,
                warning_count=warning_count,
                runs=len(manifest["mlflow_run_ids"]),
            )
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            f"Point-estimate monotonicity diagnostic: {gate_status}. Phase 2 hard acceptance is deferred to EVAL bootstrap CI (`model_lower95 > prev_model_upper95`).",
            "",
            *[f"- {detail}" for detail in gate_details],
            "",
            "Feature provenance gate: PASS, label_side_feature_count=0.",
            "Train/valid QWK gap warnings are recorded per fold in metrics_per_fold.json.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_existing_model_manifests(output_dir: Path, replacing: set[str]) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for manifest_path in sorted(output_dir.glob("M*/manifest.json")):
        manifest = load_json(manifest_path)
        if manifest.get("model_id") not in replacing:
            manifests.append(manifest)
    return manifests


def ordered_model_manifests(manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {model_id: index for index, model_id in enumerate(["M1", "M2", "M3", "M4", "M5", "M6"])}
    return sorted(
        manifests,
        key=lambda manifest: order.get(str(manifest.get("model_id")), 999),
    )


def main() -> int:
    args = parse_args()
    model_ids = normalize_model_ids(args.models)
    args.models = model_ids
    output_dir = Path(args.output_dir)
    feature_dir = Path(args.feature_dir)
    split_dir = Path(args.split_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not feature_dir.is_dir():
        raise FileNotFoundError(feature_dir)
    if not split_dir.is_dir():
        raise FileNotFoundError(split_dir)

    provenance = enforce_feature_provenance(feature_dir)
    folds = discover_folds(feature_dir)
    training_config = load_training_config(args)
    config_path = output_dir / "training_config.yaml"
    write_yaml(config_path, training_config)
    config_hash = sha256_file(config_path)
    split_hash = sha256_file(split_dir / "split_manifest.yaml")
    feature_provenance_hash = sha256_file(feature_dir / "feature_provenance_manifest.json")

    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment(args.experiment_name)

    manifests = load_existing_model_manifests(output_dir, replacing=set(model_ids))
    for model_id in model_ids:
        if model_id in {"M1", "M2", "M3", "M4"}:
            manifests.append(
                train_model(
                    model_id=model_id,
                    args=args,
                    output_dir=output_dir,
                    config_hash=config_hash,
                    split_hash=split_hash,
                    feature_provenance_hash=feature_provenance_hash,
                    folds=folds,
                )
            )
        elif model_id == "M5":
            manifests.append(
                train_transformer_model(
                    model_id=model_id,
                    args=args,
                    output_dir=output_dir,
                    config_hash=config_hash,
                    split_hash=split_hash,
                    feature_provenance_hash=feature_provenance_hash,
                    folds=folds,
                )
            )
        else:
            raise NotImplementedError(
                "M6 is implemented in pipelines.train_ensemble and is scheduled for the HPO/ensemble task"
            )
    manifests = ordered_model_manifests(manifests)

    summary_path = build_summary(output_dir, manifests, args.cycle_id)
    index_manifest = {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "config_path": str(config_path),
        "config_hash": config_hash,
        "feature_provenance_manifest_path": str(feature_dir / "feature_provenance_manifest.json"),
        "feature_provenance_manifest_sha256": feature_provenance_hash,
        "feature_provenance_label_side_count": provenance.get("label_side_feature_count"),
        "split_manifest_path": str(split_dir / "split_manifest.yaml"),
        "split_manifest_sha256": split_hash,
        "folds": folds,
        "fold_count": len(folds),
        "summary_path": str(summary_path),
        "model_manifests": [manifest["artifact_paths"]["manifest"] for manifest in manifests],
        "verification_commands": [
            (
                "python3 -c \"import mlflow; "
                f"mlflow.set_tracking_uri('{args.mlflow_uri}'); "
                f"exp=mlflow.get_experiment_by_name('{args.experiment_name}'); "
                "assert exp is not None\""
            ),
            (
                "python3 -c \"from pathlib import Path; import pandas as pd; "
                f"paths=sorted(Path('{output_dir}').glob('M*/predictions.csv')); "
                "assert paths and all(len(pd.read_csv(path)) == 5003 for path in paths)\""
            ),
        ],
    }
    write_json(output_dir / "manifest.json", index_manifest)

    print(f"wrote {config_path}")
    print(f"wrote {summary_path}")
    for manifest in manifests:
        metrics = manifest["overall_valid_metrics"]
        print(
            "{model_id}: qwk={qwk:.4f} mae={mae:.4f} rmse={rmse:.4f} runs={runs}".format(
                model_id=manifest["model_id"],
                qwk=metrics["qwk"],
                mae=metrics["mae"],
                rmse=metrics["rmse"],
                runs=len(manifest["mlflow_run_ids"]),
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
