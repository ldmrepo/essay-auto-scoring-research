# Hermes Kanban 기반 24시간 자율 연구 워크플로우 세미나 초안 v1.2

> 주제: Hermes Kanban 기반 24시간 자율 연구 워크플로우  
> Running example: 한국어 K-12 에세이 자동채점 모델 연구  
> 분량: PPT 20페이지 기준  
> 발표 정보: (주) 아이오시스 연구소 AI 개발팀 / 수석 연구원 이동명 / 2025-05-28  
> 문서 작성일: 2026-05-28

## 발표 핵심 메시지

이 세미나의 중심은 자동채점 모델 자체가 아니라, **장시간 연구를 agent가 수행해도 사람이 추적하고 통제할 수 있는 워크플로우 시스템**입니다.

여기서 말하는 24시간 자율 연구는 무감독 완전 자동화가 아닙니다. 인간 승인 gate, hard block, 비용/보안 경계 안에서 장시간 실행과 재개가 가능한 **controlled autonomy**를 의미합니다.

자동채점 프로젝트는 다음 질문에 답하기 위한 사례입니다.

- 장기 연구를 어떤 단위로 나눌 것인가?
- agent에게 어디까지 자율성을 줄 것인가?
- 실패했을 때 어떻게 멈추고, 어떻게 복구할 것인가?
- 어떤 증거를 남겨야 다음 cycle이 이어질 수 있는가?
- 인간은 어디에서 최소한으로 개입해야 하는가?

---

## 1. Title

### Hermes Kanban 기반 24시간 자율 연구 워크플로우

**Subtitle**

추적·통제·복구 가능한 Multi-Agent 연구 시스템과 자동채점 사례

**본문**

- (주) 아이오시스 연구소 AI 개발팀
- 수석 연구원 이동명 · 2025-05-28
- Hermes Multi-Agent Kanban Board
- Running example: 한국어 K-12 에세이 자동채점 모델 연구
- 핵심 관점: 모델 성능보다 **연구 운영 시스템** 검증

**시각화 제안**

중앙에 Kanban board와 agent profiles가 있고, 오른쪽에 MLflow/workspace artifacts가 연결되는 구조도.

**발표 메모**

오늘 발표는 “AI가 연구자를 대체한다”가 아니라, “AI agent가 오래 일해도 사람이 이해하고 통제할 수 있는 연구 워크플로우를 어떻게 설계할 것인가”에 대한 이야기입니다. 예시로 한국어 K-12 에세이 자동채점 연구를 사용하지만, 핵심 주제는 모델 성능 경쟁이 아니라 연구 운영 시스템입니다.

발표를 들으실 때는 세 가지 질문을 중심으로 보시면 됩니다. 첫째, 장기 연구를 어떤 단위로 나누면 agent가 이어서 처리할 수 있는가. 둘째, agent가 실패했을 때 사람이 어떤 근거로 상태를 복원하고 재개할 수 있는가. 셋째, 자율성을 높이면서도 leakage, 비용, 보안, 환경 제약을 어떻게 통제할 수 있는가입니다.

이 세미나의 결론은 완전 자동화가 아닙니다. 목표는 “사람이 통제 가능한 자율성”입니다. 즉, 정상 경로는 agent가 계속 진행하되, 위험한 결정과 정책 변경은 사람이 볼 수 있는 gate에서 멈추는 구조를 제안합니다.

---

## 2. 왜 24시간 자율 연구 워크플로우가 필요한가

### 장기 연구는 실험보다 운영이 어렵다

**본문**

- ML 연구는 단일 실험보다 반복 cycle이 중요하다.
- 데이터 audit, split, feature, model, eval, review가 계속 이어진다.
- 실패 원인이 환경, 데이터, 코드, 정책, 비용으로 섞인다.
- 사람이 모든 중간 상태를 기억하기 어렵다.
- agent가 장시간 일하려면 실행보다 **상태 추적과 복구 구조**가 먼저 필요하다.

**시각화 제안**

왼쪽: 흩어진 notebook, shell log, TODO. 오른쪽: task graph + artifacts + decision gate.

**발표 메모**

연구 자동화에서 흔한 착각은 “실행만 자동화하면 된다”는 것입니다. 실제 ML 연구는 단일 학습 명령보다 그 앞뒤의 운영이 더 어렵습니다. 데이터가 바뀌고, split 정책이 바뀌고, feature leakage가 발견되고, metric 기준이 바뀌며, 환경 문제로 학습이 멈추는 일이 반복됩니다.

이때 사람이 가장 많은 시간을 쓰는 부분은 코드를 다시 작성하는 일이 아니라 “지금 어디까지 했는가”를 복원하는 일입니다. 어느 데이터로 학습했는지, 어떤 seed였는지, 왜 block 되었는지, 다음 단계가 무엇인지가 흩어져 있으면 24시간 agent가 일해도 다음 날 사람이 이어받기 어렵습니다.

따라서 24시간 자율 연구의 핵심은 긴 시간 실행되는 프로세스가 아니라, 긴 시간 동안 상태를 잃지 않는 구조입니다. 이 문제를 해결하기 위해 Hermes Kanban은 연구를 task graph, artifact, comment, run history, decision gate로 나누어 다룹니다.

---

## 3. 기존 접근의 한계

### 실행 도구는 많지만 연구 상태 복원은 별도 문제다

**본문**

