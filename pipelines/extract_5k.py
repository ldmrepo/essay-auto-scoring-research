"""Stratified 5K subsample extractor for the AI Hub essay dataset.

Reads from a labeled essay tree (`dataset/1.Training/라벨링데이터/<essay_type>/*.json`),
samples proportionally across essay_type × student_grade_group × essay_level strata,
and mirrors the selected JSONs into an output tree (e.g. `dataset/sample_5k/`).

Read-only over the input. Deterministic given a seed.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple, TypeVar


def extract_strat_keys(doc: dict) -> Tuple[str, str, str]:
    """Return (essay_type, student_grade_group, essay_level) for stratification.

    Raises KeyError with the missing field name if any required key is absent.
    """
    info = doc.get("info") or {}
    student = doc.get("student") or {}

    if "essay_type" not in info:
        raise KeyError("essay_type")
    if "essay_level" not in info:
        raise KeyError("essay_level")
    if "student_grade_group" not in student:
        raise KeyError("student_grade_group")

    return (info["essay_type"], student["student_grade_group"], info["essay_level"])


def validate_rubric_for_phase3(doc: dict) -> Tuple[bool, str]:
    """Phase 3 multi-task rubric pre-validation (R1-NNF1 fix — extract_5k에 skip 로직).

    스펙 v1.1.x `compute_rubric_targets` 가 요구하는 rubric sub-weight 키 + score detail 키와
    숫자/shape 제약을 검증. Phase 3 학습 전 dataset 단계에서 spec drift essay를 사전 skip 가능.

    Returns:
        (ok, reason): ok=True면 학습 가능, ok=False면 reason 메시지 (skip 사유)

    필수 schema:
        - rubric.expression_weight: {exp_grammar, exp_vocab, exp_style}
        - rubric.organization_weight: {org_paragraph, org_essay, org_coherence, org_quantity}
        - rubric.content_weight: {con_clearance, con_description, con_novelty, con_prompt}
        - rubric macro weights: expression_weight.exp / organization_weight.org / content_weight.con
        - score.essay_scoreT_detail: 3 raters each, lengths exp=3/org=4/cont=4, values 0~3
        - score.essay_scoreT_avg: numeric overall raw 0~30

    호출 시점:
        - dataset/sample_5k/ 추출 시 (extract_5k.py main loop) — drift 발견 시 skip + 통계 출력
        - Phase 3 학습 직전 (pipelines/train_transformer.py) — drift 0 보장 확인
    """
    rubric = doc.get("rubric") or {}
    score = doc.get("score") or {}

    # 소분류 sub-weight 키 (스펙 v1.1.x § 7.2)
    expected_subs = {
        "expression_weight": ["exp_grammar", "exp_vocab", "exp_style"],
        "organization_weight": ["org_paragraph", "org_essay", "org_coherence", "org_quantity"],
        "content_weight": ["con_clearance", "con_description", "con_novelty", "con_prompt"],
    }
    for macro_key, sub_keys in expected_subs.items():
        macro = rubric.get(macro_key)
        if not isinstance(macro, dict):
            return False, f"rubric.{macro_key} missing or not dict"
        missing = [k for k in sub_keys if k not in macro]
        if missing:
            return False, f"rubric.{macro_key} missing sub-keys: {missing}"
        non_numeric = [k for k in sub_keys if not _is_number(macro.get(k))]
        if non_numeric:
            return False, f"rubric.{macro_key} non-numeric sub-weights: {non_numeric}"
        if sum(float(macro[k]) for k in sub_keys) <= 0:
            return False, f"rubric.{macro_key} sub-weight sum must be > 0"

    expected_macro_weights = {
        "expression_weight": "exp",
        "organization_weight": "org",
        "content_weight": "con",
    }
    for macro_key, weight_key in expected_macro_weights.items():
        if weight_key not in rubric[macro_key]:
            return False, f"rubric.{macro_key}.{weight_key} macro weight missing"
        if not _is_number(rubric[macro_key][weight_key]):
            return False, f"rubric.{macro_key}.{weight_key} macro weight non-numeric"

    if sum(float(rubric[macro_key][weight_key]) for macro_key, weight_key in expected_macro_weights.items()) <= 0:
        return False, "rubric macro weight sum must be > 0"

    # score detail
    detail = score.get("essay_scoreT_detail") or {}
    expected_detail_lengths = {
        "essay_scoreT_exp": 3,
        "essay_scoreT_org": 4,
        "essay_scoreT_cont": 4,
    }
    for key, expected_len in expected_detail_lengths.items():
        if key not in detail:
            return False, f"score.essay_scoreT_detail.{key} missing"
        ok, reason = _validate_score_detail_matrix(detail[key], expected_len)
        if not ok:
            return False, f"score.essay_scoreT_detail.{key} {reason}"

    # overall raw
    if "essay_scoreT_avg" not in score:
        return False, "score.essay_scoreT_avg missing"
    if not _is_number(score["essay_scoreT_avg"]):
        return False, "score.essay_scoreT_avg non-numeric"
    overall = float(score["essay_scoreT_avg"])
    if overall < 0 or overall > 30:
        return False, "score.essay_scoreT_avg outside 0~30"

    return True, ""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_score_detail_matrix(value: object, expected_len: int) -> Tuple[bool, str]:
    if not isinstance(value, list) or len(value) != 3:
        return False, "must contain 3 rater rows"
    for idx, row in enumerate(value):
        if not isinstance(row, list) or len(row) != expected_len:
            return False, f"rater {idx} length must be {expected_len}"
        for score in row:
            if not _is_number(score):
                return False, f"rater {idx} has non-numeric score"
            score_f = float(score)
            if score_f < 0 or score_f > 3:
                return False, f"rater {idx} score outside 0~3"
    return True, ""


T = TypeVar("T")


def stratified_sample(
    items: Iterable[T],
    key_fn: Callable[[T], object],
    target_n: int,
    seed: int = 42,
) -> List[T]:
    """Proportional stratified sample.

    Each stratum k receives n_k = round(target_n * |stratum_k| / total), capped at |stratum_k|.
    Order of returned items is grouped by stratum key, then in stratum-sample order.
    Deterministic for a given (items, key_fn, target_n, seed).
    """
    items = list(items)
    if target_n <= 0 or not items:
        return []

    rng = random.Random(seed)
    groups: dict[object, List[T]] = defaultdict(list)
    for item in items:
        groups[key_fn(item)].append(item)

    total = len(items)
    sampled: List[T] = []
    for key in sorted(groups, key=lambda k: str(k)):
        group = groups[key]
        n = round(target_n * len(group) / total)
        n = min(n, len(group))
        if n > 0:
            sampled.extend(rng.sample(group, n))
    return sampled


def mirror_files(paths: Sequence[Path], src_root: Path, dst_root: Path) -> None:
    """Copy each input path to `dst_root / <path relative to src_root>`.

    Raises ValueError if any path is not under src_root.
    Creates parent directories as needed. Overwrites existing dst files.
    """
    src_root = Path(src_root).resolve()
    dst_root = Path(dst_root).resolve()

    for p in paths:
        p_resolved = Path(p).resolve()
        try:
            rel = p_resolved.relative_to(src_root)
        except ValueError as e:
            raise ValueError(f"not under src_root: {p} (src_root={src_root})") from e
        out = dst_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p_resolved, out)


def write_manifest(
    selected_paths: Sequence[Path],
    src_root: Path,
    dst_root: Path,
    target_n: int,
    seed: int,
) -> dict:
    """Write manifest.json to dst_root and return the manifest dict.

    Schema:
      root, src_root, target_n, actual_n, seed, by_stratum (str_key -> count), files[]
    """
    by_stratum: Counter = Counter()
    files: List[str] = []
    src_root_resolved = Path(src_root).resolve()
    for p in selected_paths:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        key = "|".join(extract_strat_keys(doc))
        by_stratum[key] += 1
        files.append(str(Path(p).resolve().relative_to(src_root_resolved)))

    manifest = {
        "root": str(Path(dst_root).resolve()),
        "src_root": str(src_root_resolved),
        "target_n": target_n,
        "actual_n": len(selected_paths),
        "seed": seed,
        "by_stratum": dict(by_stratum),
        "files": files,
    }
    dst_root = Path(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)
    (dst_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def _main(argv: List[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python3 -m pipelines.extract_5k",
        description="Extract stratified subsample (target ≈ 5K) from labeled essay tree.",
    )
    parser.add_argument(
        "src",
        help="Source root containing 라벨링데이터/<essay_type>/*.json (e.g. dataset/1.Training)",
    )
    parser.add_argument("--out", required=True, help="Output root for mirrored subsample")
    parser.add_argument("--target-n", type=int, default=5000, help="Target sample size")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    # R1 5차 NEW-R1 fix: --validate-rubric flag 등록 (이전 Edit string 미일치로 누락)
    # Phase 3 multi-task rubric pre-validation (opt-in). 기본 OFF (Phase 2 호환).
    # Phase 3 학습 진입 시 ON 의무 (R1-NNF1 + R1-REG-H1 + R1 5차 NEW-R5)
    parser.add_argument(
        "--validate-rubric",
        action="store_true",
        default=False,
        help="Phase 3 multi-task rubric pre-validation (skip essays with spec drift). "
             "Phase 3 학습 진입 시 ON 의무. Phase 2 toy/test 호환 위해 기본 OFF.",
    )
    args = parser.parse_args(argv)

    src = Path(args.src)
    if not src.is_dir():
        sys.stderr.write(f"ERROR: src does not exist or is not a directory: {src}\n")
        return 2

    # Walk src for *.json (typically under 라벨링데이터/)
    all_paths = sorted(src.rglob("*.json"))
    if not all_paths:
        sys.stderr.write(f"ERROR: no .json files found under {src}\n")
        return 2

    # Pair (path, key) for stratification
    # R1-REG-H1 + R1-NNF1 fix: opt-in rubric pre-validation
    annotated: List[Tuple[Path, Tuple[str, str, str]]] = []
    drift_skipped: dict[str, int] = defaultdict(int)
    drift_skipped_total = 0
    validate_rubric_enabled = bool(getattr(args, "validate_rubric", False))
    for p in all_paths:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            key = extract_strat_keys(doc)
        except (json.JSONDecodeError, KeyError, OSError):
            continue
        # Phase 3 multi-task rubric pre-validation (opt-in via --validate-rubric)
        if validate_rubric_enabled:
            ok, reason = validate_rubric_for_phase3(doc)
            if not ok:
                drift_skipped[reason] += 1
                drift_skipped_total += 1
                continue
        annotated.append((p, key))

    if drift_skipped_total > 0:
        sys.stderr.write(
            f"INFO: skipped {drift_skipped_total} essays due to rubric spec drift "
            f"({len(drift_skipped)} unique reasons). See manifest.drift_skipped for details.\n"
        )

    selected = stratified_sample(
        annotated, key_fn=lambda x: x[1], target_n=args.target_n, seed=args.seed
    )
    selected_paths = [p for p, _ in selected]

    out = Path(args.out)
    mirror_files(selected_paths, src_root=src, dst_root=out)
    manifest = write_manifest(selected_paths, src_root=src, dst_root=out, target_n=args.target_n, seed=args.seed)
    # R1-REG-H1: drift_skipped 통계 manifest에 추가 (V8 시나리오 evidence)
    manifest["drift_skipped"] = {
        "validate_rubric_enabled": validate_rubric_enabled,
        "total": drift_skipped_total,
        "by_reason": dict(drift_skipped),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    suffix = f" (rubric drift skipped: {drift_skipped_total})" if validate_rubric_enabled else ""
    print(
        f"extracted {manifest['actual_n']} / target {manifest['target_n']} "
        f"across {len(manifest['by_stratum'])} strata -> {out}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
