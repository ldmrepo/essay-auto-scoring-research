"""Stratified 5K subsample extractor for the AI Hub essay dataset.

Reads from a labeled essay tree (`dataset/1.Training/라벨링데이터/<essay_type>/*.json`),
samples proportionally across essay_type × student_grade_group × essay_level strata,
and mirrors the selected JSONs into an output tree (e.g. `dataset/sample_5k/`).

Read-only over the input. Deterministic given a seed.
"""

from __future__ import annotations

from typing import Tuple


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