| 방식 | 장점 | 한계 |
|---|---|---|
| Notebook | 빠른 탐색 | 상태와 의사결정 추적 약함 |
| Shell script | 재현 쉬움 | 실패 분기와 인간 판단 표현 어려움 |
| Cron | 반복 실행 | 연구 맥락과 품질 gate 부족 |
| 단발성 agent | 빠른 구현 | 다음 cycle로 지식 전파 약함 |
| Airflow/Dagster/Prefect | 안정적 orchestration | 연구 판단, agent 역할, block narrative는 별도 설계 필요 |
| MLflow pipeline/CI | 실험 추적과 검증 자동화 | 다음 연구 cycle의 task body와 인간 decision gate까지는 표현 부족 |

**핵심 문제**

- 실행 이력은 남지만 연구 의사결정이 남지 않는다.
- 실패가 다음 작업의 입력으로 구조화되지 않는다.
- 장시간 실행 후 사람이 상황을 복원하기 어렵다.

**시각화 제안**

각 방식의 장단점을 작은 카드로 배치. 강한 대안인 workflow orchestrator와 MLflow/CI도 함께 비교.

**발표 메모**

기존 도구들은 각각 강점이 분명합니다. Notebook은 빠른 탐색에 좋고, shell script는 재현 명령을 남기기 좋습니다. Airflow나 Dagster 같은 orchestrator는 production pipeline에는 강력하고, MLflow는 실험 추적에 매우 유용합니다. 여기서 말하려는 것은 이런 도구들이 부족하다는 뜻이 아닙니다.

문제는 장기 연구에서 “실행 순서”와 “연구 판단”이 같이 움직인다는 점입니다. 예를 들어 split 실패는 단순 job failure가 아니라 데이터 구조와 정책의 충돌입니다. M5 학습 block도 모델 코드 실패가 아니라 네트워크와 sandbox 정책의 충돌입니다. 이런 판단은 로그 한 줄보다 task body, comment, artifact, human gate로 남겨야 다음 cycle이 같은 실패를 반복하지 않습니다.

Hermes의 차별점은 실행 graph와 의사결정 graph를 같은 Kanban surface에 올리는 것입니다. 어떤 task가 왜 ready인지, 왜 blocked인지, 어떤 artifact를 남겼는지, 다음 사람이 무엇을 승인해야 하는지가 하나의 보드에서 이어집니다.

---

## 4. 핵심 아이디어

### 연구를 Kanban task graph로 만들고 agent profile이 처리한다

**본문**

- 연구를 `task` 단위로 분해한다.
- task 간 dependency가 연구 진행 순서를 결정한다.
- 각 agent profile은 역할에 맞는 task만 처리한다.
- 실패, 승인, 재시도까지 task graph에 남긴다.

**한 줄 요약**

> 자율 연구는 자유 실행이 아니라, task graph 위에서 검증 가능한 worker들이 일하는 구조다.

**시각화 제안**

큰 task graph 그림. 키워드는 `task`, `profile`, `artifact`, `gate` 4개만 강조.

**발표 메모**

Hermes Kanban의 핵심은 agent를 “대화 상대”가 아니라 “보드 위의 작업자”로 다루는 것입니다. agent에게 자유롭게 연구를 맡기는 대신, 연구를 task 단위로 나누고 각 task의 입력, 출력, parent dependency, 완료 조건을 명확히 둡니다.

이렇게 하면 agent의 자율성은 task graph 안에서만 작동합니다. agent는 다음 할 일을 임의로 상상하는 것이 아니라, ready 상태가 된 task를 보고 수행합니다. 실패하면 silent하게 넘어가지 않고 block reason을 남깁니다. 결과는 workspace artifact나 MLflow run처럼 다음 단계가 읽을 수 있는 형태로 남깁니다.

이 구조의 장점은 사람이 중간에 들어와도 전체 맥락을 복원할 수 있다는 점입니다. “누가, 어떤 task에서, 무엇을 입력으로 받아, 어떤 산출물을 만들었고, 왜 멈췄는가”가 보드에 남습니다.

---

## 5. Hermes Kanban 기본 구조

### Board, Task, Profile, Run, Comment, Artifact

**본문**

| 요소 | 역할 |
|---|---|
| Board | 프로젝트 단위 queue |
| Task | 수행 가능한 연구 단위 |
| Parent/Child | 의존성 graph |
| Profile | 역할별 agent persona/runtime |
| Run | task 시도 이력 |
| Comment | 의사결정과 block 근거 |
| Workspace | 파일 산출물 저장 위치 |

**예시**

- `t_dcecd4b1`: `T-CYCLE-M1-MODEL: M1~M5 baseline 학습`
- assignee: `gauss`
- task status: board 상태 기준
- M5 substate: environment block/retry 대상
- artifacts: `workspace/cycle_M1/models/`

**시각화 제안**

실제 task card 또는 확대 mock을 조기 노출하고, field를 annotate.

**발표 메모**

중요한 것은 task가 단순 TODO가 아니라는 점입니다. Hermes의 task는 연구 단위이면서 동시에 상태 저장소입니다. task 안에는 parent dependency, assignee profile, status, run attempt, comment, artifact path가 함께 연결됩니다.

예를 들어 `t_dcecd4b1` 같은 task id는 단순히 “모델 학습”을 가리키는 이름이 아닙니다. 이 task를 보면 M1~M4는 완료됐고, M5는 환경 block으로 retry 대상이며, 관련 artifact가 어느 workspace에 있는지 확인할 수 있습니다. 나중에 다른 agent나 사람이 들어와도 이 task 하나에서 연구 상태를 다시 구성할 수 있습니다.

이 객체 모델을 이해하면 뒤의 모든 사례가 단순해집니다. 성공도 task에 남고, 실패도 task에 남고, 판단도 comment와 gate에 남습니다. 그래서 Hermes Kanban은 연구 실행 도구이면서 동시에 연구 기억 장치입니다.

