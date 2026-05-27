# Vast.ai Phase 2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 2 mid-scale 학습을 vast.ai 원격 GPU에 안전하게 위탁하기 위한 보안 hardening(`.env` 차단, API 키 외부화), PII audit 도구(`pipelines/audit_pii.py`), Essay 도메인 작업 guide v2 정비를 한 번에 마무리한다.

**Architecture:**
- `.gitignore` + `.env.example`로 secret을 git history에서 영구 차단
- `pipelines/audit_pii.py` (TDD)로 vast.ai 업로드 전 essay 데이터셋의 PII regex audit + `essay_id` 해시화 (제거가 아닌 audit-only, 학습 성능 영향 0)
- `VAST_GPU_GUIDE.md` v2를 Whisper 도메인 → Essay/RoBERTa 도메인으로 재작성, API 키 hardcoded → `.env` load 패턴
- `docs/research/vast_ai_essay_workflow_v_1_0.md`에 비용·데이터 흐름·위험·자동 destroy trap 등 운영 evidence 기록

**Tech Stack:** Python 3.11, pytest, stdlib (`re`, `json`, `hashlib`, `pathlib`, `argparse`), vast.ai CLI, git

---

## File Structure

| File | 역할 | 신규/수정 |
|---|---|---|
| `.gitignore` | secret 패턴(`.env`, `.env.*`) 추가 | 수정 |
| `.env.example` | 키 placeholder 템플릿 | 신규 |
| `VAST_GPU_GUIDE.md` | Essay 도메인 vast.ai 운영 가이드 v2 | 전면 재작성 |
| `pipelines/__init__.py` | 패키지 마커 (없으면 신규) | 조건부 신규 |
| `pipelines/audit_pii.py` | PII detect + essay_id hash + 디렉토리 walker + CLI | 신규 |
| `tests/__init__.py` | 테스트 패키지 마커 | 신규 |
| `tests/test_audit_pii.py` | audit_pii 단위/통합 테스트 | 신규 |
| `tests/fixtures/essay_clean.json` | PII 없는 essay sample (audit 0건 expected) | 신규 |
| `tests/fixtures/essay_with_pii.json` | PII 박힌 essay sample (이름/전화/이메일/학교) | 신규 |
| `docs/research/vast_ai_essay_workflow_v_1_0.md` | Essay × vast.ai 운영 evidence | 신규 |

PII audit은 학습용 원본 데이터를 변경하지 않는다 (Phase 1에서 `student.location` 등이 group key로 쓰임 — 제거 시 leak/split 영향). 외부 compute로 전송하기 전 위험 신호를 감지하고 `essay_id`만 hash로 치환한 사본을 export 한다.

---

### Task 1: `.gitignore` + `.env.example`로 secret 차단

**Files:**
- Modify: `/home/dev/work/essay-auto-scoring-research/.gitignore`
- Create: `/home/dev/work/essay-auto-scoring-research/.env.example`

- [ ] **Step 1: `.gitignore` 끝부분에 secret 섹션 추가**

`/home/dev/work/essay-auto-scoring-research/.gitignore`의 마지막 줄(`*:Zone.Identifier`) 다음에 아래 블록을 추가:

```gitignore

# Secrets — never commit
.env
.env.*
!.env.example
```

(`!.env.example`는 예외 — 템플릿은 추적)

- [ ] **Step 2: `.env.example` 신규 작성**

`/home/dev/work/essay-auto-scoring-research/.env.example` 전체:

```dotenv
# Vast.ai API key (https://vast.ai/console/account/)
# Copy this file to .env and replace the placeholder.
# Never commit .env.
VAST_API_KEY=replace-with-your-vast-api-key
```

- [ ] **Step 3: `.env`가 무시되는지 + `.env.example`은 추적되는지 검증**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git check-ignore -v .env && \
  git check-ignore -v .env.example; echo "exit=$?"
```

Expected:
- 1번째: `.gitignore:N:.env\t.env` 출력 (무시됨, exit 0)
- 2번째: 아무 출력 없고 `exit=1` (무시되지 않음 — `!.env.example` 예외 작동)

- [ ] **Step 4: 현재 staged 상태에서 `.env`가 절대 포함되지 않는지 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add -n .env 2>&1 | grep -E '(ignored|nothing)' || echo "WARN: .env would be added"
```

Expected: `The following paths are ignored by one of your .gitignore files: .env` 출력.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add .gitignore .env.example && \
  git commit -m "chore(security): ignore .env, add .env.example template

