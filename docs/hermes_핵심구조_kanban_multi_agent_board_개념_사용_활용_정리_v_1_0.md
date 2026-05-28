# Hermes 핵심 구조 및 Kanban Multi-Agent Board 개념·사용·활용 정리

문서 버전: v1.0
작성일: 2026-05-27
문서명: Hermes_핵심구조_Kanban_Multi_Agent_Board_개념_사용_활용_정리_v1_0.md
대상 도구: Hermes Agent
주제: Hermes 핵심 구조, Profile, Skill, Cron, Gateway, Kanban Multi-Agent Board, 장기 실행형 협업 활용

---

## 1. 문서 목적

본 문서는 Hermes Agent의 최신 핵심 구조와 Kanban Multi-Agent Board의 개념, 사용 방식, 실무 활용 방안을 정리한다.

특히 다음 질문에 답하는 것을 목적으로 한다.

1. Hermes Agent는 어떤 구조의 에이전트인가?
2. Profile은 무엇이고 왜 중요한가?
3. Kanban Multi-Agent Board는 무엇인가?
4. Durable Work Queue와 Fire-and-Forget은 어떤 의미인가?
5. Hermes Kanban은 프로젝트 단위로 어떻게 운영할 수 있는가?
6. Master와 팀원 프로파일을 구성하여 장기 실행형 프로젝트를 운영할 수 있는가?
7. 실무 적용 시 어떤 주의사항이 필요한가?

---

## 2. Hermes Agent 개요

Hermes Agent는 Nous Research가 공개한 자기 개선형 AI 에이전트이다. 단순 채팅형 CLI가 아니라, 장기 메모리, 스킬, 도구 실행, 프로파일, 메시징 게이트웨이, 예약 작업, Kanban 기반 다중 에이전트 협업 구조를 포함하는 에이전트 런타임으로 이해하는 것이 적합하다.

Hermes Agent의 핵심 특징은 다음과 같다.

| 항목 | 설명 |
|---|---|
| 자기 개선형 에이전트 | 경험을 바탕으로 스킬과 기억을 축적하고 개선하는 구조 |
| 멀티 프로바이더 | OpenAI 호환 API, 다양한 LLM provider, 로컬 모델 endpoint와 연결 가능 |
| Profile | 역할·설정·메모리·스킬·인증을 분리하는 실행 환경 |
| Skill | 반복 가능한 작업 절차와 노하우를 패키징한 단위 |
| Tool / Toolset | 파일, 터미널, 웹, MCP, 컴퓨터 사용 등 실행 기능 |
| Gateway | Telegram, Discord, Slack 등 외부 채널과 연결 |
| Cron | 예약·반복 작업 실행 |
| Kanban | 여러 프로파일 에이전트가 공유하는 장기 작업 보드 |

---

## 3. Hermes 핵심 구조

Hermes는 다음 구성요소를 중심으로 동작한다.

```text
Hermes Agent
  ├─ Model Provider / API Endpoint
  ├─ Config
  ├─ Profile
  ├─ Memory
  ├─ SOUL.md
  ├─ AGENTS.md
  ├─ Skills
  ├─ Tools / Toolsets
  ├─ Gateway
  ├─ Cron
  └─ Kanban Multi-Agent Board
```

각 구성요소의 역할은 다음과 같다.

| 구성요소 | 역할 |
|---|---|
| Model Provider | 실제 LLM 호출 대상. API provider 또는 로컬 모델 endpoint |
| Config | 모델, 도구, 실행 옵션, endpoint 등 설정 |
| Profile | 독립된 에이전트 실행 환경 |
| Memory | 장기 기억 및 사용자·작업 맥락 저장 |
| SOUL.md | 에이전트의 정체성, 말투, 역할, 기본 행동 원칙 |
| AGENTS.md | 프로젝트별 개발 규칙, 명령어, 파일 구조, 작업 방식 |
| Skills | 반복 가능한 절차, 도구 사용 방식, 업무 루틴 |
| Tools | 파일 조작, 명령 실행, 검색, MCP, 컴퓨터 제어 등 |
| Gateway | 외부 메시징 플랫폼 연결 |
| Cron | 예약된 작업 실행 |
| Kanban | 여러 에이전트가 공유하는 durable task board |

---

## 4. Profile 개념

Hermes에서 Profile은 단순한 사용자 이름이 아니라, 독립된 에이전트 실행 환경이다.

