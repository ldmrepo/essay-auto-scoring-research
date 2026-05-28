# Phase 3 산출 검수 종합 보고서 (6 사이클 종결)

> **버전**: v1.0 (FINAL)
> **작성 일자**: 2026-05-28
> **검수 팀**: R1 Spec Compliance / R2 Hard Rules + Acceptance / R3 Operations + Scripts / R4 Risk + Security
> **종결 사이클**: 6차 (1차 검수 → 5차 fix → 6차 재검수까지)

---

## 0. 최종 판정

| Reviewer | 6차 판정 | 코드 측 차단 사유 |
|---|---|---|
| R1 Spec Compliance | **CONDITIONAL GO** | 0 (잔여는 정책 anchor / NIT) |
| R2 Hard Rules + Acceptance | **GO** | 0 |
| R3 Operations + Scripts | **GO** | 0 |
| R4 Risk + Security | **NO-GO (NEW-C1 사용자 게이트만)** | 0 (NEW-C1은 환경 권한 문제) |

**종합**: 코드 측 진입 차단 사유 0건. 유일한 차단은 NEW-C1 사용자 게이트 (root 소유 `.env` 권한 변경 + API key rotation).

## 1. 검수 사이클 추이

| 사이클 | CRITICAL | HIGH | MEDIUM | LOW | 합계 | functional regression |
|---|---|---|---|---|---|---|
| 1차 (초안 검수) | 11 | 27 | 24 | 22 | 84 | (baseline) |
| 2차 fix → 3차 재검수 | 2 | 9 | 22 | 4 | 37 | 다수 |
| 3차 fix → 4차 재검수 | 1 | 8 | 18 | 2 | 29 | 일부 |
| 4차 fix → 5차 재검수 | 1 | 4 | 9 | 4 | 18 | 일부 |
| 5차 fix → **6차 재검수** | **0** | **0** | **2** | **4** | **6** | **0** |

**수렴 도달**: 5 사이클에서 18건 → 6 사이클에서 6건 (functional regression 0).

## 2. 적용 fix 산출물

### 신규 / 변경 파일 (12개)

| 파일 | 줄수 | 변경 |
|---|---|---|
| `docs/multi_task_채점모델_구현_스펙_v_1_1.md` | 705 | v1.0 → v1.1.5 (6차 update) |
| `docs/phase_3_operations_guide_v_1_0.md` | 514 | v1.0 → v1.0.3 |
| `docs/dataset_채점방식_분석_v_1_0.md` (v1.1) | (이전) | Phase 2 작업 보존 |
| `docs/reviews/PHASE3_REVIEW_CHECKLIST_v_1_0.md` | 200+ | 1차 finding tracker |
| `docs/reviews/PHASE3_REVIEW_FINAL_v_1_0.md` (본 문서) | — | 6 사이클 종합 |
| `MILESTONE_v3.md` | 192 | placeholder → 본격 (success criteria + wire-up task + KPI) |
| `AGENTS.md` | 410 | Hard Rule #15~#18 신설 + 표현 정합 |
| `ACCEPTANCE_CRITERIA.yaml` | 500+ | `mid_multitask` stage 신설 (per-rubric / fairness gate / auto_continue) |
| `configs/board_config.yaml` | 95 | `notify_channels` 신규 (10 triggers) |
| `pipelines/extract_5k.py` | 287 | `validate_rubric_for_phase3` 함수 + `--validate-rubric` flag + manifest `drift_skipped` |
| `scripts/backup_kanban_db.sh` | 145 | 신규 (DB 동적 경로 + LABEL 화이트리스트 + 권한 0600/0700 + flock + skip 카운터) |
| `scripts/verify_hermes_patch.sh` | 134 | 신규 (비주석 매치 + `--auto-repatch-confirmed` 2단계 게이트 + LINE_COUNT 가드) |
| `scripts/poll_vast_progress.sh` | 211 | 신규 (vastai execute single-quote + state persist + one-shot + notify_alert) |
| `scripts/write_progress.py` | 230 | 신규 (multi-GPU + atomic write + rate-limit + NOP fallback) |
| `scripts/cycle_preflight.sh` | 397 | 신규 (12-항목 통합 + PyYAML 파싱 + label filter + notify_alert wire-up) |
| `scripts/notify_alert.sh` | 103 | 신규 (3-채널 dispatcher + 화이트리스트 + alerts.log) |
| `scripts/__init__.py` | 0 | 신규 (패키지 import) |
| `scripts/README.md` | (이전) | 신규 |

총 신규/변경 약 3500+ 줄.

### Hard Rules 신설 (Phase 3)

- **#15** Multi-task only for M5/M6 (single-target 회귀 금지)
- **#16** Long-running off-worker (10분 초과 작업 worker foreground 금지)
- **#17** Progress observability (progress.json 주기 갱신 + DONE/FAIL marker)
- **#18** Kanban DB auto-backup (cycle 시작 + 6h cron)

### ACCEPTANCE_CRITERIA `mid_multitask` stage 핵심

