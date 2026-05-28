# Milestone Goal v2 (Phase 2 Mid-scale)

> **🛑 Phase 2 종료 (2026-05-28, 사용자 명시 결정)**
>
> - **도달 상태**: Cycle M1 진행 중 종료. M1~M4 baseline 완료 (M4 QWK 0.2635), M5 KLUE-RoBERTa 미완 (vast.ai worker hang 패턴 + codex app-server 10분 timeout으로 학습 결과 회수 실패), HPO/EVAL/REVIEW/SYNTH/DECIDE 미수행
> - **종료 사유**: 단일 타겟(`essay_scoreT_avg`) 학습 설계가 사용자 실제 목적(루브릭별 차원 점수)과 불일치. 데이터셋의 다차원 채점(표현/구성/내용 × 채점자 3명 × 소분류 9~11개) 정보 활용 부족
> - **보존 산출**: `workspace/cycle_M1/{audit,splits,features,models/M{1,2,3,4}}/` (재현 가능)
> - **archive 처리**: t_13e1eaaa (HPO), t_1bab6d23 (EVAL), t_785a48e3 (REVIEW), t_171d099a (SYNTH), t_617de071 (DECIDE-M1)
> - **Phase 3 진입 대기**: multi-task 모델 설계 (`docs/multi_task_채점모델_구현_스펙_v_1_0.md`) 기준으로 새 milestone 작성 예정
>
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
6. **Acceptance**: PASS_CANDIDATE 또는 PASS_FINAL 도달 (ACCEPTANCE_CRITERIA.yaml mid 섹션)
7. **Score-Band Fairness Gate 통과** (Hard Rule #14, 2026-05-28 신설): `worst_band_qwk >= macro_qwk × 0.7`. 본 데이터셋의 score 편중(high 90.5% / mid 9.5% / low 0.04%) 때문에 overall metric 단독 acceptance 금지. low band N<10이면 `SKIP_UNSTABLE` 마크 + qualitative risk 보고만으로 충족.

> Hard Rule #13(외부 compute PII gate)은 2026-05-28 인간 게이트로 제거. 본 데이터셋(AI Hub 공공 한국 K-12 에세이)이 사전 익명화 완료이므로 외부 GPU 전송 가능.

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