Profile은 다음을 분리한다.

| 항목 | 설명 |
|---|---|
| config.yaml | 모델, 도구, 실행 설정 |
| .env | API key, token 등 비밀값 |
| SOUL.md | 에이전트 역할과 성격 |
| MEMORY.md | 장기 기억 |
| sessions | 대화 및 작업 세션 |
| skills | 역할별 스킬 |
| gateway state | 메시징 게이트웨이 상태 |
| cron jobs | 예약 작업 |

즉, Profile은 다음처럼 이해할 수 있다.

```text
Profile = 별도의 Hermes 작업 환경
        = 별도의 설정 + 메모리 + 성격 + 스킬 + 인증 + 세션
```

---

## 5. Profile과 역할 분리

소프트웨어 개발 또는 연구 프로젝트에서는 Profile을 역할 단위로 나누는 것이 적합하다.

예시는 다음과 같다.

| Profile | 역할 |
|---|---|
| master | 전체 목표 관리, 작업 배정, 상태 점검 |
| planner | 요구사항 분해, 작업 계획, 수용 기준 작성 |
| architect | 구조 설계, 모듈 경계, 기술 리스크 검토 |
| dev | 구현, 테스트 작성, 변경 요약 |
| reviewer | 코드 리뷰, 품질 점검, 수정 요청 |
| qa | 테스트 시나리오, 회귀 검증, 수용 기준 확인 |
| reporter | 진행 리포트, 성능 리포트, 의사결정 요약 |

프로파일 생성 예시는 다음과 같다.

```bash
hermes profile create master --clone
hermes profile create planner --clone
hermes profile create architect --clone
hermes profile create dev --clone
hermes profile create reviewer --clone
hermes profile create qa --clone
```

각 Profile에는 `--description`을 붙여 역할을 명확히 하는 것이 좋다.

```bash
hermes profile create reviewer \
  --description "Reviews pull requests for correctness, maintainability, security, performance, and test coverage."
```

---

## 6. SOUL.md와 AGENTS.md의 차이

Hermes 운영에서 `SOUL.md`와 `AGENTS.md`는 역할이 다르다.

| 파일 | 범위 | 역할 |
|---|---|---|
| SOUL.md | Profile 단위 | 에이전트의 정체성, 말투, 역할, 판단 기준 |
| AGENTS.md | Project 단위 | 프로젝트 규칙, 개발 명령, 파일 구조, 완료 기준 |

예를 들어 `reviewer` 프로파일의 `SOUL.md`는 리뷰어로서의 역할을 정의한다. 반면 프로젝트 루트의 `AGENTS.md`는 해당 저장소에서 따라야 할 공통 개발 규칙을 정의한다.

정리하면 다음과 같다.

```text
SOUL.md = 이 에이전트는 누구인가?
AGENTS.md = 이 프로젝트에서는 어떻게 일해야 하는가?
```

---

## 7. Skill 개념

Skill은 Hermes가 반복 가능한 작업 절차를 저장하고 재사용하기 위한 단위이다.

예를 들어 다음과 같은 Skill을 만들 수 있다.

| Skill | 설명 |
|---|---|
| issue-breakdown | 요구사항을 GitHub issue 단위로 분해 |
| pr-review | PR 변경사항 리뷰 |
| test-checklist | 테스트 체크리스트 작성 |
| data-audit | 데이터셋 품질 점검 |
| experiment-report | 실험 결과 리포트 생성 |
| kanban-worker | Kanban task를 읽고 수행하는 worker 절차 |

Skill은 단순한 프롬프트가 아니라, 반복 가능한 작업 방식과 도구 사용 절차를 포함하는 운영 지식으로 볼 수 있다.

---

## 8. Gateway 개념

Gateway는 Hermes를 외부 메시징 플랫폼과 연결하는 기능이다.

예를 들어 다음과 같은 채널과 연결할 수 있다.

```text
Telegram
Discord
Slack
WhatsApp
Signal
Email
LINE
SimpleX
```

실무적으로 Gateway는 다음 용도로 활용된다.

1. 작업 진행 알림
2. 실패 또는 blocked 상태 알림
3. 일일 리포트 전송
4. 사람이 승인해야 하는 항목 전달
5. 장기 실행 작업 상태 확인

단, Profile별 Gateway 상태와 token이 분리될 수 있으므로, 운영 시 어떤 Profile의 Gateway가 실행 중인지 명확히 관리해야 한다.

