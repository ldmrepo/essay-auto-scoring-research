# Hermes Kanban Multi-Agent Board 최신 리서치 및 심층 이해

문서 버전: v1.0
작성일: 2026-05-27
문서명: hermes_kanban_multi_agent_board_최신_리서치_및_심층이해_v_1_0.md
대상 도구: Hermes Agent v0.14.0+
주제: Hermes Kanban Multi-Agent Board의 동작 원리, 메커니즘, 협업 패턴, 한계, 운영 함정
참고 문서:
- hermes_핵심구조_kanban_multi_agent_board_개념_사용_활용_정리_v_1_0.md
- hermes_kanban_기반_ai_서술형_자동채점_연구팀_오버뷰_v_1_0.md

---

## 1. 문서 목적

본 문서는 공식 Hermes Agent 문서, NousResearch GitHub 저장소, 커뮤니티 가이드(magnus919, blakecrosley, SingleAPI, DeepWiki, Hermes Atlas)와 실제 v0.14.0 CLI를 교차 검증해 정리한 Hermes Kanban Multi-Agent Board의 **메커니즘 중심 심층 이해 자료**이다.

기존 두 운영 문서가 개념과 워크플로우는 잘 다루었으나 다음 영역은 약했다.

1. 두 개의 상호작용 면(워커 도구 vs 사람 CLI)의 통합 구조
2. Dispatcher의 위치(gateway 임베드)와 그로 인한 운영 의존성
3. Workspace 종류와 병렬 안전성
4. 워커 프로토콜의 엄격함
5. 자동 복구 메커니즘과 circuit breaker
6. swarm, decompose, specify의 자동화 흐름
7. 공식이 명시한 한계(single-host) 및 설정 함정
8. 8가지 협업 패턴

본 문서는 위 영역을 보충하고, 두 운영 문서에 반영할 보정 사항을 §18에 정리한다.

---

## 2. 핵심 멘탈 모델

```text
사람 ── CLI / Dashboard ──┐
                          ├── kanban.db (SQLite, ~/.hermes/kanban.db) ──┐
워커 ── kanban_* 도구 ────┘                                              │
                                                                         ▼
                                                                   Dispatcher
                                                              (gateway 내부, 60초 tick)
                                                                         │
                                                                         ▼
                                                              Worker 프로세스 spawn
                                                          (hermes -p <profile> chat)
```

다음 세 가지를 정확히 이해하는 것이 가장 중요하다.

### 2.1 두 개의 상호작용 면

| 면 | 사용자 | 인터페이스 |
|---|---|---|
| 워커 측 | LLM worker 프로세스 | `kanban_show`, `kanban_complete`, `kanban_block`, `kanban_heartbeat`, `kanban_comment`, `kanban_create`, `kanban_link`, `kanban_unblock` 등 도구 호출 |
| 사람 측 | 운영자, 팀원 | `hermes kanban ...` CLI, `/kanban` 슬래시 명령, 대시보드 GUI |

두 면 모두 같은 SQLite 백엔드(`~/.hermes/kanban.db`)를 공유하므로 상태 일관성이 보장된다.

### 2.2 Dispatcher의 위치

Dispatcher는 기본적으로 Hermes Gateway 프로세스 내부에 임베드된다.

```yaml
kanban:
  dispatch_in_gateway: true   # 기본값
```

이 사실의 운영 함의는 다음과 같다.

1. Gateway가 죽으면 Kanban dispatcher도 죽는다.
2. Gateway가 stuck 상태가 되면 ready task가 spawn되지 않는다.
3. 따라서 Gateway 모니터링 = Kanban 모니터링이다.

### 2.3 워커는 OS 프로세스

워커는 부모 프로세스 메모리 안의 subagent swarm이 아니라 완전한 OS 프로세스로 spawn된다.

```bash
hermes -p <assignee> chat
```

이 구조의 장점은 다음과 같다.

1. 워커 크래시가 dispatcher를 죽이지 않는다.
2. 사람이 mid-run에 개입 가능하다 (comment, unblock).
3. 재시작 후에도 profile별 메모리·세션이 유지된다.

---

## 3. Kanban vs delegate_task — 다시 정확히

