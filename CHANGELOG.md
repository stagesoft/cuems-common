<!--
***
SPDX-FileCopyrightText: 2025 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
***
-->

# Changelog

All notable changes to `cuems-common` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — development on `rc_1` / `main`

MTC-bias latency compensation completed for the video pipeline; audio stack hardened against Pipewire/Wireplumber interference; OLA DMX infrastructure packaged as first-class CUEMS services; all services migrated to the dedicated `cuems` system user with uniform security hardening.

### Added

- **Controller network modes** (1.3.0-23) — `/etc/cuems/net-mode.conf` (`NET_MODE=auto|cable-dhcp|cable-static|ap|manual`, `AP_ARMED=yes|no`) and the operator tool `/usr/bin/cuems-net-mode {status [--check]|apply [--fix-now]|<mode>} [--yes]`. `auto` is the standard: a lease when a DHCP server answers, `192.168.6.1` when none does (asking again every minute, and **never** serving DHCP on the cable), the WiFi AP when there is no cable. A missing file or an unknown value means `manual`, in which the package does nothing — so a file-copy deploy, which runs no postinst, inherits no new behaviour. Everything acts on a controller only: `/etc/cuems/master.ip` **and** `bond0`. Written after the taller power cut of 2026-09-29, where three controllers that booted before their router served `192.168.6.0/24` on the wired LAN, to each other included. Plan and review: `Plans/2026-09-29-controller-network-modes.md`.
- **`cuems-net-guard.timer` + `/usr/lib/cuems/bin/cuems-net-guard`** — every 60 s, on a controller, in every mode but `manual`: never leaves `bond0` without an IPv4; takes the AP data path down if `hostapd` died under it (and retries a failed AP every 5 minutes in `ap` mode); restarts a missing DHCP client; and re-probes a fallback. The last is the reason the timer exists — a `dhclient` bound to the static lease sleeps until that lease expires, in 2040, and `dhclient.conf` is the operator's file. A quiet run logs nothing (`LogLevelMax=notice`).
- **`/usr/lib/cuems/bin/cuems-dhcp-probe`** (python3) — one `DHCPDISCOVER`, retransmitted at 2 s and 5 s, 8 s wait. Never sends a `REQUEST`: it takes no lease, writes no file and leaves no process. A second `dhclient` was not an option (its AppArmor profile is enforced). It uses a packet socket, like `dhclient` itself, because the probe runs while `bond0` holds the fallback and the offer comes from a server the host has no route to.
- **`/usr/lib/cuems/bin/cuems-bond0-dhclient {status|start|stop|restart|active-for}`** — the DHCP client of `bond0` outside of `ifup`/`ifdown`, with exactly ifupdown's command line (same flags, same DHCP identity, same AppArmor-allowed paths). Stops with `SIGKILL`: `dhclient -x` runs the `STOP` script, which flushes the address the operator is connected through. Starts the client as the transient unit `cuems-dhclient-bond0.service`.
- **`/usr/lib/cuems/bin/cuems-ap-path {up|down|release-wifi}`** — the AP's data path: moves `192.168.6.1` from `bond0` to `wifi0` and back, always giving before taking, with forwarding off on `wifi0` so the AP's clients are not routed onto the venue LAN or the cluster link.
- **dhclient exit hook `cuems-fallback`** — shipped under `/usr/lib/cuems/dhclient-hooks/` and symlinked into `/etc/dhcp/dhclient-exit-hooks.d/` by the postinst (not a conffile, so a downgrade can remove it). Decides from the observed state of `bond0`, because `dhclient-script` hides its status from hooks.
- **`debian/prerm`** — new, with debhelper's token so the generated unit-stop snippet is unchanged. Undoes the hook, the timer and an AP armed by this version on remove and on a downgrade below 1.3.0-23.

