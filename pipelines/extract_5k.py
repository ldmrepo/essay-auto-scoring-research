"""Stratified 5K subsample extractor for the AI Hub essay dataset.

Reads from a labeled essay tree (`dataset/1.Training/라벨링데이터/<essay_type>/*.json`),
samples proportionally across essay_type × student_grade_group × essay_level strata,
and mirrors the selected JSONs into an output tree (e.g. `dataset/sample_5k/`).

Read-only over the input. Deterministic given a seed.
"""

from __future__ import annotations

import random
import shutil
from collections import defaultdict
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