Vast.ai 진입 준비. .env 파일에 보관된 API 키가
실수로 git history에 박히지 않도록 .gitignore 보강.
.env.example을 placeholder로 추적하여 setup 절차를 문서화."
```

Expected: `2 files changed` (1 modify + 1 create).

---

### Task 2: 테스트 fixture 작성 — clean / PII 박힌 essay JSON

**Files:**
- Create: `/home/dev/work/essay-auto-scoring-research/tests/__init__.py` (빈 파일)
- Create: `/home/dev/work/essay-auto-scoring-research/tests/fixtures/essay_clean.json`
- Create: `/home/dev/work/essay-auto-scoring-research/tests/fixtures/essay_with_pii.json`

기존 sample은 이미 정제되어 있어 PII detection 회귀 테스트가 불가능. 합성 fixture로 양/음성 모두 보장한다.

- [ ] **Step 1: 빈 `tests/__init__.py` 생성**

`/home/dev/work/essay-auto-scoring-research/tests/__init__.py` 전체:

```python
```

- [ ] **Step 2: PII가 없는 clean fixture 작성**

`/home/dev/work/essay-auto-scoring-research/tests/fixtures/essay_clean.json` 전체:

```json
{
  "paragraph": [
    {
      "paragraph_txt": "미래에는 엄청난 일들이 벌어질 것 같다. 예를 들어 과학기술이 발달되어 사람 대신 로봇이 일을 할 것 같다.",
      "paragraph_len": 60,
      "paragraph_id": "001"
    }
  ],
  "score": {"essay_scoreT_avg": 24.78},
  "student": {
    "date": "2021.09.16",
    "student_grade": "중등_1학년",
    "location": "033",
    "student_grade_group": "중등",
    "student_reading": 1
  },
  "info": {
    "essay_id": "ESSAY_33474",
    "essay_prompt": "미래의 도시는 어떤 모습일까요?",
    "essay_type": "글짓기",
    "essay_len": 60,
    "essay_main_subject": "미래 도시에 대한 본인의 생각"
  }
}
```

- [ ] **Step 3: PII가 박힌 음성(audit detection 양성) fixture 작성**

`/home/dev/work/essay-auto-scoring-research/tests/fixtures/essay_with_pii.json` 전체:

```json
{
  "paragraph": [
    {
      "paragraph_txt": "안녕하세요 저는 김민수입니다. 다니고 있는 학교는 서울대학교사범대학부설초등학교이고, 6학년입니다. 연락처는 010-1234-5678 이고 이메일은 minsoo@example.com 입니다.",
      "paragraph_len": 105,
      "paragraph_id": "001"
    }
  ],
  "score": {"essay_scoreT_avg": 18.0},
  "student": {
    "date": "2022.03.01",
    "student_grade": "초등_6학년",
    "location": "011",
    "student_grade_group": "초등",
    "student_reading": 2
  },
  "info": {
    "essay_id": "ESSAY_99999",
    "essay_prompt": "내 소개를 해주세요.",
    "essay_type": "글짓기",
    "essay_len": 105,
    "essay_main_subject": "자기소개"
  }
}
```

이 fixture는 다음 4종 PII를 의도적으로 포함:
- 전화: `010-1234-5678`
- 이메일: `minsoo@example.com`
- 학교명: `서울대학교사범대학부설초등학교` (`...초등학교` / `...중학교` / `...고등학교` 패턴)
- 한국인 이름: `김민수` (성씨 + 2글자 한글, 흔한 패턴)

- [ ] **Step 4: 두 fixture가 valid JSON인지 검증**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -c "import json; [json.load(open(p)) for p in ['tests/fixtures/essay_clean.json','tests/fixtures/essay_with_pii.json']]; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add tests/__init__.py tests/fixtures/essay_clean.json tests/fixtures/essay_with_pii.json && \
  git commit -m "test(audit_pii): add clean + PII-laden essay fixtures

audit_pii TDD를 위한 합성 fixture 2건:
- essay_clean.json: 실제 sample과 동일한 schema, PII 0건
- essay_with_pii.json: 전화/이메일/학교명/한국인 이름 의도 삽입

실제 dataset/sample/은 이미 익명화되어 회귀 테스트 부적합."
```

Expected: `3 files changed`.

---

### Task 3: PII regex 패턴 TDD — `detect_pii(text)`

**Files:**
- Create: `/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py`
- Create: `/home/dev/work/essay-auto-scoring-research/pipelines/__init__.py` (없을 때만)
- Create: `/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py`

- [ ] **Step 1: `pipelines/__init__.py` 존재 확인 + 없으면 생성**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  test -f pipelines/__init__.py && echo "exists" || (touch pipelines/__init__.py && echo "created")
```

Expected: `exists` 또는 `created`.

- [ ] **Step 2: `detect_pii` 첫 테스트 작성 (FAIL)**

`/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py` 신규 생성, 전체:

```python
"""Tests for pipelines.audit_pii — PII detection + essay_id hashing for vast.ai upload."""

import pytest

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
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py -v 2>&1 | tail -20
```

Expected: `ModuleNotFoundError: No module named 'pipelines.audit_pii'` 또는 `cannot import name 'detect_pii'` (전체 FAIL).

- [ ] **Step 4: `audit_pii.py` 최소 구현 (detect_pii만)**

`/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py` 신규, 전체:

```python
"""PII audit for essay datasets before external (vast.ai) compute upload.

This module does NOT modify training data. It produces an audit report and an
optional copy with `essay_id` hashed. Training-relevant fields (student.location
as group key, student_grade_group as stratify key) are preserved.
"""

from __future__ import annotations

import re
from typing import List, TypedDict


class PiiHit(TypedDict):
    type: str
    match: str
    start: int
    end: int


# Korean mobile phone: 010-XXXX-XXXX (optional spaces/dots/dashes)
_PHONE_RE = re.compile(r"(?<!\d)01[016789][\s.\-]?\d{3,4}[\s.\-]?\d{4}(?!\d)")

# Email (RFC-light)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Korean school names: ...초등학교 / ...중학교 / ...고등학교 / ...대학교
_SCHOOL_RE = re.compile(r"[가-힣]{2,}(?:초등학교|중학교|고등학교|대학교)")

