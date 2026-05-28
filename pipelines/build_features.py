#!/usr/bin/env python3
"""Build leakage-free text features and Phase 3 target contracts for each split fold.

The builder reads only model-visible essay text: Phase 1 source
``essay_txt`` or Phase 2 label-only ``paragraph[].paragraph_txt``. Audit-table
label-side columns, student.location, and target scores are not model inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from pipelines.extract_5k import validate_rubric_for_phase3
except ModuleNotFoundError:  # direct `python3 pipelines/build_features.py`
    from extract_5k import validate_rubric_for_phase3


SENTENCE_SEPARATOR = "#@문장구분#"
DEFAULT_WORD_MAX_FEATURES = 5000
DEFAULT_CHAR_MAX_FEATURES = 10000
W_OVERALL_DEFAULT = 0.5
PHASE3_LABEL_COLUMNS = [
    "target_exp",
    "target_org",
    "target_cont",
    "target_overall_norm",
]
PHASE3_WEIGHT_COLUMNS = [
    "w_exp",
    "w_org",
    "w_cont",
    "w_overall",
]
PHASE3_TARGET_SCHEMA_PATHS = {
    "target_exp": [
        "score.essay_scoreT_detail.essay_scoreT_exp",
        "rubric.expression_weight.exp_grammar",
        "rubric.expression_weight.exp_vocab",
        "rubric.expression_weight.exp_style",
    ],
    "target_org": [
        "score.essay_scoreT_detail.essay_scoreT_org",
        "rubric.organization_weight.org_paragraph",
        "rubric.organization_weight.org_essay",
        "rubric.organization_weight.org_coherence",
        "rubric.organization_weight.org_quantity",
    ],
    "target_cont": [
        "score.essay_scoreT_detail.essay_scoreT_cont",
        "rubric.content_weight.con_clearance",
        "rubric.content_weight.con_description",
        "rubric.content_weight.con_novelty",
        "rubric.content_weight.con_prompt",
    ],
    "target_overall_norm": ["score.essay_scoreT_avg / 10.0"],
    "target_overall_raw": ["score.essay_scoreT_avg"],
    "w_exp": ["rubric.expression_weight.exp"],
    "w_org": ["rubric.organization_weight.org"],
    "w_cont": ["rubric.content_weight.con"],
    "w_overall": [
        f"rubric.overall_weight if present else W_OVERALL_DEFAULT={W_OVERALL_DEFAULT}"
    ],
}
NUMERIC_FEATURES = [
    "essay_char_count",
    "essay_word_token_count",
    "sentence_delimiter_count",
    "sentence_count_from_delimiter",
    "avg_sentence_char_count",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build per-fold train-only TF-IDF features from model-visible essay text."
    )
    parser.add_argument(
        "--audit-table",
        default=None,
        help=(
            "Optional audit_table_no_raw_text.csv used only to verify split/source "
            "identity and text hashes. Label-side audit columns are not model inputs."
        ),
    )
    parser.add_argument("--source-dir", default="dataset/sample/원천데이터")
    parser.add_argument("--split-dir", default="workspace/cycle_1/splits")
    parser.add_argument("--output-dir", default="workspace/cycle_1/features")
    parser.add_argument("--cycle-id", default="1")
    parser.add_argument("--kanban-task-id", default="t_17813ef2")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--word-max-features", type=int, default=DEFAULT_WORD_MAX_FEATURES)
    parser.add_argument("--char-max-features", type=int, default=DEFAULT_CHAR_MAX_FEATURES)
    parser.add_argument(
        "--phase3-target-contract",
        choices=["auto", "required", "off"],
        default="auto",
        help=(
            "Emit Phase 3 labels/macro_weights artifacts for M5. auto emits when "
            "source JSON rows contain score+rubric, required fails if they do not, "
            "and off skips legacy target-contract output."
        ),
    )
    return parser.parse_args()


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


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def resolve_source_path(source_dir: Path, relative_path: str) -> Path:
    candidates = [
        source_dir / relative_path,
        source_dir / "라벨링데이터" / relative_path,
        source_dir / "원천데이터" / relative_path,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    tried = [candidate.as_posix() for candidate in candidates]
    raise FileNotFoundError(f"missing source JSON for {relative_path}; tried={tried}")


def load_audit_index(audit_table: Path) -> dict[str, dict[str, str]]:
    """Load non-text audit metadata for consistency checks only."""
    source_required_columns = {
        "relative_path",
        "has_source",
        "essay_id_source",
        "essay_txt_present",
        "source_sha256",
    }
    label_only_required_columns = {
        "relative_path",
        "has_label",
        "essay_id_label",
        "paragraph_txt_present",
        "paragraph_text_sha256",
    }
    forbidden_raw_text_columns = {
        "essay_txt",
        "raw_text",
        "normalized_text",
        "paragraph",
        "correction",
        "essay_prompt",
    }
    with audit_table.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        has_source_schema = source_required_columns <= columns
        has_label_only_schema = label_only_required_columns <= columns
        if not has_source_schema and not has_label_only_schema:
            source_missing = sorted(source_required_columns - columns)
            label_missing = sorted(label_only_required_columns - columns)
            raise ValueError(
                "audit table missing required columns for both schemas: "
                f"source_missing={source_missing}; label_only_missing={label_missing}"
            )
        raw_text_columns = forbidden_raw_text_columns & columns
        if raw_text_columns:
            raise ValueError(
                f"audit table contains forbidden raw-text columns: {sorted(raw_text_columns)}"
            )

        index: dict[str, dict[str, str]] = {}
        for row in reader:
            relative_path = row["relative_path"]
            if relative_path in index:
                raise ValueError(f"duplicate relative_path in audit table: {relative_path}")
            index[relative_path] = row
    return index


def extract_model_text(doc: dict[str, Any], path: Path) -> tuple[str, str, str]:
    """Return (essay_id, model-visible essay text, source field) from supported layouts."""
    essay_id = doc.get("essay_id")
    raw_text = doc.get("essay_txt")
    if isinstance(essay_id, str) and isinstance(raw_text, str) and raw_text.strip():
        return essay_id, raw_text, "essay_txt"

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
        return essay_id, raw_text, "paragraph[].paragraph_txt"

    raise ValueError(f"missing model-visible essay text in {path}")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _weighted_rater_average(scores_per_rater: list[list[float]], weights: list[float]) -> float:
    denominator = sum(float(weight) for weight in weights)
    if denominator <= 0:
        raise ValueError("rubric sub-weight sum must be > 0")
    per_rater = []
    for rater_scores in scores_per_rater:
        per_rater.append(
            sum(float(score) * float(weight) for score, weight in zip(rater_scores, weights))
            / denominator
        )
    return float(sum(per_rater) / len(per_rater))


def compute_rubric_targets(essay_json: dict[str, Any]) -> dict[str, float]:
    """Strict Phase 3 target and loss-weight builder.

    The implementation mirrors docs § 7.2 and intentionally calls
    validate_rubric_for_phase3 first so schema drift fails before target arrays
    are emitted.
    """
    ok, reason = validate_rubric_for_phase3(essay_json)
    if not ok:
        essay_id = essay_json.get("info", {}).get("essay_id", "UNKNOWN")
        raise ValueError(
            "compute_rubric_targets: Phase 3 rubric validation failed for "
            f"essay_id={essay_id}: {reason}"
        )

    rubric = essay_json["rubric"]
    detail = essay_json["score"]["essay_scoreT_detail"]
    exp_sub_w = [
        float(rubric["expression_weight"][key])
        for key in ["exp_grammar", "exp_vocab", "exp_style"]
    ]
    org_sub_w = [
        float(rubric["organization_weight"][key])
        for key in ["org_paragraph", "org_essay", "org_coherence", "org_quantity"]
    ]
    cont_sub_w = [
        float(rubric["content_weight"][key])
        for key in ["con_clearance", "con_description", "con_novelty", "con_prompt"]
    ]

    if "overall_weight" in rubric:
        if not _is_number(rubric["overall_weight"]):
            essay_id = essay_json.get("info", {}).get("essay_id", "UNKNOWN")
            raise ValueError(
                "compute_rubric_targets: rubric.overall_weight non-numeric for "
                f"essay_id={essay_id}"
            )
        w_overall = float(rubric["overall_weight"])
    else:
        w_overall = W_OVERALL_DEFAULT

    overall_raw = float(essay_json["score"]["essay_scoreT_avg"])
    return {
        "target_exp": _weighted_rater_average(detail["essay_scoreT_exp"], exp_sub_w),
        "target_org": _weighted_rater_average(detail["essay_scoreT_org"], org_sub_w),
        "target_cont": _weighted_rater_average(detail["essay_scoreT_cont"], cont_sub_w),
        "target_overall_norm": overall_raw / 10.0,
        "target_overall_raw": overall_raw,
        "w_exp": float(rubric["expression_weight"]["exp"]),
        "w_org": float(rubric["organization_weight"]["org"]),
        "w_cont": float(rubric["content_weight"]["con"]),
        "w_overall": w_overall,
    }


def normalize_text(raw_text: str) -> str:
    text = raw_text.replace(SENTENCE_SEPARATOR, " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_token_count(raw_text: str) -> int:
    text = normalize_text(raw_text)
    if not text:
        return 0
    return len(text.split())


def numeric_features(raw_text: str) -> list[float]:
    sentence_delimiter_count = raw_text.count(SENTENCE_SEPARATOR)
    sentence_parts = [
        re.sub(r"\s+", " ", part).strip()
        for part in raw_text.split(SENTENCE_SEPARATOR)
        if part.strip()
    ]
    sentence_count = len(sentence_parts)
    avg_sentence_chars = (
        sum(len(part) for part in sentence_parts) / sentence_count
        if sentence_count
        else 0.0
    )
    return [
        float(len(raw_text)),
        float(word_token_count(raw_text)),
        float(sentence_delimiter_count),
        float(sentence_count),
        float(avg_sentence_chars),
    ]


def read_source_row(
    source_dir: Path,
    item: dict[str, Any],
    audit_index: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    relative_path = item["relative_path"]

    audit_row = audit_index.get(relative_path) if audit_index is not None else None
    if audit_index is not None and audit_row is None:
        raise ValueError(f"split item missing from audit table: {relative_path}")
    if audit_row is not None:
        if "has_source" in audit_row:
            if audit_row.get("has_source") != "True":
                raise ValueError(f"audit table marks source missing: {relative_path}")
            if audit_row.get("essay_txt_present") != "True":
                raise ValueError(f"audit table marks essay_txt missing: {relative_path}")
            audit_essay_id = audit_row.get("essay_id_source")
            audit_text_hash = audit_row.get("source_sha256")
        else:
            if audit_row.get("has_label") != "True":
                raise ValueError(f"audit table marks label missing: {relative_path}")
            if audit_row.get("paragraph_txt_present") != "True":
                raise ValueError(f"audit table marks paragraph text missing: {relative_path}")
            audit_essay_id = audit_row.get("essay_id_label")
            audit_text_hash = audit_row.get("paragraph_text_sha256")
        if audit_essay_id != item.get("essay_id"):
            raise ValueError(
                "audit/split essay_id mismatch for "
                f"{relative_path}: audit={audit_essay_id} split={item.get('essay_id')}"
            )
    else:
        audit_text_hash = None

    source_path = resolve_source_path(source_dir, relative_path)
    source = load_json(source_path)
    essay_id, raw_text, text_source_field = extract_model_text(source, source_path)
    if essay_id != item.get("essay_id"):
        raise ValueError(
            f"essay_id mismatch for {relative_path}: split={item.get('essay_id')} source={essay_id}"
        )
    source_sha256 = sha256_text(raw_text)
    if audit_row is not None and audit_text_hash != source_sha256:
        raise ValueError(
            "audit/source hash mismatch for "
            f"{relative_path}: audit={audit_text_hash} source={source_sha256}"
        )
    phase3_targets = (
        compute_rubric_targets(source)
        if "rubric" in source or "score" in source
        else None
    )
    return {
        "essay_id": essay_id,
        "relative_path": relative_path,
        "source_sha256": source_sha256,
        "text_source_field": text_source_field,
        "raw_text": raw_text,
        "normalized_text": normalize_text(raw_text),
        "numeric": numeric_features(raw_text),
        "phase3_targets": phase3_targets,
    }


def should_emit_phase3_targets(
    rows: list[dict[str, Any]],
    phase3_target_contract: str,
    fold: int,
) -> bool:
    if phase3_target_contract == "off":
        return False

    present = [row.get("phase3_targets") is not None for row in rows]
    if all(present):
        return True
    if any(present):
        missing = [
            row["relative_path"]
            for row, has_targets in zip(rows, present)
            if not has_targets
        ][:10]
        raise ValueError(
            "mixed Phase 3 target availability in fold "
            f"{fold}; first missing rows: {missing}"
        )
    if phase3_target_contract == "required":
        raise ValueError(
            f"Phase 3 target contract required but no score/rubric rows found in fold {fold}"
        )
    return False


def _array_stats(values: np.ndarray, columns: list[str]) -> dict[str, dict[str, float]]:
    return {
        column: {
            "min": float(values[:, idx].min()),
            "max": float(values[:, idx].max()),
            "mean": float(values[:, idx].mean()),
        }
        for idx, column in enumerate(columns)
    }


def build_phase3_target_artifacts(
    fold: int,
    rows: list[dict[str, Any]],
    output_dir: Path,
    train_n: int,
    valid_n: int,
) -> dict[str, Any]:
    labels = np.array(
        [
            [row["phase3_targets"][column] for column in PHASE3_LABEL_COLUMNS]
            for row in rows
        ],
        dtype=np.float32,
    )
    macro_weights = np.array(
        [
            [row["phase3_targets"][column] for column in PHASE3_WEIGHT_COLUMNS]
            for row in rows
        ],
        dtype=np.float32,
    )
    target_overall_raw = np.array(
        [row["phase3_targets"]["target_overall_raw"] for row in rows],
        dtype=np.float32,
    )
    expected_shape = (len(rows), 4)
    if labels.shape != expected_shape:
        raise RuntimeError(f"labels shape mismatch for fold {fold}: {labels.shape}")
    if macro_weights.shape != expected_shape:
        raise RuntimeError(
            f"macro_weights shape mismatch for fold {fold}: {macro_weights.shape}"
        )

    target_npz_path = output_dir / f"fold_{fold}_phase3_targets.npz"
    np.savez_compressed(
        target_npz_path,
        labels=labels,
        macro_weights=macro_weights,
        target_overall_raw=target_overall_raw,
        label_columns=np.array(PHASE3_LABEL_COLUMNS),
        macro_weight_columns=np.array(PHASE3_WEIGHT_COLUMNS),
    )

    target_row_manifest = {
        "fold": fold,
        "row_order": "train_then_valid",
        "target_artifact_path": str(target_npz_path),
        "label_columns": PHASE3_LABEL_COLUMNS,
        "macro_weight_columns": PHASE3_WEIGHT_COLUMNS,
        "labels_shape": list(labels.shape),
        "macro_weights_shape": list(macro_weights.shape),
        "target_overall_raw_shape": [int(target_overall_raw.shape[0])],
        "text_contract": {
            "field": "text",
            "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
            "stored_in_manifest": False,
            "hash_field": "source_sha256",
        },
        "prompt_text": {
            "enabled": False,
            "included": False,
            "reason": "requires explicit feature flag and provenance approval",
        },
        "rows": [
            {
                "row_index": idx,
                "partition": "train" if idx < train_n else "valid",
                "essay_id": row["essay_id"],
                "relative_path": row["relative_path"],
                "text_source_field": row["text_source_field"],
                "source_sha256": row["source_sha256"],
            }
            for idx, row in enumerate(rows)
        ],
    }
    target_row_manifest_path = output_dir / f"fold_{fold}_phase3_transformer_rows.json"
    write_json(target_row_manifest_path, target_row_manifest)

    return {
        "fold": fold,
        "target_artifact_path": str(target_npz_path),
        "target_artifact_sha256": sha256_file(target_npz_path),
        "target_row_manifest_path": str(target_row_manifest_path),
        "target_row_manifest_sha256": sha256_file(target_row_manifest_path),
        "row_order": "train_then_valid",
        "train_n": train_n,
        "valid_n": valid_n,
        "labels_shape": [int(labels.shape[0]), int(labels.shape[1])],
        "macro_weights_shape": [
            int(macro_weights.shape[0]),
            int(macro_weights.shape[1]),
        ],
        "target_overall_raw_shape": [int(target_overall_raw.shape[0])],
        "label_columns": PHASE3_LABEL_COLUMNS,
        "macro_weight_columns": PHASE3_WEIGHT_COLUMNS,
        "label_stats": _array_stats(labels, PHASE3_LABEL_COLUMNS),
        "macro_weight_stats": _array_stats(macro_weights, PHASE3_WEIGHT_COLUMNS),
    }


def build_fold(
    fold_path: Path,
    source_dir: Path,
    output_dir: Path,
    word_max_features: int,
    char_max_features: int,
    audit_index: dict[str, dict[str, str]] | None,
    phase3_target_contract: str,
) -> dict[str, Any]:
    fold_doc = load_json(fold_path)
    fold = int(fold_doc["fold"])

    train_rows = [
        read_source_row(source_dir, item, audit_index) for item in fold_doc["train"]
    ]
    valid_rows = [
        read_source_row(source_dir, item, audit_index) for item in fold_doc["valid"]
    ]
    all_rows = train_rows + valid_rows

    train_texts = [row["normalized_text"] for row in train_rows]
    valid_texts = [row["normalized_text"] for row in valid_rows]

    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b\w+\b",
        min_df=1,
        max_features=word_max_features,
        dtype=np.float32,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        min_df=1,
        max_features=char_max_features,
        dtype=np.float32,
    )

    word_train = word_vectorizer.fit_transform(train_texts)
    word_valid = word_vectorizer.transform(valid_texts)
    char_train = char_vectorizer.fit_transform(train_texts)
    char_valid = char_vectorizer.transform(valid_texts)

    numeric_train = sparse.csr_matrix(
        np.array([row["numeric"] for row in train_rows], dtype=np.float32)
    )
    numeric_valid = sparse.csr_matrix(
        np.array([row["numeric"] for row in valid_rows], dtype=np.float32)
    )

    x_train = sparse.hstack([word_train, char_train, numeric_train], format="csr")
    x_valid = sparse.hstack([word_valid, char_valid, numeric_valid], format="csr")
    x_all = sparse.vstack([x_train, x_valid], format="csr")

    matrix_path = output_dir / f"X_{fold}.npz"
    sparse.save_npz(matrix_path, x_all, compressed=True)

    word_vocab = {
        token: int(index)
        for token, index in sorted(word_vectorizer.vocabulary_.items(), key=lambda kv: kv[1])
    }
    char_vocab = {
        token: int(index)
        for token, index in sorted(char_vectorizer.vocabulary_.items(), key=lambda kv: kv[1])
    }
    word_vocab_path = output_dir / f"fold_{fold}_word_vocabulary.json"
    char_vocab_path = output_dir / f"fold_{fold}_char_vocabulary.json"
    write_json(word_vocab_path, word_vocab)
    write_json(char_vocab_path, char_vocab)

    row_manifest = {
        "fold": fold,
        "matrix": str(matrix_path),
        "row_order": "train_then_valid",
        "train_n": len(train_rows),
        "valid_n": len(valid_rows),
        "n_features": int(x_all.shape[1]),
        "feature_blocks": {
            "word_tfidf": {
                "start": 0,
                "end": int(word_train.shape[1]),
                "vocabulary_path": str(word_vocab_path),
            },
            "char_tfidf": {
                "start": int(word_train.shape[1]),
                "end": int(word_train.shape[1] + char_train.shape[1]),
                "vocabulary_path": str(char_vocab_path),
            },
            "derived_numeric": {
                "start": int(word_train.shape[1] + char_train.shape[1]),
                "end": int(x_all.shape[1]),
                "names": NUMERIC_FEATURES,
            },
        },
        "rows": [
            {
                "row_index": idx,
                "partition": "train" if idx < len(train_rows) else "valid",
                "essay_id": row["essay_id"],
                "relative_path": row["relative_path"],
                "source_sha256": row["source_sha256"],
            }
            for idx, row in enumerate(all_rows)
        ],
    }
    row_manifest_path = output_dir / f"fold_{fold}_row_manifest.json"
    write_json(row_manifest_path, row_manifest)
    phase3_outputs = None
    if should_emit_phase3_targets(all_rows, phase3_target_contract, fold):
        phase3_outputs = build_phase3_target_artifacts(
            fold=fold,
            rows=all_rows,
            output_dir=output_dir,
            train_n=len(train_rows),
            valid_n=len(valid_rows),
        )

    output = {
        "fold": fold,
        "matrix_path": str(matrix_path),
        "matrix_sha256": sha256_file(matrix_path),
        "row_manifest_path": str(row_manifest_path),
        "row_manifest_sha256": sha256_file(row_manifest_path),
        "word_vocabulary_path": str(word_vocab_path),
        "word_vocabulary_sha256": sha256_file(word_vocab_path),
        "char_vocabulary_path": str(char_vocab_path),
        "char_vocabulary_sha256": sha256_file(char_vocab_path),
        "train_n": len(train_rows),
        "valid_n": len(valid_rows),
        "shape": [int(x_all.shape[0]), int(x_all.shape[1])],
        "nnz": int(x_all.nnz),
        "word_tfidf_features": int(word_train.shape[1]),
        "char_tfidf_features": int(char_train.shape[1]),
        "derived_numeric_features": len(NUMERIC_FEATURES),
    }
    if phase3_outputs is not None:
        output["phase3_transformer_contract"] = phase3_outputs
    return output


def feature_config(
    args: argparse.Namespace,
    split_manifest_hash: str,
    audit_table_hash: str | None,
    audit_row_count: int | None,
    expected_fold_count: int,
) -> dict[str, Any]:
    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": args.source_dir,
        "audit_table": args.audit_table,
        "audit_table_sha256": audit_table_hash,
        "audit_table_validation": {
            "row_count": audit_row_count,
            "usage": "identity/hash validation only; not a model feature source",
            "raw_text_columns_allowed": False,
            "label_side_columns_used_as_features": False,
        },
        "split_dir": args.split_dir,
        "split_manifest": f"{args.split_dir}/split_manifest.yaml",
        "split_manifest_sha256": split_manifest_hash,
        "expected_fold_count": expected_fold_count,
        "output_dir": args.output_dir,
        "seed": args.seed,
        "input_policy": {
            "allowed_source_fields": [
                "source_json.essay_txt",
                "label_json.info.essay_id",
                "label_json.paragraph[].paragraph_txt",
            ],
            "allowed_model_inputs": [
                "essay text-derived features",
                "student_grade",
            ],
            "label_json_access": "forbidden except Phase 2 label-only text fields",
            "label_only_json_access": (
                "allowed for paragraph[].paragraph_txt and info.essay_id as "
                "model-visible text identity, and for Phase 3 target/loss-weight "
                "artifacts when score+rubric are present"
            ),
            "student_location": "forbidden_model_input; split metadata only",
            "student_grade": "allowed_by_policy_but_not_used_in_this_feature_matrix",
            "target_scores": "forbidden_as_model_input; emitted only as training targets",
            "prompt_text": "disabled; requires explicit feature flag and provenance approval",
        },
        "phase3_target_contract": {
            "mode": args.phase3_target_contract,
            "target_columns": PHASE3_LABEL_COLUMNS,
            "macro_weight_columns": PHASE3_WEIGHT_COLUMNS,
            "overall_weight_default": W_OVERALL_DEFAULT,
            "schema_paths": PHASE3_TARGET_SCHEMA_PATHS,
        },
        "text_preprocessing": {
            "sentence_separator": SENTENCE_SEPARATOR,
            "normalization": "replace separator with space; collapse whitespace",
        },
        "feature_blocks": {
            "word_tfidf": {
                "source": "essay_text",
                "provenance": "derived",
                "fit_scope": "fold_train_only",
                "analyzer": "word",
                "ngram_range": [1, 2],
                "token_pattern": r"(?u)\b\w+\b",
                "max_features": args.word_max_features,
            },
            "char_tfidf": {
                "source": "essay_text",
                "provenance": "derived",
                "fit_scope": "fold_train_only",
                "analyzer": "char",
                "ngram_range": [2, 5],
                "max_features": args.char_max_features,
            },
            "derived_numeric": {
                "source": "essay_text",
                "provenance": "derived",
                "fit_scope": "none",
                "features": NUMERIC_FEATURES,
            },
        },
        "matrix_layout": "X_<fold>.npz contains train rows followed by valid rows; see fold_<fold>_row_manifest.json",
    }


def provenance_manifest(
    args: argparse.Namespace,
    fold_outputs: list[dict[str, Any]],
    config_hash: str,
    audit_table_hash: str | None,
    transformer_manifest_hash: str | None,
) -> dict[str, Any]:
    features: list[dict[str, Any]] = [
        {
            "name": "essay_text",
            "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
            "source_field": "essay_txt_or_paragraph_txt",
            "provenance": "source",
            "derived": False,
            "used_as": "raw input for fit/transform only; raw text is not copied to artifacts",
            "label_side": False,
        },
        {
            "name": "word_tfidf_*",
            "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
            "source_field": "essay_txt_or_paragraph_txt",
            "provenance": "derived",
            "derived": True,
            "used_as": "sparse TF-IDF word unigram/bigram features, fit on fold train only",
            "label_side": False,
        },
        {
            "name": "char_tfidf_*",
            "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
            "source_field": "essay_txt_or_paragraph_txt",
            "provenance": "derived",
            "derived": True,
            "used_as": "sparse TF-IDF char 2-5gram features, fit on fold train only",
            "label_side": False,
        },
    ]
    for name in NUMERIC_FEATURES:
        features.append(
            {
                "name": name,
                "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
                "source_field": "essay_txt_or_paragraph_txt",
                "provenance": "derived",
                "derived": True,
                "used_as": "numeric feature recomputed from model-visible essay text",
                "label_side": False,
            }
        )

    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_config_path": f"{args.output_dir}/feature_config.yaml",
        "feature_config_sha256": config_hash,
        "audit_table_path": args.audit_table,
        "audit_table_sha256": audit_table_hash,
        "audit_table_usage": "text identity/hash validation only; no audit columns become features",
        "hard_rule_9_status": "PASS",
        "label_side_feature_count": 0,
        "forbidden_inputs_not_used": [
            "dataset/sample/라벨링데이터",
            "dataset/sample_5k/라벨링데이터 score/rubric/student metadata except allowed text",
            "target_essay_scoreT_avg",
            "essay_scoreT",
            "rater_1",
            "rater_2",
            "rater_3",
            "paragraph",
            "paragraph_count_label_side",
            "correction",
            "correction_count_label_side",
            "student.location",
            "student_date",
            "student_educated",
            "student_reading",
            "rubric weights as model input features",
            "audit table label-side columns",
        ],
        "features": features,
        "phase3_targets": {
            "status": "PASS" if all_have_phase3_contract(fold_outputs) else "NOT_EMITTED",
            "mode": args.phase3_target_contract,
            "labels_are_training_targets": True,
            "macro_weights_are_loss_weights": True,
            "not_model_input_features": True,
            "target_columns": PHASE3_LABEL_COLUMNS,
            "macro_weight_columns": PHASE3_WEIGHT_COLUMNS,
            "schema_paths": PHASE3_TARGET_SCHEMA_PATHS,
            "transformer_input_manifest_path": (
                f"{args.output_dir}/phase3_transformer_input_manifest.json"
                if all_have_phase3_contract(fold_outputs)
                else None
            ),
            "transformer_input_manifest_sha256": transformer_manifest_hash,
            "prompt_text_enabled": False,
        },
        "fold_outputs": fold_outputs,
        "verification_command": (
            "python3 -c \"import json; "
            f"m=json.load(open('{args.output_dir}/feature_provenance_manifest.json')); "
            "assert m['label_side_feature_count']==0; "
            "assert all(f.get('label_side') is False for f in m['features']); "
            "assert all('source' in f and 'derived' in f for f in m['features'])\""
        ),
    }


def all_have_phase3_contract(fold_outputs: list[dict[str, Any]]) -> bool:
    return bool(fold_outputs) and all(
        "phase3_transformer_contract" in fold for fold in fold_outputs
    )


def phase3_transformer_input_manifest(
    args: argparse.Namespace,
    fold_outputs: list[dict[str, Any]],
    config_hash: str,
) -> dict[str, Any]:
    contract_outputs = [fold["phase3_transformer_contract"] for fold in fold_outputs]
    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "feature_config_path": f"{args.output_dir}/feature_config.yaml",
        "feature_config_sha256": config_hash,
        "contract": {
            "text": {
                "name": "text",
                "source": "source_json.essay_txt_or_label_json.paragraph[].paragraph_txt",
                "stored_in_manifest": False,
                "alignment": "row_order=train_then_valid per fold",
            },
            "labels": {
                "array_name": "labels",
                "order": PHASE3_LABEL_COLUMNS,
                "shape": "(N, 4)",
                "dtype": "float32",
                "schema_paths": {
                    key: PHASE3_TARGET_SCHEMA_PATHS[key]
                    for key in PHASE3_LABEL_COLUMNS
                },
            },
            "macro_weights": {
                "array_name": "macro_weights",
                "order": PHASE3_WEIGHT_COLUMNS,
                "shape": "(N, 4)",
                "dtype": "float32",
                "loss_formula": "((preds - labels) ** 2 * macro_weights).sum(dim=1).mean()",
                "schema_paths": {
                    key: PHASE3_TARGET_SCHEMA_PATHS[key]
                    for key in PHASE3_WEIGHT_COLUMNS
                },
            },
            "target_overall_raw": {
                "array_name": "target_overall_raw",
                "shape": "(N,)",
                "dtype": "float32",
                "schema_paths": PHASE3_TARGET_SCHEMA_PATHS["target_overall_raw"],
                "usage": "evaluation/reference only, not model input",
            },
            "prompt_text": {
                "enabled": False,
                "included": False,
                "reason": "requires explicit feature flag and provenance approval",
            },
        },
        "folds": contract_outputs,
        "verification_command": (
            "python3 -c \"import json, numpy as np; "
            f"m=json.load(open('{args.output_dir}/phase3_transformer_input_manifest.json')); "
            "assert m['status']=='PASS'; "
            "assert m['contract']['labels']['order']=="
            f"{PHASE3_LABEL_COLUMNS!r}; "
            "assert m['contract']['macro_weights']['order']=="
            f"{PHASE3_WEIGHT_COLUMNS!r}; "
            "assert m['contract']['prompt_text']['enabled'] is False; "
            "assert all(((a:=np.load(f['target_artifact_path']))['labels'].shape[1] == 4 "
            "and a['macro_weights'].shape[1] == 4) for f in m['folds'])\""
        ),
    }


def package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def reproducibility_manifest(
    args: argparse.Namespace,
    split_manifest_hash: str,
    audit_table_hash: str | None,
    config_hash: str,
    provenance_hash: str,
    transformer_manifest_hash: str | None,
    fold_outputs: list[dict[str, Any]],
    expected_fold_count: int,
) -> dict[str, Any]:
    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "config_path": f"{args.output_dir}/feature_config.yaml",
        "config_hash_algorithm": "sha256",
        "config_hash": config_hash,
        "split_manifest_path": f"{args.split_dir}/split_manifest.yaml",
        "split_manifest_sha256": split_manifest_hash,
        "audit_table_path": args.audit_table,
        "audit_table_sha256": audit_table_hash,
        "feature_provenance_manifest_path": (
            f"{args.output_dir}/feature_provenance_manifest.json"
        ),
        "feature_provenance_manifest_sha256": provenance_hash,
        "phase3_transformer_input_manifest_path": (
            f"{args.output_dir}/phase3_transformer_input_manifest.json"
            if transformer_manifest_hash is not None
            else None
        ),
        "phase3_transformer_input_manifest_sha256": transformer_manifest_hash,
        "package_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": package_version("scipy"),
            "scikit-learn": package_version("scikit-learn"),
            "pyyaml": package_version("PyYAML"),
        },
        "fold_outputs": fold_outputs,
        "rebuild_command": (
            "python3 pipelines/build_features.py "
            + (f"--audit-table {args.audit_table} " if args.audit_table else "")
            + f"--source-dir {args.source_dir} "
            + f"--split-dir {args.split_dir} "
            + f"--output-dir {args.output_dir} "
            + f"--cycle-id {args.cycle_id} --kanban-task-id {args.kanban_task_id} "
            + f"--seed {args.seed} "
            + f"--phase3-target-contract {args.phase3_target_contract}"
        ),
        "verification_commands": [
            (
                "python3 -c \"import json; "
                f"m=json.load(open('{args.output_dir}/feature_provenance_manifest.json')); "
                "assert m['label_side_feature_count']==0; "
                "assert all(f.get('label_side') is False for f in m['features']); "
                "assert all('source' in f and 'derived' in f for f in m['features'])\""
            ),
            (
                "python3 -c \"from scipy import sparse; "
                f"[sparse.load_npz('{args.output_dir}/X_' + str(i) + '.npz') for i in range({expected_fold_count})]\""
            ),
            (
                "python3 -c \"import json, numpy as np; "
                f"m=json.load(open('{args.output_dir}/phase3_transformer_input_manifest.json')); "
                "assert m['status']=='PASS'; "
                "assert m['contract']['prompt_text']['enabled'] is False; "
                "assert all(((a:=np.load(f['target_artifact_path']))['labels'].shape[1] == 4 "
                "and a['macro_weights'].shape[1] == 4) for f in m['folds'])\""
                if transformer_manifest_hash is not None
                else "phase3 transformer input manifest not emitted"
            ),
        ],
    }


def feature_verification_report(
    args: argparse.Namespace, fold_outputs: list[dict[str, Any]], expected_fold_count: int
) -> str:
    audit_arg = f"--audit-table {args.audit_table} " if args.audit_table else ""
    fold_lines = "\n".join(
        "- fold {fold}: train_n={train_n}, valid_n={valid_n}, shape={shape}, "
        "word_vocab={word_vocabulary_path}, char_vocab={char_vocabulary_path}".format(
            **fold
        )
        for fold in fold_outputs
    )
    target_lines = "\n".join(
        "- fold {fold}: labels_shape={labels_shape}, macro_weights_shape={macro_weights_shape}, artifact={target_artifact_path}".format(
            **fold["phase3_transformer_contract"]
        )
        for fold in fold_outputs
        if "phase3_transformer_contract" in fold
    )
    target_section = (
        f"""
