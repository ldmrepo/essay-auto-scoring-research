# Hermes Kanban 세미나 이미지 생성 프롬프트 v1.2

> 대상 문서: `docs/seminar_hermes_kanban_autonomous_research_workflow_v_1_0.md` v1.1
> 목적: PPT 20페이지용 OpenAI 완성형 슬라이드 이미지 생성 프롬프트 운영 문서
> 스타일: 기술 세미나용 미니멀 다이어그램 / editorial vector illustration
> 기준 버전: v1.1
> 개정 버전: v1.2
> 작성일: 2026-05-28
> 표지 정보: (주) 아이오시스 연구소 AI 개발팀 / 수석 연구원 이동명 / 2025-05-28
> 개정 방향: 배경 이미지 생성용 프롬프트에서 완성형 슬라이드 이미지 생성용 프롬프트로 전환

---

## 1. 개정 요약

v1.2는 v1.1의 시각 스타일과 운영 기준을 유지하되, 산출물을 “PPT에서 텍스트를 얹기 위한 배경 이미지”가 아니라 **텍스트와 다이어그램이 함께 들어간 완성형 슬라이드 이미지**로 생성하도록 개정한다.

| 구분 | v1.1 | v1.2 개정 내용 |
|---|---|---|
| 문서 성격 | 배경/보조 다이어그램 생성 운영 문서 | 완성형 슬라이드 이미지 생성 운영 문서 |
| 텍스트 정책 | 제목·본문·수치·표는 PPT에서 후처리 | 슬라이드 제목, 핵심 문구, 짧은 라벨을 이미지 안에 직접 렌더링 |
| 페이지별 구성 | 핵심 메시지 + 배경 이미지 프롬프트 | 완성형 슬라이드 레이아웃 + exact slide text + 다이어그램 프롬프트 |
| 검수 기준 | 텍스트 최소화 중심 | 한글 텍스트 정확성, 줄바꿈, 오탈자 검수 강화 |
| 운영 리스크 | 이미지 내부 텍스트 오류 회피 | 텍스트 오류 발생 시 regenerate 또는 PPT 후처리 fallback 명시 |

---

## 2. 리서치 요약

이미지 생성 프롬프트는 길이보다 구조가 중요하다. 목적, 주 피사체, 장면 구성, 시각 스타일, 구도, 조명, 제약을 명확히 지정하는 것이 안정적이다.

PPT용 이미지는 본문 텍스트를 별도로 얹는 방식이 가장 안정적이지만, 완성형 슬라이드 이미지를 만들 때는 이미지 안의 텍스트를 짧게 제한하고, 제목·핵심 문구·라벨의 exact text를 프롬프트에 명시해야 한다. 특히 한글 텍스트는 생성 후 반드시 확대 검수한다.

본 문서는 다음 원칙에 따라 구성한다.

* 각 페이지의 핵심 메시지를 먼저 고정한다.
* 이미지는 완성형 슬라이드 한 장으로 사용한다.
* 이미지 안의 텍스트는 제목, 핵심 문구, 짧은 라벨 중심으로 제한한다.
* 반복 생성 시 같은 스타일 레퍼런스를 사용한다.
* 복잡한 다이어그램은 한 장에 모든 내용을 넣지 않고 핵심 구조만 표현한다.
* 표, 수치, 긴 설명은 완성형 이미지 안에 넣지 않는다.
* 생성 텍스트가 깨지면 같은 프롬프트로 재생성하거나 PPT 후처리 fallback을 사용한다.

참고 출처:

공식 문서:
* [OpenAI Academy: Creating images with ChatGPT](https://openai.com/academy/image-generation/)
* [OpenAI Cookbook: GPT Image 1.5 Prompting Guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide)
* [OpenAI Images API Reference](https://developers.openai.com/api/reference/images)
* [OpenAI model list: GPT Image 2](https://developers.openai.com/api/docs/models/all)

커뮤니티 참고:
* [OpenAI Developer Community: image consistency discussion](https://community.openai.com/t/prompt-to-make-exactly-same-image-but-different-pose/597498)
* [r/generativeAI: prompt library discussion](https://www.reddit.com/r/generativeAI/comments/1tphq1s/what_is_the_state_of_the_art_of_a_prompt_library/)
* [r/promptingmagic: image prompt template discussion](https://www.reddit.com/r/promptingmagic/comments/1o0l87m/the_perfect_image_prompt_template_for_nano_banana/)

학술 참고:
* [A Taxonomy of Prompt Modifiers for Text-To-Image Generation](https://arxiv.org/abs/2204.13988)
* [Design Guidelines for Prompt Engineering Text-to-Image Generative Models](https://arxiv.org/abs/2109.06977)

---

## 3. 공통 생성 원칙

### 3.1 완성형 슬라이드 텍스트 원칙

* 각 이미지는 완성된 16:9 슬라이드 한 장이어야 한다.
* 이미지 안에는 다음 텍스트만 넣는다.
  * 상단 제목 1개
  * 제목 아래 또는 좌측 상단 핵심 문구 1개
  * 다이어그램 라벨 3~8개
* 긴 문장, 표, 수치표, 각주, 많은 bullet은 이미지에 넣지 않는다.
* 한글 텍스트는 프롬프트의 `Exact slide text`에 적힌 문구를 그대로 사용한다.
* 라벨은 가능하면 영문 대문자나 짧은 한글 단어를 사용한다.
* 허용 라벨 예시:

  * `AUDIT`
  * `SPLIT`
  * `MODEL`
  * `HPO`
  * `EVAL`
  * `REVIEW`
  * `SYNTH`
  * `DECIDE`
  * `BLOCK`
  * `GATE`
  * `TRACE`

### 3.2 시각 스타일 원칙

* 모든 페이지는 같은 visual system을 유지한다.
* 권장 기본 톤은 off-white 기반의 미니멀 기술 세미나 스타일이다.
* 선은 얇고 정돈된 charcoal line을 사용한다.
* 강조 색상은 teal과 amber로 제한한다.
* teal은 정상 흐름, 연결, 자동 실행 구간에 사용한다.
* amber는 gate, block, warning, decision에 사용한다.
* 아이콘은 평면 기하학적 형태로 표현한다.
* 실제 사람, 브랜드 로고, 제품 로고, 장식용 마스코트는 사용하지 않는다.

### 3.3 레이아웃 원칙

* 권장 출력은 landscape presentation composition이다.
* 중요한 요소는 중앙 16:9 safe area 안에 배치한다.
* 상단에는 슬라이드 제목, 그 아래에는 핵심 문구를 배치한다.
* 좌측 35~45%는 메시지 영역, 우측 55~65%는 다이어그램 영역으로 나누는 구성을 기본값으로 한다.
* 복잡한 표, 대시보드, UI 스크린샷을 이미지로 만들지 않는다.
* 다이어그램은 3~5개 핵심 요소 중심으로 단순화한다.
* 보조 요소는 작은 아이콘 수준으로 제한한다.

### 3.4 금지 요소

* photorealistic people
* realistic office meeting scene
* cluttered dashboard screenshot
* dense tiny text
* fake UI text
* logos
* mascot
* fantasy imagery
* sci-fi character imagery
* decorative gradient blobs
* excessive neon glow
* complex data table inside image

---

## 4. API 설정 운영 기준

이미지 생성 API의 모델명, 크기, 품질, 배경, 출력 포맷 옵션은 실제 실행 시점의 [OpenAI Images API Reference](https://developers.openai.com/api/reference/images)를 기준으로 확인한다.

v1.2 문서에서는 다음을 권장값으로 둔다.

| 항목            | 권장값                                       | 비고                           |
| ------------- | ----------------------------------------- | ---------------------------- |
| model         | `gpt-image-2` 또는 사용 시점의 최신 GPT Image 모델 | 공식 모델 목록 기준 확인. `gpt-image-1.5`는 previous 모델로만 사용 |
| size          | API가 지원하는 16:9 landscape size          | 미지원 시 가장 가까운 landscape로 생성 후 16:9 crop |
| quality       | `high` 또는 `auto`                          | 비용·시간 기준에 따라 조정              |
| background    | `opaque`                                  | 완성형 슬라이드 이미지용              |
| output_format | `png`                                     | 편집·삽입 안정성 우선                 |
| n             | `1`                                       | 페이지별 후보 생성 시에는 2~4회 반복 생성 권장 |

실행 스크립트에서는 모델별 지원 파라미터를 반드시 검증한다.
지원되지 않는 옵션이 있을 경우, 해당 옵션을 제거하거나 `auto`로 대체한다. 완성형 슬라이드 이미지는 최종 산출물을 반드시 16:9로 맞춘다.

---

## 5. 공통 스타일 블록

각 페이지 프롬프트 끝에 아래 스타일 블록을 붙여 일관성을 유지한다.

```text
Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

## 6. 이미지 생성 에이전트 마스터 지시문

페이지별 프롬프트를 전달하기 전에 아래 지시문을 한 번 설정한다.

```text
You are generating a consistent image set for a 20-page technical seminar deck. Each output must be a finished 16:9 slide image, not a background-only illustration.

Use the same visual language across all pages: minimal vector diagrams, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, thin connectors, and generous whitespace.

Render the exact Korean slide title and exact Korean headline provided in each prompt. Use only the specified short labels. Keep typography large and readable. Avoid long body text, dense bullets, fake UI screenshots, logos, photorealistic people, mascots, sci-fi imagery, decorative gradient blobs, and clutter.

Keep every important element inside a centered 16:9 safe area. Use a consistent layout: title at the top, short headline below, main visual diagram in the center or right side, and optional small labels near diagram nodes.

If Korean text cannot be rendered cleanly, do not simplify or paraphrase it inside the image. Mark the candidate for regeneration, or use the PPT post-processing fallback for that page.
```

---

## 7. 페이지별 핵심 메시지 매핑

| Page | 제목                           | 핵심 메시지                                                      |
| ---: | ---------------------------- | ----------------------------------------------------------- |
|    1 | Title                        | Hermes Kanban은 연구 작업, 에이전트, 산출물, 실험 기록을 하나의 제어 가능한 흐름으로 묶는다 |
|    2 | 왜 24시간 자율 연구 워크플로우가 필요한가     | 연구 자동화는 단순 실행이 아니라 복구 가능한 구조가 필요하다                          |
|    3 | 기존 접근의 한계                    | 노트북, 스크립트, 단일 에이전트만으로는 추적성·복구성·결정 게이트가 부족하다                 |
|    4 | 핵심 아이디어                      | 자율성은 자유 대화가 아니라 구조화된 task graph 안에서 작동해야 한다                 |
|    5 | Hermes Kanban 기본 구조          | 하나의 task card가 상태, 담당, 의존성, 이력, 산출물을 함께 담는다                 |
|    6 | 24시간 자율 Loop                 | 자동 실행 구간과 인간 결정 지점을 분리해 연구 루프를 지속한다                         |
|    7 | Profile 기반 역할 분리             | 구현, 평가, 리뷰, 종합 역할을 분리해 책임 경계를 명확히 한다                        |
|    8 | 추적 가능성 설계                    | 작업은 카드, 실행 이력, 산출물, 실험 기록, 보고서로 연결되어야 한다                    |
|    9 | 통제 가능성 설계                    | 자율 실행은 안전·품질·비용·데이터 기준의 guardrail 안에서만 허용된다                 |
|   10 | 자기진화 메커니즘                    | 다음 사이클은 자동 등록되지만 인간 Gate 전에는 실행되지 않는다                       |
|   11 | Running Example: AI 자동채점 연구  | 자동채점 연구를 예시로 Hermes Kanban의 적용 흐름을 보여준다                     |
|   12 | 자동채점 Cycle 상세                | 연구 단계마다 재현 가능한 산출물이 남아야 한다                                  |
|   13 | 모델 진화 Ladder                 | 모델 성능 개선은 단계별 진단과 비교를 통해 추적한다                               |
|   14 | 실제 Trace 예시                  | 실패와 차단도 산출물로 남겨야 재현 가능한 연구가 된다                              |
|   15 | 실패 사례 1: Split Recovery      | 임시 복구와 최종 정책은 명확히 구분되어야 한다                                  |
|   16 | 실패 사례 2: M5 Remote GPU Block | 과거 M5 sandbox/network block은 모델 실패가 아니라 운영 통제 이벤트로 기록된다           |
|   17 | 평가와 품질 Gate                  | 전체 평균뿐 아니라 취약 구간 기준을 함께 통과해야 한다                             |
|   18 | 인간 개입 최소화                    | 자동화의 목표는 인간 제거가 아니라 인간 개입 지점의 압축이다                          |
|   19 | 배운 점                         | Boundary, Evidence, Recovery가 자율 연구 운영의 핵심이다                |
|   20 | 결론과 다음 단계                    | 연구 루프는 멈춤과 결정을 포함해 다음 사이클로 이어진다                             |

---

## 8. 페이지별 이미지 생성 프롬프트

---

### Page 1. Title

#### 핵심 메시지

Hermes Kanban은 연구 작업, 에이전트, 산출물, 실험 기록을 하나의 제어 가능한 흐름으로 묶는다.

#### Prompt

```text
Create a finished 16:9 technical seminar title slide image.

Exact slide text:
Title: Hermes Kanban 기반 24시간 자율 연구 워크플로우
Subtitle: 추적·통제·복구 가능한 Multi-Agent 연구 시스템
Small caption: Running Example · 한국어 K-12 에세이 자동채점
Presenter: (주) 아이오시스 연구소 AI 개발팀
Name: 수석 연구원 이동명
Date: 2025-05-28

Layout: large title on the left, subtitle beneath it, small caption below. Place presenter, name, and date as compact footer text at bottom-left. On the right, show a central Kanban board connected to five abstract agent nodes and two artifact panels.
Must show: task cards, agent nodes, artifact stream, experiment trace panel.
Do not show: logos, real people, dense dashboard UI, fake extra text.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 2. 왜 24시간 자율 연구 워크플로우가 필요한가

#### 핵심 메시지

연구 자동화는 단순 실행이 아니라 복구 가능한 구조가 필요하다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 장기 연구는 실험보다 운영이 어렵다
Headline: 실행보다 중요한 것은 상태 추적과 복구 구조다
Labels: 실행, 상태, 복구

Layout: title and headline at top-left. Below, split the canvas into two panels. Left panel shows fragmented notebooks and loose task cards using abstract line blocks, not readable logs. Right panel shows the same work as a clean task graph with artifact folders and a decision gate.
Must show: disorder on the left, traceable flow on the right.
Do not show: realistic screens, dense logs, people, extra paragraphs.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 3. 기존 접근의 한계

#### 핵심 메시지

노트북, 스크립트, 단일 에이전트만으로는 추적성·복구성·결정 게이트가 부족하다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 기존 접근의 한계
Headline: 실행 도구는 많지만 연구 상태 복원은 별도 문제다
Labels: Notebook, Script, Cron, Agent, Orchestrator, Tracker

Layout: title and headline at top. Center area has six compact method cards in a 2 by 3 grid. Each card uses one icon and one short label. Show that each method is useful but incomplete for long-running research context by adding subtle gap markers, not harsh warning symbols.
Must show: six method cards, complementary limitation markers, clean comparison structure.
Do not show: full dashboard, code screenshots, product logos, paragraphs.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 4. 핵심 아이디어

#### 핵심 메시지

자율성은 자유 대화가 아니라 구조화된 task graph 안에서 작동해야 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 핵심 아이디어
Headline: 자율성은 자유 대화가 아니라 task graph 안에서 작동한다
Labels: Task, Profile, Artifact, Gate

Layout: title and headline at top-left. Center-right shows a structured task graph. Four large anchor groups surround the graph: task cards, profile nodes, artifact folders, and approval gates. Use thin arrows to connect them.
Must show: controlled graph, task cards, gates, artifacts.
Do not show: chat bubbles as the main metaphor, realistic people, extra text.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 5. Hermes Kanban 기본 구조

#### 핵심 메시지

하나의 task card가 상태, 담당, 의존성, 이력, 산출물을 함께 담는다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: Hermes Kanban 기본 구조
Headline: 하나의 task card가 상태, 담당, 의존성, 이력, 산출물을 함께 담는다
Labels: Status, Assignee, Parent, Run, Comment, Artifact

Layout: title and headline at top. Main visual is one large mock Kanban task card with six clean zones and six callout labels. Keep labels large and sparse.
Must show: card zones and dependency/artifact areas.
Do not show: real product UI, dense labels, logos, fake detailed UI text.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 6. 24시간 자율 Loop

#### 핵심 메시지

자동 실행 구간과 인간 결정 지점을 분리해 연구 루프를 지속한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 24시간 자율 Loop
Headline: 자동 실행 구간과 인간 결정 지점을 분리해 연구 루프를 지속한다
Labels: AUDIT, BUILD, CHECK, DECIDE

Layout: title and headline at top. Main visual is a horizontal pipeline grouped into four labeled bands: AUDIT, BUILD, CHECK, DECIDE. Inside the bands, show small unlabeled stage nodes; include one fork inside CHECK and a thin timeline strip below with one amber BLOCK marker and one DECIDE gate.
Must show: automated segment, fork, synthesis, decision gate.
Do not show: nine readable stage labels, clock-heavy decorative scene, realistic operator, dense annotations.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 7. Profile 기반 역할 분리

#### 핵심 메시지

구현, 평가, 리뷰, 종합 역할을 분리해 책임 경계를 명확히 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: Profile 기반 역할 분리
Headline: 구현, 평가, 리뷰, 종합 역할을 분리해 책임 경계를 명확히 한다
Labels: Data, Build, Eval, Review, Synth, Implement

Layout: title and headline at top-left. Main visual is a six-lane swimlane diagram with role labels Data, Build, Eval, Review, Synth, Implement. Use tiny secondary profile names only if readable: tukey, gauss, spearman, turing, aristotle, ada-lovelace. Evaluation and review lanes should be visually distinct from implementation lanes.
Must show: separation between implementation, evaluation, review, and synthesis.
Do not show: realistic human faces, team meeting, product screenshots.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 8. 추적 가능성 설계

#### 핵심 메시지

작업은 카드, 실행 이력, 산출물, 실험 기록, 보고서로 연결되어야 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 추적 가능성 설계
Headline: 작업은 카드, 실행 이력, 산출물, 실험 기록, 보고서로 연결되어야 한다
Labels: Task, Run, Manifest, MLflow, Report

Layout: title and headline at top. Center area shows a left-to-right traceability chain: task card, run/comment history, workspace manifest, experiment tracker, final report. Use abstract document and folder icons with blank placeholder lines only; do not render fake log text.
Must show: task card, history, manifest, tracker, report.
Do not show: dense log text, spreadsheet-like tables, dashboard screenshot.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 9. 통제 가능성 설계

#### 핵심 메시지

자율 실행은 안전·품질·비용·데이터 기준의 guardrail 안에서만 허용된다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 통제 가능성 설계
Headline: 자율 실행은 안전·품질·비용·데이터 기준의 guardrail 안에서만 허용된다
Labels: DATA, PRIVACY, TRACE, QUALITY, COST, FAIL

Layout: title and headline at top-left. Center visual is one teal research pipeline passing through six compact guardrail chips: DATA, PRIVACY, TRACE, QUALITY, COST, FAIL. Keep chips large enough to read, grouped as a single guardrail layer rather than six separate complex gates. End with a final check marker.
Must show: gates protecting the autonomous pipeline.
Do not show: lock-heavy cybersecurity imagery, shield wall, hacker visuals, many tiny gates.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 10. 자기진화 메커니즘

#### 핵심 메시지

다음 사이클은 자동 등록되지만 인간 Gate 전에는 실행되지 않는다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 자기진화 메커니즘
Headline: 다음 사이클은 자동 등록되지만 인간 Gate 전에는 실행되지 않는다
Labels: SYNTH-M1, DECIDE-M1, AUDIT-M2

Layout: title and headline at top. Main visual is a simple dependency graph: SYNTH-M1 produces recommendations, DECIDE-M1 is an amber human gate, and AUDIT-M2 waits behind that gate. Show the next-cycle chain as locked until DECIDE-M1 opens.
Must show: registered but blocked next cycle.
Do not show: automatic full self-improvement without human gate.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 11. Running Example: AI 자동채점 연구

#### 핵심 메시지

자동채점 연구를 예시로 Hermes Kanban의 적용 흐름을 보여준다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: Running Example · AI 자동채점 연구
Headline: 자동채점 연구를 예시로 Hermes Kanban의 적용 흐름을 보여준다
Labels: Essays, Features, Models, Eval

Layout: title and headline at top-left. Main visual is an anonymized essay stack flowing into feature extraction, a model ladder, and an evaluation report. Add three tiny segment icons for grade group, essay type, and score band.
Must show: anonymized essays, model process, evaluation output.
Do not show: classroom scene, real students, personal data, dense rubric table.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 12. 자동채점 Cycle 상세

#### 핵심 메시지

연구 단계마다 재현 가능한 산출물이 남아야 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 자동채점 Cycle 상세
Headline: 연구 단계마다 재현 가능한 산출물이 남아야 한다
Labels: AUDIT, BUILD, CHECK, SYNTH, DECIDE

Layout: title and headline at top. Center has a circular cycle diagram grouped into five labeled segments: AUDIT, BUILD, CHECK, SYNTH, DECIDE. Inside the segments, use small unlabeled artifact icons to imply split, feature, model, HPO, eval, and review without adding more text.
Must show: artifact generated at each stage.
Do not show: full metric tables, code windows, dense pipeline text.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 13. 모델 진화 Ladder

#### 핵심 메시지

모델 성능 개선은 단계별 진단과 비교를 통해 추적한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 모델 진화 Ladder
Headline: 모델 성능 개선은 단계별 진단과 비교를 통해 추적한다
Labels: M1, M2, M3, M4, M5 Pending, M6 Pending, Diagnostic

Layout: title and headline at top-left. Main visual is a six-step ladder. M1 to M4 are solid completed steps, while M5 Pending and M6 Pending are greyed or locked future steps. Add a small abstract trend line only over M1 to M4 and one caution badge labeled Diagnostic.
Must show: completed M1-M4, pending M5-M6, diagnostic nature.
Do not show: detailed metric table, exact score values, crowded chart axes.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 14. 실제 Trace 예시

#### 핵심 메시지

실패와 차단도 산출물로 남겨야 재현 가능한 연구가 된다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 실제 Trace 예시
Headline: 실패와 차단도 산출물로 남겨야 재현 가능한 연구가 된다
Labels: t_dcecd4b1, Summary, Manifest, BLOCK, Queue

Layout: title and headline at top. Center visual shows one task card labeled t_dcecd4b1 connected to three evidence documents and a downstream waiting queue. Use a calm amber BLOCK marker.
Must show: blocked task connected to evidence.
Do not show: emergency warning scene, red alarm, chaotic failure visuals.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 15. 실패 사례 1: Split Recovery

#### 핵심 메시지

임시 복구와 최종 정책은 명확히 구분되어야 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 실패 사례 1 · Split Recovery
Headline: 임시 복구와 최종 정책은 명확히 구분되어야 한다
Labels: k=3 Recovery, Gate, k=5 Policy

Layout: title and headline at top-left. Main visual is a flow from uneven location groups to an amber k=3 Recovery evidence artifact, then a human Gate, then a teal current k=5 Policy path. Make the temporary recovery and final policy visually distinct.
Must show: k=3 recovery evidence separated from current k=5 policy.
Do not show: dense statistical chart, map details, spreadsheet table.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 16. 실패 사례 2: M5 Remote GPU Block

#### 핵심 메시지

과거 M5 sandbox/network block은 모델 실패가 아니라 운영 통제 이벤트로 기록된다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 실패 사례 2 · M5 Remote GPU Block
Headline: 과거 M5 sandbox/network block은 운영 통제 이벤트로 기록된다
Labels: Worker, GPU, Policy Gate, M5, Queue

Layout: title and headline at top. Main visual is a historical cause-chain: worker node attempts to reach remote GPU, amber sandbox/network policy gate blocks path, M5 pauses, downstream queue waits. Add three tiny check icons for credential, cost, teardown.
Must show: blocked path and waiting queue.
Do not show: detailed cloud console, credentials, pricing table, server room, too many downstream nodes.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 17. 평가와 품질 Gate

#### 핵심 메시지

전체 평균뿐 아니라 취약 구간 기준을 함께 통과해야 한다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 평가와 품질 Gate
Headline: 전체 평균뿐 아니라 취약 구간 기준을 함께 통과해야 한다
Labels: High 90%+, Macro, Worst, Gate

Layout: title and headline at top-left. Main visual shows one score-band distribution bar labeled High 90%+, then two simplified metric panels labeled Macro and Worst flowing into a quality gate. Keep it chart-like but large and readable.
Must show: high-band imbalance and gate-based acceptance.
Do not show: dense formulas, tiny axis labels, full metric table, confusion matrix.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 18. 인간 개입 최소화

#### 핵심 메시지

자동화의 목표는 인간 제거가 아니라 인간 개입 지점의 압축이다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 인간 개입 최소화
Headline: 자동화의 목표는 인간 제거가 아니라 개입 지점의 압축이다
Labels: AUTO, DECIDE, BLOCK, Gate

Layout: title and headline at top. Main visual is a 24-hour timeline with long teal automated segments, one normal DECIDE marker, and small amber exception markers for policy change, remote GPU operation, cost, and security.
Must show: compressed human intervention.
Do not show: human replaced by machine metaphor, humanoid robot, control room.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 19. 배운 점

#### 핵심 메시지

Boundary, Evidence, Recovery가 자율 연구 운영의 핵심이다.

#### Prompt

```text
Create a finished 16:9 technical seminar slide image.

Exact slide text:
Title: 배운 점
Headline: Boundary, Evidence, Recovery가 자율 연구 운영의 핵심이다
Labels: Boundary, Evidence, Recovery

Layout: title and headline at top. Center has three evenly spaced pillars. Boundary is a guardrail, Evidence is a linked artifact chain, Recovery is a paused task resuming into the next step.
Must show: guardrail, artifact chain, resumed task.
Do not show: motivational poster style, decorative icons, dense explanation.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

### Page 20. 결론과 다음 단계

#### 핵심 메시지

연구 루프는 멈춤과 결정을 포함해 다음 사이클로 이어진다.

#### Prompt

```text
Create a finished 16:9 technical seminar closing slide image.

Exact slide text:
Title: 자율 연구는 agent가 아니라 workflow system이다
Headline: 멈췄을 때도 사람이 이해하고 다시 시작할 수 있어야 한다
Small caption: Full mid-scale end-to-end 검증은 다음 단계
Labels: Loop, Block, Decide, Next

Layout: large closing message on the left with small caveat caption below. Right side has a research cycle looping into the next cycle through a controlled decision gate. Include one block marker and two artifact/report nodes.
Must show: loop, pause, decision, continuation.
Do not show: endless spiral, chaotic network, celebratory mascot.

Style: finished 16:9 technical seminar slide, minimal editorial vector design, off-white background, charcoal typography and linework, subtle grid, restrained teal and amber accents, flat geometric shapes, thin connectors, generous whitespace, professional research-lab mood. Clean Korean typography, crisp readable slide title, short readable headline, sparse labels only. No logos, no realistic people, no dense tiny text, no fake UI text, no decorative blobs, no photorealism.
```

---

## 9. 이미지 결과 검수 기준

생성된 이미지는 다음 기준으로 합격, 수정, 폐기 여부를 판단한다.

### 9.1 공통 검수 기준

| 항목       | 합격 기준                                                |
| -------- | ---------------------------------------------------- |
| 슬라이드 적합성 | 16:9 슬라이드에 배치했을 때 핵심 구조가 잘리지 않는다                     |
| 제목       | 슬라이드 제목이 정확하고 크게 읽힌다                                  |
| 핵심 문구    | headline이 정확하고 한 줄 또는 두 줄로 안정적으로 배치된다                 |
| 텍스트      | 한글 오탈자, 깨진 가짜 텍스트, 의미 없는 작은 글자가 없다                   |
| 스타일      | off-white 배경, charcoal line, teal/amber accent가 유지된다 |
| 복잡도      | 한 장에 주요 개념이 과도하게 들어가지 않는다                            |
| 메시지      | 페이지 제목 없이도 핵심 메타포가 어느 정도 구분된다                        |
| 일관성      | 다른 페이지와 선 두께, 아이콘 밀도, 색상 체계가 크게 다르지 않다               |
| 금지 요소    | 로고, 실제 사람, 복잡한 UI, 장식용 캐릭터가 없다                       |

### 9.2 수정 필요 기준

다음 경우에는 같은 프롬프트를 조정해 재생성한다.

* 이미지 내부에 깨진 글자가 많이 생긴 경우
* 제목 또는 headline의 한글 오탈자가 있는 경우
* 핵심 구조가 너무 작아 PPT에서 보이지 않는 경우
* 페이지별 핵심 메시지와 다른 메타포가 생성된 경우
* 색상이 과도하게 화려해진 경우
* 요소 수가 많아 발표용 이미지로 복잡한 경우
* 실제 사람, 로봇, 제품 로고처럼 원하지 않는 요소가 들어간 경우

### 9.3 폐기 기준

다음 경우에는 결과를 폐기하고 프롬프트를 다시 작성한다.

* 전체 구도가 PPT 메시지와 맞지 않는 경우
* 시각 스타일이 완전히 다른 경우
* 실제 인물 또는 브랜드처럼 보이는 요소가 중심에 들어간 경우
* 이미지가 표, 대시보드, UI 스크린샷처럼 보이는 경우
* 생성된 텍스트 오류가 이미지 전체에 퍼져 수정이 어려운 경우
* 제목 또는 핵심 문구가 원문과 달라 의미가 바뀐 경우

---

## 10. 반복 생성 운영 팁

1. 먼저 Page 1과 Page 6을 생성해 visual system과 한글 타이포그래피 품질을 확정한다.
2. 마음에 드는 결과를 style reference로 저장한다.
3. 나머지 페이지 생성 시 다음 문장을 추가한다.

```text
Match the same layout language, line weight, color palette, icon style, and whitespace rhythm as the reference image.
```

4. 결과가 복잡하면 다음 방식으로 한 번에 하나씩 수정한다.

```text
Reduce the number of elements by 30%. Keep only the main graph and three supporting icons.
```

5. 이미지에 불필요한 글자가 많이 생기면 다음 문장을 추가한다.

```text
Remove all extra text. Keep only the exact title, exact headline, and specified short labels.
```

6. 한글 오탈자가 생기면 다음 문장을 추가한다.

```text
Regenerate with special attention to exact Korean typography. Render only the specified Korean title and headline. Do not invent or paraphrase Korean text.
```

7. 페이지 간 스타일이 흔들리면 다음 문장을 추가한다.

```text
Use the same off-white background, charcoal line weight, restrained teal and amber accents, and simple geometric icon style as the previous approved image.
```

8. 생성 결과와 exact prompt를 같은 폴더 또는 보드에 함께 저장한다.

---

## 11. 권장 산출물 저장 구조

```text
assets/
  seminar-hermes-kanban/
    prompts/
      page_01_prompt_v1_2.md
      page_02_prompt_v1_2.md
      ...
      page_20_prompt_v1_2.md
    generated/
      page_01_candidate_01.png
      page_01_candidate_02.png
      ...
    approved/
      page_01_approved.png
      page_02_approved.png
      ...
    references/
      style_reference_page_01.png
      style_reference_page_06.png
    review/
      image_generation_review_log_v1_2.md
```

---

## 12. 이미지 생성 리뷰 로그 양식

````markdown
# Image Generation Review Log v1.2

## Page
- Page No:
- Page Title:
- Prompt Version:
- Source Deck Version:
- Prompt File Path:
- Candidate No:
- Generated At:
- Model:
- Model Snapshot:
- Size:
- Quality:
- Output Format:
- Output Image Path:
- Approved Asset Path:
- Reviewer:

## Review
| 항목 | 결과 | 메모 |
|---|---|---|
| 16:9 safe area | PASS / FAIL |  |
| slide title readability | PASS / FAIL |  |
| visual consistency | PASS / FAIL |  |
| exact title text | PASS / FAIL |  |
| exact headline text | PASS / FAIL |  |
| no extra dense text | PASS / FAIL |  |
| message fit | PASS / FAIL |  |
| complexity | PASS / FAIL |  |
| prohibited elements | PASS / FAIL |  |

## Decision
- APPROVE
- REGENERATE
- DISCARD

## Revision Reason
- Reason:

## Revision Instruction
```text
Write revision instruction here.
```
````

---

## 13. v1.2 적용 우선순위

| 우선순위 | 작업 |
|---:|---|
| 1 | Page 1, Page 6 생성 후 스타일과 한글 타이포그래피 기준 확정 |
| 2 | Page 9, 16, 17 단순화 프롬프트 우선 검증 |
| 3 | 나머지 페이지 일괄 생성 |
| 4 | 제목/headline 오탈자와 레이아웃 기준으로 승인 이미지 선별 |
| 5 | 필요 시 오탈자 페이지만 재생성 또는 PPT 후처리 fallback 결정 |
| 6 | 이미지와 exact prompt를 함께 보관 |
| 7 | 필요 시 v1.3에서 실제 생성 결과 기반 프롬프트 개정 |

---

## 14. 결론

v1.2는 Hermes Kanban 세미나용 20페이지 완성형 슬라이드 이미지 생성을 위한 운영 가능한 프롬프트 문서이다.

이 문서는 단순 이미지 설명이 아니라, 다음 세 가지를 함께 관리한다.

1. 세미나 전체 시각 언어
2. 페이지별 핵심 메시지와 이미지 메타포
3. 생성 결과의 텍스트·레이아웃 검수 및 반복 개선 기준

따라서 실제 이미지 생성 작업에서는 v1.2를 기준으로 Page 1과 Page 6을 먼저 생성하고, 승인된 이미지를 스타일·타이포그래피 레퍼런스로 삼아 나머지 페이지를 순차 생성한다.
