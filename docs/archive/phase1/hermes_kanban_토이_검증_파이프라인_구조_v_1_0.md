# Hermes Kanban 토이 검증 파이프라인 구조 및 실행 기록

문서 버전: v1.0
작성일: 2026-05-27
문서명: hermes_kanban_토이_검증_파이프라인_구조_v_1_0.md
대상 프로젝트: AI 서술형 자동채점 모델 구축 연구 (토이 검증 단계)
운영 방식: Hermes Kanban Multi-Agent Board, codex_app_server runtime

---

## 1. 문서 목적

본 문서는 토이 데이터(342건) + 라이트 모델 + 정상 파이프라인 구성으로 Hermes Kanban Multi-Agent Board의 장기 실행형 자율 연구 워크플로우를 검증하는 과정에서 채택된 파이프라인 구조와 실행 결과를 정리한다.

1차 목표는 모델 성능이 아니라 **Hermes가 다단계 자율 연구를 끝까지 실행하는지** 검증한다.

본 문서는 다음을 포함한다.

1. 전체 8단계(+ 자율 생성 1단계) 워크플로우
2. Profile별 역할 매핑
3. 데이터 흐름 (입력 → 산출물)
4. Acceptance Criteria (모델 + Hermes 메커니즘)
5. 실행 환경 구성
6. 단계별 실행 기록 및 산출물
7. 검증된 Hermes 메커니즘
8. 발견된 이슈 및 우회 방법

---

## 2. 워크플로우 다이어그램

```text
┌──────────────────────────────────────────────────────────────────────┐
│  TRIAGE (사용자 의도)                                                │
│  t_73e6bf0f "에세이 채점 토이 파이프라인 검증"                       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌───────────────┐                       ┌───────────────────┐
│  T1 tukey ✓   │                       │  T2 spearman ✓    │
│  데이터 audit │                       │  ICC + ceiling    │
│  342건 → 30col│                       │  qwk_human=0.179  │
│  leakage 4종  │                       │  ICC(2,k)=0.40    │
└───────┬───────┘                       └─────────┬─────────┘
        │                                         │
        ▼                                         │
┌───────────────────────────┐                     │
│  T3 aristotle ✓           │                     │
│  분할 정책 판정 (직접 X)  │                     │
│  → kanban_create(gauss)   │                     │
└───────┬───────────────────┘                     │
        │ (자율 생성)                             │
        ▼                                         │
┌───────────────────────────┐                     │
│  T3a gauss ✓              │                     │
│  StratifiedGroupKFold     │                     │
│  k=5, seed=42             │                     │
│  splits/fold_*.json       │                     │
└───────┬───────────────────┘                     │
        │                                         │
        ▼                                         │
┌───────────────────────────┐                     │
│  T4 gauss ● running       │                     │
│  4종 피처:                │                     │
│  - 길이 통계              │                     │
│  - TF-IDF (char/word)     │                     │
│  - 어휘 다양성 (TTR/MTLD) │                     │
│  - 문법 오류 수           │                     │
│  + configs/rubric_weights │                     │
└───────┬───────────────────┘                     │
        │                                         │
        ▼                                         │
┌───────────────────────────┐                     │
│  T5 gauss ◻ todo          │                     │
│  베이스라인 4종 (Occam):  │                     │
│  M1 dummy → M2 length →   │                     │
│  M3 TFIDF+Ridge → M4 LGBM │                     │
│  MLflow runs              │                     │
└───────┬───────────────────┘                     │
        ├──────────────────┬──────────────────────┤
        ▼                  ▼                      ▼
┌────────────────┐ ┌────────────────┐  ┌────────────────┐
│  T7 turing ◻   │ │  T6 spearman ◻ │  │ T2 metadata    │
│  코드+leakage  │ │  평가 multi-axis│  │ ceiling=0.179  │
│  리뷰          │ │  by type/grade  │  │ ICC(2,k)=0.40  │
│  WRONG/FRAGILE │ │  /score-band    │  │                │
│  /STYLE        │ │  단조 진화 검증 │  │                │
└────┬───────────┘ └─────┬───────────┘  └────────────────┘
     │                   │
     └────────┬──────────┘
              ▼
┌───────────────────────────┐
│  T8 aristotle ◻           │
│  종합 판정 + Hermes 검증  │
│  - Acceptance 결과        │
│  - 9종 메커니즘 체크      │
│  - 풀 프로덕션 권고       │
└───────────────────────────┘
```

