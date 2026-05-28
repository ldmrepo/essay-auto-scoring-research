#!/bin/bash
# Phase 3 operations C4: kanban DB sqlite hot backup (Online Backup API)
# 사용: backup_kanban_db.sh [label] [board_name]
#   - label 미지정: auto_<UTC-timestamp> (cron용, 28개 회전)
#   - label 지정: <label>.db (수동/cycle용 보존, label 화이트리스트 강제)
#   - board_name 미지정: ~/.hermes/kanban/current 파일에서 자동 도출
# Hard Rule #18 (AGENTS.md)
#
# 변경 이력:
# - v2 (2026-05-28): R3-F1 + R4-F2 + R4-F3 + R4-F6 fix
#   - DB 경로 동적 도출 (boards/<board>/kanban.db)
#   - LABEL injection 차단 (화이트리스트)
#   - 백업 파일 0600 권한 + 디렉토리 0700
#   - flock 단일 instance 보장 (race 차단)
#   - WAL 파일 동반 처리 (PRAGMA wal_checkpoint)

set -eu

# 인자 파싱
LABEL_RAW="${1:-auto_$(date -u +%Y%m%dT%H%M%SZ)}"
BOARD_OVERRIDE="${2:-}"

# T1-07 + R4-F2: LABEL 화이트리스트 강제 (injection 차단)
if ! [[ "$LABEL_RAW" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "FAIL: label contains invalid chars (whitelist: A-Z a-z 0-9 _ . -): $LABEL_RAW" >&2
    exit 3
fi
LABEL="$LABEL_RAW"

# T1-01 + R3-F1: 실제 kanban DB 경로 동적 도출
KANBAN_ROOT="$HOME/.hermes/kanban"
if [ -n "$BOARD_OVERRIDE" ]; then
    # board_name 화이트리스트 (path traversal 차단)
    if ! [[ "$BOARD_OVERRIDE" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "FAIL: board_name contains invalid chars: $BOARD_OVERRIDE" >&2
        exit 3
    fi
    BOARD="$BOARD_OVERRIDE"
else
    if [ ! -f "$KANBAN_ROOT/current" ]; then
        echo "FAIL: $KANBAN_ROOT/current not found (active board pointer)" >&2
        exit 1
    fi
    BOARD=$(tr -d '\n' < "$KANBAN_ROOT/current")
    if [ -z "$BOARD" ]; then
        echo "FAIL: $KANBAN_ROOT/current is empty" >&2
        exit 1
    fi
fi

BOARD_DIR="$KANBAN_ROOT/boards/$BOARD"
SRC="$BOARD_DIR/kanban.db"

ensure_writable_dir() {
    local primary="$1"
    local fallback="$2"
    local purpose="$3"
    local probe

    mkdir -p "$primary" 2>/dev/null || true
    chmod 700 "$primary" 2>/dev/null || true
    probe="$primary/.write_probe_$$"
    if (: > "$probe") 2>/dev/null; then
        rm -f "$probe" 2>/dev/null || true
        echo "$primary"
        return 0
    fi

    mkdir -p "$fallback"
    chmod 700 "$fallback" 2>/dev/null || true
    probe="$fallback/.write_probe_$$"
    if (: > "$probe") 2>/dev/null; then
        rm -f "$probe" 2>/dev/null || true
        echo "WARN: $purpose primary dir not writable; using fallback: $fallback" >&2
        echo "$fallback"
        return 0
    fi

    echo "FAIL: neither primary nor fallback $purpose dir is writable: $primary / $fallback" >&2
    exit 1
}

if [ ! -d "$BOARD_DIR" ]; then
    echo "FAIL: board directory not found at $BOARD_DIR" >&2
    exit 1
fi

# flock 단일 instance 보장 (T2-14 + R4-NF5: 사용자별 격리)
# R4-NF5 fix: /tmp 공유 lock은 multi-user 환경에서 DoS 가능 → user home으로 이동
# Sandbox recovery: if ~/.hermes/kanban is mounted read-only, keep the lock under
# the active board directory so required preflight backups still run.
LOCK_DIR=$(ensure_writable_dir "$KANBAN_ROOT" "$BOARD_DIR/.backup_state" "backup lock")
LOCK_FILE="$LOCK_DIR/.backup.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    # R3-NF5 fix: silent skip 누적 검출 — skip 카운터 파일
    SKIP_COUNTER="$LOCK_DIR/.backup.skip_counter"
    SKIPS=$(cat "$SKIP_COUNTER" 2>/dev/null || echo 0)
    SKIPS=$((SKIPS + 1))
    echo "$SKIPS" > "$SKIP_COUNTER"
    if [ "$SKIPS" -ge 3 ]; then
        echo "FAIL: backup_kanban_db.sh skipped $SKIPS times in a row (lock contention persistent)" >&2
        # notify_alert이 있으면 발사 (silent on missing)
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        [ -x "$SCRIPT_DIR/notify_alert.sh" ] && \
            "$SCRIPT_DIR/notify_alert.sh" kanban_db_recovery_required \
                "backup_kanban_db.sh skipped $SKIPS times (lock contention)" warn >/dev/null 2>&1 || true
        exit 4
    fi
    echo "INFO: another backup_kanban_db.sh instance is running, skipping (skips=$SKIPS)" >&2
    if [ "${HERMES_BACKUP_FAIL_ON_LOCK:-0}" = "1" ]; then
        echo "FAIL: backup lock contention during required pre-cycle backup" >&2
        exit 4
    fi
    exit 0
fi
# 정상 backup이 시작되면 skip 카운터 reset
rm -f "$LOCK_DIR/.backup.skip_counter" 2>/dev/null || true

DEST_DIR=$(ensure_writable_dir "$KANBAN_ROOT/backups" "$BOARD_DIR/backups" "backup destination")
DEST="$DEST_DIR/${LABEL}.db"

# T1-07 + R4-F2: realpath prefix 확인 (DEST가 DEST_DIR 안에 있는지)
DEST_REAL=$(readlink -f "$DEST" 2>/dev/null || echo "$DEST")
DEST_DIR_REAL=$(readlink -f "$DEST_DIR" 2>/dev/null || echo "$DEST_DIR")
case "$DEST_REAL" in
    "$DEST_DIR_REAL"/*) : ;;
    *)
        echo "FAIL: DEST '$DEST_REAL' escapes DEST_DIR '$DEST_DIR_REAL'" >&2
        exit 3
        ;;
esac

if [ ! -f "$SRC" ]; then
    echo "FAIL: kanban DB not found at $SRC" >&2
    echo "  현재 active board: $BOARD" >&2
    echo "  boards/ 디렉토리 확인 필요" >&2
    exit 1
fi

# T1-08 + R4-F3 + NEW-H3: 백업 디렉토리 권한 강제 (mkdir -m은 기존 디렉토리 권한 미변경)
mkdir -p "$DEST_DIR"
chmod 700 "$DEST_DIR" 2>/dev/null || true

# T1-01 추가: WAL 모드 checkpoint (백업 직전 wal → main 동기화)
sqlite3 "$SRC" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null 2>&1 || true

# Online Backup API (lock-safe, hermes worker 동작 중에도 안전)
# DEST는 화이트리스트 검증된 LABEL + realpath 확인 완료
sqlite3 "$SRC" ".backup '$DEST'"

# T1-08 + R4-F3: 백업 파일 권한 0600
chmod 600 "$DEST"

# 백업 무결성 검증
INTEGRITY=$(sqlite3 "$DEST" "PRAGMA integrity_check;" 2>&1)
# T3-15 + R3-F16: 전체 출력에서 첫 줄이 정확히 "ok"인지 확인
FIRST_LINE=$(echo "$INTEGRITY" | head -1)
if [ "$FIRST_LINE" != "ok" ]; then
    echo "FAIL: backup integrity check failed: $INTEGRITY" >&2
    rm -f "$DEST"
    exit 2
fi

SIZE=$(wc -c < "$DEST")
echo "OK: backup $DEST ($SIZE bytes, integrity=ok, perm=600, board=$BOARD)"

# 보관 정책: auto_* 만 최근 28개 유지 (= 6h * 28 = 7일)
# cycle_* / manual_* / 기타 label은 무기한 보관
# T2-14 + R3-F5: strict 매치로 LABEL injection 회전 잠식 차단
KEEP=28
find "$DEST_DIR" -maxdepth 1 -type f -name 'auto_*.db' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn \
    | tail -n +$((KEEP + 1)) \
    | cut -d' ' -f2- \
    | while IFS= read -r old; do
        # strict 매치: auto_<YYYYmmddTHHMMSSZ>.db
        base=$(basename "$old")
        if [[ "$base" =~ ^auto_[0-9]{8}T[0-9]{6}Z\.db$ ]]; then
            rm -v "$old"
        fi
    done

exit 0
