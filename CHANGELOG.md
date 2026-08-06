<!--
***
SPDX-FileCopyrightText: 2025 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# Changelog

All notable changes to `cuems-common` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — development on `rc_1` / `main`

MTC-bias latency compensation completed for the video pipeline; audio stack hardened against Pipewire/Wireplumber interference; OLA DMX infrastructure packaged as first-class CUEMS services; all services migrated to the dedicated `cuems` system user with uniform security hardening.

### Added

- **`cuems-cluster-poweroff.service` + `/usr/bin/cuems-cluster-poweroff`** — orderly cluster power-off on the physical power button. The unit does nothing at boot; its `ExecStop=` runs during the poweroff transition and powers the projectors off (PJLink), then the cluster node(s) off (SSH), waits until they are unreachable, and hands back to systemd. Ordering carries the design: `After=networking.service` plus both avahi units (so PJLink and `<node>.local` resolution still work), and `Before=cuems-power-bridge.service` (so the bridge has already stopped and its `_cancel_projector_on_task()` has run, ruling out a `POWR 1` racing our `POWR 0`). Confirmed on test2 by the unit's own ordering probe during a real transition: `power-bridge=inactive avahi-daemon=active networking=active`. Duplicates no protocol logic — it drives the installed `cuems-power-bridge` library against the host's own `power-bridge.conf`. Guards: poweroff-only (a reboot must not kill the lamps, since PJLink answers `ERR3` to `POWR 1` during cooldown); self-exclusion by node uuid and exact local-address membership (a standalone controller is its own node, and a host can never observe *itself* unreachable, so a missed self-entry would burn the whole `node_wait_s` every time); idempotency (state queried first, so a bridge-driven `POST /shutdown` — which ends in `sudo /sbin/poweroff` and re-enters this script — is a fast no-op).
- **`cuems-displays-on.service` + `/usr/bin/cuems-displays-on`** — boot-time confirmation that the projectors came on. `cuems-power-bridge`'s `projector_power_on_on_start` fires a single power-on with a ~4 s retry budget while lamp cooldown is tens of seconds, so a fast power cycle left the room dark with one unconfirmed WARNING. Re-issues `POST /poweron` until every display reports `on`. Gated on `projector_power_on_on_start` as well as `enabled=`, so sites whose projector fleets are deliberately left dark are never commanded.
- **`/etc/cuems/cluster-poweroff.conf`** — single kill switch and tuning for both units above. Ships **`enabled=false`**: `cuems-common` installs identically on every host, so a fleet-wide upgrade must not change any site's behaviour until a box is opted in. `projector_timeout_s=45` is measured, not guessed — against an unreachable projector a status query costs 5 s and the power-off retries 19 s (test2, 2026-08-06), so the previous 25 s left one second of margin and would have truncated the stage and lost its log.
- **`etc/systemd/logind.conf.d/10-cuems-power-button.conf`** — pins `HandlePowerKey=poweroff`. Behaviourally a no-op (it is the compiled-in default), but the new hook depends on a press producing an ordinary orderly transaction, so the contract is stated rather than inherited. Not reloadable (`CanReload=no` on systemd 252), so it applies at next boot.
- `cuems-gradient-motiond.service` — gradient fade engine as a first-class node service (`PartOf=cuems-node.target`, `User=cuems`). Connects to the NNG publish hub on `tcp://controller.local:9093` via Avahi mDNS so the unit is topology-independent and needs no per-node IP configuration. Part of MTC-bias Phase 7.
- `cuems-extract-video-latency` — `ExecStartPre` helper for `cuems-videocomposer.service`. Reads `videoplayer/output_latency_ms` from `settings.xml` (honoring `$CUEMS_CONF_PATH`) and writes `/run/cuems/videocomposer.env` with `OUTPUT_LATENCY_FLAG=--output-latency-ms N` (integer) or `OUTPUT_LATENCY_FLAG=` (auto / absent / malformed). Closes the Phase-5B asymmetry where videocomposer had no path to read settings.xml.
- `/etc/cuems/videocomposer-flags.env.example` — template for `OPERATOR_FLAGS`, the operator-tunable env var in `cuems-videocomposer.service`. Enables adding CLI flags (e.g. `--verbose`) without writing systemd drop-ins that would reset `ExecStart` and lose `OUTPUT_LATENCY_FLAG` composition.
- `cuems-ola-profile` — operator script at `/usr/bin/cuems-ola-profile`. Enables OLA DMX hardware profiles (`pro`, `opendmx`, `artnet`, `sacn`) by toggling `/etc/ola/*.conf` files and restarting `olad`. Handles the `ftdi_sio` kernel module blacklist required by the `opendmx` profile and lists enabled plugins with supported hardware models after applying.
- `olad.service` — native systemd unit for the OLA daemon. Runs as `olad` user with `dialout` and `plugdev` supplementary groups; config dir `/etc/ola`; restarts on failure.
- `/etc/modules-load.d/cuems-midi.conf` — deterministic `snd-seq` + `snd-seq-dummy` module load at boot. Prevents the racy on-demand load path that caused `RtMidiError` crashes during `cuems-controller-engine` startup.
- `/etc/systemd/user/{pipewire,pipewire-pulse,wireplumber}.{service,socket} → /dev/null` — system-wide masks for the per-user Pipewire stack. Prevents Pipewire and Wireplumber from racing `zita-j2a` for `hw:HID` (USB audio), which caused non-deterministic `JackAudioDriver::ProcessGraphAsyncMaster` errors and silently unwired the USB audio mixer.
- `jack-alsa-bridges.service` — new dedicated service for the USB audio bridge. Waits up to 30 s for JACK to advertise ports (`jack_lsp`), restores USB audio mixer state via `alsactl`, starts `zita-j2a` (`hw:HID,0`, 48 kHz, 512-frame period, 3 periods), and wires `0_mixer:output_7/8` to `usb_audio:playback_1/2` after port registration.
- Shell aliases via `/etc/profile.d/cuems.sh`: `cuems-restart`, `cuems-start`, `cuems-stop`, `cuems-status` targeting `cuems-node.target` and `cuems-controller.target`.
- `scripts/test-ola-flock-patch.sh` — six-test suite verifying that the CUEMS-patched OLA package compiled in `flock()` support, exports `AcquireLockAndOpenSerialPort`, uses `flock` instead of UUCP locking, handles the self-lock race, leaves no stale lock files after a crash, and supports same-process re-lock.
- `scripts/test-systemd-deps.sh` — static and live validation of the service dependency graph. Static mode verifies node-expected and controller-expected service assignments; `--live` mode starts and stops targets with confirmation prompts.
- `docs/latency-tuning.md` — operator runbook covering `output_latency_ms` tuning for video, audio, and DMX pipelines: which values to set, how to apply and verify, per-adapter starting points, and the 120-fps phone-camera measurement procedure.
- `docs/ola-install.md` — installation guide for the CUEMS-patched OLA 0.10.9 package, covering extract, install, apt pinning, `olad.service` via `cuems-common`, and DMX hardware profile configuration.