---

## 3. Profile별 역할 매핑

| Profile | Task | Provider | 본질 |
|---|---|---|---|
| aristotle | T3 (정책 판정), T8 (최종 판정) | openai-codex / gpt-5.5 (codex_app_server) | 분류·기준·합성, 직접 구현 X |
| tukey | T1 (데이터 audit) | openai-codex / gpt-5.5 | EDA, 5종 + leakage 4종 |
| spearman | T2 (ceiling), T6 (평가) | openai-codex / gpt-5.5 | metric 3종, segment 분리 |
| gauss | T3a, T4, T5 (코드 구현) | openai-codex / gpt-5.5 | Occam 단조 진화, kanban-codex-lane |
| turing | T7 (코드 리뷰) | openai-codex / gpt-5.5 | WRONG/FRAGILE/STYLE, 직접 수정 X |
| ada-lovelace | (예비 — 토이 단계 미사용) | openai-codex / gpt-5.5 | 보조 구현 워커 |

각 profile은 default에서 clone되었고 SOUL.md에서 페르소나(영문 Identity + 한국어 Style/Avoid/Defaults)를 정의했다. AGENTS.md는 프로젝트 루트에서 모든 profile이 공유한다.

---

## 4. 데이터 흐름

```text
dataset/sample/
   ├─ 원천데이터/ (342 .json: essay_id, essay_txt)
   └─ 라벨링데이터/ (342 .json: info, student, score[3], rubric,
                    paragraph, correction)
                ↓
          [T1 audit]
                ↓
  workspace/T1/{data_quality_report.md, distributions.csv,
                leakage_audit.md, audit_manifest.json}
                ↓
          [T2 + T3]
                ↓
  artifacts/t_7ae417f9/{human_ceiling.md, ceiling_metric.json}
  workspace/split_policy_decision.md
                ↓
          [T3a] pipelines/make_splits.py 작성
                ↓
  workspace/splits/fold_{1..5}.{yaml,json}
  workspace/split_manifest.yaml (seed=42, group_key=student.location)
  workspace/split_leakage_check.md (PASS)
                ↓
          [T4 진행중]
                ↓
  workspace/features/X_{fold}.npz × 5
  configs/rubric_weights.yaml (8가지 변형, JSON에서 추출)
                ↓
          [T5]
                ↓
  pipelines/train.py
  mlruns/ (M1, M2, M3, M4 × 5 fold = 20 runs)
  workspace/models/M{1..4}/{predictions.csv, metrics_per_fold.json}
                ↓
   ┌──────[T6 평가]──────┐──────[T7 리뷰]──────┐
   ▼                     ▼                     ▼
workspace/eval/      workspace/review/      (T2 ceiling 비교)
 eval_report.md       review_report.md
 segment_metrics.csv  leakage_reverification.md
 residual_plot.png
                ↓
          [T8 최종]
                ↓
  workspace/final/{final_report.md, hermes_validation.md}
```

---

## 5. Acceptance Criteria

### 5.1 모델 acceptance (토이지만 정상)

```text
1. Leakage 0건
2. 베이스라인 단조 진화: M1 dummy ≤ M2 length ≤ M3 TFIDF+Ridge ≤ M4 LGBM
3. M4 QWK ≤ human ceiling (ICC(2,k) = 0.40)
   초과 시 → leakage 의심 → auto block
4. Reproducibility manifest (seed=42, config_hash, package versions)
5. Type별·학년군별·score-band별 segment metric 분리 보고
6. 모든 산출물은 metadata에 파일 경로 + 검증 명령 포함
```

### 5.2 Hermes 메커니즘 acceptance (본 프로젝트 진짜 목적)

```text
A. Task 자동 승격 (todo → ready → running)
B. Profile 자동 라우팅 (description 기반)
C. Workspace 격리 (dir, scratch, worktree)
D. Worker spawn (codex_app_server runtime, OS 프로세스)
E. AGENTS.md / SOUL.md 인지 + Hard Rules 적용
F. 자율 task 생성 (T3 → T3a 같은 kanban_create 호출)
G. kanban_block / unblock 흐름 (사람 개입 지점)
H. Handoff metadata 전달 (T1 → T2 등)
I. Durable artifacts 보존 (scratch도 board artifacts에 영구 저장)
```

