#!/bin/bash
# Phase 3 operations C5: vast.ai progress.json 폴링 + 종료 감지 (one-shot 기본)
# Hard Rule #16 (off-worker) + #17 (progress observability)
# 사용: poll_vast_progress.sh <vast_instance_id> [remote_progress_path] [--once|--loop INTERVAL] [--stall-alert SEC]
#   - vast_instance_id: vastai instance ID (정수, required)
#   - remote_progress_path: default /workspace/progress.json
#   - --once: 1회 fetch + 종료 감지 후 즉시 종료 (default, T2-01 one-shot 패턴)
#   - --loop INTERVAL: 무한 polling (subprocess 환경 전용, INTERVAL초 주기)
#   - --stall-alert SEC: stall 알람 임계 (default 600s)
#
# 변경 이력:
# - v2 (2026-05-28): T1-02 + T1-06 + T2-01 + T2-02 + T2-03 + R3-F2/F6/F7/F14 + R4-F1/F9/F11 fix
#   - vastai ssh (미존재) → vastai execute로 변경
#   - 입력 화이트리스트 (INSTANCE_ID 정수, REMOTE_PATH 안전 문자)
#   - one-shot 기본 모드 (worker 10분 timeout 회피)
#   - jq 기반 last_updated 파싱
#   - VAST_API_KEY env 전달 (argv 노출 차단)

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

load_env_key() {
    local key="$1"
    local current
    eval "current=\${$key:-}"
    if [ -n "$current" ] || [ ! -f "$REPO_ROOT/.env" ]; then
        return 0
    fi
    require_env_file_secure
    local value
    value=$(awk -F= -v k="$key" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "$REPO_ROOT/.env" | tr -d '\r')
    if [ -n "$value" ]; then
        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
        export "$key=$value"
    fi
}

require_env_file_secure() {
    local env_file="$REPO_ROOT/.env"
    [ -f "$env_file" ] || return 0
    if grep -qE '^(VAST_API_KEY|PHASE3_WEBHOOK_URL|PHASE3_ALERT_EMAIL|.*_TOKEN|.*_SECRET|.*_KEY)=' "$env_file" 2>/dev/null; then
        local perm
        perm=$(stat -c%a "$env_file" 2>/dev/null || stat -f%Lp "$env_file" 2>/dev/null)
        if [ "$perm" != "600" ] && [ "$perm" != "400" ]; then
            echo "FAIL: .env contains secrets but perm=$perm. Run: chmod 600 .env" >&2
            exit 3
        fi
    fi
}

require_env_file_secure

# T1-06 + R4-F1: INSTANCE_ID 화이트리스트 (정수)
INSTANCE_ID="${1:?Usage: poll_vast_progress.sh <instance_id> [remote_path] [--once|--loop INTERVAL] [--stall-alert SEC]}"
if ! [[ "$INSTANCE_ID" =~ ^[0-9]+$ ]]; then
    echo "FAIL: instance_id must be integer: $INSTANCE_ID" >&2
    exit 3
fi
shift

# REMOTE_PATH 기본값 + 화이트리스트 (절대 경로 + 안전 문자)
REMOTE_PATH="/workspace/progress.json"
MODE="--once"
INTERVAL=300
STALL_ALERT=600
MAX_FETCH_FAILS=5

while [ $# -gt 0 ]; do
    case "$1" in
        --once)
            MODE="--once"; shift
            ;;
        --loop)
            MODE="--loop"; INTERVAL="${2:-300}"; shift 2
            ;;
        --stall-alert)
            STALL_ALERT="${2:-600}"; shift 2
            ;;
        --max-fetch-fails)
            MAX_FETCH_FAILS="${2:-5}"; shift 2
            ;;
        --*)
            echo "FAIL: unknown option: $1" >&2
            exit 3
            ;;
        *)
            REMOTE_PATH="$1"; shift
            ;;
    esac
done

# T1-06 + R4-F1: REMOTE_PATH 화이트리스트
if ! [[ "$REMOTE_PATH" =~ ^/[A-Za-z0-9_./-]+$ ]]; then
    echo "FAIL: remote_path must be absolute and safe chars only: $REMOTE_PATH" >&2
    exit 3
