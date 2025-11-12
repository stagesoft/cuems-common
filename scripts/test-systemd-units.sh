#!/bin/bash

# Systemd Unit Files Test Script
# This script validates all CUEMS systemd unit files for syntax and configuration issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_DIR="$PROJECT_ROOT/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL=0
PASSED=0
FAILED=0
WARNINGS=0

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    
    case $status in
        PASS)
            echo -e "${GREEN}✓${NC} $message"
            ;;
        FAIL)
            echo -e "${RED}✗${NC} $message"
            ;;
        WARN)
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        INFO)
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
    esac
}

# Function to test a single unit file
test_unit_file() {
    local unit_file=$1
    local unit_name=$(basename "$unit_file")
    local has_errors=false
    local has_warnings=false
    
    ((TOTAL++))
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "INFO" "Testing: $unit_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Test 1: Check if file exists
    if [ ! -f "$unit_file" ]; then
        print_status "FAIL" "File does not exist: $unit_file"
        ((FAILED++))
        return 1
    fi
    
    # Test 2: Validate syntax using systemd-analyze
    if command -v systemd-analyze >/dev/null 2>&1; then
        local verify_output=$(systemd-analyze verify "$unit_file" 2>&1 || true)
        local errors=$(echo "$verify_output" | grep -iE "error|failed|not found|not executable" | grep -v "anydesk\|PIDFile.*legacy" || true)
        
        if [ -n "$errors" ]; then
            print_status "FAIL" "Validation issues found:"
            echo "$errors" | sed 's/^/  /'
            has_errors=true
        else
            print_status "PASS" "Syntax validation passed"
        fi
        
        # Check for warnings (non-critical issues)
        local warnings=$(echo "$verify_output" | grep -i "warning" | grep -v "anydesk\|PIDFile.*legacy" || true)
        if [ -n "$warnings" ]; then
            print_status "WARN" "Warnings found:"
            echo "$warnings" | sed 's/^/  /'
            has_warnings=true
        fi
    else
        print_status "WARN" "systemd-analyze not available, skipping syntax check"
        has_warnings=true
    fi
    
    # Test 3: Check for common issues
    check_unit_issues "$unit_file" "$unit_name"
    
    # Test 4: Validate unit file structure
    validate_unit_structure "$unit_file" "$unit_name"
    
    # Test 5: Check dependencies
    check_dependencies "$unit_file" "$unit_name"
    
    # Summary for this unit
    if [ "$has_errors" = true ]; then
        ((FAILED++))
        return 1
    elif [ "$has_warnings" = true ]; then
        ((WARNINGS++))
    else
        ((PASSED++))
    fi
    
    return 0
}

# Function to check for common issues
check_unit_issues() {
    local unit_file=$1
    local unit_name=$2
    
    # Check for missing ExecStart in service files
    if [[ "$unit_name" == *.service ]]; then
        if grep -q "^\[Service\]" "$unit_file" && ! grep -q "^ExecStart=" "$unit_file" && ! grep -q "^Type=oneshot" "$unit_file"; then
            print_status "FAIL" "Service file missing ExecStart directive"
        fi
        
        # Check for Type=exec with PIDFile
        if grep -q "^Type=exec" "$unit_file"; then
            if ! grep -q "^PIDFile=" "$unit_file"; then
                print_status "WARN" "Type=exec requires PIDFile directive"
            fi
        fi
        
        # Check for Restart without RestartSec
        if grep -q "^Restart=" "$unit_file" && ! grep -q "^RestartSec=" "$unit_file"; then
            print_status "WARN" "Restart directive without RestartSec (defaults to 100ms)"
        fi
        
        # Check for hardcoded user paths
        if grep -q "/home/" "$unit_file"; then
            print_status "WARN" "Hardcoded user home directory found (may break on different systems)"
        fi
        
        # Check for non-existent executables
        if grep -q "^ExecStart=" "$unit_file" || grep -q "^ExecStartPre=" "$unit_file" || grep -q "^ExecStartPost=" "$unit_file" || grep -q "^ExecCondition=" "$unit_file"; then
            local exec_lines=$(grep -E "^Exec(Start|Condition)=" "$unit_file" || true)
            while IFS= read -r line; do
                local cmd=$(echo "$line" | cut -d'=' -f2- | awk '{print $1}' | sed 's/@.*//')
                # Skip if it's a systemd specifier
                if [[ ! "$cmd" =~ ^[@%\$] ]] && [[ "$cmd" =~ ^/ ]]; then
                    if [ ! -f "$cmd" ] && [ ! -x "$cmd" ] 2>/dev/null; then
                        # Check if it's a standard system command
                        if ! command -v "$(basename "$cmd")" >/dev/null 2>&1; then
                            print_status "WARN" "Executable may not exist: $cmd"
                        fi
                    fi
                fi
            done <<< "$exec_lines"
        fi
    fi
    
    # Check for absolute paths in ExecStart
    if grep -q "^ExecStart=" "$unit_file"; then
        local exec_start=$(grep "^ExecStart=" "$unit_file" | head -1 | cut -d'=' -f2- | awk '{print $1}')
        if [[ ! "$exec_start" =~ ^/ ]] && [[ ! "$exec_start" =~ ^@ ]] && [[ ! "$exec_start" =~ ^% ]]; then
            print_status "WARN" "ExecStart should use absolute path: $exec_start"
        fi
    fi
}