# Korean personal names: 1 common surname + 2 hangul chars, with word boundary.
# Conservative: only matches when preceded by "저는 "/"이름은 "/"제 이름은 " context
# to reduce false positives on common nouns.
_NAME_RE = re.compile(
    r"(?:저는|이름은|제\s*이름은)\s+([가-힣]{2,3})(?=입니다|이고|이며|이에요|이라|[.,])"
)

# Common occupation/role/relation nouns that appear after trigger phrases in K-12 essays.
# Matches here are NOT person names — post-filter these in detect_pii to reduce false positives.
_COMMON_NOUNS_AFTER_TRIGGER = frozenset({
    # Occupations / roles
    "학생", "선생", "교사", "의사", "간호사", "기자", "군인", "농부", "배우",
    "가수", "작가", "선수", "감독", "회사원", "공무원", "사장", "직원", "사람",
    # Family / relations
    "엄마", "아빠", "아버지", "어머니", "형", "누나", "오빠", "언니", "동생",
    "남동생", "여동생", "아들", "딸", "친구", "남편", "아내",
    # Generic identifiers
    "어른", "어린이", "청소년", "초등학생", "중학생", "고등학생", "대학생",
    # Common nouns confirmed false-positive in Task 6 sample audit (168 hits regression)
    "미역", "천사", "온난화", "비혼",
})


def detect_pii(text: str) -> List[PiiHit]:
    """Scan text for PII patterns. Returns list of hits (empty if clean)."""
    hits: List[PiiHit] = []
    for m in _PHONE_RE.finditer(text):
        hits.append({"type": "phone", "match": m.group(0), "start": m.start(), "end": m.end()})
    for m in _EMAIL_RE.finditer(text):
        hits.append({"type": "email", "match": m.group(0), "start": m.start(), "end": m.end()})
    for m in _SCHOOL_RE.finditer(text):
        hits.append({"type": "school", "match": m.group(0), "start": m.start(), "end": m.end()})
    for m in _NAME_RE.finditer(text):
        # Captured group 1 is the bare name (without the trigger phrase)
        name = m.group(1)
        if name in _COMMON_NOUNS_AFTER_TRIGGER:
            continue  # filter common nouns to reduce false positives in K-12 essays
        hits.append({"type": "person_name", "match": name, "start": m.start(1), "end": m.end(1)})
    return hits
```

- [ ] **Step 5: 테스트 재실행 → PASS 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py -v 2>&1 | tail -15
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add pipelines/__init__.py pipelines/audit_pii.py tests/test_audit_pii.py && \
  git commit -m "feat(audit_pii): detect_pii() — phone/email/school/name regex

Vast.ai 업로드 전 essay 본문 PII 검출. 6 test 통과.
보수적 name 매칭(트리거 phrase 필요)으로 일반명사 false positive 방지."
```

---

### Task 4: `essay_id` 해시화 TDD — `hash_essay_id(essay_id)`

**Files:**
- Modify: `/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py`
- Modify: `/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py`

- [ ] **Step 1: 해시 테스트 추가 (FAIL)**

`/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py` 끝에 추가:

```python


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
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py::TestHashEssayId -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'hash_essay_id'` (3 FAIL).

- [ ] **Step 3: `hash_essay_id` 구현**

`/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py` 상단 import 영역과 `detect_pii` 사이에 다음을 추가:

상단 import에 `import hashlib` 추가:

```python
from __future__ import annotations

import hashlib
import re
from typing import List, TypedDict
```

`detect_pii` 함수 아래에 추가:

```python


def hash_essay_id(essay_id: str) -> str:
    """SHA-256 prefix (16 hex chars) for masked-export essay_id.

    Deterministic and reversible (no salt). Use for audit traceability
    on copies sent to remote compute, not adversarial anonymization.
    """
    digest = hashlib.sha256(essay_id.encode("utf-8")).hexdigest()
    return digest[:16]
```

- [ ] **Step 4: 테스트 재실행 → 전체 PASS 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py -v 2>&1 | tail -15
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add tests/test_audit_pii.py pipelines/audit_pii.py && \
  git commit -m "feat(audit_pii): hash_essay_id() — SHA-256 prefix for masked export

vast.ai 인스턴스로 보내는 사본에서 essay_id를 16-hex 해시로 치환.
원본 dataset/는 그대로 유지(group key 보존). 결정성 + 충돌 회피 검증."
```

---

### Task 5: 단일 파일 audit TDD — `audit_file(path)`

**Files:**
- Modify: `/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py`
- Modify: `/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py`

- [ ] **Step 1: 통합 테스트 추가 (FAIL)**

`/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py` 끝에 추가:

```python


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
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py::TestAuditFile -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'audit_file'`.

- [ ] **Step 3: `audit_file` 구현**

`/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py` 상단 import에 `import json` 과 `from pathlib import Path` 추가:

```python
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import List, TypedDict
```

파일 끝에 추가:

```python


def _collect_essay_texts(doc: dict) -> List[str]:
    """Extract all free-form text fields a model could see (excludes prompts/scores)."""
    texts: List[str] = []
    if isinstance(doc.get("essay_txt"), str):
        texts.append(doc["essay_txt"])
    for p in doc.get("paragraph", []) or []:
        if isinstance(p, dict) and isinstance(p.get("paragraph_txt"), str):
            texts.append(p["paragraph_txt"])
    return texts


