# Hermes Kanban 기반 AI 서술형 자동채점 연구팀 풀셋 구성

문서 버전: v1.0
작성일: 2026-05-27
문서명: Hermes_Kanban_기반_AI_서술형_자동채점_연구팀_풀셋_구성_v1_0.md
대상 프로젝트: AI 서술형 자동채점 모델 구축 연구
운영 방식: Hermes Kanban Multi-Agent Board 기반 장기 실행형 연구팀
연계 도구: Hermes Agent, Claude Code Max, Codex Pro, GitHub, MLflow, DVC, Optuna

---

## 1. 문서 목적

본 문서는 AI 서술형 자동채점 모델 구축 연구를 Hermes Kanban Multi-Agent Board 기반으로 장기간 운영하기 위한 연구팀 풀셋 구성을 정의한다.

본 문서는 다음 내용을 포함한다.

1. 전체 팀원 구성
2. Hermes Profile 기반 역할 정의
3. Codex Pro 기반 구현 역할 정의
4. Claude Code Max 기반 검토 역할 정의
5. Human Approver 역할 정의
6. 단계별 투입 역할
7. 최소·표준·풀셋 구성 비교
8. 권장 확장 순서

---

## 2. 기본 운영 전제

본 연구팀 구성은 다음 전제를 따른다.

```text
프로젝트 단위 = Hermes Kanban Board
역할 단위 = Hermes Profile 또는 외부 코딩 에이전트
작업 단위 = Kanban Task
구현 단위 = Codex Pro 작업 / Git Branch / PR
검토 단위 = Claude Code Max Review / GitHub PR Review
실험 단위 = MLflow Run / DVC Dataset Version / Git Commit
완료 판정 단위 = Acceptance Criteria
최종 승인 단위 = Human Approver
```

핵심 역할 분리는 다음과 같다.

```text
Hermes Profile = 역할 담당
Codex Pro = 구현 담당
Claude Code Max = 검토 담당
Research Master = 판정과 재계획 담당
Human Approver = 기준 변경과 최종 승인 담당
```

---

## 3. 전체 팀원 풀셋 구성