---

## 6. 24시간 자율 Loop

### AUDIT → SPLIT → FEATURE → MODEL → HPO → EVAL/REVIEW → SYNTH → DECIDE

**본문**

정상 cycle의 목표 구조:

```text
AUDIT
  -> SPLIT
  -> FEATURE
  -> MODEL
  -> HPO
  -> EVAL || REVIEW
  -> SYNTH
  -> DECIDE
```

**역할**

- `AUDIT`: 데이터와 goal anchor 확인
- `SPLIT`: leakage 없는 fold 생성
- `FEATURE`: feature provenance 생성
- `MODEL`: baseline 학습
- `HPO`: Optuna trial
- `EVAL`: metric, CI, fairness 평가
- `REVIEW`: 코드, leakage, 재현성 검토
- `SYNTH`: cycle report와 다음 cycle 등록
- `DECIDE`: 인간 승인 gate

운영 의미:

- 대부분의 단계는 agent가 이어서 수행한다.
- hard rule 위반, 환경 block, 비용 초과, remote GPU 운영 전환은 즉시 멈춘다.
- 인간은 정상 경로에서는 DECIDE에 집중하고, 예외 경로에서는 별도 gate를 승인한다.

**시각화 제안**

가로 pipeline + EVAL/REVIEW 병렬 fan-out. 하단에는 24시간 timeline을 두고 auto 구간, block, DECIDE marker를 표시.

**발표 메모**

이 구조는 ML 연구의 표준 흐름을 Hermes Kanban task graph로 표현한 것입니다. AUDIT에서 데이터와 목표를 확인하고, SPLIT에서 leakage 없는 fold를 만들고, FEATURE에서 provenance를 남깁니다. MODEL과 HPO는 학습과 탐색을 담당하고, EVAL과 REVIEW는 병렬로 품질과 구현 리스크를 확인합니다. SYNTH는 결과를 종합하고, DECIDE는 사람이 다음 cycle 진행 여부를 판단하는 지점입니다.

여기서 “24시간”은 agent가 쉬지 않고 성공한다는 뜻이 아닙니다. 오히려 멈추는 상황을 전제로 합니다. hard rule 위반, 환경 block, 비용 초과, remote GPU 운영 전환처럼 위험한 상황에서는 멈추는 것이 정상 동작입니다.

따라서 이 loop의 품질은 얼마나 많이 자동 실행했는지가 아니라, 멈췄을 때 얼마나 정확히 상태를 남기고 재개할 수 있는지로 평가해야 합니다. 자율성은 계속 달리는 능력이 아니라, 통제 가능한 방식으로 이어지는 능력입니다.

---

## 7. Profile 기반 역할 분리

### 한 agent가 모든 것을 하지 않는다

**본문**

| Profile | 책임 |
|---|---|
| `tukey` | 데이터 audit |
| `gauss` | split, feature, model, HPO |
| `spearman` | 평가 통계 |
| `turing` | 코드/누수/reproducibility review |
| `aristotle` | synth, 다음 cycle planning |
| `ada-lovelace` | 구현 보조 |

**설계 의도**

- task routing을 명확히 한다.
- review와 implementation을 분리한다.
- 같은 실패가 반복될 때 profile 단위로 원인을 볼 수 있다.
- 역할 설명은 Kanban decomposer의 routing 품질에 영향을 준다.

**시각화 제안**

6개 profile을 lane 형태로 배치하고 cycle task를 연결.

**발표 메모**

multi-agent의 목적은 agent 수를 늘리는 것이 아닙니다. 핵심은 책임과 검증 관점을 분리하는 것입니다. 데이터 audit을 잘하는 관점, 모델을 학습하는 관점, 통계적으로 평가하는 관점, 코드와 leakage를 의심하는 관점은 서로 다릅니다.

예를 들어 `gauss`가 모델을 만들었다면 `turing`은 그 결과를 그대로 신뢰하지 않고 reproducibility, feature provenance, leakage 가능성을 별도로 봅니다. `spearman`은 overall score만 보지 않고 bootstrap CI, macro-QWK, worst-band QWK처럼 평가 기준을 따로 확인합니다. `aristotle`은 개별 산출물을 종합해 다음 cycle에 어떤 권고를 주입할지 판단합니다.

이 역할 분리는 감사 가능성에도 도움이 됩니다. 문제가 반복되면 어느 profile의 task에서 반복되는지 추적할 수 있고, routing 자체가 잘못됐는지도 확인할 수 있습니다.

---

## 8. 추적 가능성 설계

### 모든 작업은 나중에 재구성 가능해야 한다

**본문**

각 task는 다음 정보를 남겨야 한다.

- `task_id`
- `cycle_id`
- parent task
- workspace artifact path
- run attempt/comment history
- config hash
- seed
- verification command
- block reason

학습 task는 추가로 MLflow run id와 `cycle_id`, `kanban_task_id`, `feature_provenance` tag를 남긴다.

**예시**

```text
cycle_id=M1
kanban_task_id=t_dcecd4b1
workspace/cycle_M1/models/model_training_summary.md
mlflow experiment=cycle_M1
feature_provenance_label_side_count=0
```

**시각화 제안**

Task card → run/comment → workspace manifest → MLflow run(학습 task) → report로 이어지는 trace graph.

**발표 메모**

추적 가능성이 없으면 장기 자율성은 위험합니다. agent가 빠르게 많은 작업을 수행해도, seed, config, input artifact, output artifact, 검증 명령이 남아 있지 않으면 그 결과는 연구 evidence가 되기 어렵습니다.