def audit_file(path: str) -> dict:
    """Audit a single essay JSON. Returns report dict; does not modify the file."""
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"Expected JSON object, got {type(doc).__name__}: {path}")

    hits: List[PiiHit] = []
    for text in _collect_essay_texts(doc):
        hits.extend(detect_pii(text))

    essay_id = (doc.get("info") or {}).get("essay_id") or doc.get("essay_id") or ""
    return {
        "path": str(p),
        "pii_count": len(hits),
        "hits": hits,
        "essay_id_original": essay_id,
        "essay_id_hashed": hash_essay_id(essay_id) if essay_id else "",
    }
```

- [ ] **Step 4: 테스트 재실행 → 전체 PASS 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py -v 2>&1 | tail -15
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add tests/test_audit_pii.py pipelines/audit_pii.py && \
  git commit -m "feat(audit_pii): audit_file() — single-essay audit report

essay_txt + paragraph[].paragraph_txt 스캔 → PII hits + essay_id hash.
원본 JSON 무변경. 3 통합 test 통과."
```

---

### Task 6: 디렉토리 walker + CLI TDD — `audit_directory()` + `__main__`

**Files:**
- Modify: `/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py`
- Modify: `/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py`

- [ ] **Step 1: 디렉토리 walker 테스트 추가 (FAIL)**

`/home/dev/work/essay-auto-scoring-research/tests/test_audit_pii.py` 끝에 추가:

> **Deviation from original plan:** Use `Path(__file__).parent / "fixtures"` (same as `TestAuditFile`) instead of CWD-relative `open(f"tests/fixtures/{name}")` to avoid breakage when pytest runs from /tmp.

```python


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
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py::TestAuditDirectory -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'audit_directory'`.

- [ ] **Step 3: `audit_directory` + CLI 구현**

`/home/dev/work/essay-auto-scoring-research/pipelines/audit_pii.py` 파일 끝에 추가:

```python


def audit_directory(root: str) -> dict:
    """Walk root recursively, audit each `*.json` essay file, return aggregate report."""
    root_path = Path(root)
    per_file: List[dict] = []
    for json_path in sorted(root_path.rglob("*.json")):
        try:
            report = audit_file(str(json_path))
        except (json.JSONDecodeError, OSError, ValueError):
            continue
        # Deviation from original plan: added ValueError because Task 5 fix made
        # audit_file raise ValueError for non-dict JSON (e.g. JSON arrays).
        per_file.append(report)

    return {
        "root": str(root_path),
        "total_files": len(per_file),
        "files_with_pii": sum(1 for r in per_file if r["pii_count"] > 0),
        "total_pii_hits": sum(r["pii_count"] for r in per_file),
        "per_file": per_file,
    }


def _main(argv: List[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="python3 -m pipelines.audit_pii",
        description="Audit essay JSON files for PII before uploading to external compute (e.g. vast.ai).",
    )
    parser.add_argument("root", help="Directory to walk recursively for *.json essay files")
    parser.add_argument(
        "--report", default="pii_audit_report.json", help="Output JSON report path"
    )
    parser.add_argument(
        "--fail-on-hit",
        action="store_true",
        help="Exit with non-zero status if any PII is detected (use in CI/upload gate)",
    )
    args = parser.parse_args(argv)

    result = audit_directory(args.root)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"audited {result['total_files']} files, "
        f"{result['files_with_pii']} with PII, "
        f"{result['total_pii_hits']} hits -> {args.report}"
    )

    if args.fail_on_hit and result["total_pii_hits"] > 0:
        sys.stderr.write("ERROR: PII detected — upload blocked.\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: 테스트 재실행 → 전체 PASS 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/test_audit_pii.py -v 2>&1 | tail -20
```

Expected: 14 passed.

- [ ] **Step 5: 실제 sample 데이터에 audit 실행 → 0 hits 기대**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pipelines.audit_pii dataset/sample --report workspace/pii_audit_sample.json && \
  python3 -c "import json; r=json.load(open('workspace/pii_audit_sample.json')); print('total_files=', r['total_files'], 'pii_hits=', r['total_pii_hits'])"
```

Expected:
- 첫 줄: `audited 684 files, 0 with PII, 0 hits -> workspace/pii_audit_sample.json` (파일 수는 원천+라벨링 합산, 0 hits면 OK)
- 둘째 줄: `total_files= 684 pii_hits= 0` (혹은 비슷한 수치)

만약 PII가 검출되면 보고만 하고 plan 자체는 진행 — sample은 익명화 기대이므로 0이 정상.

- [ ] **Step 6: `--fail-on-hit` 게이트가 PII 있을 때 exit 1을 내는지 검증**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pipelines.audit_pii tests/fixtures --report /tmp/_audit_test.json --fail-on-hit; echo "exit=$?"
```

Expected: `exit=1` (fixtures에 PII 박혀있음).

- [ ] **Step 7: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add tests/test_audit_pii.py pipelines/audit_pii.py && \
  git commit -m "feat(audit_pii): directory walker + CLI with --fail-on-hit gate

\`python3 -m pipelines.audit_pii <dir> --report <path> [--fail-on-hit]\`
vast.ai 업로드 전 의무 gate로 활용. 2 walker test 통과,
실제 dataset/sample 0 hits 확인."
```

---

### Task 7: `VAST_GPU_GUIDE.md` v2 — Essay 도메인 재작성 + API 키 placeholder

**Files:**
- Modify (전면 재작성): `/home/dev/work/essay-auto-scoring-research/VAST_GPU_GUIDE.md`

기존 가이드는 Whisper 오디오 추출용. Essay/RoBERTa 도메인용으로 전면 교체하고 API 키 hardcoded를 `.env` load 패턴으로 치환한다. 가이드 자체는 git 추적(키 0 보장).