---

## 9. Cron 개념

Cron은 Hermes에서 예약 작업을 실행하는 기능이다.

활용 예시는 다음과 같다.

| 예약 작업 | 설명 |
|---|---|
| 매일 오전 9시 상태 점검 | Kanban board, blocked task, stale task 확인 |
| 매시간 실험 상태 확인 | 장기 학습 job, HPO 진행 상태 점검 |
| 매일 리포트 생성 | 성능 지표, 완료 작업, 다음 작업 요약 |
| 매주 회고 생성 | 완료된 실험, 실패 원인, 다음 개선 방향 정리 |

예시 개념은 다음과 같다.

```bash
hermes cron create "every day at 09:00" \
  "Check the kanban board, summarize blocked tasks, stale tasks, failed tests, and next actions."
```

실제 명령 옵션은 Hermes 설치 버전에 따라 다를 수 있으므로 `hermes cron --help`로 확인해야 한다.

---

## 10. Kanban Multi-Agent Board 개념

Hermes Kanban Multi-Agent Board는 여러 Hermes Profile이 공유하는 durable task board이다.

핵심 개념은 다음과 같다.

```text
Kanban Board = 여러 프로파일 에이전트가 공유하는 작업 보드
Task = 수행할 작업 단위
Assignee = 작업을 맡을 Profile
Handoff = 에이전트 간 작업 인계 기록
Comment = 사람 또는 에이전트가 남기는 작업 메모
Dependency = 작업 간 선후 관계
Worker = 실제 작업을 수행하는 Profile 프로세스
```

Hermes Kanban은 단순 To-do 목록이 아니라, 장기 실행형 다중 에이전트 협업을 위한 durable work queue이다.

---

## 11. Durable Work Queue 의미

Durable Work Queue는 작업이 사라지지 않도록 영속 저장되는 작업 대기열을 의미한다.

```text
Durable = 장애 후에도 보존되는
Work = 처리해야 할 작업
Queue = 대기열
```

따라서 Durable Work Queue는 다음 의미이다.

```text
작업을 큐에 넣으면 메모리에서만 존재하는 것이 아니라
DB 또는 파일에 저장되어 서버 재시작, 프로세스 종료, 에이전트 실패 후에도 남는 구조
```

Hermes Kanban에서는 task가 SQLite 기반 DB에 row로 남기 때문에, 작업이 장기적으로 보존되고 나중에 다시 확인하거나 재시도할 수 있다.

---

## 12. Fire-and-Forget 의미

Fire-and-Forget은 작업을 등록하고 결과를 기다리지 않는 비동기 실행 방식을 의미한다.

```text
Fire = 실행 요청을 보낸다
Forget = 결과가 끝날 때까지 기다리지 않는다
```

예시는 다음과 같다.

```text
master profile이 backend profile에게 작업을 배정한다.
작업은 Kanban board에 저장된다.
master는 backend가 끝날 때까지 기다리지 않고 다른 일을 계속한다.
backend profile은 나중에 작업을 확인하고 처리한다.
```

이 구조는 장기 실행형 프로젝트에 유리하다. 다만 작업 상태, 실패 기록, 재시도 정책, 중복 방지, 모니터링이 반드시 필요하다.

---

## 13. delegate_task와 Kanban의 차이

Hermes 문맥에서 `delegate_task`와 Kanban은 다르다.

| 구분 | delegate_task | Kanban Multi-Agent Board |
|---|---|---|
| 성격 | 일회성 하위 작업 호출 | durable work queue |
| 실행 방식 | 부모가 자식 결과를 기다리는 방식에 가까움 | fire-and-forget 가능 |
| 작업자 | 임시 subagent | 이름 있는 Profile |
| 지속성 | 약함 | 강함 |
| 이력 | 제한적 | task, handoff, comment로 남음 |
| 실패 처리 | 제한적 | blocked, retry, rerun 가능 |
| 장기 실행 | 부적합 | 적합 |
| 사람 개입 | 제한적 | comment, unblock, review 가능 |

정리하면 다음과 같다.

```text
delegate_task = 짧은 보조 작업에 적합
Kanban = 장기 실행, 역할 분리, 협업 이력, 재시도, 사람 개입이 필요한 작업에 적합
```

---

## 14. Kanban Task 상태 흐름

일반적인 상태 흐름은 다음과 같다.

