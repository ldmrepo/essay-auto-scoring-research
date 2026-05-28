# Phase 3 작업 계획 (Multi-task M5/M6 진입)

> **버전**: v1.0
> **작성 일자**: 2026-05-28
> **선행 commit**: `fefd4fa feat(phase-3): Phase 3 multi-task 진입 준비 — 12 산출 + 6 사이클 검수 종결`
> **선행 문서**:
> - `MILESTONE_v3.md` — Phase 3 goal anchor + success criteria
> - `docs/multi_task_채점모델_구현_스펙_v_1_1.md` v1.1.5 — 모델 구현 스펙
> - `docs/phase_3_operations_guide_v_1_0.md` v1.0.3 — 운영 가이드
> - `docs/reviews/PHASE3_REVIEW_FINAL_v_1_0.md` — 6 사이클 검수 종합

---

## 0. 본 작업 범위

본 계획은 Phase 3 진입을 4 Stage로 분해. 자율 진행 vs 사용자 게이트 영역 명확화.

| Stage | 작업 | 자율 가능 | 게이트 |
|---|---|---|---|
| **0** | 사전 준비 (cron / alert / preflight / dataset 재생성) | 부분 (cron/dataset은 사용자 결정) | 환경 영향 |
| **1** | **M2 WIRE-UP cycle (evaluate.py multi-task 분기 + tests)** | **본 작업 범위** | tests 통과 후 commit |
| 2 | M2 본격 9 sub-task (AUDIT → SYNTH) — vast.ai 학습 포함 | × (kanban + 비용 발생) | 사용자 명시 |
| 3 | M3+ 반복 자가발전 chain | × (DECIDE 게이트) | DECIDE 사용자 또는 auto_continue |
| 4 | Phase 3 종료 (acceptance 통과) | × | acceptance 충족 후 사용자 [Phase-up] DECIDE |

**본 commit 진행 범위**: Stage 1 WIRE-UP cycle만. Stage 0의 자동 부분 + Stage 1 코드/테스트 + ACCEPTANCE wired_v1 갱신.

---

## 1. Stage 0 — 사전 준비

### 1.1 자율 진행 (본 작업)

| # | 항목 | 명령 |
|---|---|---|
| 0-1 | PyYAML 버전 확인 | `python3 -c "import yaml; print(yaml.__version__)"` ≥ 6.0 |
| 0-4 | hermes 패치 검증 | `bash scripts/verify_hermes_patch.sh --show-hash` |
| 0-8 | cycle_preflight dry-run | `bash scripts/cycle_preflight.sh M2` (warns 모니터) |

### 1.2 사용자 결정 필요 (게이트)

| # | 항목 | 사유 |
|---|---|---|
| 0-2 | cron 등록 (6h 자동 백업) | 사용자 crontab 변경, 영구 효과 |
| 0-3 | 알림 채널 활성 (notify-send 또는 webhook/email 설정) | 사용자 환경 + 외부 endpoint 설정 |
| 0-5 | `.git/FETCH_HEAD` root 권한 정리 (`sudo chown -R dev:dev .git`) | sudo 권한 |
| 0-6 | dataset 재생성 (`--validate-rubric`) | I/O 비용 (39,591건 stream 처리, drift 통계 산출) |
| 0-7 | manifest.drift_skipped 검토 | 0이 아니면 사용자 판단 |

---

## 2. Stage 1 — M2 WIRE-UP cycle (본 작업 메인)

`ACCEPTANCE_CRITERIA.yaml stages.mid_multitask._implementation_status: not_wired_yet → wired_v1`로 전환하는 단일 cycle.

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `pipelines/evaluate.py` | mid_multitask 분기 + `score_band_per_rubric` + `fairness_gate_per_rubric` + `auto_continue_check` helper |
| `pipelines/train_transformer.py` | Phase 3 학습 진입 시 `validate_rubric_for_phase3` 사전 호출 |
| `tests/test_evaluate_phase3.py` | unit test 8건+ (per_rubric_native cutoff / fairness / auto_continue / monotone) |
| `ACCEPTANCE_CRITERIA.yaml` | `_implementation_status: wired_v1` (모든 wire-up 완료 후 갱신) |

