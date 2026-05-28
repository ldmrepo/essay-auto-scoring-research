# Hermes Workflow Validation

Task: `t_f8330a6d`
Date: 2026-05-27

## Conclusion

Hermes validation: **PASS**

The board completed a full long-running autonomous research cycle for the toy Korean essay-scoring workflow. The strongest validation signal is that the system did not merely produce model metrics: it blocked on missing schema evidence, resumed after policy clarification, blocked on missing MLflow, resumed after dependency availability, converted toy-only gates from hard block to warn-only, and finally let T7 block acceptance on a real feature-leakage issue.

## Nine-Point Validation

| Validation item | Result | Evidence |
| --- | --- | --- |
| Task automatic promotion | PASS | Parent completion promoted children: T1 completion promoted T2/T3; T4 completion promoted T5; T5 completion promoted T6/T7; T6/T7 completion promoted T8. See `task_events` promoted events `20`, `21`, `33`, `47`, `63`, `64`, `71`. |
| Decompose behavior | PASS | The initial research flow was decomposed into role-specific tasks T1-T8 plus child split implementation task T3a (`t_07d2d658`) created from T3 policy work. |
| Profile automatic routing | PASS | Work was routed to `tukey`, `spearman`, `aristotle`, `gauss`, and `turing` according to audit, reliability, policy, implementation, evaluation, and review roles. |
| Handoff metadata transfer | PASS | Completed runs recorded artifact paths, verification commands, run IDs, metrics, warnings, and blocking reasons in task run metadata. T6 and T7 consumed T5 artifacts; T8 consumed T6 and T7 outputs. |
| Workspace isolation | PASS with caveat | Outputs were kept under the project `workspace/` tree by task phase (`T1`, `splits`, `features`, `models`, `eval`, `review`, `final`) and board artifacts were stored separately under `.hermes/kanban/.../artifacts`. The board also emitted a scratch-workspace isolation hint for T2. This run primarily used a shared project directory, not per-task git worktrees. |
| Circuit breaker | PASS | T1 blocked on missing `student_school`; T5 blocked on missing MLflow; T5 blocked again on monotonic/ceiling policy before toy policy clarification; T7 produced a final BLOCK on feature leakage. |
| Human intervention points | PASS | Human/default comments unblocked T1 after approving `student.location` as proxy and unblocked T5 after toy warn-only policy was applied. |
| Memory accumulation | PASS | Knowledge accumulated through durable artifacts: T1 audit, T2 ceiling, T3 split manifest, T4 features, T5 MLflow/manifests, T6 eval, T7 review, and this T8 synthesis. |
| Cron trigger | NOT OBSERVED | No cron-triggered task was part of this toy workflow. The board dispatcher did exercise promotion and worker spawning, but cron scheduling was not directly tested by T1-T8 evidence. |

Overall judgement: **8/9 directly observed, 1/9 not exercised**. The main Hermes research workflow objective is satisfied; cron trigger validation should be covered by a separate scheduled maintenance or recurring evaluation task.

## Lifecycle Evidence

Important observed transitions:

- T1 first blocked because the hard-rule `student_school` field was absent; after human policy clarification, it completed using `student.location` as split proxy.
- T3 created and delegated T3a for concrete split implementation.
- T5 first blocked because MLflow was unavailable, then blocked again when monotonic and ceiling gates were initially treated as hard failures.
- After applying the toy policy, T5 completed with warnings recorded instead of silently ignored.
- T6 generated evaluation artifacts and surfaced model-vs-ceiling warnings.
- T7 rechecked leakage and correctly blocked acceptance because label-side annotation fields entered validation features.
- T8 synthesizes this into a blocked pipeline decision and a passed workflow validation.

## Board Evidence Commands

```bash
hermes kanban --board essay-auto-scoring-research show t_f8330a6d
hermes kanban --board essay-auto-scoring-research runs t_f8330a6d
sqlite3 /home/dev/.hermes/kanban/boards/essay-auto-scoring-research/kanban.db "select id,task_id,kind,payload,created_at from task_events order by created_at;"
sqlite3 /home/dev/.hermes/kanban/boards/essay-auto-scoring-research/kanban.db "select id,task_id,profile,status,summary,metadata from task_runs order by id;"
```

## Research Artifacts

- T1 audit: `workspace/T1/data_quality_report.md`, `workspace/T1/leakage_audit.md`, `workspace/T1/audit_manifest.json`
- T2 human ceiling: `/home/dev/.hermes/kanban/boards/essay-auto-scoring-research/artifacts/t_7ae417f9/ceiling_metric.json`
- T3 split policy and implementation: `workspace/split_policy_decision.md`, `workspace/split_manifest.yaml`, `workspace/split_leakage_check.md`, `workspace/splits/`
- T4 features: `workspace/features/feature_config.yaml`, `workspace/features/X_*.npz`
- T5 baselines and MLflow: `workspace/models/baseline_summary.json`, `workspace/models/M1/`, `workspace/models/M2/`, `workspace/models/M3/`, `workspace/models/M4/`, `mlruns/`
- T6 evaluation: `workspace/eval/eval_report.md`, `workspace/eval/segment_metrics.csv`, `workspace/eval/eval_manifest.json`
- T7 review: `workspace/review/review_report.md`, `workspace/review/leakage_reverification.md`
- T8 final synthesis: `workspace/final/final_report.md`, `workspace/final/hermes_validation.md`

## Follow-Up Recommendation

Create one small scheduled task to validate cron trigger behavior explicitly. Keep it separate from model acceptance so the next modeling cycle can focus on fixing the T7 leakage block.