이 프로젝트에서는 task id와 cycle id를 중심축으로 둡니다. 학습 task라면 MLflow run에도 `cycle_id`, `kanban_task_id`, `feature_provenance` tag가 남아야 합니다. 파일 산출물은 workspace 경로로 남고, block reason은 comment와 manifest로 남습니다. 이렇게 해야 task, 파일, 실험 run, report가 서로 연결됩니다.

발표에서는 이 슬라이드를 “나중에 다시 설명 가능한가”라는 질문으로 설명하면 좋습니다. 자율 agent 연구에서 가장 큰 리스크는 agent가 뭔가 했는데 사람이 검증할 수 없는 상태입니다. Hermes의 추적성 설계는 그 리스크를 줄이는 장치입니다.

---

## 9. 통제 가능성 설계

### 자율성은 Hard Rule 안에서만 허용한다

**본문**

핵심 Hard Rules:

- test set leakage 금지
- 학생 직접 식별자 모델 입력, prompt, log, artifact 잔존 금지
- 학습 실험 MLflow 등록
- feature provenance 필수
- HPO trial 수 기준
- score-band fairness gate
- cost circuit breaker
- silent failure 금지

**중요한 원칙**

> Agent가 실패를 숨기면 안 된다. 실패는 block artifact로 남겨야 한다.

**시각화 제안**

Pipeline 위에 guardrail 레이어를 겹쳐 표시.

**발표 메모**

자율성을 높이려면 먼저 경계를 명확히 해야 합니다. 이 프로젝트에서는 AGENTS.md가 운영 헌법 역할을 합니다. 무엇을 해도 되는지보다 무엇을 하면 안 되는지가 먼저 정의되어야 agent가 장시간 실행될 수 있습니다.

예를 들어 test leakage 금지, feature provenance 필수, score-band fairness gate, cost circuit breaker는 단순 권고가 아니라 hard block 조건입니다. agent가 성능을 올리기 위해 label-side feature를 쓰거나, majority band만 잘 맞추는 모델을 acceptance로 올리면 안 됩니다.

Phase 2에서는 PII 외부 전송 gate가 인간 결정으로 제거되었지만, 직접 식별자와 secret을 feature, prompt, log, artifact에 남기지 않는 경계는 유지됩니다. 즉, gate 하나가 제거됐다고 해서 통제가 사라진 것이 아니라, 프로젝트 상태에 맞게 통제 지점이 재정렬된 것입니다.

---

## 10. 자기진화 메커니즘

### SYNTH가 다음 cycle을 만들고 DECIDE가 시작을 승인한다

**본문**

SYNTH의 책임:

- cycle 산출물 종합
- judgement 산출
- 다음 cycle 권고 작성
- 다음 cycle task graph 등록
- 이전 cycle의 구체적 개선안을 다음 task body에 주입

DECIDE의 책임:

- `[Continue]`: 다음 cycle 진행
- `[Phase-up]`: 더 큰 phase 전환 검토
- `[Stop]`: 현재 phase 종료

**핵심**

SYNTH는 다음 cycle 후보 task를 만들 수 있지만, 실행 시작과 policy 변경은 DECIDE 또는 별도 인간 gate 뒤에서만 진행된다. 후보 task는 blocked/todo 상태로 등록되고, parent dependency가 열릴 때만 실행된다.

**시각화 제안**

목표 패턴으로 `SYNTH-M1 -> DECIDE-M1 -> AUDIT-M2` dependency graph를 표시. 실제 진행 상태와 설계 패턴을 구분해서 표기.

**발표 메모**

이 구조가 “script-free self-sustaining loop”입니다. 여기서 script-free는 외부 cron이나 별도 자동화 스크립트가 cycle을 몰래 진행하지 않는다는 뜻입니다. 다음 cycle task는 SYNTH 단계에서 명시적으로 생성되고, 그 task들은 DECIDE가 열리기 전까지 blocked 상태로 남습니다.

핵심은 권고가 자연어 요약으로 끝나지 않는다는 점입니다. SYNTH는 다음 cycle에서 실제로 써야 할 인자와 명령, 예를 들어 split 기준, HPO trial 수, fairness metric, 재시도 조건을 task body에 주입해야 합니다. 그래야 다음 cycle agent가 이전 cycle의 배움을 잃지 않습니다.

사람의 역할은 모든 세부 작업을 승인하는 것이 아니라, 다음 cycle을 계속할지, phase를 올릴지, 멈출지를 판단하는 것입니다. 이 방식은 자율성을 유지하면서도 최종 방향 결정권을 사람에게 남깁니다.

---

## 11. Running Example: AI 자동채점 연구

### 한국어 K-12 에세이 자동채점 모델 연구

**본문**

목표:

- 한국어 K-12 에세이 자동채점 모델 품질 검증
- Phase 1 toy workflow 검증
- Phase 2 mid-scale 실모델 검증
- 모델 자체보다 audit-split-model-eval-review가 필요한 장기 연구 workflow 검증

데이터:

- AI Hub 한국어 K-12 에세이
- Phase 1: toy sample 342건
- Phase 2: stratified sample 5,003건

모델:

- M1 dummy
- M2 length
- M3 TF-IDF + Ridge
- M4 LightGBM
- M5 KLUE-RoBERTa (pending/retry target)
- M6 ensemble (pending)

**시각화 제안**

자동채점 연구의 데이터-모델-평가 흐름을 간단히 도식화하되, 각 단계 아래에 대응되는 Kanban task를 붙인다.

**발표 메모**

