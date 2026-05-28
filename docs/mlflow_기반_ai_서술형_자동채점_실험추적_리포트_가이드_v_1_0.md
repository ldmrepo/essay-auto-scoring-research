# MLflow 기반 AI 서술형 자동채점 실험추적·리포트 가이드

문서 버전: v1.0
작성일: 2026-05-27
문서명: MLflow_기반_AI_서술형_자동채점_실험추적_리포트_가이드_v1_0.md
대상 프로젝트: AI 서술형 자동채점 모델 구축 연구
연계 구조: Hermes Kanban Multi-Agent Board, Codex Pro, Claude Code Max, DVC, Optuna, GitHub

---

## 1. 문서 목적

본 문서는 AI 서술형 자동채점 모델 구축 연구에서 MLflow를 사용하여 실험 결과를 추적하고, 모델 성능을 비교하며, 누적 리포트를 생성하기 위한 운영 가이드를 정의한다.

본 문서의 목적은 다음과 같다.

1. MLflow의 역할과 필요성 정의
2. AI 서술형 자동채점 연구에서 기록해야 할 항목 정의
3. 실험 Run 구조 정의
4. MLflow Tracking 구성 방식 정의
5. 모델 평가 지표 기록 방식 정의
6. 리포트 생성 방식 정의
7. Hermes Kanban 기반 연구팀과의 연계 방식 정의
8. 운영 시 주의사항 정의

---

## 2. MLflow 개요

MLflow는 머신러닝 및 AI 모델 개발 과정에서 실험, 파라미터, 성능 지표, 산출물, 모델 버전, 모델 등록 정보를 추적·관리하기 위한 오픈소스 플랫폼이다.

AI 서술형 자동채점 연구에서는 여러 모델과 피처, 데이터 분할, 하이퍼파라미터 조합을 반복적으로 실험하게 된다. 이때 MLflow는 다음 질문에 답하기 위한 실험 기록 저장소 역할을 한다.

```text
어떤 데이터 버전을 사용했는가?
어떤 split 버전을 사용했는가?
어떤 모델을 사용했는가?
어떤 피처를 사용했는가?
어떤 하이퍼파라미터를 사용했는가?
QWK, MAE, RMSE 등 성능은 얼마였는가?
어떤 모델이 현재 최고 성능인가?
실험 결과를 다시 재현할 수 있는가?
```

---

## 3. MLflow의 핵심 역할

MLflow는 본 프로젝트에서 다음 역할을 수행한다.

| 구분 | 역할 |
|---|---|
| Experiment Tracking | 실험 Run, 파라미터, 지표, 산출물 기록 |
| Model Evaluation | 모델 성능 지표와 평가 산출물 기록 |
| Artifact Store | 예측 결과, 리포트, 차트, 모델 파일 저장 |
| Model Registry | 후보 모델 버전, alias, lineage 관리 |
| Comparison UI | 실험 간 성능 비교 |
| Report Data Source | 누적 리포트 생성의 원천 데이터 제공 |

중요한 점은 MLflow가 리포트를 직접 완성하는 도구라기보다, 리포트 생성에 필요한 모든 실험 근거 데이터를 저장하는 중심 저장소라는 점이다.

```text
MLflow = 실험 결과 원천
Report Generator = MLflow 데이터를 읽어 HTML/PDF/Markdown 리포트 생성
```

---

## 4. Hermes Kanban과 MLflow의 역할 분리

Hermes Kanban과 MLflow는 목적이 다르다.

| 도구 | 책임 |
|---|---|
| Hermes Kanban | 누가 어떤 연구 작업을 수행하는가 |
| Hermes Profile | 역할별 에이전트 정체성 |
| Codex Pro | 코드 구현, 테스트 작성, 반복 수정 |
| Claude Code Max | 코드 리뷰, 설계 검토, 평가 신뢰성 검토 |
| MLflow | 실험 Run, Metric, Artifact, Model 기록 |
| DVC | 데이터셋, split, feature artifact 버전 관리 |
| Optuna | 하이퍼파라미터 탐색 trial 관리 |
| GitHub | 코드 변경, Issue, PR, Review 이력 관리 |
| Report Generator | MLflow 데이터를 기반으로 리포트 생성 |

정리하면 다음과 같다.

```text
Hermes Kanban = 작업 관리
MLflow = 실험 증거 관리
DVC = 데이터 버전 관리
Optuna = 하이퍼파라미터 탐색 관리
Report = 의사결정 문서
```

