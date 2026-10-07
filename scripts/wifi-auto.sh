#!/bin/bash
# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
#
# Switch this host's WiFi from AP mode (broadcasting our own SSID via
# hostapd) to client mode (joining an external WiFi via the `wifi-out`
# stanza in /etc/network/interfaces). Operator-invoked; the controller's
# AP is the default and stays up unless explicitly torn down.
#
# Steps:
#   1. Stop isc-dhcp-server (we're no longer the DHCP source).
#   2. Bring the WLAN interface down via ifdown.
#   3. Bring it back up under the `wifi-out` logical name, which
#      activates wpa_supplicant per the stanza's wpa-ssid/wpa-psk.
#
# The script bails BEFORE touching anything if either prerequisite is
# missing (no WLAN interface; no `wifi-out` stanza), so a misfire on a
# controller with no client-mode config doesn't leave dhcpd stopped.

set -eu

# Detect the WLAN interface dynamically. Hardcoded `wlo2` rotted across
# kernel/udev naming generations (this hardware now exposes `wifi0`).
wlan=$(ip -br link show type wlan 2>/dev/null | awk 'NR==1 {print $1}')
if [ -z "$wlan" ]; then
    echo "wifi-auto: no wireless interface found (ip -br link show type wlan)" >&2
    exit 1
fi

# Pre-flight: the wifi-out stanza must exist somewhere under /etc/network/.
# grep -qr handles an empty /etc/network/interfaces.d/ correctly; a plain
# glob would error with "no matches".
if ! grep -qr '^iface wifi-out' /etc/network/ 2>/dev/null; then
    echo "wifi-auto: 'iface wifi-out' stanza not found under /etc/network/" >&2
    echo "wifi-auto: see /usr/share/cuems/interfaces.node for the reference stanza" >&2
    exit 1
fi

systemctl stop isc-dhcp-server
ifdown "$wlan"
ifup "${wlan}=wifi-out"
