# Milestone Goal

Hermes Multi-Agent Kanban Board로 한국어 K-12 에세이 자동채점 워크플로우의
**24시간 자가발전 long-running cycle** 가능성을 toy 데이터(342건) + 라이트 모델로 검증한다.

본 milestone의 1차 목표는 모델 성능이 아니라 **자가발전 워크플로우의 동작 입증**이다.
매 Cycle N의 첫 sub-task(AUDIT)는 이 문서를 verbatim으로 컨텍스트에 재주입한다 (Hard Rule #10).

---

## Success Criteria

1. **3+ cycle 무인 반복** — DECIDE-N 결정 1회/cycle 외에는 인간 개입 없이 audit → split → feature → model → eval → review → synth 전 chain 자율 진행.
2. **Cron trigger 검증** — 9-Point validation의 1차 사이클 미검증 항목 해소 → 9/9 완성.
3. **Leakage-free 파이프라인** — Hard Rule #9 (Feature provenance) 자동 검증 + T7 리뷰가 label-side feature 0건 확인.
4. **Bootstrap CI 기반 ceiling 비교** — 점추정 단독 strict gate 회피, metric 단위 일치 (ICC(2,k) 또는 QWK(rater, k-avg) 평균).
5. **Skill library 형성 시작 (Cycle 3+)** — Voyager-style verified skill 누적, 다음 cycle의 split/feature 단계에서 reuse.
6. **Cost circuit breaker 동작 확인** — 임계 도달 시 cycle 자동 pause + 인간 알림 task 생성.

---

## Out of Scope (이번 milestone 한정)

- 풀데이터(50K) 학습
- Transformer 모델 (KLUE-RoBERTa 등)
- 정밀 bias/공정성 평가
- Model Registry champion 등록
- 외부 배포
- Hard Rule 본문 자율 수정 (AGENTS_LOCKED 영역)

---

## Non-negotiables

- 학생 PII는 어떤 경우에도 외부 LLM 전송 금지 (Hard Rule #2)
- AGENTS.md Hard Rules는 인간 게이트 통과해야만 변경 (AGENTS_LOCKED)
- DECIDE-N의 Phase-up 옵션은 타임아웃 무시, 항상 Pause (board_config.yaml `phase_transition: Pause`)
- 3 cycle 연속 acceptance fail 시 자동 종료 + Layer 3 escalation

---

## Reference

- 1차 사이클 검증 결과: `docs/archive/phase1/hermes_validation_v_1_0.md`, `docs/archive/phase1/final_report_v_1_0.md`
- Architecture: `docs/archive/background/self_improving_architecture_v_1_0.md`
- Escalation: `docs/archive/background/escalation_matrix_v_1_0.md`
- 외부 리서치: `docs/research/self_improving_long_running_research_v_1_0.md`
- 도메인 규칙: `AGENTS.md`
- 운영 설정: `configs/board_config.yaml`
