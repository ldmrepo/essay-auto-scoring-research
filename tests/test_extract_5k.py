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


class TestStratifiedSample:
    def test_proportional_by_group_size(self):
        # 100 items: 60 type A, 30 type B, 10 type C → target 10 ≈ 6/3/1
        from pipelines.extract_5k import stratified_sample

        items = (
            [("A", i) for i in range(60)]
            + [("B", i) for i in range(30)]
            + [("C", i) for i in range(10)]
        )
        result = stratified_sample(items, key_fn=lambda x: x[0], target_n=10, seed=42)
        from collections import Counter

        c = Counter(k for k, _ in result)
        assert c["A"] == 6
        assert c["B"] == 3
        assert c["C"] == 1
        assert len(result) == 10

    def test_deterministic_with_same_seed(self):
        from pipelines.extract_5k import stratified_sample

        items = [("X", i) for i in range(50)]
        r1 = stratified_sample(items, key_fn=lambda x: x[0], target_n=10, seed=42)
        r2 = stratified_sample(items, key_fn=lambda x: x[0], target_n=10, seed=42)
        assert r1 == r2

    def test_different_seed_gives_different_sample(self):
        from pipelines.extract_5k import stratified_sample

        items = [("X", i) for i in range(50)]
        r1 = stratified_sample(items, key_fn=lambda x: x[0], target_n=10, seed=1)
        r2 = stratified_sample(items, key_fn=lambda x: x[0], target_n=10, seed=2)
        assert r1 != r2

    def test_undersized_stratum_takes_all_available(self):
        # 5 items in stratum, request would round to 10 → take all 5
        from pipelines.extract_5k import stratified_sample

        items = (
            [("A", i) for i in range(95)]   # → 95 (90% of target 100)
            + [("B", i) for i in range(5)]   # → 5 (capped at available)
        )
        result = stratified_sample(items, key_fn=lambda x: x[0], target_n=100, seed=42)
        from collections import Counter

        c = Counter(k for k, _ in result)
        assert c["B"] == 5  # all available, not 10
        assert c["A"] == 95
        assert len(result) == 100

    def test_target_n_zero_returns_empty(self):
        from pipelines.extract_5k import stratified_sample

        items = [("X", i) for i in range(50)]
        assert stratified_sample(items, key_fn=lambda x: x[0], target_n=0, seed=42) == []

    def test_empty_items_returns_empty(self):
        from pipelines.extract_5k import stratified_sample

        assert stratified_sample([], key_fn=lambda x: x[0], target_n=10, seed=42) == []
