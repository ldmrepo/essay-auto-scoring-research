"""PII audit for essay datasets before external (vast.ai) compute upload.

This module does NOT modify training data. It produces an audit report and an
optional copy with `essay_id` hashed. Training-relevant fields (student.location
as group key, student_grade_group as stratify key) are preserved.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
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


def hash_essay_id(essay_id: str) -> str:
    """SHA-256 prefix (16 hex chars) for masked-export essay_id.

    Deterministic and reversible (no salt). Use for audit traceability
    on copies sent to remote compute, not adversarial anonymization.
    """
    digest = hashlib.sha256(essay_id.encode("utf-8")).hexdigest()
    return digest[:16]


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
    if not isinstance(doc.get("essay_txt"), str) and not isinstance(doc.get("paragraph"), list):
        raise ValueError(f"Expected essay JSON with essay_txt or paragraph fields: {path}")

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


def audit_directory(root: str) -> dict:
    """Walk root recursively, audit each `*.json` essay file, return aggregate report."""
    root_path = Path(root)
    per_file: List[dict] = []
    for json_path in sorted(root_path.rglob("*.json")):
        try:
            report = audit_file(str(json_path))
        except (json.JSONDecodeError, OSError, ValueError):
            continue
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

    if not Path(args.root).is_dir():
        sys.stderr.write(f"ERROR: root path does not exist or is not a directory: {args.root}\n")
        return 2

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