- `_implementation_status: not_wired_yet` + `_wire_up_required` 6항목
- `m5_overall_qwk_lower95 ≥ 0.40` / `m5_per_rubric_qwk_lower95 ≥ 0.30`
- `score_band_cutoffs` (overall raw 0~30 + per-rubric native 0~3)
- `fairness_gate.unit_per_dimension` (raw/native 차원별)
- `per_rubric_monotone_evolution` (cross-cycle warn) + `m6_per_rubric_evolution` (same-cycle warn)
- `segment_metrics` (type/grade_band/score_band)
- `auto_continue` (consecutive_pass_candidate_max=2 + grace_cycles=3 + evolution_progress_required)
- `hpo.per_cycle_min_trials` (M2 단독 30 + M3+ 최소 5 + 누적 50)

### 6 사이클 적용 fix 통계

| 카테고리 | 적용 |
|---|---|
| Tier 1 CRITICAL (1차) | 11건 |
| Tier 2 HIGH (1차) | 19건 |
| Tier 3 MEDIUM (1차) | 25건 |
| 2~5차 사이클 fix 누적 | 약 50+건 |
| **총 적용** | **약 100+건** |

---

## 3. 잔여 Backlog (6차 종결 후)

### 3.1 사용자 환경 (자율 처리 불가)

| ID | Sev | 항목 | 사용자 처리 |
|---|---|---|---|
| **NEW-C1** | CRITICAL | `.env` root:0644, VAST_API_KEY 평문 노출 | `sudo chown dev:dev .env && chmod 600 .env` + vast.ai dashboard에서 API key rotation + git history scan |

### 3.2 코드 측 backlog (운영 보강 — Phase 3 진입 후 처리 가능)

| ID | Sev | 항목 | 처리 위치 |
|---|---|---|---|
| R1-NEW6-1 | MEDIUM | SYNTH block 구현 메커니즘 anchor 부재 | M2 wire-up cycle plan 시 `phase_3_operations_guide` 또는 `cycle_task_chain`에 검사 step 신설 |
| R4-R6-3 | MEDIUM | `verify_hermes_patch.sh` exit code 차별화 (exit 2/3/4/5 caller 분기) | `cycle_preflight.sh:68` caller에 case 분기 |
| R1-NEW6-2 | LOW | NOTE "§ 12.3 후반" forward-reference fragility | 스펙 v1.1.6에서 명시적 line anchor |
| R1-NEW6-3 | LOW | § 14 V8 시나리오 NEW-R1 CLI flag 검증 row 추가 | 스펙 v1.1.6 |
| R2-NEW-R3 | LOW | cycle index 카운팅 기준 (M2=0/1) 명시 | M2 wire-up implementor 결정 후 명시 |
| R4-REG5-2 | MEDIUM | `sandbox_workspace_write` 키 단독 silent pass | `cycle_preflight.sh:113-116` 보강 |
| R4-REG5-3 | LOW | `.*_KEY=` regex false positive (`PUBLIC_KEY_PATH` 등) | secrets 패턴 정교화 |
| R4 R6-1/R6-2/R6-4 | LOW | functional 무해 (이론상 edge case) | 우선순위 낮음 |
| R3 5차 #2/#5/#6/#7/#8 | LOW/MEDIUM | jq fallback / stall persist / notify whitelist 등 | 운영 중 모니터링 |

총 backlog: 약 12건 (모두 운영 보강, functional 영향 없음).

---

## 4. Phase 3 진입 조건

### 4.1 즉시 차단 (1건)

- **NEW-C1 사용자 처리** — `.env` 권한 + key rotation. preflight [3/12]가 매번 FAIL 발생 → cycle 진입 거부

### 4.2 진입 후 cover 가능 (운영 보강)

- R1-NEW6-1 (SYNTH block anchor) — M2 wire-up task plan에서 명시
- R4-R6-3 (exit code 차별화) — cycle_preflight caller 개선

### 4.3 NIT / 우선순위 낮음

- 나머지 backlog (LOW 4 + MEDIUM 1)

---

## 5. 사용자 확인 항목

1. **NEW-C1 처리 의사**
   - `sudo chown dev:dev /home/dev/work/essay-auto-scoring-research/.env`
   - `chmod 600 /home/dev/work/essay-auto-scoring-research/.env`
   - vast.ai dashboard에서 기존 API key 폐기 + 신규 발급
   - 신규 key를 0600 권한 .env에 저장

2. **commit 진행 명시** (현재 커밋 금지 유지 중)
   - 6 사이클 결과 + 본 종결 보고서를 단일 commit으로 진행 권고
   - 또는 사용자가 별도 분리 요청 시 분리

3. **Phase 3 M2 진입 결정**
   - NEW-C1 처리 + commit 완료 후
   - M2 wire-up cycle 첫 sub-task로 SYNTH block 메커니즘 (R1-NEW6-1) 동시 처리

---

## 6. 참조

- `docs/reviews/PHASE3_REVIEW_CHECKLIST_v_1_0.md` — 1차 finding tracker (84건)
- `MILESTONE_v3.md` — Phase 3 milestone (success criteria + wire-up task)
- `docs/multi_task_채점모델_구현_스펙_v_1_1.md` v1.1.5 — 모델 구현 스펙
- `docs/phase_3_operations_guide_v_1_0.md` v1.0.3 — 운영 가이드
- `AGENTS.md` — Hard Rule #15~#18
- `ACCEPTANCE_CRITERIA.yaml` `stages.mid_multitask` — Phase 3 acceptance
- `scripts/` — 6개 신규 운영 스크립트
- `configs/board_config.yaml` `notify_channels` — 비상 알림 dispatcher
