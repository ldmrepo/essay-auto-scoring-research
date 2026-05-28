# Project Instructions

This is the repository-level `AGENTS.md` for coding agents and Hermes Kanban
workers operating in `/home/dev/work/essay-auto-scoring-research`.

Keep this file as concise, current, and executable guidance. Put long rationale,
meeting notes, and historical detail in `docs/`, then link to it here. Codex has
a default project-instruction budget near 32 KiB, so this file should stay well
below that limit.

# Project Overview

Goal: validate a 24-hour self-improving Hermes Multi-Agent Kanban research
workflow while improving a real Korean K-12 essay auto-scoring model.

Current active phase: **Phase 3 Mid Multi-task**.

Domain: Korean K-12 essay scoring.

Current modeling target:
- Dataset: `dataset/sample_5k/`, 5,003 AI Hub Training essays.
- Model progression: M1 dummy, M2 length, M3 TF-IDF+Ridge, M4 LightGBM,
  M5 KLUE-RoBERTa multi-task, M6 multi-output OOF ensemble.
- Phase 3 target shape: `[exp, org, cont, overall_norm]`.
- Phase 3 acceptance: PASS_CANDIDATE only. PASS_FINAL is reserved for a later
  production/full-data phase.

Active Hermes board:
- Board slug: `essay-auto-scoring-research-phase3`
- Board DB: `~/.hermes/kanban/boards/essay-auto-scoring-research-phase3/kanban.db`
- Board state is the source of truth for current task status.

Phase history:
- Phase 1 Toy: ended on 2026-05-27, sample 342, M1-M4, PASS_CANDIDATE.
  Evidence: `docs/archive/phase1/final_report_v_1_0.md`,
  `docs/archive/phase1/hermes_validation_v_1_0.md`, `mlruns_legacy/`.
- Phase 2 Mid-scale: archived after M1. Evidence: `MILESTONE_v2.md`,
  `docs/archive/phase2/phase_2_mid_scale_design_v_1_1.md`,
  `workspace/cycle_M1/`.
- Phase 3 Mid Multi-task: active. Source documents:
  `MILESTONE_v3.md`, `docs/multi_task_채점모델_구현_스펙_v_1_1.md`,
  `docs/phase_3_operations_guide_v_1_0.md`,
  `ACCEPTANCE_CRITERIA.yaml`.

# Operating Principle

Use **bounded self-repair** before blocking recoverable workflow defects.

Recoverable examples:
- split policy failure with an approved fallback;
- missing task metadata;
- missing M5 multi-task implementation branch;
- missing Phase 3 evaluation branch;
- transient permission/network problems with an approved recovery command.

Hard-block remains mandatory for true safety or integrity violations:
- data leakage or label-side feature use as model input;
- student direct identifiers or PII in model inputs;
- cost circuit breaker breach;
- kanban DB corruption or failed backup/integrity recovery;
- foreground worker job expected to run longer than 10 minutes;
- scalar M5/M6 path used silently in Phase 3;
- bounded recovery attempted and failed with evidence.

Self-repair workflow:
1. Record failure evidence and the reproduction command.
2. Apply the approved fallback or implement the missing branch if scoped to the
   task.
3. Run focused verification.
4. Continue only if verification passes.
5. Block only after bounded recovery fails, with exact reason, artifacts, and
   next recovery recommendation.

# Hard Rules

1. **No leakage.** Test/validation fold labels are evaluator-only. Model inputs
   must not include labels, rubric weights, rater scores, corrections, paragraph
   counts, or split-only identifiers.

2. **No student direct identifiers in model inputs.** `student_grade` may be used.
   `student.location` is split/audit metadata only.

3. **Split policy.** Default attempt is `student.location + k=5` stratified group
   k-fold with `valid_n >= 300`. If any fold violates that gate in M2, the
   approved fallback is `region merge + k=3`. Fallback must preserve
   `group_overlap_count=0`, keep `student.location` out of model inputs, and
   leave both failed-default and accepted-fallback evidence.

4. **MLflow tracking.** Training/HPO runs must log seed, config hash, artifacts,
   and tags: `cycle_id`, `phase`, `kanban_task_id`, `feature_provenance`.

5. **Rubric weights are data-derived.** Phase 3 loss weights come from each essay
   JSON: `rubric.expression_weight.exp`, `rubric.organization_weight.org`,
   `rubric.content_weight.con`. Do not hardcode rubric weights into model logic.

