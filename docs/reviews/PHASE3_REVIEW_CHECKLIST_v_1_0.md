# Phase 3 산출물 검수 체크리스트 (R1~R4)

> **작성**: 2026-05-28
> **검수 팀**: R1 Spec Compliance / R2 Hard Rules + Acceptance / R3 Operations + Scripts / R4 Risk + Security
> **검수 대상**: docs/multi_task_채점모델_구현_스펙_v_1_1.md / docs/phase_3_operations_guide_v_1_0.md / MILESTONE_v3.md / AGENTS.md / ACCEPTANCE_CRITERIA.yaml / scripts/*
> **총 finding**: 84건 (CRITICAL 11 / HIGH 27 / MEDIUM 24 / LOW 22)

---

## 검수 후 사실 검증

| 주장 | 검증 결과 |
|---|---|
| R3-F3: AGENTS.md Hard Rule #15~#18 부재 | **False positive** — 본문 존재 (line 65/74/81/89). R3 grep 패턴 오류 |
| R3-F1: kanban DB 경로 오류 | **확인** — 실제 `~/.hermes/kanban/boards/<board>/kanban.db`. `current` 파일 active board 지정 |
| R3-F2: `vastai ssh` 미존재 | **확인** — `attach ssh`, `ssh-url`, `execute`만 존재 |

---

## Tier 1 — CRITICAL (즉시 차단, 모두 fix)

### 운영 자동화 무력화

- [ ] **T1-01 [R3-F1]** kanban DB 경로 수정 — `~/.hermes/kanban/db.sqlite` → 실제 `~/.hermes/kanban/boards/$(cat current)/kanban.db` 동적 도출. WAL/SHM 파일 처리. `backup_kanban_db.sh` + `cycle_preflight.sh` + ops guide § 4 일괄 update
- [ ] **T1-02 [R3-F2]** `vastai ssh` → `vastai execute "<id>" "<cmd>"` 변경. `poll_vast_progress.sh` 전 호출 (4건) + ops guide § 1/§ 5 update

### Acceptance ↔ 코드 wire-up 부재

- [ ] **T1-03 [R2-F1]** `evaluate.py` `mid_multitask` 분기 부재 → ACCEPTANCE_CRITERIA에 `_implementation_status: not_wired_yet` 명시 + Phase 3 M2 first sub-task로 "evaluator multi-task wire-up" 등록 (MILESTONE_v3 보강)
- [ ] **T1-04 [R2-F2]** `score_band` cutoff가 0~30 raw 전용 → 차원별 0~3 cutoff 정의 추가 (스펙 § 6 + ACCEPTANCE_CRITERIA + Hard Rule #14 본문)
- [ ] **T1-05 [R2-F3]** 차원별 단조 후퇴 검출 게이트 부재 → MILESTONE_v3 Success Criteria에 "차원별 monotonic regression count" KPI 추가. ACCEPTANCE_CRITERIA `per_rubric_diagnostic_qwk: info`를 `warn`으로 격상

### 보안 injection (`danger-full-access` 정책 가드 부재)

- [ ] **T1-06 [R4-F1]** `poll_vast_progress.sh` shell command injection — INSTANCE_ID/REMOTE_PATH 입력 화이트리스트 (`^[0-9]+$` / `^[A-Za-z0-9_./-]+$`) + `printf %q` escape
- [ ] **T1-07 [R4-F2]** `backup_kanban_db.sh` LABEL injection — LABEL 화이트리스트 (`^[A-Za-z0-9_.-]+$`) + `realpath` prefix 확인 + `cycle_preflight.sh` CYCLE_ID도 동일 validation
- [ ] **T1-08 [R4-F3]** 백업 파일/디렉토리 권한 0644 → 0600 + `mkdir -m 700` 강제

### 스펙 미완 (구현 불가)

- [ ] **T1-09 [R1-F1]** `w_overall=0.5` magic number 하드코딩 → 모듈 상수 `W_OVERALL_DEFAULT` 또는 dataset-level `w_overall` 컬럼으로 단일화. § 13 D7 변경 시 단일 지점 update
- [ ] **T1-10 [R1-F2]** `w_exp/w_org/w_cont` 산출 식 누락 → `compute_rubric_targets`에 `w_exp = rubric["expression_weight"]["exp"]` 등 추가. 정규화 정책(합=1 또는 합=10) 명시
- [ ] **T1-11 [R1-F3]** 인덱스-키 매핑 가정 미가드 (`exp_grammar` ↔ `essay_scoreT_exp[0]`) → V1 검증 시나리오에 "학년군별 sample 손산" 추가. 매핑 실패 fallback 명시

---

## Tier 2 — HIGH (운영 안정성 영향, 핵심 fix)

### Polling 패턴 재설계 (C1 재현 위험)

- [x] **T2-01 [R3-F14 / R3-F7 / R4-F9]** polling task가 worker로 실행되면 10분 timeout 재현. one-shot poll + SYNTH self-respawn 패턴으로 재작성 (`poll_vast_progress.sh "$INSTANCE_ID" /workspace/progress.json --once` 기본 + 다음 polling task 자동 spawn). ops guide § 1.2 표 갱신
- [ ] **T2-02 [R3-F6]** stall 감지 로직: fetch 성공 + last_updated 미변경 카운트 / fetch 실패 별도 카운터. `jq -r '.last_updated'` 사용
- [ ] **T2-03 [R3-F11 / R4-F15]** `cycle_preflight.sh` vast.ai 잔여 인스턴스 WARN→FAIL 격상 (또는 `--auto-destroy-stale` 플래그). VAST 사용 cycle 자동 판별 (`--require-vast` 또는 cycle plan plays_to)

### PASS_CANDIDATE stuck escalation

- [ ] **T2-04 [R2-F6 / R3-F13 / R4-F8]** ACCEPTANCE_CRITERIA `auto_continue`에 `consecutive_pass_candidate_max: 2` 추가. evolution progress 조건(`best_metric_strictly_improved_in_last_N_cycles`) 추가. 미충족 시 인간 게이트 spawn

### 사용자 알림 채널 (push 부재)

- [ ] **T2-05 [R4-F4]** 비상 게이트 task 생성 시 외부 채널 push 1종 이상 의무화 (notify-send / email / Slack webhook / gotify 중 택1). `configs/board_config.yaml` `notify_channels: [...]` 정의 + `cycle_preflight` #8 항목 추가 (채널 가용성)

### Hermes patch 검증 강화

- [ ] **T2-06 [R3-F4 / R4-F13]** `verify_hermes_patch.sh` 주석 매치 false positive 차단 — `grep -E '^[^#]*"sandbox_workspace_write\.network_access=true"'` + 실제 효과 검증 (sandbox subprocess에서 outbound test) 또는 라인 위치 + sha256 동반

### 코드 wire-up + 정의 누락

- [ ] **T2-07 [R2-F4]** `train_valid_qwk_gap_abs` multi-task 정의 — `applies_to: [exp, org, cont, overall]` + `aggregation: max` 명시
- [ ] **T2-08 [R2-F5]** `inherits: mid` schema 미정의 → inherits 메커니즘 명시 (상속 규칙 + override) 또는 inherits 제거하고 `mid_multitask` self-contained
- [ ] **T2-09 [R2-F7]** Hard Rule #16 enforce 메커니즘 — "vast.ai 학습 task spawn 시 metadata `expected_duration_min > 10` 표기 의무 + SYNTH/REVIEW가 metadata 부재 시 block" 명시
- [ ] **T2-10 [R2-F8]** overall fairness 단위 명시 — "overall fairness gate는 raw 0~30 역변환 후 평가" 명시
- [ ] **T2-11 [R1-F4]** § 12.2 M6 인터페이스 4번째 슬롯 단위(norm vs raw) + 변환 책임 주체 확정. round-trip 책임 위치
- [ ] **T2-12 [R1-F5]** Hard Rule #15~#18 본문 정의가 스펙 § 4 표에만 단어로 언급 → AGENTS.md에 이미 본문 존재(검증 완료). 스펙 § 4에 cross-ref 라인 번호 추가
- [ ] **T2-13 [R1-F6]** 차원별 fairness band 정의 모호 → 차원별 native 0~3 band cutoff 명시 (T1-04와 통합 처리)

### Scripts 안정성

- [ ] **T2-14 [R3-F5 / R4-F6]** `backup_kanban_db.sh` `flock` 추가 (race 차단) + auto_*만 strict 매치 (`^auto_[0-9]{8}T[0-9]{6}Z\.db$`) + LABEL pattern 강제
- [ ] **T2-15 [R3-F8]** `scripts/__init__.py` 추가 + `write_progress.py` 호출 경로 명시 (vast.ai bootstrap PYTHONPATH 또는 fallback NOP)
- [ ] **T2-16 [R3-F10]** `cycle_preflight.sh` vast.ai count `jq '.[].id' | wc -l` 사용 (grep substring 오카운트 차단)
- [ ] **T2-17 [R3-F12]** `cycle_preflight.sh` 디스크 임계 — `LANG=C df -P` + 85% warn / 95% fail + 가용 GB 절대값 출력
- [ ] **T2-18 [R4-F5]** 백업 deadlock 회피 — cycle_*/manual_* 보관 회전 N개 또는 age cap. preflight 실패 시 즉시 외부 알림 + cleanup script cycle 외부 실행 절차 추가
- [ ] **T2-19 [R4-F7]** 신규 hermes profile 정책 검증 — `cycle_preflight` #2를 `~/.codex/config.toml` + `~/.hermes/profiles/*.toml` 일괄 grep

