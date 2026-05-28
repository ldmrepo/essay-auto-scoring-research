"""Tests for pipelines.run_hpo — HPO CLI entry point with MLflow nested run integration.

Hard Rule #12: 각 trial을 MLflow nested run으로 등록 + n_trials >= 30 hard-block.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import mlflow
import pytest

from pipelines.run_hpo import (
    enforce_min_trials,
    parse_args,
    run_with_mlflow_parent,
)


class TestCliArgs:
    def test_required_args_parse(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "run_hpo.py",
                "--model",
                "M4",
                "--n-trials",
                "30",
                "--cycle-id",
                "M1",
                "--study-name",
                "cycle_M1_M4",
                "--storage",
                "sqlite:///optuna.db",
                "--mlflow-uri",
                "sqlite:///mlflow.db",
                "--experiment-name",
                "cycle_M1",
                "--kanban-task-id",
                "t_13e1eaaa",
                "--split-dir",
                "workspace/cycle_M1/splits",
                "--feature-dir",
                "workspace/cycle_M1/features",
                "--label-dir",
                "dataset/sample_5k",
                "--output-dir",
                "workspace/cycle_M1/hpo",
            ],
        )
        args = parse_args()
        assert args.model == "M4"
        assert args.n_trials == 30
        assert args.cycle_id == "M1"
        assert args.study_name == "cycle_M1_M4"
        assert args.kanban_task_id == "t_13e1eaaa"

    def test_model_choices_restricted_to_m4_m5(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "run_hpo.py",
                "--model",
                "M3",  # not allowed
                "--n-trials",
                "30",
                "--cycle-id",
                "M1",
                "--study-name",
                "x",
                "--storage",
                "sqlite:///x.db",
                "--mlflow-uri",
                "sqlite:///m.db",
                "--experiment-name",
                "x",
                "--kanban-task-id",
                "t_x",
                "--split-dir",
                "x",
                "--feature-dir",
                "x",
                "--label-dir",
                "x",
                "--output-dir",
                "x",
            ],
        )
        with pytest.raises(SystemExit):
            parse_args()


class TestEnforceMinTrials:
    def test_passes_when_n_trials_30(self):
        enforce_min_trials(30)  # no raise

    def test_passes_when_n_trials_above_30(self):
        enforce_min_trials(50)

    def test_raises_when_below_30(self):
        with pytest.raises(ValueError, match="Hard Rule #12"):
            enforce_min_trials(29)

    def test_raises_when_zero(self):
        with pytest.raises(ValueError, match="Hard Rule #12"):
            enforce_min_trials(0)


def _quadratic_objective_factory(trial_counter: dict[str, int]):
    """f(x) = (x - 3)^2. Counts trial invocations for nested-run verification."""

    def objective(trial):
        trial_counter["count"] = trial_counter.get("count", 0) + 1
        x = trial.suggest_float("x", -10.0, 10.0)
        # Each trial logs inside nested run, set by the caller
        active = mlflow.active_run()
        if active is not None:
            mlflow.log_metric("x_value", x)
        return (x - 3.0) ** 2

    return objective


class TestRunWithMlflowParent:
    def test_creates_parent_run_and_nested_trial_runs(self, tmp_path, monkeypatch):
        mlflow_db = tmp_path / "mlflow.db"
        optuna_db = tmp_path / "optuna.db"
        mlflow.set_tracking_uri(f"sqlite:///{mlflow_db}")
        mlflow.set_experiment("test_exp")

        counter: dict[str, int] = {}
        objective = _quadratic_objective_factory(counter)

        result = run_with_mlflow_parent(
            objective_factory=lambda: objective,
            n_trials=5,
            study_name="test_parent_nested",
            storage=f"sqlite:///{optuna_db}",
            sampler_seed=42,
            parent_tags={
                "cycle_id": "M1",
                "kanban_task_id": "t_test",
                "model_id": "M4_test",
            },
            parent_params={"search_space": "x in [-10, 10]"},
        )

        assert counter["count"] == 5
        assert "best_params" in result
        assert "best_value" in result
        assert "parent_run_id" in result
        assert result["n_trials_completed"] == 5

        # Verify parent run + 5 nested trial runs exist in MLflow
        client = mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name("test_exp")
        runs = client.search_runs(experiment_ids=[experiment.experiment_id])
        # 1 parent + 5 nested = 6 runs total
        assert len(runs) == 6
        parent_runs = [r for r in runs if r.data.tags.get("mlflow.parentRunId") is None]
        nested_runs = [r for r in runs if r.data.tags.get("mlflow.parentRunId") is not None]
        assert len(parent_runs) == 1
        assert len(nested_runs) == 5
        # All nested runs should point to the parent
        parent_id = parent_runs[0].info.run_id
        for r in nested_runs:
            assert r.data.tags["mlflow.parentRunId"] == parent_id

    def test_parent_run_logs_best_params_and_study_summary(self, tmp_path):
        mlflow_db = tmp_path / "mlflow.db"
        optuna_db = tmp_path / "optuna.db"
        mlflow.set_tracking_uri(f"sqlite:///{mlflow_db}")
        mlflow.set_experiment("test_summary")

        counter: dict[str, int] = {}
        objective = _quadratic_objective_factory(counter)

        result = run_with_mlflow_parent(
            objective_factory=lambda: objective,
            n_trials=3,
            study_name="test_summary_study",
            storage=f"sqlite:///{optuna_db}",
            sampler_seed=42,
            parent_tags={"cycle_id": "M1", "kanban_task_id": "t_x", "model_id": "M4"},
            parent_params={"search_space": "x"},
        )

        client = mlflow.tracking.MlflowClient()
        parent = client.get_run(result["parent_run_id"])
        # best_params + best_value logged
        assert "best_value" in parent.data.metrics
        assert "n_trials_completed" in parent.data.metrics
        assert parent.data.metrics["n_trials_completed"] == 3.0
        # search_space param echoed
        assert parent.data.params.get("search_space") == "x"
        # tags inherited
        assert parent.data.tags.get("cycle_id") == "M1"
        assert parent.data.tags.get("kanban_task_id") == "t_x"
        assert parent.data.tags.get("model_id") == "M4"
