# Milestone Goal v3 (Phase 3 Multi-task)

> **상태**: 확정 (2026-05-28). Phase 2 종료 후 사용자 옵션 A 채택으로 D1~D6 일괄 확정 + Step 2~7 자율 진행 완료.
> **선행 문서**:
> - `docs/multi_task_채점모델_구현_스펙_v_1_1.md` — 모델 스펙 v1.1 (외부 리뷰 6건 + D1~D6 반영)
> - `docs/phase_3_operations_guide_v_1_0.md` — 운영 가이드 (C1~C6 절차)
> - `docs/dataset_채점방식_분석_v_1_0.md` v1.1 — 데이터셋 분석 (검증 완료)
> - `MILESTONE_v2.md` — Phase 2 종료 노트
>
> Hard Rule #10 source — Cycle MN의 AUDIT sub-task body에 verbatim 재주입되는 goal anchor.
> 본 문서는 변경 시 AGENTS.md LOCKED 변경과 동일한 인간 게이트 필요.

---

## Goal

Hermes Multi-Agent Kanban Board로 한국어 K-12 에세이의 **루브릭별 (대분류 3 + overall) 차원 채점 모델**을
**중단없는 지속적 실행 (사용자 개입 cycle당 < 1회)** 자가발전 long-running chain으로 달성한다.

Phase 3는 Phase 2의 단일 타겟 학습(`essay_scoreT_avg`)에서 multi-task (`exp / org / cont / overall`)로 전환하여
사용자 실제 목적(루브릭별 점수 + 차원별 진단)에 정합한다.

Phase 2의 6대 중단 원인(C1~C6)을 사전 대응 절차(`phase_3_operations_guide_v_1_0.md`) + Hard Rule #15~#18로 명문화하여
worker hang / DB 손상 / 권한 차단 / 진행 가시성 / 인간 개입 빈도 모두를 0~최소화한다.

---

## Phase 3 핵심 방향 (D1~D6 확정)

| # | 항목 | 결정 | 출처 |
|---|---|---|---|
| **D1** | 차원별 fairness gate | C: 차원별 worst_band hard-block | 스펙 v1.1 § 6 A3 |
| **D2** | 손실 스케일 | A: overall 0~3 정규화 | 스펙 v1.1 § 3 |
| **D3** | 출력 단위 | 하이브리드 3+overall (대분류 3 + 보조 overall) | 스펙 v1.1 § 2 |
| **D4** | 데이터 규모 | 5K (Phase 2 inheritance, `dataset/sample_5k/`) | 스펙 v1.1 § 7.3 |
| **D5** | base 모델 크기 | klue/roberta-small (Phase 2 inheritance) | 스펙 v1.1 § 11.1 |
| **D6** | M6 ensemble 처리 | scalar 폐기 + multi-output OOF 재작성 | 스펙 v1.1 § 4, § 12 |

---

## Success Criteria (Phase 3 Mid Multi-task acceptance)

ACCEPTANCE_CRITERIA.yaml `stages.mid_multitask` 본문 mapping. 본 표는 T3-01 fix로 Hard Rule + 측정 방법 column 추가.

| # | Criteria | 임계 | Hard Rule | 측정 방법 (출처) |
|---|---|---|---|---|
| 1 | M5 overall `qwk_lower95` ≥ 0.40 | 0.40 | #5, #14 | `evaluate.py` overall_raw bootstrap CI lower (B=1000) |
| 2 | M5 per-rubric `qwk_lower95` ≥ 0.30 (exp/org/cont) | 0.30 | #15 | `evaluate.py` per-dim QWK + bootstrap CI lower |
| 3 | M5 > M4 strict (`M5_overall_lower95 > M4_overall_upper95`) | strict | #5 | `acceptance.baseline_ordering_overall` (raw_0_30) |
| 4 | M6 > M5 strict (overall) | strict | #5 | 동상 |
| 5 | **All-dimension** fairness gate (exp/org/cont 각 native 0~3 + overall raw 0~30 — 각 `worst_band_qwk ≥ macro_qwk × 0.7`) | × 0.7 | #14 (확장), #15 | `fairness_gate.unit_per_dimension` + score_band_cutoffs |
| 6 | Optuna HPO trial 수 (M2 단독 30+, M3+ 누적 50+ 및 cycle당 5+ 추가) | M2: 30 / M3+: 50 | #12 | optuna study `len(study.trials)` + cycle delta |
| 7 | 모든 fold valid_n ≥ 300 (default `student.location + k=5`; M2 fallback `region merge + k=3` 허용) | 300 | SPLIT | 기본 split 실패 report + fallback split manifest |
| 8 | judgement: PASS_CANDIDATE | enum | — | SYNTH cycle report (`final_judgement_allowed: false` 정합) |
| 9 | **차원별 단조 후퇴 0건** (T1-05 신설) | 0 | #15 | `per_rubric_monotone_evolution.warn_condition` |
| 10 | **evaluator wire-up 완료** (T1-03 신설, Phase 3 M2 진입 게이트) | true | (운영) | `mid_multitask._implementation_status == wired_v1` |