### 2.2 evaluate.py 추가 함수 spec

```python
# score_band_per_rubric: native 0~3 → low_0_1 / mid_1_2 / high_2_3
def score_band_per_rubric(score: float) -> str: ...

# fairness_gate_per_rubric: 4 dim (exp/org/cont/overall) 각각 fairness gate 평가
# overall은 raw 0~30, per-rubric은 native 0~3 cutoff 적용
def fairness_gate_per_rubric(
    predictions: pd.DataFrame,
    rng: np.random.Generator,
    bootstrap_b: int = 1000,
) -> dict[str, dict]: ...

# auto_continue_check: ACCEPTANCE auto_continue 7 조건 평가
# grace_cycles=3 + window_cycles=2 + min_improvement_per_cycle=0.01 적용
def auto_continue_check(
    cycle_history: list[dict],
    current_cycle_idx: int,
    config: dict,
) -> tuple[bool, str]: ...
```

### 2.3 wire-up 의무 항목 (ACCEPTANCE `_wire_up_required` 6항목)

- [ ] pipelines/evaluate.py에 mid_multitask 분기 추가 (현재 toy 단일 분기만 존재)
- [ ] 차원별 score_band cutoff 함수 추가 (T1-04, score_band_per_rubric)
- [ ] fairness_gate_per_rubric() 함수 + 차원별 lower95 계산
- [ ] auto_continue 조건 evaluator/SYNTH 양측 구현
- [ ] wire-up 완료 후 _implementation_status를 wired_v1로 변경 + Phase 3 M2 SYNTH 검증
- [ ] cycle_preflight.sh [11/12]가 wired_v1 확인 후에만 M3+ 진입 허용

### 2.4 검증

- `pytest tests/test_evaluate_phase3.py -v` 8건+ 모두 통과
- `pytest tests/test_extract_5k.py` 24 passed 회귀 없음
- `bash scripts/cycle_preflight.sh M2` 결과에서 [11/12] WARN (not_wired_yet, M2 허용) → wired_v1 갱신 후 OK
- `python3 -c "import yaml; data = yaml.safe_load(open('ACCEPTANCE_CRITERIA.yaml')); assert data['stages']['mid_multitask']['_implementation_status'] == 'wired_v1'"`

### 2.5 산출 (commit 대상)

- pipelines/evaluate.py (modified)
- pipelines/train_transformer.py (modified)
- tests/test_evaluate_phase3.py (new)
- ACCEPTANCE_CRITERIA.yaml (modified)
- docs/plans/PHASE3_WORK_PLAN_v_1_0.md (본 문서, new)

---

## 3. Stage 2 — M2 본격 cycle (사용자 게이트 후)

본 작업 범위 외 (cron + vast.ai 비용 + DECIDE 게이트 필요).

### 3.1 진입 조건

- Stage 1 WIRE-UP commit + push 완료
- Stage 0 사용자 결정 항목 (0-2/0-3/0-6) 처리
- `bash scripts/cycle_preflight.sh M2 --require-vast --auto-destroy-stale --vast-label essay-auto-scoring` fails=0

### 3.2 sub-task chain (kanban native dependency)

```
T-CYCLE-M2-AUDIT     (tukey)         ← preflight + MILESTONE_v3 goal 재주입
T-CYCLE-M2-SPLIT     (gauss)         ← k=5, valid_n ≥ 300
T-CYCLE-M2-FEATURE   (gauss)         ← TF-IDF + RoBERTa CLS cache + provenance
T-CYCLE-M2-MODEL     (gauss)         ← M1~M4 + M5 multi-task (vast.ai off-worker)
T-CYCLE-M2-HPO       (gauss)         ← Optuna 30 trial+ (M2 단독)
T-CYCLE-M2-EVAL      (spearman)      ┐
T-CYCLE-M2-REVIEW    (turing)        ┘ 병렬
T-CYCLE-M2-SYNTH     (aristotle)     ← cycle_report.json + 다음 cycle 등록
DECIDE-M2            (사용자/auto)
```

### 3.3 비용 추정

- vast.ai RTX 3060 (8GB VRAM): cycle당 ~1.5h × $0.10/h ≈ $0.15
- Optuna HPO 30 trial: ~3h × $0.10/h ≈ $0.30
- M2 단독 cycle 총: ~$0.50 (cost_circuit_breaker max_usd_per_cycle = $20 안전 마진)