---

## 6. 실행 환경

### 6.1 Hermes 코어

```text
Gateway (foreground, nohup, PID 변동)
  ├─ Telegram polling (한국시간대)
  ├─ Kanban dispatcher (60s tick) ⚠ 간헐적 SQL 오류 (#30908)
  ├─ Cron ticker
  └─ Memory monitor (300s)
```

### 6.2 Kanban Board

```text
slug: essay-auto-scoring-research
DB: ~/.hermes/kanban/boards/essay-auto-scoring-research/kanban.db (SQLite)
artifacts: ~/.hermes/kanban/boards/essay-auto-scoring-research/artifacts/<task_id>/
logs: ~/.hermes/kanban/boards/essay-auto-scoring-research/logs/<task_id>.log
columns: triage | todo | scheduled | ready | running | blocked | review | done
```

### 6.3 Project Workspace

```text
/home/dev/work/essay-auto-scoring-research/
  ├─ AGENTS.md           (60줄, Hard Rules 8개, command-first)
  ├─ dataset/
  │  ├─ sample/ (342건 5장르 × 학년)
  │  ├─ 1-15_에세이 글 데이터_데이터 설명서.pdf
  │  └─ 루브릭 설명서_v0.3.pdf
  ├─ pipelines/          (worker가 자율 작성)
  │  └─ make_splits.py    ← T3a 결과
  ├─ workspace/
  │  ├─ T1/               ← T1 산출물
  │  ├─ splits/           ← T3a 산출물
  │  ├─ split_manifest.yaml
  │  └─ split_leakage_check.md
  ├─ configs/             (worker가 자율 작성)
  ├─ mlruns/              (T5 이후)
  ├─ models/              (T5 이후)
  ├─ reports/             (T6 이후)
  └─ docs/                (계획·리서치 6개 문서)
```

### 6.4 Profile Pool

```text
~/.hermes/profiles/
  ├─ aristotle/
  ├─ tukey/
  ├─ gauss/
  ├─ spearman/
  ├─ turing/
  └─ ada-lovelace/

각 profile config (동일):
  provider: openai-codex
  default: gpt-5.5
  openai_runtime: codex_app_server

각 profile SOUL.md: 영문 Identity + 한국어 Style/Avoid/Defaults
```

---

## 7. 단계별 실행 기록

### 7.1 T1: 데이터 ingestion + audit (tukey)

- Run 횟수: 3 (run 1 reclaim, run 2 실작업, run 3 block)
- 소요: run 2가 9분 32초 (84 메시지, 78 tool calls)
- 산출물:
  - workspace/T1/data_quality_report.md
  - workspace/T1/distributions.csv
  - workspace/T1/leakage_audit.md
  - workspace/T1/audit_manifest.json
- 주요 발견:
  - 342 source = 342 label, ID 불일치 0
  - 30 column audit frame, 결측 100%는 `student_school` 컬럼만
  - `student.location` 프록시: 7 groups, max 149
  - 점수 분포: mean=24.74, std=2.72 (essay_scoreT_avg, 0-30 척도)
- 결과: AGENTS.md Hard Rule #1과 schema 불일치 발견 → kanban_block (정상)
- 사람 결정: location proxy 수락 (option A) → AGENTS.md 수정 → unblock → complete

### 7.2 T2: 라벨 품질 + 인간 ceiling (spearman)

- 소요: 6분 5초
- 산출물 (artifacts/t_7ae417f9/):
  - human_ceiling.md
  - ceiling_metric.json
- 핵심 결과:
  - QWK_human = 0.1786 (pairwise 평균)
  - ICC(2,1) = 0.1811 (단일 채점자 신뢰도)
  - ICC(2,k) = 0.3988 (3명 평균 신뢰도, target=essay_scoreT_avg 기준)
  - Krippendorff α = 0.1698
  - Pairwise: r1_r2=0.26, r1_r3=0.18, r2_r3=0.10
- 함의: 모델 QWK > 0.40 이면 leakage 의심으로 자동 block

### 7.3 T3: 분할 정책 결정 (aristotle)