- **`cuems-cluster-poweroff.service` + `/usr/bin/cuems-cluster-poweroff`** — orderly cluster power-off on the physical power button. The unit does nothing at boot; its `ExecStop=` runs during the poweroff transition and powers the projectors off (PJLink), then the cluster node(s) off (SSH), waits until they are unreachable, and hands back to systemd. Ordering carries the design: `After=networking.service` plus both avahi units (so PJLink and `<node>.local` resolution still work), and `Before=cuems-power-bridge.service` (so the bridge has already stopped and its `_cancel_projector_on_task()` has run, ruling out a `POWR 1` racing our `POWR 0`). Confirmed on test2 by the unit's own ordering probe during a real transition: `power-bridge=inactive avahi-daemon=active networking=active`. Duplicates no protocol logic — it drives the installed `cuems-power-bridge` library against the host's own `power-bridge.conf`. Guards: poweroff-only (a reboot must not kill the lamps, since PJLink answers `ERR3` to `POWR 1` during cooldown); self-exclusion by node uuid and exact local-address membership (a standalone controller is its own node, and a host can never observe *itself* unreachable, so a missed self-entry would burn the whole `node_wait_s` every time); idempotency (state queried first, so a bridge-driven `POST /shutdown` — which ends in `sudo /sbin/poweroff` and re-enters this script — is a fast no-op).
- **`cuems-displays-on.service` + `/usr/bin/cuems-displays-on`** — boot-time confirmation that the projectors came on. `cuems-power-bridge`'s `projector_power_on_on_start` fires a single power-on with a ~4 s retry budget while lamp cooldown is tens of seconds, so a fast power cycle left the room dark with one unconfirmed WARNING. Re-issues `POST /poweron` until every display reports `on`. Gated on `projector_power_on_on_start` as well as `enabled=`, so sites whose projector fleets are deliberately left dark are never commanded.
- **`/etc/cuems/cluster-poweroff.conf`** — single kill switch and tuning for both units above. Ships **`enabled=false`**: `cuems-common` installs identically on every host, so a fleet-wide upgrade must not change any site's behaviour until a box is opted in. `projector_timeout_s=45` is measured, not guessed — against an unreachable projector a status query costs 5 s and the power-off retries 19 s (test2, 2026-08-06), so the previous 25 s left one second of margin and would have truncated the stage and lost its log.
- **`nodes_off=` in `/etc/cuems/cluster-poweroff.conf`** (1.3.0-17) — chooses whether the controller also powers the cluster *nodes* down, or only the displays and itself. Defaults to `true`, so no site's behaviour changes. Added because `enabled=` was all-or-nothing and sala1 at Castillo Medina del Campo wants displays-off plus a controller shutdown while its node keeps running: with no knob, the only way to express that was to **withhold the controller's SSH key from the node**, encoding an operator decision as an authentication failure — invisible in config, indistinguishable from a fault in the journal (`Permission denied (publickey)`), silently reverted the day someone installs the key for good reasons, and costing the full `node_wait_s` on every power-off, because a node that stays up is polled to the deadline (measured on sala1: **+120 s on every power-button press**). Stage 2 now logs an explicit `SKIPPED — nodes_off=…` line, so a site that deliberately leaves its nodes up says so instead of looking broken. Accepts the same `true|yes|1|on` vocabulary as `enabled=`.
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

- **`check-ip.sh` is three gates** (1.3.0-23): `check-ip.sh ap` for `cuems-wifi.service` (the default, so the old call without arguments still works), `check-ip.sh dhcpd` for `isc-dhcp-server` and `check-ip.sh hostapd` for `hostapd`. Exit 0 proceeds, 1 skips quietly, 255 fails the unit and is returned only when `/etc/cuems/ap.conf` is missing outside `manual`. In `manual` the gates reproduce the previous units, the hostapd one standing in for the `Requisite=cuems-wifi.service` that was removed.
- **The AP no longer takes `ethernet0` down nor stops `dhclient`** (1.3.0-23). `cuems-wifi.service` runs `cuems-ap-path up`/`down` where it used to run `ip link set ethernet0 down`/`up`. A cable plugged in later still gets its lease; the AP stays up until the next reboot.
- **A laptop cabled straight into a controller no longer gets a lease from it** (1.3.0-23). `isc-dhcp-server` never serves on `bond0`. Deliberate, and a regression of the scenario documented for alquiler1.
- **`cuems-wifi.target`**: `Requires=isc-dhcp-server.service` is now `Wants=` (1.3.0-23) — the DHCP server's normal state on a wired boot is "not started".
- **`/etc/default/isc-dhcp-server`**: on a controller in a mode other than `manual`, the postinst and `cuems-net-mode apply` rewrite `INTERFACESv4` from `"bond0"` or empty to `"wifi0"` (1.3.0-23). It is another package's file; a backup is kept next to it as `.bak-cuems-net-mode`.
- Planning documents moved from `dev/planning/` to `Plans/`.

