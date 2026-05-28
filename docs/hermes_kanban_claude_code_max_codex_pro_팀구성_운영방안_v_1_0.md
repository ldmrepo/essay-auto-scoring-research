# Hermes Kanban 기반 Claude Code Max · Codex Pro 팀 구성 운영 방안

문서 버전: v1.0
작성일: 2026-05-27
문서명: Hermes_Kanban_Claude_Code_Max_Codex_Pro_팀구성_운영방안_v1_0.md
대상 프로젝트: AI 서술형 자동채점 모델 구축 연구 / 장기 실행형 AI 개발·연구 프로젝트
적용 도구: Hermes Agent, Hermes Kanban Multi-Agent Board, Claude Code Max, Codex Pro, GitHub, MLflow, DVC, Optuna

---

## 1. 문서 목적

본 문서는 현재 사용 중인 Claude Code Max와 Codex Pro 구독을 Hermes Kanban Multi-Agent Board 기반 연구·개발팀 구성에 통합하는 운영 방안을 정리한다.

목표는 Hermes를 장기 실행형 작업관리자 및 오케스트레이터로 사용하고, Claude Code Max와 Codex Pro를 각각 전문 역할의 실행 도구로 배치하여 AI 서술형 자동채점 모델 구축 연구를 지속적으로 수행하는 것이다.

---

## 2. 기본 전제

현재 보유 도구는 다음과 같다.

| 도구 | 사용 위치 | 기본 역할 |
|---|---|---|
| Hermes Agent | 작업 오케스트레이션 | 장기 작업 관리, 프로파일 구성, Kanban Task 관리 |
| Hermes Kanban Multi-Agent Board | 프로젝트 작업 보드 | Task 생성, 상태 관리, 담당자 배정, blocked 관리 |
| Claude Code Max | 고급 코드 분석·리뷰 | 설계 검토, 코드 리뷰, 리팩터링 검토, 장문 컨텍스트 분석 |
| Codex Pro | 코드 구현·수정 | 코드 작성, 테스트 작성, 반복 수정, 파이프라인 구현 |
| GitHub | 공식 개발 이력 | Issue, Branch, PR, Review, CI 관리 |
| MLflow | 실험 추적 | 모델 run, metric, artifact, 모델 버전 기록 |
| DVC | 데이터 버전 관리 | 데이터셋, split, feature artifact 버전 관리 |
| Optuna | 하이퍼파라미터 탐색 | HPO study, trial, search space 관리 |

---

## 3. 핵심 운영 방향

본 구성의 핵심 방향은 다음과 같다.

```text
Hermes Kanban = 장기 작업 보드 / 오케스트레이션
Hermes Profile = 역할별 에이전트
Codex Pro = 구현자 / 테스트 작성자 / 반복 수정자
Claude Code Max = 설계 검토자 / 코드 리뷰어 / 리팩터링 검토자
GitHub Issue/PR = 공식 개발 이력
MLflow/DVC/Optuna = 실험 증거 관리
```

즉, Claude Code와 Codex를 Hermes Profile 자체로 대체하기보다, Hermes 팀원이 호출하거나 활용하는 전문 코딩 도구로 배치하는 방식이 가장 안정적이다.

---

## 4. 권장 역할 배치

| 역할 | 담당 도구 | 설명 |
|---|---|---|
| 총괄 오케스트레이션 | Hermes Kanban | 장기 Task, 상태, blocked, handoff 관리 |
| 연구 총괄 | Hermes `research-master` | 목표 달성 여부 판정, 다음 실험 생성 |
| 요구사항·작업 분해 | Hermes `planner` 또는 `research-master` | 프로젝트 목표를 Task로 분해 |
| 코드 구현 | Codex Pro | 평가 코드, 학습 파이프라인, 리포트 코드 작성 |
| 반복 수정 | Codex Pro | 테스트 실패 수정, config 변경, 파이프라인 보완 |
| 설계 검토 | Claude Code Max | 구조, 책임 경계, 데이터 누수, 평가 신뢰성 점검 |
| 코드 리뷰 | Claude Code Max | PR diff, metric 구현, edge case, 리팩터링 검토 |
| 실험 평가 | Hermes `evaluator` + Python pipeline | QWK, MAE, RMSE, Pearson, Spearman 등 측정 |
| 오류 분석 | Hermes `error-analyst` | 실패 원인, 고오차 샘플, 다음 실험 방향 분석 |
| 최종 승인 | 사용자 / 팀장 | 모델 등록, 기준 변경, test set 변경, 배포 승인 |

