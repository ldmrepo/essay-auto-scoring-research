# Hermes Kanban Multi-Agent Board 기반 AI 서술형 자동채점 연구팀 오버뷰

문서 버전: v1.0
작성일: 2026-05-27
문서명: Hermes_Kanban_기반_AI_서술형_자동채점_연구팀_오버뷰_v1_0.md
대상 프로젝트: AI 서술형 자동채점 모델 구축 연구
운영 방식: Hermes Kanban Multi-Agent Board 기반 장기 실행형 연구 워크플로우

---

## 1. 문서 목적

본 문서는 AI 서술형 자동채점 시스템의 모델 구축 연구를 Hermes Kanban Multi-Agent Board 기반으로 장기간 자율 실행하기 위한 전체 운영 방안을 정리한다.

본 방안은 단순한 모델 학습 자동화가 아니라, 주어진 데이터셋과 목표 성능 기준을 바탕으로 다음 활동을 지속적으로 수행하는 연구팀 운영 체계를 목표로 한다.

1. 데이터셋 분석
2. 라벨 품질 및 채점자 불일치 분석
3. 모델 학습 파이프라인 구성
4. 실험 실행
5. 성능 측정
6. 오류 분석
7. 완료 여부 판정
8. 목표 미달 시 피처, 모델, 하이퍼파라미터, 파이프라인 재구성
9. 실험 결과 누적 추적
10. 성능 리포트 자동 생성

---

## 2. 핵심 개념

본 구조의 핵심은 다음과 같다.

```text
프로젝트 단위 = Hermes Kanban Board
역할 단위 = Hermes Profile
작업 단위 = Kanban Task
실험 단위 = MLflow Run / DVC Dataset Version / Git Commit
완료 판정 단위 = Acceptance Criteria
```

Hermes Kanban은 연구 작업의 흐름을 관리하고, MLflow/DVC/Optuna/Git은 실험의 증거와 재현성을 관리한다. 연구 총괄 에이전트는 목표 달성 여부를 판정하고, 목표 미달 시 다음 실험 작업을 다시 생성한다.

---

## 3. 전체 운영 구조

```text
사용자 / 팀장
   ↓
research-master profile
   ↓
Hermes Kanban Board
   ↓
data-auditor / feature-engineer / modeler / hpo-agent / evaluator / error-analyst / reporter
   ↓
실험 파이프라인 실행
   ↓
MLflow / DVC / Optuna / Report DB
   ↓
성능 판정
   ├─ 목표 달성 → 후보 모델 등록 + 최종 리포트
   └─ 목표 미달 → 다음 실험 Task 자동 생성
```

본 구조에서 Hermes Kanban Board는 연구팀의 작업 보드 역할을 수행한다. 각 Hermes Profile은 연구팀 구성원 역할을 수행하며, 각 Task는 데이터 분석, 학습, 평가, 오류 분석, 리포트 작성과 같은 구체적인 연구 작업 단위가 된다.

---

## 4. Kanban Board 구성

프로젝트는 하나의 Kanban Board로 시작한다.

```bash
hermes kanban boards create essay-auto-scoring-research
```

권장 보드명은 다음과 같다.

```text
essay-auto-scoring-research
```

이 보드는 다음 항목을 관리한다.

| 관리 항목 | 설명 |
|---|---|
| 연구 목표 | QWK, MAE, RMSE, 문항별 성능 기준 |
| 데이터 분석 | 데이터셋 품질, 라벨 분포, 채점자 불일치 |
| 실험 작업 | 모델 학습, 피처 변경, HPO 실행 |
| 평가 작업 | 전체/문항별/점수대별 성능 측정 |
| 오류 분석 | 고오차 샘플, 실패 유형, 개선 방향 |
| 완료 판정 | 목표 달성 여부, 재실험 여부 |
| 리포트 | 누적 성능 리포트, 실험 비교표 |

---

## 5. Hermes Profile 구성

초기 권장 프로파일은 다음 8개이다.

```bash
hermes profile create research-master \
  --description "Orchestrates long-running essay auto-scoring research, manages Kanban tasks, decides pass/fail, and creates next experiments."

hermes profile create data-auditor \
  --description "Analyzes dataset quality, label distribution, rater disagreement, missing values, duplicates, and data risks."

hermes profile create feature-engineer \
  --description "Designs and revises text, rubric, embedding, item, and label-confidence features for essay scoring."

hermes profile create modeler \
  --description "Builds baseline and advanced essay scoring models, runs training pipelines, and logs experiment results."

hermes profile create hpo-agent \
  --description "Runs hyperparameter optimization, analyzes trials, and adjusts search spaces."

hermes profile create evaluator \
  --description "Computes QWK, MAE, RMSE, Pearson, Spearman, exact agreement, adjacent agreement, and item-wise metrics."

hermes profile create error-analyst \
  --description "Analyzes high-error samples, failure patterns, score-band bias, item-level weaknesses, and recommends next actions."

hermes profile create reporter \
  --description "Creates cumulative performance reports, experiment leaderboards, trend charts, and decision summaries."
```

