# Remote GPU Lifecycle Recovery Runbook v1.0

> Scope: Cycle M1+ Hermes Kanban tasks that use Vast.ai remote GPU for M5 KLUE-RoBERTa or HPO.
> Created: 2026-05-28
> Purpose: prevent a long-running remote GPU job from leaving Kanban in stale `running` state after the remote job already finished.

## 1. Problem

Remote GPU training can finish successfully while the local Hermes worker that launched or monitored it stops before post-processing.

Failure pattern:

1. Worker claims a Kanban task.
2. Worker creates a Vast.ai instance and starts remote training.
3. Remote training exits, but the worker session times out, crashes, or loses heartbeat.
4. Local artifacts are not collected.
5. `hermes kanban complete` is not called.
6. Child tasks remain blocked/todo behind a parent that appears `running`.
7. Vast.ai instance can remain idle and continue billing.

## 2. Stable Task Pattern

Remote GPU work must be treated as a recoverable lifecycle, not as one opaque long-running command.

Recommended graph:

```text
MODEL-CPU
  -> M5-LAUNCH
  -> M5-MONITOR
  -> M5-COLLECT
  -> MODEL-SUMMARY
  -> HPO
```

If the board currently has a single MODEL task, apply this runbook as a task comment and use it as the recovery protocol before completing the task.

## 3. Required Remote Markers

Every remote GPU training command must write these files under the task artifact directory.

For Cycle M1 M5:

```text
workspace/cycle_M1/models/M5_remote_train.log
workspace/cycle_M1/models/M5_remote_train.exitcode
workspace/cycle_M1/models/M5/manifest.json
workspace/cycle_M1/models/M5/predictions.csv
workspace/cycle_M1/models/M5/metrics_per_fold.json
workspace/cycle_M1/models/M5/segment_metrics.csv
workspace/cycle_M1/models/manifest.json
workspace/cycle_M1/models/model_training_summary.md
```

Exit code semantics:

- `0`: remote training completed; collect and verify locally.
- nonzero: block the Kanban task with the remote log tail and exit code.
- missing exitcode with live process: keep monitoring.
- missing exitcode without live process: block as `REMOTE_GPU_MARKER_MISSING` and preserve instance for manual inspection unless cost breaker requires cleanup.

## 4. Current Cycle M1 Recovery Inputs

Current observed remote instance:

```text
instance_id=38179859
ssh_host=ssh2.vast.ai
ssh_port=19858
remote_root=/workspace/essay
remote_model_dir=/workspace/essay/workspace/cycle_M1/models
```

Observed marker status:

```text
/workspace/essay/workspace/cycle_M1/models/M5_remote_train.exitcode = 0
/workspace/essay/workspace/cycle_M1/models/M5/manifest.json exists
/workspace/essay/workspace/cycle_M1/models/M5/predictions.csv exists
remote training process is no longer running
```

Therefore current `t_dcecd4b1` should not rerun M5. It should collect, verify, complete, then clean up the idle Vast.ai instance.

## 5. Collect Procedure

Load credentials without printing them:

```bash
set -a
. ./.env
set +a
```

Collect artifacts:

```bash
mkdir -p workspace/cycle_M1/models

rsync -avz -e "ssh -p 19858 -o StrictHostKeyChecking=accept-new" \
  root@ssh2.vast.ai:/workspace/essay/workspace/cycle_M1/models/M5 \
  workspace/cycle_M1/models/

rsync -avz -e "ssh -p 19858 -o StrictHostKeyChecking=accept-new" \
  root@ssh2.vast.ai:/workspace/essay/workspace/cycle_M1/models/manifest.json \
  root@ssh2.vast.ai:/workspace/essay/workspace/cycle_M1/models/model_training_summary.md \
  root@ssh2.vast.ai:/workspace/essay/workspace/cycle_M1/models/M5_remote_train.exitcode \
  root@ssh2.vast.ai:/workspace/essay/workspace/cycle_M1/models/M5_remote_train.log \
  workspace/cycle_M1/models/
```

Collect MLflow DB if needed:

```bash
rsync -avz -e "ssh -p 19858 -o StrictHostKeyChecking=accept-new" \
  root@ssh2.vast.ai:/workspace/essay/mlflow.db \
  mlflow_remote_M1.db
```

Do not overwrite local `mlflow.db` blindly. Merge or verify run ids explicitly before replacing any local tracking database.

## 6. Local Verification

Run after collect:

```bash
python3 - <<'PY'
import json
from pathlib import Path
import pandas as pd

base = Path("workspace/cycle_M1/models")
exitcode = (base / "M5_remote_train.exitcode").read_text().strip()
assert exitcode == "0", exitcode

m5_manifest = json.loads((base / "M5/manifest.json").read_text())
pred = pd.read_csv(base / "M5/predictions.csv")
assert len(pred) == m5_manifest["valid_prediction_count"] == 5003
assert len(m5_manifest["mlflow_run_ids"]) == m5_manifest["fold_count"] == 3
assert m5_manifest["kanban_task_id"] == "t_dcecd4b1"
assert m5_manifest["cycle_id"] == "M1"
assert m5_manifest["feature_provenance_hash"] == "2915e6071af230adb39bfb029412811ebf3d36bca02a57807c11b61ca6cb6034"
assert m5_manifest["split_manifest_sha256"] == "bb90ba5304fd63232dd6b72292aac9c3b4ce418b42b40dd530c13a2b78688124"

top_manifest = json.loads((base / "manifest.json").read_text())
assert "workspace/cycle_M1/models/M5/manifest.json" in top_manifest["model_manifests"]

print("M5 collect verification PASS")
print(json.dumps(m5_manifest["overall_valid_metrics"], ensure_ascii=False, indent=2))
PY
```

Expected current M5 point-estimate metrics:

```text
QWK  = 0.0005275951321298544
MAE  = 10.349331391537538
RMSE = 10.981805028045855
```

This is a MODEL completion result, not an acceptance result. Monotonicity, bootstrap CI, macro-QWK, worst-band QWK, and fairness gate judgement belong to EVAL/SYNTH.

## 7. Kanban Completion Criteria

Complete the MODEL task only after all conditions hold:

- remote exitcode is `0`
- local `workspace/cycle_M1/models/M5/manifest.json` exists
- local M5 predictions row count is `5003`
- M5 manifest has `fold_count=3`
- feature provenance hash matches the FEATURE artifact
- split manifest hash matches the SPLIT artifact
- completion comment records remote instance id, artifact paths, verification command, and M5 metrics
- Vast.ai instance is destroyed or an explicit keep-alive comment is recorded

## 8. Cleanup Procedure

After collect and verification:

```bash
vastai --api-key "$VAST_API_KEY" destroy instance 38179859
vastai --api-key "$VAST_API_KEY" show instances --raw
```

The expected post-cleanup result is no active instance for this task.

## 9. HPO Carry-Forward Rule

For `t_13e1eaaa` and later remote HPO tasks:

- do not run 30 trials as a single unrecoverable worker action
- write per-trial or per-study markers
- record `instance_id`, `ssh_host`, `ssh_port`, `remote_root`, and `hourly_cost` in the task comment before starting remote compute
- if heartbeat is stale, a new worker must inspect remote markers before rerunning anything
- if remote markers indicate success, collect and verify instead of rerunning
- if the instance is idle and no active process exists, clean it up after artifacts are preserved

