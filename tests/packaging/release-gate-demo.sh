#!/bin/bash
# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
#
# release-gate-demo.sh — watch dpkg/apt refuse out-of-order CUEMS installs (feature 001, T027/T028).
#
# A gate nobody has watched refuse is a claim (constitution IV). This builds the
# real cuems-common package from the working tree and from the previous release,
# builds equivs STUBS for its counterparts at exact versions, and replays install
# scenarios inside an unprivileged, disposable bookworm system:
#
#   mmdebstrap --mode=unshare  — a user-namespace chroot built as the calling user.
#   Nothing runs as real root, postinst's systemctl/invoke-rc.d calls cannot reach
#   host services, and the /dev/null target leaves nothing behind.
#
# Only the RELATIONSHIPS are under test: the counterparts are stubs (a real
# cuems-utils >= 0.1.0rc16 .deb does not exist yet). Each refusal is apt/dpkg
# refusing the real cuems-common package. The evidence file says so.
#
# Usage:  tests/packaging/release-gate-demo.sh
# Env:    WORK=<dir>     build/scratch directory (default: a new mktemp dir)
#         OUT=<file>     evidence file (default: the feature's evidence/ file)
#         OLD_REF=<ref>  git ref of the previous release (default: rc_1, 1.3.0-22)
#         MIRROR=<url>   Debian mirror (default: http://deb.debian.org/debian)
# Needs:  mmdebstrap, uidmap (newuidmap/newgidmap), equivs, dpkg-dev, debhelper,
#         fakeroot; /etc/subuid and /etc/subgid ranges for the calling user;
#         network access to the mirror.
# Exit:   0 if every scenario's observed outcome matches its expectation.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
FEATURE="$REPO/specs/001-node-role-and-conversion-ordering"
WORK="${WORK:-$(mktemp -d -t cuems-release-gate-XXXXXX)}"
OUT="${OUT:-$FEATURE/evidence/out-of-order-refusal.txt}"
OLD_REF="${OLD_REF:-rc_1}"
MIRROR="${MIRROR:-http://deb.debian.org/debian}"

UTILS_VERSIONS=(0.1.0rc14 0.1.0rc15 0.1.0rc16 0.1.1~rc1)
NODECONF_VERSIONS=(0.1.0-7 0.1.0-8)

log() { printf '[release-gate] %s\n' "$*" >&2; }

for tool in mmdebstrap equivs-build dpkg-buildpackage dpkg-parsechangelog newuidmap newgidmap fakeroot; do
    command -v "$tool" >/dev/null 2>&1 || { log "missing required tool: $tool"; exit 2; }
done
grep -q "^$(id -un):" /etc/subuid && grep -q "^$(id -un):" /etc/subgid \
    || { log "no /etc/subuid or /etc/subgid range for $(id -un)"; exit 2; }

mkdir -p "$WORK"/{new/src,old/src,stubs,debs}
log "work directory: $WORK"

# --- 1. the real cuems-common, from the working tree -------------------------
log "building cuems-common from the working tree"
git -C "$REPO" ls-files -co --exclude-standard -z \
    | tar -C "$REPO" --null -T - -cf - | tar -C "$WORK/new/src" -xf -
NEW_VERSION="$(cd "$WORK/new/src" && dpkg-parsechangelog -SVersion)+gatedemo1"
{
    printf 'cuems-common (%s) UNRELEASED; urgency=low\n\n' "$NEW_VERSION"
    printf '  * Release-gate demonstration build (tests/packaging/release-gate-demo.sh).\n'
    printf '    Not a release.\n\n'
    printf ' -- CUEMS release-gate demonstration <noreply@stagelab.coop>  %s\n\n' "$(date -R)"
    cat "$WORK/new/src/debian/changelog"
} > "$WORK/new/changelog" && mv "$WORK/new/changelog" "$WORK/new/src/debian/changelog"
(cd "$WORK/new/src" && dpkg-buildpackage -b -us -uc -rfakeroot) > "$WORK/new/build.log" 2>&1 \
    || { log "new build failed — see $WORK/new/build.log"; exit 1; }
