"""Tests for pipelines.extract_5k — stratified 5K subsample extractor."""

import json
from pathlib import Path

import pytest

from pipelines.extract_5k import extract_strat_keys


def _essay(essay_type="글짓기", grade_group="중등", level="2", essay_id="ESSAY_1"):
    """Minimal valid essay doc matching real schema."""
    return {
        "info": {
            "essay_id": essay_id,
            "essay_type": essay_type,
            "essay_level": level,
            "essay_prompt": "테스트",
            "essay_len": 50,
        },
        "student": {
            "student_grade_group": grade_group,
            "student_grade": f"{grade_group}_1학년",
            "location": "001",
        },
        "paragraph": [{"paragraph_txt": "테스트 본문", "paragraph_id": "001"}],
        "score": {"essay_scoreT_avg": 20.0},
    }


class TestExtractStratKeys:
    def test_returns_three_tuple(self):
        result = extract_strat_keys(_essay())
        assert result == ("글짓기", "중등", "2")

    def test_each_field_distinct(self):
        d = _essay(essay_type="설명글", grade_group="초등", level="1")
        assert extract_strat_keys(d) == ("설명글", "초등", "1")

    def test_missing_essay_type_raises(self):
        d = _essay()
        del d["info"]["essay_type"]
        with pytest.raises(KeyError, match="essay_type"):
            extract_strat_keys(d)

    def test_missing_grade_group_raises(self):
        d = _essay()
        del d["student"]["student_grade_group"]
        with pytest.raises(KeyError, match="student_grade_group"):
            extract_strat_keys(d)

    def test_missing_essay_level_raises(self):
        d = _essay()
        del d["info"]["essay_level"]
        with pytest.raises(KeyError, match="essay_level"):
            extract_strat_keys(d)
