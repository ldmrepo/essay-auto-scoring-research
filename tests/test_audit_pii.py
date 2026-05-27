"""Tests for pipelines.audit_pii — PII detection + essay_id hashing for vast.ai upload."""

import pytest
from pathlib import Path

from pipelines.audit_pii import detect_pii


class TestDetectPii:
    def test_clean_text_returns_empty_list(self):
        text = "미래에는 엄청난 일들이 벌어질 것 같다."
        assert detect_pii(text) == []

    def test_detects_korean_mobile_phone(self):
        text = "연락처는 010-1234-5678 입니다."
        hits = detect_pii(text)
        assert any(h["type"] == "phone" and "010-1234-5678" in h["match"] for h in hits)

    def test_detects_email(self):
        text = "이메일은 minsoo@example.com 입니다."
        hits = detect_pii(text)
        assert any(h["type"] == "email" and h["match"] == "minsoo@example.com" for h in hits)

    def test_detects_school_name(self):
        text = "저는 서울대학교사범대학부설초등학교 학생입니다."
        hits = detect_pii(text)
        assert any(h["type"] == "school" and "초등학교" in h["match"] for h in hits)

    def test_detects_korean_personal_name(self):
        text = "저는 김민수입니다."
        hits = detect_pii(text)
        assert any(h["type"] == "person_name" and h["match"] == "김민수" for h in hits)

    def test_does_not_flag_common_noun_without_trigger(self):
        # 한국어 일반명사는 흔한 한자어 어휘로 false positive 위험 — 이름 패턴은 보수적으로
        text = "환경오염, 바이러스, 사회문제"
        hits = [h for h in detect_pii(text) if h["type"] == "person_name"]
        assert hits == [], f"unexpected name match: {hits}"

    def test_does_not_flag_common_occupation_noun_after_trigger(self):
        # 흔한 K-12 self-intro 패턴: "저는 [직업/역할]입니다" — name이 아니라 일반명사.
        # COMMON_NOUNS_AFTER_TRIGGER 가드가 동작해야 함.
        for text in ("저는 학생입니다.", "저는 교사이고", "저는 어머니입니다."):
            hits = [h for h in detect_pii(text) if h["type"] == "person_name"]
            assert hits == [], f"false positive on {text!r}: {hits}"

    def test_does_not_flag_object_particle_after_trigger(self):
        # K-12 essays: "저는 [명사를/명사에] ~~한다" 패턴 false positive 방지
        # 조사가 lookahead의 \s|$를 트리거하면 안 됨 (Task 6 sample audit 168 hits 회귀 방지)
        for text in (
            "저는 과자를 좋아한다.",
            "저는 매일 학교에 간다.",
            "저는 바다에서 수영을 한다.",
            "저는 친구와 영화를 봤다.",
        ):
            hits = [h for h in detect_pii(text) if h["type"] == "person_name"]
            assert hits == [], f"false positive on {text!r}: {hits}"

    def test_does_not_overmatch_phone_in_long_digit_string(self):
        # 단어 경계 가드: 11자리 휴대전화 패턴이 더 긴 숫자열에 embedded 시 매치 금지.
        text = "주문번호 0101234567812345"
        hits = [h for h in detect_pii(text) if h["type"] == "phone"]
        assert hits == [], f"phone over-match: {hits}"


class TestHashEssayId:
    def test_returns_16_char_lowercase_hex(self):
        from pipelines.audit_pii import hash_essay_id

        out = hash_essay_id("ESSAY_33474")
        assert len(out) == 16
        assert all(c in "0123456789abcdef" for c in out)

    def test_is_deterministic(self):
        from pipelines.audit_pii import hash_essay_id

        assert hash_essay_id("ESSAY_33474") == hash_essay_id("ESSAY_33474")

    def test_distinct_ids_produce_distinct_hashes(self):
        from pipelines.audit_pii import hash_essay_id

        ids = ["ESSAY_33474", "ESSAY_33475", "ESSAY_99999", "ESSAY_00001"]
        hashes = {hash_essay_id(i) for i in ids}
        assert len(hashes) == len(ids), f"hash collision: {hashes}"


class TestAuditFile:
    FIXTURES = Path(__file__).parent / "fixtures"

    def test_clean_fixture_returns_zero_detections(self):
        from pipelines.audit_pii import audit_file

        report = audit_file(str(self.FIXTURES / "essay_clean.json"))
        assert report["pii_count"] == 0
        assert report["hits"] == []
        assert report["essay_id_original"] == "ESSAY_33474"
        assert len(report["essay_id_hashed"]) == 16

    def test_pii_fixture_detects_at_least_four_categories(self):
        from pipelines.audit_pii import audit_file

        report = audit_file(str(self.FIXTURES / "essay_with_pii.json"))
        types = {h["type"] for h in report["hits"]}
        assert {"phone", "email", "school", "person_name"}.issubset(types), f"missing types: {types}"
        assert report["pii_count"] >= 4
        assert report["essay_id_original"] == "ESSAY_99999"

    def test_report_includes_relative_path(self):
        from pipelines.audit_pii import audit_file

        report = audit_file(str(self.FIXTURES / "essay_clean.json"))
        assert report["path"].endswith("essay_clean.json")

    def test_rejects_non_dict_json(self, tmp_path):
        from pipelines.audit_pii import audit_file
        bad = tmp_path / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="Expected JSON object"):
            audit_file(str(bad))


class TestAuditDirectory:
    FIXTURES = Path(__file__).parent / "fixtures"

    def test_aggregates_two_files(self, tmp_path):
        from pipelines.audit_pii import audit_directory

        sub = tmp_path / "원천데이터" / "글짓기"
        sub.mkdir(parents=True)
        for name in ("essay_clean.json", "essay_with_pii.json"):
            (sub / name).write_text(
                (self.FIXTURES / name).read_text(encoding="utf-8"), encoding="utf-8"
            )

        result = audit_directory(str(tmp_path))
        assert result["total_files"] == 2
        assert result["files_with_pii"] == 1
        assert result["total_pii_hits"] >= 4
        assert len(result["per_file"]) == 2

    def test_empty_directory_returns_zero_files(self, tmp_path):
        from pipelines.audit_pii import audit_directory

        result = audit_directory(str(tmp_path))
        assert result["total_files"] == 0
        assert result["per_file"] == []

    def test_cli_rejects_nonexistent_path(self, tmp_path, capsys):
        from pipelines.audit_pii import _main

        missing = tmp_path / "does_not_exist"
        rc = _main([str(missing), "--report", str(tmp_path / "r.json"), "--fail-on-hit"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "does not exist or is not a directory" in err
