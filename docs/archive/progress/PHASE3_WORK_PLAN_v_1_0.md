# Phase 3 작업 계획 (Multi-task M5/M6 진입)

> **버전**: v1.2
> **작성 일자**: 2026-05-28
> **상태**: Stage 1 WIRE-UP 완료 (`ACCEPTANCE_CRITERIA.yaml stages.mid_multitask._implementation_status: wired_v1`). Stage 2 M2 본 cycle을 새 Hermes 보드 `essay-auto-scoring-research-phase3`에서 진행. M2R POLICY v3로 split fallback / 실행 정책 보완.
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
| **1** | **M2 WIRE-UP cycle (evaluate.py multi-task helper + tests)** | 완료 | `wired_v1` |
| **2** | **M2 본격 8 worker sub-task + DECIDE (AUDIT → SYNTH)** — vast.ai 학습 포함 | 진행 | 새 Phase 3 보드 등록 |
| 3 | M3+ 반복 자가발전 chain | × (DECIDE 게이트) | DECIDE 사용자 또는 auto_continue |
| 4 | Phase 3 종료 (acceptance 통과) | × | acceptance 충족 후 사용자 [Phase-up] DECIDE |

**현재 진행 범위**: Stage 2 M2 본 cycle을 Hermes Kanban native dependency로 등록하고 AUDIT부터 진행.

---

## 1. Stage 0 — 사전 준비

### 1.1 자율 진행 (본 작업)

| # | 항목 | 명령 |
|---|---|---|
| 0-1 | PyYAML 버전 확인 | `python3 -c "import yaml; print(yaml.__version__)"` ≥ 6.0 |
| 0-4 | hermes 패치 검증 | `bash scripts/verify_hermes_patch.sh --show-hash` |
| 0-8 | cycle_preflight dry-run | `bash scripts/cycle_preflight.sh M2` (warns 모니터) |

### 1.2 사용자 결정 필요 또는 후속 보강

| # | 항목 | 사유 |
|---|---|---|
| 0-2 | cron 등록 (6h 자동 백업) | 사용자 crontab 변경, 영구 효과. 미등록은 preflight WARN |
| 0-3 | 알림 push 채널 활성 (notify-send 또는 webhook/email 설정) | 현재 기본은 durable file-log. push 강제 시 `push_required_count: 1` |
| 0-5 | `.git/FETCH_HEAD` root 권한 정리 | 현재 `git status` 정상, 필요 시만 수행 |
| 0-6 | dataset 재생성 (`--validate-rubric`) | M2 AUDIT/SPLIT에서 실행 가능. I/O 비용 존재 |
| 0-7 | manifest.drift_skipped 검토 | 0이 아니면 사용자 판단 |

---

## 2. Stage 1 — M2 WIRE-UP cycle (본 작업 메인)

완료 상태. `ACCEPTANCE_CRITERIA.yaml stages.mid_multitask._implementation_status: wired_v1`.

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

- [x] pipelines/evaluate.py에 Phase 3 helper 추가
- [x] 차원별 score_band cutoff 함수 추가 (`score_band_per_rubric`)
- [x] fairness_gate_per_rubric() 함수 + 차원별 metric 구조 추가
- [x] auto_continue_check helper 추가
- [x] wire-up 완료 후 _implementation_status를 wired_v1로 변경
- [x] cycle_preflight.sh [11/12]가 wired_v1 확인 후에만 M3+ 진입 허용
- [ ] Phase 3 M2 SYNTH에서 cycle_report.json 표준 schema와 auto_continue_check 호출 의무 확인
- [ ] Phase 3 EVAL executable path에서 `fairness_gate_per_rubric()` 호출 확인. helper-only dead code 또는 overall-only `fairness_gate()` main path면 acceptance hard-block.

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

현재 진행 대상. 새 보드 `essay-auto-scoring-research-phase3`에 WIRE-UP evidence task와 M2 chain을 등록한다.

### 3.1 진입 조건

- Stage 1 WIRE-UP 완료 (`wired_v1`)
- 새 Phase 3 보드 생성 및 active 전환 완료
- `bash scripts/cycle_preflight.sh M2 --require-vast` fails=0
- cron/auto backup 미등록은 WARN으로 허용하되 M2 AUDIT에서 재보고

### 3.2 sub-task chain (kanban native dependency)

```
T-CYCLE-M2-WIRE-UP   (gauss+turing)  ← evidence task, 완료 처리
T-CYCLE-M2-AUDIT     (tukey)         ← preflight + MILESTONE_v3 goal 재주입
T-CYCLE-M2-SPLIT     (gauss)         ← default student.location + k=5; fallback region merge + k=3 if valid_n hard-block evidence exists
T-CYCLE-M2-FEATURE   (gauss)         ← TF-IDF + RoBERTa CLS cache + provenance
T-CYCLE-M2-MODEL     (gauss)         ← M1~M4 + M5 multi-task (vast.ai off-worker)
T-CYCLE-M2-HPO       (gauss)         ← Optuna 30 trial+ (M2 단독)
T-CYCLE-M2-EVAL      (spearman)      ┐
T-CYCLE-M2-REVIEW    (turing)        ┘ 병렬
T-CYCLE-M2-SYNTH     (aristotle)     ← cycle_report.json + 다음 cycle 등록
DECIDE-M2            (사용자/auto)
```

