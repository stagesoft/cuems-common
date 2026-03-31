#!/bin/bash
# test-systemd-deps.sh — Validate CUEMS systemd service dependency chains
#
# Two modes:
#   (default)  Static analysis of unit files — safe, read-only
#   --live     Start/stop tests on the running system (destructive, prompts)
#
# Exit codes: 0=pass, 1=failures, 2=warnings only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
UNIT_DIR="${REPO_DIR}/etc/systemd/system"
LIVE=false
FAILURES=0
WARNINGS=0

# Expected services per role
NODE_EXPECTED=(jackd-cuems cuems-hdmi-audio-map jack-alsa-bridges cuems-node-engine cuems-videocomposer cuems-nodeconf)
CTRL_EXPECTED=(cuems-controller-engine cuems-editor cuems-midiconnector)

# Controller-only services (must NOT appear in node-role Requires)
CTRL_ONLY=(cuems-controller-engine cuems-editor cuems-midiconnector)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}PASS${NC}  $1"; }
fail() { echo -e "  ${RED}FAIL${NC}  $1"; ((FAILURES++)) || true; }
warn() { echo -e "  ${YELLOW}WARN${NC}  $1"; ((WARNINGS++)) || true; }

# Parse args
for arg in "$@"; do
    case "$arg" in
        --live) LIVE=true ;;
        --source-dir=*) UNIT_DIR="${arg#--source-dir=}" ;;
        --help|-h)
            echo "Usage: $0 [--live] [--source-dir=PATH]"
            echo "  --live          Run start/stop tests (prompts for confirmation)"
            echo "  --source-dir=   Path to unit files (default: repo etc/systemd/system/)"
            exit 0
            ;;
    esac
done

echo "=== CUEMS Systemd Dependency Tests ==="
echo "Unit directory: ${UNIT_DIR}"
echo ""

# ─── T1: Unit file syntax ───────────────────────────────────────────
echo "T1: Unit file syntax verification"
VERIFY_FAIL=false
for unit in "${UNIT_DIR}"/cuems-*.service "${UNIT_DIR}"/cuems-*.target; do
    [ -f "$unit" ] || continue
    name=$(basename "$unit")
    if systemd-analyze verify "$unit" 2>&1 | grep -v -E "Cannot add dependency|anydesk|PIDFile" | grep -qi "error\|failed"; then
        fail "$name has syntax errors"
        VERIFY_FAIL=true
    fi
done
if [ "$VERIFY_FAIL" = false ]; then
    pass "All unit files pass syntax verification"
fi
echo ""

# ─── T2: Circular dependency detection ──────────────────────────────
echo "T2: Circular dependency detection"
# Build adjacency list from Requires/After and check for simple cycles
declare -A REQUIRES_MAP
CYCLE_FOUND=false
for unit in "${UNIT_DIR}"/cuems-*.service "${UNIT_DIR}"/cuems-*.target; do
    [ -f "$unit" ] || continue
    name=$(basename "$unit" | sed 's/\.\(service\|target\)$//')
    deps=$(grep -E '^Requires=' "$unit" 2>/dev/null | sed 's/Requires=//' | tr ' ' '\n' | sed 's/\.\(service\|target\)$//' || true)
    for dep in $deps; do
        # Check reverse: does dep require name?
        for other in "${UNIT_DIR}"/cuems-*.service "${UNIT_DIR}"/cuems-*.target; do
            [ -f "$other" ] || continue
            other_name=$(basename "$other" | sed 's/\.\(service\|target\)$//')
            [ "$other_name" = "$dep" ] || continue
            if grep -qE "^Requires=.*${name}" "$other" 2>/dev/null; then
                fail "Circular Requires: $name <-> $dep"
                CYCLE_FOUND=true
            fi
        done
    done
done
if [ "$CYCLE_FOUND" = false ]; then
    pass "No circular dependencies found"
fi
echo ""

# ─── T3: Role membership validation ─────────────────────────────────
echo "T3: Role membership validation"

# Check node-role: services should have WantedBy=cuems-node.target
for svc in "${NODE_EXPECTED[@]}"; do
    unit="${UNIT_DIR}/${svc}.service"
    if [ ! -f "$unit" ]; then
        fail "Node service $svc.service not found"
        continue
    fi
    if grep -q "WantedBy=cuems-node.target" "$unit" 2>/dev/null; then
        pass "$svc.service -> WantedBy=cuems-node.target"
    else
        fail "$svc.service missing WantedBy=cuems-node.target"
    fi
done

# Check controller-role: services should have WantedBy=cuems-controller.target
for svc in "${CTRL_EXPECTED[@]}"; do
    unit="${UNIT_DIR}/${svc}.service"
    if [ ! -f "$unit" ]; then
        fail "Controller service $svc.service not found"
        continue
    fi
    if grep -q "WantedBy=cuems-controller.target" "$unit" 2>/dev/null; then
        pass "$svc.service -> WantedBy=cuems-controller.target"
    else
        fail "$svc.service missing WantedBy=cuems-controller.target"
    fi
done
echo ""

# ─── T4: PartOf propagation map ─────────────────────────────────────
echo "T4: PartOf propagation verification"

# Node services with expected PartOf
declare -A PARTOF_MAP=(
    [jackd-cuems]="cuems-node.target"
    [cuems-hdmi-audio-map]="cuems-node.target"
    [cuems-videocomposer]="cuems-node.target"
    [cuems-node-engine]="cuems-node.target"
    [cuems-nodeconf]="cuems-node.target"
    [cuems-controller-engine]="cuems-controller.target"
    [cuems-editor]="cuems-controller.target"
    [cuems-midiconnector]="cuems-controller.target"
)

for svc in "${!PARTOF_MAP[@]}"; do
    expected="${PARTOF_MAP[$svc]}"
    unit="${UNIT_DIR}/${svc}.service"
    if [ ! -f "$unit" ]; then
        warn "$svc.service not found, skipping PartOf check"
        continue
    fi
    if grep -q "PartOf=${expected}" "$unit" 2>/dev/null; then
        pass "$svc.service PartOf=$expected"
    else
        actual=$(grep "^PartOf=" "$unit" 2>/dev/null || echo "(none)")
        fail "$svc.service expected PartOf=$expected, got $actual"
    fi
done

# Check drop-in overrides
for dropin in "${UNIT_DIR}/avahi-daemon.d/cuems-node-group.conf" "${UNIT_DIR}/rtpmidid.service.d/cuems-node-group.conf"; do
    if [ -f "$dropin" ]; then
        name=$(basename "$(dirname "$dropin")")
        if grep -q "PartOf=cuems-node.target" "$dropin"; then
            pass "$name drop-in PartOf=cuems-node.target"
        else
            fail "$name drop-in missing PartOf=cuems-node.target"
        fi
    fi
done
echo ""

# ─── T5: Ordering consistency ───────────────────────────────────────
echo "T5: Ordering consistency"

# Expected ordering pairs: A must be Before or B must be After A
declare -A ORDER_CHECKS=(
    ["cuems-hdmi-audio-map -> jackd-cuems"]="cuems-hdmi-audio-map.service:Before:jackd-cuems"
    ["jackd-cuems -> cuems-node-engine"]="cuems-node-engine.service:After:jackd-cuems"
    ["avahi-daemon -> cuems-controller-engine"]="cuems-controller-engine.service:After:avahi-daemon"
    ["cuems-controller-engine -> cuems-editor"]="cuems-editor.service:After:cuems-controller-engine"
)

for desc in "${!ORDER_CHECKS[@]}"; do
    IFS=':' read -r unit directive dep <<< "${ORDER_CHECKS[$desc]}"
    unit_file="${UNIT_DIR}/${unit}"
    if [ ! -f "$unit_file" ]; then
        warn "Cannot check ordering '$desc': $unit not found"
        continue
    fi
    if grep -qE "^${directive}=.*${dep}" "$unit_file" 2>/dev/null; then
        pass "$desc"
    else
        fail "Ordering not enforced: $desc"
    fi
done
echo ""

# ─── T6: Cross-role contamination ───────────────────────────────────
echo "T6: Cross-role contamination check"

CONTAMINATED=false
for svc in "${NODE_EXPECTED[@]}"; do
    unit="${UNIT_DIR}/${svc}.service"
    [ -f "$unit" ] || continue
    requires=$(grep "^Requires=" "$unit" 2>/dev/null | sed 's/Requires=//' || true)
    for ctrl in "${CTRL_ONLY[@]}"; do
        if echo "$requires" | grep -q "${ctrl}"; then
            fail "Node service $svc.service requires controller service $ctrl"
            CONTAMINATED=true
        fi
    done
done
if [ "$CONTAMINATED" = false ]; then
    pass "No node services depend on controller-only services"
fi
echo ""

# ─── T7: Source vs installed drift ───────────────────────────────────
echo "T7: Source vs installed drift"