---

## Tier 3 — MEDIUM (정합성 및 enforce 영향)

### KPI 측정 인프라

- [ ] **T3-01 [R2-F10 / R2-F11]** MILESTONE_v3 Success Criteria 표에 Hard Rule mapping column + 측정 방법 column 추가. "cycle당 < 1회" 측정 방법 명시 (cycle metadata `user_interventions:` 강제) + Phase 2 baseline 출처 인용
- [ ] **T3-02 [R3-F22]** cycle metadata 표준화 — SYNTH task가 `user_interventions`, `wall_clock_sec`, `worker_hang_count` 집계 강제. `cycle_report.json` 표준 schema 정의

### 스펙 미세 정합

- [ ] **T3-03 [R1-F7]** A1a 임계 0.30의 근거 각주 + 실패 judgement 컬럼 추가
- [ ] **T3-04 [R1-F8]** 손실 식 ↔ 코드 (1/4 factor) 일관성 — 식 또는 코드 통일
- [ ] **T3-05 [R1-F9]** M6 입력 모델 contract 명시 — M3/M4 scalar의 4D broadcast 규칙 또는 "M4+M5만"
- [ ] **T3-06 [R1-F10]** `worst_band_qwk = min(mid, high)` 명시 + low SKIP_UNSTABLE 트리거 별도 정의
- [ ] **T3-07 [R1-F11]** D10 트리거를 측정 가능 형태로 ("Cycle M4+ per_rubric_qwk_lower95 > 0.40 후")
- [ ] **T3-08 [R2-F13]** M6 multi-output OOF의 overall_qwk 산출식 명시 (4 head average vs 추가 stacker)

