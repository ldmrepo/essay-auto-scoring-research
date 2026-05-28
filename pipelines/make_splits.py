#!/usr/bin/env python3
"""Create leakage-checked location-grouped folds.

The split artifacts intentionally contain only essay identifiers and relative
paths. Raw essay text, target scores, rater scores, and label-side features are
not copied into fold JSON files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sklearn.model_selection import StratifiedGroupKFold


LOCATION_COLUMN = "student_location"
REGION_COLUMN = "region"
DEFAULT_GROUP_KEY = "student.location"
STRATIFY_KEY = "essay_type__student_grade_group__score_band"
SEED = 42
DEFAULT_REGION_MAP = {
    "02": "A_capital_chungcheong_gangwon",
    "031": "A_capital_chungcheong_gangwon",
    "032": "A_capital_chungcheong_gangwon",
    "033": "A_capital_chungcheong_gangwon",
    "041": "A_capital_chungcheong_gangwon",
    "042": "A_capital_chungcheong_gangwon",
    "043": "A_capital_chungcheong_gangwon",
    "044": "A_capital_chungcheong_gangwon",
    "061": "B_honam",
    "063": "B_honam",
    "051": "C_yeongnam",
    "053": "C_yeongnam",
    "054": "C_yeongnam",
    "055": "C_yeongnam",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create k-fold splits grouped by student.location."
    )
    parser.add_argument("--input", default="dataset/sample", help="Sample dataset root.")
    parser.add_argument("--k", type=int, default=5, help="Number of folds.")
    parser.add_argument("--output", default="workspace/cycle_2/splits")
    parser.add_argument("--cycle-id", default="2")
    parser.add_argument("--kanban-task-id", default="t_68c5fd8a")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--group-key",
        choices=["student.location", "location", "region"],
        default=DEFAULT_GROUP_KEY,
        help="Fold-disjoint grouping key. Use region for the Cycle M1 k=3 retry.",
    )
    parser.add_argument(
        "--region-map",
        default=None,
        help=(
            "Optional JSON/YAML mapping from student.location code to region. "
            "When omitted with --group-key region, the Cycle M1 approved map is used."
        ),
    )
    parser.add_argument(
        "--min-valid-n",
        type=int,
        default=300,
        help="Hard-block when any fold has fewer validation rows.",
    )
    parser.add_argument(
        "--audit-table",
        default=None,
        help=(
            "Existing audit table to reuse when present. Defaults to "
            "workspace/cycle_<cycle-id>/audit/audit_table_no_raw_text.csv."
        ),
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def load_region_map(region_map_path: str | None) -> dict[str, str]:
    if region_map_path is None:
        return dict(DEFAULT_REGION_MAP)

    path = Path(region_map_path)
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(handle)
        else:
            payload = json.load(handle)
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        raise ValueError("--region-map must contain a string-to-string mapping")
    return dict(payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def json_paths(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*.json"))
        if path.is_file()
    }


def build_split_table(input_root: Path) -> pd.DataFrame:
    source_root = input_root / "원천데이터"
    label_root = input_root / "라벨링데이터"
    source_paths = json_paths(source_root)
    label_paths = json_paths(label_root)
    rows: list[dict[str, Any]] = []

    for relative_path in sorted(set(source_paths) & set(label_paths)):
        source = load_json(source_paths[relative_path])
        label = load_json(label_paths[relative_path])
        essay_id_source = source.get("essay_id")
        essay_id_label = label.get("info", {}).get("essay_id")
        if essay_id_source != essay_id_label:
            raise ValueError(
                f"essay_id mismatch for {relative_path}: "
                f"source={essay_id_source} label={essay_id_label}"
            )
        student = label.get("student", {})
        score = label.get("score", {})
        rows.append(
            {
                "relative_path": relative_path,
                "essay_id_source": essay_id_source,
                "essay_id_label": essay_id_label,
                "essay_type": label.get("info", {}).get("essay_type")
                or label.get("rubric", {}).get("essay_type"),
                "student_grade_group": student.get("student_grade_group"),
                "student_location": student.get("location"),
                "target_essay_scoreT_avg": score.get("essay_scoreT_avg"),
            }
        )

    return pd.DataFrame(rows)


def load_split_table(args: argparse.Namespace) -> tuple[pd.DataFrame, str, str]:
    audit_table = Path(args.audit_table) if args.audit_table else Path(
        f"workspace/cycle_{args.cycle_id}/audit/audit_table_no_raw_text.csv"
    )
    if audit_table.exists():
        df = pd.read_csv(audit_table, dtype={"student_location": "string"})
        return df, str(audit_table), sha256_file(audit_table)

    df = build_split_table(Path(args.input))
    return df, "built_from_dataset_json", sha256_payload(df.to_dict(orient="records"))


def require_columns(df: pd.DataFrame) -> None:
    if "essay_id_source" not in df.columns and "essay_id_label" in df.columns:
        df["essay_id_source"] = df["essay_id_label"]

    required = [
        "relative_path",
        "essay_id_source",
        "essay_id_label",
        "essay_type",
        "student_grade_group",
        "student_location",
        "target_essay_scoreT_avg",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"split input is missing required columns: {missing}")
    null_columns = [
        column
        for column in ["relative_path", "essay_id_source", "essay_type", "student_location"]
        if df[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"split input has null values in required columns: {null_columns}")


def add_score_band(df: pd.DataFrame) -> pd.DataFrame:
    target = pd.to_numeric(df["target_essay_scoreT_avg"], errors="coerce")
    if target.isna().any():
        raise ValueError("split input has null/non-numeric target_essay_scoreT_avg values")
    if ((target < 0) | (target > 30)).any():
        bad = target[(target < 0) | (target > 30)].head(10).tolist()
        raise ValueError(f"target_essay_scoreT_avg outside 0-30 scale: {bad}")

    out = df.copy()
    out["score_band"] = pd.cut(
        target,
        bins=[-0.001, 9.999999, 19.999999, 30.000001],
        labels=["low_0_9", "mid_10_19", "high_20_30"],
        include_lowest=True,
    ).astype(str)
    return out


def selected_group_column(group_key: str) -> str:
    if group_key == "region":
        return REGION_COLUMN
    return LOCATION_COLUMN


def apply_group_key(df: pd.DataFrame, group_key: str, region_map_path: str | None) -> tuple[pd.DataFrame, dict[str, str] | None]:
    out = add_score_band(df)
    if group_key != "region":
        return out, None

    region_map = load_region_map(region_map_path)
    out[REGION_COLUMN] = out[LOCATION_COLUMN].fillna("<MISSING>").astype(str).map(region_map)
    missing = sorted(out.loc[out[REGION_COLUMN].isna(), LOCATION_COLUMN].dropna().astype(str).unique())
    if missing:
        raise ValueError(f"student_location values missing from region map: {missing}")
    return out, region_map


def item_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    rows = df.sort_values("relative_path")
    return [
        {
            "essay_id": str(row["essay_id_source"]),
            "relative_path": str(row["relative_path"]),
        }
        for _, row in rows.iterrows()
    ]


def count_dict(series: pd.Series) -> dict[str, int]:
    counts = series.fillna("<MISSING>").astype(str).value_counts().sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def percent_dict(series: pd.Series) -> dict[str, float]:
    counts = series.fillna("<MISSING>").astype(str).value_counts(normalize=True).sort_index()
    return {str(key): round(float(value), 6) for key, value in counts.items()}


def stratify_labels(df: pd.DataFrame) -> pd.Series:
    essay_type = df["essay_type"].fillna("<MISSING>").astype(str)
    grade_group = df["student_grade_group"].fillna("<MISSING>").astype(str)
    score_band = df["score_band"].fillna("<MISSING>").astype(str)
    return essay_type + "|" + grade_group + "|" + score_band


def build_folds(df: pd.DataFrame, k: int, seed: int, group_column: str) -> list[dict[str, Any]]:
    groups = df[group_column].fillna("<MISSING>").astype(str)
    labels = stratify_labels(df)
    splitter = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
    folds: list[dict[str, Any]] = []

    for fold, (train_idx, valid_idx) in enumerate(splitter.split(df, labels, groups)):
        train_df = df.iloc[train_idx].copy()
        valid_df = df.iloc[valid_idx].copy()
        train_groups = sorted(train_df[group_column].fillna("<MISSING>").astype(str).unique())
        valid_groups = sorted(valid_df[group_column].fillna("<MISSING>").astype(str).unique())
        overlap = sorted(set(train_groups) & set(valid_groups))
        train_locations = sorted(train_df[LOCATION_COLUMN].fillna("<MISSING>").astype(str).unique())
        valid_locations = sorted(valid_df[LOCATION_COLUMN].fillna("<MISSING>").astype(str).unique())
        location_overlap = sorted(set(train_locations) & set(valid_locations))
        warnings = []
        if overlap:
            warnings.append("group overlap detected")
        if location_overlap:
            warnings.append("student.location overlap detected")

        folds.append(
            {
                "fold": fold,
                "train_df": train_df,
                "valid_df": valid_df,
                "train_groups": train_groups,
                "valid_groups": valid_groups,
                "group_overlap": overlap,
                "train_locations": train_locations,
                "valid_locations": valid_locations,
                "location_overlap": location_overlap,
                "warnings": warnings,
            }
        )

    return folds


def fold_doc(args: argparse.Namespace, fold: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "fold": int(fold["fold"]),
        "seed": int(args.seed),
        "split_method": "sklearn.model_selection.StratifiedGroupKFold",
        "k": int(args.k),
        "group_key": args.group_key,
        "stratify_key": STRATIFY_KEY,
        "model_feature_policy": {
            "student_location": "split-only; exclude from model inputs",
            "raw_text": "not copied into split artifacts",
            "label_side_features": "not copied into split artifacts",
        },
        "train_n": int(len(fold["train_df"])),
        "valid_n": int(len(fold["valid_df"])),
        "train_groups": fold["train_groups"],
        "valid_groups": fold["valid_groups"],
        "group_overlap": fold["group_overlap"],
        "train_locations": fold["train_locations"],
        "valid_locations": fold["valid_locations"],
        "student_location_overlap": fold["location_overlap"],
        "warnings": fold["warnings"],
        "train": item_rows(fold["train_df"]),
        "valid": item_rows(fold["valid_df"]),
    }


def write_folds(args: argparse.Namespace, output_dir: Path, folds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs = []
    for fold in folds:
        doc = fold_doc(args, fold)
        write_json(output_dir / f"fold_{fold['fold']}.json", doc)
        docs.append(doc)
    return docs


def write_split_row_manifests(args: argparse.Namespace, output_dir: Path, folds: list[dict[str, Any]]) -> list[str]:
    paths = []
    for fold in folds:
        rows = []
        for partition, frame in [("train", fold["train_df"]), ("valid", fold["valid_df"])]:
            for item in item_rows(frame):
                rows.append({"partition": partition, **item})
        path = output_dir / f"fold_{fold['fold']}_row_manifest.json"
        write_json(
            path,
            {
                "cycle_id": args.cycle_id,
                "kanban_task_id": args.kanban_task_id,
                "fold": int(fold["fold"]),
                "row_order": "train_then_valid",
                "rows": rows,
            },
        )
        paths.append(path.as_posix())
    return paths


def manifest(
    args: argparse.Namespace,
    output_dir: Path,
    df: pd.DataFrame,
    source_audit_table: str,
    source_audit_table_sha: str,
    folds: list[dict[str, Any]],
    fold_docs: list[dict[str, Any]],
    region_map: dict[str, str] | None,
    row_manifest_paths: list[str],
) -> dict[str, Any]:
    group_column = selected_group_column(args.group_key)
    verification_parts = [
        "python3",
        "pipelines/make_splits.py",
        f"--input {args.input}",
        f"--k {args.k}",
        f"--output {args.output}",
        f"--cycle-id {args.cycle_id}",
        f"--kanban-task-id {args.kanban_task_id}",
        f"--min-valid-n {args.min_valid_n}",
        f"--group-key {args.group_key}",
    ]
    if args.audit_table:
        verification_parts.append(f"--audit-table {args.audit_table}")
    if args.region_map:
        verification_parts.append(f"--region-map {args.region_map}")

    config_payload = {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "k": args.k,
        "min_valid_n": args.min_valid_n,
        "seed": args.seed,
        "group_key": args.group_key,
        "stratify_key": STRATIFY_KEY,
        "split_method": "StratifiedGroupKFold",
        "region_map": region_map,
        "source_audit_table_sha256": source_audit_table_sha,
    }
    split_hash = sha256_payload(
        [
            {
                "fold": doc["fold"],
                "train": doc["train"],
                "valid": doc["valid"],
                "valid_groups": doc["valid_groups"],
            }
            for doc in fold_docs
        ]
    )

    fold_summaries = []
    for fold in folds:
        valid_df = fold["valid_df"]
        fold_summaries.append(
            {
                "fold": int(fold["fold"]),
                "train_n": int(len(fold["train_df"])),
                "valid_n": int(len(valid_df)),
                "train_groups": fold["train_groups"],
                "valid_groups": fold["valid_groups"],
                "group_overlap_count": int(len(fold["group_overlap"])),
                "train_locations": fold["train_locations"],
                "valid_locations": fold["valid_locations"],
                "student_location_overlap_count": int(len(fold["location_overlap"])),
                "valid_essay_type_counts": count_dict(valid_df["essay_type"]),
                "valid_student_grade_group_counts": count_dict(valid_df["student_grade_group"]),
                "valid_score_band_counts": count_dict(valid_df["score_band"]),
                "valid_score_band_pct": percent_dict(valid_df["score_band"]),
                "valid_stratify_counts": count_dict(stratify_labels(valid_df)),
                "warnings": fold["warnings"],
            }
        )

    all_valid_paths = [
        item["relative_path"]
        for doc in fold_docs
        for item in doc["valid"]
    ]
    stratify_counts = count_dict(stratify_labels(df))
    sparse_stratify_classes = {
        key: value for key, value in stratify_counts.items() if value < args.k
    }
    score_band_pct_by_fold = {
        str(summary["fold"]): summary["valid_score_band_pct"] for summary in fold_summaries
    }
    overall_score_band_pct = percent_dict(df["score_band"])
    score_band_pct_spread = {}
    score_band_pct_deviation_from_overall = {}
    for band in sorted(df["score_band"].astype(str).unique()):
        values = [
            summary["valid_score_band_pct"].get(band, 0.0)
            for summary in fold_summaries
        ]
        score_band_pct_spread[band] = {
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "spread": round(max(values) - min(values), 6),
            "spread_percentage_points": round((max(values) - min(values)) * 100, 4),
        }
        overall = overall_score_band_pct.get(band, 0.0)
        score_band_pct_deviation_from_overall[band] = {
            str(summary["fold"]): {
                "fold_pct": summary["valid_score_band_pct"].get(band, 0.0),
                "overall_pct": overall,
                "abs_deviation": round(
                    abs(summary["valid_score_band_pct"].get(band, 0.0) - overall), 6
                ),
                "abs_deviation_percentage_points": round(
                    abs(summary["valid_score_band_pct"].get(band, 0.0) - overall) * 100,
                    4,
                ),
            }
            for summary in fold_summaries
        }
    warnings = []
    hard_blocks = []
    if sparse_stratify_classes:
        warnings.append(
            "exact stratification infeasible for classes with count < k: "
            f"{sparse_stratify_classes}"
        )
    for summary in fold_summaries:
        if summary["valid_n"] < args.min_valid_n:
            hard_blocks.append(
                f"fold_{summary['fold']} valid_n={summary['valid_n']} < "
                f"{args.min_valid_n}"
            )
        if summary["student_location_overlap_count"] != 0:
            hard_blocks.append(
                f"fold_{summary['fold']} student.location overlap count "
                f"{summary['student_location_overlap_count']} > 0"
            )
    for band, deviations in score_band_pct_deviation_from_overall.items():
        for fold, deviation in deviations.items():
            if deviation["abs_deviation"] <= 0.10:
                continue
            hard_blocks.append(
                f"fold_{fold} score_band {band} deviates "
                f"{deviation['abs_deviation_percentage_points']:.2f}pp from overall > 10.00pp"
            )
    fallback_verification_parts = [
        "python3",
        "pipelines/make_splits.py",
        f"--input {args.input}",
        "--k 3",
        f"--output {args.output}_region_k3_candidate",
        f"--cycle-id {args.cycle_id}",
        f"--kanban-task-id {args.kanban_task_id}",
        f"--min-valid-n {args.min_valid_n}",
        "--group-key region",
    ]
    if args.audit_table:
        fallback_verification_parts.append(f"--audit-table {args.audit_table}")

    if args.group_key == "region":
        fallback_decision = {
            "status": "applied",
            "reason": (
                "Approved region merge + k=3 fallback split generated after "
                "preserving or reproducing default k=5 student.location failure evidence."
            ),
            "recommended_fallback": "region merge + k=3",
            "recommended_verification_command": " ".join(fallback_verification_parts),
        }
    elif hard_blocks:
        fallback_decision = {
            "status": "authorized_after_documented_failure",
            "reason": (
                "Default k=5 student.location split failed the valid_n safety gate. "
                "Active policy authorizes region merge + k=3 fallback after this "
                "failure evidence is preserved."
            ),
            "recommended_fallback": "region merge + k=3",
            "recommended_verification_command": " ".join(fallback_verification_parts),
        }
    else:
        fallback_decision = {
            "status": "not_applied",
            "reason": "Default k=5 student.location split passed; fallback not needed.",
            "recommended_fallback": "region merge + k=3",
            "recommended_verification_command": " ".join(fallback_verification_parts),
        }

    return {
        "cycle_id": args.cycle_id,
        "kanban_task_id": args.kanban_task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_audit_table": source_audit_table,
        "source_audit_table_sha256": source_audit_table_sha,
        "split_method": "sklearn.model_selection.StratifiedGroupKFold",
        "k": int(args.k),
        "min_valid_n": int(args.min_valid_n),
        "seed": int(args.seed),
        "group_key": args.group_key,
        "group_column": group_column,
        "stratify_key": STRATIFY_KEY,
        "stratify_note": (
            "essay_type x student_grade_group x score_band. Score band uses only "
            "coarse target bands for split balancing and is not copied to row-level "
            "fold artifacts or model inputs."
        ),
        "score_band_policy": {
            "low_0_9": "0 <= target_essay_scoreT_avg < 10",
            "mid_10_19": "10 <= target_essay_scoreT_avg < 20",
            "high_20_30": "20 <= target_essay_scoreT_avg <= 30",
            "acceptance_distribution_check": "absolute fold deviation from the overall percentage for every band must be <= 10 percentage points",
            "overall_distribution": overall_score_band_pct,
            "distribution_by_fold": score_band_pct_by_fold,
            "distribution_spread": score_band_pct_spread,
            "distribution_deviation_from_overall": score_band_pct_deviation_from_overall,
        },
        "region_map": region_map,
        "split_hash_algorithm": "sha256",
        "split_hash": split_hash,
        "config_hash_algorithm": "sha256",
        "config_hash": sha256_payload(config_payload),
        "location_groups": count_dict(df[LOCATION_COLUMN]),
        "selected_groups": count_dict(df[group_column]),
        "total_rows": int(len(df)),
        "unique_locations": int(df[LOCATION_COLUMN].nunique(dropna=True)),
        "unique_groups": int(df[group_column].nunique(dropna=True)),
        "stratify_feasibility": {
            "stratify_class_counts": stratify_counts,
            "classes_with_count_below_k": sparse_stratify_classes,
            "exact_stratification_feasible": not bool(sparse_stratify_classes),
        },
        "folds": fold_summaries,
        "leakage_checks": {
            "group_overlap_count_all_folds": int(
                sum(summary["group_overlap_count"] for summary in fold_summaries)
            ),
            "student_location_overlap_count_all_folds": int(
                sum(summary["student_location_overlap_count"] for summary in fold_summaries)
            ),
            "all_rows_appear_once_as_valid": sorted(all_valid_paths)
            == sorted(df["relative_path"].astype(str).tolist()),
            "raw_text_copied": False,
            "target_scores_used_for_split": True,
            "target_score_usage": "coarse score_band stratification only; target values are not written to row-level split artifacts",
            "student_location_policy": "split-only; excluded from model feature artifacts",
        },
        "fallback_decision": fallback_decision,
        "verdict": "HARD_BLOCK" if hard_blocks else "PASS",
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "outputs": {
            "fold_json_glob": str(output_dir / f"fold_{{0..{args.k - 1}}}.json"),
            "split_row_manifests": row_manifest_paths,
            "split_manifest": str(output_dir / "split_manifest.yaml"),
            "split_leakage_check": str(output_dir / "split_leakage_check.md"),
        },
        "verification_command": " ".join(verification_parts),
    }


def leakage_report(manifest_doc: dict[str, Any]) -> str:
    fold_rows = []
    for summary in manifest_doc["folds"]:
        fold_rows.append(
            "| {fold} | {train_n} | {valid_n} | {valid_groups} | {group_overlap_count} | {warnings} |".format(
                fold=summary["fold"],
                train_n=summary["train_n"],
                valid_n=summary["valid_n"],
                valid_groups=", ".join(summary["valid_groups"]),
                group_overlap_count=summary["group_overlap_count"],
                warnings=", ".join(summary["warnings"]),
            )
        )
    warnings = manifest_doc["warnings"] or ["None"]
    hard_blocks = manifest_doc["hard_blocks"] or ["None"]
    warning_lines = "\n".join(f"- WARN: {item}" for item in warnings)
    hard_block_lines = "\n".join(f"- BLOCK: {item}" for item in hard_blocks)
    type_lines = "\n".join(
        f"- fold_{summary['fold']}: {summary['valid_essay_type_counts']}"
        for summary in manifest_doc["folds"]
    )
    grade_lines = "\n".join(
        f"- fold_{summary['fold']}: {summary['valid_student_grade_group_counts']}"
        for summary in manifest_doc["folds"]
    )
    score_band_lines = "\n".join(
        f"- fold_{summary['fold']}: counts={summary['valid_score_band_counts']}, pct={summary['valid_score_band_pct']}"
        for summary in manifest_doc["folds"]
    )
    score_band_spread_lines = "\n".join(
        f"- {band}: {spread['spread_percentage_points']:.4f}pp"
        for band, spread in manifest_doc["score_band_policy"]["distribution_spread"].items()
    )
    score_band_deviation_lines = []
    for band, deviations in manifest_doc["score_band_policy"][
        "distribution_deviation_from_overall"
    ].items():
        for fold, deviation in deviations.items():
            score_band_deviation_lines.append(
                "- fold_{fold} {band}: {pp:.4f}pp".format(
                    fold=fold,
                    band=band,
                    pp=deviation["abs_deviation_percentage_points"],
                )
            )
    return f"""# Cycle {manifest_doc['cycle_id']} Split Leakage Check

