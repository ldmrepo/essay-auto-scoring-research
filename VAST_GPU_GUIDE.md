# Vast.ai GPU 임대 가이드 — Essay Auto-Scoring v2

> 대상 작업: Phase 2 mid-scale (5K essay, KLUE-RoBERTa fine-tune + Optuna HPO)
> 본 가이드는 학생 PII가 외부 compute로 새지 않도록 audit gate를 의무 단계로 둔다.

## 0. 사전 준비

```bash
# CLI 설치
pip install vastai

# API 키는 .env에서 load (절대 git/로그/공유 채널에 노출 금지)
export VAST_API_KEY=$(grep -E '^VAST_API_KEY=' .env | cut -d= -f2-)
vastai show user   # 인증 확인
```

`.env` 템플릿은 `.env.example` 참고. 키 노출 의심 시 즉시 vast.ai 콘솔에서 revoke + regenerate.

## 1. GPU 검색 (모델별 권장 조건)

| 모델 | VRAM 필요 | 검색 조건 |
|---|---|---|
| klue/roberta-small (68M) | 4 GB | `gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95 inet_down>200` |
| klue/roberta-base (110M, fp16) | 7 GB | `gpu_ram>=8 num_gpus=1 dph<=0.15 reliability>0.95 inet_down>200` |
| klue/roberta-base (fp32) | 12 GB | `gpu_ram>=12 num_gpus=1 dph<=0.15 reliability>0.95 inet_down>200` |
| klue/roberta-large (337M) | 24 GB | `gpu_ram>=24 num_gpus=1 dph<=0.40 reliability>0.95 inet_down>300` |

```bash
vastai search offers 'gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95 inet_down>200' \
  -o 'dph' --limit 5
```

추천 진입: RTX 3060 8GB ($0.04~0.08/hr) — Phase 2 첫 cycle (M1) 적정.

## 2. 인스턴스 생성

```bash
OFFER_ID=<위 검색 결과의 id>
vastai create instance $OFFER_ID \
  --image pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime \
  --disk 50 \
  --onstart-cmd "pip install transformers==4.44.* datasets accelerate optuna scikit-learn lightgbm mlflow && echo READY"
```

`onstart-cmd` 의 `&& echo READY`는 준비 완료 detection용. 15분 안에 `READY`가 안 보이면 destroy 후 다른 offer 선택.

## 3. 인스턴스 상태 + SSH URL 확인

```bash
INSTANCE_ID=<create 시 반환된 id>
vastai show instance $INSTANCE_ID
vastai ssh-url $INSTANCE_ID    # ssh://root@sshX.vast.ai:PORT
```

loading → running 전환까지 15~60초. running이 되었어도 onstart-cmd 완료(READY)까지 추가 1~3분.

## 4. PII Audit (의무 단계 — 업로드 전 절대 생략 금지)

학생 PII를 vast.ai 인스턴스로 보내는 것은 AGENTS.md Hard Rule #2 정신에 위배될 수 있다. 본 단계를 통과한 데이터만 업로드한다.

경로 `dataset/sample_5k`는 Phase 2 setup이 50K 원본에서 stratified 추출 후 생성하는 산출물 (Phase 1 시점엔 존재하지 않음). Toy 검증 시엔 `dataset/sample` 로 대체.

```bash
# Phase 2 5K subsample 디렉토리에 대해 audit (예시 경로: dataset/sample_5k/)
python3 -m pipelines.audit_pii dataset/sample_5k \
  --report workspace/pii_audit_pre_upload.json \
  --fail-on-hit
echo "audit exit=$?"   # 반드시 0이어야 다음 단계 진행
```

`--fail-on-hit`가 exit 1을 내면 업로드 중단, `workspace/pii_audit_pre_upload.json` 검토 후 수동 redact 또는 해당 essay 제외.

## 5. 파일 업로드 (auto-destroy trap 패턴)

`destroy` 누락 시 과금이 계속 누적된다. trap으로 자동화한다.

```bash
HOST=sshX.vast.ai   # ssh-url 결과에서 추출
PORT=12345          # ssh-url 결과에서 추출

# 종료 시 자동 destroy 보장 (Ctrl-C, 스크립트 실패 모두 cover)
trap 'echo "destroying $INSTANCE_ID"; vastai destroy instance "$INSTANCE_ID"' EXIT

scp -o StrictHostKeyChecking=accept-new -P $PORT \
  -r dataset/sample_5k pipelines configs AGENTS.md \
  root@$HOST:/workspace/essay/
```

`StrictHostKeyChecking=accept-new`: 첫 접속은 자동 허용, 이후 변경은 거부 (no보다 안전).

## 6. 원격 실행 (KLUE-RoBERTa fine-tune + Optuna)

인자 `--model klue/roberta-small`, `--hpo-trials 30`은 Phase 2 train.py 확장 시점부터 가용 (Phase 1 train.py는 `--models M1,M2,M3,M4` 형태). Cycle M1 setup 단계에서 train.py를 RoBERTa+Optuna 지원하도록 확장 필요.