### Changed

- **`gradient-motiond.service` → `cuems-gradient-motiond.service`** — renamed to match the `cuems-*` naming convention used by all other package-provided units. The binary path (`/usr/bin/gradient-motiond`) is unchanged — foreign binary names are not renamed on install.
- **All services migrated from `stagelab` to `cuems` user** — `cuems-controller-engine`, `cuems-editor`, `cuems-midiconnector`, `cuems-node-engine`, `cuems-videocomposer` all now declare `User=cuems Group=cuems`. The `cuems` system user is created by `preinst` and is not present in older installations; `preinst` is idempotent.
- **`jackd-cuems.service`**: replaced `alsa_out` USB audio bridging with `zita-j2a` via the new `jack-alsa-bridges.service`. `alsa_out` is deprecated in modern ALSA configurations and produced glitches under load.
- **`cuems-node-engine.service`**: added `Requires=jack-alsa-bridges.service` and `After=jack-alsa-bridges.service` so `AudioMixer.connect_to_jack()` runs only after USB JACK ports are registered. Without this ordering, the mixer skipped `usb_audio:playback_1/2` silently on fast-booting hardware.
- **User-facing scripts moved to `/usr/bin/`** — `cuems-healthcheck`, `cuems-config-node`, `cuems-stop`, `cuems-hdmi-audio-map`, and `cuems-ola-profile` are now in `/usr/bin/` (FHS-compliant for package-managed executables). They were previously in `/usr/local/bin/`.
- **`cuems-videocomposer.service`**: `ExecStart` now composes `$OPERATOR_FLAGS $OUTPUT_LATENCY_FLAG`, both sourced from independent `EnvironmentFile` blocks. A systemd drop-in that resets `ExecStart` must re-declare both variables to avoid silent flag loss.
- **`pkill` patterns in `cuems-node-engine.service`** updated from `audioplayer-cuems`/`dmxplayer-cuems` to `cuems-audioplayer`/`cuems-dmxplayer` following binary renames in the player packages.