| No | 팀원 / 역할 | 구성 방식 | 핵심 책임 |
|---:|---|---|---|
| 1 | Human Approver | 사용자 / 팀장 | 최종 승인, 기준 변경 승인, 모델 등록 승인, 배포 승인 |
| 2 | Research Master | Hermes Profile | 전체 목표 관리, Kanban Board 운영, Task 생성·배정, 완료/미달 판정 |
| 3 | Project Planner | Hermes Profile | 연구 계획 수립, Milestone/Task 분해, 의존성 정리 |
| 4 | Dataset Manager | Hermes Profile | 데이터셋 버전 관리, DVC 연계, 원천/가공/분할 데이터 관리 |
| 5 | Data Auditor | Hermes Profile | 결측, 중복, 이상치, 문항별 샘플 수, 점수 분포 분석 |
| 6 | Label Quality Analyst | Hermes Profile | 채점자 불일치, 라벨 신뢰도, 평균/중앙값/분산, sample weight 정책 분석 |
| 7 | Rubric Analyst | Hermes Profile | 루브릭 구조화, 평가 요소 정의, 점수 구간별 기준 정리 |
| 8 | Split Policy Manager | Hermes Profile | train/valid/test 분할 정책, 문항별·점수대별 stratification, leakage 방지 |
| 9 | Feature Engineer | Hermes Profile | 텍스트, 통계, 임베딩, 루브릭, 문항, 라벨 신뢰도 피처 설계 |
| 10 | Embedding Engineer | Hermes Profile + Codex Pro | 문항-답안, 기준답안-답안, 루브릭-답안 임베딩 피처 구성 |
| 11 | Baseline Modeler | Hermes Profile + Codex Pro | 길이/통계, TF-IDF, Ridge/SVR/LightGBM 등 기준선 모델 구축 |
| 12 | Transformer Modeler | Hermes Profile + Codex Pro | KLUE-RoBERTa/BERT 계열 회귀·분류 모델 실험 |
| 13 | LLM Judge Designer | Hermes Profile + Claude Code Max | 루브릭 기반 LLM 보조평가 설계, judge feature 정책 검토 |
| 14 | Ensemble Designer | Hermes Profile + Codex Pro | 전통 ML, Transformer, 임베딩, 루브릭 피처 기반 ensemble 구성 |
| 15 | HPO Agent | Hermes Profile + Codex Pro | Optuna 기반 하이퍼파라미터 탐색, search space 조정, pruning 분석 |
| 16 | Training Pipeline Engineer | Codex Pro | `train.py`, config 기반 학습 실행, checkpoint, seed, 재현성 구현 |
| 17 | Evaluation Engineer | Codex Pro | QWK, MAE, RMSE, Pearson, Spearman, Exact/Adjacent Agreement 구현 |
| 18 | Evaluator | Hermes Profile | 전체/문항별/점수대별 성능 측정, metric package 생성 |
| 19 | Error Analyst | Hermes Profile + Claude Code Max | 고오차 샘플, 실패 유형, 문항별 취약점, 점수대별 편향 분석 |
| 20 | Leakage & Validity Reviewer | Claude Code Max | 데이터 누수, split 오류, test set 오염, 평가 신뢰성 점검 |
| 21 | Code Reviewer | Claude Code Max | PR diff 리뷰, 코드 품질, edge case, 테스트 커버리지 검토 |
| 22 | Experiment Tracker | Hermes Profile | MLflow run, metric, artifact, model registry 기록 확인 |
| 23 | DVC / Reproducibility Manager | Hermes Profile + Codex Pro | DVC stage, dataset hash, split version, feature artifact 재현성 관리 |
| 24 | Report Builder | Codex Pro | HTML 리포트, leaderboard, metric trend, chart 생성 코드 작성 |
| 25 | Reporter | Hermes Profile | 누적 성능 리포트, 의사결정 요약, 다음 실험 계획 정리 |
| 26 | Decision Logger | Hermes Profile | `DECISION_LOG.md`, `EXPERIMENT_LOG.md`, `ERROR_ANALYSIS_LOG.md` 갱신 |
| 27 | Ops / Scheduler | Hermes Profile | Cron, Gateway, 일일 상태 점검, stale/blocked task 탐지 |
| 28 | Security & Privacy Reviewer | Claude Code Max | 개인정보, 민감 데이터, API key, 외부 도구 전달 범위 점검 |
| 29 | Release / Registry Manager | Hermes Profile | 최종 후보 모델 등록, 모델 버전, alias, release note 정리 |
| 30 | Implementation Worker | Codex Pro | 반복 구현, 테스트 작성, 실패 수정, 파이프라인 코드 작성 |

---

## 4. Hermes Profile 풀셋

Hermes Profile 기준으로 생성할 역할은 다음과 같다.

