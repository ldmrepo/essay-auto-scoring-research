"""Tests for pipelines.extract_5k — stratified 5K subsample extractor."""

import json
from pathlib import Path

import pytest

from pipelines.extract_5k import extract_strat_keys, validate_rubric_for_phase3


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
        "score": {
            "essay_scoreT_avg": 20.0,
            "essay_scoreT_detail": _valid_score_detail(),
        },
        "rubric": _valid_rubric(),
    }


def _valid_rubric():
    return {
        "expression_weight": {
            "exp_grammar": 3,
            "exp_vocab": 3,
            "exp_style": 0,
            "exp": 3,
        },
        "organization_weight": {
            "org_paragraph": 0,
            "org_essay": 7,
            "org_coherence": 2,
            "org_quantity": 1,
            "org": 3,
        },
        "content_weight": {
            "con_clearance": 4,
            "con_description": 2,
            "con_novelty": 2,
            "con_prompt": 1,
            "con": 4,
        },
    }


def _valid_score_detail():
    return {
        "essay_scoreT_exp": [[3, 2, 0], [3, 3, 0], [2, 3, 0]],
        "essay_scoreT_org": [[3, 0, 3, 3], [2, 0, 3, 2], [2, 0, 2, 3]],
        "essay_scoreT_cont": [[3, 3, 3, 2], [3, 2, 3, 2], [2, 2, 2, 3]],
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


class TestValidateRubricForPhase3:
    def test_valid_schema_passes(self):
        ok, reason = validate_rubric_for_phase3(_essay())
        assert ok is True
        assert reason == ""

    def test_missing_macro_weight_fails(self):
        d = _essay()
        del d["rubric"]["expression_weight"]["exp"]
        ok, reason = validate_rubric_for_phase3(d)
        assert ok is False
        assert "rubric.expression_weight.exp macro weight missing" in reason

    def test_non_numeric_sub_weight_fails(self):
        d = _essay()
        d["rubric"]["content_weight"]["con_clearance"] = "4"
        ok, reason = validate_rubric_for_phase3(d)
        assert ok is False
        assert "non-numeric sub-weights" in reason

    def test_score_detail_shape_fails(self):
        d = _essay()
        d["score"]["essay_scoreT_detail"]["essay_scoreT_org"][0] = [3, 0, 3]
        ok, reason = validate_rubric_for_phase3(d)
        assert ok is False
        assert "essay_scoreT_org rater 0 length must be 4" in reason

    def test_overall_raw_range_fails(self):
        d = _essay()
        d["score"]["essay_scoreT_avg"] = 31
        ok, reason = validate_rubric_for_phase3(d)
        assert ok is False
        assert "outside 0~30" in reason


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


def _write_essay(root: Path, essay_type: str, grade_group: str, level: str, essay_id: str) -> Path:
    """Create a single essay json under root/<essay_type>/<filename> mirroring real schema."""
    sub = root / essay_type
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"{essay_type}_{grade_group}_{essay_id}.json"
    doc = {
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
        "score": {
            "essay_scoreT_avg": 20.0,
            "essay_scoreT_detail": _valid_score_detail(),
        },
        "rubric": _valid_rubric(),
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


class TestMirrorFiles:
    def test_mirrors_directory_tree(self, tmp_path):
        from pipelines.extract_5k import mirror_files

        src_root = tmp_path / "src"
        dst_root = tmp_path / "dst"
        a = _write_essay(src_root, "글짓기", "초등", "1", "ESSAY_A")
        b = _write_essay(src_root, "주장", "중등", "2", "ESSAY_B")

        mirror_files([a, b], src_root=src_root, dst_root=dst_root)

        assert (dst_root / "글짓기" / "글짓기_초등_ESSAY_A.json").is_file()
        assert (dst_root / "주장" / "주장_중등_ESSAY_B.json").is_file()

    def test_skips_source_root_prefix(self, tmp_path):
        # The output path strips the src_root prefix and reuses everything below.
        from pipelines.extract_5k import mirror_files

        src_root = tmp_path / "deep" / "nested" / "src"
        dst_root = tmp_path / "out"
        a = _write_essay(src_root, "설명글", "고등", "3", "ESSAY_C")

        mirror_files([a], src_root=src_root, dst_root=dst_root)
        assert (dst_root / "설명글" / "설명글_고등_ESSAY_C.json").is_file()
        # No accidental nesting under "deep/nested/src"
        assert not (dst_root / "deep").exists()

    def test_preserves_file_contents(self, tmp_path):
        from pipelines.extract_5k import mirror_files

        src_root = tmp_path / "src"
        dst_root = tmp_path / "dst"
        a = _write_essay(src_root, "찬성반대", "중등", "2", "ESSAY_D")
        original = a.read_text(encoding="utf-8")

        mirror_files([a], src_root=src_root, dst_root=dst_root)
        copied = (dst_root / "찬성반대" / "찬성반대_중등_ESSAY_D.json").read_text(encoding="utf-8")
        assert copied == original

    def test_raises_when_path_outside_src_root(self, tmp_path):
        from pipelines.extract_5k import mirror_files

        src_root = tmp_path / "src"
        src_root.mkdir()
        outside = tmp_path / "outside.json"
        outside.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="not under src_root"):
            mirror_files([outside], src_root=src_root, dst_root=tmp_path / "dst")


class TestExtractCli:
    def _build_dataset(self, root: Path) -> None:
        """48 essays across 8 strata (2 type × 2 grade × 2 level × 6 ids = 48 total)."""
        eid = 0
        for et in ("글짓기", "주장"):
            for gg in ("초등", "중등"):
                for lvl in ("1", "2"):
                    for _ in range(6):  # 6 essays per stratum, 8 strata = 48 total
                        eid += 1
                        _write_essay(root, et, gg, lvl, f"ESSAY_{eid:03d}")

    def test_end_to_end_extracts_target_count_with_manifest(self, tmp_path):
        from pipelines.extract_5k import _main

        src_root = tmp_path / "src" / "라벨링데이터"
        dst_root = tmp_path / "out"
        self._build_dataset(src_root)

        rc = _main([
            str(src_root.parent),  # walk script accepts the labeled-data root container
            "--out", str(dst_root),
            "--target-n", "16",
            "--seed", "42",
        ])
        assert rc == 0

        # Output mirrors the src tree under dst_root
        copied = list(dst_root.rglob("*.json"))
        # 16 essay copies + 1 manifest.json (manifest may live in dst_root top-level)
        json_files = [p for p in copied if p.name != "manifest.json"]
        assert len(json_files) == 16

        # Manifest exists with expected schema
        manifest_path = dst_root / "manifest.json"
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["target_n"] == 16
        assert manifest["actual_n"] == 16
        assert manifest["seed"] == 42
        assert "by_stratum" in manifest
        # 8 strata × 2 essays each (16/8) = 2 per stratum
        assert all(v == 2 for v in manifest["by_stratum"].values())

    def test_validate_rubric_flag_skips_schema_drift(self, tmp_path):
        from pipelines.extract_5k import _main

        src_root = tmp_path / "src" / "라벨링데이터"
        dst_root = tmp_path / "out"
        valid_path = _write_essay(src_root, "글짓기", "초등", "1", "ESSAY_VALID")
        invalid_path = _write_essay(src_root, "글짓기", "초등", "1", "ESSAY_INVALID")
        invalid_doc = json.loads(invalid_path.read_text(encoding="utf-8"))
        del invalid_doc["rubric"]["expression_weight"]["exp"]
        invalid_path.write_text(json.dumps(invalid_doc, ensure_ascii=False), encoding="utf-8")

        rc = _main([
            str(src_root.parent),
            "--out", str(dst_root),
            "--target-n", "2",
            "--seed", "42",
            "--validate-rubric",
        ])
        assert rc == 0

        copied = [p.name for p in dst_root.rglob("*.json") if p.name != "manifest.json"]
        assert copied == [valid_path.name]
        manifest = json.loads((dst_root / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["actual_n"] == 1
        assert manifest["drift_skipped"]["total"] == 1
        assert "rubric.expression_weight.exp macro weight missing" in manifest["drift_skipped"]["by_reason"]

    def test_deterministic_end_to_end(self, tmp_path):
        from pipelines.extract_5k import _main

        src = tmp_path / "src" / "라벨링데이터"
        self._build_dataset(src)

        out1 = tmp_path / "o1"
        out2 = tmp_path / "o2"
        _main([str(src.parent), "--out", str(out1), "--target-n", "16", "--seed", "42"])
        _main([str(src.parent), "--out", str(out2), "--target-n", "16", "--seed", "42"])

        files1 = sorted(p.name for p in out1.rglob("*.json") if p.name != "manifest.json")
        files2 = sorted(p.name for p in out2.rglob("*.json") if p.name != "manifest.json")
        assert files1 == files2

    def test_missing_src_returns_error(self, tmp_path):
        from pipelines.extract_5k import _main

        rc = _main([str(tmp_path / "does_not_exist"), "--out", str(tmp_path / "o"), "--target-n", "5"])
        assert rc == 2
