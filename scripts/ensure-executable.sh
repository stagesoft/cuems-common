#!/bin/bash

# Script to ensure all CUEMS scripts are executable
# This can be run before packaging to verify permissions

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Ensuring CUEMS scripts are executable..."

# Scripts that must be executable
SCRIPTS=(
    "scripts/check-ip.sh"
    "scripts/wifi-auto.sh"
    "usr/bin/cuems-healthcheck"
    "usr/bin/cuems-config-node"
    "scripts/validate-systemd.sh"
    "scripts/verify-package-structure.sh"
    "scripts/test-systemd-units.sh"
)

FIXED=0
ALREADY_EXEC=0

for script in "${SCRIPTS[@]}"; do
    script_path="$PROJECT_ROOT/$script"
    
    if [ ! -f "$script_path" ]; then
        echo -e "${YELLOW}⚠${NC} Script not found: $script"
        continue
    fi
    
    if [ -x "$script_path" ]; then
        echo -e "${GREEN}✓${NC} Already executable: $script"
        ((ALREADY_EXEC++))
    else
        chmod +x "$script_path"
        echo -e "${GREEN}✓${NC} Made executable: $script"
        ((FIXED++))
    fi
done

echo ""
echo "Summary:"
echo "  Already executable: $ALREADY_EXEC"
echo "  Fixed: $FIXED"
echo "  Total: ${#SCRIPTS[@]}"

if [ $FIXED -gt 0 ]; then
    echo ""
    echo "✓ All scripts are now executable"
fi