6. **M5/M6 are multi-task only in Phase 3.** Scalar `essay_scoreT_avg` M5/HPO/M6
   is forbidden for acceptance. M1-M4 may remain scalar overall baselines.

7. **Current implementation gate.** `pipelines/train_transformer.py` may still
   expose scalar `num_labels=1`. Before full M5 training or HPO, implement or
   verify `num_labels=4`, labels `(N,4)`, `macro_weights (N,4)`, and weighted
   loss equivalent to:
   `((preds - labels) ** 2 * macro_weights).sum(dim=1).mean()`.

8. **Long-running work is off-worker.** Any task expected to exceed 10 minutes
   must include literal metadata `expected_duration_min > 10` and use an
   off-worker pattern. Do not run full M5/M6 training or 30-trial HPO in a
   foreground worker.

9. **Progress observability.** Long-running training/HPO must update
   `progress.json`, create DONE/FAIL markers, and use one-shot polling such as
   `scripts/poll_vast_progress.sh "$INSTANCE_ID" /workspace/progress.json --once`.

10. **Cost circuit breaker.** Use `configs/board_config.yaml`. On breach, pause
    the cycle and notify; do not downgrade to a warning.

11. **Kanban DB backup.** Cycle preflight must create/check a DB backup and
    verify SQLite integrity. Use `scripts/backup_kanban_db.sh` for manual backup.

12. **Goal anchor.** The first AUDIT task in each Phase 3 cycle must reinject the
    `MILESTONE_v3.md` goal text.

13. **HPO trial policy.** M2 requires 30+ trials in that cycle. M3+ requires 50+
    cumulative trials plus 5+ new trials in the cycle. Each trial is an MLflow
    nested run.

14. **Fairness gate.** Overall metric alone is insufficient. EVAL must report
    overall, per-segment, score-band, macro-QWK, worst-band QWK, and bootstrap
    CI. Acceptance hard-block:
    `worst_band_qwk < macro_qwk * 0.7`.

15. **Phase 3 per-rubric evaluation.** EVAL must execute the Phase 3 path that
    calls `fairness_gate_per_rubric()` or an equivalent integrated branch.
    Helper-only dead code or overall-only `fairness_gate()` is not sufficient.

16. **Human ceiling comparison.** Compare model `QWK(pred, 3-rater-avg)` against a
    matching ceiling unit such as `ICC(2,k)` or mean `QWK(rater_i, 3-rater-avg)`.
    Block only when `model_lower95 > ceiling_upper95`.

17. **All task completions need metadata.** `kanban_complete` metadata must include
    output paths and verification commands. Failures need reason, evidence, and a
    reproduction command.

18. **Human approval required.** Changing hard rules, acceptance thresholds,
    student PII policy, phase transition, model registration, champion alias, or
    external deployment requires explicit user approval.

# Data And Artifacts

Primary data:
- `dataset/sample_5k/`: active 5,003-row Phase 3 sample.
- `dataset/1.Training/라벨링데이터/`: read-only source training data.
- `dataset/2.Validation/라벨링데이터/`: Phase 3/4 holdout; do not train on it.
- `dataset/sample/`: Phase 1 toy archive.

Generated outputs:
- `workspace/cycle_MN/`: cycle-scoped artifacts.
- `workspace/cycle_M2/`: active Phase 3 M2/M2R workspace family.
- `mlflow.db`: primary local MLflow SQLite tracking DB.
- `optuna.db`: Optuna storage.
- `reports/`: generated reports.
- `skills/`: accepted reusable skills only.

Do not overwrite `workspace/cycle_M1/` Phase 2 archive outputs.

# Build And Verification Commands

Environment check:

```bash
python3 -c "import pandas, sklearn, lightgbm, mlflow, transformers, optuna"
```

Cycle preflight:

```bash
scripts/cycle_preflight.sh M2 --require-vast
```

Regenerate the 5K sample with Phase 3 rubric validation:

```bash
python3 -m pipelines.extract_5k dataset/1.Training \
  --out dataset/sample_5k --target-n 5000 --seed 42 --validate-rubric
```

Default split attempt:

```bash
python3 pipelines/make_splits.py \
  --input dataset/sample_5k/ \
  --k 5 \
  --output workspace/cycle_M2/splits_location_k5_failed \
  --cycle-id M2 \
  --kanban-task-id <task_id> \
  --min-valid-n 300 \
  --group-key student.location \
  --audit-table workspace/cycle_M2/audit/data_audit/audit_table_no_raw_text.csv
```