```text
triage → todo → ready → running → done
```

문제가 있으면 다음 상태를 사용한다.

```text
running → blocked
blocked → ready
```

상태별 의미는 다음과 같다.

| 상태 | 의미 |
|---|---|
| triage | 검토 전 작업 후보 |
| todo | 실행 예정이지만 아직 준비되지 않은 작업 |
| ready | 실행 가능한 작업 |
| running | worker profile이 처리 중인 작업 |
| blocked | 진행 불가. 데이터, 승인, 설정, 오류 등 필요 |
| done | 완료된 작업 |
| archived | 종료 또는 폐기된 작업 |

실무에서는 승인 전 작업을 바로 `ready`에 넣지 않고 `triage` 또는 `todo`에 두는 것이 안전하다.

---

## 15. Kanban Board와 프로젝트 단위 관리

Hermes Kanban은 프로젝트 단위로 board를 나누어 관리하는 것이 적합하다.

개념은 다음과 같다.

```text
Profile = 역할 단위
Board = 프로젝트 / 저장소 / 업무 도메인 단위
Task = 실제 작업 단위
```

예시는 다음과 같다.

```text
board: essay-auto-scoring-research
  profiles:
    research-master
    data-auditor
    modeler
    evaluator
    error-analyst

board: exam-system
  profiles:
    master
    planner
    architect
    backend
    frontend
    reviewer
    qa
```

Board 생성 예시는 다음과 같다.

```bash
hermes kanban boards create essay-auto-scoring-research
hermes kanban boards create exam-system
hermes kanban boards create search-engine
```

Board를 지정해 작업을 조회하거나 생성할 수 있다.

```bash
hermes kanban --board essay-auto-scoring-research list

hermes kanban --board essay-auto-scoring-research create \
  "데이터셋 구조 분석" \
  --assignee data-auditor
```

실제 옵션 위치와 명령 형식은 버전별로 차이가 있을 수 있으므로 `hermes kanban --help`로 확인해야 한다.

---

## 16. Master + 팀원 구성 방식

장기 실행 프로젝트에서는 Master Profile과 팀원 Profile을 분리한다.

```text
사용자 / 팀장
   ↓
master profile
   ↓
Kanban Board
   ↓
planner / architect / dev / qa / reviewer / reporter
   ↓
작업 수행
   ↓
master가 상태 확인 및 다음 작업 생성
```

Master Profile의 책임은 다음과 같다.

1. 프로젝트 목표 관리
2. 작업 분해
3. Kanban task 생성
4. 담당 Profile 배정
5. blocked task 확인
6. 완료 판정
7. 다음 작업 생성
8. 사용자 보고

Master Profile이 하지 말아야 할 일은 다음과 같다.

1. 모든 구현을 직접 수행
2. 자기 작업을 직접 승인
3. 테스트 실패를 무시하고 완료 처리
4. 이슈 없이 임의 작업 수행
5. 사람 승인 없이 최종 병합 또는 배포

---

## 17. 개발 프로젝트 활용 예시

소프트웨어 개발 프로젝트에서는 다음 흐름이 적합하다.

```text
요구사항 입력
  ↓
planner: 이슈 분해, 수용 기준 작성
  ↓
architect: 설계 검토, 모듈 경계 정의
  ↓
dev: 구현 및 테스트
  ↓
qa: 검수 시나리오 실행
  ↓
reviewer: PR 리뷰
  ↓
master: 완료 기준 확인
  ↓
사람 승인 후 merge
```

작업 단위는 Kanban Task로 관리하고, 코드 변경 단위는 GitHub Issue/Branch/PR과 연결한다.

```text
Kanban Task = 에이전트 작업 관리
GitHub Issue = 공식 작업 단위
GitHub PR = 코드 변경 검토 단위
AGENTS.md = 프로젝트 공통 규칙
PROJECT_STATUS.md = 장기 상태 기록
```

---

## 18. 연구 프로젝트 활용 예시

AI 모델 연구 프로젝트에서는 다음 흐름이 적합하다.

```text
데이터셋 수령
  ↓
data-auditor: 데이터 및 라벨 품질 분석
  ↓
modeler: 베이스라인 모델 학습
  ↓
evaluator: 성능 측정
  ↓
error-analyst: 오류 원인 분석
  ↓
research-master: 완료/미달 판정
  ↓
미달 시 feature-engineer / hpo-agent / modeler에게 다음 task 생성
  ↓
반복
  ↓
목표 달성 시 reporter가 최종 리포트 생성
```

