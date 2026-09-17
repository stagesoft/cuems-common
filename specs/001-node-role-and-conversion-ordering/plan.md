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

*GATE: passes for Principles I, II, III, V and VI after the 2026-09-17 analysis remediation.
**Principle IV has an open decision** — analysis findings C2/I1, see below.*

| Principle | How this feature satisfies it |
|---|---|
| **I — upgrades on a live machine** | Every new `postinst` step is guarded and cannot fail the upgrade (FR-006). No unbounded work is added to the upgrade: OOS-1 keeps the library conversion out of it entirely. The file-copy host, which never runs `postinst`, is addressed by documentation and named in Edge Cases. |
| **II — conversions back up, repeat, never fail** | FR-006 makes the live-file migration idempotent and non-fatal; **FR-006a** adds the byte-exact timestamped backup and its retention bound, which the first draft of this plan claimed without the spec requiring it; FR-007a makes refusal explicit and reported; **FR-007b** makes an unrecognised value or an inconsistent record pair a whole-file refusal that names the value and the accepted set. The rewrite is textual, so a file is never re-serialised. |
| **III — ordering authority** | US2 exists for this: FR-013 forbids deferring a decision to a feature number, FR-012 requires the order be asserted by a test rather than claimed by a comment, FR-014 requires the record to state what this package does and does not restart. |
| **IV — mechanical gate** | ⚠️ **OPEN.** FR-018 makes the demonstration a deliverable and FR-019 records other repositories' edges as theirs, now including the discovery cutover's reverse edge. But the bound itself is unresolved: measured with `dpkg --compare-versions`, the tilde floor FR-016a prescribes (`>= 0.1.0~rc16`) admits `0.1.0rc15` and `0.1.0rc5`, weakening the one working edge against the library (analysis C2), and no tilde spelling the library could adopt sorts above its already-published `0.1.0rcN` versions without either an epoch or a version jump (analysis I1). Pending decision. |
| **V — downgrade unsupported** | Unchanged and restated in Assumptions. No reverse conversion is introduced. |
| **VI — owned, retired, signed** | FR-003a delivers the privilege in a *new* file precisely because a modified conffile is kept; FR-003b retires the old file **whole** via `rm_conffile` in all three maintainer scripts — an in-place edit could not reach a kept, modified copy — relying on the privilege system skipping dotted include names; FR-003c syntax-checks every shipped privilege file. FR-020 requires the changelog entry. |

**Testing gate** (constitution, Testing Gate section): tests cover the live-file migration's
four owed cases — happy path, idempotence, whole-file refusal of an unrecognised value, backup
fidelity — plus byte-preservation and the unreadable-file case; the retired key's absence and the
new key's presence; a syntax check of every shipped sudoers file; the ordering assertion; the
version bounds by comparison; and the existing conversion's four cases. The manual half — the discovery daemon's live behaviour, the
sudoers privilege, conffile prompts, dpkg's refusal — is FR-021's written procedure, performed on
a controller plus at least one node.

No violations in I, II, III, V or VI. **IV is not a violation but an unresolved decision**: it
must be settled before `/speckit-implement` reaches US3, and it does not block US1 or US2.

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
├── sudoers.d/99-cuems                    # RETIRED WHOLE via rm_conffile (FR-003b)
└── sudoers.d/99-cuems-avahi              # new: all four rules, reload included (FR-003a)
usr/
├── share/cuems/cuems.service.firstrun    # TXT records only
├── share/cuems/cuems.service.master      # → cuems.service.controller (rename)
├── share/cuems/cuems.service.slave       # → cuems.service.node (rename)
├── bin/cuems-config-node                 # :64 hardcodes the three template names
└── bin/cuems-migrate-avahi-service       # new, operator-runnable (FR-021a); called from postinst
debian/
├── preinst                               # rm_conffile for 99-cuems (FR-003b)
├── postinst                              # ordering record; migration call; rm_conffile
├── postrm                                # rm_conffile for 99-cuems (FR-003b)
├── control                               # FR-016 bounds (pending C2/I1); existing Breaks kept
├── install                               # new sudoers file + new tool (templates ship by glob)
└── changelog                             # FR-020
tests/
├── test_network_map_conversion.py        # existing
├── test_controller_resolution.py         # existing
├── test_schema_mirror.py                 # existing
├── test_avahi_vocabulary.py              # new: retired key absent, new key present (FR-011)
├── test_avahi_live_migration.py          # new: four cases + byte-preservation + whole refusal
├── test_template_consumers.py            # new: every literal template reference resolves
├── test_sudoers_syntax.py                # new: visudo -cf over etc/sudoers.d/ (FR-003c)
├── test_postinst_ordering.py             # new: conversion precedes its readers; no deferrals
└── test_version_bounds.py                # new: bounds verified by dpkg comparison (FR-016a)
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
3. **Within US1**: templates and their by-name consumers first, the live-file migration second,
   documentation third. The migration is the piece with no counterpart anywhere else, so it
   carries the most test weight.

## Complexity Tracking

> No constitution violations. Nothing to justify.