| 측면 | Kanban | delegate_task |
|---|---|---|
| 본질 | Durable message queue + state machine | RPC call (fork → join) |
| 호출자 | 작업 후 fire-and-forget | 자식 응답까지 block |
| 자식 정체 | 이름 있는 profile, 영속 메모리 | 익명 subagent, 일회성 |
| 사람 개입 | 지원 (comment, unblock 언제든) | 미지원 |
| 재시작 생존 | 보존 | 소실 |
| 감사 추적 | 영속 row + 이벤트 | 부모 대화 안에만 |
| 적합 용도 | 장기 실행, 에이전트 경계 횡단, HITL 필요 | 짧은 추론 보조 작업 |

요약하면 다음과 같다.

```text
delegate_task = 즉시 답이 필요한 짧은 보조 작업에 적합
Kanban = 장기 실행, 역할 분리, 협업 이력, 재시도, 사람 개입이 필요한 작업에 적합
```

---

## 4. 자동화의 두 축 — Decompose와 Specify

Triage 상태의 거친 아이디어는 두 가지 자동화 경로로 todo 또는 task 그래프가 된다.

| 기능 | 사용 시점 | 동작 |
|---|---|---|
| `specify` | 작업 1개를 다듬을 때 | one-shot으로 goal, approach, acceptance criteria를 채우고 todo로 승격 |
| `decompose` | 작업이 여러 단계로 나뉠 때 | LLM이 JSON task graph 생성, profile 라우팅과 의존성 자동 설정 |

자동 모드는 다음과 같이 동작한다.

```yaml
kanban:
  auto_decompose: true             # triage 생성 시 자동 decompose 시도
  auto_decompose_per_tick: 3       # tick당 최대 3건 (auxiliary LLM 보호)
```

운영 함의는 다음과 같다.

1. 사용자는 거대한 idea만 triage로 던지면 시스템이 알아서 task 그래프를 만든다.
2. Profile description의 품질이 곧 라우팅 품질이다. `hermes profile create <name> --description "..."` 또는 `hermes profile describe <name> --text "..."`로 풍부하게 작성해야 한다.
3. Decompose는 `auxiliary.kanban_decomposer`로 지정된 모델을 사용한다. 메인 모델과 별도 설정이 필요하다.

---

## 5. Workspace 종류 — 병렬 안전성의 핵심

여러 워커가 동시에 실행될 때 같은 파일을 동시 수정하면 충돌이 발생한다. Kanban은 task별 workspace로 이를 격리한다.

| 종류 | 위치 | 수명 | 용도 |
|---|---|---|---|
| `scratch` (기본) | `~/.hermes/kanban/workspaces/<id>/` | task 완료 시 삭제 | 격리된 1회용 작업 |
| `worktree` | `.worktrees/<id>/` (git worktree) | 보존 | 병렬 코드 작업 |
| `dir:<absolute path>` | 사용자 지정 절대경로 | 보존 | Obsidian vault, 데이터 디렉토리, 공유 폴더 |

예시는 다음과 같다.

```bash
hermes kanban create "베이스라인 학습" \
  --assignee modeler \
  --workspace worktree \
  --branch wt/baseline-v1

hermes kanban create "데이터 진단" \
  --assignee data-auditor \
  --workspace dir:/home/dev/data/essay-auto-scoring

hermes kanban create "평가 실행" \
  --assignee evaluator \
  --workspace scratch
```

운영 권장 사항은 다음과 같다.

1. 코드를 수정하는 워커는 `worktree`로 격리한다.
2. 공유 데이터셋을 읽기/쓰기하는 워커는 `dir:<path>`로 명시한다.
3. 1회용 분석/리포트 워커는 `scratch`로 두어 자동 정리한다.

---

## 6. 워커 프로토콜 — 엄격함

워커 생애주기는 다음과 같다.

```text
1. spawn       : dispatcher가 HERMES_KANBAN_TASK=t_abcd 환경변수 세팅
2. read        : worker가 kanban_show() 호출 (인자 없음, env 사용)
3. work        : $HERMES_KANBAN_WORKSPACE 안에서 작업
4. heartbeat   : 60분마다 kanban_heartbeat() (4시간 timeout 갱신)
5. exit:
     kanban_complete(summary=..., metadata={...}) → 성공
     kanban_block(reason="...")                   → 차단 (사람 개입 대기)
     기타 종료 (process exit)                     → protocol_violation 자동 blocked
```

핵심 사실은 다음과 같다.