cp "$WORK"/new/cuems-common_*_all.deb "$WORK/debs/cuems-common_new.deb"

# --- 2. the previous release, unmodified -------------------------------------
log "building cuems-common from $OLD_REF"
git -C "$REPO" archive "$OLD_REF" | tar -C "$WORK/old/src" -xf -
OLD_VERSION="$(cd "$WORK/old/src" && dpkg-parsechangelog -SVersion)"
(cd "$WORK/old/src" && dpkg-buildpackage -b -us -uc -rfakeroot) > "$WORK/old/build.log" 2>&1 \
    || { log "old build failed — see $WORK/old/build.log"; exit 1; }
cp "$WORK"/old/cuems-common_*_all.deb "$WORK/debs/cuems-common_old.deb"

# --- 3. stubs ----------------------------------------------------------------
build_stub() { # package version
    local ctl="$WORK/stubs/$1_$2.ctl"
    sed "s/@VERSION@/$2/" "$REPO/tests/packaging/stubs/$1.ctl" > "$ctl"
    (cd "$WORK/stubs" && equivs-build "$ctl") > "$WORK/stubs/$1_$2.log" 2>&1
    cp "$WORK/stubs/$1_$2_all.deb" "$WORK/debs/$1_$2.deb"
}
for v in "${UTILS_VERSIONS[@]}"; do log "stub cuems-utils $v"; build_stub cuems-utils "$v"; done
for v in "${NODECONF_VERSIONS[@]}"; do log "stub cuems-nodeconf $v"; build_stub cuems-nodeconf "$v"; done

# --- 4. the scenarios, run inside the disposable system ----------------------
cat > "$WORK/debs/scenarios.sh" <<'SCENARIOS'
#!/bin/sh
# Runs inside the mmdebstrap chroot. Never exits non-zero: a failed hook would
# abort mmdebstrap and lose the transcript, and verdicts are compared outside.
G=/tmp/gate/debs
T=/tmp/gate/transcript.txt
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y --no-remove -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
: > "$T"

# No daemon may start in here: this user-namespace system shares the host's
# network, and avahi-daemon on unprivileged UDP 5353 would announce on the real
# LAN. mmdebstrap already replaces policy-rc.d while hooks run; assert it rather
# than assume it, and refuse to run any scenario if it is not so.
if [ -x /usr/sbin/policy-rc.d ]; then
    /usr/sbin/policy-rc.d avahi-daemon start; guard_rc=$?
else
    guard_rc=missing
fi
if [ "$guard_rc" != 101 ]; then
    echo "ABORT: /usr/sbin/policy-rc.d does not deny service starts (exit 101); no scenario was run" >> "$T"
    echo "VERDICT GUARD expected=ACCEPTED observed=ABORTED" >> "$T"
    exit 0
fi
echo "guard: /usr/sbin/policy-rc.d denies service starts (exit 101)" >> "$T"

attempt() { # id expected(ACCEPTED|REFUSED) title -- command...
    id=$1; expected=$2; title=$3; shift 4
    {
        echo
        echo "=== $id — $title"
        echo "expected: $expected"
        echo "\$ $*"
    } >> "$T"
    "$@" > /tmp/gate/cmd.log 2>&1
    rc=$?
    # A relationship refusal happens before anything is unpacked. A failure after
    # unpacking (a maintainer script erroring) is NOT a refusal and is classed apart.
    if [ "$rc" -eq 0 ]; then observed=ACCEPTED; tail -n 15 /tmp/gate/cmd.log >> "$T"
    elif grep -qE "installed .* script subprocess returned error|Sub-process /usr/bin/dpkg returned an error|dpkg: error processing package" /tmp/gate/cmd.log; then
        observed=CONFIGURE-FAILED; tail -n 40 /tmp/gate/cmd.log >> "$T"
    else observed=REFUSED; grep -vE "^(Reading|Building|Get:|Fetched|Selecting|Preparing|Unpacking|Setting up|Processing)" /tmp/gate/cmd.log | tail -n 30 >> "$T"; fi
    echo "exit: $rc — observed: $observed" >> "$T"
    echo "VERDICT $id expected=$expected observed=$observed" >> "$T"
}