## Verdict
{manifest_doc['verdict']}. Every validation fold has zero selected-group overlap and zero `student.location` overlap with its training fold. Raw essay text, target values, rater scores, and label-side features were not copied into fold JSON artifacts.

## Split Method
- Method: `StratifiedGroupKFold(n_splits={manifest_doc['k']}, shuffle=True, random_state={manifest_doc['seed']})`
- Group key: `{manifest_doc['group_key']}` (`{manifest_doc['group_column']}`)
- Stratify key: `{manifest_doc['stratify_key']}` (`essay_type x student_grade_group x score_band`)
- Target scores were used only to derive coarse `score_band` for fold balancing. Exact target values are not copied into row-level split artifacts or model inputs.
- `student.location` is retained only in split metadata for leakage verification and must not be used as a model input.

## Fold Leakage Summary
| fold | train_n | valid_n | valid_groups | group_overlap_count | warnings |
|---:|---:|---:|:---|---:|:---|
{chr(10).join(fold_rows)}

## Valid Essay Type Counts
{type_lines}

## Valid Grade Group Counts
{grade_lines}

## Valid Score Band Counts
{score_band_lines}

## Score Band Percentage Spread
Diagnostic max-minus-min spread across folds:
{score_band_spread_lines}

Acceptance check, absolute fold deviation from overall distribution:
{chr(10).join(score_band_deviation_lines)}