1. `summary + metadata`는 단순 로그가 아니라 다음 단계 워커에게 전달되는 구조적 입력이다.
2. 다음 단계 워커는 `kanban_show()`로 부모 task의 metadata를 구조적으로 받는다.
3. 따라서 metadata는 도메인 표준 스키마를 정의해두는 것이 좋다.

권장 metadata 스키마(서술형 자동채점 도메인 예시)는 다음과 같다.

```json
{
  "metrics": {
    "qwk": 0.78,
    "mae": 0.32,
    "rmse": 0.51,
    "adjacent_agreement": 0.91
  },
  "item_metrics_path": "metrics/item_metrics.csv",
  "mlflow_run_id": "abc123",
  "model_artifact": "models/exp_042/model.pkl",
  "config_hash": "sha256:...",
  "dataset_version": "v1.2",
  "decisions": [
    "feature set v3 적용",
    "최대 토큰 1024로 제한"
  ],
  "residual_risk": [
    "점수대 6에서 샘플 부족",
    "특정 문항 QWK 0.62로 임계 미달"
  ]
}
```

---

## 7. Task 상태 흐름 — 자동 승격 메커니즘 포함

```text
       triage
          │  (auto-decompose 또는 수동 specify)
          ▼
        todo
          │  (의존성 모두 충족 시 dispatcher가 자동 승격)
          ▼
        ready
          │  (dispatcher가 atomic claim + worker spawn)
          ▼
       running ──────────────┐
          │                  │ (kanban_block 또는 N회 실패)
          │                  ▼
          │               blocked
          │                  │ (사람 unblock)
          │                  ▼
          │                ready (재진입)
          │
          ▼
        done
          │ (수동 또는 정책에 따라)
          ▼
       archived
```

상태별 의미는 다음과 같다.

| 상태 | 의미 |
|---|---|
| triage | 검토 전 작업 후보, decompose/specify 대상 |
| todo | 사양 정해진 미실행 작업, 의존성 대기 중 |
| ready | 실행 가능. dispatcher가 claim 후보 |
| running | worker가 처리 중 |
| blocked | 사람 개입 대기. comment + unblock으로 ready 복귀 |
| done | 완료 |
| archived | 종료 또는 폐기 |

기존 운영 문서에서 누락된 점은 다음과 같다.

1. `todo → ready` 승격은 dispatcher가 의존성 충족 시 자동 수행한다.
2. `blocked → ready`는 사람 unblock으로 양방향이다.
3. `triage → todo`는 decompose/specify 자동화의 결과이다.

---

## 8. 실패와 복구 메커니즘

| 시나리오 | 탐지 | 자동 대응 |
|---|---|---|
| 워커 크래시 (segfault, OOM, 강제 종료) | `kill(pid, 0)` — 1 tick (60초) 내 | claim 회수 → ready 복귀 |
| 워커 행 (응답 없음) | heartbeat 끊김 — 15분 TTL | reclaim → ready |
| 4시간 초과 | `dispatch_stale_timeout_seconds: 14400` | timed_out 이벤트 → blocked |
| 연속 실패 | `failure_limit: 2` | circuit breaker → 자동 blocked + 마지막 에러를 reason으로 |
| 프로필 없음 | spawn 실패 | `skipped_nonspawnable` 이벤트 → ready 유지 (사람 개입 필요) |
| 프로토콜 위반 | 워커가 complete/block 없이 종료 | `protocol_violation` 이벤트 → 자동 blocked |
| Hallucinated card | 존재하지 않는 task ID 완료 시도 | 작업 거부, task는 mutable 유지 |

운영 함의는 다음과 같다.

1. 1회 실패는 transparent retry이지만 N회 연속 실패는 circuit breaker로 차단된다.
2. 모든 실패는 `task_runs` 테이블에 row로 남으므로 retrying worker가 이전 진단을 받는다.
3. 워커가 임의 종료하면 자동으로 blocked가 되므로 silent failure가 발생하지 않는다.

---

## 9. 8가지 공식 협업 패턴