Approved fallback split after default valid_n failure:

```bash
python3 pipelines/make_splits.py \
  --input dataset/sample_5k/ \
  --k 3 \
  --output workspace/cycle_M2/splits \
  --cycle-id M2 \
  --kanban-task-id <task_id> \
  --min-valid-n 300 \
  --group-key region \
  --audit-table workspace/cycle_M2/audit/data_audit/audit_table_no_raw_text.csv
```

Build features:

```bash
python3 pipelines/build_features.py \
  --source-dir dataset/sample_5k \
  --split-dir workspace/cycle_M2/splits \
  --output-dir workspace/cycle_M2/features \
  --cycle-id M2 \
  --kanban-task-id <task_id> \
  --audit-table workspace/cycle_M2/audit/data_audit/audit_table_no_raw_text.csv
```

Train CPU baselines M1-M4:

```bash
python3 pipelines/train.py \
  --models M1,M2,M3,M4 \
  --split-dir workspace/cycle_M2/splits \
  --feature-dir workspace/cycle_M2/features \
  --label-dir dataset/sample_5k/라벨링데이터 \
  --output-dir workspace/cycle_M2/models \
  --cycle-id M2 \
  --kanban-task-id <task_id> \
  --mlflow-uri sqlite:///mlflow.db \
  --experiment-name phase3_m2
```

Do not use the legacy scalar M5 command for Phase 3 acceptance. M5/M6 work must
first pass the multi-task implementation gate in the MODEL task and then run via
the off-worker/polling pattern.

Evaluate only after valid model artifacts exist:

```bash
python3 pipelines/evaluate.py \
  --models-dir workspace/cycle_M2/models \
  --audit-table workspace/cycle_M2/audit/data_audit/audit_table_no_raw_text.csv \
  --split-dir workspace/cycle_M2/splits \
  --feature-provenance workspace/cycle_M2/features/feature_provenance_manifest.json \
  --output-dir workspace/cycle_M2/eval \
  --cycle-id M2 \
  --kanban-task-id <task_id>
```

Common verification:

```bash
python3 -m py_compile pipelines/*.py scripts/*.py
bash -n scripts/*.sh
python3 -c "import yaml; yaml.safe_load(open('ACCEPTANCE_CRITERIA.yaml'))"
```

# Hermes Kanban Rules

Hermes Kanban is the durable coordination layer. Use it for work that must
survive retries, move between roles, preserve comments/logs, or wait for human
input.

Worker standard:
- Workers should use the `kanban_*` toolset when available.
- Humans, scripts, and Codex recovery work may use `hermes kanban ...` CLI.
- Every worker run must end with exactly one lifecycle terminator:
  `kanban_complete(...)`, `kanban_block(...)`, or an explicit failure.
- For code-changing work needing independent review, block with
  `review-required: ...` and attach changed files/tests in a comment.

Task graph pattern:
- `POLICY` or `WIRE-UP` when needed.
- `AUDIT -> SPLIT -> FEATURE -> MODEL -> HPO -> (EVAL || REVIEW) -> SYNTH -> DECIDE`.
- EVAL and REVIEW share HPO as parent. SYNTH depends on both.
- Next-cycle AUDIT must depend on the previous DECIDE task.

Active Phase 3 profile routing:
- `tukey`: audit/data validation.
- `gauss`: split, feature, model, HPO, implementation.
- `spearman`: evaluation/statistics.
- `turing`: independent review.
- `aristotle`: synthesis/decision prep/next-cycle registration.

Use `dir:/home/dev/work/essay-auto-scoring-research` workspaces for tasks that
must operate in this repository. Preserve parent output paths in child task body
Input Context.

# Role Instructions

## AUDIT

- Run `scripts/cycle_preflight.sh <cycle_id>`.
- Reinject `MILESTONE_v3.md` goal anchor.
- Audit shape, dtypes, nulls, duplicates, target distribution, group leakage,
  target leakage, and direct identifier risk.
- Verify `ACCEPTANCE_CRITERIA.yaml` `stages.mid_multitask._implementation_status`.
- For recoverable permission/path issues, fix and rerun once before blocking.

## SPLIT

- Try default `student.location + k=5`.
- If default fails `valid_n >= 300`, preserve failure evidence and use approved
  `region merge + k=3` fallback.
- Verify group overlap 0 and no split-only identifiers in model inputs.
- Emit split manifest, row manifests, leakage report, config hash, and commands.