## Phase 3 진입 게이트 (Cycle M2 첫 sub-task)

본 criteria #10이 PASS될 때까지 Cycle M2의 EVAL sub-task는 dead spec 위험. M2 first sub-task로 다음을 등록:

```
T-CYCLE-M2-WIRE-UP (gauss + turing) — Phase 3 evaluator + acceptance wire-up
  ├── pipelines/evaluate.py에 mid_multitask 분기 추가
  ├── score_band_per_rubric() 함수 (T1-04 cutoff 적용)
  ├── fairness_gate_per_rubric() 함수 + 차원별 lower95
  ├── evaluate.py main executable path가 mid_multitask stage에서 fairness_gate_per_rubric()를 호출 (helper-only dead code 금지)
  ├── auto_continue 평가 로직 — R2-NEW-G3/G4/G5 fix 명시:
  │     - consecutive_pass_candidate_max: 2
  │     - evolution_progress_required.window_cycles=2 + grace_cycles=3
  │       → cycle index >= grace_cycles+1 (즉 M5부터) 본 임계 적용 시작 (R2-NEW-G3 결정)
  │     - per_rubric_monotone_evolution: cross-cycle M{N+1} vs M{N} 비교 (warn)
  │     - m6_per_rubric_evolution: same-cycle M5 vs M6 ensemble 비교 (warn) — comparison_scope: same_cycle 명시 처리 (R2-NEW-G4)
  ├── tests/test_evaluate_phase3.py 신설 + 통과
  └── ACCEPTANCE_CRITERIA.yaml mid_multitask._implementation_status: wired_v1 갱신
```

위 task 완료 + tests/test_evaluate_phase3.py 통과 후 본격 cycle (AUDIT → SPLIT → ... → SYNTH → DECIDE) 진행.

## M2R Split Fallback Policy (v3)

M2 SPLIT의 default attempt는 `student.location + k=5`이다. default split에서 fold 중 하나라도 `valid_n >= 300`을 위반하면 M2에 한해 승인된 fallback `region merge + k=3`을 사용할 수 있다.

fallback acceptance 조건:
- `group_overlap_count=0`
- `student.location`은 split key / leakage audit metadata로만 사용하고 모델 입력에는 포함하지 않음
- `min_valid_n >= 300`
- evidence에 실패한 default split report와 승인된 fallback split manifest를 모두 포함

이 fallback은 `valid_n` 안전 게이트를 완화하지 않는다. fold 수와 group granularity만 조정한다.

---

## 중단없는 지속적 실행 (Phase 2 → Phase 3 대응)

