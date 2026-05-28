"""Tests for pipelines.train_transformer — RoBERTa fine-tune smoke."""

from pathlib import Path

import numpy as np
import pytest

from pipelines.train_transformer import train_transformer


def _synthetic_df():
    """20 essay rows with scores 0~30."""
    import pandas as pd

    rng = np.random.default_rng(42)
    texts = [f"미래에 대한 짧은 글짓기 샘플 {i}." for i in range(20)]
    scores = rng.uniform(0, 30, size=20).tolist()
    return pd.DataFrame({"text": texts, "score": scores})


def _tiny_random_model_init():
    """Build a tiny random-init RoBERTa regressor (no internet — uses already-cached
    klue/bert-base tokenizer's vocab_size + pad_token_id to avoid embedding index OOB)."""
    from transformers import AutoTokenizer, RobertaConfig, RobertaForSequenceClassification

    tok = AutoTokenizer.from_pretrained("klue/bert-base")
    config = RobertaConfig(
        vocab_size=tok.vocab_size,
        hidden_size=16,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=32,
        max_position_embeddings=64,
        pad_token_id=tok.pad_token_id,
        type_vocab_size=2,  # BERT tokenizer emits token_type_ids in {0,1}
        num_labels=1,  # regression head
        problem_type="regression",
    )
    return RobertaForSequenceClassification(config)


class TestTrainTransformer:
    def test_smoke_runs_one_step_and_returns_metrics(self, tmp_path):
        df = _synthetic_df()
        result = train_transformer(
            train_df=df.iloc[:15],
            valid_df=df.iloc[15:],
            hparams={
                "learning_rate": 1e-4,
                "per_device_train_batch_size": 4,
                "num_train_epochs": 1,
                "weight_decay": 0.01,
                "warmup_ratio": 0.0,
            },
            model_name=None,  # use model_init instead
            model_init=_tiny_random_model_init,
            tokenizer_name="klue/bert-base",  # bundled with transformers, smaller cache than roberta
            output_dir=str(tmp_path / "tf_run"),
            max_length=32,
            text_col="text",
            label_col="score",
        )
        assert "valid_loss" in result
        assert "valid_mae" in result
        assert "model_path" in result
        assert isinstance(result["valid_loss"], float)
        assert Path(result["model_path"]).exists()

    def test_predict_returns_ndarray_with_correct_length(self, tmp_path):
        df = _synthetic_df()
        result = train_transformer(
            train_df=df.iloc[:15],
            valid_df=df.iloc[15:],
            hparams={
                "learning_rate": 1e-4,
                "per_device_train_batch_size": 4,
                "num_train_epochs": 1,
                "weight_decay": 0.01,
                "warmup_ratio": 0.0,
            },
            model_name=None,
            model_init=_tiny_random_model_init,
            tokenizer_name="klue/bert-base",
            output_dir=str(tmp_path / "tf_run"),
            max_length=32,
            text_col="text",
            label_col="score",
        )
        assert "valid_predictions" in result
        assert len(result["valid_predictions"]) == 5

    def test_records_hparams_in_result(self, tmp_path):
        df = _synthetic_df()
        hparams = {
            "learning_rate": 2e-4,
            "per_device_train_batch_size": 2,
            "num_train_epochs": 1,
            "weight_decay": 0.05,
            "warmup_ratio": 0.0,
        }
        result = train_transformer(
            train_df=df.iloc[:15],
            valid_df=df.iloc[15:],
            hparams=hparams,
            model_name=None,
            model_init=_tiny_random_model_init,
            tokenizer_name="klue/bert-base",
            output_dir=str(tmp_path / "tf_run"),
            max_length=32,
            text_col="text",
            label_col="score",
        )
        assert result["hparams"] == hparams

    def test_can_skip_model_artifact_for_hpo_trials(self, tmp_path):
        df = _synthetic_df()
        result = train_transformer(
            train_df=df.iloc[:15],
            valid_df=df.iloc[15:],
            hparams={
                "learning_rate": 1e-4,
                "per_device_train_batch_size": 4,
                "num_train_epochs": 1,
                "weight_decay": 0.01,
                "warmup_ratio": 0.0,
            },
            model_name=None,
            model_init=_tiny_random_model_init,
            tokenizer_name="klue/bert-base",
            output_dir=str(tmp_path / "tf_hpo_trial"),
            max_length=32,
            text_col="text",
            label_col="score",
            save_model=False,
        )

        assert result["model_path"] is None
        assert not (tmp_path / "tf_hpo_trial" / "model").exists()
