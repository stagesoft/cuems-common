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

Role is decided **only** by `<node_role>` in `/etc/cuems/network_map.xml`:
- `controller` → controller
- `node` → node

(feature 007: was `<node_type>`, free text `NodeType.master`/`NodeType.slave` — every
`/etc/cuems/network_map.xml` is migrated automatically on package upgrade by
`cuems-migrate-network-map`, run from `debian/postinst`. See
`docs/node-identity-contract.md`'s "The node_type -> node_role migration" section.)

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
1. Update `<node_role>` in `network_map.xml` for the affected host.
2. Update `<role_id>` to match (`controller` for a controller, `nodeNN` for a node).
3. `touch /etc/cuems/master.ip` (or `rm` to demote).
4. `systemctl restart chrony rtpmidid cuems-node-engine` (+ `enable/disable cuems-controller.target` if the engine type changes). `rtpmidid` matters because `cuems-write-rtpmidid-config` only runs as its ExecStartPre — without a restart an ex-controller keeps acting as the network's controller and a fresh controller still tries to connect to itself.

Future procedure (when nodeconf is reactivated): edit only `<node_role>` → `xmllint --schema` → `cuems-nodeconf apply-identity --check` → `apply-identity` (**demotes first** to free `controller`, promotions second) → `reboot` each affected node. `apply-identity` rewrites `/etc/hostname`, `/etc/hosts`, `/etc/avahi/avahi-daemon.conf` and emits `CUEMS_NODE_UUID=…` before renaming (traceable under the old `_HOSTNAME`). The `apply-identity` CLI is **planned, not yet implemented in source**.

## Node identity

Every adopted node carries identity fields in `network_map.xml`. Schema shipped by cuems-utils (`network_map.xsd`), mirrored to `/etc/cuems/network_map.xsd` here. Full contract: `docs/node-identity-contract.md` (in this repo).

| Field | Required | Stable | Source | Purpose |
|-------|----------|--------|--------|---------|
| `uuid` | yes | **YES — primary key** | provisioning | The only stable identifier across the hardware's life. Every consumer keys nodes by UUID. |
| `mac` | yes | yes | hardware | Informational; matches one NIC. |
| `name` | yes | yes | nodeconf | mDNS FQDN (`<mac>._cuems_nodeconf._tcp.local.`). |
| `node_role` | yes | no | operator | `controller` / `node` / `firstrun`. |
| `ip` | yes | no | nodeconf | Link-local IP discovered via avahi. |
| `adopted` | opt | no | nodeconf | `True` once adopted. |
| `online` | opt | no | nodeconf | Discovery-pass snapshot — NOT runtime liveness. See the nodeconf CLAUDE.md. |
| `role_id` | opt | no* | nodeconf | `controller` or `nodeNN`. |
| `alias` | opt | no | operator (UI) | Free-form human label. |
| `hostname` | opt | no | nodeconf | **Transitional** — set only when the OS hostname differs from `role_id`. |

`*` `role_id` changes only on a planned role-flip with reboot. **UUID is the primary key**; `role_id`/`alias`/`hostname`/`node_role` are mutable projections — any historical correlation goes through UUID. `role_id` assignment (nodeconf, when reactivated): controller → `controller` (abort if another UUID already holds it); node → next free `nodeNN` (`max+1`, 2-digit min pad); re-adoption of the same UUID+role reuses the prior `role_id`.

`/etc/cuems/cluster.conf` (optional) — when present with `cluster_name != default`, the OS hostname becomes `<cluster_name>-<role_id>`. Example at `/usr/share/doc/cuems-common/cluster.conf.example`.

**Transition period:** nodeconf is disabled cluster-wide, so operators hand-edit `<role_id>` (+ transitional `<hostname>`). Validate with `xmllint --noout --schema /etc/cuems/network_map.xsd /etc/cuems/network_map.xml`; restart cuems-editor (and the engine — see the editor/engine CLAUDE.md) after.

### `cuems-logs`

Operator tool (`/usr/bin/cuems-logs`) resolves node names against the identity model. `-n <name>` matches, in order: `role_id` → `alias` → `hostname` → `uuid` (exact or ≥8-char prefix) → literal `_HOSTNAME=<name>`. `-n local` queries only the local journal. `--list-nodes` / `--list-units`. Full contract in `docs/node-identity-contract.md`.

## Controller WiFi AP — self-suppression on existing networks

A controller does NOT broadcast its WiFi AP unconditionally. Two independent gates must BOTH allow it, so a controller plugged into an existing managed network doesn't fight it by re-broadcasting its SSID / handing out conflicting leases.

- **Gate 1 — explicit, `check-ip.sh`** (`ExecCondition` on `cuems-wifi.service`): proceeds only when `bond0` has the fallback static IP `192.168.6.1` AND `ethernet0` Link-detected = `no`. Any real upstream IP or a plugged cable → stays down.
- **Gate 2 — implicit, dhcpd subnet match**: `dhcpd.conf` declares only the AP subnet `192.168.6.0/24`; `cuems-wifi.target` `Requires=isc-dhcp-server.service`. When bond0 has a non-fallback IP, dhcpd finds no matching subnet and exits "Not configured to listen on any interfaces!" → the Requires propagates failure upward → hostapd never starts.

Symptom: `systemctl start cuems-wifi.target` → "A dependency job failed"; check `journalctl -u isc-dhcp-server.service -u cuems-wifi.service`.

**Inverse case** (controller joins an existing WiFi as *client*): `/usr/lib/cuems/bin/wifi-auto.sh` (one-shot, operator-run) — stops isc-dhcp-server, brings up the `wifi-out` stanza. Detects the WLAN iface dynamically, refuses to touch dhcpd if `wifi-out` is absent under `/etc/network/`.

Constants: `/etc/cuems/ap.conf` (shell-sourceable — `AP_GATEWAY`, `AP_SUBNET`, `AP_RANGE_*`). `check-ip.sh` sources it; `dhcpd.conf` cross-references it; `dhclient.conf` (operator-managed, from `isc-dhcp-client`) must be hand-matched. Reference interface templates under `/usr/share/cuems/`: `interfaces.master` (controller: bond0 = ethernet0 + wifi0 active-backup) and `interfaces.node` (node: ethernet0+ethernet1 bridged, wifi0 static 192.168.6.1, includes `wifi-out`). **Auto-deployed on FIRST INSTALL** — `debian/postinst` copies `interfaces.master` over `/etc/network/interfaces` when `[ -z "$2" ]` (never on upgrades). Future: a role-aware `cuems-write-network-interfaces` helper. ⚠️ **nodeconf DOES touch network plumbing**: `CuemsNodeConf.py:770-777` (`change_network_settings_to_master`, reached from `set_node_type()`) copies `interfaces.master` over `/etc/network/interfaces` during controller promotion. An earlier note here claimed the opposite "confirmed by source audit" — it was wrong. **bond0 takes its first slave's MAC**, so `interfaces.master` lists `ethernet0` first (since 1.3.0-20); the bond is controller-only, nodes use `bridge0`.

## Naming conventions

Standardize on **controller/node** for all new code, docs, strings, log messages, config fields, and new paths. The `<node_type>`/`NodeType.master|slave` XSD migration **landed** (feature 007): `network_map.xml` now carries `<node_role>controller|node|firstrun</node_role>`, converted automatically on upgrade by `cuems-migrate-network-map`. Legacy **master/slave** still survives in identifiers that need a *separate* coordinated multi-component migration, not done here: `/etc/cuems/master.ip` + `master.lock` (read by every role-aware hook — a marker-file mechanism, not the XML field); `CONTROLLER_NETWORK_FLAG = "NodeType.master"` and enum constants in `cuems-engine`/`cuems-utils` consumers, migrated in feature 010 once the readers move (see `cuems-utils`'s `specs/planning/xml-rebuild/xml-rebuild-09-consumer-audit.md` C9). Reading these is fine; do not introduce new occurrences.

## Field notes / gotchas

- **rtpmidid role-aware config + cold-boot avahi race** are documented in the rtpmidid CLAUDE.md (cuems-common ships the templates + drop-in). Current state: fix released in cuems-common 1.3.0-10 + rtpmidid 26.06~1stagelab1.
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