# Function to validate unit file structure
validate_unit_structure() {
    local unit_file=$1
    local unit_name=$2
    
    # Check for required sections
    if [[ "$unit_name" == *.service ]]; then
        if ! grep -q "^\[Unit\]" "$unit_file"; then
            print_status "FAIL" "Missing [Unit] section"
        fi
        if ! grep -q "^\[Service\]" "$unit_file"; then
            print_status "FAIL" "Missing [Service] section"
        fi
    elif [[ "$unit_name" == *.path ]]; then
        if ! grep -q "^\[Unit\]" "$unit_file"; then
            print_status "FAIL" "Missing [Unit] section"
        fi
        if ! grep -q "^\[Path\]" "$unit_file"; then
            print_status "FAIL" "Missing [Path] section"
        fi
    fi
    
    # Check section order (Unit should come first)
    local unit_line=$(grep -n "^\[Unit\]" "$unit_file" | head -1 | cut -d: -f1 || echo "999")
    local service_line=$(grep -n "^\[Service\]" "$unit_file" | head -1 | cut -d: -f1 || echo "999")
    
    if [ "$service_line" -lt "$unit_line" ] && [ "$service_line" -ne "999" ]; then
        print_status "WARN" "[Unit] section should come before [Service] section"
    fi
}

# Function to check dependencies
check_dependencies() {
    local unit_file=$1
    local unit_name=$2
    
    # Extract Requires and Wants dependencies
    local requires=$(grep "^Requires=" "$unit_file" | cut -d'=' -f2- | tr ' ' '\n' | grep -v '^$' || true)
    local wants=$(grep "^Wants=" "$unit_file" | cut -d'=' -f2- | tr ' ' '\n' | grep -v '^$' || true)
    
    # Check if required services exist
    for dep in $requires; do
        if [[ "$dep" == *.service ]] || [[ "$dep" == *.target ]]; then
            if [ ! -f "$SYSTEMD_DIR/$dep" ] && [ ! -f "/etc/systemd/system/$dep" ] && [ ! -f "/usr/lib/systemd/system/$dep" ]; then
                print_status "WARN" "Required dependency may not exist: $dep"
            fi
        fi
    done
    
    # Check for circular dependencies (basic check)
    if grep -q "PartOf=cuems-node.service" "$unit_file" && [[ "$unit_name" == "cuems-node.service" ]]; then
        print_status "WARN" "Potential circular dependency: PartOf=cuems-node.service in cuems-node.service"
    fi
}

# Main execution
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    CUEMS Systemd Unit Files Test Suite                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
print_status "INFO" "Testing systemd unit files in: $SYSTEMD_DIR"
echo ""

# Find all unit files
if [ ! -d "$SYSTEMD_DIR" ]; then
    print_status "FAIL" "Systemd directory not found: $SYSTEMD_DIR"
    exit 1
fi

UNIT_FILES=$(find "$SYSTEMD_DIR" -maxdepth 1 -type f \( -name "*.service" -o -name "*.path" -o -name "*.socket" -o -name "*.timer" \) 2>/dev/null | sort)

if [ -z "$UNIT_FILES" ]; then
    print_status "FAIL" "No unit files found in $SYSTEMD_DIR"
    exit 1
fi

# Test each unit file
for unit_file in $UNIT_FILES; do
    test_unit_file "$unit_file"
done

# Final summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                              Test Summary                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Total units tested:  $TOTAL"
echo -e "  ${GREEN}Passed:${NC}            $PASSED"
echo -e "  ${YELLOW}Warnings:${NC}         $WARNINGS"
echo -e "  ${RED}Failed:${NC}            $FAILED"
echo ""

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    print_status "PASS" "All unit files passed validation!"
    exit 0
elif [ $FAILED -eq 0 ]; then
    print_status "WARN" "All unit files passed, but some warnings were found"
    exit 0
else
    print_status "FAIL" "Some unit files failed validation"
    exit 1
fi