---

## 5. 전체 팀 구성

AI 서술형 자동채점 연구팀 기준 권장 구성은 다음과 같다.

```text
Board:
  essay-auto-scoring-research

Hermes Profiles:
  research-master
  data-auditor
  feature-engineer
  modeler
  hpo-agent
  evaluator
  error-analyst
  reporter

External Coding Agents:
  Codex Pro
  Claude Code Max

Tracking:
  GitHub
  MLflow
  DVC
  Optuna

Reports:
  cumulative_report.html
  leaderboard.csv
  metric_trends.csv
  item_metrics.csv
  high_error_samples.csv
```

---

## 6. 도구별 책임 경계

### 6.1 Hermes Kanban

Hermes Kanban은 전체 작업 흐름을 관리한다.

주요 책임은 다음과 같다.

1. 프로젝트별 Board 관리
2. Task 생성
3. Task 상태 관리
4. 담당 Profile 배정
5. blocked 상태 추적
6. handoff/comment 기록
7. 장기 실행 작업 추적
8. Cron/Gateway와 연계한 정기 보고

Hermes Kanban은 코드 구현 자체보다 “누가 어떤 일을 어떤 상태로 수행하고 있는가”를 관리하는 계층이다.

### 6.2 Hermes Profile

Hermes Profile은 역할별 에이전트 환경이다.

예시는 다음과 같다.

| Profile | 책임 |
|---|---|
| research-master | 연구 목표 관리, 완료 판정, 다음 Task 생성 |
| data-auditor | 데이터셋 구조, 품질, 라벨 분포 분석 |
| feature-engineer | 피처 설계, 재구성, 피처 중요도 분석 |
| modeler | 학습 파이프라인 실행, 모델 후보 생성 |
| hpo-agent | 하이퍼파라미터 탐색 실행 |
| evaluator | 성능 측정, 평가 지표 산출 |
| error-analyst | 고오차 샘플, 실패 원인 분석 |
| reporter | 누적 리포트 작성 |

### 6.3 Codex Pro

Codex Pro는 구현 및 수정 중심의 작업자로 사용한다.

권장 작업은 다음과 같다.

1. 학습 파이프라인 코드 작성
2. 평가 지표 코드 작성
3. 테스트 코드 작성
4. MLflow logging 코드 작성
5. DVC pipeline script 작성
6. Optuna HPO 코드 작성
7. 리포트 생성 코드 작성
8. 테스트 실패 수정
9. 반복적인 코드 변경 반영

### 6.4 Claude Code Max

Claude Code Max는 설계 검토와 코드 리뷰 중심으로 사용한다.

권장 작업은 다음과 같다.

1. 파이프라인 구조 리뷰
2. 데이터 누수 가능성 점검
3. 평가 지표 구현 검토
4. 모델 학습 구조 검토
5. PR diff 리뷰
6. 리팩터링 방향 제안
7. 테스트 커버리지 검토
8. 실험 결과 해석 보조
9. 장문 문맥 기반 설계 검토

---

## 7. 기본 운영 흐름

```text
1. research-master가 Hermes Kanban Task 생성
2. 담당 Hermes Profile이 Task를 claim
3. 구현이 필요한 경우 Codex Pro에 작업 범위 전달
4. Codex Pro가 코드 작성 또는 테스트 작성
5. Claude Code Max가 변경사항과 설계를 리뷰
6. evaluator가 테스트 및 성능 측정 실행
7. error-analyst가 실패 원인 분석
8. research-master가 PASS/FAIL 판정
9. FAIL이면 다음 Kanban Task 생성
10. PASS이면 reporter가 리포트 갱신
```

---

## 8. AI 서술형 자동채점 연구 적용 흐름

