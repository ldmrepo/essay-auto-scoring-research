# T8 Final Report

Task: `t_f8330a6d`
Date: 2026-05-27
Assignee: `aristotle`

## Decision

Pipeline acceptance: **BLOCK**

Hermes workflow validation: **PASS**

The toy scoring pipeline reached a complete audit -> split -> feature -> baseline -> evaluation -> review cycle with durable artifacts and MLflow registration. It is not accepted as a leakage-free modeling pipeline because T7 found that feature generation reopens label JSON and uses label-side `paragraph` and `correction` annotations for validation features.

This is the correct final state for the toy phase: Hermes demonstrated the long-running autonomous research workflow, and the review stage stopped the model result from being treated as accepted.

## Acceptance Check

| Check | Result | Evidence |
| --- | --- | --- |
| Leakage 0건 | **BLOCK** | Split leakage re-verification passed, but feature boundary failed: `pipelines/build_features.py` uses label-side `paragraph_count` and `correction_count` in validation matrices. See `workspace/review/review_report.md` and `workspace/review/leakage_reverification.md`. |
| Reproducibility manifest | **PASS** | M1-M4 manifests contain `seed`, `config_hash`, `artifact_paths`, `package_versions`, and MLflow run IDs. See `workspace/eval/eval_manifest.json`. |
| MLflow registration | **PASS** | Registered run IDs: M1 `b14bca3d3728486fbbeacc339669da19`, M2 `35b81c5eb35143fc8212b2af5100017d`, M3 `dec9d7234ae44e4b8c9881df0fbfaf7d`, M4 `d2267041b8ce423cba9ab49ab2477118`. |
| Toy monotonic evolution | **PASS under toy policy** | Toy hard diagnostic checks M1 <= M3 and M1 <= M4; no toy violation. Full-phase strict order would warn on M2 > M3. |
| Human ceiling distance | **WARN under toy policy** | Human ceiling QWK `0.1786`; M2 QWK `0.1938` and M4 QWK `0.3078` exceed the point estimate. Toy policy is warn-only; full phase requires CI-based hard blocks. |
| Segment evaluation | **PASS** | `workspace/eval/segment_metrics.csv` contains 56 segment rows by form, genre, grade band, and score band. |

## Overall Model Metrics

| Model | QWK | MAE | RMSE | Ceiling distance |
| --- | ---: | ---: | ---: | ---: |
| M1 dummy | -0.0976 | 2.2399 | 2.8211 | -0.2762 |
| M2 length Ridge | 0.1938 | 1.9946 | 2.5629 | 0.0152 |
| M3 TF-IDF Ridge | 0.0270 | 2.1190 | 2.6991 | -0.1516 |
| M4 LightGBM | 0.3078 | 1.9434 | 2.5246 | 0.1292 |

Human ceiling source: `/home/dev/.hermes/kanban/boards/essay-auto-scoring-research/artifacts/t_7ae417f9/ceiling_metric.json`

## Blocking Finding

T7 classified the main issue as **WRONG**:

- `pipelines/build_features.py:248` loads label JSON by `essay_id`.
- `pipelines/build_features.py:296` applies `dense_features()` to both train and validation records.
- Label JSON fields `paragraph` and `correction` are annotation-side fields, while source JSON contains only `essay_id` and `essay_txt`.
- The split files themselves are clean, but feature construction bypasses the split contract by reopening label sidecars.

Required fix before acceptance:

1. Build model features from fold records and source text only.
2. Remove `correction_count`, or replace it with a text-only checker that does not use label JSON.
3. Compute paragraph count from raw source text only.
4. Rebuild features, rerun M1-M4, rerun T6 evaluation, and rerun T7 leakage review.

## Next Cycle

Recommended task order:

1. Patch `pipelines/build_features.py` to remove label-side feature reads.
2. Add a shared disallowed-key contract used by split, feature, train, and review checks.
3. Source human ceiling diagnostics from the T2 artifact instead of config-level point estimates.
4. Add explicit `valid_n < 30` warnings to split manifest and leakage report.
5. Redispatch T4 -> T5 -> T6 -> T7.

## Artifact Paths

- Final report: `workspace/final/final_report.md`
- Hermes validation report: `workspace/final/hermes_validation.md`
- Evaluation report: `workspace/eval/eval_report.md`
- Evaluation manifest: `workspace/eval/eval_manifest.json`
- Segment metrics: `workspace/eval/segment_metrics.csv`
- Review report: `workspace/review/review_report.md`
- Leakage re-verification: `workspace/review/leakage_reverification.md`
- Baseline summary: `workspace/models/baseline_summary.json`
- Split manifest: `workspace/split_manifest.yaml`
- Human ceiling artifact: `/home/dev/.hermes/kanban/boards/essay-auto-scoring-research/artifacts/t_7ae417f9/ceiling_metric.json`

## Verification

```bash
python3 -m py_compile pipelines/audit_data.py pipelines/make_splits.py pipelines/build_features.py pipelines/train.py pipelines/evaluate.py
python3 pipelines/evaluate.py --output-dir workspace/eval --ceiling-json /home/dev/.hermes/kanban/boards/essay-auto-scoring-research/artifacts/t_7ae417f9/ceiling_metric.json
```