의존성:
- `WIRE-UP(done) → AUDIT → SPLIT → FEATURE → MODEL → HPO`
- `HPO → EVAL`, `HPO → REVIEW`
- `EVAL + REVIEW → SYNTH → DECIDE-M2`

### 3.3 split fallback policy (M2R POLICY v3)

기본 attempt는 `student.location + k=5`이다. 기본 split 산출에서 fold 중 하나라도 `valid_n >= 300`을 위반하면 M2에 한해 승인된 fallback `region merge + k=3`을 사용할 수 있다.

fallback acceptance 조건:
- `group_overlap_count=0`
- `student.location`은 split-only metadata로만 유지하고 모델 입력에 포함하지 않음
- `min_valid_n >= 300`
- evidence에 실패한 기본 split report와 승인된 fallback split manifest를 모두 포함

검증 명령 예시:

```bash
python3 pipelines/make_splits.py --input dataset/sample_5k/ --k 5 --output workspace/cycle_M2/splits/default_k5 --cycle-id M2 --group-key student.location --min-valid-n 300
python3 pipelines/make_splits.py --input dataset/sample_5k/ --k 3 --output workspace/cycle_M2/splits/region_k3 --cycle-id M2 --group-key region --min-valid-n 300
```

### 3.4 execution policy gates

- Long-running MODEL/HPO task bodies must include literal `expected_duration_min > 10` plus off-worker detach and one-shot polling instructions.
- M5/M6 Phase 3 must be multi-task only. scalar M5/HPO fallback is forbidden, including `pipelines/train_transformer.py` `num_labels=1` scalar acceptance path.
- EVAL executable path must call `fairness_gate_per_rubric()` for Phase 3 per-rubric fairness. Helper-only dead code or overall-only `fairness_gate()` output is not acceptable.

### 3.5 비용 추정

- vast.ai RTX 3060 (8GB VRAM): cycle당 ~1.5h × $0.10/h ≈ $0.15
- Optuna HPO 30 trial: ~3h × $0.10/h ≈ $0.30
- M2 단독 cycle 총: ~$0.50 (cost_circuit_breaker max_usd_per_cycle = $20 안전 마진)

---

## 4. Stage 3 — M3+ 반복 (자가발전 chain)

- SYNTH가 다음 cycle 8 worker sub-task + DECIDE 자동 등록
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
7. fold valid_n ≥ 300 (default `student.location + k=5`; M2 fallback `region merge + k=3` only with default failure evidence)
8. judgement: PASS_CANDIDATE (`final_judgement_allowed: false`)
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
| W0 | 작업 계획 문서 최신화 | `docs/plans/PHASE3_WORK_PLAN_v_1_0.md` v1.2 |
| W1 | 새 Phase 3 보드 확인 | `hermes kanban boards show` |
| W2 | preflight | `scripts/cycle_preflight.sh M2 --require-vast` |
| W3 | WIRE-UP evidence task 등록/완료 | `T-CYCLE-M2-WIRE-UP` |
| W4 | M2 worker chain 등록 | AUDIT/SPLIT/FEATURE/MODEL/HPO/EVAL/REVIEW/SYNTH/DECIDE |
| W5 | dispatcher 진행 확인 | `hermes kanban stats`, `hermes kanban list` |

W5 완료 후:
- AUDIT task가 ready/todo 상태에서 dispatcher 대상이 된다.
- M2 MODEL/HPO에서 vast.ai 비용이 발생하므로 cost circuit breaker와 progress polling을 필수 적용한다.
- DECIDE-M2에서 `[Continue]`, `[Phase-up]`, `[Stop]` 중 하나를 기록한다.

---

## 8. References

- `MILESTONE_v3.md` Phase 3 진입 게이트 + Success Criteria
- `docs/multi_task_채점모델_구현_스펙_v_1_1.md` v1.1.5 § 6 / § 11.2 / § 14
- `docs/phase_3_operations_guide_v_1_0.md` v1.0.3 § 1 / § 6
- `ACCEPTANCE_CRITERIA.yaml stages.mid_multitask`
- `AGENTS.md` Hard Rule #15~#18 + 8 worker sub-task + DECIDE pattern
- `scripts/cycle_preflight.sh` [11/12] wire-up check
- `pipelines/evaluate.py` (current toy 분기만, mid_multitask 분기 wire-up 대상)
- `pipelines/extract_5k.py:validate_rubric_for_phase3` (사전 검증 헬퍼)
