<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Splitting `etc/systemd/system/` out of cuems-common into component repos

**Status**: exploratory discussion, no decisions executed yet
**Date**: 2026-07-31
**Scope**: `etc/systemd/system/*` currently shipped monolithically by `cuems-common`

---

## Motivation

Plan to move systemd units out of `cuems-common` into the repos of the
components they belong to (e.g. `cuems-videocomposer`, `cuems-engine`,
`gradient-motion-engine`), so each Debian package ships its own service
wiring at install time instead of `cuems-common` owning every unit for every
component. This document captures the open questions worked through and the
resulting design guidance, before any of it is implemented.

Current unit inventory (`etc/systemd/system/`):

```
cuems-controller-engine.service   cuems-videocomposer.service(.d)
cuems-node-engine.service         cuems-gradient-motiond.service
cuems-editor.service              cuems-midiconnector.service
cuems-nodeconf.service            cuems-arm-wol.service
cuems-hdmi-audio-map.service      cuems-wifi.service / .target
jackd-cuems.service               jack-alsa-bridges.service
olad.service                      rtpmidid.service.d
cuems-controller.target/.path     cuems-node.target
+ drop-ins onto third-party units: apache2, hostapd, avahi-daemon,
  chrony, isc-dhcp-server, rsync, systemd-journal-{upload,remote}
```

---

## 1. Would a shared `.target` (e.g. `cuems-node.target`) be needed by multiple component packages, and what happens if two packages ship the same path?

**Finding**: `cuems-node.target` is the grouping anchor several node-side
services enable against (`cuems-node-engine`, `jackd-cuems`,
`jack-alsa-bridges`, `rtpmidid`, `cuems-videocomposer`, `cuems-nodeconf`).
If two independently-packaged components both shipped the literal file at
`/etc/systemd/system/cuems-node.target`, dpkg would refuse to install
whichever installs second — unowned overlapping paths are a hard error
(`trying to overwrite '...', which is also in package ...`) unless the
packages declare `Replaces`/`Conflicts`, which is the wrong tool here since
this isn't a package split/rename, it's genuinely shared infrastructure.

**Guidance**: keep `cuems-node.target`, `cuems-controller.target`,
`cuems-controller.path`, and `cuems-wifi.target` centrally owned by
`cuems-common`. Move only the per-component `.service` files into their own
repos. Those packages `Depends: cuems-common (>= <version with the target>)`
and enable themselves via `systemctl enable <name>.service` in their own
postinst — this only ever *adds* a `.wants/` symlink, which is additive and
conflict-free even when many packages point at the same target. The
`.service`'s own `[Install] WantedBy=` doesn't require it to be co-shipped
with the `.target` file.

---

## 2. Would capability-layer targets (audio/video/midi) be preferable, to allow partial installation?

**Finding**: partial installation already works today without any new
layering, because `cuems-node.target` doesn't `Requires=` any specific
service — units join it only via their own `WantedBy=`. If a component
package (e.g. `cuems-videocomposer`) isn't installed, there's simply no
symlink in `cuems-node.target.wants/`; the target starts fine with fewer
members. `Wants=` is soft — absence is not a failure.

**When an extra layer earns its keep**: only if you need to act on a
*subsystem* as a unit — e.g. `systemctl stop cuems-node-audio.target` to
stop the whole JACK stack together, order something `After=` a subsystem
being fully up (not just started), or mask a whole capability on hardware
that structurally lacks it (e.g. an audio-only appliance with no video
output). If proposed:

- `cuems-node.target` stays the role umbrella in `cuems-common`,
  `Wants=` (not `Requires=`) capability targets: `cuems-node-audio.target`,
  `cuems-node-video.target`, `cuems-node-midi.target`.
- Each capability target is thin, also shipped by `cuems-common`, also
  `Wants=`-only.
- Component services enable against their capability target instead of
  `cuems-node.target` directly.