| 패턴 | 형태 | 자동채점 연구 적용 예시 |
|---|---|---|
| Fan-out | 1 → N 병렬 | 한 데이터셋에 N개 피처 조합 동시 학습 |
| Pipeline | A → B → C 순차 | data-audit → feature-eng → train → evaluate → report |
| Voting / Quorum | N workers + 1 aggregator | 여러 모델 예측을 평균/투표 후 통합 |
| Long-running journal | 공유 dir + cron | Obsidian vault에 일일 실험 로그 누적 |
| Human-in-the-loop | worker blocks → human comments → unblock | 라벨 정책 변경, bias 위반 같은 critical decision |
| @mention routing | 인라인 prose로 다음 담당 지정 | comment에서 "@reviewer 확인 부탁" |
| Thread-scoped workspace | `/kanban here` | 텔레그램 채팅 스레드마다 격리된 보드 |
| Fleet farming | 1 profile × N subjects | 1 reviewer profile이 N개 PR을 순차 처리 |

`swarm` 명령은 Voting/Quorum 패턴을 그래프 형태로 표준화한 것이다.

```bash
hermes kanban swarm "여러 모델로 결과 비교 후 통합" \
  --workers researcher-1 researcher-2 researcher-3 \
  --verifier critic \
  --synthesizer integrator
```

생성되는 그래프는 다음과 같다.

```text
[researcher-1, researcher-2, researcher-3]    (병렬 실행)
                  │ 모두 완료 후
                  ▼
              [critic]                        (검증)
                  │
                  ▼
           [integrator]                       (합성)
```

서술형 자동채점 연구에서 활용 예시는 다음과 같다.

1. 여러 피처 조합 또는 모델을 병렬 학습한다.
2. 평가자가 각 결과를 비교한다.
3. 통합기가 최선 모델 또는 ensemble을 선정한다.

---

## 10. 설정 핵심 (Gotchas 포함)

```yaml
kanban:
  dispatch_in_gateway: true              # gateway가 dispatcher 호스팅 (기본)
  dispatch_interval_seconds: 60          # tick 간격
  failure_limit: 2                       # circuit breaker 임계
  dispatch_stale_timeout_seconds: 14400  # 4시간
  auto_decompose: true                   # triage 자동 분해
  auto_decompose_per_tick: 3             # tick당 최대 분해 수 (burst 보호)
  orchestrator_profile: ""               # 비어 있으면 active profile이 자동 지정됨
  default_assignee: ""

auxiliary:
  kanban_decomposer: ""                  # decomposer LLM. 메인 모델 자동 상속 안 됨
  profile_describer: ""                  # profile 설명 자동 생성 LLM

dashboard:
  kanban:
    default_tenant: ""
    lane_by_profile: true                # Running 컬럼을 profile별 lane으로
    render_markdown: true
```

운영 함정 3가지는 다음과 같다.

1. `orchestrator_profile`이 비어 있으면 현재 활성 profile이 자동 orchestrator로 지정된다. 공유 환경에서는 의도치 않은 profile이 결정권을 가질 수 있다.
2. `auxiliary.kanban_decomposer`는 메인 모델을 자동 상속하지 않는다. 비워두면 decompose가 실패한다.
3. `auto_decompose_per_tick: 3`은 auxiliary 모델 호출량 보호장치이다. 무턱대고 늘리면 quota가 폭주한다.

---

## 11. 번들 스킬 — 표준화된 운영 패턴

자동 설치되는 두 스킬은 다음과 같다.

| 스킬 | 사용 주체 | 학습 내용 |
|---|---|---|
| `kanban-worker` | 모든 worker profile | read → work → heartbeat → complete 생애주기, metadata 구조 |
| `kanban-orchestrator` | orchestrator profile | 분해 패턴, "직접 구현 유혹 저항" 규칙 |

운영 함의는 다음과 같다.

1. `research-master`에게 `kanban-orchestrator` 스킬을 명시적으로 부여하면 직접 구현 유혹을 시스템적으로 차단할 수 있다.
2. 워커별로 도메인 스킬을 핀할 수 있다.

```bash
hermes kanban create "Korean essay translation" \
  --assignee linguist \
  --skill translation

# Python에서 동등하게:
# kanban_create(title="...", assignee="linguist", skills=["translation"])
```

---

## 12. 이벤트 모델

```bash
hermes kanban watch --kinds completed,gave_up,timed_out
```

이벤트는 3개 그룹으로 분류된다.

| 그룹 | 이벤트 |
|---|---|
| Lifecycle | created, promoted, claimed, completed, blocked, unblocked, archived |
| Edits | assigned, edited, reprioritized, status |
| Telemetry | spawned, heartbeat, reclaimed, crashed, timed_out, stale, respawn_guarded, spawn_failed, protocol_violation, gave_up |

운영 권장 사항은 다음과 같다.