## FEATURE

- Build M1-M4 compatible TF-IDF/numeric features from model-visible text only.
- Implement/verify strict Phase 3 target builder:
  `target_exp`, `target_org`, `target_cont`, `target_overall_norm`,
  `w_exp`, `w_org`, `w_cont`, `w_overall`.
- Produce M5 transformer input contract: `text`, labels `(N,4)`,
  `macro_weights (N,4)`.
- `prompt_text` stays disabled unless explicitly approved with provenance.
- `label_side_feature_count` must be 0.

## MODEL

- M1-M4 may train locally if short.
- M5 full training must be off-worker.
- Before M5 launch, prove multi-task path and scalar-block tests/smoke.
- Required MLflow tags: `cycle_id=M2`, `phase=3`, `kanban_task_id`,
  `feature_provenance`.
- If implementation is missing, implement and test if scoped; otherwise create
  or block for focused recovery. Never train scalar M5 as fallback.

## HPO

- Use Optuna `TPESampler(seed=42)` and `MedianPruner(n_startup_trials=5)`.
- M2: 30+ trials. M3+: 50+ cumulative plus 5+ new.
- M5 HPO objective must consume multi-task labels `(N,4)` and macro weights.
- Long HPO runs require off-worker chunks plus one-shot polling.
- Enforce cost circuit breaker before remote launch.

## EVAL

- Use executable Phase 3 per-rubric evaluation, not helper-only code.
- Report overall, per-rubric, per-segment, score-band, macro-QWK, worst-band
  QWK, and bootstrap CI.
- Apply fairness gate, strict overall monotone ordering, human ceiling check,
  and required warning text:
  "본 데이터셋은 high score band에 90% 이상 집중되어 있으므로, overall metric은 실제 변별력을 과대평가할 수 있다. 따라서 모델 수용 여부는 overall metric뿐 아니라 macro-QWK, worst-band QWK, per-band metric을 함께 기준으로 판단한다."

## REVIEW

- Findings first, classified as WRONG / FRAGILE / STYLE.
- Include file/line references.
- Do not approve without tests/evidence.
- Confirm split fallback evidence, feature provenance, HPO trial count, MLflow
  tags, multi-task M5/M6, and executable per-rubric EVAL branch.
- Prefer focused recovery tasks for repairable defects. Block only when safety
  or bounded recovery evidence fails.

## SYNTH

- Build `cycle_report.json` and `cycle_report.md`.
- Map judgement to `ACCEPTANCE_CRITERIA.yaml`.
- PASS_FINAL is not allowed in Phase 3 Mid.
- Run or record `auto_continue_check` inputs.
- If continuation is appropriate, register next-cycle tasks with concrete
  executable recommendations. Vague recommendations must be rewritten or SYNTH
  must block.
- If MODEL/HPO/EVAL failed because implementation is missing, register focused
  recovery tasks rather than a normal continuation.

## DECIDE

- Human-visible gate.
- Accepted comments: `[Continue]`, `[Phase-up]`, `[Stop]`.
- Never phase-up automatically.
- Auto-continue is allowed only when SYNTH records exact satisfied conditions
  from `ACCEPTANCE_CRITERIA.yaml`.

# Forbidden

- Train on `dataset/2.Validation/라벨링데이터/` during Phase 3 Mid.
- Use `klue/roberta-large` in Phase 3 Mid.
- Put direct student identifiers into model inputs or external LLM prompts.
- Register a final production model or champion alias.
- Accept M5/M6 scalar results for Phase 3.
- Run full M5/M6 training or 30-trial HPO in a foreground worker.
- Change hard rules or acceptance thresholds without user approval.
- Proceed with HPO trial count below the active threshold.
- Use external cron/decompose scripts to replace the board-native cycle chain.

# References

- `MILESTONE_v3.md`: active Phase 3 milestone and goal anchor.
- `ACCEPTANCE_CRITERIA.yaml`: active gates and judgement mapping.
- `docs/multi_task_채점모델_구현_스펙_v_1_1.md`: Phase 3 model spec.
- `docs/phase_3_operations_guide_v_1_0.md`: operations and recovery guide.
- `configs/board_config.yaml`: cost, DECIDE, backup, notify settings.
- `VAST_GPU_GUIDE.md`: remote GPU workflow.
- `workspace/cycle_M1/`: Phase 2 archive, read-only evidence.
- `workspace/cycle_M2/`: active Phase 3 M2/M2R artifact family.
