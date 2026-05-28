# Phase 2 Mid-scale Design v1.1

> 갱신일: 2026-05-28
> 범위: Phase 1 toy 종료 후 Phase 2 mid-scale 5K + KLUE-RoBERTa + Optuna HPO 운영 설계
> Source of truth: `AGENTS.md`, `MILESTONE_v2.md`, `VAST_GPU_GUIDE.md`

## 1. Status

Phase 2는 준비 단계가 아니라 **실행 단계**입니다.

| 항목 | 상태 |
|---|---|
| Active board | `essay-auto-scoring-research-phase2` |
| Current cycle | `M1` |
| Primary sample | `dataset/sample_5k/` 5,003건 |
| Sample extraction | 완료, deterministic seed=42 |
| Phase 2 code | `extract_5k`, `train`, `train_transformer`, `train_ensemble`, `run_hpo`, `evaluate` 확장 완료 |
| Vast.ai key | `.env` 제공됨, `show instances --raw`와 `search offers --raw` 검증 완료 |
| Current active task | `T-CYCLE-M1-MODEL: M1~M5 baseline 학습` |

Hard Rule #13 외부 compute PII gate는 2026-05-28 인간 게이트 통과로 제거됐습니다. AI Hub 공공 한국 K-12 에세이 데이터셋은 사전 익명화 완료로 보고, 외부 GPU 전송 게이트는 요구하지 않습니다. 단, Hard Rule #2의 학생 직접 식별자 모델 입력 금지는 유지됩니다.

## 2. Phase 1 vs Phase 2

| 차원 | Phase 1 Toy | Phase 2 Mid-scale |
|---|---|---|
| 상태 | 종료 | 진행 중 |
| Data | `dataset/sample/` 342건 | `dataset/sample_5k/` 5,003건 |
| Models | M1~M4 | M1~M6 |
| Transformer | 금지 | M5 KLUE-RoBERTa 허용 |
| Ensemble | 없음 | M6 M4+M5 OOF stacking |
| HPO | 없음 | Optuna 30 trial+ |
| Gate 정책 | 일부 warn-only | hard-block 중심 |
| Score-band fairness | 없음 | Hard Rule #14 필수 |
| MLflow | file/legacy evidence | `sqlite:///mlflow.db` primary |
| Human gate | DECIDE | DECIDE 유지 |

## 3. Data And Split Policy

Phase 2 primary data:

```bash
python3 -m pipelines.extract_5k dataset/1.Training \
  --out dataset/sample_5k \
  --target-n 5000 \
  --seed 42
```

정책 기준은 `AGENTS.md`의 `student.location` 기반 stratified group split입니다. 다만 Cycle M1에서는 location group sparsity 때문에 다음 deviation이 발생했습니다.

| 시도 | 결과 |
|---|---|
| location k=10 | valid_n < 300 fold 다수로 hard-block |
| location k=5 | 일부 fold valid_n < 300으로 hard-block |
| region k=3 | Cycle M1 한정 통과, 모든 valid_n ≥ 300 |

Cycle M1의 region k=3은 **본 cycle 한정 recovery path**입니다. 영구 정책으로 승격하려면 SYNTH 권고와 인간 게이트를 거쳐 `AGENTS.md`/`MILESTONE_v2.md`를 함께 정정해야 합니다.

## 4. Model Ladder

| ID | Model | 실행 위치 |
|---|---|---|
| M1 | dummy | local CPU |
| M2 | length + Ridge | local CPU |
| M3 | TF-IDF + Ridge | local CPU |
| M4 | LightGBM | local CPU |
| M5 | KLUE-RoBERTa regression head | vast.ai GPU 권장 |
| M6 | M4 + M5 OOF stacking ensemble | local or GPU result merge 후 |

M6는 in-sample stacking이 아니라 out-of-fold prediction 기반 stacking이어야 합니다.

## 5. HPO

HPO는 `pipelines/run_hpo.py`와 `pipelines/hpo.py`가 담당합니다.

| 항목 | 값 |
|---|---|
| Library | Optuna |
| Storage | `sqlite:///optuna.db` |
| Sampler | `TPESampler(seed=42)` |
| Pruner | `MedianPruner(n_startup_trials=5)` |
| Minimum | model당 30 trial+ |
| MLflow | parent run + nested trial runs |

