# Phase 3 운영 가이드 (중단없는 지속적 실행)

> **버전**: v1.0.3 (v1.0.2 + R3/R4 4차 재검수 fix)
> **의존성** (R3 4차 REG-3 fix): Python 3.x + PyYAML ≥ 6.0 (cycle_preflight.sh [11/12] 의존). vast.ai bootstrap 환경에서는 `pip install pyyaml` 사전 실행 의무.
> **작성 일자**: 2026-05-28 (v1.0 → v1.0.1 → v1.0.2)
> **목적**: Phase 2에서 관측된 6대 중단 원인(C1~C6) 사전 대응 절차 표준화
> **선행 문서**: `MILESTONE_v2.md` (Phase 2 종료 노트), `multi_task_채점모델_구현_스펙_v_1_1.md` (v1.1.2)
> **상태**: Phase 3 진입 운영 기준 (Cycle M2 시작 적용)
> **변경 이력**:
> - v1.0 (2026-05-28): 초안
> - v1.0.1 (2026-05-28): T1-01/T1-02/T2-01/T2-18/T3-17/T3-18/T3-19/T3-22/T3-25 + R3/R4 검수 fix
> - v1.0.2 (2026-05-28): R3-NF3/NF10 + R4-NF4/NF6 재검수 fix
>   - § 5.3 stale code block 교체 (v1 폴링 → v2 참조)
>   - § 7 체크리스트를 `cycle_preflight.sh` 단일 명령 + 12 항목 표로 통합 (R4-NF4)
>   - § 3.4 audit log source 환경별 분기 (systemd / nohup / docker, R4-NF6)
>   - § 4.4 hermes daemon 재시작 환경 자동 감지 스크립트 (R3-NF10)
>   - § 1.2 vastai execute smoke test 권고 (R3-NF3)
> - v1.0.3 (2026-05-28): R3/R4 4차 재검수 fix
>   - § 5.2 ProgressWriter stale 코드 블록 → v2 본문 참조 변환 (R3 4차 REG-5)
>   - § 7 [2/12] path `*.toml` → `*/profile.yaml + */config.yaml` (R3 4차 REG-2 + R4 4차 NEW-DOC-1)
>   - § 7 [8/12] "enforce" → "best-effort check" (R2-NEW-G2 표현 동기화)
>   - 의존성 명세: PyYAML ≥ 6.0 추가 (R3 4차 REG-3)

---

## 0. 6대 중단 원인 → 대응 매핑

| # | Phase 2 관측 사실 | Phase 3 대응 | 본 가이드 절 |
|---|---|---|---|
| **C1** | codex app-server 10분 timeout → worker hang. M5 학습 결과 회수 실패 | Long-running 작업을 worker에서 분리. vast.ai background job + status polling | § 1 |
| **C2** | hermes `codex_app_server.py:109` `network_access=false` hard-code → vast.ai 접근 차단 | 패치 영구 유지 + 업데이트 시 재패치 검증 hook | § 2 |
| **C3** | sandbox approval 거부로 worker 차단 (escalation 무한 루프) | `danger-full-access` + `approval_policy=never` 유지 (사용자 명시) + 신규 프로파일 일괄 적용 | § 3 |
| **C4** | kanban DB sqlite 손상 (수동 comment 작성 중) → 12 tasks 손실 | cycle 시작 시 자동 백업 + 정기 cron 백업 + 표준 recovery 절차 | § 4 |
| **C5** | vast.ai GPU util 0%로 학습 진행 상태 파악 불명 | 학습 스크립트 progress.json 주기 출력 + worker ssh polling + 주기 checkpoint | § 5 |
| **C6** | 사용자 개입 빈도 높음 (DECIDE 외 권한/DB/troubleshooting) | D1~D6 사전 확정 + 자동 PASS 임계 + 비상시만 인간 게이트 | § 6 |

---

## 1. C1 — Long-running 작업의 off-worker 분리

### 1.1 문제 (Phase 2 관측)

- codex app-server는 single worker request → response 라이프사이클 기준 약 10분 timeout
- M5 KLUE-RoBERTa 학습은 vast.ai에서 ~1.5h 소요
- worker가 학습 명령을 직접 실행 (foreground `python3 train.py`) → 10분 후 hang → 결과 회수 실패