```bash
hermes profile create research-master \
  --description "Orchestrates long-running essay auto-scoring research, manages Kanban tasks, decides pass/fail, and creates next experiments."

hermes profile create project-planner \
  --description "Breaks research goals into milestones, tasks, dependencies, and acceptance criteria."

hermes profile create dataset-manager \
  --description "Manages dataset versions, DVC references, raw/processed/split data, and dataset lineage."

hermes profile create data-auditor \
  --description "Analyzes dataset quality, missing values, duplicates, outliers, item-wise sample counts, and score distributions."

hermes profile create label-quality-analyst \
  --description "Analyzes rater disagreement, label confidence, mean/median/variance, and sample weighting policy."

hermes profile create rubric-analyst \
  --description "Structures essay scoring rubrics, scoring dimensions, score bands, and item-level criteria."

hermes profile create split-policy-manager \
  --description "Designs train/valid/test split policies, stratification, and leakage prevention rules."

hermes profile create feature-engineer \
  --description "Designs text, rubric, embedding, item, and label-confidence features."

hermes profile create embedding-engineer \
  --description "Builds item-answer, reference-answer, rubric-answer embedding features and semantic similarity pipelines."

hermes profile create baseline-modeler \
  --description "Builds baseline models using length/statistical features, TF-IDF, Ridge, SVR, and LightGBM."

hermes profile create transformer-modeler \
  --description "Runs Transformer-based regression and classification experiments for essay scoring."

hermes profile create llm-judge-designer \
  --description "Designs rubric-aware LLM judge prompts, judge features, and validation policies."

hermes profile create ensemble-designer \
  --description "Designs ensemble models across baseline, Transformer, embedding, rubric, and judge features."

hermes profile create hpo-agent \
  --description "Runs Optuna hyperparameter optimization, analyzes trials, pruning, and search spaces."

hermes profile create evaluator \
  --description "Computes overall, item-wise, score-band metrics and prepares evaluation packages."

hermes profile create error-analyst \
  --description "Analyzes high-error samples, failure patterns, item weaknesses, and score-band bias."

hermes profile create experiment-tracker \
  --description "Verifies MLflow runs, metrics, artifacts, model registry entries, and experiment lineage."

hermes profile create reproducibility-manager \
  --description "Manages DVC stages, dataset hashes, split versions, feature artifacts, and reproducibility checks."

hermes profile create reporter \
  --description "Creates cumulative performance reports, leaderboards, metric trends, and decision summaries."

hermes profile create decision-logger \
  --description "Maintains decision logs, experiment logs, error analysis logs, and audit trails."

hermes profile create ops-scheduler \
  --description "Runs cron checks, gateway notifications, stale task detection, and blocked task monitoring."

hermes profile create release-registry-manager \
  --description "Manages final model candidate registration, version aliases, release notes, and approval packages."
```

---

## 5. 외부 코딩 도구 역할 풀셋

Hermes Profile과 별도로 Claude Code Max와 Codex Pro는 전문 실행·검토 도구로 배치한다.

| 도구 | 역할명 | 담당 작업 |
|---|---|---|
| Codex Pro | Implementation Worker | 코드 구현, 테스트 작성, 반복 수정 |
| Codex Pro | Training Pipeline Engineer | 학습 파이프라인, config 실행, checkpoint, seed 고정 |
| Codex Pro | Evaluation Engineer | 평가 지표 구현, metric 저장, 테스트 작성 |
| Codex Pro | Report Builder | HTML/CSV/차트 리포트 생성 코드 작성 |
| Codex Pro | DVC Pipeline Implementer | `dvc.yaml`, stage script, artifact path 구성 |
| Claude Code Max | Code Reviewer | PR diff 리뷰, edge case, 테스트 누락 점검 |
| Claude Code Max | Leakage & Validity Reviewer | 데이터 누수, split 오류, 평가 신뢰성 검토 |
| Claude Code Max | Architecture Reviewer | 파이프라인 구조, 모듈 경계, 유지보수성 검토 |
| Claude Code Max | Security & Privacy Reviewer | 민감 데이터, API key, 외부 전달 범위 검토 |
| Claude Code Max | LLM Judge Reviewer | 루브릭 기반 LLM judge 설계 검토 |

---

## 6. 운영상 핵심 팀 구조

```text
Human Approver
  ↓
Research Master
  ↓
Hermes Kanban Board: essay-auto-scoring-research
  ├─ Project Planner
  ├─ Dataset Manager
  ├─ Data Auditor
  ├─ Label Quality Analyst
  ├─ Rubric Analyst
  ├─ Split Policy Manager
  ├─ Feature Engineer
  ├─ Embedding Engineer
  ├─ Baseline Modeler
  ├─ Transformer Modeler
  ├─ LLM Judge Designer
  ├─ Ensemble Designer
  ├─ HPO Agent
  ├─ Evaluator
  ├─ Error Analyst
  ├─ Experiment Tracker
  ├─ Reproducibility Manager
  ├─ Reporter
  ├─ Decision Logger
  ├─ Ops / Scheduler
  └─ Release / Registry Manager

External Execution / Review
  ├─ Codex Pro: 구현·테스트·수정
  └─ Claude Code Max: 리뷰·설계검토·신뢰성검토
```

