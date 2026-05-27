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
    annotated: List[Tuple[Path, Tuple[str, str, str]]] = []
    for p in all_paths:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            key = extract_strat_keys(doc)
        except (json.JSONDecodeError, KeyError, OSError):
            continue
        annotated.append((p, key))

    selected = stratified_sample(
        annotated, key_fn=lambda x: x[1], target_n=args.target_n, seed=args.seed
    )
    selected_paths = [p for p, _ in selected]

    out = Path(args.out)
    mirror_files(selected_paths, src_root=src, dst_root=out)
    manifest = write_manifest(selected_paths, src_root=src, dst_root=out, target_n=args.target_n, seed=args.seed)

    print(
        f"extracted {manifest['actual_n']} / target {manifest['target_n']} "
        f"across {len(manifest['by_stratum'])} strata -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