자동채점은 예시입니다. 하지만 좋은 예시인 이유가 있습니다. 한국어 K-12 에세이 자동채점은 데이터 구조, 평가 기준, 모델 진화, leakage 리스크, human ceiling, score-band 불균형이 모두 존재하는 도메인입니다. 단순 데모보다 실제 연구 workflow의 복잡성을 더 잘 드러냅니다.

Phase 1에서는 toy sample로 Hermes cycle 자체가 동작하는지 확인했고, Phase 2에서는 5,003건 mid-scale sample과 KLUE-RoBERTa, Optuna HPO, remote GPU까지 포함하는 실모델 검증으로 확장했습니다. 이 과정에서 M1~M4 CPU baseline은 완료됐고, M5/M6는 remote GPU 재시도 대상으로 남아 있습니다.

이 슬라이드의 목적은 모델 리스트를 자랑하는 것이 아닙니다. 하나의 실제 연구가 AUDIT, SPLIT, FEATURE, MODEL, HPO, EVAL, REVIEW, SYNTH, DECIDE라는 workflow로 얼마나 자연스럽게 분해되는지 보여주는 것입니다.

---

## 12. 자동채점 Cycle 상세

### ML 연구 workflow를 Kanban task로 매핑

**본문**

| 연구 단계 | Kanban task | 산출물 |
|---|---|---|
| 데이터 확인 | AUDIT | audit report, manifest |
| split | SPLIT | fold manifest, leakage check |
| feature | FEATURE | feature matrix, provenance |
| 학습 | MODEL | model artifacts, MLflow runs |
| HPO | HPO | Optuna study, best params |
| 평가 | EVAL | metrics, CI, fairness |
| 검토 | REVIEW | review report |
| 종합 | SYNTH | cycle report, next tasks |
| 인간 결정 | DECIDE | continue/phase-up/stop decision |

**시각화 제안**

표와 함께 각 산출물 path 예시를 작은 monospace label로 표시.

**발표 메모**

이 표는 ML 연구의 일반 단계를 Hermes task로 매핑한 것입니다. 중요한 점은 각 단계가 말로만 끝나지 않고 산출물과 검증 명령을 남긴다는 점입니다. AUDIT은 manifest와 data report를 남기고, SPLIT은 fold manifest와 leakage check를 남기며, MODEL은 model artifact와 MLflow run을 남깁니다.

EVAL과 REVIEW를 분리한 것도 중요합니다. EVAL은 metric과 confidence interval을 보는 단계이고, REVIEW는 코드, 누수, 재현성, trial 수 같은 구조적 리스크를 보는 단계입니다. 두 관점이 모두 통과해야 SYNTH가 cycle report를 만들 수 있습니다.

마지막 DECIDE는 단순 승인 버튼이 아닙니다. 사람이 다음 cycle을 계속할지, phase-up으로 갈지, 중단할지를 결정하는 연구 운영 gate입니다. 이 gate가 있어야 agent가 자율적으로 일해도 전체 방향은 사람이 통제할 수 있습니다.

---

## 13. 모델 진화 Ladder

### 단순한 모델에서 복잡한 모델로 올라간다

**본문**

```text
M1 dummy
  -> M2 length
  -> M3 TF-IDF + Ridge
  -> M4 LightGBM
  -> M5 KLUE-RoBERTa (pending/retry target)
  -> M6 M4+M5 ensemble (pending)
```

**왜 ladder가 필요한가**

- 성능 개선이 실제 signal인지 확인한다.
- 복잡한 모델이 단순 baseline보다 나은지 검증한다.
- 실패 시 어느 단계에서 문제가 생겼는지 분리한다.
- HPO와 transformer는 baseline이 안정화된 후 붙인다.
- 현재 evidence는 M1~M4 CPU baseline까지이며, M5/M6는 remote GPU 운영 해소 후 retry 대상이다.

**Cycle M1 CPU baseline point-estimate 예시**

| Model | QWK |
|---|---:|
| M1 | -0.0485 |
| M2 | 0.0913 |
| M3 | 0.1982 |
| M4 | 0.2635 |

주의:

- 위 QWK는 workflow trace용 point estimate다.
- 최종 acceptance metric은 아니다.
- 수용 판단은 EVAL 단계의 bootstrap CI, macro-QWK, worst-band QWK, per-band metric을 함께 본다.

**시각화 제안**

계단형 ladder 또는 line chart. 차트 옆에는 “diagnostic, not acceptance” annotation을 둔다.

**발표 메모**

복잡한 모델을 바로 학습하지 않고 ladder를 두는 이유는, 성능 경쟁보다 연구 구조의 검증이 먼저이기 때문입니다. dummy, length, TF-IDF, LightGBM을 거치면 각 단계에서 성능이 왜 개선되는지, 어떤 feature가 signal을 만드는지, 어느 지점에서 문제가 생기는지 분리해서 볼 수 있습니다.

현재 M1~M4 CPU baseline에서는 QWK가 단계적으로 개선되는 point estimate가 나왔습니다. 다만 이것은 acceptance metric이 아니라 workflow trace용 진단 값입니다. 최종 수용 판단은 EVAL 단계에서 bootstrap CI, macro-QWK, worst-band QWK, per-band metric, human ceiling 비교까지 함께 봐야 합니다.

M5 KLUE-RoBERTa와 M6 ensemble은 아직 pending/retry target으로 표현해야 합니다. 이 표현이 중요합니다. 발표에서 완료되지 않은 모델을 완료된 것처럼 말하면 workflow의 추적 가능성 메시지와 충돌합니다. 현재 evidence는 CPU baseline과 M5 block recovery traceability까지입니다.

---