- [ ] **Step 1: `VAST_GPU_GUIDE.md` 전체를 다음 내용으로 교체**

`/home/dev/work/essay-auto-scoring-research/VAST_GPU_GUIDE.md` 전체:

```markdown
# Vast.ai GPU 임대 가이드 — Essay Auto-Scoring v2

> 대상 작업: Phase 2 mid-scale (5K essay, KLUE-RoBERTa fine-tune + Optuna HPO)
> 본 가이드는 학생 PII가 외부 compute로 새지 않도록 audit gate를 의무 단계로 둔다.

## 0. 사전 준비

```bash
# CLI 설치
pip install vastai

# API 키는 .env에서 load (절대 git/로그/공유 채널에 노출 금지)
export VAST_API_KEY=$(grep -E '^VAST_API_KEY=' .env | cut -d= -f2-)
vastai show user   # 인증 확인
```

`.env` 템플릿은 `.env.example` 참고. 키 노출 의심 시 즉시 vast.ai 콘솔에서 revoke + regenerate.

## 1. GPU 검색 (모델별 권장 조건)

| 모델 | VRAM 필요 | 검색 조건 |
|---|---|---|
| klue/roberta-small (68M) | 4 GB | `gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95 inet_down>200` |
| klue/roberta-base (110M, fp16) | 7 GB | `gpu_ram>=8 num_gpus=1 dph<=0.15 reliability>0.95 inet_down>200` |
| klue/roberta-base (fp32) | 12 GB | `gpu_ram>=12 num_gpus=1 dph<=0.15 reliability>0.95 inet_down>200` |
| klue/roberta-large (337M) | 24 GB | `gpu_ram>=24 num_gpus=1 dph<=0.40 reliability>0.95 inet_down>300` |

```bash
vastai search offers 'gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95 inet_down>200' \
  -o 'dph' --limit 5
```

추천 진입: RTX 3060 8GB ($0.04~0.08/hr) — Phase 2 첫 cycle (M1) 적정.

## 2. 인스턴스 생성

```bash
OFFER_ID=<위 검색 결과의 id>
vastai create instance $OFFER_ID \
  --image pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime \
  --disk 50 \
  --onstart-cmd "pip install transformers==4.44.* datasets accelerate optuna scikit-learn lightgbm mlflow && echo READY"
```

`onstart-cmd` 의 `&& echo READY`는 준비 완료 detection용. 15분 안에 `READY`가 안 보이면 destroy 후 다른 offer 선택.

## 3. 인스턴스 상태 + SSH URL 확인

```bash
INSTANCE_ID=<create 시 반환된 id>
vastai show instance $INSTANCE_ID
vastai ssh-url $INSTANCE_ID    # ssh://root@sshX.vast.ai:PORT
```

loading → running 전환까지 15~60초. running이 되었어도 onstart-cmd 완료(READY)까지 추가 1~3분.

## 4. PII Audit (의무 단계 — 업로드 전 절대 생략 금지)

학생 PII를 vast.ai 인스턴스로 보내는 것은 AGENTS.md Hard Rule #2 정신에 위배될 수 있다. 본 단계를 통과한 데이터만 업로드한다.

```bash
# Phase 2 5K subsample 디렉토리에 대해 audit (예시 경로: dataset/sample_5k/)
python3 -m pipelines.audit_pii dataset/sample_5k \
  --report workspace/pii_audit_pre_upload.json \
  --fail-on-hit
echo "audit exit=$?"   # 반드시 0이어야 다음 단계 진행
```

`--fail-on-hit`가 exit 1을 내면 업로드 중단, `workspace/pii_audit_pre_upload.json` 검토 후 수동 redact 또는 해당 essay 제외.

## 5. 파일 업로드 (auto-destroy trap 패턴)

`destroy` 누락 시 과금이 계속 누적된다. trap으로 자동화한다.

```bash
HOST=sshX.vast.ai   # ssh-url 결과에서 추출
PORT=12345          # ssh-url 결과에서 추출

# 종료 시 자동 destroy 보장 (Ctrl-C, 스크립트 실패 모두 cover)
trap 'echo "destroying $INSTANCE_ID"; vastai destroy instance "$INSTANCE_ID"' EXIT

scp -o StrictHostKeyChecking=accept-new -P $PORT \
  -r dataset/sample_5k pipelines configs AGENTS.md \
  root@$HOST:/workspace/essay/
```

`StrictHostKeyChecking=accept-new`: 첫 접속은 자동 허용, 이후 변경은 거부 (no보다 안전).

## 6. 원격 실행 (KLUE-RoBERTa fine-tune + Optuna)

```bash
ssh -o StrictHostKeyChecking=accept-new -p $PORT root@$HOST \
  "cd /workspace/essay && \
   HF_HOME=/workspace/hf_cache \
   python3 -m pipelines.train \
     --mlflow-uri sqlite:///mlflow.db \
     --cycle-id M1 \
     --model klue/roberta-small \
     --hpo-trials 30"
```

학습 중 진행은 SSH 세션에서 직접 모니터, 종료 후 결과 회수.

## 7. 결과 회수

```bash
scp -P $PORT root@$HOST:/workspace/essay/mlflow.db ./mlflow_remote_M1.db
scp -P $PORT -r root@$HOST:/workspace/essay/workspace/cycle_M1 ./workspace/

