# Project Overview

Hermes Multi-Agent Kanban Board 기반 24시간 자기 발전형 장기 자율 연구 워크플로우 검증 + 실모델 품질 검증.
도메인: 한국어 K-12 에세이 자동채점.
모드: Mid-scale 데이터(5,003건, AI Hub Training stratified seed=42) + KLUE-RoBERTa + Optuna HPO + 정상 파이프라인.

본 프로젝트의 목표는 (1) Hermes 자가발전 long-running chain의 모델 품질 향상 가능성 입증, (2) Phase 1 toy 검증 후 실모델로 PASS_CANDIDATE → PASS_FINAL 진화이다.

# Phase History

- **Phase 1 Toy (종료, 2026-05-27 explicit_stop_decided)**: sample 342건, M1~M4 LightGBM, PASS_CANDIDATE (QWK 0.2402), Cycle 1~3 자가발전 chain 입증. 결과 evidence: `docs/final_report_v_1_0.md`, `docs/hermes_validation_v_1_0.md`, `mlruns_legacy/`.
- **Phase 2 Mid-scale (현재)**: sample 5,003건, M1~M6 (+KLUE-RoBERTa + ensemble), Optuna HPO 30~50 trial, vast.ai 원격 GPU. 진입 evidence: `docs/phase_2_mid_scale_design_v_1_1.md`, `dataset/sample_5k/manifest.json`.

본 AGENTS.md v4는 Phase 1 lesson + Phase 2 mid-scale 진입 결정의 결과물이다.

# Hard Rules (Priority Order)

1. **Test set leakage 금지** — `student.location` 기반 stratified group k-fold (sample 342건은 `student_school` 필드 부재, T1 audit 결과 7개 location 그룹 / max 149로 group split 가능). test fold 라벨은 evaluator만 접근.

2. **학생 개인정보 외부 LLM 전송 금지** — `student_grade` 외에는 모델 입력에 포함하지 않음. `student.location`은 split key로만, 모델 입력 X.

3. **모든 실험은 MLflow 등록** — seed, config_hash, artifact path, `cycle_id`, `kanban_task_id`, `feature_provenance` tag 필수.

4. **Rubric 가중치는 JSON에서 추출** — 하드코딩 금지. `configs/rubric_weights.yaml`로 외부화.

5. **베이스라인 단조 진화 검증 (Mid-scale strict)** — M1 ≤ M2 ≤ M3 ≤ M4 ≤ M5 ≤ M6 strict ordering, fold별 bootstrap CI 95% 적용, `model_lower95 > prev_model_upper95` 시에만 진화 인정. Toy `warn-only` 정책 폐기 (5K에서 noise < hyperparam effect 가정 검증됨).

6. **모든 task 산출물은 metadata에 파일 경로 + 검증 명령 포함**.

7. **실패는 silent 처리 금지** — `kanban_block` + reason + 재현 명령 필수.

8. **인간 ceiling 비교 — metric 단위 일치 + bootstrap CI hard-block (Mid-scale)** —
   - 모델은 `QWK(pred, 3-rater-avg)`로 측정 → ceiling도 동일 비교짝(`ICC(2,k)` 또는 `QWK(rater_i, 3-rater-avg)` 평균) 사용
   - `QWK(rater_i, rater_j)` 단순 짝 비교는 ceiling으로 사용 금지
   - 점추정 단독 block 금지. block 조건: `model_lower95 > ceiling_upper95`만
   - **Mid-scale: hard-block**. Toy `warn-only` 정책 폐기.

9. **(신설) Feature provenance 명시 필수** — 모든 feature에 `source` / `label-side` / `derived` 표시. `label-side` feature 사용 시 **자동 block**. 1차 사이클 T7이 발견한 `paragraph_count`/`correction_count` leakage 재발 방지.

10. **(신설) Goal anchor 재주입 필수** — cycle 첫 sub-task(AUDIT)는 MILESTONE.md의 원본 milestone goal 텍스트를 verbatim 재주입. goal drift 방지 (외부 리서치: arXiv 2505.02709).

11. **(신설) Cost circuit breaker** — `configs/board_config.yaml`의 `cost_circuit_breaker` 임계 초과 시 cycle 자동 pause + 인간 알림 task 생성. soft warning 금지.

12. **(Mid-scale 신설) HPO trial 30+ 필수** — M5/M6 학습 시 Optuna study (TPESampler, MedianPruner) 30 trial 이상. MLflow `parent_run`에 study + 각 trial을 nested run으로 등록. Cycle M2부터 누적 study 재사용. trial 미달 시 acceptance hard-block.