## 14. 실제 Trace 예시

### 하나의 block도 추적 가능한 연구 산출물이다

**본문**

예시 task:

```text
t_dcecd4b1
T-CYCLE-M1-MODEL: M1~M5 baseline 학습
assignee: gauss
M1~M4: completed
M5: environment block / retry target
```

연결된 artifact:

- `workspace/cycle_M1/models/model_training_summary.md`
- `workspace/cycle_M1/models/manifest.json`
- `workspace/cycle_M1/models/M5_BLOCKED_ENVIRONMENT.md`
- `workspace/cycle_M1/models/M5_env_block_manifest.json`

남은 상태:

- M1~M4 완료
- M5 KLUE-RoBERTa 미실행
- 당시 downstream HPO/EVAL/REVIEW/SYNTH 대기
- 네트워크/remote GPU 권한 정비 후 unblock/retry 가능

**시각화 제안**

실제 Kanban card 스크린샷 + 오른쪽에 artifact tree. 가능하면 5장 근처에도 작은 board screenshot을 재사용해 시스템 실체를 일찍 보여준다.

**발표 메모**

여기서 중요한 것은 block 자체가 실패가 아니라, 다음 사람이 이어받을 수 있는 구조화된 상태라는 점입니다. M5가 멈췄다는 사실보다 더 중요한 것은 왜 멈췄는지, 어떤 artifact가 남았는지, 어떤 권한과 환경이 정비되면 재시도할 수 있는지가 기록됐다는 점입니다.

일반적인 로그 기반 운영에서는 이런 상태가 대화나 터미널 출력에 흩어지기 쉽습니다. Hermes에서는 task id, status, comment, workspace artifact가 연결되므로 다음 agent가 “처음부터 다시 조사”하지 않아도 됩니다. 이 구조가 장기 연구에서 시간을 절약합니다.

발표에서는 “block도 산출물이다”라는 문장을 강조하면 좋습니다. 자율 연구에서 실패를 숨기거나 지나치면 다음 cycle이 같은 실패를 반복합니다. 반대로 실패가 artifact가 되면 recovery의 입력이 됩니다.

---

## 15. 실패 사례 1: Split Recovery

### 데이터 구조가 정책과 맞지 않을 때

**본문**

문제:

- `student.location` 기반 group split 필요
- location group이 sparse하거나 편중됨
- M1 중간 산출에서 k=10, k=5가 valid fold 크기 기준을 위반

Recovery:

- Cycle M1 한정 region 3권역 merge
- k=3 split로 valid_n ≥ 300 확보
- region k=3은 permanent policy가 아니라 recovery evidence로 기록
- 현재 Phase 2 표준 split 정책은 인간 게이트를 거쳐 `student.location` 기반 k=5로 재정렬

**교훈**

- agent가 정책을 임의 변경하면 안 된다.
- 임시 deviation은 명시하고, 영구 반영은 SYNTH + 인간 gate를 거쳐야 한다.
- 발표에서는 “최종 정책”이 아니라 “정책 충돌을 기록한 사례”로 제시해야 한다.

**시각화 제안**

location split 실패 → region merge → k=3 recovery evidence → human gate → current k=5 policy flow.

**발표 메모**

이 사례는 자율 workflow가 “무조건 진행”하지 않고, 정책 충돌을 기록하고 제한된 recovery를 산출물로 남긴 사례입니다. 원래 목표는 `student.location` 기반 group split이었지만, 실제 데이터 분포에서는 일부 fold가 valid_n 기준을 만족하지 못했습니다.

여기서 agent가 임의로 정책을 바꿔 계속 진행하면 위험합니다. split 정책은 leakage와 평가 신뢰성에 직접 영향을 주기 때문입니다. 그래서 M1 한정으로 region 3권역 merge와 k=3 recovery를 evidence로 남기고, 현재 Phase 2 표준 정책은 인간 gate를 거쳐 k=5로 재정렬했습니다.

핵심은 temporary recovery와 permanent policy를 구분하는 것입니다. 임시 우회는 연구를 멈추지 않기 위한 evidence이고, 영구 정책은 SYNTH와 인간 decision을 통해 반영되어야 합니다.

---

## 16. 실패 사례 2: M5 Remote GPU Block

### 과거 환경 제약도 연구 workflow의 evidence가 된다

**본문**

과거 문제:

- M5 KLUE-RoBERTa는 remote GPU 필요
- 당시 worker는 Codex sandbox 위에서 실행
- 당시 기본 sandbox/network 정책이 외부 명령과 DNS 접근을 제한
- elevated execution을 요청할 수 없는 세션에서는 worker가 자체 해결 불가
- 당시 로컬 HuggingFace cache에 `klue/roberta-small` 없음

당시 결과:

- M1~M4는 완료
- M5는 `BLOCKED_SANDBOX_NETWORK_UNAVAILABLE`
- HPO → EVAL → REVIEW → SYNTH가 대기

해소 상태:

- 인간이 승인한 범위에서 Codex sandbox/network 정책을 조정해 remote GPU 접근 가능
- API key 로그 노출 금지, 인스턴스 teardown, 비용 circuit breaker, artifact redaction 확인
- task unblock 후 M5 재시도 가능

**시각화 제안**

원인 체인 diagram: worker → sandbox/network policy → remote GPU unavailable → M5 block → downstream wait → policy fix → retry ready. 옆에는 “model failure가 아니라 operating control event” label을 둔다.

**발표 메모**

중요한 점은 block 원인이 모델 코드가 아니라 실행 환경이었다는 것입니다. M5 KLUE-RoBERTa 자체가 실패한 것이 아니라, 당시 worker가 sandbox/network 제약 안에서 remote GPU 명령과 모델 캐시 접근을 수행할 수 없었습니다.