**Guidance**: don't add this layer speculatively — only once there's a
concrete operator need for grouped start/stop/masking. Otherwise it's pure
indirection over what `Wants=` already gives for free.

---

## 3. Inverse case: installing only `cuems-videocomposer` + `gradient-motion-engine`, without the rest of the node role

**Finding**: this is governed by Debian `Depends:`, not by systemd target
files. `WantedBy=` only controls what *starts* among units that are
*installed*; it never pulls in packages. `apt install cuems-videocomposer
cuems-gradient-motiond` already installs only those two (+ whatever they
genuinely `Depends:` on) as long as neither package hard-depends on
`jackd-cuems`, `rtpmidid`, or `cuems-node-engine` — those should be
`Recommends:` at most. `cuems-node.target` itself costs nothing to have
present even with only one member enabled against it.

**The real fork this surfaces**: should these two components still be
**cluster node members** (subject to `network_map.xml` role assignment,
chrony master/slave sourcing, mDNS identity, `master.ip` hooks — see the
[role/target model](../../CLAUDE.md#roles--targets) in the repo root
CLAUDE.md), or a **fully standalone deployment** with none of that cluster
machinery? If cluster member: keep `WantedBy=cuems-node.target` as-is — the
absent audio/midi units simply don't materialize. If standalone: anchoring
to `cuems-node.target` is semantically wrong regardless of whether it
"works" (that target implies role/identity participation); such a
deployment should `WantedBy=multi-user.target` directly and skip
`cuems-common`'s role scaffolding (`network_map.xml`, chrony, avahi)
entirely.

---

## 4. Where would a fully standalone deployment be useful, and pros/cons of the split

### Standalone use cases identified

- **Dev/test workstation** — iterating on visuals/effects locally without a
  `network_map.xml`, controller, or avahi cluster.
- **Single-box fixed install** — one video output driven directly by an
  external OSC/DMX source, not a CUEMS controller; the adoption/identity
  dance is pure overhead.
- **Third-party embedding** — using a renderer as a component inside a
  non-CUEMS show-control stack.
- **CI/container testing** — spinning a service up in isolation for
  integration tests without full node bring-up.

### Pros of splitting

- Enables all of the above — reuse outside the CUEMS cluster product.
- Smaller install footprint; embedded/constrained targets pull only what
  they run.
- Independent release cadence per component, decoupled from `cuems-common`
  version bumps.
- Matches systemd's existing loose coupling (`Wants=`, not `Requires=`) —
  the architecture already tolerates partial presence.

### Cons / risks

- **Cross-cutting fixes get harder to land.** Precedent in this repo: the
  OLA cold-boot race fix (`cuems-node-engine.service After=olad.service`,
  released in `cuems-common` 1.3.0-12) and the systemd-estate cleanup commit
  touched several units *together*, in one release. Split across repos,
  that becomes a multi-repo coordination exercise — one component can drift
  out of sync with a fix the others received.
- **Dependency-matrix growth.** "Full node," "capability-only node," and
  "standalone, no cluster" are different `Depends:`/`Recommends:` shapes per
  component, each needing its own test coverage.
- **Config ownership ambiguity.** If a "standalone" component still reads
  `/etc/cuems/*`, it isn't actually independent of `cuems-common` — decide
  explicitly whether "standalone" means *no cluster role* while still using
  `cuems-common`'s config schema (fine — the package is lightweight, no
  compiled code), vs. truly zero-dependency (config duplication risk).
- **Avoid unit-file duplication.** Don't ship two parallel unit sets per
  component (one for cluster mode, one for standalone). Reuse the pattern
  already in this codebase — `systemd-journal-upload`'s drop-in uses
  `ConditionPathExists=!/etc/cuems/master.ip` for role-aware suppression —
  so a single unit no-ops appropriately depending on whether cluster config
  is present.

**Guidance**: split incrementally, starting with components that have no
cross-cutting ordering coupling to other units (`cuems-videocomposer`,
`gradient-motion-engine` are good first candidates — they don't share
ordering constraints with `olad`/`jackd` the way the audio stack does).
Keep `cuems-common` as the dependency for shared config/target scaffolding
rather than pursuing zero-dependency purity.

