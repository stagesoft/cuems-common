#!/bin/bash

# CUEMS Debian Package Structure Verification Script
# This script verifies that all files referenced in systemd units
# will exist after package installation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_DIR="$PROJECT_ROOT/etc/systemd/system"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Track missing files
MISSING_FILES=()
MISSING_DIRS=()
WARNINGS=()

print_status() {
    local status=$1
    local message=$2
    
    case $status in
        PASS) echo -e "${GREEN}✓${NC} $message" ;;
        FAIL) echo -e "${RED}✗${NC} $message" ;;
        WARN) echo -e "${YELLOW}⚠${NC} $message" ;;
        INFO) echo -e "${BLUE}ℹ${NC} $message" ;;
    esac
}

# Extract file paths from systemd unit files
extract_file_paths() {
    local unit_file=$1
    local paths=()
    
    # Extract ExecStart, ExecStartPre, ExecStartPost, ExecCondition paths
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        
        # Extract file path (first argument after =)
        if [[ "$line" =~ ^Exec(Start|Condition|Reload)= ]]; then
            local cmd=$(echo "$line" | cut -d'=' -f2- | awk '{print $1}')
            
            # Skip systemd specifiers and built-in commands
            [[ "$cmd" =~ ^[@%\$] ]] && continue
            [[ "$cmd" == "/bin/true" ]] && continue
            [[ "$cmd" == "/bin/bash" ]] && continue
            [[ "$cmd" == "/bin/sleep" ]] && continue
            [[ "$cmd" == "/bin/mkdir" ]] && continue
            
            # Extract actual file path
            if [[ "$cmd" =~ ^/ ]]; then
                # Remove arguments and get just the path
                local path=$(echo "$cmd" | cut -d' ' -f1)
                paths+=("$path")
            fi
        fi
    done < "$unit_file"
    
    printf '%s\n' "${paths[@]}"
}

# Check if file should exist in package
check_package_file() {
    local file_path=$1
    local unit_name=$2
    
    # Skip system files that come from other packages
    case "$file_path" in
        /usr/bin/xinit|/usr/bin/X|/usr/bin/rsync|/usr/sbin/hostapd|/usr/sbin/ip|/bin/kwin_wayland)
            return 0  # These come from system packages
            ;;
        /usr/bin/python3|/usr/bin/python3.7|/usr/bin/python3.*)
            return 0  # Python comes from system
            ;;
        /etc/X11/xinit/xinitrc.cuems)
            # Check if exists in package structure
            if [ -f "$PROJECT_ROOT/etc/X11/xinit/xinitrc.cuems" ]; then
                return 0
            fi
            ;;
        /usr/lib/cuems/*)
            # CUEMS-specific files - must exist in package
            local rel_path="${file_path#/usr/lib/cuems/}"
            # Special case: python3 in bin/ is likely a symlink or wrapper, not a package file
            if [[ "$rel_path" == "bin/python3" ]]; then
                print_status "WARN" "Python wrapper expected at runtime: $file_path in $unit_name"
                WARNINGS+=("Python wrapper: $file_path in $unit_name")
                return 0
            fi
            # Check if file exists in scripts/ directory (will be installed to /usr/lib/cuems/bin/)
            if [[ "$rel_path" == "bin/"* ]]; then
                local script_name="${rel_path#bin/}"
                if [ -f "$PROJECT_ROOT/scripts/$script_name" ]; then
                    print_status "PASS" "Found $script_name in scripts/ (will install to $file_path)"
                    return 0
                fi
            fi
            # Check if file exists in package structure
            if [ -f "$PROJECT_ROOT/scripts/$rel_path" ] || [ -f "$PROJECT_ROOT/usr/lib/cuems/$rel_path" ]; then
                return 0
            fi
            ;;
        /usr/local/bin/*)
            # Check if exists in package structure
            local rel_path="${file_path#/usr/local/bin/}"
            if [ -f "$PROJECT_ROOT/scripts/$rel_path" ] || [ -f "$PROJECT_ROOT/usr/local/bin/$rel_path" ]; then
                return 0
            fi
            ;;
        /home/*)
            # User home directories - these are runtime paths, not package paths
            print_status "WARN" "Runtime path (not package file): $file_path in $unit_name"
            WARNINGS+=("Runtime path: $file_path in $unit_name")
            return 0
            ;;
    esac
    
    # Check if it's a directory that needs to exist
    if [[ "$file_path" =~ /run/ ]] || [[ "$file_path" =~ /var/ ]]; then
        return 0  # Runtime directories
    fi
    
    return 1
}

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║              CUEMS Package Structure Verification                            ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Process all systemd unit files
shopt -s nullglob
for unit_file in "$SYSTEMD_DIR"/*.service "$SYSTEMD_DIR"/*.path; do
    [ -f "$unit_file" ] || continue
    
    unit_name=$(basename "$unit_file")
    print_status "INFO" "Checking: $unit_name"
    
    # Extract file paths
    while IFS= read -r file_path; do
        [ -z "$file_path" ] && continue
        
        if ! check_package_file "$file_path" "$unit_name"; then
            MISSING_FILES+=("$file_path (referenced in $unit_name)")
            print_status "FAIL" "Missing package file: $file_path"
        fi
    done < <(extract_file_paths "$unit_file")
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check for required CUEMS package files
print_status "INFO" "Verifying CUEMS package files..."

# check-ip.sh should be installed to /usr/lib/cuems/bin/check-ip.sh
if [ -f "$PROJECT_ROOT/scripts/check-ip.sh" ]; then
    print_status "PASS" "check-ip.sh exists in scripts/ (should install to /usr/lib/cuems/bin/)"
else
    MISSING_FILES+=("scripts/check-ip.sh (should install to /usr/lib/cuems/bin/check-ip.sh)")
    print_status "FAIL" "check-ip.sh not found in scripts/"
fi

# Check for other scripts that might need to be installed
if [ -f "$PROJECT_ROOT/scripts/wifi-auto.sh" ]; then
    print_status "PASS" "wifi-auto.sh exists in scripts/"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                              Summary                                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

if [ ${#MISSING_FILES[@]} -eq 0 ] && [ ${#WARNINGS[@]} -eq 0 ]; then
    print_status "PASS" "All package files verified!"
    exit 0
elif [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_status "WARN" "Package structure OK, but some warnings found"
    exit 0
else
    print_status "FAIL" "Missing files found:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi

