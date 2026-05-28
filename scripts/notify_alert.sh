#!/bin/bash
# Phase 3 operations: 비상 게이트 알림 dispatcher (R4-NF1 fix)
# 사용: notify_alert.sh <trigger> <message> [severity]
#   - trigger: configs/board_config.yaml notify_channels.triggers enum
#   - message: 사람-읽기 가능 알림 본문
#   - severity: info | warn | critical (default warn)
#
# board_config.yaml notify_channels의 활성 채널로 발사 (file-log / notify-send / webhook / mail).
# 채널 미가용 또는 발사 실패 시 stderr로 보고 + exit 1 (silent fail 차단).
#
# 호출자:
#   - cycle_preflight.sh (preflight 통과 시 dry-run self-test)
#   - SYNTH/REVIEW worker (cost_circuit_breaker_breach 등)
#   - kanban recovery procedure (kanban_db_recovery_required)
#   - cron scripts (auto_destroy_stale_vast_instance_executed)
#
# 변경 이력: 2026-05-28 신규 (R4-NF1 fix)

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

channel_enabled() {
    local kind="$1"
    python3 - "$REPO_ROOT/configs/board_config.yaml" "$kind" <<'PY'
import sys
config_path, kind = sys.argv[1], sys.argv[2]
try:
    import yaml
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    notify = data.get("notify_channels") or {}
    if not notify.get("enabled", False):
        print("false")
        raise SystemExit
    for channel in notify.get("channels") or []:
        if channel.get("kind") == kind:
            print("true" if channel.get("enabled", False) else "false")
            raise SystemExit
    print("false")
except ImportError:
    print("true" if kind == "file" else "false")
except Exception:
    print("true" if kind == "file" else "false")
PY
}

push_required_count() {
    python3 - "$REPO_ROOT/configs/board_config.yaml" <<'PY'
import sys
try:
    import yaml
    with open(sys.argv[1], encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    print(int((data.get("notify_channels") or {}).get("push_required_count", 0)))
except Exception:
    print(0)
PY
}

file_channel_target() {
    python3 - "$REPO_ROOT/configs/board_config.yaml" <<'PY'
import os
import sys

default = os.path.expanduser("~/.hermes/kanban/alerts/alerts.log")
try:
    import yaml

    with open(sys.argv[1], encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for channel in (data.get("notify_channels") or {}).get("channels") or []:
        if channel.get("kind") == "file":
            print(os.path.expanduser(str(channel.get("target") or default)))
            raise SystemExit
    print(default)
except Exception:
    print(default)
PY
}

load_env_key PHASE3_WEBHOOK_URL
load_env_key PHASE3_ALERT_EMAIL

TRIGGER="${1:?Usage: notify_alert.sh <trigger> <message> [severity]}"
MESSAGE="${2:?Usage: notify_alert.sh <trigger> <message> [severity]}"
SEVERITY="${3:-warn}"

case "$SEVERITY" in
    info|warn|critical) ;;
    *) echo "FAIL: invalid severity: $SEVERITY (info|warn|critical)" >&2; exit 3 ;;
esac

# trigger 화이트리스트 (board_config.yaml triggers enum + 미래 확장 허용)
case "$TRIGGER" in
    cost_circuit_breaker_breach| \
    hermes_patch_verification_fail| \
    kanban_db_recovery_required| \
    cycle_3_consecutive_acceptance_fail| \
    pass_candidate_stuck_consecutive_max| \
    auto_destroy_stale_vast_instance_executed| \
    phase_3_evaluator_wire_up_pending| \
    preflight_self_test| \
    auto_repatch_executed| \
    progress_stall_detected) ;;
    *) echo "WARN: unknown trigger: $TRIGGER (proceeding)" >&2 ;;
esac

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOSTNAME=$(hostname -s 2>/dev/null || echo "unknown")
FULL_MSG="[$SEVERITY][$HOSTNAME][$TS] $TRIGGER: $MESSAGE"

LOG_FILE=$(file_channel_target)
LOG_DIR=$(dirname "$LOG_FILE")
mkdir -p -m 700 "$LOG_DIR" 2>/dev/null || true
if ! (: >> "$LOG_FILE") 2>/dev/null; then
    PRIMARY_LOG_FILE="$LOG_FILE"
    LOG_FILE="$REPO_ROOT/workspace/alerts/alerts.log"
    LOG_DIR=$(dirname "$LOG_FILE")
    mkdir -p -m 700 "$LOG_DIR"
    if (: >> "$LOG_FILE") 2>/dev/null; then
        echo "  warn: primary file-log unavailable ($PRIMARY_LOG_FILE), using fallback ($LOG_FILE)" >&2
    else
        LOG_FILE="$PRIMARY_LOG_FILE"
    fi
fi
LOG_COUNT=0
PUSH_COUNT=0
CONFIGURED_PUSH_COUNT=0
ERRORS=0

# Channel 0: durable local alert log. This keeps headless/server environments
# observable even when desktop/mail/webhook transports are unavailable.
if [ "$(channel_enabled file)" = "true" ] && echo "$FULL_MSG" >> "$LOG_FILE"; then
    chmod 600 "$LOG_FILE" 2>/dev/null || true
    LOG_COUNT=$((LOG_COUNT + 1))
    echo "  sent: file-log ($LOG_FILE)"
else
    ERRORS=$((ERRORS + 1))
    echo "  fail: file-log ($LOG_FILE)" >&2
fi

# Channel 1: notify-send (local desktop)
if [ "$(channel_enabled notify-send)" = "true" ]; then
    CONFIGURED_PUSH_COUNT=$((CONFIGURED_PUSH_COUNT + 1))
    case "$SEVERITY" in
        info) URGENCY="low" ;;
        warn) URGENCY="normal" ;;
        critical) URGENCY="critical" ;;
    esac
    if command -v notify-send >/dev/null 2>&1 && \
        notify-send -u "$URGENCY" -a "phase3-bot" "$TRIGGER" "$MESSAGE" 2>/dev/null; then
        PUSH_COUNT=$((PUSH_COUNT + 1))
        echo "  sent: notify-send"
    else
        ERRORS=$((ERRORS + 1))
        echo "  fail: notify-send" >&2
    fi
fi

# Channel 2: webhook (PHASE3_WEBHOOK_URL env)
if [ "$(channel_enabled webhook)" = "true" ]; then
    CONFIGURED_PUSH_COUNT=$((CONFIGURED_PUSH_COUNT + 1))
    payload=$(python3 - "$TRIGGER" "$SEVERITY" "$HOSTNAME" "$TS" "$MESSAGE" <<'PY'
import json
import sys
trigger, severity, host, ts, message = sys.argv[1:6]
print(json.dumps({
    "trigger": trigger,
    "severity": severity,
    "host": host,
    "ts": ts,
    "message": message,
}, ensure_ascii=False))
PY
)
    if [ -n "${PHASE3_WEBHOOK_URL:-}" ] && command -v curl >/dev/null 2>&1 && \
        curl -sS --max-time 5 -H 'Content-Type: application/json' \
        -d "$payload" "$PHASE3_WEBHOOK_URL" >/dev/null 2>&1; then
        PUSH_COUNT=$((PUSH_COUNT + 1))
        echo "  sent: webhook"
    else
        ERRORS=$((ERRORS + 1))
        echo "  fail: webhook (network or endpoint)" >&2
    fi
fi

# Channel 3: mail (PHASE3_ALERT_EMAIL env)
if [ "$(channel_enabled mail)" = "true" ]; then
    CONFIGURED_PUSH_COUNT=$((CONFIGURED_PUSH_COUNT + 1))
    if [ -n "${PHASE3_ALERT_EMAIL:-}" ] && command -v mail >/dev/null 2>&1 && \
        echo "$FULL_MSG" | mail -s "[phase3] $TRIGGER ($SEVERITY)" "$PHASE3_ALERT_EMAIL" 2>/dev/null; then
        PUSH_COUNT=$((PUSH_COUNT + 1))
        echo "  sent: mail to $PHASE3_ALERT_EMAIL"
    else
        ERRORS=$((ERRORS + 1))
        echo "  fail: mail" >&2
    fi
fi

# 결과 보고
REQUIRED_PUSH=$(push_required_count)
TOTAL_COUNT=$((LOG_COUNT + PUSH_COUNT))
if [ "$TOTAL_COUNT" -eq 0 ]; then
    echo "FAIL: notify_alert dispatched 0 channels" >&2
    echo "  trigger=$TRIGGER, severity=$SEVERITY, message=$MESSAGE" >&2
    echo "  enable file-log or configure notify-send/webhook/mail in configs/board_config.yaml" >&2
    exit 1
fi

if [ "$CONFIGURED_PUSH_COUNT" -gt 0 ] && [ "$PUSH_COUNT" -eq 0 ]; then
    echo "FAIL: configured push channel(s) did not deliver (configured=$CONFIGURED_PUSH_COUNT)" >&2
    exit 1
fi

if [ "$PUSH_COUNT" -lt "$REQUIRED_PUSH" ]; then
    echo "FAIL: push delivery below required count ($PUSH_COUNT < $REQUIRED_PUSH)" >&2
    exit 1
fi

echo "OK: alert recorded to $LOG_COUNT durable channel(s), pushed to $PUSH_COUNT user channel(s) (errors=$ERRORS)"
exit 0
