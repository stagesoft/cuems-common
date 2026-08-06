<!--
***
SPDX-FileCopyrightText: 2025 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# cuems-common

**Current release: v1.3.0-10** — see [`debian/changelog`](./debian/changelog) for the authoritative Debian release history.

**System-level Debian package delivering all shared configuration, systemd services, and operator tools for a CUEMS installation.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Debian bookworm](https://img.shields.io/badge/Debian-bookworm-A81D33.svg)](https://www.debian.org)

- **Source / issues:** [stagesoft/cuems-common](https://github.com/stagesoft/cuems-common) on GitHub

`cuems-common` is the configuration foundation of every CUEMS node and controller. It installs all systemd service units that form the node and controller service stacks, the network and kernel tuning required for real-time live-performance use, the JACK audio setup, the Apache2 reverse-proxy configuration, Avahi mDNS service templates for cluster node discovery, and the scripts operators use to initialise, diagnose, and shut down a running rig.

The package carries no compiled code of its own. Every executable it ships is a shell or Python script; the compiled daemons (`node-engine`, `controller-engine`, `cuems-videocomposer`, `gradient-motiond`, and others) are provided by their respective packages and only wired here into the systemd dependency graph.

It is composed of:

- **`etc/systemd/system/`** — systemd service, target, path, and socket units for both node and controller roles, plus service drop-ins for third-party units (Apache2, hostapd, Avahi, rtpmidid)
- **`usr/bin/`** — operator-facing tools: node provisioning, HDMI audio mapping, OLA DMX profile selection, system health check, and graceful shutdown
- **`usr/lib/cuems/bin/`** — internal service helpers called only from systemd units (latency extractor, IP check, WiFi automation)
- **`etc/cuems/`** — per-installation configuration files and XML schemas (network map, Avahi service templates)
- **`usr/share/cuems/`** — Avahi service group templates (firstrun / master / slave) and network interface templates
- **`etc/`** — kernel sysctl tuning, JACK daemon configuration, Apache2 site configuration, DHCP/hostapd WiFi AP configuration, ALSA, Avahi, rsyslog, logrotate, sudoers, tmpfiles, and modules-load drop-ins
- **`scripts/`** — test and validation scripts for systemd unit syntax, service dependency chains, and the OLA flock patch

---

## Table of Contents

- [Operator Quick Reference](#operator-quick-reference)
- [Overview](#overview)
- [Architecture](#architecture)
  - [systemd Targets and Role Model](#systemd-targets-and-role-model)
  - [Node Services](#node-services)
  - [Controller Services](#controller-services)
  - [Shared and Third-party Services](#shared-and-third-party-services)
  - [Operator Tools -- `/usr/bin`](#operator-tools----usrbin)
  - [Internal Helpers -- `/usr/lib/cuems/bin`](#internal-helpers----usrlibcuemsbin)
  - [Configuration and Data Files](#configuration-and-data-files)
  - [Test and Validation Scripts](#test-and-validation-scripts)
- [Core Concepts](#core-concepts)
- [Design Goals](#design-goals)
- [API Documentation](#api-documentation)
  - [Service Discovery -- Avahi mDNS](#service-discovery----avahi-mdns)
  - [IPC Ports](#ipc-ports)
  - [Apache Reverse Proxy](#apache-reverse-proxy)
  - [Operator Tool CLI Reference](#operator-tool-cli-reference)
  - [Shell Aliases](#shell-aliases)
  - [Environment and Configuration Variables](#environment-and-configuration-variables)
  - [Process Exit Codes](#process-exit-codes)
- [Installation](#installation)
  - [Debian Package](#debian-package)
  - [Build from Source](#build-from-source)
- [Development](#development)
- [Contributors](#contributors)
- [Release Notes](#release-notes)
- [Future Developments](#future-developments)
  - [Automated Test Suite and CI](#automated-test-suite-and-ci)
  - [Documentation Site](#documentation-site)
  - [Debian Release Workflow](#debian-release-workflow)
  - [Target Badge Set](#target-badge-set)
- [Copyright Notice](#copyright-notice)
- [License](#license)

---

## Operator Quick Reference

[↑ Back to Table of Contents](#table-of-contents)

Start here for the day-to-day operator docs shipped with the package. (Some of the
deeper reference sections below predate the 1.3.x feature set — the items here track
the current node/controller tooling.)

- **Default credentials (operator user, WiFi PSK, org SSH key):**
  [`docs/default-credentials.md`](docs/default-credentials.md) — shipped as known
  defaults on every fresh node and **must be rotated during deployment hardening**.
- **Node identity model (uuid / role_id / alias / hostname):**
  [`docs/node-identity-contract.md`](docs/node-identity-contract.md).
- **WiFi-AP firewall fence (opt-in nftables):**
  [`usr/share/doc/cuems-common/firewall.README`](usr/share/doc/cuems-common/firewall.README)
  (`/usr/share/doc/cuems-common/firewall.README` on an installed host).
- **OLA / DMX install procedure:** [`docs/ola-install.md`](docs/ola-install.md).
- **Latency tuning:** [`docs/latency-tuning.md`](docs/latency-tuning.md).
- **Cluster journal access:** `cuems-logs` — semantic node/level/component filters
  over the merged cluster journal (run `cuems-logs --help`).

---

## Overview

[↑ Back to Table of Contents](#table-of-contents)

CUEMS is a distributed live-performance cue management system. A CUEMS installation consists of one **controller** machine and one or more **node** machines connected over a dedicated LAN. The controller holds the cue timeline and the web editor; each node runs the audio, video, DMX, and MIDI playback engines.

`cuems-common` wires both roles together via systemd targets and drop-ins, and places all shared system configuration on every machine regardless of role. Role selection at runtime is automatic: the presence of `/etc/cuems/master.lock` is monitored by a `systemd.path` unit, which activates `cuems-controller.target` only on the controller.

```
  CONTROLLER (one per installation)
  ┌─────────────────────────────────────────────────────────────┐
  │  cuems-controller.target                                    │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │ cuems-controller-engine  (_cuems_nodeconf._tcp :9000) │  │
  │  │ cuems-editor             (cuems-editor backend)       │  │
  │  │   └─ Apache2  :80/:443   (WebSocket reverse proxy)    │  │
  │  │ cuems-midiconnector      (MIDI I/O bridge)            │  │
  │  └───────────────────────────────────────────────────────┘  │
  │  cuems-node.target  (controller also runs the full node     │
  │  stack for its own local playback)                          │
  │  cuems-wifi.target  (hostapd + isc-dhcp-server AP)          │
  └───────────────────────────┬─────────────────────────────────┘
                              │  Avahi mDNS  →  controller.local
              ┌───────────────┼────────────────────┐
              │ OSC :9090     │ NNG :9093     │ WS :9092/:9190
              ▼               ▼               ▼
  NODE(S)  (one or more, connected over the CueMS LAN)
  ┌─────────────────────────────────────────────────────────────┐
  │  cuems-node.target                                          │
  │  cuems-nodeconf       (root; configures network / Avahi)    │
  │  cuems-hdmi-audio-map (oneshot; DRM → ALSA mapping)         │
  │  jackd-cuems          (real-time JACK audio server)         │
  │  jack-alsa-bridges    (zita-j2a USB audio bridge)           │
  │  cuems-node-engine    (playback dispatcher)                 │
  │  cuems-videocomposer  (multi-layer video compositor)        │
  │  cuems-gradient-motiond (NNG fade engine ← controller.local)│
  │  olad                 (OLA DMX daemon)                      │
  └─────────────────────────────────────────────────────────────┘
```

- **`cuems-node.target`** groups all services that every machine (including the controller) must run for local playback.
- **`cuems-controller.target`** requires and extends `cuems-node.target` with the scheduling engine, editor, and MIDI connector. It is activated automatically on the machine that holds `/etc/cuems/master.lock`.
- **`cuems-wifi.target`** brings up the controller's WiFi access point (hostapd + isc-dhcp-server) so nodes and operator devices can connect wirelessly.
- All CUEMS daemons run under the `cuems` system user (created by `preinst`). They share `/tmp/cuems` for NNG IPC sockets (which requires `PrivateTmp=no` on every unit).

---

## Architecture

[↑ Back to Table of Contents](#table-of-contents)

### systemd Targets and Role Model

Three systemd targets ship in this package and define the operational roles:

| Unit | Description | `WantedBy` |
|---|---|---|
| `cuems-node.target` | Base node service group — every machine | `multi-user.target` |
| `cuems-controller.target` | Controller extensions — requires `cuems-node.target` | `multi-user.target` |
| `cuems-wifi.target` | WiFi AP group — `PartOf=cuems-controller.target` | `multi-user.target` |

Role detection is automatic. `cuems-controller.path` monitors `/etc/cuems/master.lock`; when that file appears (placed by the operator during node provisioning), it activates `cuems-controller.target` without a reboot.

### Node Services

These units are `WantedBy=cuems-node.target` and start on every machine.

| Service | Type | User | Role |
|---|---|---|---|
| `cuems-hdmi-audio-map.service` | oneshot | root | Reads DRM connector-to-CRTC assignments via ioctl, maps each CRTC pipe to its HDA HDMI ALSA device (`hw:PCH,{3,7,8}`), and writes `/etc/asound.conf`. Runs before `jackd-cuems`. |
| `jackd-cuems.service` | simple | cuems (group audio) | JACK Audio Connection Kit server. Reads daemon arguments from `/etc/default/jack`. Runs with `FIFO` CPU scheduler at priority 10 and unlimited `MEMLOCK` / `RTPRIO`. |
| `jack-alsa-bridges.service` | simple | cuems (group audio) | Waits for JACK to be ready, restores USB audio mixer state via `alsactl`, then starts `zita-j2a` to bridge `hw:HID,0` (USB audio) into JACK as the `usb_audio` client. On start-up connects `0_mixer:output_7/8` to `usb_audio:playback_1/2`. |
| `cuems-nodeconf.service` | notify | root | Runs as root because it writes to `/etc/network/interfaces`, `/etc/avahi/services/`, and controls other systemd units via D-Bus. Signals readiness to systemd via `sd_notify`. |
| `cuems-node-engine.service` | simple | cuems | Main playback dispatcher. Requires the full JACK stack (`jackd-cuems` + `jack-alsa-bridges`). `ExecStartPre` kills orphaned player processes from a prior run; `ExecStopPost` repeats that cleanup. Uses `LD_LIBRARY_PATH` to locate the rtmidi native library. |
| `cuems-videocomposer.service` | simple | cuems (groups video, render, audio) | Multi-layer video compositor. `ExecStartPre` runs `cuems-extract-video-latency` to write `/run/cuems/videocomposer.env`; the ExecStart line sources `$OUTPUT_LATENCY_FLAG` from that file and `$OPERATOR_FLAGS` from `/etc/cuems/videocomposer-flags.env`. `PrivateDevices=no` is required for DRI/DRM access. |
| `cuems-gradient-motiond.service` | simple | cuems (group audio) | Fade/gradient motion engine. Connects to the NNG publish-subscribe hub on `tcp://controller.local:9093`. Requires Avahi for mDNS resolution of `controller.local`. |
| `olad.service` | simple | olad | OLA (Open Lighting Architecture) daemon for DMX output. Runs as the `olad` system user with `dialout` and `plugdev` supplementary groups for USB DMX devices. Config dir: `/etc/ola`. |

### Controller Services

These units are `WantedBy=cuems-controller.target` and run only on the controller.

| Service | Type | User | Role |
|---|---|---|---|
| `cuems-controller-engine.service` | simple | cuems | Central scheduling and command engine. Requires Avahi for node discovery. Announces itself on `_cuems_nodeconf._tcp` (port 9000) and `_cuems_osc._tcp` (port 9090). |
| `cuems-editor.service` | simple | cuems | Web editor backend. Requires `cuems-controller-engine` and `apache2`. Creates a `RuntimeDirectory=cuems-editor` for its PID file. Restarts automatically on failure. |
| `cuems-midiconnector.service` | simple | cuems (group audio) | MIDI I/O bridge. Requires `cuems-controller.target`. Provides MIDI connectivity for MTC and show control. |

### Shared and Third-party Services

| Service | Role |
|---|---|
| `cuems-wifi.service` | Oneshot WiFi AP setup. `ExecCondition=/usr/lib/cuems/bin/check-ip.sh` guards activation: the service only runs when bond0 has the static AP address and `ethernet0` is disconnected. Calls `ip link set ethernet0 down` to release the interface for the AP. |
| `hostapd.service` | WiFi access point daemon. `PartOf=cuems-wifi.target`, starts after `cuems-wifi.service`. Reads `/etc/hostapd/hostapd.conf`. |
| `cuems-hdmi-audio-map.service` | HDMI audio oneshot (see [Node Services](#node-services)). |
| `rsync@.service` + `rsync.socket` | Socket-activated rsync daemon. Used for media library synchronisation between controller and nodes. Config: `/etc/rsyncd.conf`. |

Drop-in overrides (`*.service.d/`) are also installed for:
- `apache2.service.d/cuems-controller-group.conf` — adds apache2 to the `cuems-controller.target` service group
- `avahi-daemon.d/cuems-node-group.conf` — adds avahi-daemon to `cuems-node.target`
- `hostapd.service.d/cuems-wifi-group.conf`, `isc-dhcp-server.service.d/cuems-wifi-group.conf` — bind third-party services into the WiFi target group
- `rtpmidid.service.d/cuems-node-group.conf` — adds rtpmidid to the node group

Pipewire, pipewire-pulse, and wireplumber are **masked system-wide** via `/etc/systemd/user/*.service → /dev/null` symlinks. This prevents the per-user Pipewire session from racing `zita-j2a` for `hw:HID` (the USB audio device), which would otherwise cause `JackAudioDriver::ProcessGraphAsyncMaster` errors and silently unwire the USB audio mixer.

### Operator Tools — `/usr/bin`

| Script | Language | Role |
|---|---|---|
| `cuems-config-node` | Python 3 | Reads the MAC address of `ethernet0` and generates a new UUID. In `test` mode writes modified files to the current directory for inspection; in `write` mode applies them to the system. Files modified: `/etc/cuems/settings.xml` (mac + uuid elements), `/usr/share/cuems/cuems.service.{firstrun,master,slave}` (uuid TXT records), `/etc/avahi/avahi-daemon.conf` (host-name, IPv4/IPv6 flags, deny-interfaces), `/etc/hostname`, `/etc/hosts`. |
| `cuems-hdmi-audio-map` | Python 3 | Detects the runtime DRM connector → GPU CRTC → ALSA device mapping via direct DRM ioctls on `/dev/dri/card0`. Generates a three-slot `multi_hdmi` PCM definition in `/etc/asound.conf` so JACK always uses a stable 6-channel device regardless of boot-time connector assignment. Accepts `--dry-run` / `-n` to print the config without writing it. |
| `cuems-ola-profile` | bash | Enables OLA DMX hardware profiles by toggling `/etc/ola/*.conf` files and restarting `olad`. Profiles: `pro` (Enttec USB Pro / DMXking), `opendmx` (Enttec Open DMX, FTDI-based), `artnet` (network-only), `sacn` (network-only). Handles the `ftdi_sio` kernel module blacklist required by the `opendmx` profile. After applying, lists enabled plugins with supported hardware models. |
| `cuems-healthcheck` | bash | Polls `systemctl is-active` for the core CUEMS services, checks disk usage against a 90 % threshold, and logs results to `/var/log/cuems-health.log`. Exits 0 when all checks pass, 1 when any check fails. |
| `cuems-cluster-poweroff` | bash | Orderly cluster power-off, run as the `ExecStop=` of `cuems-cluster-poweroff.service` so it fires during a poweroff transition (power button via logind, or `systemctl poweroff`). Projectors off over PJLink → cluster node(s) off over SSH → wait until really down → hand back to systemd. Drives the installed `cuems-power-bridge` library, so it duplicates no protocol logic and honours that host's `power-bridge.conf`. Skips on a reboot, self-excludes this host from the node list, and is idempotent. Gated by `enabled=` in `/etc/cuems/cluster-poweroff.conf` (ships `false`). Replaced the retired `cuems-stop`. |
| `cuems-displays-on` | bash | Boot-time confirmation that the projectors actually came on: polls the bridge's `GET /status` and re-issues `POST /poweron` until every display reports `on`. Exists because the bridge's own `projector_power_on_on_start` gets one attempt with a ~4 s retry budget while lamp cooldown is tens of seconds. Gated by `enabled=` **and** `projector_power_on_on_start`. |

### Internal Helpers — `/usr/lib/cuems/bin`

| Script | Called from | Role |
|---|---|---|
| `cuems-extract-video-latency` | `cuems-videocomposer.service` ExecStartPre | Reads `videoplayer/output_latency_ms` from `settings.xml` (path: `$CUEMS_CONF_PATH/settings.xml` or `/etc/cuems/settings.xml`). Writes `OUTPUT_LATENCY_FLAG=--output-latency-ms N` (integer case) or `OUTPUT_LATENCY_FLAG=` (auto / absent / missing) to `/run/cuems/videocomposer.env`. Graceful degradation on missing or malformed XML. |
| `check-ip.sh` | `cuems-wifi.service` ExecCondition | Tests whether bond0 holds the static WiFi AP address (`192.168.6.1`) and `ethernet0` is disconnected. Returns 0 (proceed), 1 (inhibit), or 255 (no IP at all). |
| `wifi-auto.sh` | Manual / operator | Stops `isc-dhcp-server`, brings down the WiFi interface, then brings it up on the `wifi-out` profile for an external network connection. |

### Configuration and Data Files

| Path | Role |
|---|---|
| `/etc/cuems/settings.xml` | Per-node settings: UUID, MAC address, player latencies (`output_latency_ms` for video, audio, DMX). Authoritative source for `cuems-extract-video-latency`. |
| `/etc/cuems/network_map.xml` | Cluster topology: one `CuemsNode` element per machine with uuid, mac, name, node_type, ip, port, online fields. Validated against `network_map.xsd` (namespace `https://stagelab.coop/cuems/`). |
| `/etc/cuems/network_map.xsd` | XML Schema for `network_map.xml`. `NodeType` requires uuid, mac, name, node_type, ip, port, and online (BoolType: `True`/`False`). |
| `/etc/default/jack` | JACK daemon arguments. Default: `-R -dalsa -dmulti_hdmi -r48000 -p512 -n3` (real-time, ALSA backend, `multi_hdmi` PCM, 48 kHz, 512-frame period, 3 periods). `multi_hdmi` is generated by `cuems-hdmi-audio-map`. |
| `/etc/cuems/videocomposer-flags.env` | Operator-tunable extra CLI flags for `cuems-videocomposer`. Set `OPERATOR_FLAGS=--verbose` or any supported flag. Do **not** set `--output-latency-ms` here — that value is managed via `settings.xml`. |
| `/run/cuems/videocomposer.env` | Machine-generated by `cuems-extract-video-latency` on every `cuems-videocomposer.service` start. Contains `OUTPUT_LATENCY_FLAG=` (may be empty). Ephemeral (lives on tmpfs). |
| `/etc/avahi/services/cuems.service` | Active Avahi service group. Announces `_cuems_nodeconf._tcp` on port 9000 and `_cuems_osc._tcp` on port 9090, both carrying `node_type` and `uuid` TXT records. Swapped between firstrun / master / slave templates by `cuems-config-node` or `cuems-nodeconf`. |
| `/usr/share/cuems/cuems.service.{firstrun,master,slave}` | Avahi service group templates. Differ only in `node_type` TXT record. Updated by `cuems-config-node write` to embed the correct UUID. |
| `/usr/share/cuems/interfaces.{master,node}` | Network interface templates. Master: bonded `bond0` over `ethernet0` + `wifi0` (active-backup, primary ethernet0) + link-local `ethernet1`. Node: bridged `bridge0` over `ethernet0` + `ethernet1` (link-local), static `wifi0` at `192.168.6.1/24`. |
| `/etc/sysctl.d/99-cuems-performance.conf` | Kernel tuning: larger socket/dgram queues (`net.core.somaxconn`, `net.unix.max_dgram_qlen`), reduced swap pressure (`vm.swappiness=10`), CFS scheduling parameters for low-latency audio, `ip_forward=1` for the WiFi AP NAT path, high inotify watch limit. |
| `/etc/sudoers.d/99-cuems` | Minimal passwordless sudo for the `cuems` user: `systemctl reload avahi-daemon.service` and copying the three Avahi service templates to `/etc/avahi/services/cuems.service`. |
| `/etc/modules-load.d/cuems-midi.conf` | Ensures `snd-seq` and `snd-seq-dummy` are loaded at boot so that `/dev/snd/seq` exists when `cuems-midiconnector` (rtmidi) starts. |
| `/etc/tmpfiles.d/cuems-tmp.conf` | Creates `/tmp/cuems` at boot with mode `0775`, owned `stagelab:stagelab`, for NNG IPC sockets shared between services. |
| `/etc/tmpfiles.d/jack-cuems.conf` | Excludes JACK shared-memory objects (`/dev/shm/jack_*`) from tmpfiles cleanup to prevent IPC loss during long sessions. |
| `/etc/logrotate.d/cuems` | Daily rotation of `/var/log/cuems.log` and `/var/log/cuems-config.log`, 30 days retention, compressed with delay, SIGHUP to rsyslog on rotate. |

### Test and Validation Scripts

| Script | Role |
|---|---|
| `scripts/test-systemd-units.sh` | Validates every `*.service`, `*.path`, `*.socket`, and `*.timer` file in `etc/systemd/system/` using `systemd-analyze verify`. Reports pass / warning / fail per unit with structured output. |
| `scripts/test-systemd-deps.sh` | Static analysis of service dependency chains (default) or live start/stop tests (`--live` flag). Verifies node-expected and controller-expected services are `PartOf` the correct targets and that controller-only services do not appear in node-role `Requires`. |
| `scripts/validate-systemd.sh` | Quick validation script that writes a timestamped report to `/tmp/cuems-systemd-validation-*.txt`. |
| `scripts/test-ola-flock-patch.sh` | Verifies that the CUEMS-patched OLA build (`0.10.9.nojsmin-2+cuems2`) compiled in `flock()` support, exports the `AcquireLockAndOpenSerialPort` symbol, and correctly handles the UUCP self-lock race condition. Requires a patched OLA installation. |
| `scripts/verify-package-structure.sh` | Checks that all files listed in `debian/install` exist in the repository tree. |
| `scripts/verify-python-paths.sh` | Checks that `/usr/lib/cuems/bin/python3` wrapper resolves and is executable. |

---

## Core Concepts

[↑ Back to Table of Contents](#table-of-contents)

- **Controller / Node role model.** Every machine runs `cuems-node.target`. The controller additionally activates `cuems-controller.target` (detected automatically via `cuems-controller.path` watching `/etc/cuems/master.lock`). The controller is therefore always also a node with its own local playback stack.

- **cuems system user.** All CUEMS daemons run as the `cuems` unprivileged system user (home `/var/lib/cuems`, no login shell). The user is created by the `preinst` script and added to the `video`, `render`, and `audio` supplementary groups. The only exception is `cuems-nodeconf`, which runs as root because it must configure kernel network interfaces, Avahi service files, and systemd units via D-Bus.

- **NNG IPC over `/tmp/cuems`.** Intra-node and controller-to-node IPC uses the NNG messaging library with socket files in `/tmp/cuems`. All units set `PrivateTmp=no` so they share the same `/tmp` namespace. The directory is pre-created at boot by `tmpfiles.d/cuems-tmp.conf`.

- **Avahi mDNS for node discovery.** The controller announces itself as `controller.local` via Avahi. Service type `_cuems_nodeconf._tcp` on port 9000 carries `node_type` and `uuid` TXT records. Nodes discover the controller purely by mDNS; no static IP configuration is needed beyond the LAN setup.

- **JACK audio stack.** Every node runs a single JACK server on the `multi_hdmi` virtual ALSA device (a 6-channel `pcm.multi` aggregating up to three HDMI/DP output pairs). `cuems-hdmi-audio-map` generates this device definition at every boot by reading the current DRM connector assignments, ensuring stable JACK channel numbering regardless of GPU pipe reordering.

- **MTC-driven latency compensation.** All playback engines (audio, video, DMX) receive a MIDI Timecode clock and advance by a pre-set `output_latency_ms` compensation so that audio, video, and lighting arrive at the output hardware at the same wall-clock instant. Compensation values are stored in `settings.xml` and are per-node, per-pipeline.

- **Debian package as system state.** `cuems-common` installs files under `/etc/` that are intended to be further edited per-installation (hostapd SSID, DHCP ranges, network interfaces). The Debian packaging preserves site-local edits via `dpkg`'s `conffile` mechanism.

---

## Design Goals

[↑ Back to Table of Contents](#table-of-contents)

- **Role auto-detection, not manual configuration.** The single mechanism — `cuems-controller.path` watching `/etc/cuems/master.lock` — determines which systemd target is active. The same `.deb` installs on every machine; operators do not toggle service enables by role.

- **Strict separation of operator-tunable and machine-generated state.** Operator settings live in `/etc/cuems/settings.xml` (hand-edited, version-controlled per rig). Machine-generated runtime state (e.g. `/run/cuems/videocomposer.env`) lives on tmpfs and is recreated on every service start. The two paths never collide.

- **Composable service arguments.** `cuems-videocomposer.service` sources two independent `EnvironmentFile` blocks — one machine-generated (`OUTPUT_LATENCY_FLAG`) and one operator-tunable (`OPERATOR_FLAGS`). Each flag source is independent; adding a new flag to either block does not require updating a systemd drop-in that would need to re-declare all other flags.

- **Minimum privilege by default.** All services run with `NoNewPrivileges=yes`, `ProtectSystem=full`, `ProtectHome=read-only`, and only the `ReadWritePaths` they strictly need. The sole exception (root for `cuems-nodeconf`) is documented and constrained: the `sudoers` drop-in limits the `cuems` user to the exact `systemctl reload` and `cp` operations needed for Avahi role switching.

- **Boot-time determinism for real-time audio.** `cuems-hdmi-audio-map` generates the ALSA multi-device before JACK starts. `cuems-modules-load.d` loads `snd-seq` deterministically at boot rather than relying on on-demand kernel module loading. `jack-alsa-bridges` waits for JACK readiness with a timed poll loop before starting USB audio bridging and wiring JACK ports.

- **Pipewire/Wireplumber suppression.** Masking the per-user Pipewire units system-wide is a deliberate, documented choice: Pipewire's device adoption races with `zita-j2a` on the USB audio interface, causing non-deterministic JACK failures that are silent from the operator's perspective.

- **Patched OLA for stable DMX.** The upstream OLA UUCP serial-port locking has a self-lock race that surfaces after long uptime (> 21 h). `cuems-common` ships a patched `olad.service` expecting the CUEMS-patched OLA package (`flock()`-based locking) and a test suite to verify the patch is installed.

---

## API Documentation

[↑ Back to Table of Contents](#table-of-contents)

The external surface of `cuems-common` is the collection of network services it starts, the operator CLI tools it installs, and the configuration paths it defines. There is no library or language-level API.

### Service Discovery — Avahi mDNS

The controller advertises two mDNS service types via `/etc/avahi/services/cuems.service`:

| Service type | Port | TXT records | Purpose |
|---|---|---|---|
| `_cuems_nodeconf._tcp` | 9000 | `node_type=master`, `uuid=<node-uuid>` | Node configuration and cluster membership |
| `_cuems_osc._tcp` | 9090 | `node_type=master`, `uuid=<node-uuid>` | OSC control protocol |

Nodes browse for `_cuems_nodeconf._tcp` to locate the controller. The `uuid` TXT record identifies the controller uniquely across installations. The hostname is set to the controller's MAC address (without colons) by `cuems-config-node`.

### IPC Ports

| Port | Protocol | Direction | Service |
|---|---|---|---|
| 9000 | TCP | Controller ← Nodes | `cuems-controller-engine` nodeconf/cluster management |
| 9090 | TCP (OSC) | Controller ← Nodes / Operators | OSC control; also proxied by Apache to the editor |
| 9092 | TCP (WebSocket) | Controller ← Browser | `cuems-editor` control and upload WebSocket |
| 9093 | TCP (NNG) | Controller → Nodes | NNG publish hub; `cuems-gradient-motiond` subscribes on each node |
| 9190 | TCP (WebSocket) | Controller ← Browser | `cuems-editor` realtime WebSocket |

Port 9093 is a CUEMS-wide constant (the NNG hub port of `cuems-controller-engine`). It can be overridden per-node by creating a systemd drop-in for `cuems-gradient-motiond.service`:

```ini
# /etc/systemd/system/cuems-gradient-motiond.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/gradient-motiond --nng-url tcp://controller.local:XXXX
```

### Apache Reverse Proxy

`cuems-common` installs Apache2 virtual-host configurations for both HTTP (port 80) and HTTPS (port 443, self-signed certificate) that proxy all WebSocket traffic from the browser to the locally-running `cuems-editor` backend:

| Proxy path | Backend | Purpose |
|---|---|---|
| `/realtime` | `ws://127.0.0.1:9190/` | Editor realtime push stream |
| `/upload` | `ws://127.0.0.1:9092/upload` | Media upload WebSocket |
| `/ws` | `ws://127.0.0.1:9092/` | Editor control WebSocket (supports query-string session rewriting) |

The HTTPS virtual host uses `/etc/ssl/certs/apache-selfsigned.crt` and `/etc/ssl/private/apache-selfsigned.key`, which the operator must generate before enabling the SSL site. The HTTP virtual host serves `DocumentRoot /var/www` with `DirectoryIndex index.html` (the editor's static assets).

### Operator Tool CLI Reference

#### `cuems-config-node`

```
cuems-config-node test   # Preview all changes in the current directory
cuems-config-node write  # Apply changes to system files
```

Reads the MAC of `ethernet0` and generates a new UUID (uuid1). Prints both before writing. No interactive confirmation for `write` — verify with `test` first.

**Exit codes:** 0 on success, non-zero if a required file is unreadable or Python exceptions propagate.

#### `cuems-hdmi-audio-map`

```
cuems-hdmi-audio-map             # Write /etc/asound.conf
cuems-hdmi-audio-map --dry-run   # Print asound.conf to stdout; do not write
cuems-hdmi-audio-map -n          # Same as --dry-run
```

Always generates exactly 3 slots (6 channels) regardless of how many displays are connected, to keep JACK channel numbering stable. Exits 1 if no HDMI/DP outputs are detected.

**Exit codes:** 0 on success, 1 if no audio-capable connectors are found.

#### `cuems-ola-profile`

```
cuems-ola-profile [--add] <profile> [<profile>...]

Profiles:
  pro       Enttec DMX USB Pro, DMXking USB DMX512-A/Ultra/Micro
  opendmx   Enttec Open DMX USB (FTDI bit-banged)
  artnet    Network-only (ArtNet + sACN; always enabled by any profile)
  sacn      Network-only (sACN; always enabled by any profile)

Flags:
  --add     Add profiles to current config without resetting all plugins first
```

`pro` and `opendmx` are mutually exclusive (usbpro vs ftdidmx kernel driver conflict). ArtNet (`ola-artnet.conf`) and sACN (`ola-e131.conf`) are always enabled regardless of profile. After applying, lists enabled plugins with supported hardware models and registered devices.

**Exit codes:** 0 on success, 1 on profile conflict or unknown profile.

#### `cuems-healthcheck`

```
cuems-healthcheck
```

Checks: `cuems-controller-engine`, `cuems-node-engine`, `cuems-videocomposer`, `jackd-cuems`, `avahi-daemon`. Appends timestamped log lines to `/var/log/cuems-health.log`.

**Exit codes:** 0 all systems healthy, 1 one or more checks failed.

#### `cuems-cluster-poweroff`

```
cuems-cluster-poweroff [--force]
```

Normally invoked only by systemd, as the `ExecStop=` of
`cuems-cluster-poweroff.service`. Sequence: displays off (PJLink) → cluster node(s)
off (SSH) → wait until unreachable → return, leaving systemd to power this controller
off. `--force` runs it outside a poweroff transaction for rehearsal; pair that with
`dry_run = true` in `power-bridge.conf` for a zero-risk full-fidelity run.

Guards worth knowing before touching it:

- **Poweroff-only.** It inspects `systemctl list-jobs` and does nothing unless a
  `poweroff.target`/`halt.target` job is in the transaction. A reboot is skipped
  deliberately: PJLink answers `ERR3` to `POWR 1` during lamp cooldown, so powering the
  lamps off on a reboot would return to a dark room.
- **Self-exclusion.** A standalone controller is its own node, so a `NodeType.slave`
  self-entry in `network_map.xml` would otherwise make it SSH `poweroff` to itself —
  and a host can never observe *itself* unreachable, so it would then burn the whole
  `node_wait_s` every time. Matching is by node uuid (from `settings.xml`) and by exact
  local-address membership, **not** by hostname: with `cuems-nodeconf` disabled the OS
  hostname is e.g. `cupula1` while the avahi name is `node01.local`.
- **Idempotent.** Display state and node liveness are queried first, so a second pass
  costs seconds instead of repeating the work. This matters because a bridge-driven
  `POST /shutdown` ends in `sudo /sbin/poweroff`, which re-enters this script.

Every run logs an *ordering probe* (whether the bridge has already stopped, whether
avahi and networking are still up), including on the skip paths — so an ordinary
`systemctl reboot` permanently certifies the unit's shutdown ordering at no cost.

**Not covered:** `systemctl poweroff --force` skips every unit's orderly stop, so no
`ExecStop` runs and the projectors and nodes stay up.

**Exit codes:** always 0 — nothing here may wedge a poweroff. Failures are logged.

#### `cuems-displays-on`

```
cuems-displays-on
```

Invoked by `cuems-displays-on.service` at boot. No arguments; cadence and gating come
from `/etc/cuems/cluster-poweroff.conf` plus `projector_power_on_on_start` in
`power-bridge.conf`.

**Exit codes:** always 0.

### Shell Aliases

Installed via `/etc/profile.d/cuems.sh` (sourced by every login shell):

| Alias | Equivalent command |
|---|---|
| `cuems-restart` | `sudo systemctl restart cuems-node.target cuems-controller.target` |
| `cuems-start` | `sudo systemctl start cuems-node.target cuems-controller.target` |
| `cuems-stop` | `sudo systemctl stop cuems-controller.target cuems-node.target` |
| `cuems-status` | `systemctl status cuems-node.target cuems-controller.target` |

Note: `cuems-stop` is now unambiguously the alias above. The `/usr/bin/cuems-stop` binary it used to shadow — a rig shutdown hardcoded to a long-gone venue's relay and SSH targets — was retired in 1.3.0-16; orderly cluster power-off is now `cuems-cluster-poweroff`, driven by systemd rather than run by hand.

### Environment and Configuration Variables

| Variable / Path | Scope | Default | Description |
|---|---|---|---|
| `CUEMS_CONF_PATH` | `cuems-videocomposer.service` env | `/etc/cuems/` | Override the directory containing `settings.xml`. Set via `systemctl edit cuems-videocomposer` if the installation uses a non-default config path. |
| `OUTPUT_LATENCY_FLAG` | `cuems-videocomposer.service` | `""` (auto) | Generated by `cuems-extract-video-latency`. `--output-latency-ms N` when `settings.xml` has an integer, empty otherwise. |
| `OPERATOR_FLAGS` | `cuems-videocomposer.service` | `""` | Operator-set extra flags (e.g. `--verbose`). Written to `/etc/cuems/videocomposer-flags.env`. |
| `DAEMON_ARGS` | `jackd-cuems.service` | `-R -dalsa -dmulti_hdmi -r48000 -p512 -n3` | JACK daemon arguments. Edited in `/etc/default/jack`. |
| `DAEMON_CONF` | `hostapd.service` | `/etc/hostapd/hostapd.conf` | hostapd configuration file path. |

### Process Exit Codes

| Tool | Exit code | Meaning |
|---|---|---|
| `cuems-healthcheck` | 0 | All service and disk checks passed |
| `cuems-healthcheck` | 1 | One or more checks failed; see `/var/log/cuems-health.log` |
| `cuems-hdmi-audio-map` | 0 | asound.conf written successfully |
| `cuems-hdmi-audio-map` | 1 | No HDMI/DP audio outputs detected; asound.conf unchanged |
| `cuems-ola-profile` | 0 | Profile applied and olad restarted |
| `cuems-ola-profile` | 1 | Conflicting profiles or unknown profile name |
| `check-ip.sh` | 0 | WiFi AP condition met; service should start |
| `check-ip.sh` | 1 | Ethernet is connected; AP should not start |
| `check-ip.sh` | 255 | No IP address on bond0; condition unknown |

---

## Installation

[↑ Back to Table of Contents](#table-of-contents)

### Debian Package

`cuems-common` targets Debian 12 (bookworm). Install the pre-built package:

```bash
sudo dpkg -i cuems-common_1.0.0-1_all.deb
sudo apt-get install -f   # resolve any missing dependencies
```

The package declares these runtime dependencies (installed automatically via `apt-get install -f`):

```
cuems-utils (>= 1.0.0)   python3   systemd
apache2      openssl      avahi-daemon
isc-dhcp-server           hostapd
rsync        iproute2     zita-ajbridge
```

The `preinst` script creates the `cuems` system user and group, assigns it to `video`, `render`, and `audio` supplementary groups, and creates `/var/lib/cuems`. The `postinst` script:

1. Marks scripts in `/usr/lib/cuems/bin/` executable.
2. Reloads systemd daemon.
3. Enables `loginctl linger` for the `cuems` user (prevents systemd-logind from destroying IPC resources on logout).
4. Stops any running pipewire/wireplumber instances across all logged-in users so the `/dev/null` masks take effect immediately.
5. Sets `600` permissions on `/etc/rsyncd.secrets` and `440` on `/etc/sudoers.d/99-cuems`.

After installation, enable the appropriate systemd target for each machine's role:

```bash
# Every machine (node + controller):
sudo systemctl enable cuems-node.target

# Controller machine only:
sudo systemctl enable cuems-controller.target

# Reboot (or start targets manually):
sudo systemctl start cuems-node.target
```

The controller role activates automatically once `/etc/cuems/master.lock` exists (watched by `cuems-controller.path`). Enable the path unit on the intended controller:

```bash
sudo systemctl enable --now cuems-controller.path
```

### Build from Source

The workspace `Makefile` at the repository root builds `cuems-common` as a Debian package. It automatically checks out the `debian/bookworm` branch into a temporary git worktree under `/tmp/cuems-build/`, then runs `debuild`:

```bash
# From the parent workspace root (one level above cuems-common/):
make cuems-common
# Output .deb is placed in rc1_packages/

# Increment the Debian revision before building:
make cuems-common BUMP=1

# Force a clean build (no -nc debuild flag):
make cuems-common CLEAN=1

# Set an explicit version:
make cuems-common VERSION=1.0.1-1
```

To build manually without the workspace Makefile:

```bash
cd cuems-common
git checkout debian/bookworm
debuild -b -uc -us
```

---

## Development

[↑ Back to Table of Contents](#table-of-contents)

### Repository layout

```
cuems-common/
├── debian/              Debian packaging (control, install, postinst, preinst, rules)
├── docs/                Operator runbooks (latency-tuning.md, ola-install.md)
├── etc/                 All system configuration files installed verbatim
│   ├── systemd/system/  Service, target, path, socket units and drop-ins
│   ├── cuems/           Network map schema and runtime config templates
│   └── ...
├── scripts/             Test and validation scripts
├── splash/              Plymouth boot splash assets
├── usr/
│   ├── bin/             Operator-facing tools
│   ├── lib/cuems/bin/   Internal service helpers
│   └── share/cuems/     Avahi templates and network interface templates
└── Makefile             Workspace-wide CUEMS package build system
```

### Running the test suite

The test scripts require a live systemd environment and the package installed. They can be run from the repository root:

```bash
# Validate systemd unit file syntax and structure:
bash scripts/test-systemd-units.sh

# Validate service dependency chains (static analysis, no side effects):
bash scripts/test-systemd-deps.sh

# Live dependency test (prompts before starting/stopping services):
bash scripts/test-systemd-deps.sh --live

# Verify OLA flock patch (requires patched OLA installed):
bash scripts/test-ola-flock-patch.sh

# Verify package file structure matches debian/install:
bash scripts/verify-package-structure.sh
```

### Modifying systemd units

Unit files in `etc/systemd/system/` are installed to `/lib/systemd/system/` on the target system. To apply changes during development without reinstalling the package, copy the modified unit and reload:

```bash
sudo cp etc/systemd/system/cuems-node-engine.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart cuems-node-engine.service
```

### Shell script linting

All shell scripts should pass `bash -n` (syntax check). For a stricter check, `shellcheck` is recommended:

```bash
shellcheck scripts/*.sh usr/bin/cuems-cluster-poweroff usr/bin/cuems-displays-on usr/bin/cuems-ola-profile usr/bin/cuems-healthcheck
```

### Debian packaging

The `debian/install` file maps every source path to its installation destination. When adding a new file, add a line to `debian/install`. If the file is a script that must be executable, add a `chmod +x` call to `debian/postinst` or use `dh_fixperms`.

---

## Contributors

[↑ Back to Table of Contents](#table-of-contents)

Contributions are welcome. Please read [CONTRIBUTORS.md](./CONTRIBUTORS.md) for the full contributing workflow, which covers:

- Development setup and prerequisites
- Contribution tiers (trivial vs. non-trivial changes)
- Branch naming conventions
- Spec-first requirement for non-trivial changes
- TDD workflow
- Conventional Commits v1.0 commit message format
- Developer Certificate of Origin (DCO) sign-off
- Pull request requirements
- Acceptance criteria and review process

All pull requests target `main`. Reviews are carried out by Ion Reguera ([@ibiltari](https://github.com/ibiltari)) or Adrià Masip ([@backenv](https://github.com/backenv)).

---

## Release Notes

[↑ Back to Table of Contents](#table-of-contents)

See [CHANGELOG.md](./CHANGELOG.md) for the full history.

**Development (unreleased, since v1.0.0-1).** This development cycle focused on three areas: (1) completing the MTC-bias latency compensation chain for videocomposer (new `cuems-extract-video-latency` helper, composable `OPERATOR_FLAGS` + `OUTPUT_LATENCY_FLAG` environment files, operator runbook in `docs/latency-tuning.md`); (2) hardening the audio stack (pipewire/wireplumber system-wide masking, `zita-j2a` replacing `alsa_out` for USB audio, `snd-seq` deterministic module loading, correct JACK bridge startup ordering); and (3) OLA DMX infrastructure (`cuems-ola-profile` tool, native `olad.service`, flock-patch test suite, patched OLA installation docs). All services were migrated from the `stagelab` user to the new `cuems` system user, with security hardening applied to every unit.

**v1.0.0-1 (2025-11-12).** Initial Debian package release. Established the systemd target hierarchy (`cuems-node.target` / `cuems-controller.target` / `cuems-wifi.target`), packaged all service units for node and controller roles, delivered the base network configuration (bonded master interface, bridged node interface, WiFi AP), included the Avahi mDNS service group templates and network map schema, and introduced `cuems-config-node` for node provisioning and `cuems-hdmi-audio-map` for boot-time HDMI audio routing. Wayland support was noted in the initial changelog but has since been refined.

---

## Future Developments

[↑ Back to Table of Contents](#table-of-contents)

The items below describe planned CI/CD and DevOps integration that is **not yet implemented**. They are documented here so each pipeline can be wired in incrementally.

### Automated Test Suite and CI

A GitHub Actions workflow (`.github/workflows/tests.yml`) is planned to automate the existing validation scripts and add static analysis:

```yaml
# Planned — not yet implemented
name: Tests
on:
  push:
    branches: [main]
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install systemd tools and shellcheck
        run: sudo apt-get install -y systemd shellcheck
      - name: Validate systemd unit syntax
        run: bash scripts/test-systemd-units.sh
      - name: Validate dependency chains (static)
        run: bash scripts/test-systemd-deps.sh
      - name: Lint shell scripts
        run: >
          shellcheck
          scripts/*.sh
          usr/bin/cuems-cluster-poweroff
          usr/bin/cuems-displays-on
          usr/bin/cuems-ola-profile
          usr/bin/cuems-healthcheck
      - name: Verify package structure
        run: bash scripts/verify-package-structure.sh
```

Once this workflow is live, add the following badge below the existing badges:

```markdown
[![Tests](https://github.com/stagesoft/cuems-common/actions/workflows/tests.yml/badge.svg)](https://github.com/stagesoft/cuems-common/actions/workflows/tests.yml)
```

### Documentation Site

A Debian/sysadmin-focused documentation site using MkDocs Material is planned. It would aggregate the runbooks in `docs/` alongside auto-generated systemd unit documentation. Workflow: `.github/workflows/gh-pages.yml` deploying to `https://stagesoft.github.io/cuems-common/`.

Once live, add:

```markdown
[![Deploy MkDocs site](https://github.com/stagesoft/cuems-common/actions/workflows/gh-pages.yml/badge.svg)](https://github.com/stagesoft/cuems-common/actions/workflows/gh-pages.yml)
```

### Debian Release Workflow

A `.github/workflows/deb-publish.yml` workflow is planned to build the `.deb` package on every tagged release using the workspace `Makefile`, upload the artifact to a GitHub Release, and optionally push to a self-hosted APT repository. Corresponds to the `make cuems-common` workflow already used locally.

### Target Badge Set

Once all pipelines are live, the full badge set for this repository will be:

```markdown
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Debian bookworm](https://img.shields.io/badge/Debian-bookworm-A81D33.svg)](https://www.debian.org)
[![Tests](https://github.com/stagesoft/cuems-common/actions/workflows/tests.yml/badge.svg)](https://github.com/stagesoft/cuems-common/actions/workflows/tests.yml)
[![Deploy MkDocs site](https://github.com/stagesoft/cuems-common/actions/workflows/gh-pages.yml/badge.svg)](https://github.com/stagesoft/cuems-common/actions/workflows/gh-pages.yml)
```

---

## Copyright Notice

[↑ Back to Table of Contents](#table-of-contents)

```
cuems-common — CUEMS common configuration, systemd services, and operator tools
Copyright (C) 2025  Stagelab Coop SCCL

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

---

## License

[↑ Back to Table of Contents](#table-of-contents)

`cuems-common` is licensed under the **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`).

See [LICENSE](./LICENSE) for the full license text.

SPDX identifier: `GPL-3.0-or-later`