이 차이를 정확히 기록하는 것이 중요합니다. 모델 실패라면 코드, hyperparameter, 데이터, loss를 봐야 합니다. 환경 실패라면 권한, 네트워크, credential, cache, 비용, 인스턴스 lifecycle을 봐야 합니다. 원인 분류가 틀리면 다음 agent가 엉뚱한 곳을 고치게 됩니다.

현재는 인간 승인 범위에서 sandbox/network 정책이 조정되어 retry 가능 상태로 정리됐습니다. 다만 remote GPU는 성능 검증의 수단인 동시에 credential, 비용, provider trust, artifact 반출 리스크를 동반합니다. 그래서 unblock 이후에도 비용 circuit breaker와 로그 redaction, teardown 확인은 별도 운영 gate로 남겨야 합니다.

---

## 17. 평가와 품질 Gate

### overall metric만 보면 안 된다

**본문**

자동채점 연구의 평가 항목:

- Overall RMSE / MAE / QWK
- Type별 metric
- 학년군별 metric
- Score-band별 metric
  - `low_0_9`
  - `mid_10_19`
  - `high_20_30`
- Macro-QWK
- Worst-band QWK
- Bootstrap CI 95%
- Human ceiling comparison

Hard Rule #14:

```text
worst_band_qwk < macro_qwk * 0.7
```

이면 acceptance hard-block.

low band가 `N < 10`이면 QWK/CI를 `SKIP_UNSTABLE`로 표시하고, acceptance는 mid/high의 worst-band와 macro-QWK 기준으로 판단한다.

**필수 문구**

> 본 데이터셋은 high score band에 90% 이상 집중되어 있으므로, overall metric은 실제 변별력을 과대평가할 수 있다. 따라서 모델 수용 여부는 overall metric뿐 아니라 macro-QWK, worst-band QWK, per-band metric을 함께 기준으로 판단한다.

**시각화 제안**

score-band 분포 막대 + overall QWK와 macro/worst-band QWK가 다르게 보이는 예시 chart.

**발표 메모**

자율 연구에서 평가 기준이 약하면 agent는 쉬운 metric만 최적화합니다. 자동채점 데이터는 high score band가 90% 이상을 차지하기 때문에 overall metric만 보면 모델이 실제보다 좋아 보일 수 있습니다. 다수 band를 잘 맞추는 것과 전체 점수 범위를 공정하게 변별하는 것은 다른 문제입니다.

그래서 이 프로젝트는 overall RMSE, MAE, QWK뿐 아니라 score-band별 metric, macro-QWK, worst-band QWK를 함께 봅니다. 특히 worst-band QWK가 macro-QWK의 70% 미만이면 acceptance hard-block으로 둡니다. 이는 agent가 majority band에만 최적화되는 것을 막기 위한 장치입니다.

또 하나 중요한 점은 low band 표본이 너무 적을 때 억지로 metric을 계산하지 않는다는 것입니다. N<10이면 `SKIP_UNSTABLE`로 표시하고 qualitative risk를 보고합니다. 좋은 평가 시스템은 숫자를 많이 내는 것이 아니라, 믿을 수 없는 숫자를 믿지 않는 것입니다.

---

## 18. 인간 개입 최소화

### 정상 경로는 DECIDE로 압축하고 예외는 별도 gate로 승격한다

**본문**

사용자 개입 지점:

- `DECIDE-MN`
- 선택지: `[Continue]`, `[Phase-up]`, `[Stop]`
- policy 변경, remote GPU 운영, 비용 초과, 보안/누수 block은 별도 인간 gate

Agent가 하는 일:

- 단계별 실행
- 산출물 저장
- 실패 기록
- review 수행
- cycle report 작성
- 다음 cycle task 등록

인간이 하는 일:

- 다음 cycle을 계속할지 판단
- phase를 올릴지 판단
- 멈출지 판단
- hard rule/policy 변경 승인
- remote GPU/credential/cost risk 승인

**시각화 제안**

24시간 timeline에서 대부분은 auto, 정상 gate는 DECIDE marker, 예외는 block/escalation marker로 표시.

**발표 메모**

완전 자동화가 목표가 아닙니다. 인간 개입을 없애는 것이 아니라, 인간이 개입해야 할 지점을 줄이고 선명하게 만드는 것이 목표입니다. 사람이 모든 task를 승인하면 workflow는 느려지고, 반대로 아무 gate도 없으면 위험한 정책 변경이 자동으로 진행될 수 있습니다.

Hermes에서는 정상 경로를 DECIDE로 압축합니다. cycle이 끝나면 사람은 Continue, Phase-up, Stop 중 하나를 선택합니다. 반면 policy 변경, remote GPU 운영, 비용 초과, 보안/누수 block 같은 예외는 별도 인간 gate로 승격됩니다.

이 구조는 연구자의 시간을 줄이면서도 책임 경계를 유지합니다. agent는 실행과 기록을 맡고, 사람은 방향 결정과 위험 승인에 집중합니다. 결국 좋은 자율 workflow는 사람을 없애는 시스템이 아니라, 사람이 판단해야 할 문제만 남기는 시스템입니다.

---

## 19. 배운 점

### Agent 자율성보다 중요한 것은 boundary, evidence, recovery다

**본문**

배운 점 3가지:

- Boundary: hard rule, privacy, cost, remote GPU operation 경계를 먼저 정해야 한다.
- Evidence: task body, comment, run, manifest, MLflow가 나중에 상태를 복원하게 한다.
- Recovery: 실패를 block artifact로 남겨야 다음 agent가 같은 실패를 반복하지 않는다.