### Hard Rule 정합

- [ ] **T3-09 [R2-F9]** Hard Rule #17 본문 — "갱신 default 60초, polling default 300초, stall threshold 600초" 분리 명시
- [ ] **T3-10 [R2-F12]** Hard Rule #18 cron enforce — `cycle_preflight` #8에 `crontab -l | grep backup_kanban_db` 검증 추가
- [ ] **T3-11 [R2-F14]** HPO trial 임계 일치 — "M2 단독 30 (hard-block), M3+ 누적 50 (hard-block 활성)" 명시
- [ ] **T3-12 [R2-F15]** AGENTS.md `When Auditing Data` 절에 `scripts/cycle_preflight.sh` 호출 의무 추가
- [ ] **T3-13 [R2-F16]** Cycle ID prefix 충돌 — Phase 3 `P3M2` prefix 또는 Phase 2 M1 archive rename 명시

### 운영 가이드 보강

- [ ] **T3-14 [R3-F15]** sandbox audit log — outbound 도메인 audit 수집 + 주 1회 review task 등록 절차
- [ ] **T3-15 [R3-F16]** `cycle_preflight` integrity_check `^ok$` 정확 매치 (전체 출력 기반)
- [ ] **T3-16 [R3-F17]** preflight #7 stale 검증 — frontmatter version 파싱 또는 git log freshness 체크. ASCII alias 파일 추가
- [ ] **T3-17 [R3-F18]** DB 수동 write 차단 — wrapper script 강제 + WAL 모드 명시 (`PRAGMA journal_mode=WAL`)
- [ ] **T3-18 [R3-F19]** 보관 정책 일치 — `cycle_*` 30일 회전 스크립트화 또는 가이드 "수동 cleanup" 수정
- [ ] **T3-19 [R3-F20]** HPO chunk 크기 명시 (예: 10 trial/task) + chunk별 progress.json
- [ ] **T3-20 [R3-F21]** `_read_gpu_util()` / `_read_gpu_mem()` 헬퍼 실제 구현 (nvidia-smi 파싱)
- [ ] **T3-21 [R3-F23]** `verify_hermes_patch.sh` 자동 재패치 옵션 (`--auto-repatch` + git diff 보고)