---

## 5. MLflow 기본 개념

### 5.1 Experiment

Experiment는 하나의 연구 주제 또는 프로젝트 단위 실험 묶음이다.

본 프로젝트에서는 다음과 같이 하나의 Experiment를 생성한다.

```text
essay-auto-scoring
```

필요 시 하위 실험을 분리할 수 있다.

```text
essay-auto-scoring-baseline
essay-auto-scoring-transformer
essay-auto-scoring-hpo
essay-auto-scoring-ensemble
```

### 5.2 Run

Run은 실험 1회 실행 단위이다.

예시는 다음과 같다.

```text
RUN-001: TF-IDF + Ridge baseline
RUN-002: TF-IDF + LightGBM
RUN-003: KLUE-RoBERTa regression
RUN-004: KLUE-RoBERTa + rubric features
RUN-005: Optuna HPO trial group
RUN-006: Ensemble model
```

각 Run은 다음 정보를 기록한다.

```text
params
metrics
tags
artifacts
model
start_time
end_time
status
```

### 5.3 Parameters

Parameters는 실험 설정값이다.

예시는 다음과 같다.

```text
model_type
learning_rate
batch_size
num_epochs
max_length
optimizer
scheduler
feature_version
split_version
seed
```

### 5.4 Metrics

Metrics는 성능 지표이다.

예시는 다음과 같다.

```text
qwk
mae
rmse
pearson
spearman
exact_agreement
adjacent_agreement
min_item_qwk
max_score_band_bias_abs
train_valid_qwk_gap
```

### 5.5 Tags

Tags는 검색·분류용 메타정보이다.

예시는 다음과 같다.

```text
dataset_version
split_version
rubric_version
feature_version
pipeline_version
code_commit
kanban_task_id
github_issue_id
pr_id
run_purpose
```

### 5.6 Artifacts

Artifacts는 실험 산출 파일이다.

예시는 다음과 같다.

```text
predictions.csv
metrics.json
item_metrics.csv
score_band_metrics.csv
high_error_samples.csv
error_analysis.md
confusion_matrix.png
metric_trends.png
cumulative_report.html
model.pkl
```

### 5.7 Model Registry

Model Registry는 학습된 모델을 버전별로 등록하고 관리하는 저장소이다.

예시는 다음과 같다.

```text
EssayScoringModel
  version 1: TF-IDF + Ridge
  version 2: KLUE-RoBERTa regression
  version 3: KLUE-RoBERTa + rubric features
  version 4: Ensemble model
  alias: champion
  alias: candidate
```

---

## 6. AI 서술형 자동채점에서 기록해야 할 핵심 항목

### 6.1 필수 Parameters

```text
model_type
model_name
feature_set
target_name
label_policy
sample_weight_policy
max_length
batch_size
learning_rate
num_epochs
optimizer
scheduler
random_seed
```

### 6.2 필수 Tags

```text
dataset_version
split_version
rubric_version
feature_version
pipeline_version
code_commit
kanban_board
kanban_task_id
assignee_profile
run_stage
```

### 6.3 필수 Metrics

```text
qwk
mae
rmse
pearson
spearman
exact_agreement
adjacent_agreement
min_item_qwk
mean_item_qwk
max_item_mae
max_score_band_bias_abs
train_qwk
valid_qwk
test_qwk
train_valid_qwk_gap
```

### 6.4 필수 Artifacts

```text
reports/predictions.csv
reports/metrics.json
reports/item_metrics.csv
reports/score_band_metrics.csv
reports/high_error_samples.csv
reports/error_analysis.md
reports/decision_summary.md
reports/cumulative_report.html
configs/used_config.yaml
```

---

## 7. 권장 프로젝트 구조

```text
essay-auto-scoring-research/
  ├── AGENTS.md
  ├── PROJECT_GOAL.md
  ├── ACCEPTANCE_CRITERIA.yaml
  ├── RESEARCH_STATUS.md
  ├── EXPERIMENT_LOG.md
  ├── DECISION_LOG.md
  ├── configs/
  │   ├── dataset/
  │   ├── split/
  │   ├── features/
  │   ├── models/
  │   ├── hpo/
  │   └── evaluation/
  ├── data/
  │   ├── raw.dvc
  │   ├── processed.dvc
  │   └── splits.dvc
  ├── src/
  │   ├── data/
  │   ├── features/
  │   ├── models/
  │   ├── evaluation/
  │   ├── error_analysis/
  │   ├── tracking/
  │   └── reporting/
  ├── pipelines/
  │   ├── train.py
  │   ├── evaluate.py
  │   ├── optimize.py
  │   ├── analyze_errors.py
  │   └── build_report.py
  ├── reports/
  │   ├── latest/
  │   ├── experiments/
  │   └── cumulative/
  ├── models/
  ├── mlruns/
  └── dvc.yaml
```