```bash
ssh -o StrictHostKeyChecking=accept-new -p $PORT root@$HOST \
  "cd /workspace/essay && \
   HF_HOME=/workspace/hf_cache \
   python3 -m pipelines.train \
     --mlflow-uri sqlite:///mlflow.db \
     --cycle-id M1 \
     --model klue/roberta-small \
     --hpo-trials 30"
```

학습 중 진행은 SSH 세션에서 직접 모니터, 종료 후 결과 회수.

## 7. 결과 회수

```bash
scp -P $PORT root@$HOST:/workspace/essay/mlflow.db ./mlflow_remote_M1.db
scp -P $PORT -r root@$HOST:/workspace/essay/workspace/cycle_M1 ./workspace/

# 로컬 MLflow와 merge가 필요하면 별 도구 (Phase 2 운영 evidence 문서 참조)
```

## 8. 종료 (trap이 동작했다면 자동 처리됨, 수동 확인)

```bash
vastai show instances    # 비어있어야 OK
# 만약 남아있다면
vastai destroy instance $INSTANCE_ID
```

## 9. 비용 참고 (Phase 2 추정)

| 작업 | GPU | 소요 | 비용 |
|---|---|---|---|
| roberta-small + 5K + HPO 30 trial | RTX 3060 8GB | ~1.5 h | ~$0.06~0.15 |
| roberta-base fp16 + 5K + HPO 30 | RTX 3060 12GB | ~2 h | ~$0.10~0.30 |
| onstart-cmd pip install | - | ~2분 | ~$0.003 |
| 데이터 업로드 (5K, ~10MB) | - | <1분 | ~$0 |

`board_config.yaml`의 `cost_circuit_breaker.max_usd_per_cycle`(Phase 2 권장 $50)와 통합 추적 권장.

## 10. 주의사항

- onstart-cmd `READY` echo 15분 초과 → destroy 후 다른 offer
- 한글 파일명 SCP 간헐 실패 → 재시도 또는 zip 후 전송
- **반드시 `vastai destroy` 또는 trap으로 정리** (과금 방지)
- `vastai show instances`로 잔존 인스턴스 0건 정기 확인
- **Hard Rule #2: 학생 PII 외부 LLM/compute 전송 금지** — §4 audit gate 절대 생략 금지
- API 키는 `.env`만, git/echo/로그/스크린샷 노출 금지

## 11. 빠른 참조 (1회 cycle 전체 흐름)

⚠️ 본 quick-ref는 Phase 2 pipeline 정비 후 동작. `vastai create --raw` 출력 schema (`new_contract` key)는 vastai CLI 버전 호환 확인 필요 (https://vast.ai/docs).

```bash
# 0. 환경
export VAST_API_KEY=$(grep -E '^VAST_API_KEY=' .env | cut -d= -f2-)

# 1. PII audit (의무 gate)
python3 -m pipelines.audit_pii dataset/sample_5k \
  --report workspace/pii_audit_pre_upload.json --fail-on-hit || exit 1

# 2. 검색 + 생성
OFFER_ID=$(vastai search offers 'gpu_ram>=8 num_gpus=1 dph<=0.10 reliability>0.95' -o 'dph' --raw \
           | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
INSTANCE_ID=$(vastai create instance $OFFER_ID \
  --image pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime --disk 50 \
  --onstart-cmd "pip install transformers==4.44.* datasets accelerate optuna scikit-learn lightgbm mlflow && echo READY" \
  --raw | python3 -c "import sys,json; print(json.load(sys.stdin)['new_contract'])")
trap 'echo "destroying $INSTANCE_ID"; vastai destroy instance "$INSTANCE_ID"' EXIT

# 3. URL 대기
sleep 90 && SSH_URL=$(vastai ssh-url $INSTANCE_ID)
HOST=$(echo $SSH_URL | sed -E 's|ssh://root@([^:]+):.*|\1|')
PORT=$(echo $SSH_URL | sed -E 's|.*:([0-9]+)$|\1|')

# 4. 업로드 + 실행 + 회수
scp -o StrictHostKeyChecking=accept-new -P $PORT -r \
  dataset/sample_5k pipelines configs AGENTS.md root@$HOST:/workspace/essay/
ssh -o StrictHostKeyChecking=accept-new -p $PORT root@$HOST \
  "cd /workspace/essay && HF_HOME=/workspace/hf_cache python3 -m pipelines.train \
     --mlflow-uri sqlite:///mlflow.db --cycle-id M1 --model klue/roberta-small --hpo-trials 30"
scp -P $PORT root@$HOST:/workspace/essay/mlflow.db ./mlflow_remote_M1.db
scp -P $PORT -r root@$HOST:/workspace/essay/workspace/cycle_M1 ./workspace/

# 5. trap이 destroy 호출
```