### Fixed

- `cuems-videocomposer.service` / `cuems-extract-video-latency`: `CUEMS_CONF_PATH` env var was ignored; now honoured, aligning the helper with `cuemsutils.tools.ConfigManager` path resolution. Operators who override the config path via `systemctl edit cuems-videocomposer` now get consistent resolution across both layers.
- `cuems-midiconnector.service`: corrected `ExecStart` path (referenced a stale binary location). Added `SupplementaryGroups=audio`, `NoNewPrivileges=yes`, `ProtectSystem=full`, `ProtectHome=read-only`.
- `cuems-nodeconf.service`: normalized `TimeoutStartSec=60`, `TimeoutStopSec=10`, added `StandardOutput=journal StandardError=journal`.
- `cuems-node-engine.service`, `cuems-controller-engine.service`: added `NoNewPrivileges=yes`, `ProtectSystem=full`, `ProtectHome=read-only`, `ReadWritePaths=/opt/cuems_library /tmp`.
- `cuems-editor.service`: added `RuntimeDirectory=cuems-editor`, `PIDFile=/run/cuems-editor/service.pid`, journal logging, `PrivateTmp=no`.
- `/tmp/cuems`: created at boot via `tmpfiles.d/cuems-tmp.conf` with `mode=0775, owner=stagelab:stagelab`. Previously relied on services to create the directory on first start, which caused races.
- `cuems-hdmi-audio-map.service` dependency order: now declared `Before=jackd-cuems.service` to guarantee asound.conf is written before JACK opens the ALSA device.
- `cuems-midiconnector.service`: fixed `ExecStart` path after upstream binary relocation.

### Removed

- **The acpid power-button chain and the `cuems-stop` binary** — `etc/acpi/events/powerbtn-acpi-support`, `etc/acpi/powerbtn-custom-handler.sh`, `etc/acpi/cuems-power-button-waiter.sh` (removed via `rm_conffile` in preinst/postinst/postrm, since they are conffiles) and `/usr/bin/cuems-stop`. None of it had ever run: `acpid` is not installed on any CUEMS host — verified on isil, test2 and both Medina controllers — so the physical power button has always been handled by systemd-logind's `HandlePowerKey`. Keeping the files was a booby trap rather than dead weight, because the handler's first action was `/usr/bin/cuems-stop`, hardcoded to a long-gone venue's power relay (`192.168.3.20`) and SSH targets (`stagelab@192.168.2.20x`) — installing `acpid` for any unrelated reason would have resurrected a script that shuts down someone else's LAN. Superseded by `cuems-cluster-poweroff.service`, which hooks the poweroff transition and so also covers `systemctl poweroff`. The `cuems-stop` shell **alias** (stop the systemd targets) survives and is now unambiguous — it no longer shadows a binary.
- **`cuems-generate-display-conf`** — removed. The script read `project_mappings.xsd canvas_region` as pixel values and emitted them to `/run/cuems/display.conf`. After the cuems-utils commit 5ac1d46 (2026-04-21) repurposed that element to normalised 0–1 UI-template floats, the script produced semantically wrong data. `cuems-videocomposer` (DRMBackend) already falls back to its DRM-detected layout when `/run/cuems/display.conf` is absent, so removing the producer moves all nodes to the DRM-default path — the path most nodes used implicitly. A replacement that generates correct defaults is tracked as urgent follow-up.
- **HDMI warm-restart hack** (reverted) — removed `cuems-i915-rebind.sh`, `cuems-wake-monitors.sh`, the `hdmi-fix.conf` service drop-in, and the GRUB `i915.enable_dc=0` parameter. The HDMI black-screen on warm restart was traced to a monitor-side setup problem, not a GPU/driver issue on the CUEMS node.

