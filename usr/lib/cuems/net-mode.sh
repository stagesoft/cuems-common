# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
#
# Shared state readers for the controller network modes (1.3.0-23).
# Sourced, never executed, by check-ip.sh, cuems-ap-path, cuems-net-guard,
# cuems-net-mode and the dhclient exit hook.
#
# The exit hook is sourced INSIDE /sbin/dhclient-script, which runs under dash
# and shares one namespace with the chrony, timesyncd, rfc3442 and avahi hooks.
# That is what dictates the rules of this file:
#   - POSIX sh only (plus `local`, which dash has and dhclient-script uses);
#   - no `set -e`, no `set -u`, never `exit`;
#   - every function and every global is prefixed `cuems_`;
#   - config files are PARSED, not sourced: sourcing /etc/cuems/ap.conf would
#     drop AP_GATEWAY & co. into dhclient-script's namespace.
#
# One definition of each notion lives here so the gates, the hook and the guard
# cannot drift apart: "controller", "routable IPv4", "who carries the gateway".

cuems_net_mode_conf="${CUEMS_NET_MODE_CONF:-/etc/cuems/net-mode.conf}"
cuems_net_ap_conf="${CUEMS_AP_CONF:-/etc/cuems/ap.conf}"

# cuems_net_conf_get FILE KEY -> value of the last KEY= line, unquoted.
cuems_net_conf_get() {
    [ -r "$1" ] || return 0
    sed -n "s/^[[:space:]]*$2=//p" "$1" 2>/dev/null | tail -n 1 | sed \
        -e 's/[[:space:]]*#.*$//' \
        -e 's/[[:space:]]*$//' \
        -e 's/^"\(.*\)"$/\1/' \
        -e "s/^'\(.*\)'\$/\1/"
}

# A controller, for everything in this feature, is a host that has BOTH the
# role marker and the bond. A demoted controller that kept interfaces.master
# has bond0 but no master.ip; a node promoted by hand may have master.ip and
# no bond. Neither is acted on.
cuems_net_is_controller() {
    [ -f /etc/cuems/master.ip ] && [ -d /sys/class/net/bond0 ]
}

# Loads cuems_net_gw / cuems_net_prefix / cuems_net_subnet from ap.conf and
# cuems_net_mode / cuems_net_armed / cuems_net_static from net-mode.conf.
# Returns 1 when ap.conf is missing or carries no gateway: the caller cannot
# evaluate anything then.
#
# A missing net-mode.conf, or a NET_MODE this version does not know, is
# `manual`. That is the rule that makes a file-copy deploy (no postinst, so no
# net-mode.conf) inert, and a typo fail towards "leave the site alone".
cuems_net_load() {
    cuems_net_gw=$(cuems_net_conf_get "$cuems_net_ap_conf" AP_GATEWAY)
    cuems_net_subnet=$(cuems_net_conf_get "$cuems_net_ap_conf" AP_SUBNET)
    cuems_net_prefix="${cuems_net_subnet##*/}"
    case "$cuems_net_prefix" in
        ''|*[!0-9]*) cuems_net_prefix=24 ;;
    esac

    cuems_net_mode=$(cuems_net_conf_get "$cuems_net_mode_conf" NET_MODE)
    case "$cuems_net_mode" in
        auto|cable-dhcp|cable-static|ap|manual) ;;
        *) cuems_net_mode=manual ;;
    esac
    cuems_net_armed=$(cuems_net_conf_get "$cuems_net_mode_conf" AP_ARMED)
    [ "$cuems_net_armed" = yes ] || cuems_net_armed=no
    cuems_net_static=$(cuems_net_conf_get "$cuems_net_mode_conf" CABLE_STATIC_ADDR)
    [ -n "$cuems_net_static" ] || cuems_net_static="${cuems_net_gw}/${cuems_net_prefix}"

    [ -n "$cuems_net_gw" ] && [ -n "$cuems_net_subnet" ]
}

# The modes in which bond0 is meant to run a DHCP client.
cuems_net_mode_wants_client() {
    case "$cuems_net_mode" in
        auto|cable-dhcp|ap) return 0 ;;
    esac
    return 1
}

# cuems_net_routable IFACE -> its IPv4 addresses, one per line, link-local
# (169.254/16) excluded. avahi-autoipd puts a 169.254.x on bond0 next to the
# fallback; comparing the WHOLE address list to the gateway, as check-ip.sh did
# until 1.3.0-22, made that transient fail the AP gate closed.
cuems_net_routable() {
    ip -4 -o addr show dev "$1" 2>/dev/null | awk '{
        split($4, a, "/")
        if (a[1] !~ /^169\.254\./) print a[1]
    }'
}

# cuems_net_has IFACE ADDR -> 0 when IFACE carries exactly that IPv4.
cuems_net_has() {
    cuems_net_routable "$1" | grep -qxF "$2"
}

# cuems_net_only_gw IFACE -> 0 when the routable set of IFACE is exactly
# { gateway }.
cuems_net_only_gw() {
    [ "$(cuems_net_routable "$1" | sort -u)" = "$cuems_net_gw" ]
}

# cuems_net_gw_elsewhere IFACE -> names of the interfaces OTHER than IFACE
# that carry the gateway address.
cuems_net_gw_elsewhere() {
    ip -4 -o addr show 2>/dev/null | awk -v skip="$1" -v gw="$cuems_net_gw" '{
        split($4, a, "/")
        if ($2 != skip && a[1] == gw) print $2
    }' | sort -u
}

# cuems_net_carrier IFACE -> yes | no | unknown.
# Reading `carrier` on an administratively-down interface returns EINVAL; that
# is a cable nobody can use, hence `no`. `unknown` is a missing interface.
cuems_net_carrier() {
    [ -d "/sys/class/net/$1" ] || { echo unknown; return 0; }
    if [ "$(cat "/sys/class/net/$1/carrier" 2>/dev/null)" = 1 ]; then
        echo yes
    else
        echo no
    fi
}

# cuems_net_enslaved IFACE -> 0 when IFACE is a slave of some master.
cuems_net_enslaved() {
    [ -e "/sys/class/net/$1/master" ]
}
