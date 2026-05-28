# Cycle Task Chain v1.1

> 갱신일: 2026-05-28
> 현재 board: `essay-auto-scoring-research-phase2`
> 현재 phase: Phase 2 Mid-scale

## 1. Purpose

이 문서는 Hermes Kanban cycle이 어떤 순서로 진행되고, 어떤 task가 다음 cycle을 등록하며, 인간 DECIDE가 어디서 개입하는지 정의합니다.

Phase 1 toy cycle 문서는 보존 evidence로 남기고, 운영 기준은 이 문서와 `AGENTS.md`, `MILESTONE_v2.md`를 따릅니다.

## 2. Phase 2 Cycle Shape

각 Cycle `MN`은 다음 chain을 따릅니다.

```text
AUDIT -> SPLIT -> FEATURE -> MODEL -> HPO -> (EVAL || REVIEW) -> SYNTH -> DECIDE-MN
```

| Step | Profile | 책임 |
|---|---|---|
| AUDIT | `tukey` | data integrity, goal anchor, leakage pre-check |
| SPLIT | `gauss` | group split, fold manifest, leakage recheck |
| FEATURE | `gauss` | TF-IDF/numeric/RoBERTa cache, feature provenance |
| MODEL | `gauss` | M1~M5 baseline train |
| HPO | `gauss` | M4/M5 Optuna 30 trial+, M6 ensemble |
| EVAL | `spearman` | overall/segment/score-band/ceiling/CI |
| REVIEW | `turing` | code, leakage, reproducibility, HPO, provenance review |
| SYNTH | `aristotle` | cycle report, judgement, next cycle registration |
| DECIDE | human | Continue / Phase-up / Stop |

## 3. Current Cycle M1

| Task | Status | Note |
|---|---|---|
| `T-CYCLE-M1-AUDIT: 데이터 검증` | done | 5K sample audit |
| `T-CYCLE-M1-SPLIT: 분할 정책` | done | location split failed, region k=3 recovery passed |
| `T-CYCLE-M1-FEATURE: 피처 + RoBERTa embedding cache` | done | feature provenance required |
| `T-CYCLE-M1-MODEL: M1~M5 baseline 학습` | running | CPU baselines + Vast M5 path |
| `T-CYCLE-M1-HPO: Optuna 30 trial+` | todo | M4/M5 30 trial+ |
| `T-CYCLE-M1-EVAL: 다축 평가 + bootstrap CI` | todo | Hard Rule #14 required |
| `T-CYCLE-M1-REVIEW: 코드/누수 리뷰` | todo | Hard Rule #13 no longer applies |
| `T-CYCLE-M1-SYNTH: 종합 + 다음 cycle 등록` | todo | Cycle M2 registration |
| `DECIDE-M1: 인간 결정` | todo | user gate |

## 4. DECIDE Semantics

DECIDE task options are exactly:

| Option | Meaning |
|---|---|
| `[Continue]` | Start the already-registered next cycle chain |
| `[Phase-up]` | Stop autonomous execution and create/prepare a human-gated phase transition |
| `[Stop]` | Stop this phase and archive pending next-cycle work if needed |

`[Pause-redesign]` is legacy wording from an earlier Phase 2 draft and should not be used in new task bodies.

Timeout policy comes from `configs/board_config.yaml`:

| Window | Behavior |
|---|---|
| 0~6h grace | default Continue only for current-phase cycle continuation |
| 6~24h | Pause |
| Phase-up decision | never automatic |

## 5. SYNTH Responsibilities

SYNTH must produce:

- `workspace/cycle_MN/final/cycle_MN_report.md`
- judgement enum
- acceptance comparison
- specific next-cycle recommendations
- skill candidates if verified
- Cycle `M(N+1)` tasks when judgement is not `PASS_FINAL`

Next-cycle registration must preserve:

- parent dependency: `T-CYCLE-M(N+1)-AUDIT` parent = `DECIDE-MN`
- full-trace input context: parent workspace paths and MLflow/Optuna paths
- `MILESTONE_v2.md` verbatim goal anchor in AUDIT body
- executable recommendations, not vague improvement notes

## 6. Required Inheritance To M2

Cycle M1 has already surfaced specific corrections. If Cycle M2 is registered, SYNTH must inject these into the relevant task bodies:

| Correction | Inject into |
|---|---|
| Avoid `vastai show user`; use `show instances --raw` or `search offers --raw` with `--api-key "$VAST_API_KEY"` | MODEL, HPO |
| Hard Rule #13 external-compute PII gate removed; Hard Rule #2 remains | MODEL, REVIEW |
| Hard Rule #14 exact score-band metrics and mandatory Korean report phrase | EVAL, SYNTH |
| M6 must use OOF stacking, not in-sample single fit | HPO, REVIEW |
| Region k=3 is Cycle M1 recovery only; permanent adoption needs human-gated policy update | SPLIT, SYNTH |

## 7. Verification

Useful commands:

```bash
hermes kanban boards list
hermes kanban stats
hermes kanban list --sort created
hermes kanban show <task_id>
hermes kanban runs <task_id>
hermes kanban context <task_id>
```

Source documents:

- `../AGENTS.md`
- `../MILESTONE_v2.md`
- `configs/board_config.yaml`
- `docs/phase_2_mid_scale_design_v_1_1.md`