---

## 8. 설치 및 기본 실행

### 8.1 설치

```bash
pip install mlflow
```

프로젝트에 필요한 패키지를 함께 설치한다.

```bash
pip install pandas scikit-learn matplotlib jinja2 mlflow
```

### 8.2 로컬 MLflow UI 실행

```bash
mlflow ui
```

기본 접속 주소는 다음과 같다.

```text
http://localhost:5000
```

### 8.3 Tracking URI 설정

로컬 파일 기반으로 시작할 경우 별도 설정 없이 `./mlruns`가 생성된다.

명시적으로 설정하려면 다음과 같이 한다.

```python
import mlflow

mlflow.set_tracking_uri("file:./mlruns")
mlflow.set_experiment("essay-auto-scoring")
```

원격 Tracking Server를 사용할 경우 다음처럼 설정한다.

```python
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("essay-auto-scoring")
```

---

## 9. 기본 로깅 예시

```python
import mlflow

mlflow.set_experiment("essay-auto-scoring")

with mlflow.start_run(run_name="baseline_tfidf_ridge"):
    mlflow.log_param("model_type", "tfidf_ridge")
    mlflow.log_param("feature_version", "feature-v1")
    mlflow.log_param("split_version", "split-v1")
    mlflow.log_param("random_seed", 42)

    mlflow.log_metric("qwk", 0.681)
    mlflow.log_metric("mae", 0.42)
    mlflow.log_metric("rmse", 0.61)
    mlflow.log_metric("pearson", 0.73)
    mlflow.log_metric("spearman", 0.71)

    mlflow.set_tag("dataset_version", "dataset-v2026-05-27")
    mlflow.set_tag("code_commit", "abc1234")
    mlflow.set_tag("kanban_task_id", "T007")

    mlflow.log_artifact("reports/predictions.csv")
    mlflow.log_artifact("reports/metrics.json")
    mlflow.log_artifact("reports/item_metrics.csv")
```

---

## 10. 자동채점 평가 지표 기록 방식

### 10.1 전체 지표

전체 모델 성능은 MLflow metric으로 기록한다.

```python
mlflow.log_metric("qwk", qwk)
mlflow.log_metric("mae", mae)
mlflow.log_metric("rmse", rmse)
mlflow.log_metric("pearson", pearson)
mlflow.log_metric("spearman", spearman)
mlflow.log_metric("exact_agreement", exact_agreement)
mlflow.log_metric("adjacent_agreement", adjacent_agreement)
```

### 10.2 문항별 지표

문항별 지표는 CSV artifact로 기록한다.

```text
reports/item_metrics.csv
```

컬럼 예시는 다음과 같다.

```text
item_id,essay_type,grade_group,n_samples,qwk,mae,rmse,pearson,spearman,exact_agreement,adjacent_agreement
```

### 10.3 점수대별 지표

점수대별 지표는 CSV artifact로 기록한다.

```text
reports/score_band_metrics.csv
```

컬럼 예시는 다음과 같다.

```text
score_band,n_samples,mae,rmse,bias,exact_agreement,adjacent_agreement
```

### 10.4 고오차 샘플

고오차 샘플은 CSV artifact로 기록한다.

```text
reports/high_error_samples.csv
```

컬럼 예시는 다음과 같다.

```text
essay_id,item_id,true_score,pred_score,error_abs,essay_type,grade_group,error_reason_candidate
```

---

## 11. 모델 저장 및 등록

### 11.1 모델 artifact 저장

scikit-learn 모델 예시는 다음과 같다.

```python
import mlflow.sklearn

mlflow.sklearn.log_model(model, artifact_path="model")
```

PyTorch 모델 예시는 다음과 같다.

```python
import mlflow.pytorch

mlflow.pytorch.log_model(model, artifact_path="model")
```

### 11.2 모델 레지스트리 등록