모든 parent/nested run에는 `cycle_id`, `kanban_task_id`, `feature_provenance` tag가 필요합니다.

## 6. Evaluation

EVAL 산출물은 다음을 모두 포함해야 합니다.

1. Overall RMSE / MAE / QWK
2. Per-band RMSE / MAE / QWK: `low_0_9`, `mid_10_19`, `high_20_30`
3. Macro-QWK
4. Worst-band QWK: low band N<10이면 `SKIP_UNSTABLE`
5. Bootstrap CI 95%: overall + per-band
6. Human ceiling comparison: metric 단위 일치 + bootstrap CI
7. Baseline monotone evolution: M1 ≤ M2 ≤ M3 ≤ M4 ≤ M5 ≤ M6

Acceptance hard-block:

```text
worst_band_qwk < macro_qwk * 0.7
```

필수 보고 문구:

> 본 데이터셋은 high score band에 90% 이상 집중되어 있으므로, overall metric은 실제 변별력을 과대평가할 수 있다. 따라서 모델 수용 여부는 overall metric뿐 아니라 macro-QWK, worst-band QWK, per-band metric을 함께 기준으로 판단한다.

## 7. Vast.ai Operating Notes

`vastai show user`는 사용하지 않습니다. CLI 0.5.0이 `/api/v0/users/current?owner=me`를 호출해 현재 API schema와 충돌할 수 있습니다.

인증/네트워크 확인:

```bash
vastai --api-key "$VAST_API_KEY" show instances --raw
vastai --api-key "$VAST_API_KEY" search offers 'gpu_ram>=8 reliability>0.95' --raw
```

보안 주의:

- `vastai --explain`은 API key를 평문 출력할 수 있으므로 사용하지 않습니다.
- `.env`는 commit하지 않습니다.
- 인스턴스 생성 후 `trap` 또는 명시적 `destroy instance`로 과금 누수를 방지합니다.

## 8. Cycle M1 Chain

| Step | Task | Profile | Status |
|---|---|---|---|
| 1 | `T-CYCLE-M1-AUDIT: 데이터 검증` | tukey | done |
| 2 | `T-CYCLE-M1-SPLIT: 분할 정책` | gauss | done, region k=3 recovery |
| 3 | `T-CYCLE-M1-FEATURE: 피처 + RoBERTa embedding cache` | gauss | done |
| 4 | `T-CYCLE-M1-MODEL: M1~M5 baseline 학습` | gauss | running |
| 5 | `T-CYCLE-M1-HPO: Optuna 30 trial+` | gauss | todo |
| 6 | `T-CYCLE-M1-EVAL: 다축 평가 + bootstrap CI` | spearman | todo |
| 7 | `T-CYCLE-M1-REVIEW: 코드/누수 리뷰` | turing | todo |
| 8 | `T-CYCLE-M1-SYNTH: 종합 + 다음 cycle 등록` | aristotle | todo |
| 9 | `DECIDE-M1: 인간 결정` | human | todo |

Dependency shape:

```text
AUDIT -> SPLIT -> FEATURE -> MODEL -> HPO -> (EVAL || REVIEW) -> SYNTH -> DECIDE-M1
```

## 9. Risks

| Risk | Mitigation |
|---|---|
| split group sparsity | Cycle M1 region k=3 recovery, SYNTH에서 영구 정책 여부 인간 게이트 |
| score-band imbalance | Hard Rule #14 macro/worst-band gate |
| cost overrun | `configs/board_config.yaml` cost circuit breaker + Vast destroy trap |
| MLflow/Optuna drift | SQLite DB 경로 고정, parent/nested run tags |
| label-side feature leakage | feature provenance manifest + REVIEW hard gate |
| stale Kanban task body | 최신 guidance를 task comment/body에 반영 |

## 10. References

- `../AGENTS.md`
- `../MILESTONE_v2.md`
- `../VAST_GPU_GUIDE.md`
- `docs/README.md`
- `docs/research/vast_ai_essay_workflow_v_1_0.md`
- `docs/research/self_improving_long_running_research_v_1_0.md`
- `docs/research/mlflow_tracing_2026_research_v_1_0.md`