1. 텔레그램 알림은 `gave_up`, `protocol_violation`, `timed_out`만 필터링하면 noise 없이 문제만 캐치 가능하다.
2. 대시보드에서는 라이브로 모든 이벤트를 본다.
3. `task_runs` 테이블은 retry 이력을 보존하므로 사후 분석에 활용한다.

---

## 13. 멀티 보드와 멀티 테넌트

### 13.1 멀티 보드 (프로젝트 격리)

```bash
hermes kanban boards create essay-auto-scoring-research --name "서술형 자동채점 연구" --icon 🧪
hermes kanban boards create exam-system --name "시험 시스템" --icon 🎓
hermes kanban boards list

# 보드 지정 실행
hermes kanban --board essay-auto-scoring-research list

# 활성 보드 전환 (sticky)
hermes kanban boards switch essay-auto-scoring-research
```

보드 해석 우선순위는 다음과 같다.

```text
1. 명시적 --board 플래그
2. HERMES_KANBAN_BOARD 환경변수
3. ~/.hermes/kanban/current 파일
4. default
```

각 보드는 독립된 SQLite, workspace, 로그를 가지며 cross-board 링크가 없다.

### 13.2 멀티 테넌트 (한 프로파일 fleet으로 여러 고객)

```bash
hermes kanban create "monthly report" \
  --assignee researcher \
  --tenant business-a \
  --workspace dir:/home/dev/tenants/business-a/data/
```

워커는 `$HERMES_TENANT` 환경변수를 받고 메모리 키도 prefix로 분리된다.

---

## 14. 명시적 한계 (Out of Scope)

공식 문서는 다음을 분명히 못박았다.

> Kanban is single-host only. No multi-host coordination, no cross-host worker spawning, no distributed locking.

다중 서버로 확장하려면 다음 중 하나를 선택해야 한다.

1. 호스트별 독립 보드 + `delegate_task`로 브릿지
2. 외부 메시지 큐 (Redis, RabbitMQ 등) 자체 구현

서술형 자동채점 연구가 단일 GPU 서버에서 끝난다면 문제 없으나, 분산 학습 클러스터로 확장하려면 별도 설계가 필요하다.

---

## 15. v0.14 신규 기능 요약

| 기능 | 도입 | 의미 |
|---|---|---|
| `swarm` v1 그래프 | v0.13 ~ v0.14 | 병렬 + 검증 + 합성 표준화 |
| `decompose` LLM 기반 분해 | v0.12 | triage → todo 자동화 |
| `specify` single-task rewrite | v0.12+ | 단일 task 사양화 |
| Worker lanes (대시보드) | v0.14 | UI에서 profile별 시각화 |
| Tenant 격리 | v0.13~ | 단일 profile fleet으로 N 고객 |
| `--idempotency-key` | v0.13+ | cron 중복 생성 방지 |
| `kanban gc` | v0.14 | 오래된 workspace 정리 |
| `kanban diagnostics (diag)` | v0.14 | 보드 건강성 진단 |

본 프로젝트 환경(v0.14.0)에서 위 기능 모두 사용 가능하다.

---

## 16. CLI 명령 요약

### 16.1 보드 관리

```bash
hermes kanban init                                  # kanban.db 생성 (idempotent)
hermes kanban boards create <slug> --name "..."     # 보드 생성
hermes kanban boards list                           # 보드 목록 + task count
hermes kanban boards switch <slug>                  # sticky 활성 보드 전환
hermes kanban boards show                           # 현재 활성 보드
hermes kanban boards rename <slug> --name "..."     # 보드 표시 이름 변경
hermes kanban boards rm <slug>                      # 보드 archive 또는 삭제
```

### 16.2 Task 생성

```bash
hermes kanban create "title" \
  --assignee <profile> \
  --body "..." \
  --parent <task_id> \
  --workspace <scratch|worktree|dir:/path> \
  --branch <branch_name> \
  --tenant <name> \
  --priority <n> \
  --triage \
  --idempotency-key <key> \
  --max-runtime <seconds> \
  --max-retries <n> \
  --skill <skill_name> \
  --initial-status <blocked|running>
```

### 16.3 Task 조회

```bash
hermes kanban list                                  # 전체 task
hermes kanban list --assignee <profile>             # 담당자 필터
hermes kanban list --status running                 # 상태 필터
hermes kanban show <task_id>                        # task + comments + events
hermes kanban runs <task_id>                        # 실행 이력 (재시도 포함)
```

