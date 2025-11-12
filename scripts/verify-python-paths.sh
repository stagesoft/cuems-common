#!/bin/bash

# Script to verify all systemd units use /usr/lib/cuems/bin/python3

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_DIR="$PROJECT_ROOT/etc/systemd/system"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo "Verifying Python paths in systemd unit files..."
echo ""

for unit_file in "$SYSTEMD_DIR"/*.service; do
    [ -f "$unit_file" ] || continue
    
    unit_name=$(basename "$unit_file")
    
    # Check for Python references
    python_refs=$(grep -E "ExecStart.*python|ExecStartPre.*python|ExecStartPost.*python" "$unit_file" || true)
    
    if [ -z "$python_refs" ]; then
        continue
    fi
    
    # Check each Python reference
    while IFS= read -r line; do
        # Extract the Python path
        python_path=$(echo "$line" | grep -oE "/[^[:space:]]*python[^[:space:]]*" | head -1 || true)
        
        if [ -z "$python_path" ]; then
            continue
        fi
        
        # Check if it's the correct path
        if [[ "$python_path" == "/usr/lib/cuems/bin/python3" ]]; then
            echo -e "${GREEN}✓${NC} $unit_name: Uses correct Python path"
        elif [[ "$python_path" =~ ^/usr/lib/cuems/bin/python3 ]]; then
            echo -e "${GREEN}✓${NC} $unit_name: Uses correct Python path ($python_path)"
        else
            echo -e "${RED}✗${NC} $unit_name: Uses incorrect Python path: $python_path"
            echo "  Should be: /usr/lib/cuems/bin/python3"
            echo "  Line: $line"
            ((ERRORS++))
        fi
    done <<< "$python_refs"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All systemd units use /usr/lib/cuems/bin/python3${NC}"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS unit(s) with incorrect Python paths${NC}"
    exit 1
fi