```text
데이터셋 수령
  ↓
research-master: 초기 Task 생성
  ↓
data-auditor: 데이터셋 구조·라벨 품질 분석
  ↓
Codex Pro: 데이터 진단 스크립트 작성
  ↓
Claude Code Max: 데이터 분할·누수 위험 검토
  ↓
modeler: 베이스라인 모델 실험
  ↓
Codex Pro: train.py / evaluate.py / metrics.py 구현
  ↓
Claude Code Max: 평가 지표 및 파이프라인 리뷰
  ↓
evaluator: QWK, MAE, RMSE, Pearson, Spearman 측정
  ↓
error-analyst: 고오차 샘플 및 실패 원인 분석
  ↓
research-master: 완료 기준 비교
  ├─ PASS → reporter: 최종 리포트 생성
  └─ FAIL → feature-engineer / hpo-agent / modeler에게 다음 Task 생성
```

---

## 9. Kanban Task 예시

초기 Task 세트는 다음과 같이 구성한다.

```text
T001. 프로젝트 목표 및 완료 기준 정의
T002. 데이터셋 구조 분석
T003. 문항별/점수별 라벨 분포 분석
T004. 채점자 불일치 및 라벨 신뢰도 분석
T005. 데이터 분할 정책 수립
T006. 평가 지표 패키지 구현
T007. QWK/MAE/RMSE/Pearson/Spearman 테스트 코드 작성
T008. 베이스라인 모델 1: 길이/통계 피처
T009. 베이스라인 모델 2: TF-IDF + 회귀 모델
T010. 베이스라인 모델 3: 임베딩 + 회귀 모델
T011. Transformer 기반 모델 실험
T012. 루브릭 기반 피처 추가 실험
T013. Optuna HPO 실험
T014. MLflow logging 연동
T015. DVC 데이터 버전 파이프라인 구성
T016. 전체/문항별/점수대별 평가 리포트 생성
T017. 고오차 샘플 분석
T018. Claude Code Max 기반 파이프라인 리뷰
T019. 목표 달성 판정
T020. 미달 시 다음 실험 계획 생성
```

---

## 10. Codex Pro에 전달할 작업 템플릿

Codex Pro에는 작업 범위를 명확히 제한해서 전달해야 한다.

```text
Task ID:
T006

작업명:
평가 지표 패키지 구현

목표:
서술형 자동채점 모델 평가를 위한 QWK, MAE, RMSE, Pearson, Spearman, Exact Agreement, Adjacent Agreement 계산 함수를 구현한다.

대상 파일:
- src/evaluation/metrics.py
- tests/test_metrics.py

완료 기준:
- 모든 metric 함수에 단위 테스트가 존재한다.
- 결측값, 범위 밖 점수, 단일 클래스 입력 edge case를 처리한다.
- pytest가 통과한다.
- metrics.json 저장 함수가 포함된다.

금지:
- 데이터 split 정책을 변경하지 않는다.
- 모델 학습 코드를 수정하지 않는다.
- test set을 튜닝 목적으로 사용하지 않는다.

테스트 명령:
pytest tests/test_metrics.py

산출물:
- 구현 코드
- 테스트 코드
- 변경 요약
```

---

## 11. Claude Code Max에 전달할 리뷰 템플릿

Claude Code Max에는 구현 결과의 검토 기준을 명확히 전달한다.

```text
Review Task ID:
R006

검토 대상:
T006 평가 지표 패키지 구현 결과

검토 범위:
- src/evaluation/metrics.py
- tests/test_metrics.py
- 관련 Git diff

검토 기준:
1. QWK 계산이 수학적으로 올바른가?
2. MAE/RMSE 계산에서 결측값과 dtype 처리가 안전한가?
3. Pearson/Spearman 계산에서 단일 값 배열 edge case가 처리되는가?
4. Exact Agreement와 Adjacent Agreement 정의가 명확한가?
5. 테스트가 정상/경계/오류 케이스를 포함하는가?
6. 향후 item-wise metric 확장에 적합한 구조인가?
7. 데이터 누수 가능성은 없는가?

결과 형식:
- 승인 가능
- 수정 필요
- 치명적 오류
- 권장 리팩터링
- 추가 테스트 제안
```

---

## 12. GitHub 연계 방식

Hermes Kanban과 GitHub는 역할을 분리해야 한다.

| 구분 | 역할 |
|---|---|
| Hermes Kanban Task | 에이전트 작업 관리 |
| GitHub Issue | 공식 작업 단위 |
| Git Branch | 구현 단위 |
| Pull Request | 코드 변경 검토 단위 |
| CI | 자동 테스트 및 품질 확인 |
| Review Comment | 사람 및 Claude Code 리뷰 기록 |

