#!/bin/sh
# provision-cage-kiosk.sh
#
# Provisions a touch-first Wayland kiosk: cage (single-app compositor) +
# Chromium in --kiosk mode, autologin via lightdm.
#
# This is a TEMPLATE for NEW kiosk builds. Do not run against an existing
# X11+openbox+Firefox kiosk without deliberately migrating it — it replaces
# the session type lightdm hands the autologin user.
#
# Usage: sudo ./provision-cage-kiosk.sh <kiosk-user> <url>

set -e

KIOSK_USER="${1:?Usage: $0 <kiosk-user> <url>}"
KIOSK_URL="${2:?Usage: $0 <kiosk-user> <url>}"

# --- 1. Packages ------------------------------------------------------------
apt-get update
apt-get install -y cage chromium lightdm lightdm-gtk-greeter

# --- 2. Kiosk user ------------------------------------------------------------
if ! id "${KIOSK_USER}" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "${KIOSK_USER}"
fi
# video/render for GPU (DRM/KMS) access, input for the touchscreen evdev node
usermod -aG video,render,input "${KIOSK_USER}"

# --- 3. Launcher script -------------------------------------------------------
# Runs cage in a restart loop: if Chromium crashes, cage exits (it's a
# single-client compositor), and we relaunch rather than leaving a blank
# screen on an unattended public display.
cat > /usr/local/bin/cage-kiosk-start <<'LAUNCHER'
#!/bin/sh
URL="__KIOSK_URL__"

while true; do
    cage -- chromium \
        --kiosk \
        --ozone-platform=wayland \
        --enable-features=UseOzonePlatform,TouchpadOverscrollHistoryNavigation \
        --touch-events=enabled \
        --enable-pinch \
        --overscroll-history-navigation=0 \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --disable-session-crashed-bubble \
        --disable-translate \
        --disable-features=TranslateUI \
        --check-for-update-interval=31536000 \
        "${URL}"
    sleep 2
done
LAUNCHER
# Substitute the URL in place (keeps the heredoc above literal/unexpanded so
# any &, ?, = in the URL don't need escaping).
sed -i "s#__KIOSK_URL__#${KIOSK_URL}#" /usr/local/bin/cage-kiosk-start
chmod +x /usr/local/bin/cage-kiosk-start

# --- 4. lightdm Wayland session entry ----------------------------------------
mkdir -p /usr/share/wayland-sessions
cat > /usr/share/wayland-sessions/cage-kiosk.desktop <<'EOF'
[Desktop Entry]
Name=Cage Kiosk
Comment=Single-app Wayland kiosk session (cage + Chromium)
Exec=/usr/local/bin/cage-kiosk-start
Type=Application
EOF

# --- 5. lightdm autologin into the kiosk session -----------------------------
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-kiosk.conf <<EOF
[Seat:*]
autologin-user=${KIOSK_USER}
autologin-user-timeout=0
user-session=cage-kiosk
greeter-session=lightdm-gtk-greeter
EOF

echo
echo "Done. On next boot, lightdm will autologin '${KIOSK_USER}' into cage + Chromium"
echo "kiosk-mode pointed at: ${KIOSK_URL}"
echo
echo "Notes:"
echo "  - --enable-pinch allows pinch-zoom; drop it (add --disable-pinch instead)"
echo "    if the page's fixed layout must never be zoomed."
echo "  - Verify GPU/DRM access works under Wayland before relying on this:"
echo "    check 'cage -- weston-info' or similar smoke test first on new hardware."
echo "  - A phantom 'connected' output lying in DRM (e.g. a stale"
echo "    video=<conn>:e kernel param) will confuse cage's output selection"
echo "    the same way it confused X11 — fix that at the kernel/GRUB level"
echo "    before blaming the compositor."
