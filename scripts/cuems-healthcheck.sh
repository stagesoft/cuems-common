#!/bin/bash

# CUEMS Health Check Script
# This script checks the status of all CUEMS services and logs any issues

LOG_FILE="/var/log/cuems-health.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Function to log messages
log() {
    echo "$TIMESTAMP - $*" | tee -a "$LOG_FILE"
}

# Function to check service status
check_service() {
    local service=$1
    local status

    if systemctl is-active --quiet "$service"; then
        log "✓ $service is running"
        return 0
    else
        log "✗ $service is NOT running"
        return 1
    fi
}

# Function to check network connectivity
check_network() {
    local host=$1
    local description=$2

    if ping -c 1 -W 2 "$host" >/dev/null 2>&1; then
        log "✓ $description ($host) is reachable"
        return 0
    else
        log "✗ $description ($host) is NOT reachable"
        return 1
    fi
}

# Function to check disk space
check_disk_space() {
    local threshold=90
    local usage

    usage=$(df / | awk 'NR==2 {print +$5}')

    if [ "$usage" -lt "$threshold" ]; then
        log "✓ Disk usage is $usage%"
        return 0
    else
        log "✗ Disk usage is $usage% (threshold: $threshold%)"
        return 1
    fi
}

# Main health check
log "=== CUEMS Health Check ==="

# Check CUEMS services
services=("cuems-node.service" "cuems-engine.service" "cuems-xorg.service" "avahi-daemon.service")
service_issues=0

for service in "${services[@]}"; do
    if ! check_service "$service"; then
        ((service_issues++))
    fi
done

# Check network connectivity
network_issues=0

if ! check_network "192.168.3.20" "Relay 1"; then
    ((network_issues++))
fi

if ! check_network "192.168.3.21" "Relay 2"; then
    ((network_issues++))
fi

# Check disk space
if ! check_disk_space; then
    ((disk_issues++))
fi

# Summary
total_issues=$((service_issues + network_issues + disk_issues))

log "=== Health Check Summary ==="
log "Service issues: $service_issues"
log "Network issues: $network_issues"
log "Disk issues: $disk_issues"
log "Total issues: $total_issues"

if [ "$total_issues" -eq 0 ]; then
    log "✓ All systems healthy"
    exit 0
else
    log "✗ Found $total_issues issue(s) - check logs for details"
    exit 1
fi