# 로컬 MLflow와 merge가 필요하면 별 도구 (Phase 2 운영 evidence 문서 참조)
```

## 8. 종료 (trap이 동작했다면 자동 처리됨, 수동 확인)

```bash
vastai show instances    # 비어있어야 OK
# 만약 남아있다면
vastai destroy instance $INSTANCE_ID
```

## 9. 비용 참고 (Phase 2 추정)

| 작업 | GPU | 소요 | 비용 |
|---|---|---|---|
| roberta-small + 5K + HPO 30 trial | RTX 3060 8GB | ~1.5 h | ~$0.06~0.15 |
| roberta-base fp16 + 5K + HPO 30 | RTX 3060 12GB | ~2 h | ~$0.10~0.30 |
| onstart-cmd pip install | - | ~2분 | ~$0.003 |
| 데이터 업로드 (5K, ~10MB) | - | <1분 | ~$0 |

`board_config.yaml`의 `cost_circuit_breaker.max_usd_per_cycle`(Phase 2 권장 $50)와 통합 추적 권장.

## 10. 주의사항

- onstart-cmd `READY` echo 15분 초과 → destroy 후 다른 offer
- 한글 파일명 SCP 간헐 실패 → 재시도 또는 zip 후 전송
- **반드시 `vastai destroy` 또는 trap으로 정리** (과금 방지)
- `vastai show instances`로 잔존 인스턴스 0건 정기 확인
- **Hard Rule #2: 학생 PII 외부 LLM/compute 전송 금지** — §4 audit gate 절대 생략 금지
- API 키는 `.env`만, git/echo/로그/스크린샷 노출 금지

## 11. 빠른 참조 (1회 cycle 전체 흐름)

```bash
# 0. 환경
export VAST_API_KEY=$(grep -E '^VAST_API_KEY=' .env | cut -d= -f2-)

# 1. PII audit (의무 gate)
python3 -m pipelines.audit_pii dataset/sample_5k \
  --report workspace/pii_audit_pre_upload.json --fail-on-hit || exit 1