DRIFT_COUNT=0
for unit in "${UNIT_DIR}"/cuems-*.service "${UNIT_DIR}"/cuems-*.target; do
    [ -f "$unit" ] || continue
    name=$(basename "$unit")
    # Check both /lib/systemd/system and /etc/systemd/system
    installed=""
    for prefix in /lib/systemd/system /etc/systemd/system; do
        if [ -f "${prefix}/${name}" ]; then
            installed="${prefix}/${name}"
            break
        fi
    done
    if [ -z "$installed" ]; then
        warn "$name not installed on system"
        continue
    fi
    if ! diff -q "$unit" "$installed" > /dev/null 2>&1; then
        warn "$name differs from installed ($installed)"
        ((DRIFT_COUNT++)) || true
    fi
done
if [ "$DRIFT_COUNT" -eq 0 ]; then
    pass "No drift detected (all matching installed files are in sync)"
fi
echo ""

# ─── T8: Controller target requires node target ─────────────────────
echo "T8: Controller target requires node target"
ctrl_target="${UNIT_DIR}/cuems-controller.target"
if [ -f "$ctrl_target" ]; then
    if grep -q "Requires=cuems-node.target" "$ctrl_target"; then
        pass "cuems-controller.target Requires=cuems-node.target"
    else
        fail "cuems-controller.target does not require cuems-node.target"
    fi
    if grep -q "After=cuems-node.target" "$ctrl_target"; then
        pass "cuems-controller.target After=cuems-node.target"
    else
        fail "cuems-controller.target missing After=cuems-node.target"
    fi
else
    fail "cuems-controller.target not found"
fi
echo ""

# ─── Live tests ─────────────────────────────────────────────────────
if [ "$LIVE" = true ]; then
    echo "=== LIVE TESTS (requires root) ==="
    echo "WARNING: This will start and stop CUEMS services."
    read -rp "Continue? [y/N] " confirm
    if [[ "$confirm" != [yY] ]]; then
        echo "Aborted."
        exit 2
    fi

    echo ""
    echo "L1: Node target start"
    sudo systemctl start cuems-node.target 2>/dev/null || true
    sleep 3
    for svc in "${NODE_EXPECTED[@]}"; do
        if systemctl is-active --quiet "${svc}.service" 2>/dev/null; then
            pass "${svc}.service is active"
        else
            fail "${svc}.service is NOT active"
        fi
    done
    echo ""

    echo "L2: Controller target start (should pull in node)"
    sudo systemctl start cuems-controller.target 2>/dev/null || true
    sleep 3
    all_expected=("${NODE_EXPECTED[@]}" "${CTRL_EXPECTED[@]}")
    for svc in "${all_expected[@]}"; do
        if systemctl is-active --quiet "${svc}.service" 2>/dev/null; then
            pass "${svc}.service is active"
        else
            fail "${svc}.service is NOT active"
        fi
    done
    echo ""

    echo "L3: Stop propagation (stop node target)"
    sudo systemctl stop cuems-node.target 2>/dev/null || true
    sleep 3
    for svc in "${NODE_EXPECTED[@]}"; do
        if ! systemctl is-active --quiet "${svc}.service" 2>/dev/null; then
            pass "${svc}.service stopped with node target"
        else
            warn "${svc}.service still running after node target stop"
        fi
    done
    echo ""

    echo "L4: Failure isolation"
    sudo systemctl start cuems-controller.target 2>/dev/null || true
    sleep 3
    sudo systemctl stop cuems-wifi.service 2>/dev/null || true
    if systemctl is-active --quiet cuems-controller-engine.service 2>/dev/null; then
        pass "controller-engine survives wifi stop"
    else
        fail "controller-engine stopped when wifi stopped"
    fi

    # Clean up
    sudo systemctl stop cuems-controller.target 2>/dev/null || true
    sudo systemctl stop cuems-node.target 2>/dev/null || true
    echo ""

    echo "L5: Ordering verification"
    systemd-analyze critical-chain cuems-controller.target 2>/dev/null || warn "Could not get critical chain"
    echo ""
fi

# ─── Summary ────────────────────────────────────────────────────────
echo "=== Summary ==="
echo "Failures: $FAILURES"
echo "Warnings: $WARNINGS"

if [ "$FAILURES" -gt 0 ]; then
    echo -e "${RED}FAILED${NC}"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}PASSED with warnings${NC}"
    exit 2
else
    echo -e "${GREEN}ALL PASSED${NC}"
    exit 0
fi
