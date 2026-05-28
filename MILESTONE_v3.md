# Milestone Goal v3 (Phase 3 — placeholder, 대기 상태)

> **상태**: Phase 2 종료 후 대기. 본격 작성은 사용자 Phase 3 진입 결정 시.
> **선행 문서**: `docs/multi_task_채점모델_구현_스펙_v_1_0.md` (multi-task 설계 스펙, v1.0)
> **Phase 2 종료 사유**: 단일 타겟 학습이 사용자 실제 목적(루브릭별 채점)과 불일치 (MILESTONE_v2.md 종료 노트 참조)

---

## Phase 3 핵심 방향 (확정 사항)

| 항목 | 결정 |
|---|---|
| **학습 타겟** | 루브릭 차원별 multi-task (`essay_scoreT_avg` 단일 타겟 폐기) |
| **출력 단위** | 1단계: 대분류 3 + overall 1 (총 4) / 2단계: 소분류 9~11 확장 |
| **데이터** | Phase 2와 동일 `dataset/sample_5k/` (5003편) 또는 풀데이터 `dataset/1.Training` (50K+) |
| **가중치 source** | JSON `rubric` 필드 동적 로드 (PDF spec 의존 제거) |
| **base 모델** | KLUE-RoBERTa-small (Phase 2 inheritance) → 안정화 후 `klue/roberta-base` 검토 |

---

## Success Criteria (placeholder, 진입 시 확정)

1. **M5 multi-task per-rubric QWK lower95 ≥ 0.30** (exp/org/cont 각각)
2. **M5 overall QWK lower95 ≥ 0.40** (Phase 2 기준 유지)
3. **M5 > M4 strict** (overall 기준, 단조 진화)
4. **Score-Band Fairness Gate 차원별 적용** (Hard Rule #14 확장)
5. **Optuna HPO 누적 50+ trial** (multi-task 변형)
6. **PASS_CANDIDATE 또는 PASS_FINAL** 도달

---

## 사용자 결정 대기 항목 (진입 시)

| # | 항목 | 옵션 |
|---|---|---|
| **D1** | 차원별 fairness gate 정의 | A: overall band 내 차원별 metric / B: 차원별 band 새 정의 / **C: 차원별 worst_band hard-block** |
| **D2** | 손실 스케일 | **A: overall 0~3 정규화** / B: loss weight 보정 |
| **D3** | 출력 단위 | **하이브리드 3+overall** / 소분류 9~11 / 두 단계 |
| **D4** | 데이터 규모 | 5K (Phase 2 데이터 재사용) / 50K (풀데이터) |
| **D5** | base 모델 크기 | klue/roberta-small (68M) / klue/roberta-base (110M) |
| **D6** | M6 ensemble 처리 | scalar 폐기 + multi-output OOF로 재작성 / M6 자체 제거 |

(권장은 `dataset_채점방식_분석_v_1_0.md` v1.1 § 8, `multi_task_채점모델_구현_스펙_v_1_0.md` 참조)

---

## 변경 범위 (Phase 2 대비)

| 영역 | 변경 |
|---|---|
| `pipelines/train.py` | `TARGET_NAME` → `TARGET_NAMES` 다중 |
| `pipelines/train_transformer.py` | `num_labels=1` → `num_labels=4` + custom loss + dataset/collator multi-label |
| `pipelines/train_ensemble.py` | scalar → multi-output OOF stacking (전면 재작성) |
| `pipelines/evaluate.py` | per-rubric metric + per-rubric fairness gate |
| `MILESTONE_v3.md` (본 문서) | placeholder → 확정 success criteria |
| `AGENTS.md` Hard Rule #5/#14 | 차원별 적용 규칙 |
| `ACCEPTANCE_CRITERIA.yaml` | per-rubric threshold |

---

## References

- `docs/multi_task_채점모델_구현_스펙_v_1_0.md` — multi-task 구현 스펙 (외부 리뷰 6건 정정 적용 v1.1 예정)
- `docs/dataset_채점방식_분석_v_1_0.md` v1.1 — 데이터셋 루브릭 구조 분석 (검증 완료)
- `MILESTONE_v2.md` — Phase 2 종료 노트
- `AGENTS.md` v5 — Hard Rules
- `workspace/cycle_M1/` — Phase 2 보존 산출 (재현 기준)