초기 실험을 단순화할 경우 다음 5개 프로파일부터 시작할 수 있다.

```text
research-master
data-auditor
modeler
evaluator
error-analyst
```

---

## 6. 역할별 책임

| Profile | 핵심 책임 | 주요 산출물 |
|---|---|---|
| research-master | 전체 목표 관리, 작업 배정, 완료 판정 | RESEARCH_STATUS.md, Kanban Task, 판정 로그 |
| data-auditor | 데이터셋 및 라벨 품질 분석 | 데이터 품질 리포트, 라벨 분포표, 불일치 분석표 |
| feature-engineer | 피처 설계 및 재구성 | feature config, feature importance, 피처 변경 이력 |
| modeler | 모델 학습 파이프라인 실행 | MLflow run, 모델 artifact, 학습 로그 |
| hpo-agent | 하이퍼파라미터 탐색 | Optuna study, trial report, search space 변경 이력 |
| evaluator | 성능 측정 | metrics json/csv, 문항별 평가표, 점수대별 평가표 |
| error-analyst | 실패 원인 분석 | error analysis report, high error samples |
| reporter | 누적 리포트 생성 | HTML 리포트, leaderboard, metric trends |

---

## 7. Kanban Task 상태 흐름

기본 상태 흐름은 다음과 같다.

```text
triage
  ↓
todo
  ↓
ready
  ↓
running
  ↓
done
```

문제가 발생하면 다음 상태로 전환한다.

```text
running → blocked
blocked → ready
```

운영 규칙상 각 상태의 의미는 다음과 같다.

| 상태 | 의미 |
|---|---|
| triage | 아직 실행 여부를 결정하지 않은 후보 작업 |
| todo | 실행 예정 작업 |
| ready | 실행 가능한 작업 |
| running | 에이전트가 처리 중인 작업 |
| blocked | 데이터, 설정, 승인, 오류로 중단된 작업 |
| done | 작업 완료 |
| archived | 종료 또는 폐기된 작업 |

---

## 8. 연구 루프

Hermes Kanban 기반 장기 실행 연구 루프는 다음으로 고정한다.

```text
PLAN
  ↓
RUN
  ↓
EVALUATE
  ↓
ANALYZE
  ↓
DECIDE
  ├─ PASS → REGISTER_MODEL → REPORT
  └─ FAIL → CREATE_NEXT_TASKS → PLAN
```

단계별 담당 프로파일은 다음과 같다.

| 단계 | 담당 Profile | 설명 |
|---|---|---|
| PLAN | research-master, feature-engineer | 다음 실험 계획 생성 |
| RUN | modeler, hpo-agent | 학습 또는 HPO 실행 |
| EVALUATE | evaluator | 성능 측정 |
| ANALYZE | error-analyst | 실패 원인 분석 |
| DECIDE | research-master | 완료 또는 재실험 판정 |
| REPORT | reporter | 누적 리포트 작성 |

---

## 9. 첫 번째 Kanban Task 세트

초기 보드에는 다음 작업을 생성한다.

```text
T001. 프로젝트 목표 및 완료 기준 정의
T002. 데이터셋 구조 분석
T003. 문항별/점수별 라벨 분포 분석
T004. 채점자 불일치 및 라벨 신뢰도 분석
T005. 데이터 분할 정책 수립
T006. 평가 지표 패키지 구현
T007. 베이스라인 모델 1: 길이/통계 피처
T008. 베이스라인 모델 2: TF-IDF + 회귀 모델
T009. 베이스라인 모델 3: 임베딩 + 회귀 모델
T010. Transformer 기반 모델 실험
T011. 루브릭 기반 피처 추가 실험
T012. Optuna HPO 실험
T013. 전체/문항별/점수대별 평가
T014. 고오차 샘플 분석
T015. 목표 달성 판정
T016. 누적 성능 리포트 생성
T017. 미달 시 다음 실험 계획 생성
```

예시 명령은 다음과 같다.

```bash
hermes kanban --board essay-auto-scoring-research create \
  "T001. 프로젝트 목표 및 완료 기준 정의" \
  --assignee research-master

hermes kanban --board essay-auto-scoring-research create \
  "T002. 데이터셋 구조 분석" \
  --assignee data-auditor

hermes kanban --board essay-auto-scoring-research create \
  "T006. 평가 지표 패키지 구현" \
  --assignee evaluator

hermes kanban --board essay-auto-scoring-research create \
  "T007. 베이스라인 모델 1: 길이/통계 피처" \
  --assignee modeler
```

