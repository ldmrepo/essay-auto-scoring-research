#!/bin/bash
# Phase 3 operations: cycle 진입 직전 사전 체크 (operations_guide § 7)
# 사용: cycle_preflight.sh <cycle_id> [--require-vast] [--auto-destroy-stale] [--vast-label LABEL]
# 실패 1건 이상 시 exit 1 → cycle 진입 거부 (Hard Rule #18)
#
# 변경 이력:
# - v2 (2026-05-28): T1-01/T1-07/T2-03/T2-16/T2-17/T2-19/T3-10/T3-15/T3-16/T3-24
# - v3 (2026-05-28): R2-NF1 + R3-NF2/NF5/NF6 + R4-NF1/NF5/NF7 + Hard Rule #16 best-effort check step
#   - [11/12] wire-up status 검증 (R2-NF1) — ACCEPTANCE_CRITERIA mid_multitask._implementation_status
#   - [7/12] --auto-destroy-stale에 label filter (R3-NF2/R4-NF2)
#   - [4/12] backup age 검증 — 마지막 auto_* 백업 시각 (R3-NF5)
#   - [2/12] profile sandbox_mode 키 부재 case (R3-NF6)
#   - lock 파일 사용자별 격리 (R4-NF5) — backup_kanban_db.sh도 동일 변경
#   - [3/12] .env perm WARN → FAIL when secrets present (R4-NF7)
#   - [12/12] notify_channels self-test — notify_alert.sh dry-run (R4-NF1)
#   - [8/12] vast.ai task metadata Hard Rule #16 best-effort check (실제 enforce는 SYNTH worker prompt)

# set -e 의도적 미사용 (각 체크 실패 누적이 목적)
set -u

CYCLE_ID="${1:?Usage: cycle_preflight.sh <cycle_id> (e.g., M2) [--require-vast] [--auto-destroy-stale] [--vast-label LABEL]}"
shift

# CYCLE_ID 화이트리스트
if ! [[ "$CYCLE_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "FAIL: cycle_id contains invalid chars: $CYCLE_ID" >&2
    exit 3
fi

REQUIRE_VAST=0
AUTO_DESTROY_STALE=0
VAST_LABEL=""
while [ $# -gt 0 ]; do
    case "$1" in
        --require-vast) REQUIRE_VAST=1; shift ;;
        --auto-destroy-stale) AUTO_DESTROY_STALE=1; shift ;;
        --vast-label) VAST_LABEL="${2:-}"; shift 2 ;;
        *) echo "FAIL: unknown option: $1" >&2; exit 3 ;;
    esac
done

# R3-NF2/R4-NF2 fix: --auto-destroy-stale은 --vast-label 의무 (label filter 없이 무차별 destroy 차단)
if [ "$AUTO_DESTROY_STALE" = "1" ] && [ -z "$VAST_LABEL" ]; then
    echo "FAIL: --auto-destroy-stale requires --vast-label <project-label> to filter (others' instances 보호)" >&2
    echo "  e.g., cycle_preflight.sh M2 --auto-destroy-stale --vast-label essay-auto-scoring" >&2
    exit 3
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
KANBAN_ROOT="$HOME/.hermes/kanban"

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

load_env_key VAST_API_KEY
load_env_key PHASE3_WEBHOOK_URL
load_env_key PHASE3_ALERT_EMAIL

FAILS=0
WARNS=0

# Helper: notify_alert dispatch (silent on success, warn on fail)
notify_if_available() {
    local trigger="$1"; local msg="$2"; local sev="${3:-warn}"
    if [ -x "$HERE/notify_alert.sh" ]; then
        "$HERE/notify_alert.sh" "$trigger" "$msg" "$sev" >/dev/null 2>&1 || true
    fi
}

echo "=== Cycle $CYCLE_ID Preflight ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="

# [1/12] hermes 패치 검증 (C2)
echo "[1/12] hermes patch verification..."
if "$HERE/verify_hermes_patch.sh"; then
    :
else
    FAILS=$((FAILS + 1))
    notify_if_available hermes_patch_verification_fail "preflight [1/12] failed" critical
