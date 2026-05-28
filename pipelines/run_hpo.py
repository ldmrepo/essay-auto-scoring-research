"""HPO entry point with MLflow nested-run integration (Hard Rule #12).

Wraps `pipelines.hpo.run_hpo_study` with:
- MLflow parent run per HPO session
- Each Optuna trial → MLflow nested run (params + metrics logged)
- Parent run logs best_params, best_value, study summary
- Hard Rule #12: n_trials >= 30 hard-block

Search spaces (Cycle M1 spec, task t_13e1eaaa body):
- M4 LightGBM: learning_rate, num_leaves, min_child_samples, reg_alpha
- M5 KLUE-RoBERTa: learning_rate(log[1e-5,5e-5]), batch_size{8,16,32}, epochs{2..5},
                   weight_decay, warmup_ratio
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import mlflow
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

MIN_TRIALS = 30  # Hard Rule #12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optuna HPO with MLflow nested runs.")
    parser.add_argument("--model", choices=["M4", "M5"], required=True)
    parser.add_argument("--n-trials", type=int, required=True)
    parser.add_argument("--cycle-id", required=True, help="e.g. 'M1', 'M2'.")
    parser.add_argument("--study-name", required=True)
    parser.add_argument("--storage", required=True, help="e.g. sqlite:///optuna.db")
    parser.add_argument("--mlflow-uri", required=True)
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--kanban-task-id", required=True)
    parser.add_argument("--split-dir", required=True)
    parser.add_argument("--feature-dir", required=True)
    parser.add_argument("--label-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sampler-seed", type=int, default=42)
    parser.add_argument("--hf-model", default="klue/roberta-small", help="M5 only.")
    return parser.parse_args()


def enforce_min_trials(n_trials: int) -> None:
    if n_trials < MIN_TRIALS:
        raise ValueError(
            f"Hard Rule #12 violation: n_trials={n_trials} < {MIN_TRIALS}. "
            "HPO study must accumulate at least 30 trials."
        )


def run_with_mlflow_parent(
    *,
    objective_factory: Callable[[], Callable[[optuna.Trial], float]],
    n_trials: int,
    study_name: str,
    storage: str,
    sampler_seed: int,
    parent_tags: dict[str, str],
    parent_params: dict[str, Any],
    direction: str = "minimize",
) -> dict[str, Any]:
    """Run an HPO study with MLflow parent + nested trial runs.

    objective_factory returns the per-trial objective. The caller's objective should
    log trial-specific params/metrics into the active MLflow run (which run_with_mlflow_parent
    sets up as a nested run for each trial).
    """
    raw_objective = objective_factory()

    with mlflow.start_run() as parent_run:
        for k, v in parent_tags.items():
            mlflow.set_tag(k, v)
        for k, v in parent_params.items():
            mlflow.log_param(k, v)
        mlflow.log_param("n_trials_requested", n_trials)
        mlflow.log_param("sampler_seed", sampler_seed)
        mlflow.log_param("optuna_sampler", "TPESampler")
        mlflow.log_param("optuna_pruner", "MedianPruner")

        def wrapped_objective(trial: optuna.Trial) -> float:
            with mlflow.start_run(nested=True) as nested:
                mlflow.set_tag("trial_number", str(trial.number))
                value = raw_objective(trial)
                mlflow.log_metric("objective_value", float(value))
                for pname, pval in trial.params.items():
                    mlflow.log_param(pname, pval)
                return value

        sampler = TPESampler(seed=sampler_seed)
        pruner = MedianPruner(n_startup_trials=5)
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            sampler=sampler,
            pruner=pruner,
            direction=direction,
            load_if_exists=True,
        )
        study.optimize(wrapped_objective, n_trials=n_trials, show_progress_bar=False)

        for pname, pval in study.best_params.items():
            mlflow.log_param(f"best_{pname}", pval)
        mlflow.log_metric("best_value", float(study.best_value))
        mlflow.log_metric("n_trials_completed", float(len(study.trials)))

        return {
            "best_params": dict(study.best_params),
            "best_value": float(study.best_value),
            "n_trials_completed": len(study.trials),
            "study_name": study_name,
            "parent_run_id": parent_run.info.run_id,
        }


def build_m4_objective_factory(
    *,
    feature_dir: Path,
    label_dir: Path,
    seed: int,
) -> Callable[[], Callable[[optuna.Trial], float]]:
    """Returns a factory that builds an M4 LightGBM objective.

    Uses train.py helpers (discover_folds, load_fold_data, select_features,
    build_estimator) so HPO trials run the same code path as final M4 training.
    Search space per task body: learning_rate, num_leaves, min_child_samples, reg_alpha.
    """

    def factory() -> Callable[[optuna.Trial], float]:
        import numpy as np

        from pipelines.train import (
            TARGET_NAME,
            build_estimator,
            discover_folds,
            load_fold_data,
            select_features,
        )

        folds = discover_folds(feature_dir)

        def objective(trial: optuna.Trial) -> float:
            hparams = {
                "learning_rate": trial.suggest_float("learning_rate", 1e-3, 1e-1, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 7, 127),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            }
            fold_maes: list[float] = []
            for fold in folds:
                matrix, labels, row_manifest = load_fold_data(
                    fold=fold, feature_dir=feature_dir, label_dir=label_dir
                )
                train_mask = (labels["partition"] == "train").to_numpy()
                valid_mask = (labels["partition"] == "valid").to_numpy()
                y_train = labels.loc[train_mask, TARGET_NAME].to_numpy(dtype=float)
                y_valid = labels.loc[valid_mask, TARGET_NAME].to_numpy(dtype=float)
                selected = select_features("M4", matrix, row_manifest)
                x_train = selected[train_mask]
                x_valid = selected[valid_mask]
                estimator = build_estimator("M4", seed, hparams=hparams)
                estimator.fit(x_train, y_train)
                valid_pred = np.asarray(estimator.predict(x_valid), dtype=float)
                fold_maes.append(float(np.abs(y_valid - valid_pred).mean()))
            return float(sum(fold_maes) / len(fold_maes))

        return objective

    return factory


def build_m5_objective_factory(
    *,
    feature_dir: Path,
    label_dir: Path,
    hf_model: str,
    seed: int,
    output_root: Path,
) -> Callable[[], Callable[[optuna.Trial], float]]:
    """Returns a factory that builds an M5 KLUE-RoBERTa objective.

    Reuses train.py load_fold_data + load_model_text to assemble raw text per fold
    (same code path as full M5 training). Search space per task body:
    learning_rate(log[1e-5,5e-5]), batch_size{8,16,32}, epochs[2,5], weight_decay,
    warmup_ratio. Returns mean valid MAE.
    """

    def factory() -> Callable[[optuna.Trial], float]:
        from pipelines.train import (
            TARGET_NAME,
            discover_folds,
            load_fold_data,
            load_model_text,
        )
        from pipelines.train_transformer import train_transformer

        folds = discover_folds(feature_dir)

        def objective(trial: optuna.Trial) -> float:
            hparams = {
                "learning_rate": trial.suggest_float("learning_rate", 1e-5, 5e-5, log=True),
                "per_device_train_batch_size": trial.suggest_categorical(
                    "per_device_train_batch_size", [8, 16, 32]
                ),
                "num_train_epochs": trial.suggest_int("num_train_epochs", 2, 5),
                "weight_decay": trial.suggest_float("weight_decay", 0.0, 0.3),
                "warmup_ratio": trial.suggest_float("warmup_ratio", 0.0, 0.2),
            }
            fold_maes: list[float] = []
            for fold in folds:
                _, labels, _ = load_fold_data(
                    fold=fold, feature_dir=feature_dir, label_dir=label_dir
                )
                labels["text"] = [
                    load_model_text(label_dir, row.relative_path, row.essay_id)
                    for row in labels.itertuples(index=False)
                ]
                train_df = labels.loc[labels["partition"] == "train", ["text", TARGET_NAME]].rename(
                    columns={TARGET_NAME: "score"}
                )
                valid_df = labels.loc[labels["partition"] == "valid", ["text", TARGET_NAME]].rename(
                    columns={TARGET_NAME: "score"}
                )
                result = train_transformer(
                    train_df=train_df,
                    valid_df=valid_df,
                    hparams=hparams,
                    model_name=hf_model,
                    tokenizer_name=hf_model,
                    output_dir=str(output_root / f"trial_{trial.number}_fold_{fold}"),
                    max_length=256,
                    text_col="text",
                    label_col="score",
                    seed=seed,
                )
                fold_maes.append(float(result["valid_mae"]))
            return float(sum(fold_maes) / len(fold_maes))

        return objective

    return factory


def main() -> int:
    args = parse_args()
    enforce_min_trials(args.n_trials)

    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment(args.experiment_name)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parent_tags = {
        "cycle_id": str(args.cycle_id),
        "kanban_task_id": args.kanban_task_id,
        "model_id": args.model,
        "study_name": args.study_name,
    }
    parent_params = {
        "model": args.model,
        "n_trials_requested": args.n_trials,
        "study_name": args.study_name,
        "storage": args.storage,
    }

    if args.model == "M4":
        factory = build_m4_objective_factory(
            feature_dir=Path(args.feature_dir),
            label_dir=Path(args.label_dir),
            seed=args.sampler_seed,
        )
        parent_params["search_space"] = (
            "learning_rate log[1e-3,1e-1], num_leaves[7,127], "
            "min_child_samples[5,50], reg_alpha log[1e-3,10]"
        )
    else:  # M5
        factory = build_m5_objective_factory(
            feature_dir=Path(args.feature_dir),
            label_dir=Path(args.label_dir),
            hf_model=args.hf_model,
            seed=args.sampler_seed,
            output_root=output_dir / "trials",
        )
        parent_params["search_space"] = (
            "learning_rate log[1e-5,5e-5], batch_size{8,16,32}, epochs[2,5], "
            "weight_decay[0,0.3], warmup_ratio[0,0.2]"
        )
        parent_params["hf_model"] = args.hf_model

    result = run_with_mlflow_parent(
        objective_factory=factory,
        n_trials=args.n_trials,
        study_name=args.study_name,
        storage=args.storage,
        sampler_seed=args.sampler_seed,
        parent_tags=parent_tags,
        parent_params=parent_params,
    )

    summary_path = output_dir / f"study_summary_{args.model}.json"
    summary_path.write_text(
        json.dumps(
            {
                "model": args.model,
                "study_name": args.study_name,
                "storage": args.storage,
                "n_trials_completed": result["n_trials_completed"],
                "best_value": result["best_value"],
                "best_params": result["best_params"],
                "parent_run_id": result["parent_run_id"],
                "cycle_id": args.cycle_id,
                "kanban_task_id": args.kanban_task_id,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"HPO complete: best_value={result['best_value']:.6f}, summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