# 2. 검색 + 생성
OFFER_ID=$(vastai search offers 'gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95' -o 'dph' --raw \
           | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
INSTANCE_ID=$(vastai create instance $OFFER_ID \
  --image pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime --disk 50 \
  --onstart-cmd "pip install transformers==4.44.* datasets accelerate optuna scikit-learn lightgbm mlflow && echo READY" \
  --raw | python3 -c "import sys,json; print(json.load(sys.stdin)['new_contract'])")
trap 'vastai destroy instance "$INSTANCE_ID"' EXIT

# 3. URL 대기
sleep 90 && SSH_URL=$(vastai ssh-url $INSTANCE_ID)
HOST=$(echo $SSH_URL | sed -E 's|ssh://root@([^:]+):.*|\1|')
PORT=$(echo $SSH_URL | sed -E 's|.*:([0-9]+)$|\1|')

# 4. 업로드 + 실행 + 회수
scp -o StrictHostKeyChecking=accept-new -P $PORT -r \
  dataset/sample_5k pipelines configs AGENTS.md root@$HOST:/workspace/essay/
ssh -o StrictHostKeyChecking=accept-new -p $PORT root@$HOST \
  "cd /workspace/essay && HF_HOME=/workspace/hf_cache python3 -m pipelines.train \
     --mlflow-uri sqlite:///mlflow.db --cycle-id M1 --model klue/roberta-small --hpo-trials 30"
scp -P $PORT root@$HOST:/workspace/essay/mlflow.db ./mlflow_remote_M1.db
scp -P $PORT -r root@$HOST:/workspace/essay/workspace/cycle_M1 ./workspace/

# 5. trap이 destroy 호출
```
```

- [ ] **Step 2: 파일에 API 키 평문이 남아있지 않은지 검증**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  grep -E '[a-f0-9]{32,}' VAST_GPU_GUIDE.md && echo "FAIL: hex key found" || echo "OK: no hex key"
```

Expected: `OK: no hex key`

- [ ] **Step 3: 가이드가 git에 무시되지 않는지 확인 (추적 가능)**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git check-ignore VAST_GPU_GUIDE.md; echo "ignored_exit=$?"
```

Expected: `ignored_exit=1` (무시되지 않음, 추적 가능).

- [ ] **Step 4: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add VAST_GPU_GUIDE.md && \
  git commit -m "docs(vast.ai): rewrite guide for Essay/RoBERTa + .env-based key

기존 Whisper 가이드를 Essay Phase 2 (KLUE-RoBERTa + Optuna)에 맞춰 재작성.
- 모델별 VRAM/검색조건 테이블
- onstart-cmd를 transformers/optuna 스택으로
- PII audit (\`pipelines.audit_pii --fail-on-hit\`)을 업로드 전 의무 gate로
- API 키 hardcoded 2곳 제거 → \`\$(grep VAST_API_KEY .env ...)\`
- destroy trap 자동화 패턴
- StrictHostKeyChecking=accept-new (no보다 안전)"
```

---

### Task 8: 운영 evidence 문서 — `docs/research/vast_ai_essay_workflow_v_1_0.md`

**Files:**
- Create: `/home/dev/work/essay-auto-scoring-research/docs/research/vast_ai_essay_workflow_v_1_0.md`

- [ ] **Step 1: 운영 evidence 문서 신규 작성**

`/home/dev/work/essay-auto-scoring-research/docs/research/vast_ai_essay_workflow_v_1_0.md` 전체:

```markdown
# Vast.ai × Essay Phase 2 운영 Evidence v1.0

> 문서 버전: v1.0 · 작성일: 2026-05-27
> 범위: Phase 2 mid-scale (5K essay + KLUE-RoBERTa + Optuna)에서 vast.ai 임대 GPU를 안전·효율적으로 사용하기 위한 운영 evidence 모음. `VAST_GPU_GUIDE.md`(작업 절차)의 근거 문서.

## 1. 의사결정 요약

| 항목 | 결정 | 근거 |
|---|---|---|
| GPU 공급자 | vast.ai | 시간당 단가 최저 (~$0.05/hr RTX 3060), API/CLI 단순, 한국 인근 region 가용 |
| 진입 모델 | klue/roberta-small (68M) | 8GB VRAM로 충분, 5K + HPO 30 trial 1~1.5h |
| 첫 cycle 예산 | < $0.30 | RTX 3060 8GB × 2h max, board_config $50/cycle cap 내 |
| 데이터 전송 보호 | `pipelines.audit_pii --fail-on-hit` gate | Hard Rule #2 정신(외부 compute로 PII 송신 금지) |
| Auto-destroy | shell `trap ... EXIT` 패턴 | 누락 시 과금 누적 → 운영 위험 #1 |

## 2. 데이터 흐름

```
[로컬]                                         [vast.ai 인스턴스]
dataset/sample_5k/ ──audit──┐
                            ↓
              workspace/pii_audit_pre_upload.json  (gate)
                            ↓ (pii_hits=0 일 때만)
        scp ─────────────────────────────────►  /workspace/essay/dataset/sample_5k/
        scp pipelines/, configs/, AGENTS.md ─►  /workspace/essay/
                                                       │
                                                       ▼
                                            python3 -m pipelines.train
                                            (KLUE-RoBERTa + Optuna)
                                                       │
                                                       ▼
                                            /workspace/essay/mlflow.db
                                            /workspace/essay/workspace/cycle_M1/
                                                       │
        scp ◄──────────────────────────────────────────┘
mlflow_remote_M1.db, workspace/cycle_M1/

                            ▼
        (옵션) MLflow merge로 누적 보드에 통합
                            ▼
       reports/latest/cumulative_report.html
```

## 3. 위험 분석 + mitigation

| # | 위험 | 영향 | mitigation |
|---|---|---|---|
| 1 | `vastai destroy` 누락 | 과금 누적 (~$1~5/일) | shell `trap "vastai destroy instance $ID" EXIT` 의무, `vastai show instances` 정기 점검 |
| 2 | API 키 git/로그 노출 | 임의 인스턴스 생성 → 비용 폭주 | `.env`만 보관, `.gitignore` `.env` 차단, 가이드 내 `$(grep ... .env)` 패턴, 노출 의심 시 즉시 revoke |
| 3 | 학생 PII 외부 송신 (Hard Rule #2 정신) | 컴플라이언스 위반 | `pipelines.audit_pii --fail-on-hit`을 업로드 전 의무 gate로, audit report `workspace/pii_audit_pre_upload.json` 보존 |
| 4 | onstart-cmd `READY` 미수신 (장기 hang) | 시간 낭비 | 15분 deadline → destroy 후 다른 offer |
| 5 | MITM (SSH host key 자동 수락) | 데이터 가로채기 | `-o StrictHostKeyChecking=accept-new` 사용 (`no` 금지) |
| 6 | 한글 파일명 SCP 실패 | 데이터 누락 | 사전 zip 또는 재시도, `--ascii-filename` 옵션 활용 검토 |
| 7 | HF 모델 매번 다운로드 | cycle당 2~5분 추가 | `HF_HOME=/workspace/hf_cache` 고정, persistent volume 검토 |
| 8 | MLflow DB 결과 merge 충돌 | 누적 evidence 단절 | 원격 결과는 `mlflow_remote_<cycle>.db`로 별 보관, 누적 보드는 로컬 SQLite로 일원화 |
| 9 | 추정치보다 오래 걸려 예산 초과 | cost cap trip | board_config cost_circuit_breaker로 자동 차단, gauss profile이 인간 escalation |
| 10 | Spot 인스턴스 강제 종료 | cycle 중단 | reliability>0.95 + interruptible=false 검색 조건, 중간 checkpoint MLflow에 기록 |

## 4. 비용 모델

| 시나리오 | GPU | 시간 | dph | 예상 cost |
|---|---|---|---|---|
| roberta-small + HPO 30 trial | RTX 3060 8GB | 1.5 h | $0.05 | $0.075 |
| roberta-base fp16 + HPO 30 | RTX 3060 12GB | 2 h | $0.08 | $0.16 |
| roberta-large + HPO 50 | RTX 3090 24GB | 3 h | $0.35 | $1.05 |
| 10 cycle 누적 (small) | - | 15 h | $0.05 | ~$0.75 |
| 한 milestone (Phase 2 완주, 5~10 cycle base) | - | ~20 h | $0.08 | ~$1.60 |

→ Phase 1의 board_config `max_usd_per_cycle=20` 그대로 두어도 Phase 2 base 시나리오는 여유. roberta-large 또는 long-tail HPO 시 50으로 상향 검토.

## 5. 외부 참고

- vast.ai Pricing & Search docs: https://vast.ai/docs/
- HuggingFace KLUE-RoBERTa: https://huggingface.co/klue
- Optuna HPO best practice: Akiba et al. 2019 (Optuna paper)
- AGENTS.md Hard Rule #2 (학생 PII), board_config `cost_circuit_breaker`

## 6. 다음 액션 (Phase 2 setup 시점)

- [ ] vast.ai 콘솔에서 신규 API 키 발급, 기존 키 revoke
- [ ] `.env`에 신규 키 저장, `vastai show user` 인증 확인
- [ ] `dataset/sample_5k/` 추출 (Phase 2 design 문서 §B2 데이터 출처 결정 후)
- [ ] `pipelines.audit_pii dataset/sample_5k --fail-on-hit` PASS 확인
- [ ] `VAST_GPU_GUIDE.md` §11 빠른 참조 그대로 1회 dry-run
- [ ] Cycle M1 ready
```

- [ ] **Step 2: 문서가 valid markdown인지 가벼운 sanity check (line count)**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  wc -l docs/research/vast_ai_essay_workflow_v_1_0.md && \
  grep -c '^## ' docs/research/vast_ai_essay_workflow_v_1_0.md
```

Expected: 행 수 60+ 줄, `##` 섹션 6개 이상.

- [ ] **Step 3: Commit**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git add docs/research/vast_ai_essay_workflow_v_1_0.md && \
  git commit -m "docs(research): vast.ai × Essay Phase 2 운영 evidence v1.0

VAST_GPU_GUIDE.md(작업 절차)의 근거 문서.
의사결정 요약, 데이터 흐름, 10종 위험 분석, 비용 모델,
Phase 2 setup 시 다음 액션 체크리스트 포함."
```

---

### Task 9: 최종 검증 + 사용자 보고 (commit 없음)

**Files:** (없음 — 검증 + 보고 단계)

- [ ] **Step 1: 전체 test 통과 + git 상태 깨끗 확인**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  python3 -m pytest tests/ -v 2>&1 | tail -5 && \
  echo "---git---" && git status && \
  echo "---log---" && git log --oneline -10
```

Expected:
- pytest: `14 passed`
- git status: `nothing to commit, working tree clean`
- log: 본 plan으로 7개의 신규 commit (`5693e65` 이후)

- [ ] **Step 2: 보안 최종 점검 — 추적되는 파일에 API 키 절대 없음**

Run:
```bash
cd /home/dev/work/essay-auto-scoring-research && \
  git grep -E '[a-f0-9]{40,}' -- ':!*.json' ':!dataset' ':!assets' || echo "OK: no long hex secrets in tracked files"
```

Expected: `OK: no long hex secrets in tracked files` (또는 무관한 commit hash 한두 줄 — 콘텐츠 점검 후 무해 확인).

- [ ] **Step 3: 사용자에게 보고 (텍스트만)**

다음 5개 항목을 사용자에게 보고:

1. `.env` 추적 차단 + `.env.example` 신규 (1 commit)
2. `pipelines/audit_pii.py` + 14 test 통과, sample 실데이터 0 PII 확인 (4 commit)
3. `VAST_GPU_GUIDE.md` Essay v2 재작성, API 키 placeholder 화 (1 commit)
4. `docs/research/vast_ai_essay_workflow_v_1_0.md` 운영 evidence 신규 (1 commit)
5. **사용자 액션 (plan 외)**: vast.ai 콘솔에서 기존 키 revoke + 신규 발급 → `.env`에 새 키 저장. 본 plan 작성 과정에서 키가 컨텍스트에 노출됐으므로 rotation 권고.

Phase 2 setup 단계로 진입 가능한 상태가 됨을 명시.

---

## Self-Review

- **Spec coverage:**
  - P0-1 (`.gitignore` `.env` 차단): Task 1
  - P0-2 (`VAST_GPU_GUIDE.md` 키 placeholder): Task 7
  - P0-3 (API 키 rotate 권고): Task 9 Step 3
  - P1-1 (PII 마스킹/audit 도구): Task 2-6 (audit-only, 마스킹은 essay_id hash까지)
  - P1-2 (가이드 Essay v2 갱신): Task 7
  - P1-3 (운영 evidence 문서): Task 8
  - P2-1 (destroy trap), P2-2 (HF cache): Task 7 가이드 §5 + Task 8 위험 #1, #7
  - **누락된 spec 항목**: Hard Rule #2 본문 확장 ("외부 LLM" → "외부 LLM 및 외부 compute") — LOCKED 변경이라 본 plan에서 의도적 제외 (인간 게이트 task로 별 운영 단계 권장). Task 8 위험 #3에 정신적 cover 명시.

- **Placeholder scan:** Task 6 Step 5의 "684 files"는 실제 sample 수와 다를 수 있음. plan 본문에 "혹은 비슷한 수치"로 명시했으며 핵심은 `pii_hits=0`이라 placeholder 아님.

- **Type consistency:** 
  - `detect_pii(text: str) -> List[PiiHit]` (Task 3) — Task 5 `_collect_essay_texts` → `detect_pii` 호출 일치
  - `hash_essay_id(essay_id: str) -> str` (Task 4) — Task 5 `audit_file` 내부 호출 일치
  - `audit_file(path: str) -> dict` (Task 5) — Task 6 `audit_directory` 내부 호출 일치
  - 시그니처 일관성 OK

- **TDD discipline:** Task 3/4/5/6 모두 fail-first → minimal impl → pass → commit 순서 유지.

- **Frequent commits:** 7개 commit (Task 1, 2, 3, 4, 5, 6, 7, 8) — 각 단위 self-contained.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-27-vast-ai-phase2-hardening.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