fi

# [2/12] codex + hermes profile sandbox 정책 (C3) — R3-NF6 fix: 키 부재 case
echo "[2/12] codex sandbox policy (config.toml + profiles)..."
CODEX_CFG="$HOME/.codex/config.toml"
if [ -f "$CODEX_CFG" ] && grep -q 'sandbox_mode = "danger-full-access"' "$CODEX_CFG"; then
    echo "  OK: ~/.codex/config.toml sandbox_mode=danger-full-access"
else
    echo "  FAIL: codex sandbox_mode != danger-full-access" >&2
    FAILS=$((FAILS + 1))
fi
# NEW-H1 + R3-NF6 fix: hermes profile은 YAML 구조 (profile.yaml + config.yaml).
# 이전 .toml grep은 영구 false-pass (R4 3차 finding) → .yaml로 변경.
PROFILE_DIR="$HOME/.hermes/profiles"
if [ -d "$PROFILE_DIR" ]; then
    # profile 디렉토리들 (gauss, aristotle, ...) 안의 profile.yaml + config.yaml 검사
    PROFILE_YAML_FILES=$(find "$PROFILE_DIR" -maxdepth 2 -type f \( -name 'profile.yaml' -o -name 'config.yaml' \) 2>/dev/null)
    PROFILE_COUNT=$(echo "$PROFILE_YAML_FILES" | grep -c . || echo 0)
    PROFILE_BAD=""
    if [ -n "$PROFILE_YAML_FILES" ]; then
        for pf in $PROFILE_YAML_FILES; do
            # NEW-PRE-1 fix: 4종 키 모두 검사 (sandbox_mode + sandbox_workspace_write + approval_policy + network_access)
            # 키 부재 = codex default 상속 (정상). 키 존재 시 정확한 값이어야 함.
            if grep -qE '^\s*sandbox_mode\s*:' "$pf"; then
                if ! grep -qE '^\s*sandbox_mode\s*:\s*"?danger-full-access"?' "$pf"; then
                    PROFILE_BAD="$PROFILE_BAD $pf:sandbox_mode"
                fi
            fi
            if grep -qE '^\s*approval_policy\s*:' "$pf"; then
                if ! grep -qE '^\s*approval_policy\s*:\s*"?never"?' "$pf"; then
                    PROFILE_BAD="$PROFILE_BAD $pf:approval_policy"
                fi
            fi
            # NEW-PRE-1: network_access (sandbox_workspace_write 하위 키 또는 단독)
            if grep -qE '^\s*network_access\s*:' "$pf"; then
                if ! grep -qE '^\s*network_access\s*:\s*true' "$pf"; then
                    PROFILE_BAD="$PROFILE_BAD $pf:network_access"
                fi
            fi
            # NEW-PRE-1: sandbox_workspace_write (전체 블록 비활성화 검출)
            if grep -qE '^\s*sandbox_workspace_write\s*:' "$pf"; then
                # 블록 내부 network_access는 위에서 별도 검사. 블록 자체가 null 등이면 INFO만.
                :
            fi
            # 명시적 위반 패턴
            if grep -qE '^\s*sandbox_mode\s*:\s*"?(read-only|workspace-write)"?' "$pf"; then
                PROFILE_BAD="$PROFILE_BAD $pf:explicit-violation"
            fi
        done
    fi
    if [ -n "$PROFILE_BAD" ]; then
        echo "  FAIL: profile sandbox override mismatch (NEW-H1 fix — yaml 패턴):" >&2
        echo "$PROFILE_BAD" | tr ' ' '\n' | grep -v '^$' | sed 's/^/    /' >&2
        FAILS=$((FAILS + 1))
    else
        echo "  OK: hermes profiles ($PROFILE_COUNT yaml files checked, no conflicting override)"
    fi
fi

