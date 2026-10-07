<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# Plan — cuems-common 1.3.0-23: controller network modes, dhcpd/AP gating, fallback re-probe, AP data path

| | |
|---|---|
| Date | 2026-09-29 |
| Target repo | `/casas/dion/src/cuems/cuems-common` (origin `stagesoft/cuems-common`) |
| Branch assumed | new `fix/controller-network-modes` off `rc_1` @ `d9e0cc3` (1.3.0-22) |
| Author | Claude Fable 5.1, with the user (Ion) |
| Reviewed by | Claude Opus 5.5, 2026-09-29 (verdict table in §17) |
| Status | v3, review incorporated, approved 2026-09-29, in execution on `fix/controller-network-modes` |
| Artifact path | `cuems-common/Plans/2026-09-29-controller-network-modes.md` (this file) |

## 1. Context

Incident 2026-09-29, taller, power cut: the controllers (test, test2, test3) booted before the
MikroTik router. dhclient timed out on `bond0`, bound the documented fallback lease 192.168.6.1
(expiry 2040, so it never retried), and `isc-dhcp-server` started and served 192.168.6.0/24 on the
**wired** LAN. claw and the "Taller" device took 192.168.6.x leases; test2's own dhcpd NAKed
test2's later request for 10.16.10.3 and leased 192.168.6.17 to test2 itself. Nothing was
reachable over the VPN until every dhcpd was stopped and every dhclient restarted by hand.

