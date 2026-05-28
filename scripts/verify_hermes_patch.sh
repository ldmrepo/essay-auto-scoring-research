#!/bin/bash
# Phase 3 operations C2: hermes codex_app_server.py network_access=true 패치 검증
# Hard Rule #16 + phase_3_operations_guide § 2
# 호출 시점: 매 cycle AUDIT 시작 / hermes 업데이트 직후
#
# 사용: verify_hermes_patch.sh [--show-hash] [--auto-repatch]
#   - --show-hash: 패치 파일 sha256 출력 (변경 추적용)
#   - --auto-repatch: 패치 누락 시 자동 재적용 시도 (백업 후)
#
# 변경 이력:
# - v2 (2026-05-28): T2-06 + T3-21 + R3-F4/F23 + R4-F13 fix
#   - 주석 매치 false positive 차단 (non-comment 라인만 매치)
#   - 패치 파일 sha256 동반 출력 (변경 감지)
#   - --auto-repatch 옵션 (백업 후 sed in-place)

set -eu

TARGET="$HOME/.hermes/hermes-agent/agent/transports/codex_app_server.py"
# T2-06 + R3-F4: 주석이 아닌 라인에만 매치 (^# 시작 제외)
EXPECTED_PATTERN='^[^#]*"sandbox_workspace_write\.network_access=true"'
EXPECTED_LITERAL='"sandbox_workspace_write.network_access=true"'
NEG_PATTERN='^[^#]*"sandbox_workspace_write\.network_access=false"'

SHOW_HASH=0
AUTO_REPATCH=0
AUTO_REPATCH_CONFIRMED=0
while [ $# -gt 0 ]; do
    case "$1" in
        --show-hash) SHOW_HASH=1; shift ;;
        --auto-repatch) AUTO_REPATCH=1; shift ;;
        # R3/R4-NF3 fix: --auto-repatch만으로는 사용자 결정 우회 → 두 단계 게이트
        --auto-repatch-confirmed) AUTO_REPATCH=1; AUTO_REPATCH_CONFIRMED=1; shift ;;
        *) echo "FAIL: unknown option: $1" >&2; exit 3 ;;
    esac
done

# R3/R4-NF3 + R3 3차 #4 fix: --auto-repatch 단독은 dry-run mode + exit 0 + diff/예상 변경 출력
# 두 단계 게이트: --auto-repatch (dry-run 진단) → 사용자 확인 → --auto-repatch-confirmed (실제 patch)
DRY_RUN_MODE=0
if [ "$AUTO_REPATCH" = "1" ] && [ "$AUTO_REPATCH_CONFIRMED" = "0" ]; then
    echo "INFO: --auto-repatch is DRY-RUN. Use --auto-repatch-confirmed for actual modification." >&2
    echo "  Reason: hermes upstream의 의도적 보안 강화(예: CVE 대응)를 silent 우회 차단" >&2
    DRY_RUN_MODE=1
    AUTO_REPATCH=0    # 실제 sed 미실행
fi

if [ ! -f "$TARGET" ]; then
    echo "FAIL: hermes codex_app_server.py not found at $TARGET" >&2
    echo "  hermes 설치 확인 또는 경로 갱신 필요" >&2
    exit 1
fi

# T2-06: 비주석 라인 grep
MATCHES=$(grep -nE "$EXPECTED_PATTERN" "$TARGET" 2>/dev/null || true)
NEG_MATCHES=$(grep -nE "$NEG_PATTERN" "$TARGET" 2>/dev/null || true)