후보 모델을 등록할 때는 다음 정보를 확인해야 한다.

```text
run_id
dataset_version
split_version
feature_version
model_version
metrics
artifacts
approval_status
```

등록 개념은 다음과 같다.

```python
model_uri = f"runs:/{run_id}/model"
mlflow.register_model(model_uri, "EssayScoringModel")
```

### 11.3 Alias 운영

권장 alias는 다음과 같다.

```text
candidate
champion
archived
```

운영 규칙은 다음과 같다.

```text
candidate = 현재 검토 중인 후보 모델
champion = 현재 최고 승인 모델
archived = 더 이상 사용하지 않는 모델
```

---

## 12. 리포트 생성 구조

MLflow 자체는 실험 비교 UI를 제공하지만, 제출용 또는 의사결정용 리포트는 별도 생성기가 만드는 것이 적합하다.

권장 흐름은 다음과 같다.

```text
학습 실행
  ↓
MLflow에 params / metrics / artifacts 기록
  ↓
report.py가 MLflow Tracking Server에서 run 목록 조회
  ↓
leaderboard, metric trend, item-wise report, error analysis 생성
  ↓
HTML/PDF/Markdown 리포트 저장
  ↓
생성된 리포트도 MLflow artifact로 저장
```

---

## 13. 리포트 생성기 설계

### 13.1 입력

```text
MLflow Experiment Name
Acceptance Criteria YAML
DVC dataset version
Latest error analysis files
Latest item metrics files
Latest score band metrics files
```

### 13.2 출력

```text
reports/latest/cumulative_report.html
reports/latest/leaderboard.csv
reports/latest/metric_trends.csv
reports/latest/item_metrics_summary.csv
reports/latest/high_error_samples.csv
reports/latest/decision_summary.md
```

### 13.3 리포트 목차

```text
1. 프로젝트 개요
2. 데이터셋 버전
3. 실험 누적 현황
4. 최고 성능 모델 Top 10
5. 목표 대비 현재 성능
6. 지표별 성능 추세
7. 문항별 성능 현황
8. 점수대별 오차 현황
9. 고오차 샘플 분석
10. 하이퍼파라미터 탐색 요약
11. 모델 변경 이력
12. 완료 판정
13. 미달 사유
14. 다음 실험 계획
```

---

## 14. 리포트 생성 코드 예시

```python
import mlflow
import pandas as pd
from pathlib import Path

EXPERIMENT_NAME = "essay-auto-scoring"
REPORT_DIR = Path("reports/latest")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

mlflow.set_tracking_uri("file:./mlruns")
experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)

if experiment is None:
    raise RuntimeError(f"Experiment not found: {EXPERIMENT_NAME}")

runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])

leaderboard = runs.sort_values("metrics.qwk", ascending=False)
leaderboard.to_csv(REPORT_DIR / "leaderboard.csv", index=False)

metric_cols = [
    "run_id",
    "tags.dataset_version",
    "tags.split_version",
    "params.model_type",
    "metrics.qwk",
    "metrics.mae",
    "metrics.rmse",
    "metrics.pearson",
    "metrics.spearman",
]

available_cols = [c for c in metric_cols if c in runs.columns]
summary = leaderboard[available_cols]
summary.to_csv(REPORT_DIR / "metric_trends.csv", index=False)

html = f"""
<html>
<head><title>Essay Auto Scoring Cumulative Report</title></head>
<body>
<h1>Essay Auto Scoring Cumulative Report</h1>
<h2>Best Runs</h2>
{summary.head(10).to_html(index=False)}
</body>
</html>
"""

(REPORT_DIR / "cumulative_report.html").write_text(html, encoding="utf-8")

with mlflow.start_run(run_name="build_cumulative_report"):
    mlflow.log_artifact(str(REPORT_DIR / "leaderboard.csv"))
    mlflow.log_artifact(str(REPORT_DIR / "metric_trends.csv"))
    mlflow.log_artifact(str(REPORT_DIR / "cumulative_report.html"))
```

---

## 15. 완료 판정과 MLflow 연계

`research-master`는 MLflow에서 최고 성능 Run을 조회한 뒤 `ACCEPTANCE_CRITERIA.yaml`과 비교한다.

예시 기준은 다음과 같다.

