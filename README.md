# Essay Auto-Scoring Research

<p>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="pandas" src="https://img.shields.io/badge/pandas-150458?style=flat-square&logo=pandas&logoColor=white">
  <img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white">
  <img alt="LightGBM" src="https://img.shields.io/badge/LightGBM-02569B?style=flat-square">
  <img alt="Hugging Face Transformers" src="https://img.shields.io/badge/Hugging%20Face-Transformers-FFD21E?style=flat-square&logo=huggingface&logoColor=black">
  <img alt="KLUE-RoBERTa" src="https://img.shields.io/badge/KLUE--RoBERTa-model-4B5563?style=flat-square">
  <img alt="Optuna" src="https://img.shields.io/badge/Optuna-HPO-3B82F6?style=flat-square">
  <img alt="MLflow" src="https://img.shields.io/badge/MLflow-tracking-0194E2?style=flat-square&logo=mlflow&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white">
  <img alt="Hermes Kanban" src="https://img.shields.io/badge/Hermes-Kanban-111827?style=flat-square">
  <img alt="Vast.ai" src="https://img.shields.io/badge/Vast.ai-GPU-16A34A?style=flat-square">
</p>

![alt text](assets/cover.png)

한국어 K-12 서술형 에세이 자동채점 연구를 Hermes Multi-Agent Kanban Board로 장기 자율 실행하는 검증 프로젝트입니다.

현재 기준은 **Phase 3 Mid Multi-task**입니다. Phase 1 toy 검증과 Phase 2 scalar 모델 검증은 종료됐고, 지금은 5,003건 표본에서 3개 rubric head + overall head를 함께 학습하는 multi-task KLUE-RoBERTa/HPO/ensemble workflow를 검증합니다.

## Current State

| 항목 | 현재 값 |
|---|---|
| Active board | `essay-auto-scoring-research-phase3` |
| Phase | Phase 3 Mid Multi-task |
| Primary data | `dataset/sample_5k/` |
| Active cycle | `M2R` recovery chain |
| Models | M1-M4 CPU baseline, M5 multi-task KLUE-RoBERTa, M6 multi-output ensemble |
| Tracking | `sqlite:///mlflow.db`, `sqlite:///optuna.db` |
| Human gate | `DECIDE-*`에서 `[Continue]`, `[Phase-up]`, `[Stop]` |

현재 source of truth:

- Project rules: `AGENTS.md`
- Phase goal: `MILESTONE_v3.md`
- Gates: `ACCEPTANCE_CRITERIA.yaml`
- Docs index: `docs/README.md`

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
| `dataset/2.Validation/라벨링데이터/` | final holdout 후보, 현재 학습 fold 포함 금지 |
| `dataset/sample_5k/` | Phase 3 primary sample, Training에서 stratified seed=42 추출 |
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

# split 생성: 기본 k=5
python3 pipelines/make_splits.py \
  --input dataset/sample_5k/ \
  --k 5 \
  --output workspace/cycle_M<N>/splits \
  --cycle-id M<N> \
  --kanban-task-id <task_id> \
  --min-valid-n 300 \
  --group-key student.location

# M2 승인 fallback: 기본 k=5 valid_n 실패 evidence 보존 후 region merge + k=3
python3 pipelines/make_splits.py \
  --input dataset/sample_5k/ \
  --k 3 \
  --output workspace/cycle_M<N>/splits \
  --cycle-id M<N> \
  --kanban-task-id <task_id> \
  --min-valid-n 300 \
  --group-key region \
  --audit-table workspace/cycle_M<N>/audit/data_audit/audit_table_no_raw_text.csv

# CPU baseline
python3 -m pipelines.train \
  --models M1,M2,M3,M4 \
  --cycle-id M<N> \
  --mlflow-uri sqlite:///mlflow.db

# Phase 3 acceptance용 M5/M6는 legacy scalar command 금지.
# multi-task launcher/spec은 docs/multi_task_채점모델_구현_스펙_v_1_1.md를 따른다.

# HPO
python3 -m pipelines.run_hpo \
  --model M4 \
  --cycle-id M<N> \
  --n-trials 30 \
  --study-name cycle_M<N>_M4 \
  --storage sqlite:///optuna.db \
  --mlflow-uri sqlite:///mlflow.db \
  --experiment-name essay-auto-scoring-phase3 \
  --kanban-task-id <task_id> \
  --split-dir workspace/cycle_M<N>/splits \
  --feature-dir workspace/cycle_M<N>/features \
  --label-dir dataset/sample_5k/ \
  --output-dir workspace/cycle_M<N>/hpo

# 평가
python3 pipelines/evaluate.py --cycle-id M<N>
```

Vast.ai 인증 확인은 `vastai show user`를 쓰지 않습니다. CLI 0.5.0이 현재 API에 `owner=me`를 붙여 실패할 수 있습니다.

```bash
vastai --api-key "$VAST_API_KEY" show instances --raw
vastai --api-key "$VAST_API_KEY" search offers 'gpu_ram>=8 reliability>0.95' --raw
```

## Repository Layout

```text
.
├── AGENTS.md
├── MILESTONE.md
├── MILESTONE_v2.md
├── MILESTONE_v3.md
├── ACCEPTANCE_CRITERIA.yaml
├── VAST_GPU_GUIDE.md
├── configs/
├── pipelines/
├── tests/
├── docs/
│   ├── README.md
│   ├── archive/
│   └── research/
├── reports/          # optional generated reports, ignored when absent
├── skills/
├── workspace/        # ignored runtime artifacts
├── mlflow.db         # ignored runtime DB
└── optuna.db         # ignored runtime DB
```

## Profiles

| Profile | 책임 |
|---|---|
| `aristotle` | SYNTH, cycle report, 다음 cycle 등록 |
| `tukey` | AUDIT |
| `gauss` | SPLIT, FEATURE, MODEL, HPO |
| `spearman` | EVAL |
| `turing` | REVIEW |
| `ada-lovelace` | 구현 보조 |

## Archive

완료된 Phase 1/2 문서, 발표 자료, 리뷰 체크리스트, 구버전 스펙은 `docs/archive/` 아래로 이동했습니다. 운영 기준은 루트 문서와 `docs/README.md`의 active 문서 목록을 따릅니다.

## License

Code in this repository is licensed under the [MIT License](LICENSE).

Dataset files, source PDFs, and external model/data assets remain subject to
their original provider terms. Verify redistribution rights before reusing data
files outside this repository.