## Warnings
{warning_lines}

## Hard Blocks
{hard_block_lines}
- Rationale: this split policy requires every fold to satisfy `valid_n >= {manifest_doc['min_valid_n']}`.

## Fallback Decision
- Status: `{manifest_doc['fallback_decision']['status']}`
- Reason: {manifest_doc['fallback_decision']['reason']}
- Recommended fallback: `{manifest_doc['fallback_decision']['recommended_fallback']}`
- Candidate verification command:
```bash
{manifest_doc['fallback_decision']['recommended_verification_command']}
```

## Reproducibility
- Split hash: `{manifest_doc['split_hash']}`
- Config hash: `{manifest_doc['config_hash']}`
- Verification command:
```bash
{manifest_doc['verification_command']}
```
"""


def validate_manifest(manifest_doc: dict[str, Any]) -> None:
    checks = manifest_doc["leakage_checks"]
    if checks["group_overlap_count_all_folds"] != 0:
        raise RuntimeError("group leakage detected in split manifest")
    if checks["all_rows_appear_once_as_valid"] is not True:
        raise RuntimeError("not every row appears exactly once as validation")
    if checks["student_location_overlap_count_all_folds"] != 0:
        raise RuntimeError("student.location leakage detected in split manifest")
    if checks["raw_text_copied"]:
        raise RuntimeError("split artifact leakage policy violated")
    if manifest_doc["hard_blocks"]:
        raise RuntimeError("; ".join(manifest_doc["hard_blocks"]))


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output)
    df, source_audit_table, source_audit_table_sha = load_split_table(args)
    require_columns(df)
    df, region_map = apply_group_key(df, args.group_key, args.region_map)
    df = df.sort_values("relative_path").reset_index(drop=True)
    group_column = selected_group_column(args.group_key)

    folds = build_folds(df, args.k, args.seed, group_column)
    fold_docs = write_folds(args, output_dir, folds)
    row_manifest_paths = write_split_row_manifests(args, output_dir, folds)
    manifest_doc = manifest(
        args=args,
        output_dir=output_dir,
        df=df,
        source_audit_table=source_audit_table,
        source_audit_table_sha=source_audit_table_sha,
        folds=folds,
        fold_docs=fold_docs,
        region_map=region_map,
        row_manifest_paths=row_manifest_paths,
    )
    write_yaml(output_dir / "split_manifest.yaml", manifest_doc)
    (output_dir / "split_leakage_check.md").write_text(
        leakage_report(manifest_doc), encoding="utf-8"
    )
    validate_manifest(manifest_doc)

    print(
        f"wrote {args.k} folds to {output_dir}; "
        f"split_hash={manifest_doc['split_hash']}; "
        f"warnings={len(manifest_doc['warnings'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
