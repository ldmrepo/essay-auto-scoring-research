# Self-Improving Research Architecture

> 갱신일: 2026-05-28
> 범위: Hermes Kanban 기반 Phase 2+ long-running research cycle

## 1. Operating Model

목표는 인간이 cycle 단위 결정만 하고, Hermes가 그 사이의 audit, split, feature, model, HPO, eval, review, synth를 자율 진행하는 것입니다.

```text
Human goal / DECIDE
        |
        v
AUDIT -> SPLIT -> FEATURE -> MODEL -> HPO -> (EVAL || REVIEW) -> SYNTH
        ^                                                           |
        |                                                           v
        +---------------------- DECIDE-MN <------------------ cycle report
```

## 2. Layer Model

| Layer | Name | Allowed | Human gate |
|---|---|---|---|
| 1 | Auto-decompose | approved goal을 task graph로 분해, profile routing, dependency link | hard rules/phase/privacy 변경 불가 |
| 2 | Event/dispatcher | ready task spawn, stale claim recovery, scheduled continuation | 새 외부 integration은 승인 필요 |
| 3 | Mutable policy proposal | retry/routing/report cadence 같은 운영 정책 제안 | reviewer + human approval 필요 |
| 4 | Phase transition | evidence package 준비 | 자동 phase-up 금지 |

## 3. Boundaries

Autonomous allowed:

- task 생성과 의존성 연결
- current phase 안의 반복 cycle 등록
- transient failure retry
- blocked task에 reason, command, artifact 기록
- report, manifest, MLflow/Optuna evidence 작성
- acceptance 미달 시 개선 cycle 등록

Human approval required:

- `AGENTS.md` hard rule 변경
- `MILESTONE_v2.md` acceptance goal 변경
- phase-up
- full Validation set 학습 fold 포함
- production model registration / champion alias
- 외부 배포
- privacy/data policy 변경

## 4. DECIDE Pattern

DECIDE options:

| Option | Meaning |
|---|---|
| `[Continue]` | current phase에서 다음 cycle 진행 |
| `[Phase-up]` | 더 큰 phase로 전환하기 위한 human-gated planning |
| `[Stop]` | 현재 phase 종료 |

다른 option label은 새 task body에 쓰지 않습니다.

## 5. Phase 2 Hard Gates

Phase 2에서 SYNTH는 다음을 acceptance 비교에 포함해야 합니다.

| Gate | 기준 |
|---|---|
| leakage | group/test leakage 0 |
| feature provenance | label-side feature 0 |
| MLflow | `cycle_id`, `kanban_task_id`, `feature_provenance` tag |
| HPO | Optuna 30 trial+ |
| monotone evolution | M1 ≤ M2 ≤ M3 ≤ M4 ≤ M5 ≤ M6, CI 기반 |
| human ceiling | metric 단위 일치 + bootstrap CI |
| score-band fairness | macro-QWK, worst-band QWK, per-band metric |
| cost | cost circuit breaker 미초과 |

Hard Rule #13 external-compute PII gate는 제거됐지만, Hard Rule #2는 유지됩니다.

## 6. Full-Trace Propagation

SYNTH가 다음 cycle task를 만들 때 각 task body는 다음을 포함해야 합니다.

- parent task id
- parent workspace artifact path
- MLflow/Optuna DB path
- 이전 cycle report path
- 검증 명령
- 구체적인 inherited recommendation

자연어 권고만 남기고 실행 인자나 명령을 누락하면 다음 cycle에서 같은 실패를 반복할 수 있습니다.

## 7. Verification

```bash
hermes kanban list --sort created
hermes kanban context <task_id>
test -f MILESTONE_v2.md
test -f configs/board_config.yaml
```
