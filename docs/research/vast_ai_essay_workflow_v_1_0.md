# Vast.ai × Essay Phase 2 Operating Evidence v1.0

> 갱신일: 2026-05-28
> 범위: Phase 2 mid-scale 5K + KLUE-RoBERTa + Optuna HPO에서 vast.ai 원격 GPU를 사용하는 운영 근거

## 1. Decision Summary

| 항목 | 결정 |
|---|---|
| GPU provider | vast.ai |
| Entry model | `klue/roberta-small` |
| Minimum GPU | 8GB VRAM |
| Expected cost | RTX 3060 8GB 기준 cycle당 대략 $0.10~$0.30 |
| Auth check | `vastai --api-key "$VAST_API_KEY" show instances --raw` |
| Forbidden check | `vastai show user`, `vastai --explain` |
| Data policy | Hard Rule #13 external-compute PII gate 제거, Hard Rule #2는 유지 |

Hard Rule #13은 2026-05-28 인간 게이트 통과로 제거됐습니다. 본 데이터셋은 AI Hub 공공 한국 K-12 에세이로 사전 익명화 완료됐다고 보고 외부 GPU 전송을 허용합니다. 단, 학생 직접 식별자를 모델 입력 feature로 쓰는 것은 계속 금지됩니다.

## 2. Current Vast CLI Finding

`vastai 0.5.0`에서 다음 명령은 현재 API와 충돌할 수 있습니다.

```bash
vastai show user
```

관찰된 원인:

```text
/api/v0/users/current?owner=me
```

현재 Vast API schema는 `owner` query parameter를 extra input으로 거부합니다. 따라서 인증 확인은 아래처럼 수행합니다.

```bash
vastai --api-key "$VAST_API_KEY" show instances --raw
vastai --api-key "$VAST_API_KEY" search offers 'gpu_ram>=8 reliability>0.95' --raw
```

또한 `vastai --explain`은 API key를 평문 출력할 수 있으므로 사용하지 않습니다.

## 3. Data Flow

```text
[local]                                      [vast.ai instance]
dataset/sample_5k/
pipelines/
configs/
AGENTS.md
VAST_GPU_GUIDE.md
        scp/rsync -----------------------> /workspace/essay/
                                             |
                                             v
                                   python3 -m pipelines.train
                                   python3 -m pipelines.run_hpo
                                             |
                                             v
                                   mlflow.db, optuna.db,
                                   workspace/cycle_MN/
        scp/rsync <----------------------- artifacts
```

업로드 전 별도 PII gate는 요구하지 않습니다. 대신 다음은 유지합니다.

- 모델 입력 feature provenance 확인
- `student.location`은 split key 전용
- `student_grade` 외 학생 관련 직접 식별자는 모델 입력 금지
- 결과 artifact에 seed, config hash, package versions, MLflow run id 기록

## 4. Risk Matrix

| # | 위험 | 영향 | mitigation |
|---|---|---|---|
| 1 | `destroy instance` 누락 | 과금 누적 | `trap` 또는 작업 종료 후 명시적 destroy |
| 2 | API key 로그 노출 | 비용/보안 사고 | `.env`만 사용, `--explain` 금지, 노출 시 revoke |
| 3 | 잘못된 auth health check | worker block 반복 | `show instances --raw`와 `search offers --raw`만 사용 |
| 4 | SSH host key 무시 | MITM 위험 | `StrictHostKeyChecking=accept-new` 사용 |
| 5 | onstart READY 미수신 | 시간 낭비 | deadline 후 destroy + 다른 offer |
| 6 | HF 모델 반복 다운로드 | 시간 증가 | `HF_HOME=/workspace/hf_cache` 고정 |
| 7 | MLflow DB merge 충돌 | evidence 단절 | 원격 DB 별도 회수 후 local primary에 merge 또는 artifact로 보존 |
| 8 | spot interruption | 학습 중단 | reliability 높은 offer, checkpoint/MLflow artifact 보존 |

## 5. Cost Model

| 시나리오 | GPU | 시간 | 예상 비용 |
|---|---|---:|---:|
| roberta-small + short train | RTX 3060 8GB | 1~2h | $0.05~$0.20 |
| roberta-small + HPO 30 | RTX 3060 8GB | 1.5~3h | $0.10~$0.30 |
| roberta-base fp16 + HPO 30 | RTX 3060 12GB+ | 2~4h | $0.20~$0.60 |

`configs/board_config.yaml`의 `max_usd_per_cycle: 20.0`은 Phase 2 small/base 실험에는 충분히 큰 hard cap입니다.

## 6. Minimal Checklist

```bash
# 1. auth/network
vastai --api-key "$VAST_API_KEY" show instances --raw
vastai --api-key "$VAST_API_KEY" search offers 'gpu_ram>=8 reliability>0.95' --raw

# 2. local deps
python3 -c "import transformers, datasets, accelerate, optuna, mlflow"

# 3. run path
python3 -m pipelines.train --models M5 --model klue/roberta-small --cycle-id M<N>
python3 -m pipelines.run_hpo --models M5 --cycle-id M<N> --n-trials 30
```

## 7. References

- `../../VAST_GPU_GUIDE.md`
- `../../AGENTS.md`
- `../../MILESTONE_v2.md`
- Vast.ai docs: https://vast.ai/docs/
- HuggingFace KLUE: https://huggingface.co/klue