| Phase 2 중단 원인 | Phase 3 사전 대응 | Hard Rule | 산출 |
|---|---|---|---|
| C1: worker 10분 timeout → hang | Long-running off-worker 패턴 (vast.ai background + polling) | #16 | `scripts/poll_vast_progress.sh`, ops § 1 |
| C2: hermes network_access=false hard-code | 패치 영구 유지 + cycle 시작 시 검증 | (운영) | `scripts/verify_hermes_patch.sh`, ops § 2 |
| C3: sandbox approval 거부 | `danger-full-access` + `approval_policy=never` 유지 | (운영) | `~/.codex/config.toml`, ops § 3 |
| C4: kanban DB 손상 | 자동 백업 (cycle 시작 + 6h cron) + 표준 recovery | #18 | `scripts/backup_kanban_db.sh`, ops § 4 |
| C5: GPU util 0% / 진행 상태 불명 | progress.json 주기 갱신 + checkpoint | #17 | `scripts/write_progress.py`, `poll_vast_progress.sh`, ops § 5 |
| C6: 사용자 개입 빈도 높음 | D1~D6 사전 확정 + 자동 PASS 임계 + 비상시만 인간 게이트 | (운영) | ACCEPTANCE_CRITERIA `auto_continue`, ops § 6 |

Phase 3 운영 KPI (T3-01 + T3-02 + R2-F11 + R3-F22 fix — 측정 방법 명시):

| 지표 | 목표 | 측정 방법 | Phase 2 baseline 출처 |
|---|---|---|---|
| 사용자 개입 빈도 (DECIDE auto_continue 제외) | cycle당 < 1회 | SYNTH가 cycle 내 `human_intervention_count` 집계 (kanban task owner=human + DECIDE 제외) | Phase 2 Cycle M1 archive log (사용자 직접 명령 5회: 권한 승인 2회 / DB 복구 1회 / vast.ai check 2회) |
| Worker hang 발생 | 0회 | cycle metadata `worker_hang_count` (10분 timeout 사후 검출) | Phase 2 M5 hang 1건 (vast.ai 학습 timeout) |
| kanban DB 손상 | 0회 (자동 복구 성공) | preflight integrity_check fail 횟수 0 | Phase 2 1건 (수동 comment 작성 중) |
| vast.ai 학습 결과 회수 성공률 | 100% | polling task DONE marker 수신 / 전 학습 task 수 | Phase 2 0/1 (M5 미수행) |
| Cycle 평균 wall-clock | < 4h | SYNTH가 cycle 시작 (AUDIT spawn) ~ DECIDE 등록 시각 차 | Phase 2 M1 비교 불가 (미완 종료) → Phase 3 M2 첫 cycle을 baseline으로 |
| **차원별 단조 후퇴 (T1-05)** | 0회 | EVAL이 `per_rubric_monotone_evolution.warn_condition` 평가 | Phase 3 신규 |

cycle metadata 표준 schema (`cycle_report.json`):
```json
{
  "cycle_id": "M2",
  "started_at": "2026-...",
  "ended_at": "2026-...",
  "wall_clock_sec": 14400,
  "user_interventions": [{"task_id": "...", "kind": "...", "at": "..."}],
  "worker_hang_count": 0,
  "db_integrity_check_passes": 1,
  "vast_ai_recovery_rate": 1.0,
  "per_rubric_monotone_regressions": []
}
```

---

## Out of Scope (본 milestone 종결 후)

- 풀데이터 50K 학습 (Phase 3 Full, 별도 milestone)
- `klue/roberta-base` (110M, Phase 3 안정화 후 D5 update)
- `klue/roberta-large` (337M, 24GB VRAM, Phase 4 GPU budget 확보 후)
- 소분류 9~11 head (스펙 v1.1 § 8 단계 D, M4+ cycle)
- Paragraph-level auxiliary task (스펙 v1.1 § 8 단계 E)
- Production model registration / champion alias (Phase 4 인간 + 법무 게이트)
- 외부 배포 (Phase 4)

---

## Phase Transition Criteria

| 진입 | 조건 |
|---|---|
| Phase 3 Mid → Phase 3 Mid+1 (klue/roberta-base) | Success Criteria 1~5 통과 + small 모델 안정화 입증 + 사용자 [Phase-up] DECIDE |
| Phase 3 → Phase 4 (Full + Production) | Phase 3 PASS_CANDIDATE + bias audit + 인간 + 법무 게이트. PASS_FINAL은 Phase 4 acceptance에서만 허용 |

---

## Self-Improving Loop Reminder

각 Cycle MN은 8개 worker sub-task + DECIDE chain (Phase 2 HPO 구조 유지). M2는 WIRE-UP 1회성 sub-task가 AUDIT 앞에 추가된다:

```
T-CYCLE-M2-WIRE-UP   (gauss+turing, M2 only)
  ↓ Phase 3 evaluator + acceptance wire-up
T-CYCLE-MN-AUDIT     (tukey)
  ↓ 0순위: cycle_preflight.sh MN 실행 (Hard Rule #18 12-항목 체크 — R2-NF9 fix)
  ↓ MILESTONE_v3.md goal 재주입 (Hard Rule #10)
T-CYCLE-MN-SPLIT     (gauss)
T-CYCLE-MN-FEATURE   (gauss)
T-CYCLE-MN-MODEL     (gauss)
  ↓ M5/M6는 off-worker (Hard Rule #16) + progress.json (Hard Rule #17)
  ↓ MODEL/HPO task body metadata literal: `expected_duration_min > 10` + off-worker/polling instructions
T-CYCLE-MN-HPO       (gauss)
T-CYCLE-MN-EVAL      (spearman) ┐
T-CYCLE-MN-REVIEW    (turing)   ┘ 병렬 (T-HPO parent)
  ↓ per-rubric metric + per-rubric fairness gate (Hard Rule #15)
  ↓ EVAL executable path must call `fairness_gate_per_rubric()`, not helper-only dead code or overall-only fairness
T-CYCLE-MN-SYNTH     (aristotle)
  ↓ parent
DECIDE-MN            (사용자 또는 auto_continue)
  ↓ auto_continue 조건 충족 시 자동 [Continue] (6h grace 후)
```

SYNTH가 다음 Cycle M(N+1)의 8개 worker sub-task + DECIDE 등록 (PASS_CANDIDATE/FAIL 무관).
DECIDE-MN [Continue] 또는 auto_continue → Cycle M(N+1) 자동 시작.

---

## Cycle ID 명명 (T3-13 + R2-F16 + R2-NF10 fix — Phase 2/3 disambiguate)

Phase 3 Mid Multi-task는 prefix `M` 유지하되 다음 규칙으로 Phase 2와 disambiguate:

- **Phase 3 cycle ID**: `M2`, `M3`, ... (Phase 2의 `M1` 종료에 이어 M2부터)
- **Phase 2 archive** (이미 종료): `workspace/cycle_M1/` 그대로 보존. 신규 산출 금지
- **mlflow + kanban search 시 disambiguate**: cycle_id와 함께 **phase tag 의무** (`phase=3` 또는 `phase=2`) — MLflow `mlflow_recording.required_tags`에 `phase` 추가 필요 (Phase 3 wire-up 시점)
- **artifact 명명**: Phase 2 잔존 산출(`mlflow_remote_M1.db` 등)은 `mlflow_phase2_M1.db`로 rename 권고 (수동, 우선순위 낮음)
- **AGENTS.md cycle ID 명명 정합 (R2-NF10)**: AGENTS.md `Cycle ID 명명` 절(Mid-scale prefix `M`)에 본 disambiguate 규칙 cross-ref 의무 (별도 update)

Phase 3 Full 진입 시 prefix `F` 사용 (`F1`, `F2`, ... — AGENTS.md 본문 inheritance).

---

## References

- AGENTS.md v5 — Hard Rules #1~#18 (Phase 3 #15~#18 신설)
- `docs/multi_task_채점모델_구현_스펙_v_1_1.md` — 모델 스펙 v1.1
- `docs/phase_3_operations_guide_v_1_0.md` — 운영 가이드 v1.0
- `docs/dataset_채점방식_분석_v_1_0.md` v1.1 — 데이터셋 분석
- `ACCEPTANCE_CRITERIA.yaml` `stages.mid_multitask` — Phase 3 acceptance
- `scripts/` — 운영 도구 (backup_kanban_db / verify_hermes_patch / poll_vast_progress / write_progress / cycle_preflight)
- `MILESTONE_v2.md` — Phase 2 종료 노트
- `workspace/cycle_M1/` — Phase 2 보존 산출 (재현 기준)
- `dataset/sample_5k/manifest.json` — primary 데이터셋 spec (D4 inheritance)
