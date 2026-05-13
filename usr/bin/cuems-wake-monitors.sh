#!/bin/bash
# cuems-wake-monitors.sh
# Sends DDC/CI Power On commands to connected monitors 10 seconds after
# cuems-videocomposer starts its DRM modeset.
#
# LG UltraFine (and similar HDMI monitors) can remain in a sleep state after
# a warm restart even when the GPU is sending a valid HDMI signal. This script
# uses ddcutil to explicitly wake each monitor via the DDC/CI protocol.
#
# !!! CONTROLLER-ONLY HELPER — node hosts do not need this !!!
# Node hosts (slave/clones) initialise their HDMI outputs cleanly
# via the always-on display-conf-gen drop-in and do NOT need the
# DDC/CI wake nudge. This script exists for the dev-lab controller
# 000000000002 (Alder Lake-N + LG UltraFine via TC-port), and the
# bus numbers below are hardcoded for that controller's layout:
#
#   HDMI-A-1 → /dev/i2c-4  (true HDMI port, DDC confirmed working)
#   DP-2     → /dev/i2c-11 (DP++ in HDMI mode, DDC bridge unreliable;
#                           monitor wakes from stable HDMI signal instead)
#
# TODO (future refactor): auto-discover bus numbers via
# /sys/class/drm/<connector>/ddc/i2c-N so the script becomes
# hardware-agnostic.
#
# Must run as root (ExecStartPost=+ in the service unit).

# Wait for videocomposer DRM modeset to stabilise before sending DDC commands.
sleep 10

# Ensure i2c-dev is loaded — the i915 rebind destroys i2c adapters and
# /dev/i2c-* nodes are only recreated if this module is present.
modprobe i2c-dev 2>/dev/null
sleep 0.5

echo "cuems-wake-monitors: sending DDC/CI power-on commands..."

# HDMI-A-1 → i2c-4: true HDMI port, DDC confirmed working
ddcutil --bus 4 setvcp 0xD6 0x01 2>/dev/null \
    && echo "cuems-wake-monitors: HDMI-A-1 (i2c-4) power-on sent OK" \
    || echo "cuems-wake-monitors: HDMI-A-1 (i2c-4) DDC failed (non-fatal)"

# DP-2 → i2c-11: DP++ in HDMI mode, DDC bridge unreliable - try with --force
ddcutil --bus 11 --force setvcp 0xD6 0x01 2>/dev/null \
    && echo "cuems-wake-monitors: DP-2 (i2c-11) power-on sent OK" \
    || echo "cuems-wake-monitors: DP-2 (i2c-11) DDC failed - relying on HDMI signal"

echo "cuems-wake-monitors: done"