- 소요: 분류기 다운 중 자율 완료
- 결과:
  - 정책 artifact: workspace/split_policy_decision.md
  - 자율 task 생성: T3a (gauss, implementation)
- 핵심 결정:
  - StratifiedGroupKFold(k=5, shuffle=True, random_state=42)
  - group: student.location
  - stratify: essay_type × analysis_grade_band
  - location은 split key만, 모델 입력 X
- 검증된 페르소나: aristotle SOUL.md "직접 구현 금지"가 실제로 작동, kanban_create로 specialist 위임

### 7.4 T3a: split implementation (gauss)

- 소요: 4분
- 산출물:
  - pipelines/make_splits.py
  - workspace/split_manifest.yaml (seed, hashes, group/stratify policy)
  - workspace/split_leakage_check.md (PASS)
  - workspace/splits/fold_{1..5}.{yaml, json}
- 결과: "stratified location group split generation with leakage checks passing"

### 7.5 T4: 피처 엔지니어링 (gauss) - 진행중

- 시작: 14:56
- 4종 피처 그룹 작성 예정
- rubric_weights.yaml 외부화 (JSON rubric에서 추출)

### 7.6 T5: 베이스라인 모델 4종 (gauss) - todo

- M1 dummy → M2 length regression → M3 TFIDF+Ridge → M4 LightGBM
- 5-fold × 4모델 = 20 MLflow runs
- 단조 진화 + reproducibility manifest

### 7.7 T6: 평가 multi-axis (spearman) - todo

- QWK, MAE, RMSE, Pearson, Spearman, Exact/Adjacent Agreement
- overall + by type(2) + by 학년군(4) + by score-band(3)
- 인간 ceiling 대비 거리 명시

### 7.8 T7: 코드 + leakage 리뷰 (turing) - todo

- pipelines/{make_splits.py, features.py, train.py} 리뷰
- WRONG/FRAGILE/STYLE 분류
- leakage 재검증
- APPROVE / REQUEST_CHANGES / BLOCK

### 7.9 T8: 종합 판정 + Hermes 검증 보고 (aristotle) - todo

- Acceptance criteria PASS/FAIL
- Hermes 메커니즘 9종 체크
- 풀 프로덕션 확장 권고

---

## 8. 검증된 Hermes 메커니즘 (현재 시점)

| 메커니즘 | 상태 | 증거 |
|---|---|---|
| Board 생성/관리 | ✅ | essay-auto-scoring-research 정상 동작 |
| Profile 시스템 (6명, SOUL.md) | ✅ | clone + 페르소나 분리 |
| Task 생성/의존성/auto promote | ✅ | T1 → T2/T3 → T3a 흐름 |
| Worker spawn (codex_app_server) | ✅ | T1, T2, T3, T3a 모두 spawn |
| AGENTS.md/SOUL.md 인지 | ✅ | tukey가 Hard Rule #1 인용하며 block |
| 자율 코드 작성 | ✅ | audit_data.py, make_splits.py 작성 |
| kanban_block + 사람 결정 + unblock | ✅ | T1 흐름 완수 |
| Result + metadata 기록 | ✅ | 모든 task에 산출물 경로 + 검증 명령 |
| Durable board artifacts | ✅ | scratch 산출물도 artifacts/<task>/에 보존 |
| Handoff metadata 전달 | ✅ | T1 distributions → T2 ICC 입력 |
| 자율 task 생성 (kanban_create) | ✅ | T3 → T3a |
| Type-aware data handling | ✅ | T3가 essay_type × grade-band stratify |
| Workspace 격리 (dir / scratch) | ✅ | task별 분리 |
| Codex CLI (codex_app_server) 통합 | ✅ | 78 tool calls/task 안정적 |

---

## 9. 발견된 이슈 및 우회

### 9.1 Codex backend (openai-codex provider) 호환성 (#5736)

- 증상: HTTPS 직접 호출 시 `'NoneType' object is not iterable`
- 영향: agent loop + full context 시 worker 실패
- 우회: `model.openai_runtime: codex_app_server` 설정 (로컬 Codex CLI subprocess 사용)
- 적용 위치: `~/.hermes/config.yaml` + `~/.hermes/profiles/<name>/config.yaml` 6개 모두

### 9.2 Gateway dispatcher SQL 오류 (#30908)