### 16.4 Task 변경

```bash
hermes kanban assign <task_id> <profile>            # 할당 또는 재할당
hermes kanban reclaim <task_id>                     # 활성 claim 해제
hermes kanban reassign <task_id> <profile>          # 재할당 (필요 시 reclaim)
hermes kanban comment <task_id> "..."               # comment 추가
hermes kanban complete <task_id> --result "..." --metadata '{}'
hermes kanban block <task_id> "reason"
hermes kanban unblock <task_id>
hermes kanban edit <task_id> --field value
hermes kanban link <parent_id> <child_id>           # 의존성 추가
hermes kanban unlink <parent_id> <child_id>         # 의존성 제거
hermes kanban archive <task_id>
hermes kanban promote <task_id>                     # 상태 승격
```

### 16.5 자동화

```bash
hermes kanban swarm "..." --workers a b c --verifier v --synthesizer s
hermes kanban specify <task_id>                     # 단일 task 사양화
hermes kanban decompose <task_id>                   # task graph 분해
hermes kanban dispatch --max 3                      # 수동 dispatch pass
hermes kanban daemon                                # dispatcher 단독 실행
hermes kanban claim <task_id>                       # atomic claim
hermes kanban heartbeat <task_id>                   # worker 생존 신호
```

### 16.6 모니터링

```bash
hermes kanban tail                                  # 보드 이벤트 tail
hermes kanban watch --kinds completed,gave_up       # 이벤트 종류별 watch
hermes kanban stats                                 # 통계
hermes kanban diagnostics                           # 보드 건강성 진단
hermes kanban assignees                             # assignee 목록
hermes kanban context <task_id>                     # task context 조회
hermes kanban log <task_id>                         # 실행 로그
```

### 16.7 알림 구독

```bash
hermes kanban notify-subscribe <task_id> --platform telegram
hermes kanban notify-list
hermes kanban notify-unsubscribe <id>
```

### 16.8 정리

```bash
hermes kanban gc                                    # 오래된 workspace, archived task 정리
```

---

## 17. 운영 안전 점검표

### 17.1 일일 점검 항목

```text
1. Gateway 프로세스 살아 있는가? (ps -ef | grep "hermes gateway")
2. Dispatcher tick이 발생하고 있는가? (gateway.log에 spawned 이벤트 확인)
3. blocked task 누적 수가 임계 이하인가?
4. stale task가 있는가? (hermes kanban diagnostics)
5. circuit breaker가 trip한 task가 있는가?
6. auxiliary LLM quota 잔량은 충분한가?
7. 디스크 사용량 (~/.hermes/kanban/workspaces) 정상인가?
```

### 17.2 주간 점검 항목

```text
1. task_runs 통계로 재시도율 추세 확인
2. workspace gc 실행 (hermes kanban gc)
3. archived task 정리
4. profile description 최신화 여부
5. 알림 구독 정리
```

### 17.3 사고 대응

| 증상 | 1차 조치 | 근본 조치 |
|---|---|---|
| ready task가 spawn되지 않음 | gateway 상태 확인, 재시작 | dispatcher 임베드 옵션 검토 |
| 같은 task 무한 재시도 | circuit breaker 확인, blocked 처리 | failure_limit 또는 max-retries 조정 |
| 다수 task가 blocked | comment 확인, 일괄 unblock | 정책 검토, profile description 보강 |
| workspace 디스크 폭주 | hermes kanban gc | scratch 사용 강화, 보존 정책 명시 |
| decompose 실패 | auxiliary.kanban_decomposer 설정 | 모델/quota 점검 |
| profile not found 반복 | profile 생성, --description 부여 | distribution 표준화 |

---

## 18. 기존 운영 문서 보정 권고

### 18.1 hermes_kanban_기반_ai_서술형_자동채점_연구팀_오버뷰_v_1_0.md

다음 보정이 필요하다.

1. 새 §0 — 시스템 사전 요구사항
   - hermes >= 0.14.0
   - gateway 24/7 운영 (dispatcher 호스팅)
   - auxiliary.kanban_decomposer 명시적 설정
