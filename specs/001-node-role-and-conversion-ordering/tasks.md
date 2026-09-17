<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Tasks: Node-role conversion ordering, the packaging gate, and the Avahi vocabulary cutover

**Input**: Design documents from `specs/001-node-role-and-conversion-ordering/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md) (user stories and its
Clarifications session), [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

**Tests**: **required, not optional.** The constitution's Testing Gate names the cases a
conversion owes, and SC-010 asserts the suite covers them. Test tasks are therefore first-class
here, and each story's tests come before its implementation.

**Organization**: grouped by user story so each can be implemented, tested and merged as its own
increment. US1 is the MVP and the only story with a cross-repository merge gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, mapping to the spec's user stories
- Every task names the exact file it touches

## Path Conventions

This is a Debian packaging repository: paths are the repository's own tree
(`etc/`, `usr/`, `debian/`, `tests/`, `docs/`), which `debian/install` maps onto the installed
filesystem. Tests import `usr/bin/` and `usr/lib/cuems/bin/` scripts by path through
`SourceFileLoader`, the convention already used by `tests/test_network_map_conversion.py` —
these scripts have no `.py` extension and are not a package.

---

## Phase 1: Setup (shared)

**Purpose**: pin the vocabulary and build the fixtures every US1 task is checked against.

- [ ] T001 Write `specs/001-node-role-and-conversion-ordering/contracts/avahi-txt.md` — this repository's half of the pinned vocabulary: key `node_role`, values `controller`/`node`/`firstrun`, filenames `cuems.service.{firstrun,controller,node}`, two records per template (`_cuems_nodeconf._tcp:9000` and `_cuems_osc._tcp:9090`), `uuid` untouched; state which files this repository owns and which belong to flow 04
- [ ] T002 [P] Add live-discovery-file fixtures under `tests/fixtures/avahi/`: a pristine copy of each shipped template, a hand-edited variant (extra record, reordered lines, a comment, odd whitespace), an already-migrated file, an unreadable/unrelated file, and a file carrying the retired key in a shape the rewrite must refuse
- [ ] T003 [P] Add a converted-and-unconverted `network_map.xml` fixture pair under `tests/fixtures/maps/` for the ordering test, reusing the document shape already inlined in `tests/test_controller_resolution.py`

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the one thing no story may proceed past without agreement from the paired
repository.

**⚠️ CRITICAL**: T004 blocks every file edit in Phase 3. Editing a template before the
vocabulary is cross-checked is how a half-renamed cluster gets built.

- [ ] T004 Cross-check `specs/001-node-role-and-conversion-ordering/contracts/avahi-txt.md` against `../cuems-nodeconf/specs/001-network-map-object-adoption/contracts/avahi-txt.md` — key, all three values and all three filenames must agree exactly (FR-009, SC-003); record the compared revision of the counterpart in this repository's contract file

---

## Phase 3: User Story 1 — the discovery vocabulary changes everywhere a host can see it (Priority: P1) 🎯 MVP

**Goal**: after an upgrade every host — including one adopted years ago, one whose discovery
file was hand-edited, and one whose sudoers was locally modified — announces the new vocabulary
and is discovered.

**Independent test**: upgrade a controller plus at least one node; every announcement carries
the new key and value, the node appears in the controller's discovery, and no file under
`/etc/avahi/` or `/usr/share/cuems/` on either host carries the retired key.

### Tests for User Story 1

- [ ] T005 [P] [US1] Write `tests/test_avahi_vocabulary.py`: no file this repository ships or owns carries the retired TXT key, with the spec's named exceptions (the conversion tooling and the migration's own documentation) enumerated explicitly rather than pattern-matched; **and** every shipped template carries the new key in both of its service types (`_cuems_nodeconf._tcp` and `_cuems_osc._tcp`), so a deleted record fails rather than passing as clean (FR-002, FR-011, SC-002)
- [ ] T006 [P] [US1] Write `tests/test_avahi_live_migration.py` covering the constitution's four owed cases — **happy path**: a pristine file is rewritten; **idempotence**: a second run rewrites nothing, writes no backup, and reports that; **whole-file refusal**: a value outside `master`/`slave`/`firstrun`, and a file whose two records would convert inconsistently, are both left byte-identical with the offending value and the accepted set named in the report; **backup fidelity**: the backup reproduces the pre-migration bytes exactly, its name does not end in `.service`, and accumulation is pruned to the newest five — plus this migration's own: a hand-edited file is rewritten **byte-for-byte except the key and value** (comments, ordering, whitespace, extra records preserved); an absent or unreadable file is left untouched with its path reported; the call never returns non-zero (FR-006, FR-006a, FR-007, FR-007a, FR-007b, SC-005, SC-006, SC-010)
- [ ] T007 [P] [US1] Write `tests/test_template_consumers.py`: every file that names a template literally names one that exists — covering `etc/sudoers.d/*` and `usr/bin/cuems-config-node` — so a future rename cannot half-land again (FR-003)
- [ ] T008 [P] [US1] Write `tests/test_sudoers_syntax.py`: run `visudo -cf` over every file in `etc/sudoers.d/`, skipping (not failing) when `visudo` is absent from the test environment, so a malformed rule is caught in the repository instead of on a host (FR-003c)

### Implementation for User Story 1

- [ ] T009 [US1] `git mv usr/share/cuems/cuems.service.master usr/share/cuems/cuems.service.controller` and `git mv usr/share/cuems/cuems.service.slave usr/share/cuems/cuems.service.node`; no `debian/install` change is needed or wanted — they ship through the glob at `debian/install:224` (planning doc §0.5-B)
- [ ] T010 [US1] Rewrite both TXT records in each of `usr/share/cuems/cuems.service.{firstrun,controller,node}` (lines 6 and 13) to `node_role=<firstrun|controller|node>`, leaving the `uuid` records untouched
- [ ] T011 [P] [US1] Rewrite both TXT records in `etc/avahi/services/cuems.service` (lines 6 and 13) — the in-repo copy of the live file, which this package does not ship; keep it consistent so the repository does not contradict the hosts
- [ ] T012 [US1] Add the new privileged-command file `etc/sudoers.d/99-cuems-avahi` carrying **all four** rules `99-cuems` carries today, updated: the `systemctl reload avahi-daemon.service` rule and the three `cp` rules for `cuems.service.firstrun`, `.controller` and `.node`. Add it to `debian/install`. A file never shipped before installs unconditionally, so a locally modified `99-cuems` cannot block the privilege; carrying every rule is what lets T013 retire the old file whole (FR-003a, FR-003b)
- [ ] T013 [US1] Retire `etc/sudoers.d/99-cuems` **whole**: delete it from the repository and from `debian/install`, and add a hand-written `dpkg-maintscript-helper rm_conffile /etc/sudoers.d/99-cuems <this release>~ cuems-common -- "$@"` to `debian/preinst`, `debian/postinst` and `debian/postrm`, in the style of the existing acpid and grub-display retirement blocks. Record in the comment why an in-place edit was rejected (a kept, locally modified copy would retain the removed rules forever) and why the rename is safe (sudo's `#includedir` skips names containing a dot, so the `.dpkg-bak` a modified copy becomes is inert). Must land in the same commit as T012: shipping either alone leaves a window with no privilege or with duplicated rules (FR-003b, Constitution VI)
- [ ] T014 [P] [US1] Update the hardcoded template list in `usr/bin/cuems-config-node:64` to the renamed files
- [ ] T015 [US1] Write `usr/bin/cuems-migrate-avahi-service` — operator-facing, beside its sibling `usr/bin/cuems-migrate-network-map`, because file-copy hosts must run it by hand (FR-021a): a stdlib-only targeted key rewrite of `/etc/avahi/services/cuems.service` that rewrites only the retired TXT records, maps `master`→`controller` and `slave`→`node` and keeps `firstrun`, leaves every other byte unchanged, and never re-serialises the XML. Before any rewrite it writes `<path>.<UTC timestamp>.bak` — reproducing the original bytes, never ending in `.service` — and prunes to the newest five, reusing the sibling's `_BACKUP_SUFFIX_FMT` and `_prune_old_backups` approach. A value outside the accepted set, or records that would convert inconsistently, refuse the whole file and name the value and the accepted set. Idempotent, reports distinguishable outcomes, always exits 0 (FR-004, FR-005, FR-006, FR-006a, FR-007, FR-007a, FR-007b)
- [ ] T016 [US1] Add `usr/bin/cuems-migrate-avahi-service` to `debian/install`, and add its `chmod +x` guard to `debian/postinst` beside the existing one for `cuems-migrate-network-map`
- [ ] T017 [US1] Call the migration from `debian/postinst`, guarded (`[ -x ]` plus `|| true`), and reload `avahi-daemon` only when the file actually changed, so an upgraded host announces the new vocabulary without a reboot (FR-006, FR-008)
- [ ] T018 [P] [US1] Update `README.md`'s six occurrences (`:227,231,232,264,306,307`) and the discovery-record description in `docs/node-identity-contract.md` to the new vocabulary (FR-010)
- [ ] T019 [US1] 🚧 **MERGE GATE (FR-009) — blocking, do not clear early.** Confirm flow 04's counterpart branch in `../cuems-nodeconf` is reviewed and ready, record its branch and commit in this branch's PR description, and agree the simultaneous-merge window. Neither half merges alone: a publisher and a listener disagreeing about the key discover nothing, silently

**Checkpoint**: US1 is independently shippable — the cluster's discovery is correct end to end.

---

## Phase 4: User Story 2 — the upgrade's ordering is decided here, and written down (Priority: P2)

**Goal**: an engineer reading the maintainer scripts can tell what runs before what and why,
with no reference to another repository's feature numbers.

**Independent test**: every ordering claim in the record is checkable against the file, and no
maintainer script defers a decision to a feature number.

### Tests for User Story 2

- [ ] T020 [P] [US2] Write `tests/test_postinst_ordering.py`: the network-map conversion appears before every in-`postinst` reader of the converted document (today `cuems-write-chrony-source`) and before the live-discovery migration; and no maintainer script contains a **deferral** as FR-013 defines it — postponing phrasing such as "deferred to feature N", "until feature N", "left for feature N" — while provenance labels stay allowed: the test MUST pass on `debian/postinst:109`'s `(feature 007, M3)` and MUST fail on the current `:113-117` deferral before T021 lands (FR-012, FR-013, SC-007, SC-008)

### Implementation for User Story 2

- [ ] T021 [US2] Replace the deferral at `debian/postinst:113-117` with the decision: state that this `postinst` carries no `#DEBHELPER#` token — only `debian/preinst:117` does — so `dh_installsystemd` injects nothing here and no map-reading CUEMS service is restarted by this script; state that the readers restart at reboot or by operator action; state the conversion's position relative to the in-script readers and to the live-discovery migration, with the reason (FR-012, FR-013, FR-014)
- [ ] T022 [P] [US2] Write `docs/upgrade-ordering.md`: what this package restarts or reloads during an upgrade — journald, rsyslog, apache2, hostapd `reenable`, ssh, rsync, **and the conditional `avahi-daemon` reload this feature adds** — versus what it only enables; that the avahi reload re-reads static service files only and fires only when the live file actually changed, which is what makes it acceptable on a host that may be mid-show (Constitution I); why the ordering question is a decision rather than a re-sequencing; and the standing obligation to correct the record if the restart behaviour changes (FR-014)
- [ ] T023 [US2] State the cluster-upgrade position in `docs/upgrade-ordering.md`: the cluster upgrades as a unit, and the engine's host-to-host project distribution is therefore never mixed-version — naming that path explicitly so the exclusion is a decision rather than an omission (FR-015)

**Checkpoint**: the deferral that outlived two renumberings is closed, and a test keeps it closed.

---

## Phase 5: User Story 3 — the release gate is mechanical, and has been seen to work (Priority: P3)

**Goal**: an out-of-order installation is refused by the package manager, and somebody has
watched it happen.

**Independent test**: build the packages, install a deliberately out-of-order combination in a
disposable environment, capture the refusal.

### Tests for User Story 3

- [ ] T024 [P] [US3] Write `tests/test_version_bounds.py`: assert via `dpkg --compare-versions` that the declared floor admits the library's final release, that the ceiling excludes the next minor, and that the pre-release spelling sorts below the corresponding final — the measurement that showed `0.1.0 < 0.1.0rc16` is true, i.e. today's floor would refuse `cuems-utils` 0.1.0 (FR-016a, SC-009a)

### Implementation for User Story 3

- [ ] T025 [US3] Set the bounds in `debian/control:12`: floor and ceiling locked to the library's minor release, in the tilde pre-release spelling (`>= 0.1.0~rc16`, `<< 0.1.1`); preserve `Breaks: cuems-nodeconf (<< 0.1.0-8)` at `:50` unchanged, and update the package description's paragraph about what the relationships enforce (FR-016, FR-017)
- [ ] T026 [P] [US3] Record in `specs/001-node-role-and-conversion-ordering/contracts/release-gate.md` the cross-repository deliverables this repository cannot perform: `cuems-utils`'s versioning obligations (content pending the C2/I1 decision); **the reverse edge of the discovery cutover** — `../cuems-nodeconf/debian/control:19` declares only `cuems-common (>= 1.0.0)`, which every current version satisfies, so flow 04's `0.1.0-8` must declare `cuems-common (>= <this release>)` or a `Breaks:` to refuse installing beside an un-renamed cuems-common; and each other consumer's own bound — including `cuems-engine`'s `pyproject.toml` `>=0.1.0rc10` versus `debian/control` `>= 0.1.0rc4` disagreement (FR-016b, FR-019)
- [ ] T027 [US3] Build the `.deb`s and run the out-of-order installation in a disposable environment, capturing versions, command and output verbatim into `specs/001-node-role-and-conversion-ordering/evidence/out-of-order-refusal.txt` — 007's T054b, deferred twice; a gate nobody has watched refuse is a claim. Attempt **both** directions of the discovery cutover and record each outcome as observed: the forward direction (renamed cuems-common, un-renamed nodeconf) must be refused; the reverse direction is expected to be refused only once flow 04 lands T026's recorded edge, and its result is recorded either way rather than assumed (FR-018, FR-019, SC-009)
- [ ] T028 [US3] Confirm in the same environment that a correctly-ordered install is **not** refused, and record it alongside the refusal — a gate that refuses everything is not a gate either

**Checkpoint**: the ecosystem's only mechanical edge is joined by a second, and both have been observed.

---

## Phase 6: Polish and cross-cutting

- [ ] T029 [P] Write `docs/upgrade-verification.md`: the manual procedure the tests structurally cannot cover — the discovery daemon's live behaviour, the role-flip privilege on a pristine and on a locally modified sudoers host, the conffile prompts, and the package manager's refusal — performed on a controller **plus at least one node**, recording versions installed and what was observed; **and** a section for hosts the package manager never configures (file-copy deployment), giving the manual equivalent of every maintainer-script step this feature adds: running `cuems-migrate-avahi-service`, installing `99-cuems-avahi` and moving `99-cuems` aside to a dotted name, and reloading `avahi-daemon` (FR-021, FR-021a, SC-011, Constitution Testing Gate)
- [ ] T030 [P] State this package's position on the project library in `docs/upgrade-verification.md` and `README.md`: a CUEMS upgrade never rewrites an operator's project documents; the batch conversion is an operator command owned by `cuems-utils`, and a library nobody converts keeps loading because the shared library converts on read (FR-022, SC-012, OOS-1)
- [ ] T031 [P] File the `cuems-power-bridge` defect report — the node-role findings written during this feature — against that repository, with the reproduction and the evidence, and note the operator-visible symptom where an operator of a converted controller will meet it: the orderly cluster power-off selects by a vocabulary this package's own conversion has removed, so it can report success having powered off nothing (FR-023, SC-013, OOS-2)
- [ ] T032 Add the `debian/changelog` entry for this release in operator-observable terms: the discovery vocabulary changed and every host's live file is migrated on upgrade; the role-flip privilege moved to a new sudoers file and why; the version bounds tightened; what did **not** change (project libraries) (FR-020, Constitution VI)
- [ ] T033 Run the full suite — `uv run --with pytest --with lxml python -m pytest tests/ -q` — and confirm every case named in SC-010 is present and passing
- [ ] T034 Perform the T029 procedure on a controller plus at least one node and record the result; the feature is not done until this exists (SC-001, SC-004, SC-011)

---

## Dependencies

**Story order**: US1 (P1) → US2 (P2) → US3 (P3) by priority, but only US1 has an external
gate. US2 and US3 touch disjoint files from US1 and from each other, so they may proceed in
parallel with US1 once Phase 2 is complete.

**Blocking edges**:

- T004 (vocabulary cross-check) blocks T009-T019. Nothing in US1 may edit a file first.
- T001 blocks T004.
- T002 blocks T006; T003 blocks T020.
- T009 (the renames) blocks T010, T012, T014, T007's green state.
- T015 blocks T016 → T017.
- T012 and T013 land **together**, in one commit: the new sudoers file without the retirement duplicates every rule; the retirement without the new file removes the privilege.
- T012 blocks T008's green state (the new file must exist to be syntax-checked).
- T019 (merge gate) blocks the merge of US1, not its implementation.
- T025 blocks T027; T027 blocks T028.
- T032 and T034 come last: the changelog describes what shipped, and the manual check verifies it.
- T031 is independent of everything — it can be filed at any point.

**Cross-repository**: T019 pairs with flow 04's T041/T042. Their merges are simultaneous (D33).
Nothing in the ecosystem releases until every 010 flow lands (D27).

## Parallel execution examples

**Phase 1** — all three at once: T001, T002, T003 (different files).

**US1 tests** — T005, T006, T007, T008 together, before any implementation task.

**US1 implementation** — after T009 lands, run T011, T014 and T018 in parallel (three
independent files); T010, T012, T013 touch files T009 renamed or the sudoers pair, so keep them
ordered.

**Across stories** — once Phase 2 clears, one worker can take US1 while another takes T020-T023
(US2) and a third takes T024-T026 (US3). Only T027/T028 need the build environment.

**Polish** — T029, T030, T031 in parallel; T032 after them; T033 and T034 last.

## Implementation strategy

**MVP = User Story 1 alone.** It is the only story with a silent failure mode and the only one
another repository is waiting on. Shipped by itself it delivers a cluster that discovers itself
correctly after an upgrade, on every host including the awkward ones.

**Increment 2 = US2.** Closes a deferral that has already outlived two renumberings, and the
test keeps it closed. No host-visible behaviour changes.

**Increment 3 = US3.** The bound is one line; the demonstration is the deliverable. It gates the
release rather than the code, so it can land last — but it must land before anything in the
ecosystem is released (D27).

**Do not batch the merge.** US1 merges in the same window as flow 04's half and only then; US2
and US3 may merge independently.
