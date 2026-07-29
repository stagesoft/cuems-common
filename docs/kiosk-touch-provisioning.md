# Touch kiosk provisioning (Firefox-esr → Chromium/Wayland)

Standalone public-facing touchscreen displays (e.g. `museullivia.dseny.es` on the
`kiosk-llivia-*` hosts) are **not** part of the CUEMS controller/node role model —
they're plain Debian kiosks running lightdm + openbox + a browser pointed at a
fixed URL. This doc is not shipped/installed by the package; it's operator
reference for provisioning and troubleshooting this class of host.

## Background: why touch feels like a dragged cursor on X11

X11 has no native touch concept. Touch input arrives via `libinput`, which by
default converts it into synthetic core-pointer (mouse) events so unmodified
X clients keep working. That conversion is why a finger drag on an X11 kiosk
tracks 1:1 like a mouse cursor instead of producing the momentum/inertia feel
of a phone or tablet — real kinetic scrolling requires the browser to receive
raw touch (XInput2 touch events on X11, native `wl_touch` on Wayland) and run
its own gesture/async-pan-zoom engine on top.

Two independent levers exist to improve this:

1. **Browser choice** — Chromium's touch/gesture engine (shared lineage with
   Chrome on Android/ChromeOS) is materially better than Firefox's on Linux,
   even under plain X11.
2. **Display server** — Wayland delivers touch natively (no pointer-emulation
   layer at all). Bigger change, biggest ceiling.

Firefox's own Enterprise Policy engine (`policies.json`) was checked and
confirmed **not** to expose any lever here: the `Preferences` policy only
accepts a curated prefix allow-list (`app.update.*`, `signon.*`,
`spellchecker.*`, various `security.*`/`privacy.*` fingerprinting prefs,
`general.smoothScroll`, …) — nothing touch/APZ/zoom/pan/gesture-related is on
it. That's a hard ceiling, not a missing setting.

## Option A — swap browser only, keep X11 + openbox + lightdm

Lowest-risk path for an existing production kiosk. See commands below for the
specific hosts; the general shape is: install `chromium`, replace the
`firefox-esr --kiosk …` line in the kiosk user's
`~/.config/openbox/autostart` with a `chromium --kiosk …` line, and port the
Firefox `policies.json` lockdown to Chromium's managed-policy format
(`/etc/chromium/policies/managed/policies.json`).

## Option B — full replacement: cage (Wayland) + Chromium

For **new** kiosk builds, or an existing one where Option A isn't enough.
Use [`provision-cage-kiosk.sh`](./provision-cage-kiosk.sh):

```bash
sudo ./provision-cage-kiosk.sh <kiosk-user> <url>
```

It installs `cage` (a minimal wlroots-based single-app Wayland compositor —
functionally replaces openbox's role, since there's only ever one window) and
Chromium launched with Wayland/touch flags, wires a `cage-kiosk.desktop`
Wayland session, and points lightdm's autologin at it. Read the script's
trailing notes output — it flags two decisions that are per-deployment, not
safe defaults:

- Whether pinch-zoom should stay enabled (`--enable-pinch`) — depends on
  whether the page's fixed layout should ever be zoomable.
- Verifying DRM/GPU access works under Wayland on new/untested hardware
  before relying on it.

**Do not run this against an existing X11+openbox+Firefox kiosk casually** —
it replaces the lightdm session type the autologin user gets. Migrating an
existing host is a deliberate decision, not a drop-in patch.

## Things that don't change regardless of display server

A kernel/DRM-level lie about display state — e.g. the `video=<connector>:e`
GRUB parameter that force-enabled a phantom `DP-1` output on `kiosk-llivia-1`
and stretched its virtual screen past the real touch panel — confuses cage's
output selection exactly as it confused X11/xrandr. Fix that at the
kernel/GRUB layer first; don't try to work around it in compositor or
browser config.

## Firefox policy management (`policies.json`)

Lives at `/etc/firefox-esr/policies/policies.json`. Confirmed identical
content on both `.253`/`.254` as of this writing:

```json
{
  "policies": {
    "Homepage": { "URL": "https://museullivia.dseny.es/", "Locked": true },
    "NewTabPage": false,
    "DisableAppUpdate": true,
    "DisableFeedbackCommands": true,
    "DNSOverHTTPS": { "Enabled": false }
  }
}
```

Two genuinely different enforcement mechanisms live inside this one file —
don't confuse them:

- **Dedicated policies** — `Homepage`, `SanitizeOnShutdown`,
  `DisableAppUpdate`, `NewTabPage`, `DisableFeedbackCommands`,
  `DNSOverHTTPS`, etc. Each is its own first-class, fully-supported
  top-level key. No allow-list restriction applies to these.