---

## 4. Stage 3 — M3+ 반복 (자가발전 chain)

- SYNTH가 다음 cycle 9 sub-task + DECIDE 자동 등록
- HPO 누적 50+ trial 도달 (M2 30 + M3 10 + M4 10)
- PASS_CANDIDATE 2회 + 개선 < 0.01 시 FAIL_STOP_NO_GAIN escalation
- grace_cycles=3 (M2~M4 면제) → M5+ evolution_progress_required 본격 평가

---

## 5. Stage 4 — Phase 3 종료

### 5.1 acceptance 통과 (10 success criteria)

1. M5 overall qwk_lower95 ≥ 0.40
2. M5 per-rubric qwk_lower95 ≥ 0.30 (exp/org/cont)
3. M5 > M4 strict (overall)
4. M6 > M5 strict (overall)
5. All-dimension fairness gate (× 0.7)
6. HPO 누적 trial ≥ 50
7. fold valid_n ≥ 300
8. judgement: PASS_CANDIDATE / PASS_FINAL
9. per-rubric monotone regression = 0
10. evaluator wire-up: wired_v1

### 5.2 종료 산출

- `workspace/cycle_M{N}/` 모든 cycle 보존
- `cycle_report_M{N}.json` 표준 schema
- `MILESTONE_v3.md` 종료 노트 (Phase 2 inheritance 형식)
- 사용자 [Phase-up] DECIDE → Phase 4 (Full + production, 별 milestone)

---

## 6. 비상 게이트 (모든 Stage)

| 트리거 | 자동 조치 | 사용자 알림 |
|---|---|---|
| cycle_preflight FAIL 1건+ | cycle 진입 거부 | `notify_alert preflight_self_test critical` |
| cost_circuit_breaker_breach | cycle pause | `notify_alert cost_circuit_breaker_breach critical` |
| hermes_patch_verification_fail | cycle 진입 거부 | 사용자 게이트 |
| kanban_db_recovery_required | `ops § 4.4` daemon stop + WAL/SHM 정리 + 복원 | critical alert |
| pass_candidate_stuck_consecutive_max | FAIL_STOP_NO_GAIN escalation | critical alert |
| progress_stall_detected | polling task 사용자 게이트 spawn | warn alert |
| 3 cycle 연속 acceptance fail | Layer 3 escalation | critical alert |

---

## 7. 본 작업 진행 순서

| # | 단계 | 명령 / 산출 |
|---|---|---|
| W0 | 작업 계획 문서 (본 문서) | `docs/plans/PHASE3_WORK_PLAN_v_1_0.md` |
| W1 | evaluate.py wire-up | mid_multitask 분기 + 3 helper 함수 |
| W2 | tests/test_evaluate_phase3.py | unit test 8건+ |
| W3 | train_transformer.py validate 호출 | `validate_rubric_for_phase3` 사전 검증 |
| W4 | ACCEPTANCE_CRITERIA wired_v1 | tests 통과 후 갱신 |
| W5 | commit + push | Stage 1 단일 commit |

W5 완료 후 사용자 결정:
- Stage 2 진입 (M2 본격 cycle, kanban + vast.ai)
- 또는 Stage 0 잔여 (cron / dataset 재생성) 처리 후 진입
- 또는 일시 대기

---

## 8. References

- `MILESTONE_v3.md` Phase 3 진입 게이트 + Success Criteria
- `docs/multi_task_채점모델_구현_스펙_v_1_1.md` v1.1.5 § 6 / § 11.2 / § 14
- `docs/phase_3_operations_guide_v_1_0.md` v1.0.3 § 1 / § 6
- `ACCEPTANCE_CRITERIA.yaml stages.mid_multitask`
- `AGENTS.md` Hard Rule #15~#18 + 9 sub-task pattern
- `scripts/cycle_preflight.sh` [11/12] wire-up check
- `pipelines/evaluate.py` (current toy 분기만, mid_multitask 분기 wire-up 대상)
- `pipelines/extract_5k.py:validate_rubric_for_phase3` (사전 검증 헬퍼)
