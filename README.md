# Essay Auto-Scoring Research

한국어 K-12 서술형 에세이 자동채점 연구를 Hermes Multi-Agent Kanban Board로 장기 자율 실행하는 검증 프로젝트입니다.

현재 초점은 **Phase 2 Mid-scale**입니다. Phase 1 toy 검증은 종료됐고, 지금은 5,003건 표본, KLUE-RoBERTa, Optuna HPO, score-band fairness gate를 포함한 실모델 품질 검증을 진행합니다.

## Current State

| 항목 | 현재 값 |
|---|---|
| Active board | `essay-auto-scoring-research-phase2` |
| Phase | Phase 2 Mid-scale |
| Primary data | `dataset/sample_5k/` |
| Active cycle | `M1` |
| Models | M1 dummy, M2 length, M3 TF-IDF+Ridge, M4 LightGBM, M5 KLUE-RoBERTa, M6 M4+M5 ensemble |
| Tracking | `sqlite:///mlflow.db`, `sqlite:///optuna.db` |
| Human gate | `DECIDE-MN`에서 `[Continue]`, `[Phase-up]`, `[Stop]` |

Phase 1 evidence는 보존합니다:

- `docs/final_report_v_1_0.md`
- `docs/hermes_validation_v_1_0.md`
- `docs/hermes_kanban_토이_검증_파이프라인_구조_v_1_0.md`
- `mlruns_legacy/`

## Quick Start

```bash
# 환경 확인
python3 -c "import pandas, sklearn, lightgbm, mlflow, transformers, datasets, accelerate, optuna"

# active board 확인
hermes kanban boards list
hermes kanban stats
hermes kanban list --sort created

# 현재 작업 상세
hermes kanban show <task_id>
hermes kanban runs <task_id>
```

Dashboard:

```text
http://localhost:9119/kanban
```

## Data

| 위치 | 용도 |
|---|---|
| `dataset/1.Training/라벨링데이터/` | AI Hub Training 원본, read-only |
| `dataset/2.Validation/라벨링데이터/` | Phase 3 final holdout 후보, Phase 2 학습 fold에 포함 금지 |
| `dataset/sample_5k/` | Phase 2 primary sample, Training에서 stratified seed=42 추출 |
| `dataset/sample/` | Phase 1 toy evidence, read-only |

5K 표본 재생성:

```bash
python3 -m pipelines.extract_5k dataset/1.Training \
  --out dataset/sample_5k \
  --target-n 5000 \
  --seed 42
```

## Pipeline

```bash
# 데이터 audit
python3 pipelines/audit_data.py --input dataset/sample_5k/

# split 생성
python3 pipelines/make_splits.py --input dataset/sample_5k/ --k 5 --output dataset/splits/M<N>/

# CPU baseline
python3 -m pipelines.train \
  --models M1,M2,M3,M4 \
  --cycle-id M<N> \
  --mlflow-uri sqlite:///mlflow.db

# KLUE-RoBERTa
python3 -m pipelines.train \
  --models M5 \
  --model klue/roberta-small \
  --cycle-id M<N> \
  --mlflow-uri sqlite:///mlflow.db

# HPO
python3 -m pipelines.run_hpo \
  --models M4,M5 \
  --cycle-id M<N> \
  --n-trials 30 \
  --mlflow-uri sqlite:///mlflow.db

# 평가
python3 pipelines/evaluate.py --cycle-id M<N>
```

Vast.ai 인증 확인은 `vastai show user`를 쓰지 않습니다. CLI 0.5.0이 현재 API에 `owner=me`를 붙여 실패할 수 있습니다.

```bash
vastai --api-key "$VAST_API_KEY" show instances --raw
vastai --api-key "$VAST_API_KEY" search offers 'gpu_ram>=8 reliability>0.95' --raw
```

## Hard Gates

핵심 운영 규칙은 `AGENTS.md`가 기준입니다. 특히 Phase 2에서 중요한 게이트는 다음입니다.

| Rule | 요약 |
|---|---|
| #1 | test set leakage 금지 |
| #2 | 학생 직접 식별자 모델 입력 금지. `student_grade`만 허용, `student.location`은 split key 전용 |
| #5 | M1 ≤ M2 ≤ M3 ≤ M4 ≤ M5 ≤ M6 strict ordering, bootstrap CI 기반 |
| #8 | 인간 ceiling 비교는 metric 단위 일치 + bootstrap CI hard-block |
| #9 | feature provenance 필수, label-side feature 자동 block |
| #10 | AUDIT task에 `MILESTONE_v2.md` goal anchor verbatim 주입 |
| #11 | cost circuit breaker 초과 시 pause + 인간 알림 |
| #12 | HPO 30 trial+ 필수 |
| #14 | score-band fairness gate: macro-QWK, worst-band QWK, per-band metric 필수 |

Hard Rule #13 PII external-compute gate는 2026-05-28 인간 게이트 통과로 제거됐습니다. 단, Hard Rule #2는 유지됩니다.

## Repository Layout

```text
.
├── AGENTS.md
├── MILESTONE.md
├── MILESTONE_v2.md
├── ACCEPTANCE_CRITERIA.yaml
├── VAST_GPU_GUIDE.md
├── configs/
├── pipelines/
├── tests/
├── docs/
├── reports/
├── skills/
├── workspace/
├── mlflow.db
└── optuna.db
```

문서 색인:

- `docs/README.md`
- `docs/phase_2_mid_scale_design_v_1_1.md`
- `docs/research/vast_ai_essay_workflow_v_1_0.md`
- `docs/research/self_improving_long_running_research_v_1_0.md`
- `docs/research/mlflow_tracing_2026_research_v_1_0.md`

## Profiles

| Profile | 책임 |
|---|---|
| `aristotle` | SYNTH, cycle report, 다음 cycle 등록 |
| `tukey` | AUDIT |
| `gauss` | SPLIT, FEATURE, MODEL, HPO |
| `spearman` | EVAL |
| `turing` | REVIEW |
| `ada-lovelace` | 구현 보조 |

## License

내부 연구용입니다.