---

## 7. 단계별 투입 역할

| 단계 | 투입 역할 |
|---|---|
| 1. 목표 정의 | Human Approver, Research Master, Project Planner |
| 2. 데이터 진단 | Dataset Manager, Data Auditor, Label Quality Analyst |
| 3. 루브릭 분석 | Rubric Analyst, LLM Judge Designer |
| 4. 분할 정책 | Split Policy Manager, Leakage & Validity Reviewer |
| 5. 피처 설계 | Feature Engineer, Embedding Engineer |
| 6. 베이스라인 구축 | Baseline Modeler, Codex Pro, Evaluator |
| 7. 고급 모델 실험 | Transformer Modeler, Ensemble Designer, HPO Agent |
| 8. 실험 추적 | Experiment Tracker, Reproducibility Manager |
| 9. 성능 평가 | Evaluator, Evaluation Engineer |
| 10. 오류 분석 | Error Analyst, Claude Code Max |
| 11. 코드 리뷰 | Code Reviewer, Architecture Reviewer |
| 12. 리포트 생성 | Reporter, Report Builder, Decision Logger |
| 13. 완료 판정 | Research Master, Human Approver |
| 14. 모델 등록 | Release / Registry Manager, Human Approver |
| 15. 장기 운영 | Ops / Scheduler, Research Master, Reporter |

---

## 8. 최소·표준·풀셋 구성 비교

| 구분 | 역할 수 | 구성 |
|---|---:|---|
| 최소 구성 | 6 | Research Master, Data Auditor, Modeler, Evaluator, Codex Pro, Claude Code Max |
| 표준 구성 | 12 | 최소 구성 + Feature Engineer, HPO Agent, Error Analyst, Reporter, Experiment Tracker, Reproducibility Manager |
| 풀셋 구성 | 30 | 전체 역할 구성 |

---

## 9. 최소 구성

초기 검증용 최소 구성은 다음과 같다.

```text
1. Research Master
2. Data Auditor
3. Modeler
4. Evaluator
5. Implementation Worker / Codex Pro
6. Reviewer / Claude Code Max
```

최소 구성의 목적은 다음과 같다.

1. Kanban Board 운영 가능성 확인
2. 데이터 진단 Task 실행
3. 베이스라인 학습 Task 실행
4. 평가 지표 산출
5. Codex Pro 구현 흐름 확인
6. Claude Code Max 리뷰 흐름 확인

---

## 10. 표준 구성

실제 연구 운영에 적합한 표준 구성은 다음과 같다.

```text
1. Research Master
2. Data Auditor
3. Feature Engineer
4. Modeler
5. HPO Agent
6. Evaluator
7. Error Analyst
8. Reporter
9. Experiment Tracker
10. Reproducibility Manager
11. Codex Pro
12. Claude Code Max
```

표준 구성의 목적은 다음과 같다.

1. 반복 실험 운영
2. 하이퍼파라미터 탐색
3. 성능 미달 시 원인 분석
4. 실험 재현성 확보
5. 누적 리포트 제공
6. 리뷰 기반 품질 확보

---

## 11. 풀셋 구성

풀셋 구성은 장기 실행형 연구 조직을 전제로 한다.

```text
1. Human Approver
2. Research Master
3. Project Planner
4. Dataset Manager
5. Data Auditor
6. Label Quality Analyst
7. Rubric Analyst
8. Split Policy Manager
9. Feature Engineer
10. Embedding Engineer
11. Baseline Modeler
12. Transformer Modeler
13. LLM Judge Designer
14. Ensemble Designer
15. HPO Agent
16. Training Pipeline Engineer
17. Evaluation Engineer
18. Evaluator
19. Error Analyst
20. Leakage & Validity Reviewer
21. Code Reviewer
22. Experiment Tracker
23. DVC / Reproducibility Manager
24. Report Builder
25. Reporter
26. Decision Logger
27. Ops / Scheduler
28. Security & Privacy Reviewer
29. Release / Registry Manager
30. Implementation Worker
```