```yaml
primary_metrics:
  qwk:
    operator: ">="
    value: 0.75

secondary_metrics:
  adjacent_agreement:
    operator: ">="
    value: 0.90
  mae:
    operator: "<="
    value: 0.35
  rmse:
    operator: "<="
    value: 0.55

segment_metrics:
  min_item_qwk:
    operator: ">="
    value: 0.65
  max_score_band_bias_abs:
    operator: "<="
    value: 0.20
```

판정 결과는 다음 중 하나로 기록한다.

```text
PASS_FINAL
PASS_CANDIDATE
FAIL_RETRY_HPO
FAIL_REBUILD_FEATURES
FAIL_REVIEW_LABELS
FAIL_CHANGE_MODEL
FAIL_NEED_MORE_DATA
FAIL_STOP_NO_GAIN
```

판정 결과는 MLflow tag와 artifact에 모두 남긴다.

```python
mlflow.set_tag("judgement", "FAIL_RETRY_HPO")
mlflow.log_artifact("reports/latest/decision_summary.md")
```

---

## 16. Hermes Kanban Task와 MLflow Run 연결

각 실험 Run에는 Kanban Task ID를 반드시 기록한다.

```python
mlflow.set_tag("kanban_board", "essay-auto-scoring-research")
mlflow.set_tag("kanban_task_id", "T012")
mlflow.set_tag("assignee_profile", "hpo-agent")
```

이를 통해 다음 추적이 가능하다.

```text
Kanban Task → 어떤 MLflow Run을 만들었는가?
MLflow Run → 어떤 Task와 Profile이 실행했는가?
Report → 어떤 Task 결과가 성능 개선에 기여했는가?
```

---

## 17. Optuna와 MLflow 연계

Optuna HPO를 사용할 경우 각 trial을 MLflow에 기록한다.

권장 방식은 다음과 같다.

```text
Optuna Study = HPO 작업 묶음
Optuna Trial = 개별 하이퍼파라미터 실험
MLflow Run = trial별 성능 기록 또는 study 단위 기록
```

기록 항목은 다음과 같다.

```text
study_name
trial_number
trial_value
trial_state
learning_rate
batch_size
dropout
weight_decay
qwk
mae
rmse
```

---

## 18. DVC와 MLflow 연계

DVC는 데이터셋과 split artifact 버전을 관리하고, MLflow는 실험 결과를 기록한다.

MLflow에는 DVC 관련 정보를 tag로 남긴다.

```python
mlflow.set_tag("dataset_version", "dataset-v2026-05-27")
mlflow.set_tag("dvc_data_hash", "a81f2...")
mlflow.set_tag("split_version", "split-v3-stratified")
mlflow.set_tag("feature_version", "feature-v7")
```

이렇게 하면 실험 결과를 데이터 버전과 연결할 수 있다.

---

## 19. 원격 MLflow 서버 구성 방향

초기에는 로컬 `./mlruns`로 충분하다.

```text
Local Mode:
  Tracking Store = ./mlruns
  Artifact Store = ./mlruns
  적합 용도 = 개인 실험, 초기 검증
```

장기 운영에서는 원격 Tracking Server 구성이 적합하다.

```text
Production-like Mode:
  Backend Store = PostgreSQL
  Artifact Store = S3 / MinIO / NAS / Object Storage
  Tracking Server = mlflow server
  UI = http://mlflow-server:5000
```

예시 명령은 다음과 같다.

```bash
mlflow server \
  --backend-store-uri postgresql://mlflow:password@localhost:5432/mlflow \
  --default-artifact-root s3://mlflow-artifacts/experiments \
  --host 0.0.0.0 \
  --port 5000
```

내부망 또는 로컬 NAS를 사용할 경우 artifact root를 NAS 경로로 지정할 수 있다.

```bash
mlflow server \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root /mnt/nas/mlflow-artifacts \
  --host 0.0.0.0 \
  --port 5000
```

---

## 20. 보안 및 운영 주의사항

```text
1. 원본 개인정보 데이터는 artifact로 저장하지 않는다.
2. predictions.csv에 민감 텍스트가 포함될 경우 비식별화한다.
3. API key, .env, credential 파일을 artifact로 올리지 않는다.
4. test set 결과를 반복 튜닝에 사용하지 않는다.
5. 최종 모델 등록은 Human Approver 승인 후 수행한다.
6. MLflow UI 접근 권한을 제한한다.
7. 외부 공유 리포트에는 원문 에세이 대신 essay_id와 요약 정보만 포함한다.
```