## Phase 3 Transformer Input Contract

- status: PASS
- text: model-visible essay text only; raw text is not copied into manifests
- labels order: `{PHASE3_LABEL_COLUMNS}`
- macro_weights order: `{PHASE3_WEIGHT_COLUMNS}`
- prompt_text: disabled

{target_lines}
"""
        if target_lines
        else """
## Phase 3 Transformer Input Contract

- status: NOT_EMITTED
- reason: source rows did not contain score+rubric, or target contract mode was off
"""
    )
    return f"""# Cycle {args.cycle_id} Feature Verification

Task: `{args.kanban_task_id}`

## Hard Rule #9

- label-side feature count: 0
- model inputs: train-fold TF-IDF from model-visible essay text; dense features derived from the same text
- excluded: `student.location`, target scores, rater scores, label paragraph/correction fields
- `student_grade`: allowed by policy, not materialized in this matrix

## Train-only Vocabulary Fit

Each fold fits word and char TF-IDF vectorizers only on that fold's train rows, then transforms valid rows. Row manifests record `row_order=train_then_valid` and partition per row.

{fold_lines}
{target_section}

## Verification Commands

```bash
python3 -m py_compile pipelines/build_features.py
python3 pipelines/build_features.py {audit_arg}--source-dir {args.source_dir} --split-dir {args.split_dir} --output-dir {args.output_dir} --cycle-id {args.cycle_id} --kanban-task-id {args.kanban_task_id} --seed {args.seed} --phase3-target-contract {args.phase3_target_contract}
python3 -c "import json; m=json.load(open('{args.output_dir}/feature_provenance_manifest.json')); assert m['label_side_feature_count']==0; assert all(f.get('label_side') is False for f in m['features']); assert all('source' in f and 'derived' in f for f in m['features'])"
python3 -c "import json; from pathlib import Path; d=Path('{args.output_dir}'); assert all(json.load(open(d / f'fold_{{i}}_row_manifest.json'))['row_order']=='train_then_valid' for i in range({expected_fold_count}))"
python3 -c "import json, numpy as np; m=json.load(open('{args.output_dir}/phase3_transformer_input_manifest.json')); assert m['status']=='PASS'; assert m['contract']['labels']['order']=={PHASE3_LABEL_COLUMNS!r}; assert m['contract']['macro_weights']['order']=={PHASE3_WEIGHT_COLUMNS!r}; assert m['contract']['prompt_text']['enabled'] is False; assert all(((a:=np.load(f['target_artifact_path']))['labels'].shape[1] == 4 and a['macro_weights'].shape[1] == 4) for f in m['folds'])"
```
"""


def expected_split_fold_paths(split_dir: Path) -> list[Path]:
    manifest_path = split_dir / "split_manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    expected_fold_count = int(manifest["k"])
    paths = [split_dir / f"fold_{fold}.json" for fold in range(expected_fold_count)]
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing split fold files: {missing}")
    return paths


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir)
    split_dir = Path(args.split_dir)
    output_dir = Path(args.output_dir)
    audit_table = Path(args.audit_table) if args.audit_table else None

    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)
    if not split_dir.is_dir():
        raise FileNotFoundError(split_dir)
    if audit_table is not None and not audit_table.is_file():
        raise FileNotFoundError(audit_table)

    output_dir.mkdir(parents=True, exist_ok=True)

    split_manifest_path = split_dir / "split_manifest.yaml"
    split_manifest_hash = sha256_file(split_manifest_path)
    fold_paths = expected_split_fold_paths(split_dir)
    expected_fold_count = len(fold_paths)
    audit_index = load_audit_index(audit_table) if audit_table is not None else None
    audit_table_hash = sha256_file(audit_table) if audit_table is not None else None
    audit_row_count = len(audit_index) if audit_index is not None else None

    config_path = output_dir / "feature_config.yaml"
    config_doc = feature_config(
        args=args,
        split_manifest_hash=split_manifest_hash,
        audit_table_hash=audit_table_hash,
        audit_row_count=audit_row_count,
        expected_fold_count=expected_fold_count,
    )
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config_doc, handle, allow_unicode=True, sort_keys=False)
    config_hash = sha256_file(config_path)

    fold_outputs = []
    for fold_path in fold_paths:
        fold_outputs.append(
            build_fold(
                fold_path=fold_path,
                source_dir=source_dir,
                output_dir=output_dir,
                word_max_features=args.word_max_features,
                char_max_features=args.char_max_features,
                audit_index=audit_index,
                phase3_target_contract=args.phase3_target_contract,
            )
        )

    if len(fold_outputs) != expected_fold_count:
        raise RuntimeError(
            f"expected {expected_fold_count} fold outputs, got {len(fold_outputs)}"
        )

    transformer_manifest_hash = None
    if all_have_phase3_contract(fold_outputs):
        transformer_manifest_path = output_dir / "phase3_transformer_input_manifest.json"
        write_json(
            transformer_manifest_path,
            phase3_transformer_input_manifest(args, fold_outputs, config_hash),
        )
        transformer_manifest_hash = sha256_file(transformer_manifest_path)

    manifest_path = output_dir / "feature_provenance_manifest.json"
    write_json(
        manifest_path,
        provenance_manifest(
            args,
            fold_outputs,
            config_hash,
            audit_table_hash,
            transformer_manifest_hash,
        ),
    )
    provenance_hash = sha256_file(manifest_path)

    reproducibility_path = output_dir / "reproducibility_manifest.json"
    write_json(
        reproducibility_path,
        reproducibility_manifest(
            args=args,
            split_manifest_hash=split_manifest_hash,
            audit_table_hash=audit_table_hash,
            config_hash=config_hash,
            provenance_hash=provenance_hash,
            transformer_manifest_hash=transformer_manifest_hash,
            fold_outputs=fold_outputs,
            expected_fold_count=expected_fold_count,
        ),
    )
    verification_report_path = output_dir / "feature_verification_report.md"
    verification_report_path.write_text(
        feature_verification_report(args, fold_outputs, expected_fold_count),
        encoding="utf-8",
    )

    print(f"wrote {config_path}")
    print(f"wrote {manifest_path}")
    if transformer_manifest_hash is not None:
        print(f"wrote {output_dir / 'phase3_transformer_input_manifest.json'}")
    print(f"wrote {reproducibility_path}")
    print(f"wrote {verification_report_path}")
    for fold in fold_outputs:
        print(
            "fold {fold}: {shape} nnz={nnz} matrix={matrix_path}".format(
                fold=fold["fold"],
                shape=tuple(fold["shape"]),
                nnz=fold["nnz"],
                matrix_path=fold["matrix_path"],
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
