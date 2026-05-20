#!/bin/bash
# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
#
# ExecCondition for cuems-wifi.service. Decides whether the controller
# should bring up its fallback WiFi AP.
#
# Returns 0 (proceed -> start AP) ONLY when both:
#   - bond0 carries the fallback static IP ($AP_GATEWAY from ap.conf)
#     i.e. no upstream DHCP server replied, dhclient fell back to the
#     hardcoded lease
#   - ethernet0 has no cable carrier
#
# Returns 1 in every other state (cluster-connected, partial setup,
# bond0 still acquiring an address, etc). systemd ExecCondition treats
# exit codes 1..254 as "skip silently" — 255 used to be hardcoded here
# for the "bond0 has no IP yet" branch and made systemd report the unit
# as failed at boot instead of silently inactive.
set -eu

if [ ! -f /etc/cuems/ap.conf ]; then
    echo "check-ip.sh: /etc/cuems/ap.conf is required" >&2
    exit 1
fi
# shellcheck source=/etc/cuems/ap.conf
. /etc/cuems/ap.conf

ip=$(ip -4 addr show bond0 | grep -oP "(?<=inet ).*(?=/)" || true)
ethernet0_connected=$(ethtool ethernet0 | grep -oP "(?<=Link detected: )(.*)" || true)

if [[ -n "$ip" ]]; then
    if [[ "$ip" == "$AP_GATEWAY" ]]; then
        if [[ "$ethernet0_connected" == "no" ]]; then
            exit 0
        else
            exit 1
        fi
    else
        exit 1
    fi
else
    exit 1   # was 255; condition-skip, not failure
fi
