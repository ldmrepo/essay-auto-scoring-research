# Multi-task 루브릭별 채점 모델 구현 스펙

> **버전**: v1.1.5 (v1.1.4 + R1 5차 재검수 6건 fix)
> **작성 일자**: 2026-05-28 (v1.0 → v1.1 → v1.1.1 → v1.1.2 → v1.1.3 → v1.1.4 → v1.1.5)
> **목적**: M5 KLUE-RoBERTa를 single-target (`essay_scoreT_avg` 1개)에서 루브릭별 multi-task 모델로 확장
> **선행 문서**: `dataset_채점방식_분석_v_1_0.md` v1.1 — 데이터셋 루브릭 구조 분석 (검증 완료)
> **상태**: Phase 3 진입 스펙 (Cycle M2 시작 기준, 구현 wire-up 전)
> **변경 이력**:
> - v1.0 (2026-05-28): 초안. Phase 2 종료 + Phase 3 방향 확정 시 작성
> - v1.1 (2026-05-28): 외부 리뷰 6건 반영. D1~D6 결정 적용. 권장 표현 → 결정 사항 명시
> - v1.1.1 (2026-05-28): R1 검수 fix — T1-09 (w_overall 모듈 상수화), T1-10 (`w_exp/w_org/w_cont` 산출 식), T1-11 (인덱스-키 매핑 가드), T2-11 (M6 단위 명시), T2-12 (Hard Rule cross-ref), T3-03~T3-07
> - v1.1.2 (2026-05-28): R1 재검수 7건 fix — NF2 (M6 stacking 주석 모순), NF3 (손실 .mean() 분모 .sum/.mean으로 정정), NF4 (M1/M2 배제 사유), NF5 (compute_rubric_targets fallback 의도 명확화 — fatal 채택), NF6 (소분류 key 검증 의무), NF7 (M6 OOF fold loop), NF1 (AGENTS.md cross-ref line 번호 정확)
> - v1.1.3 (2026-05-28): R1 3차 재검수 7건 fix — NNF1 (extract_5k에 validate_rubric_for_phase3 추가), NNF2 (M6 inference k-fold ensemble average), NNF3 (보조 anchor 정정), NNF4 (V1 시나리오 타입×학년군 매트릭스 8 셀), NNF5 (overall_weight key fallback-only 명시), NNF6 (M4 출력 spec 단일화), NNF7 (essay_scoreT_detail path 명시)
> - v1.1.4 (2026-05-28): R1 4차 재검수 4건 fix — REG-H1 (extract_5k._main loop 통합 + --validate-rubric flag), REG-M1 (_build_stacking_features ndim 분기 정리), REG-M2 (predict_m6_inference metas contract docstring), REG-M3 (§ 7.1 grade_group key drift 정정 — student_grade_group)
> - v1.1.5 (2026-05-28): R1 5차 재검수 6건 fix — NEW-R1 (extract_5k argparse `--validate-rubric` 등록), NEW-R2 (§ 7.3 재생성 명령에 flag 추가), NEW-R3 (`_build_stacking_features` 이중 정의 제거), NEW-R5 (Phase 3 진입 시 ON 강제 정책 명시)

---

## 0. v1.1 변경 요약 (외부 리뷰 6건 + D1~D6 결정 반영)