# [3/12] .env perm — R4-NF7 fix: secrets 포함 시 FAIL 격상
echo "[3/12] .env file permissions..."
ENV_FILE="$REPO_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    PERM=$(stat -c%a "$ENV_FILE" 2>/dev/null || stat -f%Lp "$ENV_FILE" 2>/dev/null)
    HAS_SECRET=0
    if grep -qE '^(VAST_API_KEY|PHASE3_WEBHOOK_URL|PHASE3_ALERT_EMAIL|.*_TOKEN|.*_SECRET|.*_KEY)=' "$ENV_FILE" 2>/dev/null; then
        HAS_SECRET=1
    fi
    if [ "$PERM" = "600" ] || [ "$PERM" = "400" ]; then
        echo "  OK: .env perm=$PERM"
    else
        if [ "$HAS_SECRET" = "1" ]; then
            echo "  FAIL: .env perm=$PERM but secrets present. chmod 600 .env" >&2
            FAILS=$((FAILS + 1))
        else
            echo "  WARN: .env perm=$PERM (recommend 600)" >&2
            WARNS=$((WARNS + 1))
        fi
    fi
fi

# [4/12] kanban DB pre-cycle 백업 + age 검증 (R3-NF5 fix)
echo "[4/12] kanban DB pre-cycle backup + recent auto backup age..."
if HERMES_BACKUP_FAIL_ON_LOCK=1 "$HERE/backup_kanban_db.sh" "cycle_${CYCLE_ID}_pre"; then
    :
else
    FAILS=$((FAILS + 1))
fi
# R3-NF5: 마지막 auto_* 백업이 12h 이내인지 (6h cron이 정상 작동했는지)
LAST_AUTO=$(find "$KANBAN_ROOT/backups" -maxdepth 1 -type f -name 'auto_*.db' -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
NOW=$(date +%s)
if [ -n "$LAST_AUTO" ]; then
    AGE_HOURS=$(awk -v now="$NOW" -v last="$LAST_AUTO" 'BEGIN { printf "%d", (now - last) / 3600 }')
    if [ "$AGE_HOURS" -gt 12 ]; then
        echo "  WARN: last auto backup ${AGE_HOURS}h ago (>12h, cron skip 가능성)" >&2
        WARNS=$((WARNS + 1))
    else
        echo "  OK: last auto backup ${AGE_HOURS}h ago"
    fi
else
    echo "  WARN: no auto_*.db backup found (cron not yet registered or no run)" >&2
    WARNS=$((WARNS + 1))
fi

# [5/12] kanban DB 무결성 (실제 경로 동적 도출)
echo "[5/12] kanban DB integrity..."
if [ -f "$KANBAN_ROOT/current" ]; then
    BOARD=$(tr -d '\n' < "$KANBAN_ROOT/current")
    KANBAN_DB="$KANBAN_ROOT/boards/$BOARD/kanban.db"
    if [ -f "$KANBAN_DB" ]; then
        INTEGRITY=$(sqlite3 "$KANBAN_DB" "PRAGMA integrity_check;" 2>&1)
        FIRST_LINE=$(echo "$INTEGRITY" | head -1)
        if [ "$FIRST_LINE" = "ok" ]; then
            echo "  OK: kanban DB integrity=ok (board=$BOARD)"
        else
            echo "  FAIL: kanban DB corrupt: $INTEGRITY" >&2
            FAILS=$((FAILS + 1))
            notify_if_available kanban_db_recovery_required "preflight [5/12] integrity fail" critical
        fi
    else
        echo "  WARN: kanban DB not found at $KANBAN_DB (신규 보드?)" >&2
        WARNS=$((WARNS + 1))
    fi
else
    echo "  WARN: $KANBAN_ROOT/current not found (active board pointer 부재)" >&2
    WARNS=$((WARNS + 1))
fi

# [6/12] cron 등록 검증
echo "[6/12] cron backup registration..."
if crontab -l 2>/dev/null | grep -q 'backup_kanban_db.sh'; then
    echo "  OK: crontab registered (backup_kanban_db.sh)"
else
    echo "  WARN: crontab not registered. install:" >&2
    echo "    (crontab -l 2>/dev/null; echo \"0 */6 * * * $HERE/backup_kanban_db.sh >> $KANBAN_ROOT/backups/cron.log 2>&1\") | crontab -" >&2
    WARNS=$((WARNS + 1))
fi

# [7/12] vast.ai 잔여 인스턴스 (R3-NF2/R4-NF2 fix: --vast-label filter)
echo "[7/12] vast.ai stale instances..."
if [ -n "${VAST_API_KEY:-}" ]; then
    export VAST_API_KEY
    if ! command -v jq >/dev/null 2>&1; then
        echo "  FAIL: jq required for safe vast.ai instance parsing/label filtering" >&2
        echo "    install: sudo apt-get install jq" >&2
        FAILS=$((FAILS + 1))
        INSTANCE_COUNT=0
    else
        ALL_INSTANCES=$(vastai show instances --raw 2>/dev/null)
        if [ -n "$VAST_LABEL" ]; then
            # label filter (vast.ai의 label 필드는 instance 생성 시 --label로 지정)
            FILTERED=$(echo "$ALL_INSTANCES" | jq --arg lbl "$VAST_LABEL" '[.[] | select(.label == $lbl)]' 2>/dev/null)
            INSTANCE_COUNT=$(echo "$FILTERED" | jq 'length' 2>/dev/null || echo "0")
        else
            FILTERED=""
            INSTANCE_COUNT=$(echo "$ALL_INSTANCES" | jq 'length' 2>/dev/null || echo "0")
        fi
    fi
    if [ "$INSTANCE_COUNT" -eq 0 ]; then
        if [ -n "$VAST_LABEL" ]; then
            echo "  OK: no vast.ai instances with label=$VAST_LABEL"
        else
            echo "  OK: no vast.ai instances running"
        fi
    else
        if [ "$AUTO_DESTROY_STALE" = "1" ] && [ -n "$VAST_LABEL" ]; then
            echo "  AUTO-DESTROY: $INSTANCE_COUNT stale instance(s) with label=$VAST_LABEL"
            echo "$FILTERED" | jq -r '.[].id' 2>/dev/null | while read -r id; do
                echo "    destroying instance $id (label=$VAST_LABEL)..."
                vastai destroy instance "$id" 2>&1 | head -1 || true
            done
            notify_if_available auto_destroy_stale_vast_instance_executed \
                "[$CYCLE_ID] destroyed $INSTANCE_COUNT vast instances (label=$VAST_LABEL)" warn
        else
            echo "  FAIL: $INSTANCE_COUNT vast.ai instance(s) running. Use --auto-destroy-stale --vast-label <label>, or destroy manually." >&2
            FAILS=$((FAILS + 1))
        fi
    fi
else
    if [ "$REQUIRE_VAST" = "1" ]; then
        echo "  FAIL: VAST_API_KEY unset but --require-vast" >&2
        FAILS=$((FAILS + 1))
    else
        echo "  INFO: VAST_API_KEY unset"
    fi
fi

# [8/12] Hard Rule #16 best-effort check — vast.ai 학습 task의 expected_duration_min metadata
# R2-NEW-G2 fix: "enforce" 표현 완화 (실제 hard-block은 SYNTH/REVIEW worker prompt 의존)
# (R2-NF5/R3-NF8/R2-G2 fix — best-effort: 현재 cycle에 등록된 vast task의 metadata 부재 검출만)
echo "[8/12] Hard Rule #16 expected_duration_min metadata best-effort check..."
# 현재 active board에서 cycle_id 관련 vast 학습 task 검색
if command -v hermes >/dev/null 2>&1 && [ -f "$KANBAN_ROOT/current" ]; then
    BOARD=$(tr -d '\n' < "$KANBAN_ROOT/current")
    # vast task = task body 또는 metadata에 "vast" + cycle_id 포함
    # hermes CLI 출력 형식이 환경 종속이므로 grep 기반 best-effort
    VAST_TASKS=$(hermes kanban list --board "$BOARD" 2>/dev/null \
        | grep -iE "vast|cycle.*$CYCLE_ID.*model" || true)
    if [ -n "$VAST_TASKS" ]; then
        # 각 vast task에 대해 expected_duration_min metadata 확인
        # 실제 hermes API 의존 — 본 체크는 spec text only로 표기
        echo "  INFO: vast task detected for $CYCLE_ID — SYNTH/REVIEW가 metadata 검증 의무 (Hard Rule #16)"
        echo "  → 실제 hard-block은 SYNTH worker prompt 의존 (preflight는 best-effort 검출만)"
    else
        echo "  INFO: no vast task yet registered for $CYCLE_ID (skipped)"
    fi
else
    echo "  INFO: hermes CLI unavailable or no active board (Hard Rule #16 check skipped)"
fi

# [9/12] 디스크 사용량
echo "[9/12] disk usage..."
DF_LINE=$(LANG=C df -P "$REPO_ROOT" | tail -1)
USE_PCT=$(echo "$DF_LINE" | awk '{print $5}' | tr -d '%')
AVAIL_KB=$(echo "$DF_LINE" | awk '{print $4}')
AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
if [ "$USE_PCT" -ge 95 ]; then
    echo "  FAIL: disk usage ${USE_PCT}% (avail ${AVAIL_GB}GB, >= 95%)" >&2
    FAILS=$((FAILS + 1))
elif [ "$USE_PCT" -ge 85 ]; then
    echo "  WARN: disk usage ${USE_PCT}% (avail ${AVAIL_GB}GB, >= 85%)" >&2
    WARNS=$((WARNS + 1))
else
    echo "  OK: disk usage ${USE_PCT}% (avail ${AVAIL_GB}GB)"
fi

# [10/12] notification 채널 가용성
echo "[10/12] notification channel availability..."
ALERT_OK=0
ALERT_CHANNELS=""
ALERT_OUTPUT=""
if [ -x "$HERE/notify_alert.sh" ] && ALERT_OUTPUT=$("$HERE/notify_alert.sh" preflight_self_test "[$CYCLE_ID] alert channel self-test" info 2>&1); then
    ALERT_OK=1
    ALERT_CHANNELS=$(echo "$ALERT_OUTPUT" | awk -F'sent: ' '/sent: / { print $2 }' | tr '\n' ' ')
fi
if [ "$ALERT_OK" = "1" ]; then
    echo "  OK: alert self-test passed (${ALERT_CHANNELS:-see notify_alert output})"
else
    echo "  FAIL: no alert channel (R4-NF1 — 비상 게이트 도달 0%)" >&2
    [ -n "$ALERT_OUTPUT" ] && echo "$ALERT_OUTPUT" | sed 's/^/    /' >&2
    echo "    enable file-log or configure notify-send/webhook/mail in configs/board_config.yaml" >&2
    FAILS=$((FAILS + 1))
fi

# [11/12] Phase 3 evaluator wire-up 상태 (R2-NF1 + R3 3차 #1 + R2-G4 + R2-NEW-G1 fix)
echo "[11/12] Phase 3 evaluator wire-up status..."
ACCEPT_FILE="$REPO_ROOT/ACCEPTANCE_CRITERIA.yaml"
if [ -f "$ACCEPT_FILE" ]; then
    # R3 3차 #1 + R2-NEW-G1 fix: PyYAML 파싱 + ImportError를 try 안에서 catch + stderr 표시
    # 미설치 환경 (vast.ai bootstrap)에서 silent skip 차단
    WIRE_STATUS=$(python3 -c "
import sys
try:
    import yaml
    with open('$ACCEPT_FILE') as f:
        data = yaml.safe_load(f)
    print(data['stages']['mid_multitask'].get('_implementation_status', 'MISSING'))
except ImportError as e:
    print('IMPORT_ERROR: PyYAML not installed (pip install pyyaml)', file=sys.stderr)
    print('YAML_MISSING')
except Exception as e:
    print('PARSE_ERROR:' + str(e), file=sys.stderr)
    print('UNKNOWN')
")

    if [ "$WIRE_STATUS" = "wired_v1" ]; then
        echo "  OK: mid_multitask._implementation_status=$WIRE_STATUS"
    elif [ "$WIRE_STATUS" = "not_wired_yet" ]; then
        # Phase 3 M2 wire-up cycle은 not_wired_yet 허용. 그 외 cycle은 FAIL
        if [ "$CYCLE_ID" = "M2" ]; then
            echo "  WARN: mid_multitask._implementation_status=not_wired_yet (M2 wire-up cycle 허용)" >&2
            WARNS=$((WARNS + 1))
            notify_if_available phase_3_evaluator_wire_up_pending \
                "[$CYCLE_ID] mid_multitask wire-up pending — M2 first sub-task로 처리" info
        else
            echo "  FAIL: mid_multitask._implementation_status=not_wired_yet for $CYCLE_ID (M2 wire-up 필수 선행)" >&2
            FAILS=$((FAILS + 1))
        fi
    elif [ "$WIRE_STATUS" = "MISSING" ]; then
        echo "  FAIL: mid_multitask._implementation_status key missing in ACCEPTANCE_CRITERIA.yaml" >&2
        FAILS=$((FAILS + 1))
    elif [ "$WIRE_STATUS" = "YAML_MISSING" ]; then
        # R2-NEW-G1 fix: PyYAML 미설치를 FAIL로 격상 (silent skip 차단)
        echo "  FAIL: PyYAML not installed. wire-up status 검증 불가." >&2
        echo "    설치: pip install pyyaml" >&2
        FAILS=$((FAILS + 1))
    else
        echo "  WARN: _implementation_status unknown ($WIRE_STATUS)" >&2
        WARNS=$((WARNS + 1))
    fi
fi

# [12/12] MILESTONE + spec presence + freshness
echo "[12/12] milestone + spec presence + freshness..."
MILESTONE="$REPO_ROOT/MILESTONE_v3.md"
SPEC_V1_1="$REPO_ROOT/docs/multi_task_채점모델_구현_스펙_v_1_1.md"
SPEC_FALLBACK=$(find "$REPO_ROOT/docs" -maxdepth 1 -type f -name 'multi_task*v_1_*.md' 2>/dev/null | sort -V | tail -1)
SPEC_FOUND=""
if [ -f "$SPEC_V1_1" ]; then SPEC_FOUND="$SPEC_V1_1"; elif [ -n "$SPEC_FALLBACK" ]; then SPEC_FOUND="$SPEC_FALLBACK"; fi

if [ -f "$MILESTONE" ] && [ -n "$SPEC_FOUND" ]; then
    echo "  OK: MILESTONE_v3.md + spec ($(basename "$SPEC_FOUND"))"
    if [ -d "$REPO_ROOT/.git" ] && command -v git >/dev/null 2>&1; then
        RECENT=$(cd "$REPO_ROOT" && git log -1 --since="14 days ago" --format=%h -- "$SPEC_FOUND" 2>/dev/null || true)
        if [ -z "$RECENT" ]; then
            echo "  WARN: spec not modified in last 14 days" >&2
        fi
    fi
else
    echo "  FAIL: missing — MILESTONE=$([ -f "$MILESTONE" ] && echo ok || echo missing), SPEC=$([ -n "$SPEC_FOUND" ] && echo ok || echo missing)" >&2
    FAILS=$((FAILS + 1))
fi

echo ""
echo "=== Preflight Summary ==="
echo "  fails: $FAILS / warns: $WARNS"
if [ "$FAILS" -gt 0 ]; then
    echo "  → cycle $CYCLE_ID 진입 거부 (Hard Rule #18)" >&2
    notify_if_available preflight_self_test "[$CYCLE_ID] preflight FAILS=$FAILS WARNS=$WARNS" critical
    exit 1
fi
if [ "$WARNS" -gt 0 ]; then
    echo "  → warns 존재. cycle $CYCLE_ID 진입 진행하되 모니터 강화"
fi
echo "  → cycle $CYCLE_ID 진입 승인"
# preflight 통과 시 self-test alert (silent 발사 — 채널 활성 확인)
notify_if_available preflight_self_test "[$CYCLE_ID] preflight passed (warns=$WARNS)" info
exit 0