실제 명령 옵션은 Hermes 설치 버전에 따라 달라질 수 있으므로 다음 명령으로 확인한다.

```bash
hermes kanban create --help
hermes kanban --help
```

---

## 10. 프로젝트 저장소 구조

Hermes Kanban은 작업 흐름을 관리하지만, 연구 이력과 재현성은 프로젝트 저장소에 함께 남겨야 한다.

권장 폴더 구조는 다음과 같다.

```text
essay-auto-scoring-research/
  ├── AGENTS.md
  ├── PROJECT_GOAL.md
  ├── ACCEPTANCE_CRITERIA.yaml
  ├── RESEARCH_PLAN.md
  ├── RESEARCH_STATUS.md
  ├── DECISION_LOG.md
  ├── EXPERIMENT_LOG.md
  ├── ERROR_ANALYSIS_LOG.md
  ├── REPORT_INDEX.md
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
  │   └── reporting/
  ├── pipelines/
  │   ├── run_data_audit.py
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

## 11. AGENTS.md 역할

프로젝트 루트의 `AGENTS.md`는 모든 Hermes 프로파일이 공유하는 공통 규칙이다.

```md
# AGENTS.md

## Project
AI 서술형 자동채점 모델 구축 연구

## Goal
주어진 데이터셋을 기반으로 자동채점 모델의 성능 목표를 달성한다.

## Core Rules
- 모든 실험은 config 기반으로 실행한다.
- 모든 실험은 MLflow에 기록한다.
- 데이터셋, split, feature, model, code commit을 반드시 기록한다.
- test set은 최종 검증 외 반복 튜닝에 사용하지 않는다.
- 목표 미달 시 원인 분석 없이 다음 실험을 생성하지 않는다.
- 성능 개선이 없는 반복 실험을 무제한 수행하지 않는다.
- 완료 판정은 ACCEPTANCE_CRITERIA.yaml을 기준으로 한다.

## Required Metrics
- QWK
- MAE
- RMSE
- Pearson
- Spearman
- Exact Agreement
- Adjacent Agreement
- Item-wise Metrics
- Score-band Bias

## Required Artifacts
- metrics.json
- item_metrics.csv
- score_band_metrics.csv
- predictions.csv
- high_error_samples.csv
- error_analysis.md
- experiment_summary.md
```

---

## 12. 완료 기준 파일

`ACCEPTANCE_CRITERIA.yaml` 예시는 다음과 같다.

```yaml
project:
  name: essay-auto-scoring-research
  version: v1.0

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

reliability:
  max_train_valid_qwk_gap:
    operator: "<="
    value: 0.08

required_artifacts:
  - metrics.json
  - item_metrics.csv
  - score_band_metrics.csv
  - predictions.csv
  - high_error_samples.csv
  - error_analysis.md
  - cumulative_report.html

human_approval_required:
  - final_model_registration
  - test_set_change
  - label_policy_change
  - production_deployment