| # | v1.0 미반영 | v1.1 처리 |
|---|---|---|
| R1 | 손실 스케일 차원 간 불일치 (overall 0~30 vs 대분류 0~3) | § 3 — overall 0~3 정규화 (D2 채택) |
| R2 | M6 변경 범위 모호 ("multi-output OOF stacking"만 명기) | § 4, § 12 — scalar 폐기 + multi-output OOF 명세 (D6 채택) |
| R3 | fairness gate 차원별 정의 없음 ("적용" 수준) | § 6, § 12.4 — 차원별 worst_band hard-block 정의 (D1 채택) |
| R4 | pseudocode에 입력 컬럼 누락 | § 7, § 11 — 입력 컬럼 명시 (`text`, `prompt_text`, `grade_group`, `rubric`) |
| R5 | acceptance에 `lower95` 명시 안 됨 (점추정 vs CI 불명확) | § 6 — `qwk_lower95` 명시 (Hard Rule #5/#8과 정합) |
| R6 | "권장" 표현 다수 — 결정과 검토 사항 혼재 | 전 섹션 — 결정 사항은 단언 / 검토 항목은 § 13에 분리 |

D1~D6 채택 결과:

| # | 결정 | 적용 절 |
|---|---|---|
| **D1** | 차원별 worst_band hard-block | § 6, § 12.4 |
| **D2** | overall 0~3 정규화 (차원과 동일 스케일) | § 3, § 7 |
| **D3** | 하이브리드 3+overall (대분류 3 + 보조 overall) | § 2, § 11 |
| **D4** | 5K 재사용 (Phase 2 inheritance) | § 7 |
| **D5** | klue/roberta-small (Phase 2 inheritance) | § 11 |
| **D6** | scalar 폐기 + multi-output OOF 재작성 | § 4, § 12.3 |

**구현 상태 주의 (2026-05-28 현재)**:
본 문서는 Phase 3 M2에서 구현할 target spec이다. 현재 repo 코드는 아직 Phase 2 single-target 경로가 기본이다:
`pipelines/train.py`는 `essay_scoreT_avg`, `pipelines/train_transformer.py`는 `num_labels=1`, `pipelines/train_ensemble.py`는 scalar OOF stacking을 사용한다. 따라서 `ACCEPTANCE_CRITERIA.yaml`의 `mid_multitask._implementation_status`가 `wired_v1`로 바뀌기 전까지 본 문서를 code-ready 상태로 해석하면 안 된다.

---

## 1. 핵심 아이디어

1 출력 → N 출력으로 확장. 인코더, 학습 인프라, 평가 인프라는 그대로, **출력 head와 타겟만 다중화**.

```
[Phase 2 (single-target)]
RoBERTa → [CLS] → Linear(768 → 1) → essay_scoreT_avg (0~30)

[Phase 3 (multi-task, hybrid 3+overall)]
RoBERTa → [CLS] → Linear(768 → 4) → [exp, org, cont, overall_norm] (모두 0~3)
                                     ↓
                                     단조 진화 비교용 overall_norm 보조 head
```

---

## 2. 출력 단위 결정 (D3)

| 단위 | 출력 N | v1.1 채택 |
|---|---:|---|
| 대분류 only | 3 (exp/org/cont) | ✗ |
| 소분류 | 9~11 (학년군별 가변) | 단계 D로 보류 |
| **하이브리드** | **3 + overall = 4** | **✓ (Phase 3 default)** |

이유: ① Phase 2 단조 진화 (Hard Rule #5) 호환 유지를 위해 overall head 필요. ② 차원별 진단/피드백 신호 확보. ③ 소분류 9~11 슬롯 매핑은 PDF 명세에 부재하므로 단계 D로 보류.

---

## 3. 손실 함수 (D2 — overall 0~3 정규화)

### 3.1 스케일 정규화

| 차원 | 원본 범위 | 정규화 후 (학습 타겟) | 정규화 식 |
|---|---|---|---|
| exp | 0~3 | 0~3 (그대로) | `target_exp = avg_norm(detail.essay_scoreT_exp, exp_weights)` |
| org | 0~3 | 0~3 (그대로) | `target_org = avg_norm(detail.essay_scoreT_org, org_weights)` |
| cont | 0~3 | 0~3 (그대로) | `target_cont = avg_norm(detail.essay_scoreT_cont, cont_weights)` |
| overall | 0~30 | **0~3** | `target_overall = essay_scoreT_avg / 10.0` |

평가 보고 시점에 `pred_overall_raw = pred_overall_norm × 10`로 역변환 (원본 단위 QWK 호환).

### 3.2 손실 식

```python
loss = (
    w_exp     * MSE(pred_exp,     target_exp)     +
    w_org     * MSE(pred_org,     target_org)     +
    w_cont    * MSE(pred_cont,    target_cont)    +
    w_overall * MSE(pred_overall, target_overall_norm)
)
```

| 가중치 | 값 | 출처 |
|---|---|---|
| `w_exp`, `w_org`, `w_cont` | JSON `rubric` 대분류 가중치 (per-essay 동적, T1-10 § 7.2 참조) | `essay_json["rubric"]["expression_weight"]["exp"]` 등 첫 키 |
| `w_overall` | **`W_OVERALL_DEFAULT = 0.5`** (모듈 상수, T1-09 fix) | `pipelines/train_transformer.py` 모듈 상수. § 13 D7 변경 시 단일 지점 update + dataset-level `w_overall` 컬럼이 있으면 그 값 우선 |

이유: ① 차원별 head와 overall head 모두 동일 스케일(0~3)이므로 MSE 항이 매크로 평균과 동등하게 기여. ② `w_overall=1.0`이면 overall head가 차원별 학습 신호를 압도 (Phase 2 inheritance 답습) → 0.5로 다운가중.

**T1-09 fix (R1-F1 magic number 모순 해소)**:
- `w_overall=0.5`는 `pipelines/train_transformer.py` 상단의 `W_OVERALL_DEFAULT` 모듈 상수로 단일화
- `compute_rubric_targets`가 반환하는 dict에 `w_overall` 키를 포함 (per-essay dynamic 가능). 없으면 모듈 상수 fallback
- § 13 D7 결정 시 모듈 상수 1곳만 수정하면 collator + trainer 자동 일관

**T3-04 / R1-NF3 fix (손실 식 ↔ 코드 분모 일관성)**:
- 이전 v1.1.1 코드 `((preds - labels) ** 2 * macro_weights).mean()`은 `(B, 4)` element-wise 곱 후 전체 `.mean()` → 분모 = B×4
- 결과: `w_overall=0.5`가 차원당 합산이 아닌 batch×차원 평균으로 추가 1/4 down-weight되어 실효 0.125
- v1.1.2 결정: **`.sum(dim=1).mean()`으로 정정** (차원 4 분모 제거 + batch B 분모 유지)
- 정정 코드: `((preds - labels) ** 2 * macro_weights).sum(dim=1).mean()`
- 이로써 수식 (`w_exp * MSE + ...`)와 코드가 동일 의미. `w_overall=0.5`가 의도된 가중치 그대로 적용

---

## 4. 변경 범위 (D6 — M6 multi-output OOF)

| 파일 | Phase 2 (v1.0 기준) | Phase 3 v1.1 변경 |
|---|---|---|
| `pipelines/train.py` | `TARGET_NAME = "essay_scoreT_avg"` (str 1개) | `TARGET_NAMES = ["exp", "org", "cont", "overall_norm"]` (List[str] 4개) + `compute_rubric_targets(essay_json)` 헬퍼 |
| `pipelines/train_transformer.py` | `num_labels=1`, MSE | `num_labels=4`, `WeightedMSEMultiTaskTrainer` (custom loss + dataset collator multi-label) |
| `pipelines/train_ensemble.py` | OOF Ridge stacking, **scalar** (Phase 2 v1.0의 b16b5b3 commit 기준) | **scalar 인터페이스 폐기**. multi-output OOF stacking으로 전면 재작성. `fold_predictions: dict[model_id, list[{fold, y_true: (N,4), y_pred: (N,4)}]]` |
| `pipelines/evaluate.py` | overall metric + score_band fairness gate (Phase 2 Hard Rule #14) | per-rubric metric 4종 + per-rubric fairness gate 4종 |
| `ACCEPTANCE_CRITERIA.yaml` | mid 섹션 overall threshold | mid 섹션에 `m5_per_rubric_qwk_lower95: 0.30`, `fairness_gate_per_rubric: true` 추가 |
| `MILESTONE_v3.md` | placeholder | success criteria 차원별 명시 |
| `AGENTS.md` | Hard Rule #1~#14 | Hard Rule #15 (multi-task only) / #16 (long-running off-worker) / #17 (progress observability) / #18 (auto-backup) 추가 |

### 4.1 M1~M4 처리

| 모델 | Phase 3 처리 |
|---|---|
| M1 dummy | scalar 유지 (overall만, 비교 floor) |
| M2 length | scalar 유지 (회귀 baseline) |
| M3 TF-IDF+Ridge | scalar 유지. 단, multi-output Ridge 옵션 (`MultiOutputRegressor`)으로 확장 가능 — § 13 D8 |
| M4 LightGBM | scalar 유지. 단, 차원별 모델 4개로 확장 가능 — § 13 D8 |
| **M5 KLUE-RoBERTa** | **multi-task (3+overall)** |
| **M6 Ensemble** | **multi-output OOF Ridge** (각 차원별 stacking) |

---

## 5. 단조 진화 (Hard Rule #5) 처리

| 모델 | 단조 비교 단위 |
|---|---|
| M1~M4 | overall QWK (Phase 2 동일) |
| **M5** | overall QWK (auxiliary head) + **차원별 QWK 보고** |
| **M6** | overall QWK (overall ensemble) + 차원별 QWK 보고 |

→ Hard Rule #5의 strict 비교(`lower95 > prev_upper95`)는 **overall로 유지**하되, 차원별 QWK는 진단 정보로 EVAL/REVIEW에 첨부. 차원별 단조 진화는 hard-block이 아닌 정보 보고 (Phase 3 기준, § 13 D9에서 hard-block 승격 검토).

---

## 6. Acceptance 기준 (R5 — lower95 명시 + D1 차원별 fairness gate)

| # | 기준 | 임계 | 단위 | hard-block | 실패 judgement (T3-03 + R1-F7) |
|---|---|---|---|---|---|
| **A1** | M5 overall `qwk_lower95` ≥ 0.40 | 0.40 | raw_0_30 | hard-block | `FAIL_CHANGE_MODEL` |
| **A1a** | M5 per-rubric `qwk_lower95` ≥ 0.30 (exp/org/cont 각각) | 0.30 | native_0_3 | hard-block | `FAIL_CHANGE_MODEL` |
| **A2** | M5 > M4 strict (`M5_lower95 > M4_upper95`) | overall 기준 | raw_0_30 | hard-block (Hard Rule #5) | `FAIL_CHANGE_MODEL` |
| **A3** | Score-Band Fairness Gate per-rubric (T2-13 + T2-10): 각 차원의 `worst_band_qwk ≥ macro_qwk × 0.7` | × 0.7 | native/raw 차원별 | hard-block (Hard Rule #14 확장) | `FAIL_REVIEW_LABELS` |
| **A4** | Optuna HPO trial 수: M2 단독 30+, M3+ 누적 50+ 및 cycle당 신규 5+ | M2=30 / M3+=50+5 | trial count | hard-block (Hard Rule #12) | `FAIL_RETRY_HPO` |
| **A5** | 모든 fold valid_n ≥ 300 | 300 | sample count | hard-block | `FAIL_REBUILD_FEATURES` |
| **A6** | judgement: PASS_CANDIDATE | — | enum | `final_judgement_allowed: false` 정합 |
| **A7** | **차원별 단조 후퇴 0건 (T1-05 신설)** | 0 | regression count | warn (D9 후 hard-block 승격 검토) | warn only |

용어 + 차원별 band 정의 (T1-04 + T2-13 + R1-F6 fix):
- `qwk_lower95` = QWK 점추정 ± bootstrap CI 95% 하한 (B=1000 default)
- `macro_qwk` = 각 score band의 QWK simple unweighted mean
- `worst_band_qwk` = `min(mid, high)` — low band 항상 제외 (T3-06 + R1-F10)
- low band N<10이면 `SKIP_UNSTABLE` 마크 + qualitative risk 보고
- per-rubric fairness gate band 정의:
  - exp/org/cont: native 0~3 (`low_0_1`, `mid_1_2`, `high_2_3`) — `score_band_cutoffs.per_rubric_native`
  - overall: raw 0~30 (`low_0_9`, `mid_10_19`, `high_20_30`) — evaluator가 `overall_norm × 10` 역변환 후 적용 (T2-10)
- A1a 임계 0.30의 calibration: overall 0.40 대비 1단계 낮춤. 차원별 학습 신호가 overall보다 빈약 (3-rater 평균에서 1단계 분산 큰 점 고려)

**Acceptance criteria ↔ Hard Rule 매핑 (T2-12 + R1-F5 + R1-NF1 + R1-NNF3 fix — 정확 anchor)**:
- A1, A2, A3 ↔ AGENTS.md Hard Rule #5 (단조 진화), #14 (Score-Band Fairness Gate)
- A1a, A7 ↔ Hard Rule #15 (Multi-task only for M5/M6) 본문 (AGENTS.md `^15\.`)
- A3 차원별 band 정의 ↔ Hard Rule #14 본문 (R1-NNF3 fix — 들여쓰기/bold 포함 anchor)
  - 실 매치 anchor: `grep -nE '^[[:space:]]*\*\*차원별 band 정의' AGENTS.md`
- 정확한 line 번호는 AGENTS.md를 변경 시 변동하므로 anchor 패턴(`grep -nE '^15\.|^16\.|^17\.|^18\.' AGENTS.md`)로 추적

---

## 7. 데이터 처리 (R4 — 입력 컬럼 명시)

### 7.1 입력 컬럼

| 컬럼 | 타입 | 출처 | 용도 |
|---|---|---|---|
| `text` | str | `essay_json["paragraph"][*]["paragraph_txt"]` join | RoBERTa input |
| `prompt_text` | str | `essay_json["info"]["essay_prompt"]` | (옵션) prompt-aware fine-tune. 현재 parser/audit에는 미연결. 모델 입력 포함은 별도 실험 flag + feature provenance 승인 후에만 허용 |
| `grade_group` | str | `essay_json["student"]["student_grade_group"]` | 학년군별 segment metric (R1-REG-M3 fix — extract_5k와 일치) |
| `essay_type` | str | `essay_json["info"]["essay_type"]` | 논술형/수필형 stratify |
| `rubric` | dict | `essay_json["rubric"]` | per-essay 동적 가중치 (`expression_weight["exp"]`, `organization_weight["org"]`, `content_weight["con"]`) |
| `student_location` | str | `essay_json["student"]["location"]` | **split key only** (Hard Rule #2 — 모델 입력 X) |
| `target_exp` | float (0~3) | § 7.2 식 | 학습 타겟 |
| `target_org` | float (0~3) | § 7.2 식 | 학습 타겟 |
| `target_cont` | float (0~3) | § 7.2 식 | 학습 타겟 |
| `target_overall_norm` | float (0~3) | `essay_scoreT_avg / 10` | 학습 타겟 (보조) |
| `target_overall_raw` | float (0~30) | `essay_scoreT_avg` | 평가 시 역변환 비교용 |

### 7.2 타겟 + 손실 가중치 산출 (T1-10 fix — 가중치도 함께 반환)

```python
# T1-09: 모듈 상수 (pipelines/train_transformer.py 상단)
W_OVERALL_DEFAULT = 0.5      # § 13 D7 변경 시 본 상수만 수정

def compute_rubric_targets(essay_json: dict) -> dict:
    """
    각 에세이당 (target, weight) 9-tuple 산출.

    T1-10 fix (R1-F2 산출식 누락 해소):
    - target_*: 채점자 3명의 가중 평균 (대분류별 독립)
    - w_*: 손실 함수 가중 (collator가 macro_weights로 stack)
    - PDF spec 의존 제거: 가중치는 JSON `rubric` 필드 동적 로드
    """
    detail = essay_json["score"]["essay_scoreT_detail"]
    rubric = essay_json["rubric"]

    # === target 산출용 소분류 가중치 (T1-11 + R1-NF5 + R1-NF6 fix — 인덱스-키 매핑 가드) ===
    #
    # 가정: PDF spec에 소분류 순서가 명시 안 되어 있으므로 키 이름 순으로 정렬했다고 가정.
    # 본 가정의 검증은 § 14 V1 시나리오 (학년군별 sample 손산)로 수행.
    #
    # R1-NF5 fix: 검증 실패 시 **fatal stop** 채택 (균등 가중치 fallback 폐기).
    #   이유: silent 균등 fallback은 spec drift 데이터가 다른 데이터와 섞여 학습 신호 오염.
    #   대신 essay 단위로 skip은 데이터 파이프라인(extract_5k) 측에서 처리하고,
    #   compute_rubric_targets는 strict 변환. drift 발견 시 사용자 게이트로 스펙 검토.
    # R1-NF6 fix: 학년군별 활성 소분류 슬롯 차이 (수필형은 con_prompt weight=0 등)
    #   dataset 분석 v1.1 § 4 JSON dump로 실제 key 일치 확인 의무 (V1 시나리오 필수).
    try:
        exp_sub_w = [rubric["expression_weight"][k] for k in ["exp_grammar", "exp_vocab", "exp_style"]]
        org_sub_w = [rubric["organization_weight"][k] for k in ["org_paragraph", "org_essay", "org_coherence", "org_quantity"]]
        cont_sub_w = [rubric["content_weight"][k] for k in ["con_clearance", "con_description", "con_novelty", "con_prompt"]]
    except KeyError as e:
        # R1-NF5: fatal stop. fallback은 별도 데이터 audit으로 처리. silent 균등 가중 금지.
        raise ValueError(
            f"compute_rubric_targets: rubric sub-weight key missing: {e}. "
            f"essay_id={essay_json.get('info', {}).get('essay_id', 'UNKNOWN')}. "
            f"학년군/essay_type 조합이 v1.1.2 § 14 V1 시나리오에 없거나 spec drift 가능. "
            f"조치: (1) extract_5k 단계에서 해당 essay skip (2) § 14 V1에 학년군 추가 (3) "
            f"사용자 게이트로 스펙 검토. silent fallback 금지 (R1-NF5)."
        )

    # === 손실 함수 대분류 가중치 (T1-10 — 신규 반환) ===
    # JSON의 첫 키가 대분류 자체 weight ("exp"/"org"/"con") — dataset 분석 v1.1 § 8 참조
    w_exp_macro  = float(rubric["expression_weight"]["exp"])
    w_org_macro  = float(rubric["organization_weight"]["org"])
    w_cont_macro = float(rubric["content_weight"]["con"])
    # w_overall — per-essay dynamic (드물게 rubric에 명시) 또는 모듈 상수
    w_overall = float(rubric.get("overall_weight", W_OVERALL_DEFAULT))

    def avg_normalized(scores_per_rater: list[list[float]], weights: list[float]) -> float:
        per_rater = [
            sum(s * w for s, w in zip(rater, weights)) / sum(weights)
            for rater in scores_per_rater
        ]
        return sum(per_rater) / len(per_rater)

    overall_raw = essay_json["score"]["essay_scoreT_avg"]   # 0~30

    return {
        # targets (학습 head 출력 대상)
        "target_exp":            avg_normalized(detail["essay_scoreT_exp"], exp_sub_w),     # 0~3
        "target_org":            avg_normalized(detail["essay_scoreT_org"], org_sub_w),     # 0~3
        "target_cont":           avg_normalized(detail["essay_scoreT_cont"], cont_sub_w),   # 0~3
        "target_overall_norm":   overall_raw / 10.0,                                         # 0~3
        "target_overall_raw":    overall_raw,                                                # 0~30
        # 손실 함수 가중치 (collator → macro_weights stack 대상, T1-10 신규)
        "w_exp":     w_exp_macro,
        "w_org":     w_org_macro,
        "w_cont":    w_cont_macro,
        "w_overall": w_overall,
    }
```

**T1-10/T1-11 검증 의무**: § 14 V1 시나리오에서 학년군별 sample 10건 손산으로 (a) 소분류 인덱스-키 매핑 (b) 대분류 가중치 합(=10) 검증 통과 후 Phase 3 M2 진입.

**R1-NNF1 fix — extract_5k에 사전 validation 추가**:
`pipelines/extract_5k.py:validate_rubric_for_phase3(doc)` 헬퍼가 본 § 7.2 `compute_rubric_targets`가 요구하는 모든 키와 schema (rubric sub/macro weights numeric, sub-weight sum > 0, score detail 3 rater × exp=3/org=4/cont=4 shape, score range 0~3, overall_raw 0~30) 사전 검증. fatal stop 정책 (NF5)을 운영 가능하게 함:
1. extract_5k 추출 시 drift essay는 자동 skip (manifest에 통계 기록)
2. 학습 직전 (pipelines/train_transformer.py)에 한 번 더 검증
3. 통과 후 학습 진행 → fatal stop 발생 0건 보장

**R1-NNF5 fix — `overall_weight` key fallback-only 명시**:
`dataset_채점방식_분석_v_1_0.md` v1.1 § 4 JSON 스키마에 `overall_weight` 키 evidence 부재 → 모든 essay가 모듈 상수 (`W_OVERALL_DEFAULT=0.5`) fallback 경로 사용. `rubric.get("overall_weight", ...)` 시도는 향후 데이터 spec 확장 호환성 유지용. 현 시점에는 사실상 `W_OVERALL_DEFAULT` 단일 값.

**R1-NNF7 fix — `essay_scoreT_detail` path 검증**:
`dataset_채점방식_분석_v_1_0.md` v1.1 § 4 JSON 예 기준 `doc["score"]["essay_scoreT_detail"]` path 정합 확인 의무. V1 시나리오에서 학년군별 sample 1건씩 path 검증.

### 7.3 데이터 source (D4)

| 항목 | Phase 3 v1.1 |
|---|---|
| 데이터셋 | `dataset/sample_5k/` (5003편, Phase 2 inheritance) |
| 재생성 명령 (Phase 2 호환) | `python3 -m pipelines.extract_5k dataset/1.Training --out dataset/sample_5k --target-n 5000 --seed 42` |
| **재생성 명령 (Phase 3, R1 5차 NEW-R2 fix)** | `python3 -m pipelines.extract_5k dataset/1.Training --out dataset/sample_5k --target-n 5000 --seed 42 --validate-rubric` |
| Phase 3 진입 시 강제 정책 (R1 5차 NEW-R5) | M2 wire-up cycle의 AUDIT/SPLIT sub-task가 dataset 재생성 명령 호출 시 `--validate-rubric` flag **의무 포함**. 누락 시 SYNTH가 block + 사용자 게이트 |
| 풀데이터 (50K+) 진입 | Phase 3 Mid 종료 + 사용자 [Phase-up] DECIDE 후 |

---

## 8. 점진 도입 단계

| 단계 | 작업 | Phase 3 cycle |
|---|---|---|
| **A** | 대분류 3+1 multi-output head + 가중 MSE | M2 (Phase 3 최초) |
| **B** | per-rubric evaluate.py + acceptance 차원별 추가 | M2 (A와 동시) |
| **C** | 차원별 진단 보고 (단조 진화 차원별 정보) | M2 |
| **D** | 소분류 9~11 head로 확장 — 학년군별 슬롯 매핑 검증 후 | M4+ (Phase 3 후반) |
| **E** | paragraph_score auxiliary task 추가 | M5+ |
| **F** | 채점자 분산 → uncertainty-aware loss | Phase 4 |

---

## 9. Phase 2 대비 즉시 가치

| 영역 | Phase 2 (single-target) | Phase 3 v1.1 (multi-task) |
|---|---|---|
| 채점 정확도 | overall QWK 0.40+ 목표 | 차원별 QWK 0.30+ + overall 0.40+ |
| 진단 신호 | "글이 잘못됐다" 1차원 | "표현 약 / 구성 양호 / 내용 보통" 3차원 |
| 피드백 | 단일 점수 | 차원별 강약점 |
| 학습 신호 | 1/99 정보 | 3~11/99 정보 |
| 데이터 inheritance | — | Phase 2 5K 동일 (D4) |

---

## 10. 위험과 완화

| # | 위험 | 완화 |
|---|---|---|
| W1 | Multi-task loss 차원 간 학습 어려움 차이 | 가중치 적응 (PCGrad/GradNorm) — Phase 3 M3+ 검토. M2는 균등(JSON rubric) weight |
| W2 | Phase 2 acceptance 단일 기준이라 평가 인프라 충돌 | overall(4번째 head)로 단조 진화 호환 유지. evaluate.py 차원별 보고 추가 (§ 4) |
| W3 | 학년군별 가중치 다름 → batch 내 mixed | JSON `rubric`에서 per-essay 동적 가중치 (§ 7.2) |
| W4 | 모델 복잡도 증가 → overfitting | dropout 유지 + 작은 head (768→4). HPO `weight_decay` 탐색 |
| W5 | 소분류 슬롯 매핑 미명시 (PDF/spec 누락) | 단계 D로 보류. 가설(grammar/vocab/style 순) + 학년군별 데이터 역추정은 별도 sprint |
| W6 | Data spec drift (초5 논술형 등) | JSON `rubric` 가중치 source of truth (PDF 의존 제거) |
| W7 | overall head가 차원별 학습 신호 압도 | `w_overall=0.5` 다운가중 (§ 3.2). 학습 시 차원별 loss 모니터링 |

---

## 11. 구현 핵심 코드 (의사) — R4 입력 컬럼 명시 + R6 표현 완화

### 11.1 train_transformer.py 핵심

```python
import torch
from torch import nn
from transformers import AutoModelForSequenceClassification, Trainer

# D5 채택: klue/roberta-small (Phase 2 inheritance)
MODEL_NAME = "klue/roberta-small"
TARGET_NAMES = ["exp", "org", "cont", "overall_norm"]   # D3, 4개

def model_init():
    return AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(TARGET_NAMES),           # = 4
        problem_type="regression",
    )

def collator_with_macro_weights(features: list[dict]) -> dict:
    """
    각 sample의 macro_weights를 batch dim에 stack.
    columns: input_ids, attention_mask, labels(B,4), macro_weights(B,4)

    T1-09 fix (R1-F1 magic number 해소):
    - w_overall은 dataset-level (compute_rubric_targets 반환)에서 가져옴
    - dataset에 없으면 W_OVERALL_DEFAULT 모듈 상수 fallback
    """
    batch = {
        "input_ids":      torch.tensor([f["input_ids"] for f in features]),
        "attention_mask": torch.tensor([f["attention_mask"] for f in features]),
        "labels":         torch.tensor([
            [f["target_exp"], f["target_org"], f["target_cont"], f["target_overall_norm"]]
            for f in features
        ], dtype=torch.float),
        "macro_weights":  torch.tensor([
            [
                f["w_exp"],
                f["w_org"],
                f["w_cont"],
                f.get("w_overall", W_OVERALL_DEFAULT),    # dataset-level → 모듈 상수 fallback
            ]
            for f in features
        ], dtype=torch.float),
    }
    return batch

class WeightedMSEMultiTaskTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels         = inputs.pop("labels")             # (B, 4)
        macro_weights  = inputs.pop("macro_weights")      # (B, 4)
        outputs        = model(**inputs)
        preds          = outputs.logits                    # (B, 4)
        # R1-NF3 fix: .sum(dim=1).mean() — 차원 4 분모 제거, batch B 분모 유지
        # 수식 (w_exp*MSE(exp) + w_org*MSE(org) + w_cont*MSE(cont) + w_overall*MSE(overall)) 그대로
        loss           = ((preds - labels) ** 2 * macro_weights).sum(dim=1).mean()
        return (loss, outputs) if return_outputs else loss
```

### 11.2 evaluate.py 핵심 (per-rubric fairness gate)

```python
# 입력 컬럼 (R4): essay_id, fold, y_true_<dim>, y_pred_<dim>, score_band, grade_band, essay_type
# (<dim> ∈ {exp, org, cont, overall_norm, overall_raw})

def fairness_gate_per_rubric(predictions: pd.DataFrame, rng, bootstrap_b: int = 1000) -> dict:
    """
    각 대분류 + overall_raw 4종에 대해 fairness gate 산출.
    overall은 raw 스케일(0~30)로, 대분류는 native 스케일(0~3)로 평가.
    """
    out = {}
    dims = [
        ("exp",          "exp",     (0, 3)),
        ("org",          "org",     (0, 3)),
        ("cont",         "cont",    (0, 3)),
        ("overall_raw",  "overall", (0, 30)),
    ]
    for col_suffix, label, score_range in dims:
        y_true = predictions[f"y_true_{col_suffix}"]
        y_pred = predictions[f"y_pred_{col_suffix}"]
        if label == "overall":
            # overall은 raw 0~30 기준 band 사용.
            band = predictions["score_band_overall_raw"]
        else:
            # exp/org/cont는 native 0~3 기준 band 사용.
            # overall score_band 재사용 금지: high-score majority 편향이 차원별 fairness를 가린다.
            band = score_band_per_rubric(y_true, cutoffs="per_rubric_native")
        out[label] = fairness_gate(y_true, y_pred, band, rng, bootstrap_b)
    return out


def acceptance_per_rubric(per_rubric_metrics: dict, criteria: dict) -> dict:
    """
    Hard-block 판정.
    """
    judgements = {}
    for dim in ["exp", "org", "cont"]:
        m = per_rubric_metrics[dim]
        judgements[f"{dim}_qwk_lower95"] = m["qwk_lower95"] >= criteria["m5_per_rubric_qwk_lower95"]
        judgements[f"{dim}_fairness"]    = m["worst_band_qwk"] >= m["macro_qwk"] * criteria["fairness_gate_ratio"]
    o = per_rubric_metrics["overall"]
    judgements["overall_qwk_lower95"] = o["qwk_lower95"] >= criteria["m5_overall_qwk_lower95"]
    judgements["overall_fairness"]    = o["worst_band_qwk"] >= o["macro_qwk"] * criteria["fairness_gate_ratio"]
    judgements["pass"] = all(judgements.values())
    return judgements
```

### 11.3 ACCEPTANCE_CRITERIA.yaml 차원별 (요약 — 본문 변경은 A4+A5 task)

```yaml
mid:
  primary_metrics:
    m5_overall_qwk_lower95:
      operator: ">="
      value: 0.40
      hard_block: true
      failure_judgement: FAIL_CHANGE_MODEL
    m5_per_rubric_qwk_lower95:     # 신규 (R5 + D1)
      operator: ">="
      value: 0.30
      hard_block: true
      applies_to: [exp, org, cont]
      failure_judgement: FAIL_CHANGE_MODEL
  fairness_gate:
    ratio: 0.7
    per_rubric: true               # 신규 (D1)
    hard_block: true
```

---

## 12. M6 Ensemble 재작성 명세 (D6 — scalar 폐기)

### 12.1 Phase 2 v1.0 인터페이스 (폐기)

```python
# Phase 2 train_ensemble.py — scalar (폐기)
fold_predictions: dict[model_id, list[{fold: int, y_true: np.ndarray, y_pred: np.ndarray}]]
#                                                  shape (N,)             shape (N,)
```

**T2-11 fix + R3-F12 — polymorphic input 차단**: Phase 3 `train_ensemble.py`는 scalar shape (`(N,)`) 인터페이스로 호출 시 명시적 `ValueError` raise (silent 폐기 X).

### 12.2 Phase 3 v1.1.1 인터페이스 (신규, T2-11 + R1-F4 fix — 단위 명시)

```python
# Phase 3 train_ensemble.py — multi-output
fold_predictions: dict[model_id, list[{
    fold:    int,
    y_true:  np.ndarray,    # shape (N, 4) — [exp, org, cont, overall_norm]
    y_pred:  np.ndarray,    # shape (N, 4)
}]]
```

**4번째 슬롯 단위 결정 (T2-11 + R1-F4 + R2-F8)**:
- M5/M6 fold export 시: **`overall_norm` (0~3)** 단위로 저장 — `pred_overall_raw = pred_overall_norm × 10` 역변환은 evaluator 시점에 처리
- 이유: ① 학습/stacking은 동일 스케일 (0~3) 4 차원에서 일관 ② 역변환은 acceptance/fairness gate (overall_raw 0~30) 시점에만 필요
- 변환 책임: **M5 export = norm 그대로**, **M6 stacking = norm 입력, norm 출력**, **evaluator = norm → raw 역변환 (overall acceptance 시)**

### 12.3 Stacking 모델 (T3-05 + R1-F9 + R1-NF2/NF4/NF7 fix — M6 입력 contract 명시)

| 차원 | meta-learner | 입력 |
|---|---|---|
| exp / org / cont / overall_norm | `MultiOutputRegressor(Ridge)` (내부적으로 차원별 Ridge 4개) | M5 (4 차원) + M4 4-dim broadcast |

**M6 입력 contract (T3-05 + R1-NF4 결정 — 배제 사유 명시)**:

| 모델 | M6 입력 포함 | 사유 |
|---|---|---|
| M1 (dummy) | **제외** | 평균 회귀 baseline floor — OOF stacking에 정보 가치 미만 |
| M2 (length) | **제외** | 1 feature 회귀 baseline — stacking 변별력 미달 |
| M3 (TF-IDF Ridge) | **제외** | overall만 scalar — D8 결정 후 차원별 확장 시 재검토 (스펙 § 13 D8) |
| M4 (LightGBM) | **포함 (overall→broadcast)** | Phase 2 best CPU baseline. 4-dim broadcast로 stacking |
| M5 (KLUE-RoBERTa multi-task) | **포함 (4 차원)** | multi-task 출력 그대로 |

코드 (R1-NF2 + R1-NF7 fix — 주석 정정 + OOF fold loop):
```python
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
import numpy as np

def train_m6_multi_output_oof(
    fold_preds_m4: list[dict],   # [{fold, y_true: (N_f,), y_pred: (N_f,) overall_raw}, ...]
    fold_preds_m5: list[dict],   # [{fold, y_true: (N_f, 4), y_pred: (N_f, 4) overall_norm}, ...]
    n_folds: int,
) -> dict:
    """OOF stacking — 각 fold valid에 대해 meta를 학습 (다른 fold의 OOF로).

    R1-NF7 fix: 이전 v1.1.1 코드는 single global meta로 학습 → fold OOF semantics 미준수.
        본 함수는 fold별 meta 학습 + OOF 예측 보존.
    R1-NF2 fix: 주석 명확화 — y_true는 [exp, org, cont, overall_norm] 4 차원 each native 0~3.

    Returns: {fold: meta_model, "oof_predictions": (N_total, 4) overall_norm}
    """
    n_total = sum(len(fp["y_true"]) for fp in fold_preds_m5)
    oof_predictions = np.zeros((n_total, 4), dtype=float)
    metas = {}
    offset = 0

    for fold_idx in range(n_folds):
        # train: other folds의 OOF, valid: current fold
        train_m4 = [fp for fp in fold_preds_m4 if fp["fold"] != fold_idx]
        train_m5 = [fp for fp in fold_preds_m5 if fp["fold"] != fold_idx]
        valid_m4 = next(fp for fp in fold_preds_m4 if fp["fold"] == fold_idx)
        valid_m5 = next(fp for fp in fold_preds_m5 if fp["fold"] == fold_idx)

        # Input contract 검증 (R1-F9 + T2-11)
        if valid_m5["y_true"].ndim != 2 or valid_m5["y_true"].shape[1] != 4:
            raise ValueError(
                f"M5 y_true must be (N, 4) [exp, org, cont, overall_norm] each native 0~3; "
                f"got shape {valid_m5['y_true'].shape}. Phase 2 scalar deprecated (D6)."
            )

        # train set 합치기 (M4 scalar overall_raw → overall_norm broadcast)
        X_train = _build_stacking_features(train_m4, train_m5)
        y_train = np.vstack([fp["y_true"] for fp in train_m5])  # (N_train, 4)
        meta = MultiOutputRegressor(Ridge(alpha=1.0, random_state=42))
        meta.fit(X_train, y_train)
        metas[fold_idx] = meta

        # valid set OOF 예측
        X_valid = _build_stacking_features([valid_m4], [valid_m5])
        n_v = len(valid_m5["y_true"])
        oof_predictions[offset:offset + n_v] = meta.predict(X_valid)
        offset += n_v

    return {"folds": metas, "oof_predictions": oof_predictions}


# NOTE (R1 5차 NEW-R3 fix): `_build_stacking_features` 정의는 § 12.3 후반 (R1-REG-M1 fix
# 신규 코드 블록) 하나만 사용. v1.1.3의 ndim 분기 정의는 § 12.3 후반에서 ValueError raise로
# 대체됨. 이전 v1.1.3 정의 코드 블록은 본 spec에서 삭제 (이중 정의 모순 제거).


def predict_m6(metas: dict, fp_m4: dict, fp_m5: dict, fold_idx: int) -> np.ndarray:
    """단일 fold predict — (N, 4) [exp, org, cont, overall_norm] each native 0~3."""
    X = _build_stacking_features([fp_m4], [fp_m5])
    return metas[fold_idx].predict(X)


def predict_m6_inference(metas_dict_or_folds: dict, fp_m4: dict, fp_m5: dict) -> np.ndarray:
    """R1-NNF2 + R1-REG-M2 fix — production inference 시 k-fold meta ensemble average.

    Phase 3 M5/M6 acceptance 평가 후 deploy 단계에서 사용. 단일 fold meta가 아닌
    k-fold meta 평균으로 안정성 확보.

    Args:
        metas_dict_or_folds:
            - `train_m6_multi_output_oof()` 반환 dict 자체 또는 그 `["folds"]` value.
            - dict이면 자동으로 `dict["folds"]` 추출 시도, 없으면 dict 자체를 folds로 가정.
            - 표준 caller: `result = train_m6_multi_output_oof(...); pred = predict_m6_inference(result, ...)`
        fp_m4: {"y_pred": (N,) overall_raw or (N, 4) overall_norm}
        fp_m5: {"y_pred": (N, 4) overall_norm}

    Returns: (N, 4) [exp, org, cont, overall_norm] each native 0~3 — k-fold meta 평균
    """
    # R1-REG-M2: metas argument 자동 분기 (caller 편의)
    if "folds" in metas_dict_or_folds:
        metas = metas_dict_or_folds["folds"]
    else:
        metas = metas_dict_or_folds

    X = _build_stacking_features([fp_m4], [fp_m5])
    predictions = np.stack([metas[fold_idx].predict(X) for fold_idx in metas], axis=0)
    return predictions.mean(axis=0)  # k-fold ensemble average
```

**R1-NNF6 + R1-REG-M1 fix — M4 출력 spec 단일화 + 코드 일관성**:
v1.1.3은 spec 단일화 의도 + 코드 ndim 분기 유지 모순. v1.1.4는 **spec 의도대로 코드도 단일화**:

```python
# R1-REG-M1 fix: ndim 분기 제거, M4 contract 강제
def _build_stacking_features(fp_m4_list: list[dict], fp_m5_list: list[dict]) -> np.ndarray:
    """M4 contract: 항상 (N_f,) 1D overall_raw. M5: (N_f, 4) overall_norm."""
    m4_arrays = []
    for fp in fp_m4_list:
        y_pred = fp["y_pred"]
        if y_pred.ndim != 1:
            raise ValueError(
                f"M4 contract violation: y_pred must be (N_f,) 1D overall_raw, "
                f"got shape {y_pred.shape}. D8 결정 전 multi-task M4 미허용 (스펙 § 12.3)."
            )
        m4_arrays.append(np.tile((y_pred / 10.0).reshape(-1, 1), (1, 4)))   # raw→norm + 4D broadcast
    m4_concat = np.concatenate(m4_arrays, axis=0)
    m5_concat = np.concatenate([fp["y_pred"] for fp in fp_m5_list], axis=0)
    return np.concatenate([m4_concat, m5_concat], axis=1)  # (N, 8)
```

- M4 export 시 contract: scalar overall_raw만 저장 (`(N_f,)` 1D). multi-task M4는 D8 결정 후 도입 → 그때 함수 분리
- ndim != 1 시 `ValueError` raise (이전 분기 제거)

### 12.4 M6 fairness gate (T2-13 + R1-F6 + T3-06 fix — 차원별 band 정의)

- 차원별 fairness gate를 M6에도 동일 적용 (§ 6 A3). Hard Rule #5와 일관성
- **band cutoff**: `ACCEPTANCE_CRITERIA.yaml` `stages.mid_multitask.score_band_cutoffs` 참조
  - exp/org/cont: native 0~3 (`low_0_1`, `mid_1_2`, `high_2_3`)
  - overall: raw 0~30 (`low_0_9`, `mid_10_19`, `high_20_30`) — evaluator가 `overall_norm × 10` 역변환 후 적용
- **worst_band_qwk = `min(mid, high)`** (T3-06 + R1-F10 — low 항상 제외)
- **low band SKIP_UNSTABLE 트리거**: low band N < 10 시 별도 mark, fairness gate에서 제외
- M6 acceptance hard-block: `worst_band_qwk < macro_qwk × 0.7` 시 `FAIL_REVIEW_LABELS`

---

## 13. 후속 결정 사항 (Phase 3 운영 중 필요시 결정)

본 스펙은 D1~D6을 확정했으나, 다음 사항은 Phase 3 운영 중 cycle별 결정 가능 (PASS_CANDIDATE 후 사용자 게이트):

| # | 항목 | 옵션 | 결정 트리거 (T3-07 — 측정 가능 형태) |
|---|---|---|---|
| **D7** | `W_OVERALL_DEFAULT` 값 (현재 0.5) | 0.3 / 0.5 / 1.0 / GradNorm | Cycle M2 EVAL에서 `(metrics_so_far["overall_loss"] / metrics_so_far["per_rubric_loss_mean"]) > 1.5` 시 |
| **D8** | M3/M4 multi-output 확장 여부 | 유지 (scalar) / 차원별 모델 4개 | Cycle M3 SYNTH의 `per_rubric_diagnostic_qwk` 평균이 0.20 미만 + M4 single-target QWK > M5 차원별 평균 시 |
| **D9** | 차원별 단조 진화 hard-block 승격 | warn 유지 (현재 T1-05) / hard-block 승격 | Phase 3 후반 — 3 consecutive cycle에서 `per_rubric_monotone_regressions` 평균 ≤ 1 + M5 안정성 입증 시 |
| **D10** | 소분류 9~11 head 도입 (단계 D) | 보류 / 학년군별 슬롯 매핑 sprint | Cycle M4+에서 모든 대분류 차원 `per_rubric_qwk_lower95 > 0.40` 충족 시 (T3-07 + R1-F11 측정 가능 형태) |

---

## 14. 검증 시나리오 (Phase 3 M2 진입 직후, T1-11 + R1-NNF4 강화)

R1-NNF4 fix — 타입(논술형/수필형) × 학년군(4종) = **8 셀 매트릭스 cover 의무**. V1 시나리오는 8 셀 × 1-2건 (총 8-16건) 학년군별 + 타입별 활성 슬롯 차이 검증.

| # | 항목 | 검증 방법 | 통과 기준 |
|---|---|---|---|
| **V1** | `compute_rubric_targets` 정확성 + **인덱스-키 매핑** (T1-11 fix) + **타입×학년군 매트릭스** (R1-NNF4) | 8 셀 매트릭스 (논술형 × 4학년군 + 수필형 × 4학년군) 각 1-2건 PDF spec 가중치 대비 손산 비교. 수필형 `con_prompt` weight=0 등 학년군-타입 조합 활성 슬롯 차이 명시적 검증 | 8 셀 모두 일치 (오차 0.01 이내). 수필형 con_prompt 0-weight 케이스 통과 |
| V2 | `WeightedMSEMultiTaskTrainer` loss 계산 | unit test: 알려진 입력 → 손계산 손실 일치. `tests/test_train_transformer_multitask.py` | assert 통과 |
| V3 | overall head 정규화 ↔ 역변환 | `pred_overall_raw = pred_overall_norm × 10` round-trip QWK 일치 | QWK 차이 < 1e-6 |
| V4 | per-rubric fairness gate | Phase 2 evidence (overall만) ↔ Phase 3 v1.1.x (차원별 + overall) | 동일 데이터에서 overall QWK 동일, 차원별 fairness gate 4 dim 모두 평가 |
| V5 | M6 multi-output OOF + **polymorphic input 차단** (T2-11 + R3-F12) | Phase 2 scalar 인터페이스 호출 시 명시적 `ValueError` | exception 발생 + 메시지 명확 |
| V6 | `W_OVERALL_DEFAULT` 단일 지점 변경 (T1-09) | 모듈 상수 0.5 → 0.3 변경 후 collator + trainer 자동 일관 | 다른 코드 변경 없이 loss 가중치 변경됨 |
| V7 | 가중치 합 검증 (T1-10) | sample 8건의 대분류 가중치 합 (`w_exp + w_org + w_cont`) | dataset 분석 § 8 표(논술형 10, 수필형 10)와 일치 |
| **V8** | **`validate_rubric_for_phase3` skip 로직** (R1-NNF1) | extract_5k에서 drift essay 발견 시 skip + manifest에 통계 기록. 통과 후 fatal stop 발생 0 | drift skip 통계가 manifest에 명시. 학습 시 fatal stop 0건 |
| **V9** | **M6 inference k-fold ensemble** (R1-NNF2) | `predict_m6_inference` 5개 fold meta 평균이 단일 fold predict보다 안정 (variance 감소) | ensemble QWK ≥ 단일 fold QWK 평균 |
| **V10** | **JSON path 검증** (R1-NNF7) | `doc["score"]["essay_scoreT_detail"]` path 8 셀 sample 모두 존재 확인 | 8/8 통과 |

---

## 부록 A: 출처

- `dataset_채점방식_분석_v_1_0.md` v1.1 — 데이터셋 분석 및 검증
- `dataset/루브릭 설명서_v0.3.pdf` — 가중치 spec
- `dataset/1-15_에세이 글 데이터_데이터 설명서.pdf` — JSON 스키마
- `pipelines/train_transformer.py` — Phase 2 single-target 구현
- `pipelines/train.py` — `TARGET_NAME`, `train_transformer_model`
- `pipelines/train_ensemble.py` (commit 16b0fb5) — Phase 2 OOF stacking scalar 인터페이스 (D6에서 폐기)
- `MILESTONE_v2.md` — Phase 2 acceptance criteria + 종료 노트
- `MILESTONE_v3.md` — Phase 3 milestone (A2 task 산출)
- `AGENTS.md` — Hard Rule #5 (단조 진화), #14 (Score-Band Fairness Gate). #15~#18은 A4 task 산출
- `docs/phase_3_operations_guide_v_1_0.md` — A3 task 산출 (C1~C6 운영 절차)
- `ACCEPTANCE_CRITERIA.yaml` mid 섹션 — A5 task에서 per-rubric 추가

## 부록 B: v1.0 → v1.1 diff 요약

| 영역 | v1.0 | v1.1 |
|---|---|---|
| 표현 톤 | "권장: 대분류 3+1" | "D3 채택: 하이브리드 3+overall" (단언) |
| 손실 함수 | scale 불일치 (overall 0~30) | overall_norm 0~3 정규화 (§ 3) |
| M6 변경 | "multi-output OOF stacking" 1줄 | 인터페이스 명세 + 코드 + scalar 폐기 명시 (§ 4, § 12) |
| Acceptance | "차원별 QWK ≥ 0.30" | `qwk_lower95` 명시 + per-rubric fairness gate (§ 6) |
| pseudocode | 입력 컬럼 불명 | 모든 입력 컬럼 표 명시 (§ 7.1, § 11) |
| 결정 사항 | 본문에 산재 ("권장") | § 0 요약 + § 13 후속 결정 분리 |