2. §5 보강 — Profile 생성 시 `--description`을 풍부하게 작성 (decomposer 라우팅 품질의 근본)
3. §7 보강 — 상태 흐름 = 자동 승격 + blocked 양방향
4. §8 신규 단계 — SWARM 패턴 활용
5. §9 보강 — 모든 task에 `--workspace` 명시 (modeler/hpo-agent는 worktree, data-auditor는 dir, evaluator는 scratch)
6. §17 보강 — `kanban.*` 설정값 명시

### 18.2 hermes_핵심구조_kanban_multi_agent_board_개념_사용_활용_정리_v_1_0.md

다음 보정이 필요하다.

1. §10 보강 — swarm v1 그래프 패턴 추가
2. §13 보강 — Kanban과 delegate_task 구분을 synchronous RPC vs durable message-passing으로 더 정확히
3. §14 보강 — 자동 승격 메커니즘 명시
4. §15 신규 — workspace 종류 (scratch/worktree/dir) 비교
5. §16 신규 — Anti-pattern: orchestrator가 직접 구현하지 못하도록 kanban-orchestrator 스킬 부여
6. §21 보강
   - 21.6 신규: dispatcher = gateway. gateway가 죽으면 Kanban도 죽음
   - 21.7 신규: orchestrator_profile / auxiliary.kanban_decomposer 함정
   - 21.8 신규: single-host 한계 명시
7. §27 신규 — 8가지 협업 패턴 정리

---

## 19. 핵심 한 줄

```text
Kanban은 worker swarm이 아니다.
이름이 있는 OS 프로세스로서의 에이전트들이,
durable SQLite 큐를 통해 결정·교차검증·핸드오프하며,
gateway 안의 dispatcher가 60초마다 그들을 깨우는 시스템이다.
```

이 한 줄을 운영 문서 서두에 박으면 독자의 멘탈 모델이 정확하게 잡힌다.

---

## 20. 참고 자료

### 20.1 공식 문서

- Kanban (Multi-Agent Board): https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Kanban Tutorial: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-tutorial
- Kanban Worker Lanes: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-worker-lanes
- NousResearch/hermes-agent (GitHub): https://github.com/NousResearch/hermes-agent
- RFC PR#16100 — Multi-profile Collaboration Board: https://github.com/NousResearch/hermes-agent/issues/16102

### 20.2 커뮤니티 자료

- The Hermes Kanban Complete Guide (Magnus919): https://magnus919.com/2026/05/the-hermes-kanban-a-complete-guide-to-multi-agent-task-orchestration/
- Hermes Kanban Cheatsheet (SingleAPI): https://www.singleapi.net/2026/05/19/hermes-kanban-cheatsheet-commands-tools-solutions/
- Hermes v0.14 Reference (Blake Crosley): https://blakecrosley.com/guides/hermes
- Kanban Core and Database (DeepWiki): https://deepwiki.com/NousResearch/hermes-agent/12.1-kanban-core-and-database
- Hermes Atlas: https://hermesatlas.com/

### 20.3 본 프로젝트 관련 문서

- hermes_핵심구조_kanban_multi_agent_board_개념_사용_활용_정리_v_1_0.md
- hermes_kanban_기반_ai_서술형_자동채점_연구팀_오버뷰_v_1_0.md

---

## 21. 결론

Hermes Kanban Multi-Agent Board는 단순한 task 큐가 아니라, 다음을 한 시스템에 통합한 장기 실행 협업 인프라이다.

1. Durable SQLite 백엔드로 모든 task와 이벤트를 영속화한다.
2. 두 면(워커 도구, 사람 CLI)이 같은 백엔드를 공유한다.
3. Gateway 임베드 dispatcher가 60초 tick으로 worker 생애주기를 관리한다.
4. Workspace 격리로 병렬 안전성을 보장한다.
5. Decompose/Specify로 거친 idea를 자동으로 task 그래프로 변환한다.
6. Swarm으로 fan-out + verify + synthesize 패턴을 표준화한다.
7. Circuit breaker, heartbeat, protocol violation 탐지로 silent failure를 방지한다.
8. 사람 개입 지점이 명확하다 (blocked + comment + unblock).
9. 멀티 보드, 멀티 테넌트로 프로젝트와 고객을 격리한다.
10. 단, 단일 호스트 한계가 있다.

이 자료는 본 프로젝트가 서술형 자동채점 연구를 Hermes Kanban 기반으로 운영할 때, 운영 문서의 메커니즘 이해를 보강하고 함정을 사전에 인지하기 위한 참조 문서로 사용한다.