**핵심 문장**

> 자율 연구의 품질은 agent의 지능보다, 실패를 기록하고 이어받게 만드는 시스템 설계에 더 크게 좌우된다.

**시각화 제안**

Boundary, Evidence, Recovery 3개 pillar로 배치. 세부 항목은 발표 메모로 이동.

**발표 메모**

이 슬라이드는 기술 세미나의 결론부입니다. “무엇이 잘됐나”보다 “운영하면서 무엇이 중요하다고 확인됐나”를 강조합니다. 실제로 장기 agent 연구에서 가장 중요한 것은 agent가 얼마나 똑똑한가보다, 실패했을 때 상태를 잃지 않는 시스템입니다.

Boundary는 agent가 넘지 말아야 할 선입니다. Evidence는 나중에 사람이 다시 설명할 수 있는 근거입니다. Recovery는 실패를 다음 시도의 입력으로 바꾸는 구조입니다. 이 세 가지가 없으면 agent는 빠르게 움직일 수는 있지만, 연구 품질을 보장하기 어렵습니다.

발표에서는 여기서 메시지를 단순하게 정리합니다. 자율 연구의 품질은 모델 하나의 성능이나 agent 하나의 추론력보다, 실패와 판단을 어떻게 기록하고 이어받게 만드는지에 더 크게 좌우됩니다.

---

## 20. 결론과 다음 단계

### 자율 연구는 agent가 아니라 workflow system이다

**본문**

결론:

- Hermes Kanban은 long-running research를 task graph로 운영하게 한다.
- profile 기반 agent는 역할별 책임을 가진 worker로 동작한다.
- MLflow/workspace/manifest/comment/run이 추적 가능성을 만든다.
- block과 DECIDE가 통제 가능성을 만든다.
- 자동채점 연구는 audit-split-feature-CPU baseline-M5 block recovery traceability까지 실제 ML workflow에 적용 가능한 초기 evidence를 제공했다.

다음 단계:

- M5 KLUE-RoBERTa remote GPU 재시도 및 학습 완료
- HPO → EVAL → REVIEW → SYNTH 완주
- Cycle M2 자동 등록과 개선 권고 inheritance 검증
- skill library 축적과 다른 연구 도메인 확장성 검증

다른 팀이 가져갈 운영 원칙:

- task graph 없이는 장기 agent 연구를 운영하지 않는다.
- block을 실패가 아니라 재개 가능한 evidence로 만든다.
- 인간 gate는 없애지 말고 가장 위험한 결정 지점에 배치한다.

**마지막 메시지**

> 24시간 자율 연구의 핵심은 “계속 실행되는 agent”가 아니라, “멈췄을 때도 사람이 이해하고 다시 시작할 수 있는 연구 시스템”이다.

**시각화 제안**

Cycle loop가 다음 cycle로 이어지는 closing diagram.

**발표 메모**

마지막은 과장 없이 정리합니다. 이 시스템은 아직 full mid-scale end-to-end 검증 전입니다. M5 KLUE-RoBERTa 학습, HPO, EVAL, REVIEW, SYNTH 완주와 Cycle M2 inheritance 검증이 다음 단계로 남아 있습니다.

그럼에도 지금까지의 evidence는 의미가 있습니다. Hermes Kanban은 장기 연구를 task graph로 만들 수 있고, profile 기반 agent가 역할별로 수행할 수 있으며, MLflow와 workspace artifact로 추적 가능성을 만들 수 있음을 보여줬습니다. 또한 split recovery와 M5 remote GPU block처럼 실패한 상태도 연구 자산으로 남길 수 있었습니다.

다른 팀이 가져갈 핵심 원칙은 단순합니다. 장기 agent 연구를 운영하려면 먼저 task graph를 만들고, block을 재개 가능한 evidence로 남기며, 인간 gate를 없애지 말고 위험한 결정 지점에 배치해야 합니다. 24시간 자율 연구의 핵심은 계속 실행되는 agent가 아니라, 멈췄을 때도 사람이 이해하고 다시 시작할 수 있는 연구 시스템입니다.

---

## 부록 후보

20페이지 본문 이후 질의응답용으로 준비할 수 있는 부록입니다.

### A. 실제 Hermes CLI 명령

```bash
hermes kanban boards list
hermes kanban stats
hermes kanban list --sort created
hermes kanban show <task_id>
hermes kanban runs <task_id>
hermes kanban context <task_id>
```

### B. 실제 artifact 예시

- `workspace/cycle_M1/models/model_training_summary.md`
- `workspace/cycle_M1/models/M5_BLOCKED_ENVIRONMENT.md`
- `workspace/cycle_M1/features/feature_provenance_manifest.json`
- `workspace/cycle_M1/splits/split_manifest.yaml`

### C. 발표 전 확인할 source-of-truth

- 현재 board task status와 M5 retry 여부
- split 정책: M1 recovery evidence와 현재 k=5 표준 정책 구분
- M5 block enum과 최신 artifact 내용
- EVAL 완료 전 성능 수치는 point estimate로만 표기

### D. 시스템 확장 가능 도메인

- 장기 benchmark 운영
- 논문 survey + reproduction workflow
- 데이터셋 구축/정제 pipeline
- 모델 후보군 자동 비교
- 지속적 error analysis
- human review가 필요한 규제/교육/의료 ML 연구

도메인 확장은 가능성 수준이며, 각 도메인별 데이터 거버넌스와 인간 승인 gate를 새로 정의해야 한다.