권장 규칙은 다음과 같다.

```text
1 Kanban Task = 1 GitHub Issue 또는 Issue 하위 작업
1 구현 Task = 1 Branch
1 완료 후보 = 1 Pull Request
1 Review Task = Claude Code Max 검토
최종 Merge = 사람 승인
```

---

## 13. AGENTS.md에 포함할 외부 코딩 도구 규칙

프로젝트 루트의 `AGENTS.md`에는 다음 규칙을 포함한다.

```md
## External Coding Agents

이 프로젝트에서는 구현 및 리뷰 작업에 다음 외부 코딩 도구를 사용할 수 있다.

- Codex Pro: 구현, 테스트 작성, 반복 수정
- Claude Code Max: 코드 리뷰, 설계 검토, 리팩터링 제안

## Rules

- Codex Pro와 Claude Code Max에 넘기는 작업은 Kanban Task 범위 안으로 제한한다.
- 전체 프로젝트 목표를 무제한으로 전달하지 않는다.
- 대상 파일, 금지 변경 범위, 완료 기준, 테스트 명령을 함께 전달한다.
- 외부 도구가 만든 변경은 반드시 Git diff로 확인한다.
- 테스트 실패 상태에서는 Kanban Task를 done 처리하지 않는다.
- Claude Code Max 리뷰 없이 핵심 평가/학습 파이프라인을 완료 처리하지 않는다.
- test set 변경, label policy 변경, final model registration은 사람 승인이 필요하다.
```

---

## 14. 완료 판정 기준

외부 코딩 도구를 사용하더라도 완료 판정은 Hermes `research-master`가 기준 파일을 보고 수행한다.

완료 조건 예시는 다음과 같다.

```text
1. Kanban Task 완료
2. GitHub PR 생성
3. 테스트 통과
4. Claude Code Max 리뷰 통과
5. MLflow run 기록 존재
6. DVC dataset/split/version 기록 존재
7. 평가 metric 산출 완료
8. error analysis 또는 review log 작성
9. ACCEPTANCE_CRITERIA.yaml 기준 통과
10. 사람 승인 필요 항목이면 승인 완료
```

판정 상태는 다음과 같이 관리한다.

| 판정 | 의미 |
|---|---|
| PASS_FINAL | 최종 기준 통과 |
| PASS_CANDIDATE | 후보 기준 통과, 추가 검증 필요 |
| FAIL_RETRY_HPO | HPO 재시도 필요 |
| FAIL_REBUILD_FEATURES | 피처 재구성 필요 |
| FAIL_REVIEW_LABELS | 라벨 품질 검토 필요 |
| FAIL_CHANGE_MODEL | 모델 구조 변경 필요 |
| FAIL_NEED_MORE_DATA | 데이터 추가 필요 |
| FAIL_STOP_NO_GAIN | 개선 정체, 사람 판단 필요 |

---

## 15. 리포트 구성

Codex Pro와 Claude Code Max 사용 이력도 리포트에 포함해야 한다.

리포트 항목은 다음과 같다.

```text
1. 전체 Kanban Task 현황
2. Codex Pro 구현 Task 목록
3. Claude Code Max 리뷰 Task 목록
4. PR별 리뷰 결과
5. 테스트 통과/실패 이력
6. MLflow run별 성능 지표
7. DVC dataset/split/feature version
8. Optuna trial 요약
9. 목표 대비 현재 성능
10. 실패 원인과 다음 Task
11. 최종 후보 모델 및 선정 근거
```

권장 산출물은 다음과 같다.

```text
reports/latest/cumulative_report.html
reports/latest/codex_task_summary.csv
reports/latest/claude_review_summary.csv
reports/latest/leaderboard.csv
reports/latest/metric_trends.csv
reports/latest/decision_summary.md
```

---

## 16. 운영 시 주의사항

### 16.1 책임 경계 유지

Hermes, Codex, Claude Code의 책임을 혼합하지 않는다.

```text
Hermes = 작업 관리와 판정
Codex = 구현과 테스트 작성
Claude Code = 리뷰와 설계 검토
GitHub = 공식 이력
```

### 16.2 동시 수정 방지

같은 파일을 여러 도구가 동시에 수정하지 않도록 관리한다.

권장 규칙은 다음과 같다.