The fallback address is intentional and documented (`cuems-common/CLAUDE.md`, "Controller WiFi
AP — self-suppression on existing networks"). It stays. `/etc/dhcp/dhclient.conf` stays
operator-managed and untouched.

## 2. Requirements (user, 2026-09-29)

| Situation (standard mode, `auto`) | Required |
|---|---|
| Cable, no DHCP server | `bond0` = 192.168.6.1. **Never** serve DHCP on the cable |
| Cable, DHCP server | take the lease; if DHCP fails, 192.168.6.1; re-ask **every 60 s** and move to the real lease as soon as a server answers |
| No cable | WiFi AP up, 192.168.6.1, serve DHCP to the AP clients |

- Reachability above all. "No IP" is never permissible. 169.254.x-only is not acceptable.
- `auto` is the standard. A box must be switchable in one step to: always cable with a fixed IP,
  always DHCP client, always AP with fixed IP and dhcpd.
- Always-on-AP and always-cable sites are exceptions, configured separately. They are not migrated
  by this plan; they must only not break.

## 3. Out of scope

- Any venue or fleet rollout (house rule A1). The plan ends on test2. Installing on the bench
  boxes test and test3 is a later, separate decision.
- Migrating Medina / romancera / formitgo to the new `ap` mode.
- Bridging the AP to the wired LAN (the venue "setup" mode with `br-venue`).
- A per-box unique fallback address. Several controllers on one DHCP-less LAN all hold
  192.168.6.1 (the taller has three). That ambiguity is documented, not solved.
- Decoupling the AP from `cuems-controller.target` restarts (`PartOf=`), a pre-existing property.
- The published default WiFi passphrase, and changes to `cuems-nodeconf`.

## 4. Defects being fixed

| # | Defect | Evidence |
|---|---|---|
| D1 | dhcpd is not behind Gate 1. Its only gate is dhcpd.conf's subnet match, which opens exactly when the fallback is taken. It then serves on the wire and answers its own host's DISCOVER | test2 journal 12:00–12:26 |
| D2 | On the fallback, dhclient never asks again | `bound: renewal in 356807623 seconds` |
| D3 | `cuems-wifi.service` is enabled by nothing on test2, so hostapd's `Requisite=` fails every boot | `Dependency failed for hostapd.service` |
| D4 | `check-ip.sh` compares the whole bond0 IPv4 list to 192.168.6.1, so a transient 169.254.x fails the gate closed | script text |
| D5 | The packaged AP data path cannot work: hostapd unenslaves `wifi0`, but 192.168.6.1 and dhcpd stay on `bond0` | template has no `bridge=` |
| D6 | Wired boots leave dhcpd `failed` and the system `degraded` | runbook :166 |
| D7 | During a fallback at boot, bond0 has no routable IPv4 for ~10 s | test2 journal 12:00:15–12:00:24 |
| D8 | hostapd can never start: `ConditionFileNotEmpty=/run/cuems/hostapd.conf` is checked before the `ExecStartPre=` that renders that file. Hidden today behind D3 (review C1) | `20-cuems-config.conf:18,21` |
| D9 | hostapd's `ExecStopPost=ip link set wifi0 master bond0` fails with EPERM when wifi0 is up, leaving hostapd `failed` (review M1) | `20-cuems-config.conf:31`, bonding refuses up slaves |

## 5. Design rules (what keeps the venues safe)

1. **Never order dhcpd after hostapd.** It is boot-fatal: an ordering cycle, and systemd silently
   deletes hostapd's start job (cupula1, `always-on-wifi-ap-medina-del-campo.md:368`). The proven
   order is **address first, then dhcpd, then hostapd**.
2. **Never rename** `hostapd.service.d/cuems-wifi-group.conf` or `20-cuems-config.conf`.
3. **`20-cuems-config.conf` is not modified.** formitgo does not shadow it. Every hostapd change
   goes into `cuems-wifi-group.conf`, which Medina and formitgo both shadow and which sorts after
   `20-`, so it can reset what `20-` sets.
4. **New behaviour in `cuems-wifi.service` lives only in `ExecCondition=`, `ExecStartPost=`,
   `ExecStop=`**, exactly what the venue drop-ins clear. `ExecStart=` stays `/bin/true`.
5. **Dependency lists cannot be cleared by a drop-in**, so our dhcpd drop-in (shadowed nowhere)
   gains only an `ExecCondition=` and one `After=`.
6. **The new postinst code starts, stops and restarts nothing.**
7. **`manual` mode is the explicit opt-out**, and the default whenever the mode is unknown.
8. **The AP never comes up unless `AP_ARMED=yes`.** Unit enablement alone decides nothing.

## 6. State model

`/etc/cuems/net-mode.conf` holds `NET_MODE` and `AP_ARMED`. `/etc/cuems/ap.conf` keeps the constants.
All new logic acts only on a controller: `/etc/cuems/master.ip` exists **and** `bond0` exists.

| Mode / situation | bond0 | dhclient on bond0 | AP path | dhcpd | guard timer | exit hook |
|---|---|---|---|---|---|---|
| `auto`, cable + DHCP | real lease | running | skipped | skipped | idle | drops .6.1 from bond0 if present |
| `auto`, cable, no server | 192.168.6.1/24 only | bound to the static lease | skipped | skipped | probes every 60 s; on an offer restarts dhclient | re-adds .6.1 whenever bond0 loses its address |
| `auto`, no cable at boot, armed | no IPv4 (the address moved) | running, untouched | active; **192.168.6.1/24 on wifi0** | active on wifi0 | probes if a cable appears later | keeps .6.1 off bond0 while wifi0 holds it |
| same, then a cable with DHCP | real lease | running | stays up until reboot | stays on wifi0 | idle | — |
| same, then a cable with no DHCP | no IPv4 | running | stays up | stays on wifi0 | probes | **the box is reachable over WiFi only, until reboot** |
| `auto`, no cable, not armed | 192.168.6.1/24 | bound to the static lease | skipped | skipped | idle (no carrier) | — |
| `cable-dhcp` | as the cable rows | as above | never | never | as above | as above |
| `cable-static` | static address (default 192.168.6.1/24) | none | never | never | re-asserts the address | — |
| `ap`, armed | DHCP lease or none | running | always; .6.1 on wifi0 | active on wifi0 | probes; retries a failed AP every 5 min | keeps .6.1 off bond0 |
| `manual`, or mode unknown | site-managed | site-managed | our gate never opens | our gate always allows | no-op | no-op |

Deliberate changes against today's semantics:
- The AP no longer takes `ethernet0` down or stops dhclient.
- A laptop cabled straight into a controller no longer gets a lease (user decision). This regresses
  the scenario documented for alquiler1.
- In the AP state bond0 has no IPv4. `cuems-nodeconf` reads bond0's first IPv4
  (`CuemsNodeConf.py:360`), so where nodeconf is enabled it warns every 30 s and skips its map
  refresh while the AP is up. See §15.

## 7. Files

Every new or modified file carries the three SPDX lines with
`SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>` in its own comment syntax. The two files
moved from `dev/planning/` get the line added. `debian/changelog` cannot carry comments; its
trailer is the attribution.

New:

| Repo path | Installed as | Notes |
|---|---|---|
| `scripts/cuems-ap-path` | `/usr/lib/cuems/bin/` | git mode 0755 |
| `scripts/cuems-bond0-dhclient` | `/usr/lib/cuems/bin/` | 0755 |
| `scripts/cuems-net-guard` | `/usr/lib/cuems/bin/` | 0755 |
| `scripts/cuems-dhcp-probe` | `/usr/lib/cuems/bin/` | python3, 0755. Replaces the second-dhclient probe |
| `usr/bin/cuems-net-mode` | `/usr/bin/` | operator helper, structured like `usr/bin/cuems-ola-profile` |
| `usr/lib/cuems/dhclient-hooks/cuems-fallback` | same | POSIX sh, sourced. Not a conffile: postinst symlinks it into `/etc/dhcp/dhclient-exit-hooks.d/` |
| `usr/share/cuems/net-mode.conf.default` | via the `usr/share/cuems/*` glob | template |
| `etc/systemd/system/cuems-net-guard.service` | `lib/systemd/system/` | explicit `debian/install` line |
| `etc/systemd/system/cuems-net-guard.timer` | via the `*.timer` glob | |
| `debian/prerm` | — | contains `#DEBHELPER#`, so the unit-stop snippet debhelper generates today is kept |
| `Plans/2026-09-29-controller-network-modes.md` | — | plus `git mv dev/planning/*.md Plans/` |

Modified: `scripts/check-ip.sh`, `etc/systemd/system/cuems-wifi.service`,
`etc/systemd/system/cuems-wifi.target`, `etc/systemd/system/hostapd.service.d/cuems-wifi-group.conf`,
`etc/systemd/system/isc-dhcp-server.service.d/cuems-wifi-group.conf`, `usr/bin/cuems-healthcheck`,
`debian/install`, `debian/postinst`, `debian/postrm`, `debian/changelog`, `CHANGELOG.md`,
`CLAUDE.md`, `README.md`, `CONTRIBUTORS.md`, `etc/cuems/ap.conf` (header comment only),
`scripts/ensure-executable.sh`, `scripts/verify-package-structure.sh`.

Not modified: `hostapd.service.d/20-cuems-config.conf`, `cuems-controller.target`,
`usr/share/cuems/dhcpd.conf`, `usr/share/cuems/interfaces.master`, `dhclient.conf`.

## 8. Design per component

### 8.1 `/etc/cuems/net-mode.conf` (config file, not a conffile)
`NET_MODE=auto|cable-dhcp|cable-static|ap|manual`, `AP_ARMED=yes|no`, optional
`CABLE_STATIC_ADDR=192.168.6.1/24`. Created by postinst, rewritten by `cuems-net-mode`, removed on
purge. **Every reader treats a missing file or an unknown value as `manual`.**

### 8.2 `check-ip.sh [ap|hostapd|dhcpd]` — the three gates
Exit 0 = proceed, 1 = skip quietly, 255 = cannot evaluate (unit shows `failed`; only when
`/etc/cuems/ap.conf` is missing). Default argument `ap`. "Routable IPv4" is the interface's IPv4
list minus 169.254/16 (fixes D4).

| Gate | Used by | Logic |
|---|---|---|
| `ap` | `cuems-wifi.service` | not a controller, `manual`, `cable-*`, `AP_ARMED` ≠ yes, or no `wifi0` → 1. `ap` → 0. `auto` → 0 iff bond0's routable set is exactly {AP_GATEWAY} **and** `ethtool ethernet0` says `Link detected: no` |
| `hostapd` | hostapd drop-in | `manual` → 0. Otherwise 0 iff `wifi0` carries AP_GATEWAY |
| `dhcpd` | isc-dhcp-server drop-in | `manual` → 0. `cable-*` → 1. Otherwise: interfaces = `INTERFACESv4` (empty = all); serving = those carrying an address inside `AP_SUBNET`. `bond0` in serving → log "refusing to serve DHCP on bond0", 1. Serving empty → 1. Else 0 |

### 8.3 Units
- `cuems-wifi.service`: add `PartOf=cuems-wifi.target`; `ExecStartPost=…/cuems-ap-path up`
  replaces `ip link set ethernet0 down`; `ExecStop=…/cuems-ap-path down` replaces
  `ip link set ethernet0 up`. Everything else, `[Install]` included, unchanged.
- `cuems-wifi.target`: `Requires=isc-dhcp-server.service` → `Wants=`. `Before=hostapd.service` stays.
- hostapd `cuems-wifi-group.conf`:
  - remove `Requisite=cuems-wifi.service`; add `PartOf=cuems-wifi.service`; keep `After=` and `[Install]`;
  - `ConditionFileNotEmpty=` (reset; fixes D8. `ExecStartPre` still renders the file before
    `ExecStart` reads it);
  - `ExecCondition=/usr/lib/cuems/bin/check-ip.sh hostapd`;
  - `ExecStopPost=` (reset) then `ExecStopPost=-/usr/lib/cuems/bin/cuems-ap-path release-wifi`
    (fixes D9). ExecStopPost also runs after a condition skip, so `release-wifi` must be a no-op
    when wifi0 is already a bond slave.
- isc-dhcp-server `cuems-wifi-group.conf`: add `After=cuems-wifi.service` and
  `ExecCondition=/usr/lib/cuems/bin/check-ip.sh dhcpd`.

Resulting order, confirmed acyclic by the reviewer on test2's live graph:
`networking.service` → `network.target` → `cuems-controller.target` → `cuems-wifi.service`
→ `isc-dhcp-server` → `cuems-wifi.target` → `hostapd`. Always drive the group through the target.

### 8.4 `cuems-ap-path {up|down|release-wifi}`
- `up`: `manual` → exit 0. `ip link set wifi0 nomaster`; `ip link set wifi0 up`;
  `sysctl -w net.ipv4.conf.wifi0.forwarding=0` (AP clients are not routed onto the LAN or the
  cluster link; `ip_forward=1` is shipped globally); `ip -4 addr replace GW/prefix dev wifi0`; only
  then `ip -4 addr del GW/prefix dev bond0`. If a wifi0 step fails: undo, leave bond0 untouched,
  exit 1.
- `down`: if bond0 has no routable IPv4, put GW on bond0 **first**; then remove GW from wifi0; if
  `ethernet0` is admin-down bring it up (a box upgraded while the old takeover was active).
- `release-wifi`: if wifi0 is not enslaved: `ip link set wifi0 down`, then
  `ip link set wifi0 master bond0`. Otherwise nothing.

### 8.5 Exit hook `cuems-fallback`
Sourced by `/sbin/dhclient-script` after every event, before `zzz_avahi-autoipd`. Never `exit`, no
`set -e/-u`, only `cuems_`-prefixed variables, last command `:`. Acts only on a controller, for
`interface=bond0`, in `auto|cable-dhcp|ap`.

Hooks always see `exit_status=0` (`run_hook` declares it local), so the hook decides from the
**observed state** of bond0, not from dhclient-script's status:

| After the event, bond0 … | Action |
|---|---|
| carries a routable address other than GW, and GW too | delete GW from bond0 |
| carries no routable IPv4, and no other interface carries GW | `ip -4 addr replace GW/prefix dev bond0` (covers EXPIRE, FAIL, and a TIMEOUT whose recorded lease was rejected and flushed; fixes D7) |
| carries GW while another interface carries GW too | delete GW from bond0 |

### 8.6 Guard timer (`cuems-net-guard.timer` → `.service` → `cuems-net-guard`)
Timer: `OnBootSec=120s`, `OnUnitActiveSec=60s`, `AccuracySec=5s`, `WantedBy=timers.target`.
Service: oneshot, `ConditionPathExists=/sys/class/net/bond0`, `RuntimeDirectory=cuems-net-guard`,
`RuntimeDirectoryPreserve=yes`, `TimeoutStartSec=45s`, `LogLevelMax=notice`.

Each run, in order (not a controller, or `manual` → exit 0 first):
1. **Never no IP.** bond0 has no routable IPv4, no other interface carries GW, and no dhclient is
   in the foreground of an `ifup` (scan `/proc`) → put GW on bond0.
2. **AP sanity.** wifi0 carries GW but hostapd is inactive for two runs → warn,
   `systemctl --no-block stop cuems-wifi.service`. In `ap` mode retry
   `start cuems-wifi.target` every 5 minutes. hostapd active but dhcpd inactive → warn, start it.
3. **dhclient alive.** The mode needs a client, `/run/network/ifstate` lists bond0, the stanza is
   `inet dhcp`, and no dhclient owns bond0 → `cuems-bond0-dhclient start`.
4. **Re-probe.** "Stuck" = bond0's routable set is exactly {GW}, or bond0 has none while another
   interface carries GW. If stuck, `ethernet0` has carrier, and the last restart was ≥180 s ago:
   run `cuems-dhcp-probe bond0`. Offer → log, `cuems-bond0-dhclient restart`. No offer → silent.

`cuems-dhcp-probe` (python3): sends one DHCPDISCOVER with the broadcast flag and bond0's MAC from a
UDP socket bound to bond0:68 (`SO_REUSEADDR`, `SO_BROADCAST`, `SO_BINDTODEVICE`), retransmits at
2 s and 5 s, waits 8 s in total for a DHCPOFFER with its xid. Exit 0 offer, 2 none, 1 error. It
never sends a REQUEST, so it takes no lease, writes no file and leaves no process. A second
`dhclient` was rejected: its AppArmor profile is enforced on test2 and allows neither the config
path, nor the lease and pid paths, nor `-sf /bin/true`.

### 8.7 `cuems-bond0-dhclient {status|start|stop|restart|active-for}`
The argv is a constant in the script (ifupdown compiles its own in; there is no `inet.defn` on
disk): `/sbin/dhclient -4 -i -pf /run/dhclient.bond0.pid -lf /var/lib/dhcp/dhclient.bond0.leases
-I -df /var/lib/dhcp/dhclient6.bond0.leases bond0`. Those paths are inside the AppArmor profile.
The running client is found by scanning `/proc`, not only through the pid file. `stop` and
`restart` use **SIGKILL**: `dhclient -x` runs the `STOP` script, which flushes the address.
`start` runs `systemd-run --unit=cuems-dhclient-bond0 --collect -p KillSignal=SIGKILL --
/sbin/dhclient -d …`; a failure of `systemd-run` is logged at warning, never swallowed. Every
`systemctl`/`systemd-run` call is `--no-block` inside `timeout 10`.

### 8.8 `cuems-net-mode {status [--check]|apply|auto|cable-dhcp|cable-static [ADDR]|ap|manual} [--yes]`
Root only, operator-invoked, never called from a unit.
- `status`: mode, arming, addresses, carrier, dhclient, unit states, `INTERFACESv4`, the stanza
  method, the three gate results, warnings. `--check` prints nothing and exits non-zero on an
  inconsistency; on a non-controller it exits 0.
- `apply`: config reconcile. On a controller in a standard mode, rewrite `INTERFACESv4` from
  `"bond0"` or empty to `"wifi0"`. `apply --fix-now` also stops a dhcpd serving on a cabled bond0
  and waits until its pid is gone (the init script's stop does not wait). `apply --postinst`
  touches no service and **always exits 0**, including on a node.
- Mode subcommands refuse on a non-controller. They print what will change, warn that sessions
  over an address that goes away will drop and that a running show keeps playing, and ask for
  confirmation unless `--yes`. Then: write `NET_MODE`; for `auto`/`ap` write `AP_ARMED=yes` and
  `systemctl enable cuems-wifi.service` (refuse if masked); for `cable-static` transitions edit
  only the `iface bond0 inet dhcp|static` line plus one marked `address` line (tmp file,
  `ifquery -i <tmp> bond0`, `cp -a` backup, `mv`), apply the address live with `ip`, and say that
  the stanza itself takes effect at the next boot; `systemctl stop cuems-wifi.target`, wait for
  dhcpd's pid to go; `apply`; for `auto`/`ap` `systemctl start cuems-wifi.target`; `status`.

### 8.9 Maintainer scripts
- `postinst`, in this order, each new call guarded with `|| echo "WARNING: …" >&2`:
  1. create `/etc/cuems/net-mode.conf` if absent. `NET_MODE=manual` when any of
     `/etc/systemd/system/{cuems-wifi,hostapd,isc-dhcp-server}.service.d/*.conf` or
     `/etc/systemd/system/cuems-ap-mode.service` exists, `cuems-wifi.service` is masked, or the
     bond0 stanza is `inet static`; otherwise `auto`. `AP_ARMED=yes` only on a first install
     (`[ -z "$2" ]`); `no` on every upgrade, whatever the unit's enablement;
  2. create the hook symlink;
  3. first install only: `systemctl enable cuems-wifi.service`;
  4. `systemctl enable cuems-net-guard.timer` (arms at the next boot; not started);
  5. `cuems-net-mode apply --postinst`;
  6. add the new scripts to the chmod loop at `postinst:89`.
- `prerm` (new, with `#DEBHELPER#`): on `remove`, and on `upgrade` to a version `lt 1.3.0-23~`,
  delete the hook symlink, disable the timer, and `systemctl disable cuems-wifi.service` if
  `AP_ARMED=yes` was set by this version (so a downgrade cannot re-arm the old ethernet0-down
  takeover).
- `postrm`: on `purge` remove `/etc/cuems/net-mode.conf`.

### 8.10 `cuems-healthcheck`
One check: `cuems-net-mode status --check`, counted as a network issue when non-zero.

### 8.11 Docs
- `CLAUDE.md`: replace the AP section with "Controller network modes": the state table, the gates,
  arming, the address-first rule with its reference, the AP data path, the guard, the hook,
  `cuems-net-mode`, the drop-in filename rule, the behaviour changes of §6, the shared-address
  limitation, the nodeconf limitation, the recorded-lease nuance, and that a role flip or a
  nodeconf promotion must be followed by `cuems-net-mode apply`.
- `README.md`, `CONTRIBUTORS.md`, `etc/cuems/ap.conf` header, `CHANGELOG.md`, `debian/changelog`.
- Follow-ups in other repos, listed for the user, not edited here: the alquiler1 plan :250, the
  3-pair runbook :166, the fleet notes that call the dhcpd failure expected, and a row in
  `cuems-RELATIONS/Plans/STATUS.md`.

## 9. Blast radius

| Question | Answer |
|---|---|
| Shared code / schema | none. The shared surface is dhclient-script's sourced namespace, next to the chrony, timesyncd, rfc3442, avahi and site hooks: hence the `cuems_` prefix and the final `:` |
| Cross-process contracts | `check-ip.sh` gains arguments, backward-compatible. `cuems-nodeconf` reads bond0's IPv4 and is affected in the AP state (§6). avahi re-announces on an address change; test2 and test3 are both named `controller` on one LAN, so a rename to `controller-2` can happen, as it can today |
| Role divergence | everything keys on `master.ip` **and** bond0. A demoted controller that kept `interfaces.master` is not acted on |
| Persisted state | `net-mode.conf` (new, purged). `INTERFACESv4` rewritten on standard controllers. `cuems-wifi.service` enablement, undone by prerm on downgrade. `/etc/network/interfaces` only through an explicit `cable-static` |
| Config surface | no `net-mode.conf`, or an unknown value, means `manual`. A file-copy deploy (no postinst) therefore gets no new behaviour at all |
| Version skew | networking is per-box. Downgrade handled by prerm |
| Failure visibility | gate cannot evaluate, or `cuems-ap-path up` fails → unit `failed`. AP without dhcpd, AP address without hostapd, probe errors, `systemd-run` failures → guard warnings. `cuems-healthcheck` reports inconsistencies |

What an upgrade does, by inspection of the fleet docs. Nothing here is executed by this plan.

| Box | Mode after upgrade | Effect |
|---|---|---|
| test2, test, test3 | `auto`, not armed | gates, hook and guard from the next boot. No AP until `cuems-net-mode auto` |
| isil, alquiler1, badajoz, panera (standard units; isil recorded with the AP fallback enabled) | `auto`, not armed | same. `AP_ARMED=no` keeps the AP off even where the unit is enabled. A laptop cabled straight in no longer gets a lease |
| Medina cúpulas / sala1 | `manual` | nothing; our dhcpd gate returns 0 |
| formitgo at romancera | `manual` | nothing |
| any node | not a controller | dhcpd goes from `failed` to skipped |
| a box in the incident state | `auto` | the rogue dhcpd keeps running until reboot or `cuems-net-mode apply --fix-now`; postinst prints a warning |

## 10. If a show is running (house rule A3)

- The **existing** postinst already restarts `systemd-journald` and `rsyslog`, reloads `apache2`
  and `ssh`, stops `man-db.timer` and may start `rsync` on every upgrade (`postinst:157-164,
  435-439, 468-472, 484-486, 649-653, 660-664`). None of that stops playback; an apache reload can
  blip an open editor page. This plan adds no restart to that list, but an upgrade is therefore
  not free of side effects, and V2 is run with no project loaded.
- The guard can change bond0's address at runtime. Playback does not depend on bond0. An operator
  connected over the address that goes away loses the session and reconnects. Proven in V6.
- No new code stops or restarts an engine, the editor, videocomposer, jack or rtpmidid.
- `cuems-net-mode` is explicit, prints the consequences and asks for confirmation.

## 11. New automation, argued (house rule A8)

The guard timer is new automation on every controller. Each of its four steps is here because a
requirement cannot be met without it:

| Step | Requirement it serves | Why nothing simpler works |
|---|---|---|
| 4, re-probe | "re-ask every 60 s" | a dhclient bound to the static lease sleeps until 2040, and `dhclient.conf` is out of bounds |
| 1, never no IP | "no IP is never permissible" | the hook only runs on dhclient events; an address removed by anything else would stay gone |
| 3, dhclient alive | "cable with DHCP takes the lease" | a client killed for a restart that then failed to start would never come back |
| 2, AP sanity | reachability when the AP fails | without it the address stays on a wifi0 that is not an AP |

Rejected: restarting the real client every minute; removing the static lease; a long-running daemon.

## 12. Verification

Build on casas (`jump`): `cd /casas/dion/src/cuems/cuems-common && debuild -b -uc -us`; artifact
`/casas/dion/src/cuems/cuems-common_1.3.0-23_all.deb`, copied to `rc1_packages/`. Tests on test2.
Every step that can cut access is preceded by a dead-man unit
(`systemd-run --on-active=… -p KillMode=process`) that removes the `tc` filter **and** runs
`cuems-bond0-dhclient restart`.

| # | Step | Pass when |
|---|---|---|
| V1 | `shellcheck`, `bash -n`/`sh -n`, `python3 -m py_compile`; the repo's unit and package checks; `systemd-analyze verify` | clean |
| V2 | install on test2, no project loaded; `systemctl show` hostapd and isc-dhcp-server | both list their `ExecCondition`; hostapd `Requisite` and `ConditionFileNotEmpty` empty; `INTERFACESv4="wifi0"`; `net-mode.conf` = `auto`, `AP_ARMED=no`; hook symlink present; prerm contains the debhelper unit-stop snippet |
| V3 | wired reboot | `is-system-running` = running; dhcpd and hostapd skipped; hostapd not `failed`; no "Dependency failed", no "ordering cycle"; bond0 = 10.16.10.3 only |
| V4 | router-late without touching the router: dead-man 300 s; `tc qdisc add dev bond0 clsact` + `tc filter add dev bond0 egress protocol ip flower ip_proto udp dst_port 67 action drop`; strip the recorded leases; `ip -4 addr flush dev bond0`; `cuems-bond0-dhclient restart` | within ~40 s bond0 = 192.168.6.1/24 only; an observer logging `ip -br a` every second shows no sample without a routable IPv4; dhcpd skipped with "refusing to serve DHCP on bond0" |
| V4b | V4 again **keeping** the recorded lease (the path of the incident) | the rejected recorded lease is followed at once by the fallback; no sample without a routable IPv4 |
| V5 | the dead-man removes the filter | within ~90 s the guard logs the offer, bond0 = 10.16.10.3, .6.1 gone, `cuems-dhclient-bond0` active |
| V6 | V4–V5 with a project playing (load → GO) | playback continues; no stop or unload in the engine journal; node01 stays connected |
| V7 | `ifdown bond0; ifup bond0` from the console | transient unit collected; `--failed` empty; lease restored |
| V8 | `cuems-net-mode ap --yes`, then `auto --yes` | hostapd **active**, `iw`-free check: `/sys/class/net/wifi0/operstate` up and hostapd's journal shows `AP-ENABLED`; wifi0 = 192.168.6.1/24; dhcpd listening on wifi0; bond0 still 10.16.10.3; SSH intact; nodeconf's journal inspected. Back: all reversed, wifi0 in the bond, hostapd not `failed` |
| V9 | soak: V4 for 70 minutes with a project playing | ~60 guard runs, one dhclient, `--failed` empty, no leftover files, videocomposer's dropped-frame counter no worse than a 70-minute baseline without the guard |
| V10 | manual, on site, on test2: `cuems-net-mode auto`, unplug, reboot | a phone joins the SSID, gets .11–.100, reaches 192.168.6.1 and the web UI, and cannot reach the cluster link. **The AP is unproven end to end until this runs** |
| all | after each step | `journalctl -k | grep -i denied` shows no new AppArmor denial |

## 13. Rollback

`dpkg -i /casas/dion/src/cuems/cuems-common_1.3.0-22_all.deb`. The 1.3.0-23 prerm removes the hook
symlink, disables the timer and disables `cuems-wifi.service` if this version armed it. Then, by
hand: `INTERFACESv4="bond0"`, remove `/etc/cuems/net-mode.conf`, restore
`/etc/network/interfaces.bak-*` if `cable-static` was used, confirm
`systemctl is-enabled cuems-wifi.service` = disabled, reboot.

## 14. Execution order

0. Copy this plan to `cuems-common/Plans/2026-09-29-controller-network-modes.md` with its SPDX
   header; `git mv dev/planning/*.md Plans/` and add the contributor line to both.
1. Branch `fix/controller-network-modes` off `rc_1`. Commits are GPG-signed; if signing would
   prompt or fails, stop and hand the commit to the user. Nothing is pushed without being asked.
2. Commits: Plans; gates and units (§8.2–8.4); hook, guard, probe, dhclient helper (§8.5–8.7);
   `cuems-net-mode` and healthcheck; packaging and changelogs; docs.
3. V1, build, V2–V9 on test2. V10 when the user is at the taller.
4. Inventory (house rule A10): test2 has no row and its UUID is clone-image residue, so recording
   it is a decision for the user (§15). Existing rows are updated with `store::set_node_field`,
   never `register-node`, whose upsert wipes the notes.

## 15. Decisions and open questions for the user

1. **nodeconf in the AP state.** Accept the limitation of §6, or keep an address on bond0 while the
   AP is up (which needs a different AP data path, such as a bridge)?
2. **The AP keeps broadcasting**, on the default passphrase, after a cable lease arrives. Accept,
   or tear the AP down when bond0 gets a real lease?
3. postinst rewrites `INTERFACESv4` `bond0`→`wifi0` in another package's config file.
4. The package enforces the fallback even where `dhclient.conf` declares none; `manual` is the
   only opt-out.
5. Should test2 get an inventory row, and under which UUID?
6. Are test and test3 meant to get the package after test2? No step here installs them.
7. Not checked by anyone: whether `avahi-autoipd -w` returns at once when a routable address is
   already present (V4b shows it), and which kernel test3 boots (one FP530 kernel never probes
   iwlwifi).

## 16. History

| Version | Change |
|---|---|
| v1 | planning-agent design |
| v2 | address-first ordering instead of `dhcpd After=hostapd`; `20-cuems-config.conf` untouched; no ethernet0 takeover; `manual` mode; SIGKILL instead of `dhclient -x`; `tc` filter instead of disabling the router's DHCP; venue rollout removed |
| v3 | review incorporated: §17 |

## 17. Review — 2026-09-29, reviewer: Claude Opus 5.5

Verdict of the review on v2: not ready to execute; 1 critical, 6 high. Confirmed by the reviewer
and left unchanged: the ordering graph is acyclic; an `ExecCondition` skip fails nothing; the
`manual` detection classifies Medina, formitgo, test2 and a node correctly; the `tc` egress filter
does stop dhclient. The reviewer wrote and deleted one scratch file in `/tmp` on test2.

| # | Finding | Verdict | Action |
|---|---|---|---|
| C1 | hostapd's `ConditionFileNotEmpty` is checked before the `ExecStartPre` that renders the file | accepted, confirmed in the repo | D8; condition reset in `cuems-wifi-group.conf` (§8.3); V8 now requires hostapd active |
| H1 | hooks always see `exit_status=0` | accepted, confirmed in dhclient-script | hook decides from bond0's observed state (§8.5); V4b added |
| H2 | a second dhclient violates the enforced AppArmor profile | accepted, confirmed on test2 | python3 DISCOVER-only probe (§8.6); denial grep after every step |
| H3 | `cuems-net-mode apply --postinst` would abort postinst on nodes | accepted | always exits 0; calls guarded (§8.8, §8.9) |
| H4 | rollback re-arms the old ethernet0-down takeover | accepted | prerm and §13 disable the unit |
| H5 | V4/V5 cannot pass; the dead-man does not restore access | accepted | V4 flushes first; the dead-man also restarts the client |
| H6 | probe false positives from a persisted lease file | accepted, moot | the new probe keeps no lease file |
| M1 | hostapd ends `failed` after every AP stop | accepted | D9; `ExecStopPost` reset, `release-wifi` (§8.3, §8.4) |
| M2 | "the upgrade restarts no unit" is false | accepted | §10 rewritten; V2 with no project loaded |
| M3 | a rogue dhcpd survives an upgrade until reboot | accepted in part | documented (§9); `--fix-now` waits for the pid. No automatic stop: postinst must not touch services, and the guard is not running before the reboot that gates dhcpd anyway |
| M4 | role keyed on bond0 instead of `master.ip` | accepted | both are required everywhere (§6) |
| M5 | nodeconf needs an IPv4 on bond0 | accepted as a limitation | documented (§6, §9); V8 inspects it; decision 1 |
| M6 | the AP comes with `ip_forward=1` | accepted | per-interface forwarding off on wifi0 (§8.4); V10 checks it |
| M7 | no wired path after an AP boot | accepted | row added to the state table |
| M8 | the AP would go live where the unit is already enabled; boxes missing from the table | accepted | `AP_ARMED` (§5 rule 8, §8.1, §8.2); table extended (§9) |
| M9 | probe mechanics unspecified | accepted, moot | replaced by the python probe |
| M10 | V10 cannot pass as written | accepted | V10 moved to test2 and arms first |
| M11 | `manual` is fragile when the conf file is missing | accepted | missing or unknown means `manual`; conf created before the symlink |
| L1 | no `inet.defn` on disk | accepted | argv is a constant (§8.7) |
| L2 | a dangling hook does not make dhclient-script fail | accepted | rationale dropped; prerm action kept |
| L3 | a hand-written prerm drops debhelper's unit-stop snippet | accepted | prerm carries `#DEBHELPER#`; checked in V2 |
| L4 | `SuccessExitStatus=5 6` on the sysv unit | dismissed | the gate only ever exits 0, 1 or 255 |
| L5 | `down` had a gap and could leave wifi0 down inside the bond | accepted | order reversed; `release-wifi` acts only on an unenslaved wifi0 |
| L6 | the guard would restart dhclient behind an operator's `ifdown` | accepted | checks `/run/network/ifstate` |
| L7 | `OnBootSec=90s` can overlap a slow boot | accepted | 120 s; foreground client found by scanning `/proc` |
| L8 | dhcpd stop→start race | accepted | the helper waits for the pid |
| L9 | `status --check` undefined; healthcheck on nodes | accepted | defined (§8.8) |
| L10 | avahi may rename `controller` on an address change | noted | pre-existing; listed in §9 |
| L11 | step 0, STATUS.md row, SPDX on moved files | accepted | §14 step 0, §7, §8.11 |
| L12 | `ap` mode did not self-heal | accepted | retry every 5 minutes (§8.6) |
| L13 | V7 from a detached unit kills ifup's dhclient | accepted | V7 from the console |
| L14 | `-v` logs twice; `systemd-run` errors swallowed | accepted | `-v` dropped; failures logged |
| L15 | `cable-static` stanza edits take effect at the next boot | accepted | stated by the helper (§8.8) |
| A3 | violation through M2 | accepted | §10 |
| A8 | guard steps 1–3 not argued | accepted | §11 table |
| A10 | use `store::set_node_field`; test2's UUID is residue | accepted | §14 step 4; decision 5 |
| B1 | V3 masked C1; V8 proved nothing | accepted | V3, V8 strengthened |
| B2 | no video soak | accepted | V9 with a project playing and the frame counter |

## 18. Execution notes — 2026-09-29

Implemented on `fix/controller-network-modes`. Built as `cuems-common_1.3.0-23_all.deb`. V1, the build
and V2–V9 are done (results in §19); V10 waits for someone at the taller.

### Deviations from v3, and why

| # | v3 said | Implemented | Reason |
|---|---|---|---|
| X1 | no shared code | `usr/lib/cuems/net-mode.sh`, sourced by the gates, `cuems-ap-path`, the guard, `cuems-net-mode` and the hook | one definition of "controller", "routable IPv4" and "who carries the gateway"; five copies would drift. POSIX sh, `cuems_` names only, parses the conf files instead of sourcing them |
| X2 | probe: UDP socket bound to bond0:68 | `AF_PACKET`/`SOCK_DGRAM`, no client identifier | the probe runs while bond0 holds the fallback: the offer comes from a server the host has no route to (reverse-path filtering), and a UDP socket would send the DISCOVER from 192.168.6.1 instead of 0.0.0.0. A packet socket sits where dhclient itself listens |
| X3 | carrier from `ethtool` | `/sys/class/net/<if>/carrier` | same answer, no dependency inside the hook. An administratively-down interface reads as "no" |
| X4 | `release-wifi` re-enslaves any unenslaved wifi0 | it leaves wifi0 alone while it carries the gateway; `down` re-enslaves at the end | never enslave an interface that still holds the address |
| X5 | guard stops `cuems-wifi.service` | stops `cuems-wifi.target` and the service; runs `cuems-ap-path down` itself when the service is not active | through the target dhcpd goes too; and systemd runs no `ExecStop=` for an inactive unit (code review M1) |
| X6 | guard service `ConditionPathExists=/sys/class/net/bond0` | no condition; the script checks the role | `OnUnitActiveSec=` counts from the last activation, and a condition-skipped start is not one |
| X7 | `cuems-net-mode`: write `NET_MODE`, then stop the target | stop first, then write | `cuems-ap-path down` does nothing in `manual`, so writing `manual` first would strand 192.168.6.1 on wifi0 |
| X8 | hostapd gate: `manual` → 0 | `manual` → 0 only if `cuems-wifi.service` is active | code review H1: with `Requisite=` and the condition gone, a plain 0 would put hostapd on the air at every boot of a `manual` controller that does not shadow `cuems-wifi-group.conf`. This restores what `Requisite=` enforced |
| X9 | gate exits 255 when `ap.conf` is missing | not in `manual` | code review M2: the dhcpd drop-in is shadowed nowhere, so the gate also runs at Medina and formitgo |
| X10 | `etc/cuems/ap.conf`: header comment | unchanged | it is a conffile: a cosmetic change is a dpkg prompt on every host that edited it, which can stall a non-interactive upgrade |
| X11 | prerm on downgrade: hook, timer, unit | also takes the AP data path down first, outside `manual` | code review M3: after the unpack the older unit cannot move the address back |
| X12 | `cable-static`: one marked `address` line | the marker is a comment line of its own above it | interfaces(5) has no end-of-line comments |

### Corrections to the verification matrix

- **Rollback (§13) and V2** assume test2 runs 1.3.0-22. It runs **1.3.0-21**. The upgrade therefore also
  carries -22's change (the `/etc/network/interfaces` deregistration and its preinst snapshot), and the
  rollback target is `cuems-common_1.3.0-21_all.deb`.
- **V4** expects the message "refusing to serve DHCP on bond0", but nothing starts dhcpd during V4. Add
  `/usr/lib/cuems/bin/check-ip.sh dhcpd; echo $?` (expect the message and 1) to the step.
- **test2 has `cuems-nodeconf` enabled and active**, so the limitation of §6 will show in V8.

### Done without test2

- V1: `shellcheck` clean on every new script, the prerm, the lib (`-s sh`) and the hook (`-s dash`);
  `bash -n`, `dash -n`, `py_compile`; `validate-systemd.sh` parses the new units; the repo's
  `verify-package-structure.sh` reports the same ten entries as on `rc_1` (binaries of other packages).
  `scripts/test-systemd-units.sh` exits 1 on `rc_1` too.
- A network-namespace bench (real bond, veth as the cable, dummy as wifi0, `systemctl` stubbed): the three
  gates in every mode, the AP data path up and down, the hook after PREINIT/BOUND/EXPIRE/TIMEOUT, the
  probe against a responder and against silence, the guard, and the `cuems-net-mode` transitions
  including the `interfaces` edit and its byte-identical way back.
- An independent code review (Claude Opus 5.5): no critical finding and no path by which dhcpd serves on
  bond0 outside `manual`; one high, three medium and five low, all addressed (X5, X8, X9, X11, X12 above
  and the stale pid file).

### Decisions of §15, as taken by the user on 2026-09-29

| # | Decision |
|---|---|
| 1 | nodeconf in the AP state: **evaluate** — done, see §19 "nodeconf". Open again, with a recommendation |
| 2 | the AP keeps broadcasting after a cable lease arrives: **accepted** |
| 3 | postinst rewrites `INTERFACESv4`: **accepted** |
| 4 | the package enforces the fallback; `manual` is the opt-out: **accepted** |
| 5 | test2 gets an inventory row, under its **current** UUID — done 2026-09-30 in cuems-fleet (controller and node01, cluster `test2`) |
| 6 | test and test3: **decide after test2** |
| 7 | not decisions; see §19 for what the runs showed |

## 19. Verification on test2 — 2026-09-29

test2 went 1.3.0-21 → 1.3.0-23. Every run that cut access was started as a detached unit with a dead-man
timer behind it. The observer sampled `ip -4 -o addr show dev bond0` once a second.

| # | Result | What was seen |
|---|---|---|
| V2 | **pass** | `NET_MODE=auto`, `AP_ARMED=no`; `INTERFACESv4="wifi0"`; hook symlink present; `/etc/network/interfaces` byte-identical; hostapd and isc-dhcp-server list their `ExecCondition`, hostapd has no `Requisite`; prerm carries the debhelper snippet; no show process changed pid (apache reloaded, as §10 says) |
| V3 | **pass**, one unrelated failure | dhcpd and hostapd `Skipped due to 'exec-condition'`, not failed; no "Dependency failed", no ordering cycle; bond0 = 10.16.10.3 only. The hook put 192.168.6.1 on bond0 at PREINIT and removed it at BOUND, 11 s later. `is-system-running` was `degraded` because of `accounts-daemon` ("Failed to set up mount namespacing: /run/systemd/seats"), a boot race with logind that has nothing to do with this package; it started on a manual restart |
| V4 | **pass** | fallback 1 s after the flush; **0 of 278 samples** without a routable IPv4; dhcpd refused by its gate (`Result=exec-condition`). The message "refusing to serve DHCP on bond0" does not appear any more on an installed box: with `INTERFACESv4="wifi0"` bond0 is not even in the list, so the gate closes one step earlier |
| V4b | **pass**, but did not test what it meant to | with only DHCP filtered the router still answered the ping, so the recorded lease was accepted. 0 of 266 samples without an address |
| V4c | **pass** (added) | DHCP **and ICMP** filtered: the recorded lease was tried for 10 s, its router did not answer, it was flushed, and the static lease followed. This is the path of the incident. **0 of 320 samples** without a routable IPv4 |
| V5 | **pass** | the guard logged the offer and bond0 was back on 10.16.10.3 within 11 s (V4) and 2 s (V4c) of the filter going away |
| V6 | **pass** | run together with V4c, project `prova` playing: `engine_state` stayed `running` and node01 stayed reachable in every snapshot; no stop or unload in the engine journal. Audio never played in this project on this box ("No JACK server available"), which predates the test |
| V7 | **pass** | `ifdown bond0; ifup bond0` released the transient client, `cuems-dhclient-bond0.service` was collected (`LoadState=not-found`), `--failed` empty, lease restored. Run detached with `setsid`, not from the console |
| V8 | **pass** | `cuems-net-mode ap --yes`: hostapd `AP-ENABLED`, wifi0 = 192.168.6.1/24 and out of the bond, dhcpd running on `wifi0` only, forwarding 0 on wifi0, bond0 still 10.16.10.3, SSH intact, project still running. A reinstall of the package with the AP up left mode, arming and AP untouched. `auto --yes`: address off wifi0, wifi0 back in the bond, the three units skipped, none failed |
| V9 | **pass** | 70 minutes on the fallback with the project playing, after a 70-minute baseline in the same state with the guard timer stopped. 70 guard runs, all silent; one dhclient throughout; `--failed` empty; no file left behind (the only change under `/var/lib/dhcp` is the lease file the test itself emptied). videocomposer's `total unexpected` dropped-frame counter: **+0 in the baseline, +0 with the guard**. 0 of 4207 samples without a routable IPv4. Lease back 29 s after the filter went away |
| all | **pass** | no AppArmor denial in any run |

dhcpd logged `receive_packet failed on wifi0: Network is down` once, while hostapd reconfigured the
interface. Whether it still answers afterwards is only proven by a real client: **V10**.

### Defects found by the runs, fixed in c1f9ea0

- The probe exited 1 ("could not run") while the `tc` filter was on: `sendto` returns `ENOBUFS` when the
  queue drops the frame. It is now an unanswered DISCOVER, and the guard stays silent.
- `cuems-net-mode ap` printed "wifi0 carries 192.168.6.1 but hostapd is not running" and exited 1 with
  the AP up: the target is ordered before hostapd, so its start job returns first. It now waits.

### Left behind by the tests, not by the package

- avahi-autoipd's 169.254.9.198 stayed on bond0 after its daemon was gone (its own enter hook kills the
  daemon on PREINIT; the address survived the SIGKILL of the client that owned the hooks). Removed by
  hand. Worth a look: it is the same transient the old gate tripped over (D4).
- test2 is left in `auto` with **`AP_ARMED=yes`**, ready for V10. With a cable in, that changes nothing.

### nodeconf (decision 1)

Measured on test2 with the AP up and bond0 without IPv4 (DHCP and ICMP filtered):

| nodeconf is … | what happens |
|---|---|
| already running | every tick: `get_ips timed out in resident loop; retrying next tick`. No map refresh, no alias re-publication. Engines and playback unaffected. Recovers by itself when bond0 gets an address |
| (re)started in that state | `CRITICAL Could not find network interfaces within timeout`, exit with a core dump, `Restart=on-failure` every 10 s: **a crash loop for as long as bond0 has no IPv4**. Four restarts in the 75 s of the test. It came back on its own when the lease did |

This is worse than §6 says. `get_ips()` (`CuemsNodeConf.py:335`) finds the cluster address on
`ethernet1:avahi` and then keeps waiting for an IPv4 on bond0 that it only needs for the UI alias; after
10 s it raises, and `run()` turns that into `sys.exit(-1)`.

A cold boot without a cable gets past it, because nodeconf starts while bond0 still holds the fallback
and the AP moves the address afterwards. Any later restart of nodeconf does not.

Who is exposed: a controller with nodeconf enabled, the AP armed, and no lease on the cable. No fielded
box is armed by an upgrade, so nothing in the field changes until someone arms one.

Recommendation: fix it in `cuems-nodeconf`, not here. bond0 becomes optional once the cluster address is
known, and the UI address falls back to wifi0 when bond0 has none. It is a few lines, it also makes
nodeconf survive a bond0 that is simply slow, and it keeps the AP data path of this plan as reviewed.
The alternative, keeping an address on bond0 while the AP is up, means the same address on two
interfaces or a bridge, which is the design this plan rejected.