- **`gradient-motiond.service` → `cuems-gradient-motiond.service`** — renamed to match the `cuems-*` naming convention used by all other package-provided units. The binary path (`/usr/bin/gradient-motiond`) is unchanged — foreign binary names are not renamed on install.
- **All services migrated from `stagelab` to `cuems` user** — `cuems-controller-engine`, `cuems-editor`, `cuems-midiconnector`, `cuems-node-engine`, `cuems-videocomposer` all now declare `User=cuems Group=cuems`. The `cuems` system user is created by `preinst` and is not present in older installations; `preinst` is idempotent.
- **`jackd-cuems.service`**: replaced `alsa_out` USB audio bridging with `zita-j2a` via the new `jack-alsa-bridges.service`. `alsa_out` is deprecated in modern ALSA configurations and produced glitches under load.
- **`cuems-node-engine.service`**: added `Requires=jack-alsa-bridges.service` and `After=jack-alsa-bridges.service` so `AudioMixer.connect_to_jack()` runs only after USB JACK ports are registered. Without this ordering, the mixer skipped `usb_audio:playback_1/2` silently on fast-booting hardware.
- **User-facing scripts moved to `/usr/bin/`** — `cuems-healthcheck`, `cuems-config-node`, `cuems-stop`, `cuems-hdmi-audio-map`, and `cuems-ola-profile` are now in `/usr/bin/` (FHS-compliant for package-managed executables). They were previously in `/usr/local/bin/`.
- **`cuems-videocomposer.service`**: `ExecStart` now composes `$OPERATOR_FLAGS $OUTPUT_LATENCY_FLAG`, both sourced from independent `EnvironmentFile` blocks. A systemd drop-in that resets `ExecStart` must re-declare both variables to avoid silent flag loss.
- **`pkill` patterns in `cuems-node-engine.service`** updated from `audioplayer-cuems`/`dmxplayer-cuems` to `cuems-audioplayer`/`cuems-dmxplayer` following binary renames in the player packages.

### Fixed

- **`pkill` in `cuems-node-engine.service` kills only the player binaries** (1.3.0-24, 869evtdf7). `ExecStartPre`/`ExecStopPost` matched an unanchored substring, so every node-engine start and stop also SIGKILLed any `cuems`-owned `tail -f …/jack-volume.log`, `less …cuems-dmxplayer…` or `grep cuems-audioplayer` (and its own parent `sh -c`). The pattern is now anchored on argv[0]: `^([^ ]*/)?((cuems-audioplayer|cuems-dmxplayer|(cuems-)?jack-volume) |xjadeo .*--osc)`. A player installed under another binary name is no longer cleaned up by name; cuems-engine warns at start when a configured path has an unknown basename. Plan: `Plans/2026-10-07-engine-orphan-kill-eperm-aborts-load.md` (cuems-RELATIONS).
- **`isc-dhcp-server` served the AP subnet on the wired LAN** (1.3.0-23). It was never behind the AP gate; its only gate was `dhcpd.conf`'s subnet match, which opens exactly when `bond0` takes the fallback address.
- **A controller on the fallback address never asked for a lease again** (1.3.0-23) — see `cuems-net-guard` above.
- **The packaged AP could not start and could not carry traffic** (1.3.0-23), for three reasons each hidden by the previous one: nothing enabled `cuems-wifi.service`, so `hostapd`'s `Requisite=` failed on every boot; `ConditionFileNotEmpty=/run/cuems/hostapd.conf` was checked before the `ExecStartPre=` that renders that file; and the gateway address and the DHCP server stayed on `bond0` while `hostapd` took `wifi0` out of the bond. All fixed in `hostapd.service.d/cuems-wifi-group.conf` — the file Medina and formitgo shadow — leaving `20-cuems-config.conf` untouched.
- **`hostapd` ended `failed` after every stop** (1.3.0-23): its `ExecStopPost=ip link set wifi0 master bond0` hit `EPERM`, because bonding refuses to enslave an interface that is up.
- **Wired boots left `isc-dhcp-server` `failed`, `hostapd` with "Dependency failed" and the system `degraded`** (1.3.0-23). Both are now condition skips.
- **A transient `169.254.x` on `bond0` failed the AP gate closed** (1.3.0-23): the gate compared the whole IPv4 list of `bond0` to the gateway address.
- **`bond0` could be left without any IPv4** (1.3.0-23) when a recorded lease was tried on `TIMEOUT`, rejected and flushed.

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