fi
# INTERVAL/STALL_ALERT 정수 검증
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || ! [[ "$STALL_ALERT" =~ ^[0-9]+$ ]]; then
    echo "FAIL: INTERVAL/STALL_ALERT must be integer" >&2
    exit 3
fi

DONE_MARKER="${REMOTE_PATH%/*}/DONE"
FAIL_MARKER="${REMOTE_PATH%/*}/FAIL"

# T3-23 + R4-F11: VAST_API_KEY env 전달 (vastai CLI 자동 인식, argv 노출 차단)
load_env_key VAST_API_KEY
: "${VAST_API_KEY:?VAST_API_KEY env required (or set VAST_API_KEY in .env with chmod 600)}"
export VAST_API_KEY

# R4-NF8 fix: one-shot 모드에서 FETCH_FAILS persist (instance dead 영구 미감지 차단)
STATE_DIR="$HOME/.hermes/kanban/state"
mkdir -p -m 700 "$STATE_DIR"
STATE_FILE="$STATE_DIR/vast_${INSTANCE_ID}.fails"

echo "=== Polling vast.ai instance $INSTANCE_ID (mode=$MODE) ==="
echo "  remote progress: $REMOTE_PATH"
echo "  stall alert: ${STALL_ALERT}s, max fetch fails: $MAX_FETCH_FAILS"

LAST_UPDATED=""
STALL_START=""
# R4-NF8: state file에서 누적 fail 카운터 로드
FETCH_FAILS=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
echo "  persisted fetch_fails so far: $FETCH_FAILS"