- **The generic `Preferences` block** — a **curated allow-list only**, not
  a passthrough to arbitrary `about:config`. Confirmed-allowed prefixes
  (checked against Mozilla's own reference this session):
  `app.update.*`, `signon.*`, `spellchecker.*`, `sidebar.*`,
  `general.smoothScroll`, `browser.cache.disk.parent_directory`, several
  fingerprinting-related `privacy.*`/`security.*` prefs, and a handful of
  others (list changes across Firefox versions, some entries are
  version-gated — re-check
  [Mozilla's `preferences` policy reference](https://firefox-admin-docs.mozilla.org/reference/policies/preferences/)
  rather than trusting this list to stay current). **Anything not on that
  list is silently ignored, not rejected or errored** — the policy applies
  cleanly with no warning and simply does nothing for that key, which gives
  false confidence unless you check.

  Confirmed **not** on the allow-list this session, so these are
  ineffective if placed under `Preferences` — use a dedicated policy or a
  different mechanism instead:
  - Anything touch/APZ/zoom/pan/gesture-related (`apz.*`,
    `dom.w3c_touch_events.*`) — see Background section above; this is why
    Firefox touch/momentum-scroll behavior can't be tuned via policy at
    all.
  - `privacy.sanitize.sanitizeOnShutdown`, `privacy.clearOnShutdown.cache`,
    `privacy.clearOnShutdown_v2.cache`, `browser.cache.disk.enable` — use
    the dedicated `SanitizeOnShutdown` policy for this instead (below).

### Preserving cache/history (manual clearing only)

Goal: nothing auto-clears cache or history on shutdown; an operator clears
it by hand when actually needed (e.g. forcing a fresh asset fetch after a
site deploy). Use the dedicated `SanitizeOnShutdown` policy, not
`Preferences` — none of the `privacy.clearOnShutdown*` prefs above are
enforceable through `Preferences` anyway.

Mozilla's documented behavior for this policy in object form: **any
omitted category defaults to `false`** (don't clear), not "unmanaged" —
so `{"Cache": false, "Locked": true}` alone already suppresses every
category, not just cache. Still, spell every category out explicitly
rather than rely on that implicit-default rule staying true across
Firefox versions:

```json
{
  "policies": {
    "SanitizeOnShutdown": {
      "Cache": false,
      "Cookies": false,
      "Downloads": false,
      "FormData": false,
      "History": false,
      "Sessions": false,
      "SiteSettings": false,
      "OfflineApps": false,
      "Locked": true
    }
  }
}
```

Merge this block alongside the existing `Homepage`/`DisableAppUpdate`/etc.
keys in the same `policies.json` — don't replace the file, add to it.

**Status: proposed, not yet applied to `.253`/`.254`** — remote access to
both hosts was unavailable at the time this was written up. Deploy and then
verify via `about:preferences#privacy` (the "Clear history when Firefox
closes" section should show cache/history/etc. all unchecked and
greyed-out/locked) before considering this done.

## Operational baseline tooling

Install on every touch kiosk (both X11 and Wayland/cage builds), not just when
a problem shows up. None of these run a daemon or open a port — static
diagnostic binaries only, negligible footprint — so there's no cost to
having them on hand versus needing `apt-get install` mid-incident on a
client's (possibly restricted) network:

```bash
apt-get update && apt-get install -y evtest libinput-tools
# X11 builds only — no Wayland equivalent needed, cage/wlroots expose
# device state differently:
apt-get install -y x11-xserver-utils   # xinput, xrandr
```

- `evtest` — raw kernel evdev event stream per device (`BTN_TOUCH`,
  `ABS_MT_*`, etc.). Use to confirm whether a touch release is actually
  reaching the kernel at all before suspecting X/libinput/the browser.
- `libinput debug-events` / `libinput list-devices` — same events after
  libinput's processing (device matching, calibration, tapping config
  applied). Use to compare against `evtest`'s raw view to isolate which
  layer (kernel vs. libinput vs. X) is dropping or duplicating an event.
- `xinput list` / `xinput test-xi2 --root` (X11 only) — confirms which
  logical X devices exist (watch for a touchscreen controller enumerating
  as *two* devices — a touch interface and a separate legacy relative-mouse
  HID interface, seen on the Weida controllers in this fleet — a common
  source of conflicting button-state events) and what X itself receives
  after `InputClass` matching is applied.

Diagnostic workflow for an event-delivery bug (e.g. touch-release/mouseup
not reaching page JS): capture with `evtest` and `libinput debug-events`
concurrently while reproducing, and check whether button-down and
button-up land on the same device stream. If they split across two
devices, the fix is disabling/ignoring the redundant HID interface (udev
rule stripping its `ID_INPUT_MOUSE` tag, or an `InputClass` with
`Option "Ignore" "on"` matched to that specific product string) — not
tuning the touchscreen device's own options.

## Fleet notes (learned auditing kiosk-llivia-1/2)

- The two "twin" hosts are **not** on the same Debian release:
  `kiosk-llivia-2` (.253) is Debian 13 (trixie), `kiosk-llivia-1` (.254) is
  Debian 12 (bookworm). This means different candidate versions of
  everything (`cage` 0.2.0 vs 0.1.4, `chromium` 149 vs 150, etc.) — verify
  behavior on each host individually rather than assuming parity.
- The two hosts also currently autologin as **different local users**
  (`kiosk` on .253, `stagelab` on .254) even though both `/home/kiosk` and
  `/home/stagelab` exist on both machines — a leftover from provisioning
  history, not a deliberate difference. Locate the active kiosk user via
  `loginctl list-sessions` before editing openbox autostart / profile paths,
  don't assume the username.

## Incident: Image Map Pro pins not clickable via touch (2026-07-28)

**Symptom:** on `espais-de-memoria/`, tapping an `.imp-object-spot` map pin
(Image Map Pro plugin) never opened its popup on either kiosk touchscreen —
a mouse click on the same element worked every time. Reproduced
independently on both `.253` and `.254`, which ruled out anything
host-specific from the start.

**Investigation, ruled out in this order** — kept here so a future
touch-click bug on this fleet doesn't re-walk the same path:

1. **libinput/kernel layer** — `libinput debug-events` showed clean
   `TOUCH_DOWN` → `TOUCH_MOTION` → `TOUCH_UP` sequences on both hosts, no
   missing release. Input delivery at the kernel/libinput level was never
   the problem.
2. **Dual-HID-device race** — the Weida controller's secondary "Mouse" HID
   interface (`event5`, visible in `libinput debug-events`/Xorg logs
   alongside the real touchscreen `event4`) stayed completely silent during
   the captured gesture. Worth checking on this hardware given it exists,
   but it wasn't the cause here.
3. **Browser touch-exposure layer** — disabled `dom.w3c_touch_events.enabled`
   / `legacy_apis.enabled` fleet-wide via a Firefox autoconfig
   (`/usr/lib/firefox-esr/mozilla.cfg` +
   `/usr/lib/firefox-esr/defaults/pref/autoconfig.js`, install-level so it
   survives profile wipes/cache cleanup — see git history of this file for
   the exact setup if this pattern is needed again for something else).
   Confirmed correctly applied (checked in `about:config`) but **did not
   fix it**. Root cause: those prefs only gate the legacy `TouchEvent` API,
   not `navigator.maxTouchPoints`, which is what modern touch
   feature-detection (including this plugin's) actually reads — so
   disabling them was never going to change the plugin's behavior.
4. **Actual root cause, found by reading `image-map-pro/js/client/main.js`
   directly:** the plugin implements its own pointer/gesture tracker and
   rejects a tap as a "click" if it detects *any* movement between press
   and release. A mouse physically cannot move during a click; a finger
   always has a few pixels of natural jitter — so mouse always worked and
   touch never did, on any machine, regardless of OS/browser layer. That's
   exactly why every layer below the plugin kept coming back clean.

**Fix:** implemented on the website itself (a footer script on
`museullivia.dseny.es`), not in any local kiosk config. All local
experiments from steps 2–3 above were reverted — verified removed from
both `.253` and `.254` (`mozilla.cfg`/`autoconfig.js` deleted, no stray
`user.js`, `.254`'s `40-touchscreen.conf` `Tapping "on"` `InputClass` also
removed) — since none of them were the actual fix and there's no reason to
carry dead workarounds forward.

Reference copy of the deployed footer script, kept here for institutional
memory (the live copy lives on the client's WordPress site, not in this
repo — this is what it looked like at the time of this fix, in case it
ever needs revisiting):

```js
/* ---------------------------------------------------------------
  Arreglo marcadores image-map-pro en pantallas tactiles.

  Causa: el plugin anula el clic si detecta CUALQUIER movimiento
  entre pulsar y soltar. Un raton no se mueve; un dedo siempre
  tiembla unos pixeles. Por eso funciona con raton y no con dedo.

  Solucion: filtrar los movimientos menores de 12px en fase de
  CAPTURA, antes de que lleguen a los manejadores del plugin.
  Solo actua si la pulsacion empezo sobre un marcador.
--------------------------------------------------------------- */
(function () {
 var THRESH = 12, down = null;

 function pos(e) {
   var t = e.touches && e.touches[0];
   return t ? { x: t.pageX, y: t.pageY } : { x: e.pageX, y: e.pageY };
 }
 function start(e) {
   var el = e.target && e.target.closest
          ? e.target.closest('[data-object-id],[data-parent-id]') : null;
   down = el ? pos(e) : null;
 }
 function end() { down = null; }
 function move(e) {
   if (!down) return;
   var p = pos(e), dx = p.x - down.x, dy = p.y - down.y;
   if (Math.sqrt(dx * dx + dy * dy) < THRESH) e.stopImmediatePropagation();
 }

 var h = [['mousedown', start], ['touchstart', start],
          ['mouseup', end], ['touchend', end], ['touchcancel', end],
          ['mousemove', move], ['touchmove', move]];
 for (var i = 0; i < h.length; i++) {
   document.addEventListener(h[i][0], h[i][1], true);
 }
})();
```
