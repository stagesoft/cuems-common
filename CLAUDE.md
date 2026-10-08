<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# cuems-common

Part of the **CUEMS** ecosystem — see the [`cuems-RELATIONS`](https://github.com/stagesoft/cuems-RELATIONS) repo for the system index, architecture diagram, and protocol/port map.

## Role

The system-level Debian package delivering **all shared configuration, systemd units, and operator tools** for a CUEMS install. It carries no compiled code — every executable it ships is a shell or Python script; the compiled daemons come from their own packages and are only wired into the systemd graph here. **Commits are GPG-signed** (retry on "gpg failed to sign", never `--no-gpg-sign`).

Ships: systemd service/target/path/socket units for both roles + drop-ins for third-party units (Apache2, hostapd, Avahi, rtpmidid); operator tools in `usr/bin/`; internal service helpers in `usr/lib/cuems/bin/`; per-install config + XSD schemas in `etc/cuems/`; Avahi/interface templates in `usr/share/cuems/`; kernel sysctl, JACK, Apache2, DHCP/hostapd, ALSA, Avahi, rsyslog, logrotate, sudoers, tmpfiles, modules-load drop-ins in `etc/`. Also ships the `cuems-power-bridge.service` unit (the daemon itself is a separate package).

## Roles & targets

A CUEMS host is either a **controller** (one per cluster) or a **node** (many). **Roles are dynamic** — any host can be promoted/demoted without a reinstall by editing the cluster topology. One source of truth: `network_map.xml` + `master.ip`; the postinst-time and runtime hooks adapt automatically on a flip.

Role is decided **only** by `<node_type>` in `/etc/cuems/network_map.xml`:
- `NodeType.master` → controller
- `NodeType.slave` → node

systemd targets per role:
- **Controller host** enables `cuems-controller.target` (`Requires=cuems-node.target` → also pulls node-side units). Controller-side units: `cuems-controller-engine.service`, `cuems-editor.service`, `cuems-midiconnector.service`.
- **Node host** enables `cuems-node.target` only. Node-side units: `cuems-node-engine.service`, `cuems-nodeconf.service` (if used), `jackd-cuems.service`, `jack-alsa-bridges.service`, `rtpmidid.service`, `cuems-videocomposer.service`.

`/etc/cuems/master.ip` + `/etc/cuems/master.lock` are managed by `cuems-nodeconf` (currently operator-placed where nodeconf is disabled) — their presence is a *side-effect* of controller role, not the mechanism. Role-aware hooks key off `[ -f /etc/cuems/master.ip ]`:
- `cuems-write-chrony-source` (chrony.service ExecStartPre) — installs server-or-client chrony config on every chrony start; deletes `sources.d/cuems-master.sources` when running as controller (cleans up after a slave→master promotion).
- `systemd-journal-upload` drop-in `ConditionPathExists=!/etc/cuems/master.ip` — suppresses the journal uploader on the controller.

Hooks that depend on role must (a) detect via `master.ip` presence, (b) be idempotent, (c) clean up files from the opposite role when invoked.

### Role-flip procedure

**Planned operation with mandatory reboot. NEVER mid-show.**

Current procedure (nodeconf disabled, hand-managed):
1. Update `<node_type>` in `network_map.xml` for the affected host.
2. Update `<role_id>` to match (`controller` for master, `nodeNN` for slave).
3. `touch /etc/cuems/master.ip` (or `rm` to demote).
4. `systemctl restart chrony rtpmidid cuems-node-engine` (+ `enable/disable cuems-controller.target` if the engine type changes). `rtpmidid` matters because `cuems-write-rtpmidid-config` only runs as its ExecStartPre — without a restart an ex-controller keeps acting as the network's controller and a fresh controller still tries to connect to itself.

Future procedure (when nodeconf is reactivated): edit only `<node_type>` → `xmllint --schema` → `cuems-nodeconf apply-identity --check` → `apply-identity` (**demotes first** to free `controller`, promotions second) → `reboot` each affected node. `apply-identity` rewrites `/etc/hostname`, `/etc/hosts`, `/etc/avahi/avahi-daemon.conf` and emits `CUEMS_NODE_UUID=…` before renaming (traceable under the old `_HOSTNAME`). The `apply-identity` CLI is **planned, not yet implemented in source**.

## Node identity

Every adopted node carries identity fields in `network_map.xml`. Schema shipped by cuems-utils (`network_map.xsd`), mirrored to `/etc/cuems/network_map.xsd` here. Full contract: `docs/node-identity-contract.md` (in this repo).

| Field | Required | Stable | Source | Purpose |
|-------|----------|--------|--------|---------|
| `uuid` | yes | **YES — primary key** | provisioning | The only stable identifier across the hardware's life. Every consumer keys nodes by UUID. |
| `mac` | yes | yes | hardware | Informational; matches one NIC. |
| `name` | yes | yes | nodeconf | mDNS FQDN (`<mac>._cuems_nodeconf._tcp.local.`). |
| `node_type` | yes | no | operator | `NodeType.master` / `NodeType.slave`. |
| `ip` | yes | no | nodeconf | Link-local IP discovered via avahi. |
| `adopted` | opt | no | nodeconf | `True` once adopted. |
| `online` | opt | no | nodeconf | Discovery-pass snapshot — NOT runtime liveness. See the nodeconf CLAUDE.md. |
| `role_id` | opt | no* | nodeconf | `controller` or `nodeNN`. |
| `alias` | opt | no | operator (UI) | Free-form human label. |
| `hostname` | opt | no | nodeconf | **Transitional** — set only when the OS hostname differs from `role_id`. |

`*` `role_id` changes only on a planned role-flip with reboot. **UUID is the primary key**; `role_id`/`alias`/`hostname`/`node_type` are mutable projections — any historical correlation goes through UUID. `role_id` assignment (nodeconf, when reactivated): master → `controller` (abort if another UUID already holds it); slave → next free `nodeNN` (`max+1`, 2-digit min pad); re-adoption of the same UUID+type reuses the prior `role_id`.

`/etc/cuems/cluster.conf` (optional) — when present with `cluster_name != default`, the OS hostname becomes `<cluster_name>-<role_id>`. Example at `/usr/share/doc/cuems-common/cluster.conf.example`.

**Transition period:** nodeconf is disabled cluster-wide, so operators hand-edit `<role_id>` (+ transitional `<hostname>`). Validate with `xmllint --noout --schema /etc/cuems/network_map.xsd /etc/cuems/network_map.xml`; restart cuems-editor (and the engine — see the editor/engine CLAUDE.md) after.

### `cuems-logs`

Operator tool (`/usr/bin/cuems-logs`) resolves node names against the identity model. `-n <name>` matches, in order: `role_id` → `alias` → `hostname` → `uuid` (exact or ≥8-char prefix) → literal `_HOSTNAME=<name>`. `-n local` queries only the local journal. `--list-nodes` / `--list-units`. Full contract in `docs/node-identity-contract.md`.

## Controller network modes

Since 1.3.0-23. Plan, review and verification matrix: `Plans/2026-09-29-controller-network-modes.md`. Origin: taller, 2026-09-29 — the controllers booted before their router, took the fallback lease and **served `192.168.6.0/24` on the wired LAN**, to each other included.

`/etc/cuems/net-mode.conf` holds `NET_MODE` and `AP_ARMED`; `/etc/cuems/ap.conf` keeps the constants. Switch with `cuems-net-mode <mode>`, inspect with `cuems-net-mode status`. **Everything acts only on a controller: `/etc/cuems/master.ip` exists AND `bond0` exists.** A missing `net-mode.conf` or an unknown value is `manual` — so a file-copy deploy (no postinst) inherits nothing.

| Mode / situation | bond0 | dhclient on bond0 | AP | dhcpd |
|---|---|---|---|---|
| `auto`, cable + DHCP | real lease | running | skipped | skipped |
| `auto`, cable, no server | `192.168.6.1/24` only | bound to the static lease; the guard probes every 60 s and replaces it on an offer | skipped | skipped — **never on the cable** |
| `auto`, no cable at boot, armed | no IPv4 (the address moved) | running, untouched | up, `192.168.6.1/24` on **wifi0** | on wifi0 |
| … then a cable with DHCP | real lease | running | stays up until reboot | stays on wifi0 |
| … then a cable with no DHCP | no IPv4 | running | stays up | on wifi0 — **reachable over WiFi only, until reboot** |
| `auto`, no cable, not armed | `192.168.6.1/24` | bound to the static lease | skipped | skipped |
| `cable-dhcp` | as the cable rows | as above | never | never |
| `cable-static` | `CABLE_STATIC_ADDR` (default `192.168.6.1/24`) | none | never | never |
| `ap`, armed | lease or none | running | always | on wifi0 |
| `manual`, or unknown | site-managed | site-managed | our gate never opens | our gate always allows |

- **Three gates, one script.** `check-ip.sh ap` (`cuems-wifi.service`), `check-ip.sh dhcpd` (`isc-dhcp-server`), `check-ip.sh hostapd`. Exit 0 proceed, 1 quiet skip, 255 failed unit (only when `ap.conf` is missing, and never in `manual`). The dhcpd gate refuses to serve on `bond0` in every mode but `manual`. In `manual` the gates reproduce the pre-1.3.0-23 units: `ap` closed, `dhcpd` open, `hostapd` open only while `cuems-wifi.service` is active — that last one stands in for the `Requisite=` that was removed, and is what keeps hostapd off the air on a `manual` controller that does not shadow `cuems-wifi-group.conf`. "Routable IPv4" excludes `169.254/16` everywhere (`usr/lib/cuems/net-mode.sh`, the single definition shared by the gates, the hook and the guard).
- **Arming.** The AP never comes up unless `AP_ARMED=yes`; unit enablement alone decides nothing. First install writes `yes`; **an upgrade always writes `no`**. `cuems-net-mode auto` / `ap` arm and enable `cuems-wifi.service`.
- **Address first, then dhcpd, then hostapd.** ⚠️ **NEVER order dhcpd after hostapd**: it is an ordering cycle, systemd silently deletes hostapd's start job, and it is boot-fatal for the AP (cupula1; `cuems-fleet/Plans/always-on-wifi-ap-medina-del-campo.md`). Resulting order: `networking.service` → `network.target` → `cuems-controller.target` → `cuems-wifi.service` → `isc-dhcp-server` → `cuems-wifi.target` → `hostapd`. Always drive the group through `cuems-wifi.target`.
- **AP data path** (`cuems-ap-path up|down|release-wifi`): the gateway address moves bond0 → wifi0 and back, always giving before taking. Forwarding is switched off on wifi0 (`ip_forward=1` ships globally), so AP clients reach the controller and nothing behind it. The AP no longer takes `ethernet0` down nor stops dhclient.
- **Exit hook** `cuems-fallback` (symlink in `/etc/dhcp/dhclient-exit-hooks.d/`, target under `/usr/lib/cuems/dhclient-hooks/`). Sourced inside `dhclient-script` (dash, shared namespace): never `exit`, only `cuems_` names, last command `:`. It decides from the **observed state** of bond0 — `run_hook` declares `exit_status` local, so hooks always see 0. *Recorded-lease nuance:* on `TIMEOUT` dhclient tries each recorded lease, pings its router and flushes bond0 when that fails; the hook is what keeps an address there in between.
- **Guard** (`cuems-net-guard.timer`, every 60 s, `OnBootSec=120s`): never no IP → AP sanity → dhclient alive → re-probe. The probe (`cuems-dhcp-probe`) sends DISCOVER only — no lease, no file, no process — over a packet socket. A second dhclient is not possible: its AppArmor profile is enforced. Replacing the client is `cuems-bond0-dhclient restart`, which uses **SIGKILL** (`dhclient -x` runs `STOP`, which flushes the address) and ifupdown's exact argv (`-i` is part of the DHCP identity).
- **Drop-in filename rule.** Never rename `hostapd.service.d/cuems-wifi-group.conf` or `20-cuems-config.conf`, and put every hostapd change in the former: Medina and formitgo shadow `cuems-wifi-group.conf` under `/etc`, formitgo does **not** shadow `20-`. New behaviour in `cuems-wifi.service` lives only in `ExecCondition=`/`ExecStartPost=`/`ExecStop=` — exactly what the venue drop-ins clear. Dependency lists cannot be cleared by a drop-in, so the dhcpd drop-in gains only `ExecCondition=` and one `After=`.
- **postinst starts, stops and restarts nothing new**; gates, hook and guard take effect at the next boot. It does rewrite `INTERFACESv4` (`"bond0"`/empty → `"wifi0"`) in `/etc/default/isc-dhcp-server` on a non-`manual` controller. A dhcpd already serving on the cable survives the upgrade until reboot or `cuems-net-mode apply --fix-now`.
- **After a role flip or a nodeconf promotion, run `cuems-net-mode apply`** — `net-mode.conf` was written for the role the host had at install time.
- **Behaviour changes against ≤ 1.3.0-22:** no `ethernet0` takeover; a laptop cabled straight into a controller gets no lease (regresses the alquiler1 scenario, by decision); hostapd and dhcpd are skipped, not failed, on wired boots.
- **Known limitations.** (a) *Shared address:* several controllers on one DHCP-less LAN all hold `192.168.6.1` (the taller has three) — documented, not solved. (b) *nodeconf:* it reads bond0's first IPv4 (`CuemsNodeConf.py:360`); while the AP is up bond0 has none, so where nodeconf is enabled it warns every 30 s and skips its map refresh. (c) The AP keeps broadcasting, on the default passphrase, after a cable lease arrives. (d) The AP is restarted with `cuems-controller.target` (`PartOf=`, pre-existing).
- **Downgrade:** `debian/prerm` removes the hook symlink, disables the timer and disables `cuems-wifi.service` if this version armed it. By hand afterwards: `INTERFACESv4="bond0"`, remove `net-mode.conf`, restore `interfaces.bak-*` if `cable-static` was used.

**Inverse case** (controller joins an existing WiFi as *client*): `/usr/lib/cuems/bin/wifi-auto.sh` (one-shot, operator-run) — stops isc-dhcp-server, brings up the `wifi-out` stanza. Detects the WLAN iface dynamically, refuses to touch dhcpd if `wifi-out` is absent under `/etc/network/`.

Constants: `/etc/cuems/ap.conf` (plain `KEY=value` — `AP_GATEWAY`, `AP_SUBNET`, `AP_RANGE_*`). `usr/lib/cuems/net-mode.sh` parses it (never sources it: the dhclient hook shares a namespace); `dhcpd.conf` cross-references it; `dhclient.conf` (operator-managed, from `isc-dhcp-client`) must be hand-matched. Reference interface templates under `/usr/share/cuems/`: `interfaces.master` (controller: bond0 = ethernet0 + wifi0 active-backup) and `interfaces.node` (node: ethernet0+ethernet1 bridged, wifi0 static 192.168.6.1, includes `wifi-out`). **Auto-deployed on FIRST INSTALL** — `debian/postinst` copies `interfaces.master` over `/etc/network/interfaces` when `[ -z "$2" ]` (never on upgrades). Future: a role-aware `cuems-write-network-interfaces` helper. ⚠️ **nodeconf DOES touch network plumbing**: `CuemsNodeConf.py:770-777` (`change_network_settings_to_master`, reached from `set_node_type()`) copies `interfaces.master` over `/etc/network/interfaces` during controller promotion. An earlier note here claimed the opposite "confirmed by source audit" — it was wrong. **bond0 takes its first slave's MAC**, so `interfaces.master` lists `ethernet0` first (since 1.3.0-20); the bond is controller-only, nodes use `bridge0`.

## Naming conventions

Standardize on **controller/node** for all new code, docs, strings, log messages, config fields, and new paths. Legacy **master/slave** survives only in identifiers that would need coordinated multi-component migrations: `/etc/cuems/master.ip` + `master.lock` (read by every role-aware hook); `<node_type>NodeType.master|slave</node_type>` (serialized enum, XSD migration); `CONTROLLER_NETWORK_FLAG = "NodeType.master"` and enum constants in engine/utils. Reading these is fine; do not introduce new occurrences.

## Field notes / gotchas

- **rtpmidid role-aware config + cold-boot avahi race** are documented in the rtpmidid CLAUDE.md (cuems-common ships the templates + drop-in). Current state: fix released in cuems-common 1.3.0-10 + rtpmidid 26.06~1stagelab1.
- **`cuems-node-engine.service` cleanup is by binary name** (1.3.0-24, 869evtdf7): its `ExecStartPre`/`ExecStopPost` `pkill -u cuems -f` is anchored on argv[0] (`cuems-audioplayer`, `cuems-dmxplayer`, `jack-volume`/`cuems-jack-volume`, legacy `xjadeo … --osc`), so logs being tailed are no longer killed. A player installed under another name escapes it (and the engine's own sweeps); the engine warns at start. The pattern deliberately has no `$` or `%` (systemd + `sh` would rewrite them).
- **OLA race + eurolite** codified in cuems-common 1.3.0-12: `cuems-node-engine.service After=olad.service` (native olad binds :9010 before node-engine spawns dmxplayer → no rogue olad at boot) + `cuems-ola-profile eurolite-mk2`. Details in the `ola` CLAUDE.md.
- **Hardware enablement (unrelated to CUEMS code):** Meteor Lake controllers (PCI VGA `7d45`) on Debian 6.1 need `i915.force_probe=7d45` in GRUB or `/dev/dri` is absent → jackd/node-engine/videocomposer cascade-fail. i3-1215U NIC naming standardized via systemd `.link` files (PCI `04/03/02:00.0` I226-V → ethernet0/1/2, `05:00.0` AX200 → wifi0); filename must == `Name=` (duplicate `Name=` silently breaks one); renames apply on reboot only; bond0 slave/MAC/DHCP-IP change is the dangerous part. Future improvement: hardware-specific golden base images (i3 vs N97) so provisioning is only uniqueness + customization.
- **dpkg-db drift on can't-`dpkg -i` controllers**: where an operator has no sudo password for dpkg, packages get deployed by file-copy (rsync of extracted `.deb` trees), so `dpkg-query` reports stale versions while the binaries are new. Audit by binary file date / `/proc/<pid>/exe`, not dpkg.
- **GRUB recovery entry — package-owned since 1.3.0-18.** On a video host the compositor holds DRM master over every output, so there is no text console exactly when an operator needs one. `/etc/grub.d/11_cuems_recovery` (shipped, conffile) generates boot entries titled `CUEMS Recovery (<kver>) — videocomposer disabled`, id `cuems-recovery-<kver>`, top-level in the menu, for each of the **two newest** kernels that have a matching initrd. They mask **only** `cuems-videocomposer.service`, via `systemd.mask=` on the kernel command line — nothing on disk changes, so **one ordinary reboot undoes it**; `quiet`/`splash` are stripped. It is a console escape hatch, not a "CUEMS off" switch.
  - Two kernels, not one: the entry must not inherit whatever is wrong with the default boot (the FP530's backports 6.12.95 comes up on the wrong IP — `iwlwifi` never probes, the bond takes the wrong MAC, the DHCP reservation misses). Two, not all: this package's postinst disables `apt-daily*.timer`, so superseded kernels are **never purged** on a CUEMS host.
  - `postinst` deletes the legacy hand-placed `/etc/grub.d/11_formitgo_recovery` (it existed on the FP530 only, owned by no package) and runs `update-grub`; `postrm` runs it again on remove/purge, otherwise the compiled menu would keep offering the entry after the package is gone. Both are guarded but **warn on stderr** — a failing `update-grub` is host-wide, since `/etc/grub.d/*` runs under `set -e` and the same failure breaks the kernel package's own hook.
  - When editing it: never hardcode `/boot/vmlinuz-<kver>` (that assumes `/boot` is not a separate partition) — the script sources `grub-mkconfig_lib` and uses `make_system_path_relative_to_its_root` + `prepare_grub_to_access_device`. And never `exit` non-zero: that aborts `grub-mkconfig` before `20_linux_xen`/`30_os-prober` for the whole host, permanently. Missing input ⇒ `exit 0`.
  - It is a **conffile**: do not edit it on a box to try something out. dpkg would then keep the local version on the next non-interactive `dpkg -i` and say almost nothing — which reads as "the .deb didn't install". Copy it elsewhere to experiment.
- **Obsolete conffiles are the package's standing footgun.** Dropping a file from `debian/install` does **not** remove it from installed hosts: dpkg marks it `obsolete` in `/var/lib/dpkg/status` and keeps it on disk forever, so upgraded boxes and fresh installs diverge with nothing in any log to say so. Two have bitten already — the acpid power-button trio (retired in 1.3.0-16) and `/etc/default/grub.d/cuems-display.cfg` (the `i915.enable_dc=0` remnant of the reverted HDMI warm-restart hack, retired in 1.3.0-19, four months after the code revert). Find them with `awk '/^Package: cuems-common$/,/^$/' /var/lib/dpkg/status | grep obsolete`. Retire them with `dpkg-maintscript-helper rm_conffile` in **all three** of preinst/postinst/postrm — hand-written, never via `debian/*.maintscript` (the reason is at the top of `debian/postinst`).
- Default credentials, latency tuning, and OLA install notes live in `docs/` (`default-credentials.md`, `latency-tuning.md`, `ola-install.md`).