---

## 21. Hermes 팀 역할별 MLflow 책임

| 역할 | MLflow 관련 책임 |
|---|---|
| Research Master | 최고 Run 확인, 완료 판정, 다음 실험 생성 |
| Modeler | 학습 Run 생성, params/metrics/model 기록 |
| HPO Agent | Optuna trial과 MLflow Run 연결 |
| Evaluator | 평가 metric과 artifact 기록 |
| Error Analyst | high_error_samples, error_analysis artifact 기록 |
| Reporter | MLflow run 조회 후 누적 리포트 생성 |
| Experiment Tracker | run 누락, tag 누락, artifact 누락 점검 |
| Reproducibility Manager | dataset/split/feature/code commit 연결 확인 |
| Claude Code Max | logging 구조, metric 구현, leakage risk 리뷰 |
| Codex Pro | train/evaluate/report 코드 구현 |

---

## 22. 첫 번째 구축 Task 세트

Hermes Kanban에는 다음 Task를 생성한다.

```text
T-MLF-001. MLflow 로컬 설치 및 UI 실행
T-MLF-002. essay-auto-scoring experiment 생성
T-MLF-003. 기본 log_param/log_metric/log_artifact 유틸 구현
T-MLF-004. 평가 지표 기록 함수 구현
T-MLF-005. predictions/item_metrics/score_band_metrics artifact 저장 구현
T-MLF-006. train.py에 MLflow logging 연동
T-MLF-007. evaluate.py에 MLflow logging 연동
T-MLF-008. report.py에서 MLflow run 조회 구현
T-MLF-009. cumulative_report.html 생성 구현
T-MLF-010. 최고 Run 기준 완료 판정 로직 구현
T-MLF-011. Claude Code Max로 MLflow logging 구조 리뷰
T-MLF-012. 원격 Tracking Server 구성 검토
```

---

## 23. 완료 기준

MLflow 적용 완료 기준은 다음과 같다.

```text
1. mlflow ui 실행 가능
2. essay-auto-scoring experiment 생성 완료
3. train.py 실행 시 Run 자동 생성
4. params 기록 완료
5. metrics 기록 완료
6. tags 기록 완료
7. artifacts 기록 완료
8. predictions.csv 저장 완료
9. item_metrics.csv 저장 완료
10. cumulative_report.html 생성 완료
11. 최고 Run 조회 가능
12. ACCEPTANCE_CRITERIA.yaml 기준 PASS/FAIL 판정 가능
13. Kanban Task ID와 MLflow Run 연결 완료
14. Claude Code Max 리뷰 완료
```

---

## 24. 최종 권장안

AI 서술형 자동채점 연구에서 MLflow는 다음 위치에 둔다.

```text
Hermes Kanban:
  연구 작업 관리

Codex Pro:
  MLflow logging 코드 구현

Claude Code Max:
  MLflow logging 구조와 평가 신뢰성 리뷰

MLflow:
  실험 결과, 모델, metric, artifact 기록

DVC:
  데이터 버전 관리

Optuna:
  하이퍼파라미터 탐색 관리

Reporter:
  MLflow 데이터를 읽어 누적 리포트 생성
```

---

## 25. 결론

MLflow는 AI 서술형 자동채점 연구에서 실험 추적과 모델 성능 관리의 중심 도구이다.

본 프로젝트에서 MLflow는 다음 역할을 담당한다.

```text
1. 실험 Run 기록
2. 모델 설정값 기록
3. 성능 지표 기록
4. 산출물 저장
5. 모델 버전 관리
6. 최고 모델 비교
7. 누적 리포트 생성의 데이터 원천 제공
8. Hermes Kanban Task와 실험 결과 연결
```

따라서 MLflow는 리포트를 직접 완성하는 도구라기보다, 모든 실험 근거를 저장하고, 별도 리포트 생성기가 이를 읽어 HTML/PDF/Markdown 리포트를 만드는 구조로 사용하는 것이 적합하다.

핵심 원칙은 다음과 같다.

```text
MLflow는 실험 결과의 진실 원천이다.
리포트는 MLflow 데이터를 기반으로 생성한다.
Hermes Kanban은 MLflow Run을 만드는 작업 흐름을 관리한다.
완료 판정은 MLflow metric과 ACCEPTANCE_CRITERIA.yaml을 비교하여 수행한다.
```