풀셋 구성의 목적은 다음과 같다.

1. 데이터 품질부터 모델 등록까지 전 과정 관리
2. 역할별 책임 분리
3. 장기 실행형 자율 연구 운영
4. 실험 재현성 및 추적성 확보
5. 코드 품질과 평가 신뢰성 확보
6. 리포트 기반 의사결정 지원
7. 최종 모델 후보의 근거 기반 선정

---

## 12. 권장 확장 순서

풀셋을 한 번에 모두 운영하기보다 단계적으로 확장한다.

### 12.1 1단계: 기본 연구 루프 검증

```text
Research Master
Data Auditor
Modeler
Evaluator
Codex Pro
Claude Code Max
```

검증 목표는 다음과 같다.

1. 데이터셋 진단 가능성 확인
2. 베이스라인 모델 학습 가능성 확인
3. 평가 지표 산출 가능성 확인
4. 구현·리뷰 분리 흐름 확인

### 12.2 2단계: 실험 개선 루프 확장

```text
Feature Engineer
HPO Agent
Error Analyst
Reporter
```

확장 목표는 다음과 같다.

1. 성능 미달 시 개선 방향 생성
2. 피처 재구성
3. HPO 반복 실행
4. 오류 분석 기반 다음 실험 생성
5. 누적 성능 리포트 작성

### 12.3 3단계: 데이터·루브릭 품질 관리 확장

```text
Dataset Manager
Label Quality Analyst
Rubric Analyst
Split Policy Manager
```

확장 목표는 다음과 같다.

1. 데이터셋 버전 관리
2. 라벨 신뢰도 분석
3. 루브릭 구조화
4. 데이터 누수 방지
5. train/valid/test 분할 정책 안정화

### 12.4 4단계: 추적성·운영성 확장

```text
Experiment Tracker
Reproducibility Manager
Decision Logger
Ops Scheduler
```

확장 목표는 다음과 같다.

1. MLflow run 검증
2. DVC artifact 추적
3. 실험·판정 로그 누적
4. Cron/Gateway 기반 상태 점검
5. blocked/stale task 탐지

### 12.5 5단계: 고급 모델·배포 준비 확장

```text
LLM Judge Designer
Ensemble Designer
Release Registry Manager
Security & Privacy Reviewer
```

확장 목표는 다음과 같다.

1. LLM 보조평가 설계
2. Ensemble 모델 구성
3. 최종 후보 모델 등록
4. 보안·개인정보 점검
5. 배포 전 승인 패키지 준비

---

## 13. 역할별 산출물

| 역할 | 주요 산출물 |
|---|---|
| Research Master | Kanban Task, 완료 판정, 다음 실험 계획 |
| Project Planner | Milestone, Task dependency, 연구 계획 |
| Dataset Manager | dataset_version, DVC reference, data lineage |
| Data Auditor | data_quality_report, label_distribution.csv |
| Label Quality Analyst | rater_disagreement.csv, label_confidence 정책 |
| Rubric Analyst | rubric_schema, score_band_definition |
| Split Policy Manager | split_policy.yaml, leakage_check_report |
| Feature Engineer | feature_config.yaml, feature_importance.csv |
| Embedding Engineer | embedding_feature_pipeline, similarity_features.csv |
| Baseline Modeler | baseline_run, baseline_report |
| Transformer Modeler | transformer_run, model artifact |
| LLM Judge Designer | judge_prompt_template, judge_feature_policy |
| Ensemble Designer | ensemble_config, ensemble_result |
| HPO Agent | optuna_study, trial_report |
| Training Pipeline Engineer | train.py, training_config, checkpoint policy |
| Evaluation Engineer | metrics.py, test_metrics.py |
| Evaluator | metrics.json, item_metrics.csv, score_band_metrics.csv |
| Error Analyst | high_error_samples.csv, error_analysis.md |
| Leakage & Validity Reviewer | leakage_review.md, validity_check_report |
| Code Reviewer | PR review, code_review_report |
| Experiment Tracker | mlflow_run_check, experiment_lineage |
| Reproducibility Manager | dvc_stage_check, reproducibility_report |
| Report Builder | report generator code, chart generation code |
| Reporter | cumulative_report.html, leaderboard.csv |
| Decision Logger | DECISION_LOG.md, EXPERIMENT_LOG.md |
| Ops / Scheduler | daily_status_report, blocked_task_report |
| Security & Privacy Reviewer | privacy_review.md, secret_scan_report |
| Release / Registry Manager | model_registry_entry, release_note |
| Implementation Worker | implementation diff, tests, fix summary |

