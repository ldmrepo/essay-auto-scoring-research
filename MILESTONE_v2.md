# Milestone Goal v2 (Phase 2 Mid-scale)

> Hard Rule #10 source — Cycle MN의 AUDIT sub-task body에 verbatim 재주입되는 goal anchor.
> 본 문서는 변경 시 AGENTS.md LOCKED 변경과 동일한 인간 게이트 필요.

## Goal

Hermes Multi-Agent Kanban Board로 한국어 K-12 에세이 자동채점 모델의
**Mid-scale 5K 학습 + KLUE-RoBERTa transformer 도입 + Optuna HPO + Voyager-style skill library 활성**을
**24시간 인간 개입 최소(cycle당 DECIDE 1클릭)** 자가발전 long-running chain으로 검증한다.

## Success Criteria (Phase 2 acceptance)

1. **M5 KLUE-RoBERTa valid QWK ≥ 0.40** (95% CI lower bound, k=10 fold 평균)
2. **M5 > M4 LightGBM** strict 진화 (`M5_lower95 > M4_upper95`, Hard Rule #5)
3. **모든 fold valid_n ≥ 300** (k=5 적용, location 편중 데이터에서 산술 만족 — Cycle M1 SPLIT-block 후 2026-05-28 결정)
4. **Optuna HPO 누적 50+ trial** (Cycle M1 30 + Cycle M2+ 추가, Hard Rule #12)
5. **Skill library 5+ verified skill 누적** (Cycle M3 종료 시점)
6. **PII gate 통과**: 외부 compute(vast.ai) 송신 전 `audit_pii --fail-on-hit` exit=0 (Hard Rule #13)
7. **Acceptance**: PASS_CANDIDATE 또는 PASS_FINAL 도달 (ACCEPTANCE_CRITERIA.yaml mid 섹션)

## Out of Scope (본 milestone 종결 후)

- 풀데이터 50K 학습 (Phase 3 Full)
- `klue/roberta-large` (337M, Phase 3 GPU budget 확보 후)
- Production model registration / champion alias (Phase 4, 별 인간 게이트 + 법무)
- 외부 배포 (Phase 4)

## Phase Transition Criteria

| 진입 | 조건 |
|---|---|
| Phase 2 → Phase 3 (Full) | Success Criteria 1~5 통과 + 사용자 [Phase-up] DECIDE + T-PHASE-MIGRATE-FULL 인간 결재 |
| Phase 3 → Phase 4 (Production) | Phase 3 PASS_FINAL + bias audit 통과 + 인간 + 법무 게이트 |

## Self-Improving Loop Reminder

각 Cycle MN은 9 sub-task chain (AUDIT → SPLIT → FEATURE → MODEL → HPO → EVAL ‖ REVIEW → SYNTH → DECIDE-MN).
SYNTH가 다음 Cycle M(N+1)의 9 sub-task + DECIDE 등록 (PASS_CANDIDATE/FAIL 무관, 옵션 #1).
DECIDE-MN [Continue] 1클릭으로 Cycle M(N+1) 자동 시작.

## References

- AGENTS.md v4 — Hard Rules + 9-step Cycle Pattern + When HPO
- docs/phase_2_mid_scale_design_v_1_1.md — 인프라/리스크/일정 상세
- VAST_GPU_GUIDE.md — vast.ai 원격 GPU 작업 절차
- dataset/sample_5k/manifest.json — 본 milestone primary 데이터셋 spec
