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
    save_model: bool = True,
    rubric_json_col: Optional[str] = None,
) -> dict[str, Any]:
    """Fine-tune a transformer regression model. Returns metrics + predictions + model_path.

    Phase 3 multi-task wire-up (P3-W3): `rubric_json_col`이 지정되고 dataframe에 해당 컬럼이
    있으면 학습 진입 직전 `validate_rubric_for_phase3` 사전 검증. drift essay 발견 시 `RuntimeError`.
    Phase 2 호환을 위해 기본은 비활성 (rubric_json_col=None).
    """
    # P3-W3 fix (R1-NNF1 + R1-REG-H1 운영 보강): Phase 3 학습 직전 사전 검증
    if rubric_json_col is not None:
        from pipelines.extract_5k import validate_rubric_for_phase3
        for df_name, df in (("train_df", train_df), ("valid_df", valid_df)):
            if rubric_json_col not in df.columns:
                raise ValueError(
                    f"train_transformer: rubric_json_col='{rubric_json_col}' not in {df_name}. "
                    "Phase 3 multi-task 학습 시 rubric JSON dict 컬럼 필수."
                )
            drift = []
            for idx, rubric_doc in enumerate(df[rubric_json_col]):
                ok, reason = validate_rubric_for_phase3(rubric_doc)
                if not ok:
                    drift.append((idx, reason))
                    if len(drift) >= 3:
                        break
            if drift:
                drift_msg = "; ".join(f"row {i}: {r}" for i, r in drift[:3])
                raise RuntimeError(
                    f"train_transformer: rubric spec drift in {df_name} — {drift_msg}. "
                    "extract_5k --validate-rubric로 사전 skip 필수 (Hard Rule #15)."
                )
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

    # Predict on train/valid for the same train-vs-valid diagnostics used by
    # the CPU baselines.
    train_output = trainer.predict(train_ds)
    train_predictions = np.asarray(train_output.predictions).squeeze(-1)
    train_labels = np.asarray([train_ds[i]["labels"].item() for i in range(len(train_ds))])

    valid_output = trainer.predict(valid_ds)
    valid_predictions = np.asarray(valid_output.predictions).squeeze(-1)
    valid_labels = np.asarray([valid_ds[i]["labels"].item() for i in range(len(valid_ds))])

    train_mae = float(mean_absolute_error(train_labels, train_predictions))
    train_rmse = float(np.sqrt(mean_squared_error(train_labels, train_predictions)))
    train_loss = float(np.mean((train_predictions - train_labels) ** 2))
    valid_mae = float(mean_absolute_error(valid_labels, valid_predictions))
    valid_rmse = float(np.sqrt(mean_squared_error(valid_labels, valid_predictions)))
    valid_loss = float(np.mean((valid_predictions - valid_labels) ** 2))

    model_path = output_dir_p / "model"
    if save_model:
        trainer.save_model(str(model_path))

    return {
        "train_loss": train_loss,
        "train_mae": train_mae,
        "train_rmse": train_rmse,
        "train_predictions": train_predictions,
        "valid_loss": valid_loss,
        "valid_mae": valid_mae,
        "valid_rmse": valid_rmse,
        "valid_predictions": valid_predictions,
        "model_path": str(model_path) if save_model else None,
        "hparams": hparams,
    }