```text
1개 구현 Task = 1개 담당자
같은 파일을 수정하는 Task는 dependency 설정
리뷰 반영 Task는 별도로 생성
```

### 16.3 컨텍스트 제한

Codex와 Claude Code에 전체 저장소와 모든 데이터를 무제한 전달하지 않는다.

전달해야 할 정보는 다음으로 제한한다.

```text
- Task ID
- 작업 목표
- 대상 파일
- 완료 기준
- 금지 변경 범위
- 테스트 명령
- 관련 문서 링크
```

### 16.4 데이터 보안

서술형 자동채점 데이터에는 개인정보나 민감 정보가 포함될 수 있다.

따라서 다음 규칙이 필요하다.

```text
- 원본 데이터 직접 전달 금지
- 샘플 데이터는 비식별화 후 전달
- API key, .env, 인증 정보 전달 금지
- 외부 도구에는 최소한의 파일만 제공
- 모델 평가 결과는 내부 저장소에 기록
```

### 16.5 최종 승인 유지

다음 항목은 반드시 사람 승인이 필요하다.

```text
- test set 변경
- label policy 변경
- acceptance criteria 변경
- final model registration
- production deployment
- 개인정보 포함 데이터 사용
```

---

## 17. 권장 도입 순서

### 17.1 1단계: 기본 팀 구성

```text
1. Hermes board 생성
2. research-master / modeler / evaluator / reviewer profile 생성
3. AGENTS.md 작성
4. Codex Pro 사용 규칙 추가
5. Claude Code Max 리뷰 규칙 추가
```

### 17.2 2단계: 코드 구현 루프 검증

```text
1. 작은 평가 지표 구현 Task 생성
2. Codex Pro로 구현
3. Claude Code Max로 리뷰
4. 테스트 실행
5. Kanban Task done 처리
```

### 17.3 3단계: 모델 실험 루프 확장

```text
1. train.py 구현
2. evaluate.py 구현
3. MLflow logging 연동
4. DVC dataset version 연동
5. Optuna HPO 실행
6. 리포트 자동 생성
```

### 17.4 4단계: 장기 실행 운영

```text
1. Cron으로 상태 점검
2. Gateway로 리포트 알림
3. blocked task 자동 탐지
4. 목표 미달 시 다음 실험 Task 생성
5. Claude Code Max 정기 리뷰 Task 생성
```

---

## 18. 최종 권장안

현재 Claude Code Max와 Codex Pro를 구독 중인 상황에서는 다음 구조가 가장 현실적이다.

```text
Hermes Kanban:
  장기 실행 연구 보드

Hermes Profiles:
  research-master
  data-auditor
  feature-engineer
  modeler
  hpo-agent
  evaluator
  error-analyst
  reporter

Codex Pro:
  구현 전담 worker
  테스트 작성 worker
  반복 수정 worker

Claude Code Max:
  설계 리뷰어
  코드 리뷰어
  평가 신뢰성 검토자
  리팩터링 검토자

GitHub:
  Issue / Branch / PR / Review 이력 관리

MLflow + DVC + Optuna:
  실험 추적 / 데이터 버전 / HPO 관리
```

---

## 19. 결론

Claude Code Max와 Codex Pro는 Hermes Kanban 기반 팀 구성에서 충분히 활용 가능하다.

가장 안정적인 방식은 다음과 같다.

```text
Hermes를 팀장/작업관리자로 둔다.
Codex Pro를 구현 팀원으로 둔다.
Claude Code Max를 수석 리뷰어로 둔다.
GitHub PR을 공식 검토 지점으로 둔다.
MLflow/DVC/Optuna를 실험 증거 저장소로 둔다.
```

이 구조를 적용하면 AI 서술형 자동채점 모델 구축 연구에서 다음을 달성할 수 있다.

1. 장기 실행형 연구 작업 관리
2. 구현과 리뷰의 역할 분리
3. 실험 재현성 확보
4. 모델 성능 추적
5. 목표 미달 시 자동 재실험 계획 생성
6. 코드 품질과 평가 신뢰성 확보
7. 최종 후보 모델의 근거 기반 선정

핵심 원칙은 다음 한 문장으로 정리할 수 있다.

```text
Hermes Kanban은 작업을 관리하고, Codex Pro는 구현하며, Claude Code Max는 검토하고, GitHub와 MLflow/DVC/Optuna는 증거를 남긴다.
```

