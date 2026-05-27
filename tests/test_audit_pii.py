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
