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

## Summary of guidance

| Question | Guidance |
|---|---|
| Shared `.target` needed by multiple packages | Keep in `cuems-common`; components `Depends:` + enable via symlink, never ship the file themselves |
| Capability layering for partial install | Not needed today — `Wants=` already gives partial install for free; add only for concrete subsystem start/stop/mask needs |
| Installing a subset of components | Governed by `Depends:`, not targets; decide explicitly if the deployment is a cluster node or standalone |
| Standalone deployment | Real use cases exist (dev, single-box, embedding, CI); split incrementally, starting with uncoupled components |
| Resource-owned config split (audio/DMX) | Sound in principle; verify single-consumer assumptions first; document cross-repo ordering contracts |
| Future-proofing daemon swaps (OLA → successor) | Introduce a thin interface `.target` in `cuems-common` with `Before=+WantedBy=` on concrete units; avoids hardcoding daemon names in dependents |