state() { # label -- command...
    label=$1; shift 2
    { echo "--- $label"; echo "\$ $*"; "$@" 2>&1; echo; } >> "$T"
}

versions() {
    dpkg-query -W -f='${Package} ${Version} ${db:Status-Abbrev}\n' cuems-common cuems-utils cuems-nodeconf 2>&1 || true
}

# Library floor and ceiling (FR-016, FR-016a): the host's cuems-utils is set,
# then the real new cuems-common is attempted beside it.
$APT --allow-downgrades install $G/cuems-utils_0.1.0rc14.deb > /dev/null 2>&1
attempt A1 REFUSED "new cuems-common beside cuems-utils 0.1.0rc14 (newest published; below the floor)" -- \
    $APT install $G/cuems-common_new.deb
$APT --allow-downgrades install $G/cuems-utils_0.1.0rc15.deb > /dev/null 2>&1
attempt A2 REFUSED "new cuems-common beside cuems-utils 0.1.0rc15 (what a tilde floor would admit)" -- \
    $APT install $G/cuems-common_new.deb
$APT --allow-downgrades install "$G/cuems-utils_0.1.1~rc1.deb" > /dev/null 2>&1
attempt A3 REFUSED "new cuems-common beside cuems-utils 0.1.1~rc1 (past the ceiling)" -- \
    $APT install $G/cuems-common_new.deb
state "cuems-common must not be installed after three refusals" -- versions

# Forward edge of the discovery cutover (FR-017): renamed cuems-common with an
# un-renamed cuems-nodeconf.
$APT --allow-downgrades install $G/cuems-utils_0.1.0rc16.deb > /dev/null 2>&1
attempt B1 REFUSED "new cuems-common together with cuems-nodeconf 0.1.0-7 (un-renamed)" -- \
    $APT install $G/cuems-common_new.deb $G/cuems-nodeconf_0.1.0-7.deb
state "still nothing installed" -- versions

# Reverse edge (FR-019): renamed cuems-nodeconf with the un-renamed previous
# release. Expected to be ACCEPTED today — cuems-nodeconf declares only
# cuems-common (>= 1.0.0) — and recorded as the gap its own flow must close.
attempt C1 ACCEPTED "previous cuems-common (un-renamed) together with cuems-nodeconf 0.1.0-8 — the reverse-edge GAP" -- \
    $APT install $G/cuems-common_old.deb $G/cuems-nodeconf_0.1.0-8.deb
state "installed: the previous release" -- versions

# Correct order (T028): upgrade the previous release in place, on a host that
# looks like a deployed controller — a live discovery file copied from the old
# template, and an operator-modified 99-cuems sudoers file.
cp /usr/share/cuems/cuems.service.master /etc/avahi/services/cuems.service
echo "# operator note: edited on site" >> /etc/sudoers.d/99-cuems
state "before upgrade: live discovery file" -- grep -n "txt-record" /etc/avahi/services/cuems.service
state "before upgrade: sudoers.d" -- ls -1 /etc/sudoers.d
attempt D1 ACCEPTED "upgrade previous -> new cuems-common, with cuems-utils 0.1.0rc16 and cuems-nodeconf 0.1.0-8 (correct order)" -- \
    $APT install $G/cuems-common_new.deb
