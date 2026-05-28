# Escalation Matrix

> 갱신일: 2026-05-28
> 범위: Phase 2 Hermes Kanban task failure, block, cost, policy boundary handling

## 1. Failure Levels

| Repeated failure | Action |
|---:|---|
| 1 | same assignee retry, failed command and artifact path 기록 |
| 2 | reassign or sub-decompose |
| 3 | blocked + human gate task |

Silent failure는 허용하지 않습니다. 모든 block은 reason, reproduction command, artifact path, next action을 남깁니다.

## 2. Block Metadata

Blocked task metadata/comment must include:

| Field | Meaning |
|---|---|
| `reason` | 짧은 차단 사유 |
| `failed_command` | 재현 명령 |
| `artifact_paths` | log/report/manifest path |
| `policy_reference` | 관련 Hard Rule 또는 문서 |
| `next_action` | unblock을 위한 최소 행동 |

## 3. Routing

| Failure type | Default response |
|---|---|
| dependency missing | block with install/check command |
| CLI/API incompatibility | document exact command and replacement command |
| split leakage or fold invalid | hard-block SPLIT and propose split redesign |
| label-side feature | hard-block FEATURE/MODEL acceptance |
| HPO trial < 30 | hard-block HPO/REVIEW |
| score-band fairness fail | hard-block EVAL acceptance |
| cost circuit breaker | pause + human notification task |
| repeated model underperformance | continue with concrete next-cycle recommendation or stop after repeated no-gain |

## 4. Resource Limits

`configs/board_config.yaml` is the source of truth.

| Setting | Current |
|---|---|
| max concurrent cycles | 1 |
| max tasks per cycle | 12 |
| max cycles | 30 |
| max consecutive failures | 3 |
| max USD per cycle | 20.0 |

## 5. Human Gate Required

The board must not autonomously do these:

- change hard rules
- change acceptance criteria
- phase-up to full dataset
- include Validation holdout in training folds
- register final model/champion alias
- deploy externally
- alter student privacy/data policy

## 6. DECIDE Timeout

| Case | Behavior |
|---|---|
| current-phase continuation within 6h grace | default Continue allowed |
| 6h~24h | Pause |
| phase-up | never automatic |

DECIDE labels are `[Continue]`, `[Phase-up]`, `[Stop]`.

## 7. Verification

```bash
hermes kanban diagnostics
hermes kanban stats
hermes kanban runs <task_id>
hermes kanban log <task_id>
```
