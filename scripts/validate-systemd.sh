#!/bin/bash

# Quick Systemd Unit Files Validation Script

SYSTEMD_DIR="$(cd "$(dirname "$0")/.." && pwd)/etc/systemd/system"
REPORT_FILE="/tmp/cuems-systemd-validation-$(date +%Y%m%d-%H%M%S).txt"

echo "CUEMS Systemd Unit Files Validation Report" > "$REPORT_FILE"
echo "Generated: $(date)" >> "$REPORT_FILE"
echo "==========================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find and test all unit files
shopt -s nullglob
for unit_file in "$SYSTEMD_DIR"/*.service "$SYSTEMD_DIR"/*.path "$SYSTEMD_DIR"/*.socket "$SYSTEMD_DIR"/*.timer; do
    [ -f "$unit_file" ] || continue
    
    unit_name=$(basename "$unit_file")
    echo "Testing: $unit_name"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
    echo "Unit: $unit_name" >> "$REPORT_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
    
    # Run systemd-analyze verify
    if command -v systemd-analyze >/dev/null 2>&1; then
        verify_output=$(systemd-analyze verify "$unit_file" 2>&1 || true)
        
        # Filter out unrelated warnings
        filtered_output=$(echo "$verify_output" | grep -v "anydesk\|PIDFile.*legacy" || true)
        
        if [ -n "$filtered_output" ]; then
            echo "$filtered_output" >> "$REPORT_FILE"
        else
            echo "✓ Validation passed" >> "$REPORT_FILE"
        fi
    else
        echo "⚠ systemd-analyze not available" >> "$REPORT_FILE"
    fi
    
    echo "" >> "$REPORT_FILE"
done

echo ""
echo "Report saved to: $REPORT_FILE"
cat "$REPORT_FILE"

