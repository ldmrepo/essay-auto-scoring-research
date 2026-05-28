# Multi-task 루브릭별 채점 모델 구현 스펙

> **버전**: v1.0
> **작성 일자**: 2026-05-28
> **목적**: 현재 single-target (`essay_scoreT_avg` 1개)으로 학습되는 M5 KLUE-RoBERTa를 루브릭별 multi-task 모델로 확장하기 위한 구현 스펙
> **선행 문서**: `dataset_채점방식_분석_v_1_0.md` (v1.1) — 데이터셋 루브릭 구조 분석
> **상태**: 제안 (구현 전, Cycle M2+ 대상)

---

## 1. 핵심 아이디어

**1 출력 → N 출력으로 확장.** 모든 인프라(인코더, 손실, 평가)는 그대로, head와 타겟만 다중화.

```
[기존]
RoBERTa → [CLS] → Linear(768→1) → essay_scoreT_avg

[변경]
RoBERTa → [CLS] → Linear(768→N) → [exp, org, cont, ...] 동시 출력
                                    가중합 → overall (필요 시)
```

---

## 2. 출력 단위 선택 (3가지)

| 단위 | 출력 N | 장점 | 단점 |
|---|---:|---|---|
| **대분류** | 3 (exp/org/cont) | 단순, 안정 | 정보 손실 일부 |
| **소분류** | 9~11 (학년군별 다름) | 가장 풍부한 신호 | 학년군별 가변, 처리 복잡 |
| **하이브리드** | 3 + overall | overall 단조 진화 + 차원별 진단 | head 2개 |

→ **권장: 대분류 3 + overall 1 = 4 출력** (단순성 + Phase 2 단조 진화 호환)

---

## 3. 손실 함수

```python
# 가중 MSE (각 대분류 + overall)
loss = (
    w_exp  * MSE(pred_exp,  true_exp)  +
    w_org  * MSE(pred_org,  true_org)  +
    w_cont * MSE(pred_cont, true_cont) +
    w_all  * MSE(pred_all,  true_all)     # auxiliary, 단조 진화용
)
```

- `w_*` 가중치는 JSON `rubric` 필드(에세이별 대분류 가중치 3:3:4 or 4:2:4)에서 동적 로드
- **PDF spec drift 자동 회피** (초5 논술형 등 spec 불일치 케이스도 JSON 가중치로 정확 처리)

---

## 4. 변경 범위 (최소 침습)

| 파일 | 변경 |
|---|---|
| `pipelines/train.py` | `TARGET_NAME` → `TARGET_NAMES = [exp, org, cont, avg]` |
| `pipelines/train_transformer.py` | `num_labels=1` → `num_labels=4` + custom loss |
| `pipelines/evaluate.py` | per-rubric metric 4종 + per-rubric fairness gate |
| `MILESTONE_v2.md` | acceptance criteria 차원별 추가 |
| `ACCEPTANCE_CRITERIA.yaml` | per-rubric threshold |

기존 M1~M4(CPU baseline)는 single-target 유지 → **M5만 multi-task 전환**, M6도 multi-output OOF stacking.

---

## 5. 단조 진화 (Hard Rule #5) 처리

| 모델 | 단조 비교 단위 |
|---|---|
| M1~M4 | overall QWK만 |
| M5 | overall QWK (auxiliary head) + 차원별 QWK 보고 |
| M6 | overall QWK (ensemble) |

→ Hard Rule #5의 strict 비교는 overall로 유지하되, **차원별 QWK는 진단 정보로 EVAL/REVIEW에 추가**.

---

## 6. Acceptance 기준 확장

| 기준 | 추가 |
|---|---|
| **#1 단일 QWK ≥ 0.40** | overall 기준 유지 |
| **#1a 차원별 QWK ≥ 0.30** | exp/org/cont 각각 |
| **#14 fairness gate** | 차원별 적용 (각 대분류의 worst_band_qwk ≥ macro_qwk × 0.7) |

---

## 7. 데이터 처리

각 에세이당:

```python
# 채점자 3명의 가중 평균을 각 대분류별로 따로 계산
def compute_rubric_targets(essay_json):
    detail = essay_json["score"]["essay_scoreT_detail"]
    rubric = essay_json["rubric"]

    # 각 대분류별 소분류 가중치 (JSON에서 직접 로드, PDF 무관)
    exp_w = [
        rubric["expression_weight"]["exp_grammar"],
        rubric["expression_weight"]["exp_vocab"],
        rubric["expression_weight"]["exp_style"],
    ]
    org_w = [
        rubric["organization_weight"]["org_paragraph"],
        rubric["organization_weight"]["org_essay"],
        rubric["organization_weight"]["org_coherence"],
        rubric["organization_weight"]["org_quantity"],
    ]
    cont_w = [
        rubric["content_weight"]["con_clearance"],
        rubric["content_weight"]["con_description"],
        rubric["content_weight"]["con_novelty"],
        rubric["content_weight"]["con_prompt"],
    ]

    # 채점자 3명별 정규화 점수 → 평균
    def avg_normalized(scores_per_rater, weights):
        per_rater = [
            sum(s * w for s, w in zip(rater, weights)) / sum(weights)
            for rater in scores_per_rater
        ]
        return sum(per_rater) / len(per_rater)

    return {
        "exp": avg_normalized(detail["essay_scoreT_exp"], exp_w),     # 0~3
        "org": avg_normalized(detail["essay_scoreT_org"], org_w),     # 0~3
        "cont": avg_normalized(detail["essay_scoreT_cont"], cont_w),  # 0~3
        "overall": essay_json["score"]["essay_scoreT_avg"],            # 0~30
    }
```

학습 타겟 = `(exp, org, cont, overall)` 4차원 벡터.

---

## 8. 점진 도입 단계

| 단계 | 작업 | 우선순위 |
|---|---|---|
| **A** | 대분류 3+1 multi-output head + 가중 MSE (Cycle M2에서 신규 구현) | 최우선 |
| **B** | per-rubric evaluate.py + acceptance 차원별 추가 | A와 동시 |
| **C** | 차원별 단조 진화 진단 (정보 보고만, hard-block 아님) | A 이후 |
| **D** | 소분류 9~11 head로 확장 (Cycle M3+, 충분한 데이터 검증 후) | 중기 |
| **E** | paragraph_score auxiliary task 추가 | 중기 |
| **F** | 채점자 분산 → uncertainty-aware loss | 장기 |

---

## 9. 즉시 가치

| 영역 | 단일 타겟 | Multi-task |
|---|---|---|
| 채점 정확도 | overall QWK 0.40+ 목표 | 각 차원 0.30+ + overall 0.40+ (학습 신호 풍부 → 수렴 빠름) |
| 진단 | "글이 잘못됐다" 1차원 | "표현 약함 / 구성 좋음 / 내용 보통" 3차원 |
| 학생/교사 피드백 | 단일 점수 | 차원별 강약점 |
| 데이터 활용 | 1/99 정보 | 3~11/99 정보 |

---

## 10. 위험과 완화

| 위험 | 완화 |
|---|---|
| Multi-task loss 균형 (차원별 학습 어려움 차이) | 가중치 적응 (PCGrad, GradNorm 등) — 다만 Phase 2엔 균등 weight로 충분 |
| Phase 2 acceptance 단일 기준이라 평가 인프라 충돌 | overall(4번째 head)로 단조 진화 호환 유지 |
| 학년군별 가중치 다름 → batch 내 mixed | JSON `rubric`에서 per-essay 동적 가중치 |
| 모델 복잡도 증가 → overfitting | dropout 적용 + 작은 head (768→4) |
| 소분류 슬롯 매핑 미명시 (PDF/spec 누락) | 가설(grammar/vocab/style 순) + 학년군별 데이터로 역추정 검증 |
| Data spec drift (초5 논술형 등) | JSON `rubric` 가중치 source of truth로 사용 → PDF spec 의존 제거 |

---

## 11. 구현 핵심 코드 (의사)

### 11.1 train_transformer.py 수정

```python
def model_init():
    return AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=4,  # exp, org, cont, overall
        problem_type="regression",
    )

class WeightedMSEMultiTaskTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False):
        labels = inputs.pop("labels")        # (batch, 4)
        macro_weights = inputs.pop("macro_weights")  # (batch, 4) — exp/org/cont 가중치 + overall=1
        outputs = model(**inputs)
        preds = outputs.logits               # (batch, 4)
        loss = ((preds - labels) ** 2 * macro_weights).mean()
        return (loss, outputs) if return_outputs else loss
```

### 11.2 evaluate.py 수정

```python
def fairness_gate_per_rubric(predictions, rng, bootstrap_b):
    out = {}
    for rubric in ["exp", "org", "cont", "overall"]:
        out[rubric] = fairness_gate(
            predictions[predictions["rubric"] == rubric],
            rng, bootstrap_b
        )
    return out
```

### 11.3 ACCEPTANCE_CRITERIA.yaml 수정

```yaml
mid:
  m5_overall_qwk_lower95: 0.40
  m5_per_rubric_qwk_lower95: 0.30    # 신규
  fairness_gate_ratio: 0.7
  fairness_gate_per_rubric: true     # 신규
```

---

## 12. 후속 결정 사항

본 스펙 도입 결정 후 사용자가 답해야 할 항목:

1. **출력 단위**: 대분류 3+1 (권장) vs 소분류 9~11 vs 하이브리드
2. **도입 시점**: Cycle M2 시작 vs M3 vs Phase 3 진입
3. **acceptance 추가**: 차원별 QWK ≥ 0.30 (기본) vs 다른 임계값
4. **fairness gate 차원별**: 각 대분류 모두 적용 vs overall만 유지
5. **소분류 슬롯 매핑 검증**: 별도 sprint로 진행 vs A 단계 안에 포함

---

## 부록 A: 출처

- `dataset_채점방식_분석_v_1_0.md` (v1.1) — 데이터셋 분석 및 검증
- `dataset/루브릭 설명서_v0.3.pdf` — 가중치 spec
- `dataset/1-15_에세이 글 데이터_데이터 설명서.pdf` — JSON 스키마
- `pipelines/train_transformer.py` — 현재 single-target 구현
- `pipelines/train.py` — TARGET_NAME, train_transformer_model
- `MILESTONE_v2.md` — Phase 2 acceptance criteria
- `AGENTS.md` — Hard Rule #5 (단조 진화), #14 (Score-Band Fairness Gate)
