"""KLUE-RoBERTa regression head fine-tune (M5).

Built on HuggingFace Trainer for stability. The function accepts either a
pretrained `model_name` (HF Hub or local cache) or a `model_init` callable
(for synthetic tiny-model unit tests).

Real Phase 2 runs: `model_name="klue/roberta-small"` with HF_HOME pre-cached.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np


def train_transformer(
    train_df,
    valid_df,
    hparams: dict[str, Any],
    output_dir: str,
    text_col: str = "text",
    label_col: str = "score",
    model_name: Optional[str] = None,
    model_init: Optional[Callable] = None,
    tokenizer_name: Optional[str] = None,
    max_length: int = 256,
    seed: int = 42,
) -> dict[str, Any]:
    """Fine-tune a transformer regression model. Returns metrics + predictions + model_path."""
    import torch
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    if model_name is None and model_init is None:
        raise ValueError("Provide either model_name or model_init.")

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name or model_name)

    def _to_features(df):
        encs = tokenizer(
            df[text_col].tolist(),
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors=None,
        )
        encs["labels"] = [float(x) for x in df[label_col].tolist()]
        return encs

    class _DictDataset(torch.utils.data.Dataset):
        def __init__(self, encs):
            self.encs = encs
            self.n = len(encs["labels"])

        def __len__(self):
            return self.n

        def __getitem__(self, i):
            return {
                k: (
                    torch.tensor(v[i])
                    if k != "labels"
                    else torch.tensor(v[i], dtype=torch.float32)
                )
                for k, v in self.encs.items()
            }

    train_ds = _DictDataset(_to_features(train_df))
    valid_ds = _DictDataset(_to_features(valid_df))

    if model_init is None:
        def model_init():
            return AutoModelForSequenceClassification.from_pretrained(
                model_name, num_labels=1, problem_type="regression"
            )

    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(output_dir_p),
        per_device_train_batch_size=int(hparams.get("per_device_train_batch_size", 16)),
        per_device_eval_batch_size=int(hparams.get("per_device_train_batch_size", 16)),
        learning_rate=float(hparams.get("learning_rate", 2e-5)),
        num_train_epochs=int(hparams.get("num_train_epochs", 3)),
        weight_decay=float(hparams.get("weight_decay", 0.01)),
        warmup_ratio=float(hparams.get("warmup_ratio", 0.0)),
        seed=seed,
        report_to=[],
        logging_steps=10,
        save_strategy="no",
        eval_strategy="no",
        disable_tqdm=True,
    )

    trainer = Trainer(
        model_init=model_init,
        args=args,
        train_dataset=train_ds,
        eval_dataset=valid_ds,
    )
    trainer.train()

    # Predict on valid
    valid_output = trainer.predict(valid_ds)
    valid_predictions = np.asarray(valid_output.predictions).squeeze(-1)
    valid_labels = np.asarray([valid_ds[i]["labels"].item() for i in range(len(valid_ds))])

    valid_mae = float(mean_absolute_error(valid_labels, valid_predictions))
    valid_rmse = float(np.sqrt(mean_squared_error(valid_labels, valid_predictions)))
    valid_loss = float(np.mean((valid_predictions - valid_labels) ** 2))

    # Save model artifact
    model_path = output_dir_p / "model"
    trainer.save_model(str(model_path))

    return {
        "valid_loss": valid_loss,
        "valid_mae": valid_mae,
        "valid_rmse": valid_rmse,
        "valid_predictions": valid_predictions,
        "model_path": str(model_path),
        "hparams": hparams,
    }