- 증상: `sqlite3.OperationalError: disk I/O error` (간헐적)
- 원인: gateway 잦은 재시작 + WAL checkpoint 불완전
- 우회: 수동 dispatch (`hermes kanban dispatch --max 1`)로 task 진행
- 추후: gateway 재시작 횟수 최소화, DB dump-rebuild 권장

### 9.3 Anthropic provider 사용 한도 (third-party usage)

- 증상: `HTTP 400: Third-party apps now draw from your extra usage`
- 원인: Claude Code 구독은 third-party 앱에서 별도 usage pool 차감
- 결정: 6 profile 모두 openai-codex(codex_app_server)로 통일
- 효과: Codex CLI 로컬 인증으로 추가 비용 0, 검증 완료

### 9.4 안전성 분류기 일시 불가

- 증상: `claude-opus-4-7 is temporarily unavailable, so auto mode cannot determine the safety`
- 원인: Anthropic 분류기 모델 일시 응답 불가
- 영향: Bash/Monitor 도구 잠시 사용 불가 (Read는 가능)
- 회복: 자동 (수 분 내)

### 9.5 T4-T8 초기 생성 실패

- 원인: `--max-runtime` CLI 옵션 형식 오류
- 우회: 옵션 제거 후 재생성, 의존성은 `--parent` + `hermes kanban link`로 명시 연결
- 적용: T4(t_2c34c9dc), T5(t_130be2fe), T6(t_8cba519c), T7(t_e2536eb0), T8(t_f8330a6d)

---

## 10. 운영 원칙 (재확인)

```text
1. Hermes Kanban이 연구 작업 흐름을 관리한다.
2. 모든 task 산출물은 metadata에 파일 경로 + 검증 명령 포함.
3. 모든 실패는 silent 처리 금지 — kanban_block + reason + 재현 명령 필수.
4. Profile은 SOUL.md 페르소나대로 행동한다.
5. Aristotle은 직접 구현하지 않고 specialist에게 위임한다.
6. Gauss는 가장 단순한 모델부터 단조 진화로 검증한다.
7. Spearman은 metric을 도메인 의미와 함께 보고한다.
8. Turing은 리뷰만 한다 — 절대 직접 수정하지 않는다.
9. 인간 ceiling 위에 모델 결과가 나오면 자동 block (leakage 의심).
10. test set leakage는 0건이어야 한다 — student.location 기반 group split.
```

---

## 11. 다음 검증 포인트 (T5 이후)

T5 학습 단계에서 검증할 추가 메커니즘:
- MLflow tracking 통합 (worker가 자율 등록)
- 단조 진화 위반 시 자동 block 트리거
- 학습 시간이 긴 task (4시간 timeout 검증)

T6/T7 병렬 실행 가능성:
- Dispatcher가 의존성 충족된 ready task 2개를 동시 spawn하는지
- Worker 동시 실행 시 codex_app_server 자원 경합

T8 종합 판정:
- Aristotle이 third-party 모델 cross-check 없이 self-PASS 안 하는지
- Final report에 acceptance criteria 정확히 인용하는지

---

## 12. 결론

본 토이 검증을 통해 Hermes Kanban Multi-Agent Board가 다음 능력을 갖춤이 입증되었다.

1. 6개 profile이 SOUL.md 페르소나에 따라 자율적으로 행동
2. 의존성 그래프 기반 자동 task 승격
3. Profile 간 task 자율 위임 (kanban_create)
4. AGENTS.md Hard Rules를 worker가 자율 인지·적용
5. 코드 작성·실행·산출물 생성·metadata 첨부까지 끝까지 자율 수행
6. 발견된 정책 불일치는 적절히 block + 사람 결정 요청

남은 검증(T5-T8)이 완료되면 본 프로젝트는 토이 단계를 마치고 풀 프로덕션 확장 가능성을 확보한다. 풀 확장 시 추가 검토 항목은 다음과 같다.

- 데이터 규모 50K로 확장 시 메모리·디스크·실행 시간
- 8가지 루브릭 변형 모두 처리하는 multi-task 모델
- Bias 평가, 설명가능성, adversarial robustness
- Cron 기반 24/7 자율 실행 (장기 실행)
- 풀 LLM 비용 모니터링 + budget cap
