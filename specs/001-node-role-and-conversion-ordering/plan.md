<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Implementation Plan: Node-role conversion ordering, the packaging gate, and the Avahi vocabulary cutover

**Branch**: `feat/xml-refactor` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-node-role-and-conversion-ordering/spec.md`

**Scope note**: deliberately thin. `dev/planning/cuems-utils-xml-refactor-consumer-migration.md`
§0.7 argued this repository should run a trimmed spec-kit chain — no `research.md`, no
`data-model.md`, no flow-04-scale quickstart, because this package has no object model, no
importable API and no build step. This file exists because `setup-tasks.sh` requires it, and
because the per-file scope and the constitution check below are genuinely worth writing down.
The design questions that would normally fill a plan were already settled: the ordering question
by measurement (§0.5-A of the planning document), and three more by the clarification session
recorded in the spec.

## Summary

Rename this repository's half of the Avahi discovery vocabulary — including the two template
filenames and, critically, a migration that reaches each host's **live**
`/etc/avahi/services/cuems.service`, which this package does not ship — close the postinst
ordering deferral by writing the decision down rather than re-sequencing anything, and give the
release gate the one edge this repository can actually declare plus the demonstration that has
been deferred twice. A late addition, accepted 2026-09-17, stops the shipped `network_map.xml`
from carrying a placeholder node that a take-maintainer conffile answer would install over a live
topology, makes the two map readers warn instead of failing their units when no controller is
named, and fixes the node-map conversion to reach the copies dpkg actually leaves. Two findings
moved work out: the batch document conversion belongs to
`cuems-utils` as an operator command, and the `cuems-cluster-poweroff` regression belongs to
`cuems-power-bridge` and is reported, not fixed.

## Technical Context

**Language/Version**: Bash (maintainer scripts, operator tools) and Python 3.11 (shared-venv
scripts under `usr/lib/cuems/bin/`, stdlib only). No compiled code in this package.

**Primary Dependencies**: `dpkg`/`debhelper` (compat 13) as the delivery mechanism;
`cuems-utils` for the schema this package mirrors and converts to; `avahi-daemon` as the
consumer of the discovery files; `cuems-nodeconf` as the paired half of the cutover.

**Storage**: files on a live host — `/etc/cuems/*`, `/etc/avahi/services/`,
`/usr/share/cuems/`, `/etc/sudoers.d/`. Conffiles where dpkg owns them, plain files where it
does not.

**Testing**: `pytest`, three files under `tests/`, 23 tests. Run with
`uv run --with pytest --with lxml python -m pytest tests/ -q` — the default interpreter has no
pytest. Plus a written manual upgrade check for what tests structurally cannot cover.

**Target Platform**: Debian 12 (bookworm) CUEMS hosts, controller and node roles.

**Project Type**: system-level Debian package — configuration, systemd units and operator
tools. Not an application.

**Performance Goals**: N/A. The one timing constraint is that nothing this feature adds may
extend a package upgrade by unbounded work on a live machine (Constitution I) — which is part of
why OOS-1 keeps the library conversion out of `postinst`.

**Constraints**: the upgrade must leave a working host, including one mid-show, one whose
conffiles were locally modified, and one the package manager never configures at all (file-copy
deployment). Downgrade is unsupported. Commits are GPG-signed.

**Scale/Scope**: one controller plus N nodes per cluster; four discovery files; two renamed
templates; one live file per host; one new sudoers file; three `debian/` files; ~6 documentation
files.

## Constitution Check

*GATE: passes for all six principles after the 2026-09-17 analysis remediation and the
C2/I1 decision recorded in the spec's Clarifications.*

| Principle | How this feature satisfies it |
|---|---|
| **I — upgrades on a live machine** | Every new `postinst` step is guarded and cannot fail the upgrade (FR-006). No unbounded work is added to the upgrade: OOS-1 keeps the library conversion out of it entirely. The file-copy host, which never runs `postinst`, is addressed by documentation and named in Edge Cases. FR-024 removes a shipped file's power to overwrite live topology with a wrong one; FR-025 keeps an unprovisioned node from failing two units at its next boot — damage that would otherwise appear after the upgrade, which this principle ranks worst. |
| **II — conversions back up, repeat, never fail** | FR-006 makes the live-file migration idempotent and non-fatal; **FR-006a** adds the byte-exact timestamped backup and its retention bound, which the first draft of this plan claimed without the spec requiring it; FR-007a makes refusal explicit and reported; **FR-007b** makes an unrecognised value or an inconsistent record pair a whole-file refusal that names the value and the accepted set. The rewrite is textual, so a file is never re-serialised. **FR-027** makes the existing node-map conversion reach the copies dpkg actually leaves (`.dpkg-dist`, `.dpkg-old`) instead of a `.dpkg-new` that no longer exists when `postinst` runs. |
| **III — ordering authority** | US2 exists for this: FR-013 forbids deferring a decision to a feature number, FR-012 requires the order be asserted by a test rather than claimed by a comment, FR-014 requires the record to state what this package does and does not restart. |
| **IV — mechanical gate** | FR-016 sets `>= 0.1.0rc16, << 0.1.1~`, and FR-016a verifies it by comparison against the versions that matter — so the floor keeps refusing `0.1.0rc15`, which a tilde floor would not (analysis C2). FR-016b records the library's versioning contract (rc through 0.1.0, tilde from 0.1.1, minor bump on schema change, coupled with the removal release), resolving I1 without an epoch or a consumer-wide rewrite. The one gap — a schema change inside the rc line passes the ceiling — is stated as accepted, not hidden, and is covered by the mirror test and D27. FR-018 makes the demonstration a deliverable; FR-019 records other repositories' edges, including the discovery cutover's reverse edge. |
| **V — downgrade unsupported** | Unchanged and restated in Assumptions. No reverse conversion is introduced. |
| **VI — owned, retired, signed** | FR-003a delivers the privilege in a *new* file precisely because a modified conffile is kept; FR-003b retires the old file **whole** via `rm_conffile` in all three maintainer scripts — an in-place edit could not reach a kept, modified copy — relying on the privilege system skipping dotted include names; FR-003c syntax-checks every shipped privilege file. FR-028 forbids ever de-registering the node map by bare `rm_conffile` — the constitution's 1.0.1 amendment to this principle. FR-020 requires the changelog entry. |

**Testing gate** (constitution, Testing Gate section): tests cover the live-file migration's
four owed cases — happy path, idempotence, whole-file refusal of an unrecognised value, backup
fidelity — plus byte-preservation and the unreadable-file case; the retired key's absence and the
new key's presence; a syntax check of every shipped sudoers file; the ordering assertion; the
version bounds by comparison; and the existing conversion's four cases. The manual half — the discovery daemon's live behaviour, the
sudoers privilege, conffile prompts, dpkg's refusal — is FR-021's written procedure, performed on
a controller plus at least one node.

No violations. The Complexity Tracking table is therefore empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-node-role-and-conversion-ordering/
├── spec.md                    # the specification, with its Clarifications session
├── plan.md                    # this file
├── contracts/
│   ├── avahi-txt.md           # this repository's half of the pinned vocabulary (T001)
│   └── release-gate.md        # cross-repo deliverables this repository cannot perform (T026)
├── evidence/
│   └── out-of-order-refusal.txt   # the observed dpkg refusal, both directions attempted (T027)
├── checklists/
│   └── requirements.md        # spec quality checklist, 16/16
└── tasks.md                   # /speckit-tasks output
```

Deliberately absent: `research.md`, `data-model.md`, `quickstart.md` — see the scope note.

### Source (repository root)

```text
etc/
├── avahi/services/cuems.service          # in-repo copy of the live file; NOT shipped (FR-004)
├── cuems/network_map.xml                 # conffile, emptied: no placeholder node (FR-024)
├── cuems/network_map.xml.example         # new: one node entry → /usr/share/doc/cuems-common/ (FR-026)
├── systemd/system/systemd-journal-upload.service.d/cuems-target.conf   # ExecCondition (FR-025)
├── sudoers.d/99-cuems                    # RETIRED WHOLE via rm_conffile (FR-003b)
└── sudoers.d/99-cuems-avahi              # new: all four rules, reload included (FR-003a)
usr/
├── share/cuems/cuems.service.firstrun    # TXT records only
├── share/cuems/cuems.service.master      # → cuems.service.controller (rename)
├── share/cuems/cuems.service.slave       # → cuems.service.node (rename)
├── bin/cuems-config-node                 # :64 hardcodes the three template names
└── bin/cuems-migrate-avahi-service       # new, operator-runnable (FR-021a); called from postinst
scripts/
├── cuems-write-chrony-source             # no controller → warn, drop own source, exit 0 (FR-025)
└── cuems-log-collector-url               # no controller → warn, exit 0; --check mode (FR-025)
debian/
├── preinst                               # rm_conffile for 99-cuems (FR-003b)
├── postinst                              # ordering record; migration call; rm_conffile; loop fix (FR-027)
├── postrm                                # rm_conffile for 99-cuems (FR-003b)
├── control                               # >= 0.1.0rc16, << 0.1.1~ (FR-016); Breaks kept
├── install                               # new sudoers file + new tool (templates ship by glob)
└── changelog                             # FR-020
tests/
├── test_network_map_conversion.py        # existing; .dpkg-new cases → .dpkg-dist/.dpkg-old (FR-027)
├── test_controller_resolution.py         # existing; + no-controller warning case (FR-025)
├── test_schema_mirror.py                 # existing
├── test_avahi_vocabulary.py              # new: retired key absent, new key present (FR-011)
├── test_avahi_live_migration.py          # new: four cases + byte-preservation + whole refusal
├── test_template_consumers.py            # new: every literal template reference resolves
├── test_sudoers_syntax.py                # new: visudo -cf over etc/sudoers.d/ (FR-003c)
├── test_postinst_ordering.py             # new: conversion precedes its readers; no deferrals
├── test_version_bounds.py                # new: bounds verified by dpkg comparison (FR-016a)
├── test_shipped_network_map.py           # new: shipped map valid, zero nodes (FR-024)
└── test_network_map_example.py           # new: example valid, one complete node (FR-026)
docs/
├── node-identity-contract.md             # discovery vocabulary update
├── upgrade-ordering.md                   # new: the ordering record (FR-014, FR-015)
└── upgrade-verification.md               # new: manual procedure + file-copy equivalents (FR-021/021a)
README.md                                 # 6 occurrences of the retired key
```

**Structure Decision**: no new top-level layout. The package's existing shape — `etc/`,
`usr/`, `debian/`, `tests/`, `docs/` mirrored into the installed filesystem by
`debian/install` — is unchanged. The only structural additions are one operator tool under `usr/bin/` — beside its
sibling `cuems-migrate-network-map`, because FR-021a requires operators on file-copy hosts to
run it by hand — and one sudoers file, which replaces `99-cuems` rather than joining it.

## Sequencing

1. **The cutover (US1) pairs with flow 04** (`../cuems-nodeconf`). Specs are separate because
   the repositories are; the **merges are simultaneous** (D33). Flow 04's T041/T042 read this
   repository for a reviewed counterpart branch before either side merges, so this
   repository's `contracts/avahi-txt.md` must exist and agree before that gate can clear.
2. **US2 and US3 are independent of flow 04** and can land in any order relative to it, but
   nothing releases until every 010 flow lands (D27).
3. **Phase 7 is independent of flow 04** and of US1/US3. Its one internal coupling is to US2:
   the node-map loop fix (T044) edits the `debian/postinst` block the ordering task (T021)
   rewrites, and its record (T045, T047) lands in US2's `docs/upgrade-ordering.md`.
4. **Within US1**: templates and their by-name consumers first, the live-file migration second,
   documentation third. The migration is the piece with no counterpart anywhere else, so it
   carries the most test weight.

## Complexity Tracking

> No constitution violations. Nothing to justify.