이 구조는 AI 서술형 자동채점 모델 구축과 같이 장기간 실험과 성능 개선이 필요한 프로젝트에 적합하다.

---

## 19. AI 서술형 자동채점 연구 적용 예시

AI 서술형 자동채점 모델 구축 연구에서는 다음 구성이 적합하다.

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

초기 Kanban Task 예시는 다음과 같다.

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

---

## 20. Kanban과 실험 추적 도구의 역할 분리

Hermes Kanban은 작업 흐름을 관리하는 도구이지, 실험 결과 저장소 자체는 아니다. 따라서 MLflow, DVC, Optuna, Git과 역할을 나누어야 한다.

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
Hermes Kanban = 연구 작업 관리
MLflow / DVC / Optuna = 실험 증거 관리
Report = 의사결정 관리
```

---

## 21. 운영 시 주의사항

Hermes Kanban은 강력하지만 아직 빠르게 발전 중인 기능이므로 다음 주의사항이 필요하다.

### 21.1 Profile별 Kanban DB 경로 이슈

공식 개념상 Kanban은 프로파일 간 공유 보드이지만, 일부 버전이나 설정에서는 profile별 `kanban.db`가 생성되어 작업자가 task를 찾지 못하는 문제가 보고되었다.

운영 전 다음을 확인해야 한다.

```bash
ls ~/.hermes/kanban.db
find ~/.hermes/profiles -name "kanban.db"
hermes kanban list
```

Profile별로 다른 DB를 보고 있으면 cross-profile task dispatch가 실패할 수 있다.

### 21.2 Dispatcher 과부하

Ready task를 너무 많이 넣으면 여러 worker가 동시에 실행되어 LLM gateway, GPU, CPU, 메모리, API quota에 부담을 줄 수 있다.

초기 운영 권장값은 다음과 같다.

```text
초기 병렬 worker 수: 1~2
대량 ready task 투입 금지
running / blocked / done 상태 수시 확인
self-hosted LLM 사용 시 rate limit 또는 batching 필요
```

### 21.3 자동 실행 전 승인 단계 필요

검토되지 않은 task가 바로 `ready` 상태가 되면 원하지 않는 자동 실행이 발생할 수 있다.

권장 규칙은 다음과 같다.

```text
아이디어 작업 = triage
실행 예정 작업 = todo
승인된 작업 = ready
실행 중 작업 = running
```

### 21.4 Dashboard만 의존하지 않기

Dashboard는 편리하지만 profile, board, cron, gateway 상태를 모두 완전하게 통합해서 보여주지 못할 수 있다. 따라서 다음 기록을 병행한다.

```text
Kanban Board
PROJECT_STATUS.md
DECISION_LOG.md
EXPERIMENT_LOG.md
TEST_LOG.md
REVIEW_LOG.md
Gateway logs
Cron last_run_at
```

### 21.5 Profile은 Sandbox가 아님

Profile은 설정과 메모리를 분리하지만 보안 sandbox는 아니다. 로컬 backend에서 실행하는 에이전트는 사용자의 파일 접근 권한을 그대로 가질 수 있다.

중요 프로젝트에서는 다음 방식을 고려한다.

```text
Docker container 분리
프로파일당 컨테이너 1개
작업 디렉터리 제한
민감정보 .env 분리
쓰기 권한 최소화
```

---

## 22. Docker 운영 관점

Docker 환경에서는 하나의 컨테이너에서 여러 profile을 돌리는 것보다, profile별 컨테이너를 분리하는 방식이 더 안전하다.

예시는 다음과 같다.

```text
hermes-master container   → ~/.hermes-master
hermes-planner container  → ~/.hermes-planner
hermes-dev container      → ~/.hermes-dev
hermes-reviewer container → ~/.hermes-reviewer
```

장점은 다음과 같다.

1. 역할별 실행 환경 격리
2. API key와 token 분리
3. 장애 영향 범위 축소
4. gateway 포트 충돌 방지
5. 리소스 제한 적용 가능
6. 로그 추적 용이

---

## 23. Profile Distribution 활용

Profile Distribution은 완성된 Hermes profile 구성을 Git 저장소 형태로 배포하는 방식이다.

포함 가능한 항목은 다음과 같다.

```text
SOUL.md
config.yaml
skills/
cron/
mcp.json
distribution.yaml
```

포함하지 않는 것이 좋은 항목은 다음과 같다.

```text
API key
개인 memory
session history
민감한 .env
개별 사용자 데이터
```

활용 예시는 다음과 같다.

```text
표준 PM 에이전트
표준 코드 리뷰 에이전트
표준 AI 연구 에이전트
표준 제안서 검토 에이전트
```

팀 단위로 Hermes 운영 규칙을 재사용하려면 Profile Distribution이 유용하다.

---

## 24. 권장 실무 도입 순서

Hermes Kanban 기반 장기 실행 구조는 다음 순서로 도입하는 것이 안전하다.

### 24.1 1단계: 단일 프로젝트 Pilot

```text
1. WSL2 또는 Linux VM에 Hermes 설치
2. master / dev / reviewer 3개 profile 생성
3. project board 1개 생성
4. AGENTS.md 작성
5. 작은 기능 1개를 Kanban task로 실행
```

### 24.2 2단계: 역할 확장

```text
1. planner 추가
2. architect 추가
3. qa 추가
4. reporter 추가
5. blocked / comment / handoff 규칙 정리
```

### 24.3 3단계: 장기 실행 자동화

```text
1. cron으로 daily status report 실행
2. gateway로 알림 전송
3. PROJECT_STATUS.md 자동 갱신
4. stale task 감지
5. 실패 task 재시도 정책 적용
```

### 24.4 4단계: 연구·개발 표준화

```text
1. profile별 SOUL.md 표준화
2. 프로젝트별 AGENTS.md 표준화
3. reusable skill 작성
4. Profile Distribution 구성
5. Docker 기반 분리 운영
```

---

## 25. 권장 운영 원칙

```text
1. 프로젝트마다 Kanban Board를 분리한다.
2. 역할마다 Profile을 분리한다.
3. 작업은 Kanban Task로만 시작한다.
4. 실행 전 task 상태를 ready로 명시적으로 전환한다.
5. Master는 직접 구현보다 조율과 판정을 담당한다.
6. Worker는 자기 역할 범위를 벗어나지 않는다.
7. Reviewer는 구현하지 않는다.
8. 완료 판정은 기준 파일이나 acceptance criteria를 따른다.
9. 실험·코드·문서 산출물은 외부 추적 시스템에 남긴다.
10. 중요한 변경은 사람 승인을 거친다.
11. Profile은 sandbox가 아니므로 보안 격리를 별도 설계한다.
12. 장기 실행 작업은 상태 문서와 리포트를 함께 남긴다.
```

---

## 26. 핵심 요약

Hermes Agent는 단순한 AI 채팅 도구가 아니라, 다음 기능을 결합한 자기 개선형 에이전트 런타임이다.

```text
Profile
Memory
SOUL.md
AGENTS.md
Skills
Tools
Gateway
Cron
Kanban Multi-Agent Board
```

Kanban Multi-Agent Board는 다음 역할을 한다.

```text
여러 Profile 에이전트가 공유하는 durable work queue
작업을 task로 저장
담당 profile에 배정
작업 상태와 handoff를 기록
blocked, comment, dependency, complete 흐름 관리
장기 실행 협업 지원
```

프로젝트 운영 관점에서는 다음 구조가 가장 적합하다.

```text
Board = 프로젝트 단위
Profile = 역할 단위
Task = 작업 단위
GitHub Issue/PR = 공식 개발 이력
MLflow/DVC/Optuna = 실험 증거
Report = 사람용 의사결정 자료
```

---

## 27. 결론

Hermes Kanban Multi-Agent Board는 장기 실행형 개발·연구 프로젝트를 에이전트 팀 방식으로 운영하기 위한 핵심 기능이다.

단순히 여러 에이전트에게 작업을 나누는 수준을 넘어, 다음을 가능하게 한다.

1. 역할별 에이전트 분리
2. 프로젝트별 작업 보드 운영
3. 작업 상태의 지속 저장
4. 에이전트 간 handoff 기록
5. 실패·차단 상태 관리
6. 사람 개입 지점 명확화
7. Cron/Gateway와 결합한 장기 운영
8. 개발·연구·리포트 자동화 확장

다만 Kanban은 아직 빠르게 발전하는 기능이므로, 초기에는 작은 프로젝트에서 `master + worker + reviewer` 구조로 검증하고, 이후 board 분리, cron, gateway, Dock