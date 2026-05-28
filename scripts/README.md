# Phase 3 운영 스크립트

Phase 3 운영 가이드(`docs/phase_3_operations_guide_v_1_0.md`) C1~C6 대응 스크립트.

| 스크립트 | 대응 | 호출 시점 |
|---|---|---|
| `backup_kanban_db.sh` | C4 — kanban DB 자동 백업 | cycle AUDIT 시작 / cron 6h |
| `verify_hermes_patch.sh` | C2 — hermes 패치 영구 검증 | cycle AUDIT 시작 / hermes 업데이트 직후 |
| `poll_vast_progress.sh` | C5 — vast.ai progress.json polling | M5/M6 학습 detach 후 polling task |
| `write_progress.py` | C5 — 학습 스크립트 progress.json 헬퍼 | 학습 스크립트 import |
| `cycle_preflight.sh` | C2+C4 통합 — cycle 진입 전 12체크 | 매 cycle AUDIT 첫 step |

설치 (cron 등록 권장):

```bash
# 6시간 주기 자동 백업
crontab -e
# 다음 줄 추가:
0 */6 * * * /home/dev/work/essay-auto-scoring-research/scripts/backup_kanban_db.sh >> /home/dev/.hermes/kanban/backups/cron.log 2>&1
```