state "after upgrade: versions" -- versions
state "after upgrade: live discovery file migrated" -- grep -n "txt-record" /etc/avahi/services/cuems.service
state "after upgrade: its backup" -- sh -c 'ls -1 /etc/avahi/services/ ; for b in /etc/avahi/services/cuems.service.*.bak; do grep -c node_type "$b"; done'
state "after upgrade: sudoers.d (99-cuems retired, modified copy kept inert)" -- ls -1 /etc/sudoers.d
state "after upgrade: sudo parses the whole configuration" -- visudo -c
state "after upgrade: shipped templates" -- sh -c 'ls -1 /usr/share/cuems/cuems.service.*'

# Forward edge on an upgraded host: take cuems-nodeconf back to 0.1.0-7.
attempt E1 REFUSED "on the upgraded host, downgrade cuems-nodeconf to 0.1.0-7 (un-renamed)" -- \
    $APT --allow-downgrades install $G/cuems-nodeconf_0.1.0-7.deb
state "final versions" -- versions
exit 0
SCENARIOS

log "running scenarios in an unprivileged mmdebstrap system (downloads from $MIRROR)"
mmdebstrap --mode=unshare --variant=apt --include=ca-certificates \
    --customize-hook='mkdir -p "$1/tmp/gate"' \
    --customize-hook="copy-in $WORK/debs /tmp/gate" \
    --customize-hook='chroot "$1" sh /tmp/gate/debs/scenarios.sh' \
    --customize-hook="copy-out /tmp/gate/transcript.txt $WORK" \
    bookworm /dev/null "$MIRROR" > "$WORK/mmdebstrap.log" 2>&1 \
    || { log "mmdebstrap failed — see $WORK/mmdebstrap.log"; exit 1; }

# --- 5. evidence --------------------------------------------------------------
mkdir -p "$(dirname "$OUT")"
{
    echo "# Release-gate demonstration — observed, not asserted (feature 001, T027/T028)"
    echo "#"
    echo "# Generated by tests/packaging/release-gate-demo.sh. Do not edit by hand; re-run it."
    echo "#"
    echo "# date:              $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# repository commit: $(git -C "$REPO" rev-parse HEAD)$(git -C "$REPO" diff --quiet HEAD -- . ':!specs/001-node-role-and-conversion-ordering/evidence' || echo ' (+ uncommitted changes)')"
    echo "# cuems-common new:  $NEW_VERSION (built from the working tree; +gatedemo1 marks a demo build)"
    echo "# cuems-common old:  $OLD_VERSION (built from $OLD_REF)"
    echo "# cuems-utils:       STUBS at ${UTILS_VERSIONS[*]}"
    echo "# cuems-nodeconf:    STUBS at ${NODECONF_VERSIONS[*]} — Depends: cuems-common (>= 1.0.0), as the real package"
    echo "# environment:       $(mmdebstrap --version), --mode=unshare --variant=apt, bookworm, $MIRROR"
    echo "#"
    echo "# The counterparts are equivs stubs: they carry versions and relationships only."
    echo "# Every REFUSED outcome is apt/dpkg refusing the REAL cuems-common package."
    echo "# apt runs with --no-remove, so a relationship it could only satisfy by removing"
    echo "# an installed package is reported as a refusal instead of silently removing it."
    cat "$WORK/transcript.txt"
    echo
    echo "=== SUMMARY"
    grep '^VERDICT' "$WORK/transcript.txt" | while read -r _ id exp obs; do
        e=${exp#expected=}; o=${obs#observed=}
        [ "$e" = "$o" ] && m=match || m=MISMATCH
        printf '%-3s expected %-8s observed %-8s %s\n' "$id" "$e" "$o" "$m"
    done
} > "$OUT"
log "evidence written: $OUT"

if grep '^VERDICT' "$WORK/transcript.txt" | awk '{split($3,e,"="); split($4,o,"="); if (e[2]!=o[2]) bad=1} END {exit bad}'; then
    log "all scenarios matched their expectations"
else
    log "at least one scenario did NOT match — see $OUT"
    exit 1
fi