# T1-02 + R3-F2: vastai execute로 변경 (vastai ssh 미존재)
# T1-06 + R4-F1: instance_id는 화이트리스트 통과한 정수, 명령 본문은 single-quote 강제
# R3-NF3 fix: vastai execute는 공식 syntax상 bash command를 single-quote로 감싸야 안전.
#   화이트리스트 통과한 REMOTE_PATH는 안전 문자만 포함하므로 single-quote 안에 그대로 보간 가능.
poll_once() {
    local now cur_updated stall_now stall_dur cur_epoch now_epoch stale_age
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "[$now] poll vastai instance $INSTANCE_ID"

    # Terminal markers have priority over stale progress timestamps. A completed
    # job may have an old last_updated by the time the next one-shot poll runs.
    if vastai execute "$INSTANCE_ID" "$(printf "'test -f %s && echo DONE_FOUND'" "$DONE_MARKER")" 2>/dev/null | grep -q DONE_FOUND; then
        echo "DONE: training complete (DONE marker detected)"
        echo "  다음 단계: workspace 회수 + mlflow.db merge"
        rm -f "$STATE_FILE" 2>/dev/null || true
        return 100
    fi

    if vastai execute "$INSTANCE_ID" "$(printf "'test -f %s && cat %s'" "$FAIL_MARKER" "$FAIL_MARKER")" 2>/dev/null | grep -q .; then
        echo "FAIL: training failed (FAIL marker detected)" >&2
        vastai execute "$INSTANCE_ID" "$(printf "'cat %s'" "$FAIL_MARKER")" 2>/dev/null || true
        rm -f "$STATE_FILE" 2>/dev/null || true
        return 101
    fi

    # progress.json fetch (vastai execute, single-quote 권장 syntax)
    # bash inside single-quote → variable expansion 미발생. REMOTE_PATH는 local에서만 보간.
    if PROGRESS=$(vastai execute "$INSTANCE_ID" "$(printf "'cat %s'" "$REMOTE_PATH")" 2>/dev/null); then
        # 성공: persisted 카운터 reset
        FETCH_FAILS=0
        rm -f "$STATE_FILE" 2>/dev/null || true
        echo "$PROGRESS" | head -30

        # T2-02 + R3-F6: jq 기반 last_updated (head -1 부정확 회피)
        if command -v jq >/dev/null 2>&1; then
            cur_updated=$(echo "$PROGRESS" | jq -r '.last_updated // empty' 2>/dev/null || echo "")
        else
            cur_updated=$(echo "$PROGRESS" | grep -oE '"last_updated"\s*:\s*"[^"]+"' | head -1 | grep -oE '"[^"]+"$' | tr -d '"')
        fi

        # One-shot polling cannot rely on process memory for stall detection.
        # Compare remote last_updated directly with wall clock so each polling
        # task can detect stale progress independently.
        if [ -n "$cur_updated" ]; then
            cur_epoch=$(date -u -d "$cur_updated" +%s 2>/dev/null || true)
            if [ -n "$cur_epoch" ]; then
                now_epoch=$(date -u +%s)
                stale_age=$((now_epoch - cur_epoch))
                if [ "$stale_age" -gt "$STALL_ALERT" ]; then
                    echo "ALERT: progress.json last_updated stale ${stale_age}s (> ${STALL_ALERT}s)" >&2
                    echo "  사용자 게이트 spawn 권장 (Hard Rule #17)" >&2
                    [ -x "$SCRIPT_DIR/notify_alert.sh" ] && \
                        "$SCRIPT_DIR/notify_alert.sh" progress_stall_detected \
                            "vast $INSTANCE_ID progress stale ${stale_age}s" warn >/dev/null 2>&1 || true
                    return 5
                fi
            fi
        fi

        if [ -n "$cur_updated" ] && [ "$cur_updated" != "$LAST_UPDATED" ]; then
            LAST_UPDATED="$cur_updated"
            STALL_START=""
        elif [ -n "$cur_updated" ] && [ "$cur_updated" = "$LAST_UPDATED" ]; then
            if [ -z "$STALL_START" ]; then
                STALL_START=$(date +%s)
            else
                stall_now=$(date +%s)
                stall_dur=$((stall_now - STALL_START))
                if [ "$stall_dur" -gt "$STALL_ALERT" ]; then
                    echo "ALERT: progress.json stalled ${stall_dur}s (> ${STALL_ALERT}s)" >&2
                    echo "  사용자 게이트 spawn 권장 (Hard Rule #17)" >&2
                    [ -x "$SCRIPT_DIR/notify_alert.sh" ] && \
                        "$SCRIPT_DIR/notify_alert.sh" progress_stall_detected \
                            "vast $INSTANCE_ID progress stalled ${stall_dur}s" warn >/dev/null 2>&1 || true
                    return 5
                fi
            fi
        fi
    else
        # R4-NF8 fix: persist 누적 (one-shot 모드 reset 차단)
        FETCH_FAILS=$((FETCH_FAILS + 1))
        echo "$FETCH_FAILS" > "$STATE_FILE"
        echo "  WARN: progress.json fetch failed (persisted=$FETCH_FAILS / $MAX_FETCH_FAILS)" >&2
        if [ "$FETCH_FAILS" -ge "$MAX_FETCH_FAILS" ]; then
            echo "FAIL: $MAX_FETCH_FAILS consecutive fetch failures, instance unreachable" >&2
            [ -x "$SCRIPT_DIR/notify_alert.sh" ] && \
                "$SCRIPT_DIR/notify_alert.sh" progress_stall_detected \
                    "vast $INSTANCE_ID unreachable ($FETCH_FAILS consecutive fetch fails)" critical \
                    >/dev/null 2>&1 || true
            return 6
        fi
    fi

    return 0  # 진행 중
}

# T2-01 + R3-F14 + R4-F9: one-shot 모드 (worker 10분 timeout 회피)
if [ "$MODE" = "--once" ]; then
    poll_once
    rc=$?
    case "$rc" in
        0)
            echo "INFO: still running. next polling task spawn 권장 (SYNTH-style chain)"
            exit 0
            ;;
        100)
            echo "INFO: DONE → 후속 회수 task spawn 권장"
            exit 0
            ;;
        101)
            echo "INFO: FAIL → 후속 인간 게이트 task spawn 권장"
            exit 2
            ;;
        5)
            exit 4   # stall
            ;;
        6)
            exit 5   # consecutive fetch fail
            ;;
        *)
            exit "$rc"
            ;;
    esac
fi

# --loop 모드 (subprocess 환경 전용, worker가 아닌 cron/nohup으로 spawn 시)
while true; do
    poll_once
    rc=$?
    case "$rc" in
        100) exit 0 ;;
        101) exit 2 ;;
        5|6) exit "$rc" ;;
        *) sleep "$INTERVAL" ;;
    esac
done