### 1.1 적용 대상 데이터 (T3-22 + R4-F10 — PII evidence 보강)

vast.ai 외부 GPU 전송 데이터는 `dataset/sample_5k/` (5003편). PII 위험 평가:

| 차원 | 평가 | 근거 |
|---|---|---|
| 데이터 출처 | AI Hub 공공 데이터셋 (한국 K-12 에세이) | https://www.aihub.or.kr/ |
| 익명화 수준 | 사전 익명화 완료 — 이름/주민번호/전화/주소 0건 | AI Hub data card |
| `student.location` | 시도 코드만 (예: "031" 경기도) — quasi-identifier | granularity는 시도 단위, 학교 단위는 X |
| `paragraph_txt` 자전적 본문 | 자전적 표현 가능 ("도등학교 2학년 때..."). 본문 + location + grade 4단 결합 시 small-group 재식별 위험 잔존 | 학년군 (4) × 시도 (17) × 학기 = 약 1000개 segment |
| vast.ai 인스턴스 신뢰 | host operator가 disk access 가능 (untrusted) | vast.ai marketplace 모델 |

**완화 조치 (T3-22)**:
- vast.ai 전송 데이터에서 `student.location`, `student.date` 컬럼 명시적 drop. split key는 로컬에서만 유지 (Hard Rule #2 split_only_fields 정합)
- 학습 입력은 `(text, target_*, w_*)` 4-tuple만 — student/info segment 컬럼 제외
- Hard Rule #13 제거 결정 (2026-05-28)의 evidence로 본 § 1.1 참조

### 1.2 표준 패턴 (T1-02 + T2-01 fix — vastai execute + one-shot polling)

**R3-NF3 smoke test 의무 (Phase 3 M2 진입 직전)**:
첫 vast.ai 인스턴스 spawn 후 polling 호출 전, 다음 smoke test 1회 실행:
```bash
# 실제 instance ID로 단발 fetch 검증 (single-quote syntax 확인)
INSTANCE_ID=<실제 id>
VAST_API_KEY=<key> vastai execute "$INSTANCE_ID" "$(printf "'echo HELLO_VAST'")"
# 기대 출력: HELLO_VAST
```
출력 부재 또는 syntax error 시 `poll_vast_progress.sh`의 single-quote 본문 호환성 재검증 + 수정. Phase 3 M2 학습 task spawn 전 본 smoke test 통과 필수 (Hard Rule #16 enforce 보강).


| 단계 | 누가 | 무엇을 |
|---|---|---|
| 1. spawn | worker (gauss/ada-lovelace) | `vastai execute "$INSTANCE_ID" "cd /workspace && nohup python3 train.py ... > train.log 2>&1 &"` → PID + start_at metadata 기록 |
| 2. detach | worker | launcher task를 `done` 처리하고 remote job 상태는 metadata(`remote_job_state=running`)로 남김. 다음 polling task는 `scheduled`로 등록. `kanban_metadata: {worker_pid, vast_instance_id, expected_done_at, log_path, progress_path, expected_duration_min}` (Hard Rule #16 expected_duration_min > 10 명시 의무) |
| 3. poll (one-shot, T2-01 fix) | 별도 polling task (`T-CYCLE-MN-MODEL-POLL-K`, K=1,2,...) | `scripts/poll_vast_progress.sh "$INSTANCE_ID" /workspace/progress.json --once` 호출 → progress.json 1회 fetch + DONE/FAIL marker 체크 → 즉시 task complete + SYNTH가 다음 polling task `T-CYCLE-MN-MODEL-POLL-(K+1)` 자동 spawn (300초 후 시작 예약). 학습 종료까지 chain. |
| 4. finalize | DONE 감지 polling task | mlflow.db + workspace/cycle_MN/models/ scp로 회수 → 로컬 merge → 후속 EVAL/REVIEW sub-task spawn |

**T2-01 + R3-F14 + R4-F9 핵심**:
- polling worker 자체도 10분 timeout 적용되므로 `while true` 무한 polling 금지
- one-shot 모드 (`--once`)는 1회 fetch (수 초) 후 즉시 종료 → worker timeout 회피
- 다음 polling은 SYNTH-style spawn (kanban dependency + 시작 예약 시각)
- 학습 1.5h 기준: polling task ~18회 chain (300초 주기 × 18 = 5400초 ≈ 1.5h)
- vast.ai 인스턴스가 사라지면 polling task가 FAIL 반환 + 인간 게이트 spawn

### 1.3 적용 대상

- M5 KLUE-RoBERTa fine-tune (vast.ai)
- M5 HPO Optuna study (T3-19 fix — chunk 단위 spawn): **chunk 10 trial/task**, chunk별 별도 polling chain
- M6 multi-output ensemble (각 fold 학습)

### 1.4 적용 제외

- M1~M4 CPU baseline (로컬, <5분)
- evaluate / review / synth (CPU, <2분)

### 1.5 구현

- 학습 스크립트는 `scripts/write_progress.py` 헬퍼 호출 (§ 5 참조)
- polling task 템플릿: `scripts/poll_vast_progress.sh "$INSTANCE_ID" /workspace/progress.json --once`
- HPO chunk (T3-19): `pipelines/run_hpo.py --n-trials 10 --start-trial $((CHUNK_K * 10))` (chunk_k=0,1,2 → 누적 30 trial)
- 각 chunk별 progress.json 위치 분리: `/workspace/progress.M5.hpo.chunk_$K.json`

---

## 2. C2 — hermes 패치 영구 유지 + 재패치 검증

### 2.1 패치 위치

`/home/dev/.hermes/hermes-agent/agent/transports/codex_app_server.py:109`

```python
# 2026-05-28 user-approved (explicit "직접 수정해"): allow network
# for vast.ai GPU workflow. Original value was "false".
"sandbox_workspace_write.network_access=true",
```

### 2.2 위험

- hermes 업데이트 (pip install -U, git pull) 시 패치가 덮어쓰기됨
- 덮어쓰기 감지 없이 worker 동작 시 vast.ai 접근 차단 → C1 hang 재발

### 2.3 검증 hook

`scripts/verify_hermes_patch.sh` — cycle 시작 시 호출:

```bash
#!/bin/bash
# Phase 3 operations: hermes codex_app_server.py network_access=true 패치 검증
set -e
TARGET="/home/dev/.hermes/hermes-agent/agent/transports/codex_app_server.py"
EXPECTED='"sandbox_workspace_write.network_access=true"'

if ! grep -q "$EXPECTED" "$TARGET"; then
    echo "FAIL: hermes patch missing — $TARGET line 109 expected '$EXPECTED'"
    echo "원인: hermes 업데이트로 덮어쓰기 가능성"
    echo "조치: 사용자 게이트로 재패치 결정 필요 (MILESTONE_v3.md C2 참조)"
    exit 1
fi
echo "OK: hermes patch verified ($TARGET)"
```

### 2.4 호출 시점

- 모든 cycle AUDIT sub-task 시작 시 (Hard Rule #15와 같이 inject)
- hermes 업데이트 직후 (수동 trigger)

---

## 3. C3 — sandbox 정책 유지 + 신규 프로파일 일괄 적용

### 3.1 현재 정책 (Phase 2 종료 시점 유지)

`/home/dev/.codex/config.toml`:
```toml
sandbox_mode = "danger-full-access"
approval_policy = "never"

[sandbox_workspace_write]
network_access = true
```

### 3.2 적용 범위

- 모든 hermes profile: gauss / aristotle / spearman / turing / tukey / ada-lovelace
- Phase 3에서 신규 profile 추가 시 동일 정책 자동 적용 (별도 결정 필요 시 사용자 게이트)

### 3.3 위험 인지

본 정책 하에서 임의 도메인 접근/명령 자동 실행 가능. Phase 3 운영 기간 동안 본 정책에 의한 사고 발생 시 즉시 보고 + 사용자 게이트 진입 (사용자가 정책 재검토).

### 3.4 Sandbox audit log (T3-14 + R3-F15 + R4-NF6 fix — 환경별 log source 분기)

본 정책의 사후 traceability 확보를 위해 outbound 접근 audit log 수집. **R4-NF6 fix — hermes-agent log source가 환경 종속이므로 분기 처리**:

| 환경 | log source | audit 명령 |
|---|---|---|
| systemd (Ubuntu/Debian) | `journalctl -u hermes` | `journalctl -u hermes -S "1 week ago"` |
| nohup/직접 실행 (WSL2 등) | `~/.hermes/agent.log` | `tail -n 100000 ~/.hermes/agent.log` |
| docker | container log | `docker logs hermes-agent --since 168h` |

표준 audit script (환경 자동 감지):
```bash
mkdir -p workspace/audit
if systemctl is-active --quiet hermes 2>/dev/null; then
    LOG_SRC="journalctl -u hermes -S '1 week ago'"
elif [ -f ~/.hermes/agent.log ]; then
    LOG_SRC="tail -n 100000 ~/.hermes/agent.log"
else
    LOG_SRC="docker logs hermes-agent --since 168h 2>&1"
fi
eval "$LOG_SRC" | grep -oE 'https?://[A-Za-z0-9._-]+' \
    | awk -F/ '{print $3}' | sort -u \
    > workspace/audit/outbound_domains_$(date -u +%Y%m%d).txt
```

| 항목 | 절차 |
|---|---|
| 주 1회 review task | 매주 월요일 cron 또는 SYNTH가 다음 cycle 등록 시 `T-AUDIT-OUTBOUND-WEEK-N` task spawn — tukey worker가 outbound 도메인 anomaly 검토 |
| anomaly 기준 | 화이트리스트 외 도메인 (`api.vast.ai`, `cloud.vast.ai`, `pypi.org`, `huggingface.co`, `github.com`, `googleapis.com` 외) 발견 시 사용자 게이트 + `notify_alert.sh` 발사 |
| 저장 위치 | `workspace/audit/outbound_domains_<YYYYMMDD>.txt` |
| log source 미가용 fallback | 위 3종 모두 실패 시 audit script가 명시적 FAIL + 사용자 보고 (silent skip 금지) |

allowlist 모드 (egress firewall)는 Phase 4 deferral.

---

## 4. C4 — kanban DB 자동 백업 + 표준 recovery

### 4.0 실제 DB 경로 (T1-01 + R3-F1 fix)

| 경로 | 용도 |
|---|---|
| `~/.hermes/kanban/current` | active board 이름 1줄 텍스트 |
| `~/.hermes/kanban/boards/<board-name>/kanban.db` | **실제 board DB (백업 대상)** |
| `~/.hermes/kanban/boards/<board-name>/kanban.db-wal` | WAL (백업 전 wal_checkpoint 처리) |
| `~/.hermes/kanban/boards/<board-name>/kanban.db-shm` | SHM (백업 전 wal_checkpoint 처리) |
| `~/.hermes/kanban/db.sqlite` | **placeholder (0 byte), 사용 안 함** |

backup_kanban_db.sh는 `current` 파일에서 active board 이름을 동적으로 도출. 별도 board 백업이 필요하면 두 번째 인자로 board 이름 전달.

### 4.1 백업 위치 + 보관 정책 (T3-18 + R3-F19 fix — 정책 일치)

| 종류 | 빈도 | 보관 위치 | 보관 정책 |
|---|---|---|---|
| Cycle 시작 백업 | cycle별 1회 (preflight #4) | `~/.hermes/kanban/backups/cycle_MN_pre.db` | **수동 cleanup** (사용자 결정으로 archive) |
| 정기 백업 | 6시간 (cron) | `~/.hermes/kanban/backups/auto_<UTC-timestamp>.db` | 최근 28개 보관 (1주일치) — backup_kanban_db.sh가 자동 회전 |
| 수동 백업 | 사용자 trigger | `~/.hermes/kanban/backups/manual_<label>.db` | **수동 cleanup** |

T3-18 update: `cycle_*` / `manual_*`는 무기한이 아닌 **수동 cleanup**. v1.0의 "cycle 종료 후 30일 보관" 자동 정책은 폐기 (스크립트에 미구현). 사용자가 분기별로 archive 결정.

### 4.2 백업 방법 (실제 구현은 `scripts/backup_kanban_db.sh` 본문 참조)

핵심:
- LABEL 화이트리스트 (`^[A-Za-z0-9_.-]+$`) — injection 차단
- realpath prefix 검증 — DEST_DIR escape 차단
- 백업 파일 0600 + 디렉토리 0700 권한
- `flock` 단일 instance 보장 — cron + cycle 동시 실행 race 차단
- `PRAGMA wal_checkpoint(TRUNCATE)` 선행 — WAL 동기화 후 백업
- integrity_check `^ok$` strict 매치

### 4.3 Cron 등록 (T3-10 + R2-F12 — enforce)

```cron
0 */6 * * * /home/dev/work/essay-auto-scoring-research/scripts/backup_kanban_db.sh >> /home/dev/.hermes/kanban/backups/cron.log 2>&1
```

검증: `cycle_preflight.sh` [6/12] 단계에서 `crontab -l | grep backup_kanban_db.sh` 확인. 미등록 시 WARN + 등록 명령 안내.

### 4.4 Recovery 절차 (표준, T3-25 + R4-F14 fix — daemon stop + WAL/SHM)

1. **hermes daemon stop (T3-25 신규)**:
   ```bash
   # hermes daemon 또는 worker가 DB hold 상태이면 cp 시 cache/WAL 정합성 깨짐
   pkill -f 'hermes-agent' || true
   sleep 2
   ```
2. **현 DB 손상 진단**:
   ```bash
   BOARD=$(cat ~/.hermes/kanban/current)
   KANBAN_DB="$HOME/.hermes/kanban/boards/$BOARD/kanban.db"
   sqlite3 "$KANBAN_DB" "PRAGMA integrity_check;"
   ```
3. **손상 확인 시 최신 백업 식별**:
   ```bash
   ls -lt ~/.hermes/kanban/backups/*.db | head -5
   ```
4. **WAL/SHM 정리 + 백업 복원 (T3-25 fix)**:
   ```bash
   # 손상된 DB + 동반 WAL/SHM 파일 격리
   mv "$KANBAN_DB" "${KANBAN_DB}.corrupt.$(date -u +%Y%m%dT%H%M%SZ)"
   rm -f "${KANBAN_DB}-wal" "${KANBAN_DB}-shm"
   # 백업 복원
   cp ~/.hermes/kanban/backups/<선택>.db "$KANBAN_DB"
   chmod 600 "$KANBAN_DB"
   ```
5. **hermes daemon 재시작 (R3-NF10 fix — 환경 자동 감지 스크립트)**:
   ```bash
   # 환경별 자동 감지 재시작
   if systemctl list-unit-files 2>/dev/null | grep -q '^hermes\.service'; then
       sudo systemctl start hermes
   elif command -v hermes-agent >/dev/null 2>&1; then
       nohup hermes-agent serve > ~/.hermes/agent.log 2>&1 &
       echo "hermes-agent PID: $!"
   else
       echo "FAIL: hermes-agent not found. 수동 설치 필요" >&2
       exit 1
   fi
   sleep 2
   # 동작 확인
   pgrep -f hermes-agent || { echo "FAIL: hermes-agent failed to start" >&2; exit 1; }
   ```
6. **백업 이후 변경 사항 수동 재현** (가능한 경우 git log + workspace 산출 참조)
7. **사용자 보고** — 손실된 task/comment 목록 + 백업 시점 + 외부 알림 채널 push (Phase 3 § 6.3)

### 4.5 손상 패턴 사전 회피 (T3-17 + R3-F18 fix)

- 직접 sqlite3 write 차단: kanban 조작은 `hermes kanban` CLI만 사용. 직접 sqlite3 write 시 git pre-commit hook으로 차단 권장
- WAL 모드 명시: `PRAGMA journal_mode=WAL` (이미 활성화 — 별도 enable 필요 없음, recovery 시에만 wal/shm 정리 의무)
- 디스크 공간 95% 초과 시 즉시 cleanup (Hard Rule #11 cost circuit breaker 연계)
- comment 수동 작성 중 worker 동시 write 충돌: `flock` 기반 wrapper script 또는 hermes CLI의 lock 메커니즘 사용 의무

### 4.6 Backup deadlock 회피 (T2-18 + R4-F5 fix)

preflight [4/12] kanban DB backup이 디스크 풀 등으로 실패 → cycle 진입 거부 → cleanup task spawn 불가의 데드락 회피:

| 시나리오 | 조치 |
|---|---|
| 디스크 95% 초과 + backup 실패 | cycle 외부에서 `hermes kanban gc` 직접 실행 (Hard Rule #11 연계). 그 후 preflight 재시도 |
| `cycle_*` 백업 100개+ 누적으로 디스크 잠식 | 분기별 사용자 archive (수동 cleanup 정책에 따름) |
| `auto_*` 28개 회전 + `cycle_*` 무한 보관 모두 정상이나 디스크 풀 | `mlflow.db`, `workspace/cycle_*`, vast download 정리 우선 (kanban backup이 아닌 학습 산출 cleanup) |

---

## 5. C5 — Progress observability (학습 진행 가시성)

### 5.1 progress.json 구조

각 학습 스크립트는 주기 (default 60초) progress.json 갱신:

```json
{
  "task_id": "T-CYCLE-M2-MODEL",
  "model_id": "M5",
  "started_at": "2026-05-29T10:00:00Z",
  "current_step": "fold_1_epoch_2",
  "total_steps": 15,
  "current_step_idx": 4,
  "metrics_so_far": {
    "fold_0_qwk": 0.32,
    "fold_1_qwk_partial": null
  },
  "gpu_util_pct": 87,
  "gpu_mem_used_mb": 6432,
  "elapsed_sec": 1842,
  "eta_sec": 3654,
  "last_checkpoint_path": "/workspace/cycle_M2/models/M5/fold_1_epoch_1.pt",
  "last_updated": "2026-05-29T10:30:42Z"
}
```

### 5.2 학습 스크립트 헬퍼 (R3 4차 REG-5 fix — stale v1 코드 블록 교체)

`scripts/write_progress.py` v2 — 학습 스크립트 import. 실제 본문은 파일 참조 (§ 5.3과 동일 처리).

핵심 동작:
- `ProgressWriter(path, task_id, model_id, total_steps, min_flush_interval_sec=5.0)` 생성자
- **REQUIRED_FIELDS 13종**: `task_id, model_id, started_at, current_step, total_steps, current_step_idx, metrics_so_far, gpu_util_pct, gpu_mem_used_mb, elapsed_sec, eta_sec, last_checkpoint_path, last_updated`
- **atomic write**: `path.parent / "{stem}.{pid}.tmp"` → `os.replace(tmp, path)` (multi-worker race 회피)
- **rate-limit**: `min_flush_interval_sec=5.0` (force=True인 epoch 종료 시 즉시)
- **multi-GPU GPU stats**: `nvidia-smi --query-gpu=index,utilization.gpu,memory.used` + `CUDA_VISIBLE_DEVICES` 필터 + max util (R3-NF1)
- **DONE/FAIL marker**: `path.parent / "DONE"` 또는 `FAIL` 파일 생성
- **NOP fallback**: `_maybe_progress(...)` — import 실패 시 None 반환 (R3-NF8)

사용 예 (학습 스크립트):
```python
from scripts.write_progress import ProgressWriter

progress = ProgressWriter("/workspace/progress.json", task_id="T-CYCLE-M2-MODEL", model_id="M5", total_steps=15)
for fold_idx in range(5):
    for epoch_idx in range(3):
        progress.update(current_step=f"fold_{fold_idx}_epoch_{epoch_idx}",
                        current_step_idx=fold_idx*3+epoch_idx,
                        last_checkpoint_path=str(ckpt_path))
        # ... training ...
        progress.record_metric(f"fold_{fold_idx}_qwk", qwk)
progress.mark_done()
```

### 5.3 Polling 스크립트

`scripts/poll_vast_progress.sh` (v2 — R4-NF4 fix: stale v1 코드 블록 교체. 실제 본문은 `scripts/poll_vast_progress.sh` 파일 참조).

핵심 동작:
- **`--once` 기본 모드** (Hard Rule #16 worker timeout 회피): 1회 fetch + DONE/FAIL marker 체크 후 즉시 종료
- `vastai execute` (vastai ssh 미존재) + single-quote 명령 본문 (입력 화이트리스트 통과 후 안전 보간)
- VAST_API_KEY env 전달 (`--api-key` argv 노출 차단)
- FETCH_FAILS state persist (`~/.hermes/kanban/state/vast_<id>.fails`) — one-shot reset 차단 (R4-NF8)
- stall 감지 시 `scripts/notify_alert.sh progress_stall_detected` 발사
- `--loop INTERVAL`은 subprocess 환경 전용

사용:
```bash
# 단발 폴링 (worker가 호출하는 표준 패턴)
scripts/poll_vast_progress.sh 12345 /workspace/progress.json --once

# 무한 폴링 (cron/nohup 환경에서만)
scripts/poll_vast_progress.sh 12345 /workspace/progress.json --loop 300
```

### 5.4 Checkpoint 정책

| 빈도 | 파일 |
|---|---|
| 매 epoch 종료 | `models/M5/fold_{i}_epoch_{e}.pt` |
| 매 5 trial | `models/M5/hpo_trial_{n}_best.pt` |
| 종료 | `models/M5/final.pt` + `DONE` marker file |

복구: 학습 재시작 시 `--resume-from <checkpoint>` 옵션 (train_transformer.py 확장 — Phase 3 M2 도입).

---

## 6. C6 — 인간 개입 최소화 (자동 PASS + 비상 게이트)

### 6.1 Phase 2 인간 개입 카테고리 분석

| 카테고리 | Phase 2 발생 | Phase 3 처리 |
|---|---|---|
| DECIDE 1클릭 | 의도된 게이트 | 유지 |
| 보안 정책 승인 | sandbox/network 차단으로 worker hang | C3 정책 유지로 0회 (영구 승인 상태) |
| DB 손상 복구 | 1회 | C4 백업으로 0회 (자동 복구) + 손상 발생 시 보고만 |
| vast.ai 명령 직접 실행 | "직접 진행" 피드백 | C1 polling 패턴으로 0회 (worker가 status만 보고) |
| 진행 상태 확인 | 빈번 (5+ 회) | C5 progress.json 보고로 자동화 |
| 외부 리뷰 반영 (스펙 v1.1) | 1회 (본 산출) | Phase 3 cycle별 v1.x update는 자율 진행 |

### 6.2 자동 PASS 임계

DECIDE-N 게이트에서 다음 조건 모두 충족 시 자동 [Continue] (사용자 게이트 timeout 6h grace 후):

| 조건 | 임계 |
|---|---|
| judgement | PASS_CANDIDATE |
| 모든 차원 fairness gate | per-rubric `worst_band_qwk ≥ macro_qwk × 0.7` |
| Cost circuit breaker | 미발동 |
| 단조 진화 위반 | 0건 |

→ 본 임계는 ACCEPTANCE_CRITERIA.yaml + Hard Rule로 명문화 (A4+A5 task).

### 6.3 비상 인간 게이트 (자동 PASS 우회 + 즉시 사용자 알림)

| 사유 | 행동 |
|---|---|
| FAIL judgement | DECIDE 자동 진행 정지, 사용자 명시 결정 대기 |
| Cost circuit breaker 발동 | cycle 자동 pause, 사용자 알림 |
| 3 cycle 연속 acceptance fail | Layer 3 escalation, 사용자 게이트 |
| hermes 패치 검증 실패 (C2) | cycle 진입 거부, 사용자 게이트 |
| kanban DB 손상 자동 복구 실패 (C4) | cycle 진입 거부, 사용자 게이트 |
| vast.ai 인스턴스 학습 실패 / OOM | M5 폐기 + M4 결과로 acceptance 재판정 → judgement 갱신 |

### 6.4 사용자 결정 사전 확정 (D1~D6)

`docs/multi_task_채점모델_구현_스펙_v_1_1.md` § 0에 D1~D6 확정. Phase 3 운영 중 D7~D10은 운영 게이트로 발생 시 사용자 결정.

---

## 7. Phase 3 운영 체크리스트 (cycle 진입 직전, R4-NF4 fix — 단일 명령으로 통합)

매 cycle MN의 AUDIT sub-task 시작 시 다음 단일 명령 실행 (Hard Rule #18 enforce):

```bash
scripts/cycle_preflight.sh MN [--require-vast] [--auto-destroy-stale --vast-label essay-auto-scoring]
```

`cycle_preflight.sh`가 다음 12 항목을 자동 체크 (R4-NF4 + R2-NF9 fix — 실제 스크립트와 일치):

| # | 항목 | 동적 경로 / 검증 |
|---|---|---|
| 1/12 | hermes 패치 검증 | `verify_hermes_patch.sh` |
| 2/12 | codex sandbox + hermes profile 정책 | `~/.codex/config.toml` + `~/.hermes/profiles/*/profile.yaml` + `*/config.yaml` (R3-REG-2 fix — 실제 yaml 구조) |
| 3/12 | `.env` 권한 (secrets 포함 시 FAIL) | 0600 또는 0400 |
| 4/12 | kanban DB pre-cycle 백업 + age 검증 | `backup_kanban_db.sh cycle_MN_pre` + 마지막 auto_* < 12h |
| 5/12 | kanban DB 무결성 | `~/.hermes/kanban/boards/$(cat ~/.hermes/kanban/current)/kanban.db` (R4-NF4 동적 경로) |
| 6/12 | cron 등록 | `crontab -l \| grep backup_kanban_db.sh` |
| 7/12 | vast.ai 잔여 인스턴스 (label filter) | `vastai show instances --raw \| jq` |
| 8/12 | Hard Rule #16 best-effort check (R2-NEW-G2 fix — enforce 표현 완화) | hermes CLI grep + SYNTH worker prompt 의존 |
| 9/12 | 디스크 사용량 | 85% warn / 95% fail |
| 10/12 | 알림 채널 가용성 | 기본: durable file-log 1종+. 사용자 push 강제 시 `push_required_count: 1` + notify-send/webhook/mail 중 enabled channel 1종+ |
| 11/12 | evaluator wire-up 상태 | `mid_multitask._implementation_status == wired_v1` (M3+ 진입 시 hard-block) |
| 12/12 | MILESTONE_v3 + spec presence + freshness | git log 14일 이내 |

추가 cycle 시작 시 의무 (preflight 외):
- MILESTONE_v3.md goal 재주입 (Hard Rule #10) — AUDIT sub-task body
- multi_task 스펙 최신 버전 확인 (외부 리뷰 미반영 항목 0건) — REVIEW sub-task

preflight FAIL 1건 이상 시 cycle 진입 거부 + `notify_alert.sh preflight_self_test critical` 자동 발사.

---

## 8. Phase 3 운영 KPI

| 지표 | 목표 |
|---|---|
| 사용자 개입 빈도 (DECIDE 외) | cycle당 < 1회 (Phase 2 평균 5+ 회 대비) |
| Worker hang 발생 | 0회 (C1 off-worker 패턴) |
| kanban DB 손상 | 0회 (C4 백업) — 손상 시 자동 복구 |
| Vast.ai 학습 결과 회수 성공률 | 100% (C5 progress + checkpoint) |
| Cycle 평균 wall-clock | < 4h (Phase 2 평균 ~6h 대비, hang 제거 효과) |
| 외부 리뷰 → 스펙 반영 latency | < 24h (자율 v1.x update) |

---

## 9. References

- `MILESTONE_v2.md` — Phase 2 종료 노트 (C1~C6 1차 관측 evidence)
- `multi_task_채점모델_구현_스펙_v_1_1.md` — Phase 3 모델 스펙
- `AGENTS.md` — Hard Rule #15~#18 (본 가이드 § 1, § 4, § 5, § 6 명문화)
- `ACCEPTANCE_CRITERIA.yaml` — per-rubric + 자동 PASS 임계
- `scripts/backup_kanban_db.sh` / `verify_hermes_patch.sh` / `poll_vast_progress.sh` / `write_progress.py` — A6 산출
- `VAST_GPU_GUIDE.md` — vast.ai 절차 (C1 off-worker 통합 필요 시 보강)
- `/home/dev/.hermes/hermes-agent/agent/transports/codex_app_server.py:109` — C2 패치 위치
- `/home/dev/.codex/config.toml` — C3 sandbox 정책