---

## 5. Splitting by resource ownership: JACK/audio → `cuems-audioplayer`, OLA/DMX → `cuems-dmxplayer`

**Finding**: sound in principle — "the package that spawns/depends on a
daemon ships that daemon's wiring" mirrors the drop-in pattern already used
in this directory for third-party daemons CUEMS doesn't own (`apache2`,
`hostapd`, `chrony`, `avahi-daemon`). JACK and OLA are the same shape of
problem: third-party daemons that specific CUEMS components drive.

Two concrete things to verify before executing, both surfaced by this
repo's own history:

1. **`olad.service` is a full top-level unit, not a `.d` drop-in** — unlike
   every other third-party integration in this directory. Resolve this
   inconsistency regardless of the split: either it's a genuine full
   override of upstream OLA's packaging (in which case it belongs with the
   profile logic — `cuems-ola-profile eurolite-mk2` — in
   `cuems-dmxplayer`), or it should become a drop-in like its siblings.
   Check upstream OLA's own `.deb` packaging before deciding.

2. **`cuems-node-engine.service After=olad.service`** is the exact ordering
   fix from the cold-boot DMX race (`cuems-common` 1.3.0-12, see repo root
   CLAUDE.md "Field notes / gotchas"). If `olad.service` moves into
   `cuems-dmxplayer`, that `After=` line becomes a cross-repo contract:
   node-engine's race-freedom depends on `cuems-dmxplayer` continuing to
   ship a unit literally named `olad.service`. systemd won't error if it's
   missing or renamed — the race fix would silently regress with no
   packaging-level signal. See §6 for the recommended fix to this
   fragility.

**JACK needs verification, not assumption.** `jackd-cuems.service` and
`jack-alsa-bridges.service` look audioplayer-exclusive, but confirm nothing
else on a node depends on JACK being up (e.g. any JACK-transport or
JACK-MIDI relationship from `rtpmidid` or `cuems-videocomposer`) before
moving them fully into `cuems-audioplayer`. If JACK turns out to be a
shared dependency, it belongs in `cuems-common` (or a dedicated shared
package) under the same reasoning as the `.target` files in §1 — not
inside a single component's exclusive ownership.

**Guidance**: proceed with resource-owning the config (audio →
`cuems-audioplayer`, OLA/DMX → `cuems-dmxplayer`), but first (a) confirm
single-consumer status for JACK, (b) resolve the `olad.service`
full-unit-vs-drop-in question against upstream OLA packaging, and (c)
explicitly document the `After=olad.service` cross-package ordering
contract in whichever repo/CLAUDE.md ends up owning it.

---

## 6. Decoupling dependents from the concrete daemon: an interface/contract unit

**Question that prompted this**: could the OLA race fix be the right place
to introduce a strictly-named interface layer, so that a future DMX daemon
swap (replacing OLA) doesn't require rewriting every dependent unit across
every repo?

**Finding — yes, and there's systemd prior art for exactly this**:
`display-manager.service`, `dbus.service`, `network-online.target` are all
stable interface names that concrete implementations bind to, so dependents
never reference the concrete daemon by name.

Two mechanisms, solving different halves of the problem:

- **`Alias=`** — a concrete unit's `[Install]` can declare
  `Alias=cuems-dmx-daemon.service`; enabling it creates a second symlink
  under that name. This decouples *naming* only — it adds **no ordering
  guarantee**, so it does not by itself protect against the original race.

- **A thin interface `.target`** (recommended) — e.g. `cuems-dmx.target`,
  shipped once by `cuems-common` alongside the other shared targets from
  §1. The concrete daemon (`olad.service` today, in `cuems-dmxplayer`)
  declares **both**:

  ```ini
  [Install]
  WantedBy=cuems-dmx.target

  [Unit]
  Before=cuems-dmx.target
  ```

  Dependents write `After=cuems-dmx.target` instead of
  `After=olad.service`. `WantedBy=` alone does not imply ordering in
  systemd — the `Before=` line on the concrete unit is what makes the
  interface target a real ordering barrier, so both are required.