```

---

## 13. 성능 미달 시 재구성 정책

`research-master`는 evaluator와 error-analyst의 결과를 기준으로 다음 판정 중 하나를 선택한다.

| 판정 | 의미 | 다음 작업 |
|---|---|---|
| PASS_FINAL | 최종 기준 통과 | 모델 등록, 최종 리포트 |
| PASS_CANDIDATE | 후보 기준 통과 | 추가 검증 |
| FAIL_RETRY_HPO | 모델 구조는 유효하나 튜닝 필요 | HPO task 생성 |
| FAIL_REBUILD_FEATURES | 피처 부족 | feature-engineer task 생성 |
| FAIL_REVIEW_LABELS | 라벨 품질 문제 | data-auditor task 생성 |
| FAIL_CHANGE_MODEL | 모델 구조 한계 | modeler task 생성 |
| FAIL_NEED_MORE_DATA | 데이터 부족 | 데이터 확장 요청 |
| FAIL_STOP_NO_GAIN | 개선 정체 | 사람 판단 요청 |

---

## 14. 누적 리포트 구성

리포트는 매 실험 또는 주요 실험 묶음마다 갱신한다.

### 14.1 최소 리포트 항목

```text
1. 현재 최고 모델
2. 목표 대비 현재 성능
3. 전체 실험 수
4. 최근 10개 실험 결과
5. 지표별 성능 추세
6. 문항별 성능 현황
7. 점수대별 오차 현황
8. 고오차 샘플 요약
9. 하이퍼파라미터 탐색 결과
10. 실패 원인 분류
11. 다음 실험 계획
12. 완료 판정 이력
```

### 14.2 리포트 산출물

```text
reports/latest/cumulative_report.html
reports/latest/leaderboard.csv
reports/latest/metric_trends.csv
reports/latest/item_metrics_heatmap.png
reports/latest/high_error_samples.csv
reports/latest/decision_summary.md
```

---

## 15. Hermes Kanban과 실험 추적 도구의 역할 분리

| 도구 | 책임 |
|---|---|
| Hermes Kanban | 누가 어떤 연구 작업을 수행하는가 |
| Hermes Profile | 역할별 에이전트 정체성 |
| MLflow | 실험 run, metric, artifact 추적 |
| DVC | 데이터셋, split, feature artifact 버전 |
| Optuna | 하이퍼파라미터 trial 관리 |
| Git | 코드, config, 리포트 템플릿 버전 |
| Report DB | 누적 성능 조회 |
| HTML Dashboard | 사람용 리포트 |

정리하면 다음과 같다.

```text
Hermes Kanban은 연구 작업 관리
MLflow/DVC는 실험 증거 관리
Report는 의사결정 관리
```

---

## 16. 권장 실행 순서

### 16.1 1단계: 보드와 역할 구성

```text
1. Hermes board 생성
2. profile 생성
3. AGENTS.md 작성
4. PROJECT_GOAL.md 작성
5. ACCEPTANCE_CRITERIA.yaml 작성
```

### 16.2 2단계: 실험 인프라 구성

```text
1. MLflow tracking 구성
2. DVC 데이터 버전 구성
3. 평가 지표 코드 작성
4. 리포트 생성기 작성
5. 베이스라인 학습 파이프라인 작성
```

### 16.3 3단계: Kanban 기반 연구 루프 시작

```text
1. 데이터 진단 task 실행
2. 베이스라인 task 실행
3. 평가 task 실행
4. 오류 분석 task 실행
5. 완료 판정 task 실행
6. 미달 시 다음 실험 task 생성
```

---

## 17. 최종 권장 구성

최종 권장 구성은 다음과 같다.

```text
Board:
  essay-auto-scoring-research

Profiles:
  research-master
  data-auditor
  feature-engineer
  modeler
  hpo-agent
  evaluator
  error-analyst
  reporter

Core Files:
  AGENTS.md
  PROJECT_GOAL.md
  ACCEPTANCE_CRITERIA.yaml
  RESEARCH_STATUS.md
  EXPERIMENT_LOG.md
  DECISION_LOG.md

Tracking:
  MLflow
  DVC
  Optuna
  Git

Reports:
  cumulative_report.html
  leaderboard.csv
  metric_trends.csv
  item_metrics.csv
  high_error_samples.csv
```

---

## 18. 핵심 운영 원칙

```text
1. Hermes Kanban은 연구팀의 작업 흐름을 관리한다.
2. MLflow/DVC/Optuna는 실험의 증거를 관리한다.
3. research-master는 목표 달성 여부를 판정한다.
4. 목표 미달 시 다음 실험 task를 생성한다.
5. 사람은 최종 모델 등록과 기준 변경만 승인한다.
6. 모든 실험은 dataset_version, split_version, feature_version, model_version, code_commit을 남긴다.
7. 테스트 세트는 반복 튜닝에 사용하지 않는다.
8. 성능 미달 시 원인 분석 없이 재실험하지 않는다.
9. 리포트는 매 실험 또는 주요 실험 묶음마다 갱신한다.
10. 실험 결과는 추적 가능하고 재현 가능해야 한다.
```

---

## 19. 결론

AI 서술형 자동채점 모델 구축 연구를 Hermes Kanban Multi-Agent Board 기반으로 운영하면 다음 목표를 달성할 수 있다.

1. 자율 연구 진행
2. 장기 실행형 실험 반복
3. 역할별 에이전트 협업
4. 데이터셋 및 실험 버전 관리
5. 성능 목표 기반 완료 판정
6. 목표 미달 시 파이프라인, 피처, 모델, 하이퍼파라미터 재구성
7. 누적 성능 추적 리포트 제공
8. 최종 후보 모델의 근거 기반 선정

본 구조는 Hermes Kanban을 연구 작업 관리 계층으로 사용하고, MLflow/DVC/Optuna/Git을 실험 증거 관리 계층으로 결합하는 방식이다. 따라서 단순 자동 학습 시스템이 아니라, 목표 달성을 위해 스스로 실험을 계획하고, 실행하고, 평가하고, 개선하는 장기 실행형 연구 운영 체계로 확장할 수 있다.