13. **(Mid-scale 신설) Transformer PII 토큰 audit** — RoBERTa fine-tune 전 `pipelines/audit_pii.py --fail-on-hit`가 학습 데이터셋(`dataset/sample_5k/`)에서 0건 통과한 commit hash가 task body에 명시되어야 함. 외부 compute(vast.ai 등) 전송 직전에도 동일 게이트 재실행. Hard Rule #2와 결합 — 외부 LLM 송신 0 + 외부 compute 송신 audit 통과 0.

# Data Locations

- Source full (read-only): `dataset/1.Training/라벨링데이터/` (39,591건, AI Hub) + `dataset/2.Validation/라벨링데이터/` (5,906건, Phase 2 holdout)
- **Mid-scale sample (현 chain primary): `dataset/sample_5k/`** — Training에서 essay_type × grade_group × essay_level stratified 5,003건. 재생성: `python3 -m pipelines.extract_5k dataset/1.Training --out dataset/sample_5k --target-n 5000 --seed 42`. `dataset/sample_5k/manifest.json` 산출.
- Phase 1 evidence (read-only): `dataset/sample/` (342건 toy, 종료된 cycle 재현 참조용)
- Reference PDFs: `dataset/*.pdf` (참고만 — 직접 파싱 X)
- Outputs: `$HERMES_KANBAN_WORKSPACE` 별 격리
- Configs: `configs/`
- MLflow: `mlflow.db` (SQLite, Phase 2 primary). Phase 1 file-store: `mlruns_legacy/`
- Reports: `reports/`
- Skills (Voyager-style library): `skills/` — acceptance_pass된 산출만 누적 (Cycle M2+ 활성)

# Domain Facts (요약 — 자세한 건 dataset_and_rubric_analysis 문서)

- 점수 스케일: 종합 0-30, 항목 0-3 (4단계 behavioral descriptor)
- 평가 차원 3종: 표현 / 구성 / 내용
- Type 2종: 논술형(주장/찬성반대/대안제시) / 수필형(설명글/글짓기)
- 학년군 4종: 초4~5 / 초6~중1 / 중2~고1 / 고2~고3
- 채점자: 3명 (`essay_scoreT`에 raw 3개, `essay_scoreT_avg`에 평균)
- 문단 점수: 표현만 채점 (구성/내용 제외)
- 수필형: 프롬프트 독해력 항목 없음

# Mid-scale Scope (Phase 2, 현재)

