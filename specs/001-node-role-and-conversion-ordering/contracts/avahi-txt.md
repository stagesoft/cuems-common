<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Contract — the Avahi discovery TXT record (cuems-common's half)

**Status**: changing in this feature, as one cutover across two repositories (D33).
**Counterpart**: `../cuems-nodeconf/specs/001-network-map-object-adoption/contracts/avahi-txt.md`
(flow 04). The two files must agree on every pinned point below before either repository merges
(FR-009, SC-003).

This is a **wire contract between two daemons**. A listener reading `node_role` against a
publisher writing `node_type` discovers nothing, and the failure is silent: no error, no
exception, nodes simply never appear.

## Pinned vocabulary — the seven points both halves compare

| | Before | After |
|---|---|---|
| TXT key | `node_type` | **`node_role`** |
| Value for the controller | `master` | **`controller`** |
| Value for a node | `slave` | **`node`** |
| Value before role assignment | `firstrun` | `firstrun` (unchanged) |
| Controller template filename | `cuems.service.master` | **`cuems.service.controller`** |
| Node template filename | `cuems.service.slave` | **`cuems.service.node`** |
| First-run template filename | `cuems.service.firstrun` | `cuems.service.firstrun` (unchanged) |

Rename only — no semantic change. A host announces the same role after the cutover as before it.

## Records per template

Each template publishes the record **twice**, once per service type, and both are renamed:

| Service type | Port | Records |
|---|---|---|
| `_cuems_nodeconf._tcp` | 9000 | `node_role=<value>`, `uuid=<node uuid>` |
| `_cuems_osc._tcp` | 9090 | `node_role=<value>`, `uuid=<node uuid>` |

The `uuid` record is untouched.

## Ownership

| Repository | Owns |
|---|---|
| **cuems-common** (this) | The three shipped templates `usr/share/cuems/cuems.service.{firstrun,controller,node}`, **including their filenames**; the in-repo copy `etc/avahi/services/cuems.service`; the migration that brings each host's **live** `/etc/avahi/services/cuems.service` to the new key on upgrade (`usr/bin/cuems-migrate-avahi-service`, FR-004); every consumer in this repository that names a template literally — `etc/sudoers.d/99-cuems-avahi` (replacing `99-cuems`) and `usr/bin/cuems-config-node`; the README and node-identity contract |
| **cuems-nodeconf** (flow 04) | The publisher (`CuemsSettings.py`), the listener (`CuemsAvahiListener.py`), both translation tables, the installer's template-path construction, its test fixtures, and deleting its unshipped root-level template duplicates |

Templates ship through the glob `usr/share/cuems/* usr/share/cuems/` in `debian/install`; there
are no per-file entries to rename. The live `/etc/avahi/services/cuems.service` is **not** shipped
by any package — it is created by copying a template — which is why the migration exists.

## Cutover rule

1. Both halves are developed independently.
2. Their **merges are simultaneous**; neither lands alone (T019).
3. `cuems-common` keeps `Breaks: cuems-nodeconf (<< 0.1.0-8)`, which refuses an un-renamed
   nodeconf beside this release. The reverse edge — a renamed nodeconf beside an un-renamed
   cuems-common — can only be declared by nodeconf, and is recorded as its deliverable in
   `contracts/release-gate.md`.

## Cross-check record

| Compared | Result |
|---|---|
| Date | 2026-09-17 |
| Counterpart file | `../cuems-nodeconf/specs/001-network-map-object-adoption/contracts/avahi-txt.md` |
| Counterpart revision | `e5278bb4231f54fe755a2e0f651f4e43205f4d59` (2026-09-17) |
| TXT key | agree — `node_role` |
| Values | agree — `controller`, `node`, `firstrun` |
| Filenames | agree — `cuems.service.{firstrun,controller,node}` |
| **Seven pinned points** | **all agree** |

Compared by extracting each table's code spans rather than by reading. If the counterpart file
changes after the revision above, this comparison must be repeated before either side merges.