---

## 14. Kanban Board와 역할 연결

권장 Board는 다음과 같다.

```text
essay-auto-scoring-research
```

Board 안에서 역할별 Task를 배정한다.

```text
T001 → Research Master
T002 → Dataset Manager
T003 → Data Auditor
T004 → Label Quality Analyst
T005 → Split Policy Manager
T006 → Evaluation Engineer / Codex Pro
T007 → Baseline Modeler / Codex Pro
T008 → Evaluator
T009 → Error Analyst
T010 → Claude Code Max Reviewer
T011 → Reporter
T012 → Research Master
```

Task 상태 흐름은 다음을 따른다.

```text
triage → todo → ready → running → done
                    ↓
                 blocked
```

---

## 15. 운영 원칙

```text
1. Research Master는 모든 작업의 목표와 완료 기준을 관리한다.
2. Human Approver는 최종 승인과 기준 변경만 담당한다.
3. Codex Pro는 구현과 테스트 작성을 담당한다.
4. Claude Code Max는 리뷰와 신뢰성 검토를 담당한다.
5. Hermes Profile은 역할별 분석·판정·리포트를 담당한다.
6. 같은 파일을 여러 역할이 동시에 수정하지 않는다.
7. 모든 실험은 MLflow에 기록한다.
8. 모든 데이터·분할·피처 artifact는 DVC로 추적한다.
9. 모든 주요 결정은 DECISION_LOG.md에 남긴다.
10. 성능 미달 시 원인 분석 없이 다음 실험을 실행하지 않는다.
11. test set은 반복 튜닝에 사용하지 않는다.
12. final model registration은 Human Approver 승인 후 수행한다.
```

---

## 16. 최종 권장안

풀셋 구성은 장기 실행형 연구 조직의 전체 역할을 정의한 것이다. 실제 시작은 최소 구성으로 시작하고, 연구 루프가 안정화되면 표준 구성, 이후 풀셋 구성으로 확장한다.

권장 시작 구성은 다음과 같다.

```text
1단계:
Research Master + Data Auditor + Modeler + Evaluator + Codex Pro + Claude Code Max

2단계:
Feature Engineer + HPO Agent + Error Analyst + Reporter

3단계:
Dataset Manager + Label Quality Analyst + Rubric Analyst + Split Policy Manager

4단계:
Experiment Tracker + Reproducibility Manager + Decision Logger + Ops Scheduler

5단계:
LLM Judge Designer + Ensemble Designer + Release Registry Manager + Security Reviewer
```

---

## 17. 결론

Hermes Kanban 기반 AI 서술형 자동채점 연구팀은 다음과 같은 구조로 운영하는 것이 적합하다.

```text
Hermes Profile은 역할을 담당한다.
Codex Pro는 구현을 담당한다.
Claude Code Max는 검토를 담당한다.
Research Master는 판정과 재계획을 담당한다.
Human Approver는 기준 변경과 최종 승인을 담당한다.
```

풀셋 구성은 총 30개 역할로 정의되며, 데이터 진단, 라벨 품질 분석, 루브릭 구조화, 피처 설계, 모델링, HPO, 평가, 오류 분석, 리포트, 재현성, 보안, 모델 등록까지 전체 연구 생애주기를 포괄한다.

이 구성을 적용하면 AI 서술형 자동채점 모델 구축 연구를 단기 실험이 아니라, 목표 달성까지 지속적으로 실행되는 장기 연구팀 체계로 운영할 수 있다.

