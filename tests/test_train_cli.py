"""Tests for pipelines.train CLI extensions (--model, --hpo-trials, --cycle-id str, M5/M6 dispatch)."""

import json
from pathlib import Path

import pytest

from pipelines.train import MODEL_SPECS, load_hparams_override, parse_args


class TestCliArgs:
    def test_accepts_model_arg(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["train.py", "--models", "M5", "--model", "klue/roberta-small", "--cycle-id", "M1"],
        )
        args = parse_args()
        assert args.model == "klue/roberta-small"

    def test_accepts_hpo_trials_arg(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["train.py", "--models", "M5", "--hpo-trials", "30", "--cycle-id", "M1"],
        )
        args = parse_args()
        assert args.hpo_trials == 30

    def test_cycle_id_accepts_string(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["train.py", "--models", "M5", "--cycle-id", "M2"],
        )
        args = parse_args()
        assert args.cycle_id == "M2"


class TestModelSpecs:
    def test_m5_klue_roberta_in_specs(self):
        assert "M5" in MODEL_SPECS
        spec = MODEL_SPECS["M5"]
        assert spec["model_type"] == "KLUE-RoBERTa"
        assert spec["feature_set"] == "raw_text"
        assert "assumption" in spec

    def test_m6_ensemble_in_specs(self):
        assert "M6" in MODEL_SPECS
        spec = MODEL_SPECS["M6"]
        assert spec["model_type"] == "RidgeStackingEnsemble"
        assert "M4" in spec["depends_on"]
        assert "M5" in spec["depends_on"]


class TestHparamsJsonArg:
    """--hparams-json wires HPO run_hpo.py best_params into final training."""

    def test_arg_parses(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "train.py",
                "--models",
                "M5",
                "--cycle-id",
                "M1",
                "--hparams-json",
                "workspace/cycle_M1/hpo/study_summary_M5.json",
            ],
        )
        args = parse_args()
        assert args.hparams_json == "workspace/cycle_M1/hpo/study_summary_M5.json"

    def test_arg_default_none(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["train.py", "--models", "M5", "--cycle-id", "M1"])
        args = parse_args()
        assert args.hparams_json is None


class TestLoadHparamsOverride:
    def test_returns_none_for_none_path(self):
        assert load_hparams_override(None) is None

    def test_returns_none_for_empty_string(self):
        assert load_hparams_override("") is None

    def test_loads_best_params_key(self, tmp_path):
        payload = {
            "model": "M5",
            "best_params": {"learning_rate": 3e-5, "num_train_epochs": 3},
            "best_value": 2.5,
        }
        path = tmp_path / "study_summary_M5.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = load_hparams_override(str(path))
        assert result == {"learning_rate": 3e-5, "num_train_epochs": 3}

    def test_loads_top_level_dict_as_hparams(self, tmp_path):
        payload = {"learning_rate": 0.05, "num_leaves": 31}
        path = tmp_path / "hparams.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = load_hparams_override(str(path))
        assert result == payload

    def test_raises_on_non_dict_payload(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="must be a dict"):
            load_hparams_override(str(path))