# 부정 패턴 (false 값) 비주석 라인이 있으면 즉시 FAIL
if [ -n "$NEG_MATCHES" ]; then
    echo "FAIL: 'network_access=false' (active, non-comment) found in $TARGET:" >&2
    echo "$NEG_MATCHES" | sed 's/^/  /' >&2
    if [ "$AUTO_REPATCH" = "1" ]; then
        echo "  AUTO-REPATCH attempt (CONFIRMED)..." >&2
        BACKUP="$TARGET.bak.$(date -u +%Y%m%dT%H%M%SZ)"
        cp -p "$TARGET" "$BACKUP"
        echo "  backup: $BACKUP" >&2
        # R3/R4-NF3: diff 출력 (사용자 추적 가능)
        echo "  diff before patch:" >&2
        grep -nE "$NEG_PATTERN|$EXPECTED_PATTERN" "$TARGET" | sed 's/^/    /' >&2
        # sed로 false → true 치환 (비주석 라인만)
        sed -i 's|^\([^#]*\)"sandbox_workspace_write\.network_access=false"|\1"sandbox_workspace_write.network_access=true"|g' "$TARGET"
        # 재검증
        if grep -qE "$NEG_PATTERN" "$TARGET"; then
            echo "  AUTO-REPATCH failed: 'false' still present after sed" >&2
            exit 4
        fi
        echo "  AUTO-REPATCH success" >&2
        # R3/R4-NF3 + R4-NF1: notify_alert 발사 (silent 변경 차단)
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        [ -x "$SCRIPT_DIR/notify_alert.sh" ] && \
            "$SCRIPT_DIR/notify_alert.sh" auto_repatch_executed \
                "verify_hermes_patch.sh --auto-repatch-confirmed re-applied network_access=true (backup: $BACKUP)" critical \
                >/dev/null 2>&1 || true
        # R3-REG-1 fix: sed 치환 후 MATCHES 재계산 (caller false-FAIL exit 2 차단)
        # R4 5차 REG5-1 fix: LINE_COUNT silent false-OK 차단 (>=1 가드 + wc -l 통일)
        MATCHES=$(grep -nE "$EXPECTED_PATTERN" "$TARGET" 2>/dev/null || true)
        if [ -n "$MATCHES" ]; then
            LINE_COUNT=$(printf '%s\n' "$MATCHES" | wc -l)
        else
            LINE_COUNT=0
        fi
        if [ "$LINE_COUNT" -lt 1 ]; then
            echo "FAIL: AUTO-REPATCH sed completed but EXPECTED_PATTERN still missing" >&2
            echo "  hermes 코드 구조 변경 가능성 — 수동 검증 필요" >&2
            exit 5
        fi
        echo "OK: hermes patch re-applied + verified ($TARGET, $LINE_COUNT non-comment match)"
        echo "$MATCHES" | sed 's/^/  /'
        exit 0
    else
        # R3 3차 #4 fix: dry-run mode는 진단 출력만 + exit 0
        if [ "$DRY_RUN_MODE" = "1" ]; then
            echo "  DRY-RUN diagnosis:" >&2
            echo "    found 'network_access=false' (active, non-comment):" >&2
            echo "$NEG_MATCHES" | sed 's/^/      /' >&2
            echo "    예상 변경: false → true (sed in-place + backup)" >&2
            echo "    실제 적용: scripts/verify_hermes_patch.sh --auto-repatch-confirmed" >&2
            exit 0
        fi
        echo "  조치: --auto-repatch-confirmed 옵션 또는 수동 fix" >&2
        exit 2
    fi
fi

# 긍정 패턴 (true 값) 비주석 라인이 없으면 FAIL
if [ -z "$MATCHES" ]; then
    echo "FAIL: hermes patch missing in $TARGET" >&2
    echo "  expected non-comment line containing: $EXPECTED_LITERAL" >&2
    echo "  원인: hermes 업데이트로 패치 덮어쓰기 가능성" >&2
    echo "  조치: 사용자 게이트로 재패치 결정 필요 (또는 --auto-repatch)" >&2
    exit 2
fi

LINE_COUNT=$(echo "$MATCHES" | wc -l)
echo "OK: hermes patch verified ($TARGET, $LINE_COUNT non-comment match)"
echo "$MATCHES" | sed 's/^/  /'

if [ "$SHOW_HASH" = "1" ]; then
    HASH=$(sha256sum "$TARGET" | awk '{print $1}')
    echo "  sha256: $HASH"
fi

exit 0
