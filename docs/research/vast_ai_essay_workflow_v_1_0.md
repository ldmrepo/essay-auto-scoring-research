# Vast.ai × Essay Phase 2 운영 Evidence v1.0

> 문서 버전: v1.0 · 작성일: 2026-05-27
> 범위: Phase 2 mid-scale (5K essay + KLUE-RoBERTa + Optuna)에서 vast.ai 임대 GPU를 안전·효율적으로 사용하기 위한 운영 evidence 모음. `VAST_GPU_GUIDE.md`(작업 절차)의 근거 문서.

## 1. 의사결정 요약

| 항목 | 결정 | 근거 |
|---|---|---|
| GPU 공급자 | vast.ai | 시간당 단가 최저 (~$0.05/hr RTX 3060), API/CLI 단순, 한국 인근 region 가용 |
| 진입 모델 | klue/roberta-small (68M) | 8GB VRAM로 충분, 5K + HPO 30 trial 1~1.5h |
| 첫 cycle 예산 | < $0.30 | RTX 3060 8GB × 2h max, board_config $20/cycle cap 내 (대형 모델 시 $50 상향 검토) |
| 데이터 전송 보호 | `pipelines.audit_pii --fail-on-hit` gate | Hard Rule #2 정신(외부 compute로 PII 송신 금지) |
| Auto-destroy | shell `trap ... EXIT` 패턴 | 누락 시 과금 누적 → 운영 위험 #1 |

## 2. 데이터 흐름

```
[로컬]                                         [vast.ai 인스턴스]
dataset/sample_5k/ ──audit──┐
                            ↓
              workspace/pii_audit_pre_upload.json  (gate)
                            ↓ (pii_hits=0 일 때만)
        scp ─────────────────────────────────►  /workspace/essay/dataset/sample_5k/
        scp pipelines/, configs/, AGENTS.md ─►  /workspace/essay/
                                                       │
                                                       ▼
                                            python3 -m pipelines.train
                                            (KLUE-RoBERTa + Optuna)
                                                       │
                                                       ▼
                                            /workspace/essay/mlflow.db
                                            /workspace/essay/workspace/cycle_M1/
                                                       │
        scp ◄──────────────────────────────────────────┘
mlflow_remote_M1.db, workspace/cycle_M1/

                            ▼
        (옵션) MLflow merge로 누적 보드에 통합
                            ▼
       reports/latest/cumulative_report.html
```

## 3. 위험 분석 + mitigation

| # | 위험 | 영향 | mitigation |
|---|---|---|---|
| 1 | `vastai destroy` 누락 | 과금 누적 (~$1~5/일) | shell `trap "vastai destroy instance $ID" EXIT` 의무, `vastai show instances` 정기 점검 |
| 2 | API 키 git/로그 노출 | 임의 인스턴스 생성 → 비용 폭주 | `.env`만 보관, `.gitignore` `.env` 차단, 가이드 내 `$(grep ... .env)` 패턴, 노출 의심 시 즉시 revoke |
| 3 | 학생 PII 외부 송신 (Hard Rule #2 정신) | 컴플라이언스 위반 | `pipelines.audit_pii --fail-on-hit`을 업로드 전 의무 gate로, audit report `workspace/pii_audit_pre_upload.json` 보존 |
| 4 | onstart-cmd `READY` 미수신 (장기 hang) | 시간 낭비 | 15분 deadline → destroy 후 다른 offer |
| 5 | MITM (SSH host key 자동 수락) | 데이터 가로채기 | `-o StrictHostKeyChecking=accept-new` 사용 (`no` 금지) |
| 6 | 한글 파일명 SCP 실패 | 데이터 누락 | 사전 zip 또는 재시도, `--ascii-filename` 옵션 활용 검토 |
| 7 | HF 모델 매번 다운로드 | cycle당 2~5분 추가 | `HF_HOME=/workspace/hf_cache` 고정, persistent volume 검토 |
| 8 | MLflow DB 결과 merge 충돌 | 누적 evidence 단절 | 원격 결과는 `mlflow_remote_<cycle>.db`로 별 보관, 누적 보드는 로컬 SQLite로 일원화 |
| 9 | 추정치보다 오래 걸려 예산 초과 | cost cap trip | board_config cost_circuit_breaker로 자동 차단, gauss profile이 인간 escalation |
| 10 | Spot 인스턴스 강제 종료 | cycle 중단 | reliability>0.95 + interruptible=false 검색 조건, 중간 checkpoint MLflow에 기록 |

## 4. 비용 모델

| 시나리오 | GPU | 시간 | dph | 예상 cost |
|---|---|---|---|---|
| roberta-small + HPO 30 trial | RTX 3060 8GB | 1.5 h | $0.05 | $0.075 |
| roberta-base fp16 + HPO 30 | RTX 3060 12GB | 2 h | $0.08 | $0.16 |
| roberta-large + HPO 50 | RTX 3090 24GB | 3 h | $0.35 | $1.05 |
| 10 cycle 누적 (small) | - | 15 h | $0.05 | ~$0.75 |
| 한 milestone (Phase 2 완주, 5~10 cycle base) | - | ~20 h | $0.08 | ~$1.60 |

→ Phase 1의 board_config `max_usd_per_cycle=20` 그대로 두어도 Phase 2 base 시나리오는 여유. roberta-large 또는 long-tail HPO 시 50으로 상향 검토.

## 5. 외부 참고

- vast.ai Pricing & Search docs: https://vast.ai/docs/
- HuggingFace KLUE-RoBERTa: https://huggingface.co/klue
- Optuna HPO best practice: Akiba et al. 2019 (Optuna paper)
- AGENTS.md Hard Rule #2 (학생 PII), board_config `cost_circuit_breaker`

## 6. 다음 액션 (Phase 2 setup 시점)

- [ ] vast.ai 콘솔에서 신규 API 키 발급, 기존 키 revoke
- [ ] `.env`에 신규 키 저장, `vastai --api-key "$VAST_API_KEY" show instances --raw` 인증 확인 (`vastai show user`는 CLI 0.5.0/API schema 호환성 문제로 사용 금지)
- [ ] `dataset/sample_5k/` 추출 (Phase 2 design 문서 §B2 데이터 출처 결정 후)
- [ ] `pipelines.audit_pii dataset/sample_5k --fail-on-hit` PASS 확인
- [ ] `VAST_GPU_GUIDE.md` §11 빠른 참조 그대로 1회 dry-run
- [ ] Cycle M1 ready