**Why this fixes the fragility from §5**: today
`cuems-node-engine.service After=olad.service` hardcodes the concrete
implementation. With the interface target, swapping OLA for a future DMX
daemon is contained entirely inside `cuems-dmxplayer`: drop `olad.service`,
ship `newdmxd.service` with the same `Before=+WantedBy=cuems-dmx.target`
stanza — `cuems-node-engine.service` in the engine repo needs zero changes.

**Placement**: the interface target belongs in `cuems-common`, in the same
category as `cuems-node.target`/`cuems-controller.target` — a stable
contract multiple repos rely on existing, not an implementation. Only the
concrete daemon units move out to their component repos. If JACK is
confirmed multi-consumer (§5), the same pattern (`cuems-audio.target`)
would apply there.

**Discipline required**: the contract becomes "any package providing DMX
output must ship a unit with `Before=cuems-dmx.target` +
`WantedBy=cuems-dmx.target`." Nothing at packaging time enforces this — it
needs to be written down (target repo's README/CLAUDE.md) as explicitly as
a function signature. Getting it wrong silently loses the ordering
guarantee, the same failure mode as the hardcoded-name version, just moved
one layer up.

---

## 7. File-control requirements — what each unit needs on disk, and which package puts it there

**Audited 2026-09-15** against `etc/systemd/system/*`, `debian/install`, and the sibling
repositories' packaging branches.

Moving a `.service` file moves the unit. It does **not** move the files the unit reads, and
several of those are not shipped by the package that ships the unit — one class is shipped by
*no* package at all. A component repository that takes ownership of a unit without taking
ownership of that unit's inputs produces a package that installs cleanly and fails at start.
This section is the inventory a split has to satisfy.

### 7.1 The five provenance classes

| Class | Meaning | Examples |
|---|---|---|
| **A — packaged here** | `cuems-common` ships it via `debian/install`; conffile or plain | `etc/cuems/network_map.xml`, `ap.conf`, `gpu-pin.conf`, `cluster-poweroff.conf`, the `usr/share/cuems/` templates |
| **B — venv-shipped** | Installed under `/usr/lib/cuems/` by a `dh-virtualenv` package | `/usr/lib/cuems/bin/{node-engine,controller-engine,cuems-editor,cuems-midiconnector,cuems-nodeconf}`, the interpreter, `site-packages/rtmidi` |
| **C — generated at start** | Written to `/run` (tmpfs) by an `ExecStartPre` helper `cuems-common` ships; never on disk at install time | `/run/cuems/videocomposer.env`, `/run/cuems/display.conf`, `/run/cuems/rtpmidid.ini`, `/run/cuems/hostapd.conf`, `/run/cuems-journal-upload/url.env` |
| **D — hand-placed, authority elsewhere** | Required at runtime, shipped by nobody; its schema and reference template live in another repository | `/etc/cuems/settings.xml`, `/etc/cuems/settings.xsd` |
| **E — template-derived** | A shipped template exists; the live file is created by *copying* it, and the live path is owned by no package | `/etc/avahi/services/cuems.service`, `/etc/avahi/avahi-daemon.conf`, `/etc/dhcp/dhcpd.conf`, `/etc/cuems/master.ip` |

Classes **D** and **E** are the ones that break a split silently: in both, `Depends:` on the
"owning" package delivers nothing to the path the unit names.

### 7.2 Per-unit inventory

| Unit | Needs at runtime | Class | Who provides it today | What a split must arrange |
|---|---|---|---|---|
| `cuems-videocomposer.service` | `/usr/bin/cuems-videocomposer` | own pkg | `cuems-videocomposer` | moves with the unit |
| | `/etc/cuems/settings.xml` (`output_latency_ms`) | **D** | **nobody** — schema + template in `cuems-utils` source | decide: ship a template + first-install copy, or document it as operator state |
| | `/run/cuems/videocomposer.env` | C | `cuems-extract-video-latency` (`cuems-common`) | the helper must move with the unit or stay a declared dependency |
| | `/etc/cuems/videocomposer-flags.env` (optional) | A (`.example` only) | `cuems-common` ships the `.example`; live file is operator-made | move the `.example` with the unit — it *is* the key documentation |
| | `/run/cuems/display.conf` | C | `cuems-generate-display-conf`, from this unit's own drop-in | stays with the unit; the engines consume it (ordering contract) |
| | `/var/lib/cuems` (`HOME=`) | dir | `cuems-common` (tmpfiles/adduser) | a standalone package must create it itself |
| `cuems-node-engine.service` / `cuems-controller-engine.service` | `/usr/lib/cuems/bin/{node,controller}-engine` | **B** | `cuems-engine` venv | see 7.3-②: the venv root is shared |
| | `LD_LIBRARY_PATH=/usr/lib/cuems/lib/python3.11/site-packages/rtmidi` | **B** | `cuems-engine` venv — **a hardcoded Python minor version** | any interpreter bump silently breaks it; a split must own or parameterise this |
| | `/run/cuems/display.conf` | C | `cuems-videocomposer`'s drop-in | cross-package ordering contract (§6 applies) |
| | `/etc/cuems/network_map.xml`, `settings.xml` | A / **D** | `cuems-common` / nobody | the map moves with role scaffolding; settings does not exist |
| `cuems-editor.service` | `/usr/lib/cuems/bin/cuems-editor`, `/run/cuems-editor/service.pid` | B / C | `cuems-editor` venv / runtime | — |
| `jackd-cuems.service` | `/usr/bin/jackd` | third party | `jackd2` | `Depends:` |
| | `/etc/default/jack` (optional) | **nobody** | shipped by no package in this ecosystem | a `cuems-audioplayer` split must decide whether it owns the tuning file |
| `jack-alsa-bridges.service` | `/usr/bin/zita-j2a`, `alsactl`, `/run/alsa` | third party | `zita-ajbridge`, `alsa-utils` | `Depends:`; the hardcoded `hw:HID,0` is host state, not package state |
| `cuems-gradient-motiond.service` | `/usr/bin/gradient-motiond` | own pkg | `cuems-gradient-motiond` | moves with the unit |
| | `/etc/cuems/gradient-motiond.env` (optional) | A (`.example` only) | `cuems-common` | move the `.example` with the unit |
| `cuems-midiconnector.service`, `cuems-nodeconf.service` | `/usr/lib/cuems/bin/*` | B | their venvs | — |
| `rtpmidid.service.d` drop-in | `/run/cuems/rtpmidid.ini` ← `/usr/share/cuems/rtpmidid/default.ini.{controller,node}` + `/etc/cuems/master.ip` | C ← A + **E** | `cuems-common` | role scaffolding: keep central (§1 reasoning) |
| `chrony.service.d` drop-in | `/etc/cuems/network_map.xml`, `master.ip`, `/usr/share/cuems/chrony-*.template` | A + **E** | `cuems-common` | keep central |
| `hostapd.service.d`, `cuems-wifi.service` | `/run/cuems/hostapd.conf` ← `hostapd.conf.template` + `/etc/cuems/ap.conf`; `check-ip.sh` | C ← A | `cuems-common` | keep central |
| `cuems-gpu-pin.service` | `/etc/cuems/gpu-pin.conf` | A (conffile, ships `false`) | `cuems-common` | moves only with the hardware policy |
| `cuems-cluster-poweroff.service` | `/etc/cuems/cluster-poweroff.conf`, `network_map.xml`, `settings.xml` (own uuid), the bridge venv | A + **D** + B | `cuems-common` + nobody + `cuems-power-bridge` | see 7.3-① |
| `systemd-journal-upload.service.d` | `/run/cuems-journal-upload/url.env`, `/etc/cuems/master.ip` | C + **E** | `cuems-common` | keep central |
| Avahi discovery | `/etc/avahi/services/cuems.service` ← `/usr/share/cuems/cuems.service.{firstrun,master,slave}` | **E** ← A | template shipped; **live file shipped by nobody** | see 7.3-③ |

### 7.3 The findings that actually bite

**① `/etc/cuems/settings.xml` and `settings.xsd` are required by units and shipped by no
package.** `cuems-videocomposer.service`'s `ExecStartPre` reads `settings.xml`, the engines read
it, `cuems-cluster-poweroff` reads the node's own uuid from it, and `docs/latency-tuning.md`
tells operators to validate it against `/etc/cuems/settings.xsd`. Neither path is in this
package's `debian/install`, and `cuems-utils`'s `.deb` is a `dh-virtualenv` build whose
`debian/rules` installs **only the venv under `/usr/lib/cuems`** — no `debian/install`, no
`.links`, nothing under `/etc`. The *authority* for the file is `cuems-utils` (it owns
`settings.xsd` and the per-node template in its source tree, and its changelog tracks the
schema's fields); the *deployment* is an operator copy. So `Depends: cuems-utils` does not put
`settings.xml` on a host, and a future `cuems-videocomposer` package that assumes it does will
install cleanly and fail at first start on a fresh box. **A split must decide explicitly**:
either the component package ships a template and first-install-copies it (the pattern this
repo already uses for `avahi-daemon.conf`/`dhcpd.conf` — copy on `[ -z "$2" ]` only, so
operator edits survive upgrades), or it stays hand-placed and that is stated in the package
description, not assumed.

**② `/usr/lib/cuems/` is a shared multi-package tree.** `cuems-utils` and `cuems-engine` are
both `dh-virtualenv` builds with `--install-suffix cuems`, i.e. both rooted at
`/usr/lib/cuems/`, and `cuems-common` additionally ships eleven of its own helpers into
`/usr/lib/cuems/bin/` via `debian/install`. Overlapping *identical* paths between packages are a
dpkg hard error unless `Replaces:`/`Conflicts:` is declared, and `cuems-engine`'s
`debian/control` declares neither against `cuems-utils` (its only `Conflicts:` is on
`cuems-engine-mock`). Whatever the current state is on a live host — and the `dpkg-db` drift
note in the repo-root CLAUDE.md means the database may not answer honestly there — **this must
be established before any further package is pointed into that tree.** A split that adds a
fourth writer to `/usr/lib/cuems/bin/` without resolving it is adding a third way for two CUEMS
packages to become mutually uninstallable.

**③ Template-derived files (class E) are not reachable by shipping a template.** The live
`/etc/avahi/services/cuems.service` is created by copying one of three shipped templates; no
package owns the live path. The same is true of `avahi-daemon.conf`, `dhcpd.conf` and
`/etc/cuems/master.ip`. Consequence for a split: **a package that ships only the template
cannot claim to control the runtime file** — changing the template changes nothing on an
already-deployed host until something re-copies it, and on a cluster where `cuems-nodeconf` is
disabled, nothing does. The same finding is what forced a live-file migration step into feature
010's spec (`specs/001-node-role-and-conversion-ordering`, FR-004). Any unit whose behaviour
depends on a class-E file needs a named mechanism that reaches the live copy, in whichever
package ends up owning the unit.

**④ The `.example` files are the interface documentation.** `videocomposer-flags.env.example`,
`gradient-motiond.env.example` and `cluster.conf.example` are shipped by `cuems-common`; the
live files are optional and operator-made (`EnvironmentFile=-`). If the unit moves and the
`.example` does not, the operator keeps a unit whose tunables are undocumented on the host.
Move them together.

**⑤ Version-pinned paths inside units.** `cuems-{node,controller}-engine.service` hardcode
`/usr/lib/cuems/lib/python3.11/site-packages/rtmidi` in `LD_LIBRARY_PATH`. That path is valid
only for the interpreter `cuems-utils`'s packaging pins (`/usr/bin/python3`, 3.11 on bookworm).
Whoever ends up owning those units owns that coupling; it belongs in the same repository as the
venv it points into, or it must be computed at start rather than written literally.

### 7.4 The rule this section exists to state

> **A package that ships a unit MUST also ship — or name, in its own packaging, the package or
> the operator step that provides — every path that unit references.**

Checklist to run against any unit before moving it out of `cuems-common`:

- [ ] Every `ExecStart*`, `EnvironmentFile=`, `Environment=` path classified A-E.
- [ ] Every class-A input either moves with the unit or becomes a declared `Depends:` with a
      version floor that guarantees the path exists.
- [ ] Every class-C helper either moves with the unit or is declared; a generator and its
      consumer must not end up in packages that can be installed independently.
- [ ] Every class-D input has a named deployer — or the package documents that it has none.
- [ ] Every class-E input has a named mechanism that reaches the *live* file, not just the
      template.
- [ ] No path collides with another package's tree (see 7.3-②).
- [ ] `.example` files travel with the unit that reads their live counterpart.

---

## Open items to verify before executing any of this

- [ ] Does anything besides `cuems-audioplayer` consume JACK
      (`jackd-cuems.service` / `jack-alsa-bridges.service`)? Check
      `rtpmidid` and `cuems-videocomposer` for JACK-transport/JACK-MIDI
      dependencies.
- [ ] Is `olad.service` a full CUEMS-authored unit or should it be a `.d`
      drop-in onto upstream OLA's own unit? Check upstream OLA's Debian
      packaging.
- [ ] Confirm which other units besides `cuems-node-engine.service`
      currently order against `olad.service`, `jackd-cuems.service`, or
      `jack-alsa-bridges.service`, to scope the full blast radius of the
      split.
- [ ] Decide package naming/versioning contract for `cuems-common` as the
      permanent home of shared `.target` interface units once component
      `.service` files move out.
- [ ] **Establish whether `cuems-utils` and `cuems-engine` can be co-installed**
      at all: both are `dh-virtualenv` builds rooted at `/usr/lib/cuems/`, and
      neither declares `Replaces:`/`Conflicts:` against the other (§7.3-②).
      Check a real host by file, not by `dpkg-query`.
- [ ] **Decide who deploys `/etc/cuems/settings.xml` and `settings.xsd`** — no
      package does today, and two units plus three tools require them (§7.3-①).
- [ ] For each unit proposed for a move, run the §7.4 checklist and record the
      A-E classification of its inputs alongside the move.

## Summary of guidance

| Question | Guidance |
|---|---|
| Shared `.target` needed by multiple packages | Keep in `cuems-common`; components `Depends:` + enable via symlink, never ship the file themselves |
| Capability layering for partial install | Not needed today — `Wants=` already gives partial install for free; add only for concrete subsystem start/stop/mask needs |
| Installing a subset of components | Governed by `Depends:`, not targets; decide explicitly if the deployment is a cluster node or standalone |
| Standalone deployment | Real use cases exist (dev, single-box, embedding, CI); split incrementally, starting with uncoupled components |
| Resource-owned config split (audio/DMX) | Sound in principle; verify single-consumer assumptions first; document cross-repo ordering contracts |
| Future-proofing daemon swaps (OLA → successor) | Introduce a thin interface `.target` in `cuems-common` with `Before=+WantedBy=` on concrete units; avoids hardcoding daemon names in dependents |
| Files a moved unit needs at install time | §7: classify every referenced path A-E; a package that ships a unit must ship or name the provider of every path it references. Two paths (`settings.xml`, `settings.xsd`) are provided by **no package today** |
| Shared `/usr/lib/cuems/` venv tree | Three packages write into it and none declares `Replaces:`/`Conflicts:`; resolve before pointing a fourth at it |
