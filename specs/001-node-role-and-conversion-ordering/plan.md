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
been deferred twice. Two findings moved work out: the batch document conversion belongs to
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

*GATE: passes. Re-checked after the clarification session.*

| Principle | How this feature satisfies it |
|---|---|
| **I — upgrades on a live machine** | Every new `postinst` step is guarded and cannot fail the upgrade (FR-006). No unbounded work is added to the upgrade: OOS-1 keeps the library conversion out of it entirely. The file-copy host, which never runs `postinst`, is addressed by documentation and named in Edge Cases. |
| **II — conversions back up, repeat, never fail** | FR-006/FR-007 make the live-file migration idempotent and non-fatal; FR-007a makes refusal explicit and reported. The rewrite is textual, so an unrecognised file is never re-serialised. |
| **III — ordering authority** | US2 exists for this: FR-013 forbids deferring a decision to a feature number, FR-012 requires the order be asserted by a test rather than claimed by a comment, FR-014 requires the record to state what this package does and does not restart. |
| **IV — mechanical gate** | FR-016/016a/016b give the bound its real form, verified by version comparison rather than by reading; FR-018 makes the demonstration a deliverable; FR-019 records other repositories' edges as theirs. |
| **V — downgrade unsupported** | Unchanged and restated in Assumptions. No reverse conversion is introduced. |
| **VI — owned, retired, signed** | FR-003a delivers the privilege in a *new* file precisely because a modified conffile is kept; FR-003b requires the dead rules' retirement to use the established `rm_conffile` discipline. FR-020 requires the changelog entry. |

**Testing gate** (constitution, Testing Gate section): tests cover the live-file migration
including the unrecognised-file case, the retired key's absence, the ordering assertion, and the
existing conversion's four cases. The manual half — the discovery daemon's live behaviour, the
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
│   └── avahi-txt.md           # this repository's half of the pinned vocabulary (to be written)
├── checklists/
│   └── requirements.md        # spec quality checklist, 16/16
└── tasks.md                   # /speckit-tasks output
```

Deliberately absent: `research.md`, `data-model.md`, `quickstart.md` — see the scope note.

### Source (repository root)

```text
etc/
├── avahi/services/cuems.service          # in-repo copy of the live file; NOT shipped (FR-004)
├── sudoers.d/99-cuems                    # conffile; its three role-flip rules become inert
└── sudoers.d/<new file>                  # FR-003a: the rules that name the renamed templates
usr/
├── share/cuems/cuems.service.firstrun    # TXT records only
├── share/cuems/cuems.service.master      # → cuems.service.controller (rename)
├── share/cuems/cuems.service.slave       # → cuems.service.node (rename)
├── bin/cuems-config-node                 # :64 hardcodes the three template names
└── lib/cuems/bin/<live-file migration>   # new helper, invoked from postinst
debian/
├── postinst                              # ordering record; the live-file migration call
├── control                               # FR-016 bounds; existing Breaks preserved
├── install                               # new sudoers file + new helper (templates ship by glob)
└── changelog                             # FR-020
tests/
├── test_network_map_conversion.py        # existing
├── test_controller_resolution.py         # existing
├── test_schema_mirror.py                 # existing
├── test_avahi_vocabulary.py              # new: retired key absent from shipped/owned files
├── test_avahi_live_migration.py          # new: rewrite, idempotence, byte-preservation, refusal
└── test_postinst_ordering.py             # new: conversion precedes its readers
docs/                                     # node-identity contract + the upgrade procedure
README.md                                 # 6 occurrences of the retired key
```

**Structure Decision**: no new top-level layout. The package's existing shape — `etc/`,
`usr/`, `debian/`, `tests/`, `docs/` mirrored into the installed filesystem by
`debian/install` — is unchanged. The only structural addition is one helper under
`usr/lib/cuems/bin/` and one sudoers file, both placed the way this package already places
such things.

## Sequencing

1. **The cutover (US1) pairs with flow 04** (`../cuems-nodeconf`). Specs are separate because
   the repositories are; the **merges are simultaneous** (D33). Flow 04's T041/T042 read this
   repository for a reviewed counterpart branch before either side merges, so this
   repository's `contracts/avahi-txt.md` must exist and agree before that gate can clear.
2. **US2 and US3 are independent of flow 04** and can land in any order relative to it, but
   nothing releases until every 010 flow lands (D27).
3. **Within US1**: templates and their by-name consumers first, the live-file migration second,
   documentation third. The migration is the piece with no counterpart anywhere else, so it
   carries the most test weight.

## Complexity Tracking

> No constitution violations. Nothing to justify.