### Risk 추가

- [ ] **T3-22 [R4-F10]** vast.ai PII evidence — (a) AI Hub 익명화 spec 인용 (b) `paragraph_txt` 자전적 audit (c) location/date drop 셋 중 최소 1개. 미완 시 audit gate 재도입
- [ ] **T3-23 [R4-F11]** `VAST_API_KEY` argv 노출 → env 전달로 변경 (`vastai --api-key` 제거 + `VAST_API_KEY=...` env)
- [ ] **T3-24 [R4-F12]** `.env` perm 600 강제 + preflight 검증
- [ ] **T3-25 [R4-F14]** kanban DB 복구 절차 § 4.4 단계 3 — hermes daemon stop 명시 + WAL/SHM 처리

---

## Tier 4 — LOW / NIT (별도 issue, 본 fix 사이클 제외)

22건 — 본 문서 부록 또는 별도 issue tracker로 처리. 본 fix 사이클에서는 건너뜀.

`R1-F12~F17 / R2 누락 NIT / R3-F24~F31 / R4-F16~F20` — 후속 cycle 진입 시 정리.

---

## 실행 순서

1. **Tier 1 (CRITICAL 11건)** — 즉시 차단 항목, 모두 fix
2. **Tier 2 (HIGH 19건)** — 운영 안정성 영향, 모두 fix
3. **Tier 3 (MEDIUM 25건)** — 정합성/enforce, 모두 fix
4. **Tier 4** — 별도 issue로 deferral
5. **재검수** — 리뷰 에이전트 4명 재 dispatch (동일 lens)
6. **재검수 통과 시 사용자 게이트** — 산출물 검수 + 커밋

## 진행 시 commit 단위

- Tier 1 fix 완료 → 단일 commit (`fix(phase-3): Tier 1 CRITICAL — 운영 자동화 / 보안 / 스펙`)
- Tier 2 fix 완료 → 단일 commit (`fix(phase-3): Tier 2 HIGH — polling 패턴 / PASS_CANDIDATE stuck / 알림 채널`)
- Tier 3 fix 완료 → 단일 commit (`fix(phase-3): Tier 3 MEDIUM — KPI 측정 / 스펙 정합 / 운영 가이드 보강`)
- 재검수 → 추가 fix 발생 시 별도 commit
- 모두 검수 통과 후 → 사용자 게이트 → 최종 push
