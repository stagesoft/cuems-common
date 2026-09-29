#!/bin/bash
# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
#
# The three gates of the controller's standalone WiFi AP, one per unit:
#
#   check-ip.sh ap       ExecCondition of cuems-wifi.service (the default,
#                        so the pre-1.3.0-23 call without arguments still works)
#   check-ip.sh hostapd  ExecCondition of hostapd.service
#   check-ip.sh dhcpd    ExecCondition of isc-dhcp-server.service
#
# Exit codes, as systemd reads an ExecCondition:
#   0    proceed
#   1    skip quietly — the unit ends inactive, NOT failed
#   255  cannot evaluate — the unit ends failed. Only when /etc/cuems/ap.conf
#        is missing or has no gateway: that is a broken install, and a broken
#        install must be visible. NOT in NET_MODE=manual: the dhcpd drop-in is
#        shadowed by no site, so this gate also runs where the site manages
#        its own AP, and a site's ap.conf is none of this script's business.
#
# Until 1.3.0-22 only hostapd was behind a gate. isc-dhcp-server's single gate
# was dhcpd.conf's subnet match, which opens exactly when bond0 takes the
# fallback address — so a controller that booted before its router served
# 192.168.6.0/24 on the WIRED venue LAN (taller, 2026-09-29). The dhcpd gate
# below is what closes that: it refuses, whatever the mode, to serve on bond0.
set -u

# shellcheck source=usr/lib/cuems/net-mode.sh
. /usr/lib/cuems/net-mode.sh

gate="${1:-ap}"

# cuems_net_load sets the mode even when ap.conf cannot be read.
conf_ok=yes
cuems_net_load || conf_ok=no

# NET_MODE=manual, which is also a missing net-mode.conf and an unknown value:
# every gate behaves as the units did before 1.3.0-23.
gate_manual() {
    case "$gate" in
        dhcpd)
            return 0
            ;;
        hostapd)
            # What `Requisite=cuems-wifi.service` used to enforce. Without it,
            # removing that Requisite= would put hostapd — and the default
            # passphrase — on the air at every boot of a manual controller
            # that does not shadow cuems-wifi-group.conf. After= guarantees
            # the service's job has finished by the time this runs.
            timeout 10 systemctl is-active --quiet cuems-wifi.service
            return
            ;;
    esac
    return 1
}

gate_ap() {
    cuems_net_is_controller || return 1
    [ "$cuems_net_armed" = yes ] || return 1
    [ -d /sys/class/net/wifi0 ] || return 1
    case "$cuems_net_mode" in
        ap)
            return 0
            ;;
        auto)
            # The fallback address AND no cable. Either alone is not enough: the
            # fallback with a cable is a wired LAN whose DHCP server is late or
            # absent, which must never grow an AP or a DHCP server.
            cuems_net_only_gw bond0 || return 1
            [ "$(cuems_net_carrier ethernet0)" = no ] || return 1
            return 0
            ;;
    esac
    # cable-dhcp, cable-static
    return 1
}

gate_hostapd() {
    # Address first, then dhcpd, then hostapd: hostapd only ever starts on a
    # wifi0 that cuems-ap-path has already given the gateway address.
    cuems_net_has wifi0 "$cuems_net_gw"
}

gate_dhcpd() {
    local ifaces iface serving=""

    case "$cuems_net_mode" in
        cable-dhcp|cable-static) return 1 ;;
    esac

    # The interfaces dhcpd would be started on: INTERFACESv4, where empty
    # means every interface.
    ifaces=$(cuems_net_conf_get /etc/default/isc-dhcp-server INTERFACESv4)
    if [ -z "$ifaces" ]; then
        ifaces=$(ip -4 -o addr show 2>/dev/null | awk '$2 != "lo" {print $2}' | sort -u)
    fi

    # Of those, the ones it would actually serve: dhcpd.conf declares the AP
    # subnet only, so an interface is served iff it has an address inside it.
    for iface in $ifaces; do
        if [ -n "$(ip -4 -o addr show dev "$iface" to "$cuems_net_subnet" 2>/dev/null)" ]; then
            serving="$serving $iface"
        fi
    done

    case " $serving " in
        *" bond0 "*)
            echo "check-ip.sh: refusing to serve DHCP on bond0" >&2
            return 1
            ;;
    esac
    [ -n "$serving" ]
}

case "$gate" in
    ap|hostapd|dhcpd) ;;
    *)
        echo "check-ip.sh: unknown gate '$gate' (ap|hostapd|dhcpd)" >&2
        exit 255
        ;;
esac

if [ "$cuems_net_mode" = manual ]; then
    gate_manual && exit 0
    exit 1
fi
if [ "$conf_ok" = no ]; then
    echo "check-ip.sh: $cuems_net_ap_conf is missing or has no AP_GATEWAY/AP_SUBNET" >&2
    exit 255
fi

case "$gate" in
    ap)      gate_ap ;;
    hostapd) gate_hostapd ;;
    dhcpd)   gate_dhcpd ;;
esac
# Anything but 0 is a skip. Never let a helper's own exit status leak a 255.
# shellcheck disable=SC2181
[ $? -eq 0 ] && exit 0
exit 1