### Notes

- Pipewire masking (`/etc/systemd/user/*.service → /dev/null`) takes effect immediately on installation: `postinst` stops any running Pipewire instances across all logged-in users via `runuser`. Nodes that are rebooted after installation will have the masks in effect from first boot.
- The `cuems-common` package does not ship the `cuems-utils` Python wrapper at `/usr/lib/cuems/bin/python3` — that path is provided by `cuems-utils`. The `postinst` script aborts with an error if the wrapper is missing, because all Python-based services depend on it for their virtual-environment Python.

---

## 1.0.0-1 — 2025-11-12

Initial Debian package release establishing the systemd service architecture for CUEMS installations.

### Added

- `cuems-node.target` / `cuems-controller.target` / `cuems-wifi.target` — three systemd targets defining the node, controller, and WiFi AP service groups.
- `cuems-controller.path` — path unit monitoring `/etc/cuems/master.lock` for automatic controller role activation.
- Service units: `cuems-controller-engine`, `cuems-editor`, `cuems-midiconnector`, `cuems-node-engine`, `cuems-videocomposer`, `cuems-nodeconf`, `jackd-cuems`, `cuems-hdmi-audio-map`, `cuems-wifi`, `hostapd`, `rsync@` + `rsync.socket`.
- Service drop-ins binding `apache2`, `avahi-daemon`, `hostapd`, `isc-dhcp-server`, and `rtpmidid` into the appropriate CUEMS targets.
- `cuems-config-node` — Python script for node provisioning (MAC/UUID injection into settings.xml, Avahi templates, hostname, and hosts).
- `cuems-hdmi-audio-map` — Python script for boot-time DRM-to-ALSA mapping via DRM ioctl; writes `/etc/asound.conf` with a stable `multi_hdmi` 6-channel PCM definition.
- `cuems-healthcheck` — bash service health check and disk usage monitor.
- Network configuration templates (`interfaces.master`, `interfaces.node`), Avahi service group templates (`cuems.service.{firstrun,master,slave}`).
- `network_map.xml` / `network_map.xsd` — cluster topology document and XML Schema.
- Apache2 virtual-host configuration for HTTP and HTTPS WebSocket reverse proxy (ports 9190, 9092).
- Kernel performance tuning (`99-cuems-performance.conf`), JACK daemon configuration (`/etc/default/jack`), sudoers drop-in (`99-cuems`), logrotate configuration, rsyslog configuration, DHCP / hostapd / Avahi configuration.
- `scripts/test-systemd-units.sh` — systemd unit syntax and structure test suite.
- `scripts/validate-systemd.sh` — quick validation report script.
- `splash/` — Plymouth boot splash assets (background tile, BGRT theme, icon).

### Notes

- All Python scripts use `/usr/lib/cuems/bin/python3` (provided by `cuems-utils`). The `postinst` script verifies this wrapper exists before completing installation.
- `isc-dhcp-server` and `hostapd` are required dependencies for WiFi AP functionality; they are installed but the AP is only activated on machines with `cuems-wifi.target` enabled.
- Wayland support (`cuems-wayland.service`) was noted in the initial changelog entry but was not included in the final package tree; it remained as aspirational planned work.