- **Sample 5,003건** 5장르 stratified (`dataset/sample_5k/`, AI Hub Training seed=42 추출, PDF 분포 ±2%p 부합)
- Fold: StratifiedGroupKFold **k=10**, group key `student.location` (Phase 3에서 `student_school` 활성 시 교체 검토). 단일 fold valid_n ≥ 300 강제 (sample 5K / k=10 = 500이라 충분 보장).
- Baseline 6종 단조 진화: **M1 dummy → M2 length → M3 TF-IDF+Ridge → M4 LightGBM → M5 KLUE-RoBERTa fine-tune → M6 M4+M5 ensemble**
- HPO: M4/M5/M6에 대해 Optuna 30 trial+ (TPESampler+MedianPruner). Cycle M2+에서 누적 study 재사용 → trial 누적 50+ 도달.
- 평가는 type별, 학년군별, score-band별 분리 + bootstrap CI 95%
- 인간 ceiling: ICC(2,k) + bootstrap CI 95%, hard-block 비교
- **Gate 정책**: Hard Rule #1~#13 모두 **hard-block** (Toy warn-only 폐기)
- 학습 hardware: 로컬 CPU (M1~M4) + vast.ai 원격 GPU (M5/M6 KLUE-RoBERTa fine-tune, 8GB VRAM 권장 RTX 3060). `VAST_GPU_GUIDE.md` 참조.
- PII 게이트: `pipelines/audit_pii.py --fail-on-hit`가 외부 compute 송신 직전 의무 통과 (Hard Rule #13).

# Pipeline Conventions

- Python 3.11+, pandas, scikit-learn, lightgbm, mlflow.
- Random seed: 42 (또는 명시).
- Split: `student.location` 기반 stratified group k-fold (k=5). (`student_school` 필드는 sample 342건에 부재, T1 audit에서 location proxy 승인)
- Feature scaling: 회귀 모델만 StandardScaler.
- Text 전처리: `#@문장구분#` 토큰을 문장 분리자로 처리.
- Tokenization: char + word n-gram (TF-IDF용).

# Build & Test Commands

```bash
# 환경 사전 검증
python3 -c "import pandas, sklearn, lightgbm, mlflow, transformers, optuna" || \
  (echo "missing dep: pip install pandas scikit-learn lightgbm mlflow transformers datasets accelerate optuna" && exit 1)

# 데이터 audit + PII 게이트 (외부 compute 송신 직전 의무, Hard Rule #13)
python3 pipelines/audit_data.py --input dataset/sample_5k/
python3 -m pipelines.audit_pii dataset/sample_5k --report workspace/pii_audit_M<N>.json --fail-on-hit

# 5K subsample 재생성 (deterministic)
python3 -m pipelines.extract_5k dataset/1.Training --out dataset/sample_5k --target-n 5000 --seed 42

# Split 생성 (k=10)
python3 pipelines/make_splits.py --input dataset/sample_5k/ --k 10 --output dataset/splits/M<N>/

# 학습 (CPU baseline M1~M4)
python3 pipelines/train.py --models M1,M2,M3,M4 --cycle-id M<N> --mlflow-uri sqlite:///mlflow.db

# 학습 (vast.ai 원격 GPU, M5 KLUE-RoBERTa) — VAST_GPU_GUIDE.md §11 참조
python3 pipelines/train.py --models M5 --model klue/roberta-small --hpo-trials 30 --cycle-id M<N>

# 평가 + 인간 ceiling 비교 + bootstrap CI
python3 pipelines/evaluate.py --cycle-id M<N>

# 누적 리포트
python3 pipelines/build_report.py --output reports/
```

# Definition of Done (Per Task)

- `kanban_complete` 호출 + metadata에 산출 파일 경로 포함
- MLflow run 등록 (학습 task만) — `cycle_id`, `kanban_task_id`, `feature_provenance` tag 필수
- Reproducibility manifest (seed, config_hash, package versions) 첨부
- 인간 ceiling 대비 비교 metric + bootstrap CI 보고 (평가 task만)
- type별·학년군별 segment metric 분리 (평가 task만)

# Cycle Sub-task Pattern (Mid-scale, 9 sub-task)

매 Cycle MN은 9 sub-task의 chain으로 구성 (HPO 추가):

```
T-CYCLE-MN-AUDIT     (tukey)         ← MILESTONE_v2.md goal 재주입 + PII audit 통과 commit hash 기록
T-CYCLE-MN-SPLIT     (gauss)         ← StratifiedGroupKFold k=10
T-CYCLE-MN-FEATURE   (gauss)         ← TF-IDF + RoBERTa CLS embedding cache
T-CYCLE-MN-MODEL     (gauss)         ← M1~M5 baseline (M5 vast.ai 원격 GPU)
T-CYCLE-MN-HPO       (gauss)         ← Optuna 30 trial+ over M4/M5/M6 (study 누적)
T-CYCLE-MN-EVAL      (spearman)      ┐
T-CYCLE-MN-REVIEW    (turing)        ┘ 병렬 (T-HPO parent)
T-CYCLE-MN-SYNTH     (aristotle)
   ↓ parent
DECIDE-MN            (사용자)        ← [Continue]/[Phase-up]/[Stop]
```

각 sub-task의 parent에는 직전 step만. 단 EVAL과 REVIEW는 HPO를 공통 parent로 가짐 (모델 best run 결정 후 평가/리뷰).

**Full-trace propagation 의무**: 각 sub-task spawn 시 부모 task의 전체 산출(workspace/*, mlflow.db 경로) + 직전 cycle의 skill library 후보를 task body의 Input Context로 명시.

**Cycle ID 명명**: Mid-scale prefix `M` (예: M1, M2, M3). Phase 3 Full 진입 시 prefix `F`.

# DECIDE Task Pattern (DECIDE-N) — Board Native, Script-Free

## Lifecycle
- 인간 결정 task. parent=T-CYCLE-N-SYNTH (SYNTH done 시 ready로 auto-promote)
- 사용자는 UI에서 **task complete 시 코멘트로 결정** 명시:
  - `[Continue]` — 다음 cycle 자동 진행 (SYNTH가 이미 등록한 blocked sub-task chain이 unblock)
  - `[Phase-up]` — Phase 진입 task 생성, 인간 게이트
  - `[Stop]` — 종결, 다음 cycle 진행 X (등록된 blocked sub-task는 사용자가 UI archive)
- timeout 처리는 board_config.yaml `decide_timeout_policy` 참조

## Self-Sustaining Mechanism (핵심)
1. Cycle N의 SYNTH(aristotle) worker가 다음 cycle sub-task 7개 + DECIDE-(N+1)을 미리 등록 (blocked)
2. SYNTH done → DECIDE-N ready (parent dependency)
3. 사용자 DECIDE-N complete → 등록된 Cycle N+1 첫 sub-task(AUDIT) unblock → chain 자동 진행
4. 모든 transition이 board native dependency만으로 동작. **외부 script 0건**.

## Timeout Policy
- 6h grace → default Continue (cycle 내부 chain 진행)
- 6h~24h → Pause (board_config.yaml `decide_n_after_grace`)
- Phase-up DECIDE는 timeout 무시, 무조건 Pause

# Skill Library (Voyager-style, Phase 2 활성)

Cycle synth 산출 중 `acceptance_pass`된 것만 `skills/` 폴더에 누적:
- `skills/<category>/<name>.md` — 재사용 가능 unit 정의
- `skills/index.json` — semantic search index (Cycle M2+ 활성). Cycle M1은 placeholder만 등록.
- 다음 cycle의 SPLIT/FEATURE/HPO 단계에서 retrieve 후 reuse
- Mid-scale 목표: Cycle M3 종료 시점 5+ verified skill 누적 (MILESTONE_v2.md 성공 기준)

Category 예시: `text_preprocessing/`, `feature_engineering/`, `roberta_finetune_patterns/`, `optuna_search_patterns/`, `error_analysis_patterns/`

# When Auditing Data (tukey)

- MILESTONE.md goal 재주입 (Hard Rule #10)
- 5종 검사: shape, dtype, NaN, duplicates, target 분포
- leakage 검사 4종: ID 중복, 시간 누수, target 누수, group(`student.location`) 누수
- 라벨 분포 불균형(>5x) 발견 시 자동 보고 + 가중치/리샘플 정책 제안

# When Splitting (gauss + aristotle)

- `student.location` 기반 StratifiedGroupKFold k=10 (Phase 3에서 `student_school` 활성 시 교체)
- Type×학년군 stratify
- split 후 leakage 재검증 필수
- split manifest YAML로 저장 + hash
- fold별 valid 크기 보고 — 단일 fold valid_n < **300** 시 **hard-block** (Mid-scale strict)

# When Modeling (gauss + ada-lovelace)

- 가장 단순한 모델부터 (dummy → length → TF-IDF → LightGBM → KLUE-RoBERTa → ensemble)
- 모든 모델 보고 4종 정보: 가정, 학습 시간, valid metric, 예측 분포
- Train/valid metric gap > 10%면 자동 overfit 경보
- 구현은 `kanban-codex-lane` 스킬로 git worktree에서 격리 (선택)
- **Feature provenance tag 필수** (Hard Rule #9)
- **MLflow tracking URI: `sqlite:///mlflow.db`** (Phase 2 primary). argument `--mlflow-uri sqlite:///mlflow.db` 명시. Phase 1 file-store evidence는 `mlruns_legacy/`에 보존됨.

## CPU 모델 (M1~M4)

- 로컬 실행. `python3 pipelines/train.py --models M1,M2,M3,M4 --cycle-id MN --mlflow-uri sqlite:///mlflow.db`

## Transformer 모델 (M5 KLUE-RoBERTa)

- 권장 모델: `klue/roberta-small` (68M) 진입, 안정화 후 `klue/roberta-base` (110M)
- HuggingFace cache 고정: `HF_HOME=/home/dev/.cache/huggingface` (sandbox network=false 대응, 사전 다운로드)
- 실행 위치: vast.ai 원격 GPU (8GB VRAM, RTX 3060 기준 cycle당 ~1.5h). `VAST_GPU_GUIDE.md` 절차.
- **업로드 직전 의무 게이트**: `python3 -m pipelines.audit_pii dataset/sample_5k --fail-on-hit` 통과 (Hard Rule #13). exit=0인 commit hash를 task body에 기록.
- 원격 학습 종료 후 `mlflow.db`와 `workspace/cycle_MN/models/` 회수 → 로컬 mlflow.db에 merge

## Ensemble (M6)

- M4 LightGBM + M5 RoBERTa 예측을 valid set에 대해 stacking (logistic regression meta-learner)
- 단조 진화 검증: `M6_lower95 > M5_upper95` (Hard Rule #5)

# When HPO (gauss)

- Library: Optuna. Sampler: `TPESampler(seed=42)`. Pruner: `MedianPruner(n_startup_trials=5)`.
- Storage: `sqlite:///optuna.db` (cycle 간 study 누적). Study 이름: `cycle_MN_<model_id>`.
- 최소 trial: **30 (Hard Rule #12)**. Cycle MN+1에서 동일 study 재개 시 누적 50+ 도달 권장.
- 각 trial은 MLflow nested run으로 등록 (`mlflow.start_run(nested=True)`). parent run에 study summary + best_params.
- Search space (M5 KLUE-RoBERTa 예시):
  - `learning_rate`: log-uniform [1e-5, 5e-5]
  - `per_device_train_batch_size`: categorical [8, 16, 32]
  - `num_train_epochs`: int [2, 5]
  - `weight_decay`: log-uniform [1e-4, 1e-2]
  - `warmup_ratio`: uniform [0.0, 0.1]
- Cost circuit breaker (Hard Rule #11) 임계 도달 시 study 중단 + 인간 알림 task spawn.

# When Evaluating (spearman)

- metric 3가지 형태로 보고: overall / per-segment / acceptance 비교
- segment: by type / by 학년군 / by score_band
- Confidence interval 또는 bootstrap 표준편차 동반
- 인간 ceiling 대비 거리 명시 (metric 단위 일치 필수)
- baseline 단조 진화 검증

# When Reviewing (turing)

- WRONG / FRAGILE / STYLE 분류로 보고
- failing test 없으면 APPROVE 금지
- split leakage 재검증 필수
- reproducibility manifest 확인
- **Feature provenance audit** — label-side feature 0건 확인 (Hard Rule #9)
- **HPO trial 수 ≥ 30 확인** (Hard Rule #12) — Optuna study summary 첨부
- **PII audit gate commit hash 확인** (Hard Rule #13) — `dataset/sample_5k/`에 대해 `audit_pii --fail-on-hit` 통과한 SHA가 AUDIT task body에 기록되어 있는지

# When Synthesizing (aristotle)

- 7 sub-task 산출 종합 → cycle_N_report.md
- ACCEPTANCE_CRITERIA.yaml과 비교 → judgement enum 명시 (PASS_FINAL/PASS_CANDIDATE/FAIL_* 8종)
- 다음 cycle 권고 작성 (DECIDE-N 본문에 자동 첨부)
- skill library 후보 추출 (Voyager-style, Cycle 3+ 활성)

**자가발전 핵심 책임 (Script-Free)**:
- judgement가 PASS_FINAL이 아니고 + acceptance_pass 미달 시:
  - `hermes kanban create`로 다음 cycle sub-task 7개 + DECIDE-(N+1) 등록 (모두 todo, 부모 의존성으로 자동 chain)
  - **task 명명 규칙 (mixed: 영어 prefix + 한글 설명)**:
    - `T-CYCLE-(N+1)-AUDIT: 데이터 검증`
    - `T-CYCLE-(N+1)-SPLIT: 분할 정책`
    - `T-CYCLE-(N+1)-FEATURE: 피처 엔지니어링`
    - `T-CYCLE-(N+1)-MODEL: 베이스라인 학습`
    - `T-CYCLE-(N+1)-EVAL: 다축 평가`
    - `T-CYCLE-(N+1)-REVIEW: 코드/누수 리뷰`
    - `T-CYCLE-(N+1)-SYNTH: 종합 + 다음 cycle 등록`
    - `DECIDE-(N+1): 인간 결정 (Cycle N+1)`
    - 영어 prefix는 CLI/grep 친화 + cycle 진행 단계 식별, 한글 설명은 도메인 친화
  - **핵심 의존성**: T-CYCLE-(N+1)-AUDIT의 **parent = DECIDE-N** 으로 설정. 즉 DECIDE-N done 시에만 Cycle N+1 chain 시작.
  - 내부 chain: DECIDE-N → AUDIT → SPLIT → FEATURE → MODEL → (EVAL || REVIEW) → SYNTH → DECIDE-(N+1)
  - 모든 sub-task 등록 시 parent의 workspace 산출 경로를 Input Context로 명시 (Full-trace propagation)
  - T-CYCLE-(N+1)-AUDIT body에 `MILESTONE.md` verbatim 주입 (Hard Rule #10)
- judgement가 PASS_FINAL이면 → 다음 cycle 등록 X (production 단계 전환 필요, 인간 게이트)
- judgement가 **PASS_CANDIDATE**이면 → **다음 cycle sub-task 7 + DECIDE-(N+1) 등록** (FAIL 분기와 동일 패턴). Cycle N+1 AUDIT body에 "직전 cycle PASS_CANDIDATE 상태에서의 추가 검증 또는 skill library 수집 목적" 명시. 사용자 [Continue] 선택 시 chain 자동 시작.
- 사용자가 DECIDE-N에서 [Stop] 선택 시: 등록된 Cycle N+1 task들은 사용자가 UI에서 일괄 archive
- 사용자가 DECIDE-N에서 [Phase-up] 선택 시: 등록된 Cycle N+1 task들은 사용자가 archive + 별도 T-PHASE-MIGRATE 등록
- 외부 script (cron/decompose.py 등) 호출 금지. 모든 spawn은 `hermes kanban create` CLI inline 호출만.

# Forbidden (Mid-scale Phase)

- 풀 Validation 5,906건을 학습 fold에 포함 (Phase 3 holdout 보존)
- `klue/roberta-large` (337M, 24GB VRAM 필요 — Phase 2 GPU budget 초과)
- 학생 PII를 외부 LLM 송신 (Hard Rule #2) **또는 외부 compute 송신 audit 미통과** (Hard Rule #13)
- Final model registration / champion alias (production 진입은 Phase 4 인간 게이트)
- Hold-out test set 분리 (k=10 fold CV로 대체. Validation set은 Phase 3에서 final holdout으로)
- Hard Rule 본문 자율 수정 (AGENTS_LOCKED 영역)
- DECIDE timeout 시 Phase 자동 진행 (board_config.yaml phase_transition: Pause)
- 외부 script로 cycle 자동화 (`cron`, `cycle_decompose.py` 등) — 모든 cycle chain은 hermes board native dependency + SYNTH의 inline `hermes kanban create` 만 허용
- HPO trial < 30 인 acceptance 통과 (Hard Rule #12)

# Escalation

- task 3회 실패 → 자동 blocked → 인간 게이트 task 자동 생성
- 베이스라인 단조성 위반 → toy: warn 기록 / full: blocked
- 누수 검사 통과 못함 → 자동 blocked → split 재설계
- 인간 ceiling 초과 metric → toy: warn / full: blocked → leakage 의심
- cost circuit breaker 초과 → cycle 자동 pause + 알림
- 3 cycle 연속 acceptance fail → 자동 blocked + Layer 3 escalation
- 디스크 100MB 초과 → `hermes kanban gc` 실행

# Human Approval Required

- Toy 검증 → 풀 프로덕션 확장 결정 (Phase-up DECIDE)
- 학생 PII 정책 변경 (Hard Rule #2)
- 모델 등록 (현 단계 X — Forbidden)
- Acceptance criteria 변경 (ACCEPTANCE_CRITERIA.yaml 본문)
- Hard Rule 본문 변경 (AGENTS_LOCKED)
- Champion alias 교체
- 외부 배포

# References

- `MILESTONE.md` — Phase 1 Toy milestone (종료, Hard Rule #10 source 원본)
- `MILESTONE_v2.md` — Phase 2 Mid-scale milestone (현재, Hard Rule #10 source)
- `docs/phase_2_mid_scale_design_v_1_1.md` — Phase 2 진입 설계 + 인프라/리스크/일정
- `docs/research/vast_ai_essay_workflow_v_1_0.md` — vast.ai × Essay 운영 evidence
- `VAST_GPU_GUIDE.md` — vast.ai 원격 GPU 작업 절차
- `docs/self_improving_architecture_v_1_0.md` — Cycle 2+ Layer 1-4 architecture
- `docs/escalation_matrix_v_1_0.md` — 실패 행동 매트릭스
- `docs/research/self_improving_long_running_research_v_1_0.md` — 외부 사례 리서치 (Voyager, AutoGPT, Devin)
- `docs/research/mlflow_tracing_2026_research_v_1_0.md` — MLflow Tracing 도입 검토
- `docs/mlflow_기반_ai_서술형_자동채점_실험추적_리포트_가이드_v_1_0.md` — MLflow 운영 가이드
- `docs/hermes_validation_v_1_0.md` — Phase 1 1차 사이클 9-Point 검증
- `docs/final_report_v_1_0.md` — Phase 1 1차 사이클 종합 판정
- `configs/board_config.yaml` — 자가발전 cycle 운영 설정
- `dataset/sample_5k/manifest.json` — 현 cycle primary 5K 추출 spec
