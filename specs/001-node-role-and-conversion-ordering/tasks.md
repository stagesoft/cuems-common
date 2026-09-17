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

- [X] T001 Write `specs/001-node-role-and-conversion-ordering/contracts/avahi-txt.md` — this repository's half of the pinned vocabulary: key `node_role`, values `controller`/`node`/`firstrun`, filenames `cuems.service.{firstrun,controller,node}`, two records per template (`_cuems_nodeconf._tcp:9000` and `_cuems_osc._tcp:9090`), `uuid` untouched; state which files this repository owns and which belong to flow 04
- [X] T002 [P] Add live-discovery-file fixtures under `tests/fixtures/avahi/`: a pristine copy of each shipped template, a hand-edited variant (extra record, reordered lines, a comment, odd whitespace), an already-migrated file, an unreadable/unrelated file, and a file carrying the retired key in a shape the rewrite must refuse
- [X] T003 [P] Add a converted-and-unconverted `network_map.xml` fixture pair under `tests/fixtures/maps/` for the ordering test, reusing the document shape already inlined in `tests/test_controller_resolution.py`

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the one thing no story may proceed past without agreement from the paired
repository.

**⚠️ CRITICAL**: T004 blocks every file edit in Phase 3. Editing a template before the
vocabulary is cross-checked is how a half-renamed cluster gets built.

- [X] T004 Cross-check `specs/001-node-role-and-conversion-ordering/contracts/avahi-txt.md` against `../cuems-nodeconf/specs/001-network-map-object-adoption/contracts/avahi-txt.md` — key, all three values and all three filenames must agree exactly (FR-009, SC-003); record the compared revision of the counterpart in this repository's contract file

---

## Phase 3: User Story 1 — the discovery vocabulary changes everywhere a host can see it (Priority: P1) 🎯 MVP

**Goal**: after an upgrade every host — including one adopted years ago, one whose discovery
file was hand-edited, and one whose sudoers was locally modified — announces the new vocabulary
and is discovered.

**Independent test**: upgrade a controller plus at least one node; every announcement carries
the new key and value, the node appears in the controller's discovery, and no file under
`/etc/avahi/` or `/usr/share/cuems/` on either host carries the retired key.

### Tests for User Story 1

- [X] T005 [P] [US1] Write `tests/test_avahi_vocabulary.py`: no file this repository ships or owns carries the retired TXT key, with the spec's named exceptions (the conversion tooling and the migration's own documentation) enumerated explicitly rather than pattern-matched; **and** every shipped template carries the new key in both of its service types (`_cuems_nodeconf._tcp` and `_cuems_osc._tcp`), so a deleted record fails rather than passing as clean (FR-002, FR-011, SC-002)
- [X] T006 [P] [US1] Write `tests/test_avahi_live_migration.py` covering the constitution's four owed cases — **happy path**: a pristine file is rewritten; **idempotence**: a second run rewrites nothing, writes no backup, and reports that; **whole-file refusal**: a value outside `master`/`slave`/`firstrun`, and a file whose two records would convert inconsistently, are both left byte-identical with the offending value and the accepted set named in the report; **backup fidelity**: the backup reproduces the pre-migration bytes exactly, its name does not end in `.service`, and accumulation is pruned to the newest five — plus this migration's own: a hand-edited file is rewritten **byte-for-byte except the key and value** (comments, ordering, whitespace, extra records preserved); an absent or unreadable file is left untouched with its path reported; the call never returns non-zero (FR-006, FR-006a, FR-007, FR-007a, FR-007b, SC-005, SC-006, SC-010)
- [X] T007 [P] [US1] Write `tests/test_template_consumers.py`: every file that names a template literally names one that exists — covering `etc/sudoers.d/*` and `usr/bin/cuems-config-node` — so a future rename cannot half-land again (FR-003)
- [X] T008 [P] [US1] Write `tests/test_sudoers_syntax.py`: run `visudo -cf` over every file in `etc/sudoers.d/`, so a malformed rule is caught in the repository instead of on a host. **Resolve `visudo` inside the test**, never through a symlink or an exported `PATH`: `shutil.which("visudo", path=os.pathsep.join([os.environ.get("PATH", ""), "/usr/sbin", "/sbin"]))`. Debian gives only root `/usr/sbin` on `PATH` (`ENV_SUPATH` vs `ENV_PATH` in `/etc/login.defs`), so a `PATH`-only lookup would check sudoers as root and silently skip as a user; a symlink into `/usr/bin` would be an unowned file in a dpkg-managed directory. When the tool is absent, skip with a reason naming the directories searched — and **fail instead of skipping when `CUEMS_REQUIRE_TOOLS=1`**, so the environment meant to enforce FR-003c cannot pass it vacuously. Measured 2026-09-17: `/usr/sbin/visudo -cf` runs unprivileged and parses all four currently shipped files OK (FR-003c)

### Implementation for User Story 1

- [X] T009 [US1] `git mv usr/share/cuems/cuems.service.master usr/share/cuems/cuems.service.controller` and `git mv usr/share/cuems/cuems.service.slave usr/share/cuems/cuems.service.node`; no `debian/install` change is needed or wanted — they ship through the glob at `debian/install:224` (planning doc §0.5-B)
- [X] T010 [US1] Rewrite both TXT records in each of `usr/share/cuems/cuems.service.{firstrun,controller,node}` (lines 6 and 13) to `node_role=<firstrun|controller|node>`, leaving the `uuid` records untouched (FR-001, FR-002)
- [X] T011 [P] [US1] Rewrite both TXT records in `etc/avahi/services/cuems.service` (lines 6 and 13) — the in-repo copy of the live file, which this package does not ship; keep it consistent so the repository does not contradict the hosts (FR-001)
- [X] T012 [US1] Add the new privileged-command file `etc/sudoers.d/99-cuems-avahi` carrying **all four** rules `99-cuems` carries today, updated: the `systemctl reload avahi-daemon.service` rule and the three `cp` rules for `cuems.service.firstrun`, `.controller` and `.node`. Add it to `debian/install`. A file never shipped before installs unconditionally, so a locally modified `99-cuems` cannot block the privilege; carrying every rule is what lets T013 retire the old file whole (FR-003a, FR-003b)
- [X] T013 [US1] Retire `etc/sudoers.d/99-cuems` **whole**: delete it from the repository and from `debian/install`, and add a hand-written `dpkg-maintscript-helper rm_conffile /etc/sudoers.d/99-cuems <this release>~ cuems-common -- "$@"` to `debian/preinst`, `debian/postinst` and `debian/postrm`, in the style of the existing acpid and grub-display retirement blocks. Record in the comment why an in-place edit was rejected (a kept, locally modified copy would retain the removed rules forever) and why the rename is safe (sudo's `#includedir` skips names containing a dot, so the `.dpkg-bak` a modified copy becomes is inert). Must land in the same commit as T012: shipping either alone leaves a window with no privilege or with duplicated rules (FR-003b, Constitution VI)
- [X] T014 [P] [US1] Update the hardcoded template list in `usr/bin/cuems-config-node:64` to the renamed files
- [X] T015 [US1] Write `usr/bin/cuems-migrate-avahi-service` — operator-facing, beside its sibling `usr/bin/cuems-migrate-network-map`, because file-copy hosts must run it by hand (FR-021a): a stdlib-only targeted key rewrite of `/etc/avahi/services/cuems.service` that rewrites only the retired TXT records, maps `master`→`controller` and `slave`→`node` and keeps `firstrun`, leaves every other byte unchanged, and never re-serialises the XML. Before any rewrite it writes `<path>.<UTC timestamp>.bak` — reproducing the original bytes, never ending in `.service` — and prunes to the newest five, reusing the sibling's `_BACKUP_SUFFIX_FMT` and `_prune_old_backups` approach. A value outside the accepted set, or records that would convert inconsistently, refuse the whole file and name the value and the accepted set. Idempotent, reports distinguishable outcomes, always exits 0 (FR-004, FR-005, FR-006, FR-006a, FR-007, FR-007a, FR-007b)
- [X] T016 [US1] Add `usr/bin/cuems-migrate-avahi-service` to `debian/install`, and add its `chmod +x` guard to `debian/postinst` beside the existing one for `cuems-migrate-network-map`
- [X] T017 [US1] Call the migration from `debian/postinst`, guarded (`[ -x ]` plus `|| true`), and reload `avahi-daemon` only when the file actually changed, so an upgraded host announces the new vocabulary without a reboot (FR-006, FR-008)
- [X] T018 [P] [US1] Update `README.md`'s six occurrences (`:227,231,232,264,306,307`) and the discovery-record description in `docs/node-identity-contract.md` to the new vocabulary (FR-010)
- [ ] T019 [US1] 🚧 **MERGE GATE (FR-009) — blocking, do not clear early.** Confirm flow 04's counterpart branch in `../cuems-nodeconf` is reviewed and ready, record its branch and commit in this branch's PR description, and agree the simultaneous-merge window. Flow 04 is being implemented in parallel; this gate blocks US1's **merge**, not its implementation. Neither half merges alone: a publisher and a listener disagreeing about the key discover nothing, silently

**Checkpoint**: US1 is independently shippable — the cluster's discovery is correct end to end.

---

## Phase 4: User Story 2 — the upgrade's ordering is decided here, and written down (Priority: P2)

**Goal**: an engineer reading the maintainer scripts can tell what runs before what and why,
with no reference to another repository's feature numbers.

**Independent test**: every ordering claim in the record is checkable against the file, and no
maintainer script defers a decision to a feature number.

### Tests for User Story 2

- [X] T020 [P] [US2] Write `tests/test_postinst_ordering.py`: the network-map conversion appears before every in-`postinst` reader of the converted document (today `cuems-write-chrony-source`) and before the live-discovery migration; and no maintainer script contains a **deferral** as FR-013 defines it — postponing phrasing such as "deferred to feature N", "until feature N", "left for feature N" — while provenance labels stay allowed: the test MUST pass on `debian/postinst:109`'s `(feature 007, M3)` and MUST fail on the current `:113-117` deferral before T021 lands (FR-012, FR-013, SC-007, SC-008)

### Implementation for User Story 2

- [X] T021 [US2] Replace the deferral at `debian/postinst:113-117` with the decision: state that this `postinst` carries no `#DEBHELPER#` token — only `debian/preinst:117` does — so `dh_installsystemd` injects nothing here and no map-reading CUEMS service is restarted by this script; state that the readers restart at reboot or by operator action; state the conversion's position relative to the in-script readers and to the live-discovery migration, with the reason (FR-012, FR-013, FR-014)
- [X] T022 [P] [US2] Write `docs/upgrade-ordering.md`: what this package restarts or reloads during an upgrade — journald, rsyslog, apache2, hostapd `reenable`, ssh, rsync, **and the conditional `avahi-daemon` reload this feature adds** — versus what it only enables; that the avahi reload re-reads static service files only and fires only when the live file actually changed, which is what makes it acceptable on a host that may be mid-show (Constitution I); why the ordering question is a decision rather than a re-sequencing; and the standing obligation to correct the record if the restart behaviour changes (FR-014)
- [X] T023 [US2] State the cluster-upgrade position in `docs/upgrade-ordering.md`: the cluster upgrades as a unit, and the engine's host-to-host project distribution is therefore never mixed-version — naming that path explicitly so the exclusion is a decision rather than an omission (FR-015)

**Checkpoint**: the deferral that outlived two renumberings is closed, and a test keeps it closed.

---

## Phase 5: User Story 3 — the release gate is mechanical, and has been seen to work (Priority: P3)

**Goal**: an out-of-order installation is refused by the package manager, and somebody has
watched it happen.

**Independent test**: build the packages, install a deliberately out-of-order combination in a
disposable environment, capture the refusal.

### Tests for User Story 3

- [X] T024 [P] [US3] Write `tests/test_version_bounds.py`: parse the `cuems-utils` bounds out of `debian/control` (not a hardcoded copy) and assert via `dpkg --compare-versions` that `0.1.0rc14`, `0.1.0rc15`, bare `0.1.0`, `0.1.1~rc1` and `0.1.1` are refused and `0.1.0rc16`, `0.1.0rc17` and `0.1.0+final` are admitted. The `0.1.0rc15` case is the regression guard for analysis C2: it is exactly what a tilde floor would silently admit. Skip, not fail, when `dpkg` is absent (FR-016a, SC-009a)

### Implementation for User Story 3

- [X] T025 [US3] Set the bounds in `debian/control:12` to `cuems-utils (>= 0.1.0rc16), cuems-utils (<< 0.1.1~)` — the floor deliberately keeps the library's current non-tilde spelling; preserve `Breaks: cuems-nodeconf (<< 0.1.0-8)` at `:50` unchanged; and update the package description's paragraph to say what the relationships enforce, including that the lock is partial inside the 0.1.0 rc line (FR-016, FR-016b, FR-017)
- [X] T026 [P] [US3] Record in `specs/001-node-role-and-conversion-ordering/contracts/release-gate.md` the cross-repository deliverables this repository cannot perform: `cuems-utils`'s versioning contract from FR-016b — publish `0.1.0rcN` for the rest of the 0.1.0 line and never a bare `0.1.0` (a final is `0.1.0+final`); first tilde at `0.1.1~rc1`; bump the minor on any schema change; ship 0.1.1 together with the removal release its `_deprecation.REMOVAL_RELEASE` already announces — with the measurements behind each rule and the note that its newest published package is `0.1.0rc14`, below this package's floor; **the reverse edge of the discovery cutover** — `../cuems-nodeconf/debian/control:19` declares only `cuems-common (>= 1.0.0)`, which every current version satisfies, so flow 04's `0.1.0-8` must declare `cuems-common (>= <this release>)` or a `Breaks:` to refuse installing beside an un-renamed cuems-common; and each other consumer's own bound — including `cuems-engine`'s `pyproject.toml` `>=0.1.0rc10` versus `debian/control` `>= 0.1.0rc4` disagreement (FR-016b, FR-019)
- [X] T027 [US3] Build the `.deb`s and run the out-of-order installation in a disposable environment. **Environment: `mmdebstrap --mode=unshare`**, scripted at `tests/packaging/release-gate-demo.sh` (not shipped — `debian/install` names its paths explicitly), which builds a bookworm rootfs as an unprivileged user inside a user namespace, copies the `.deb`s in, installs them in the wrong order and captures the output — reproducible from a commit rather than from a shell history. Not `debootstrap`: a root chroot leaves `postinst`'s `systemctl restart`/`invoke-rc.d … reload` calls to each tool's chroot detection plus a `policy-rc.d` stub, with real root behind any slip; not `sbuild`: it is a build tool, and this is an install test. **The counterpart packages are `equivs` stubs** built from control files under `tests/packaging/stubs/` at exact versions — `cuems-utils` `0.1.0rc14`, `0.1.0rc15`, `0.1.0rc16`, `0.1.1~rc1`; `cuems-nodeconf` `0.1.0-7`, `0.1.0-8` — because a real `cuems-utils` rc16 `.deb` does not exist yet and only the relationships are under test; install with `apt` from the local `.deb`s so every Debian dependency resolves from the mirror and the relationship under test is the only unmet one. The refusal is dpkg refusing the real cuems-common package; the evidence file states that the counterparts were stubs. Host prerequisites: `mmdebstrap`, `uidmap`, `equivs` (root install), plus the `/etc/subuid`/`/etc/subgid` ranges already present. Capturing versions, command and output verbatim into `specs/001-node-role-and-conversion-ordering/evidence/out-of-order-refusal.txt` — 007's T054b, deferred twice; a gate nobody has watched refuse is a claim. The library floor needs no special build: the published `cuems-utils 0.1.0rc14` package is below `>= 0.1.0rc16` and must be refused as-is. Attempt **both** directions of the discovery cutover and record each outcome as observed: the forward direction (renamed cuems-common, un-renamed nodeconf) must be refused; the reverse direction is expected to be refused only once flow 04 lands T026's recorded edge, and its result is recorded either way rather than assumed (FR-018, FR-019, SC-009)
- [X] T028 [US3] Confirm in the same environment that a correctly-ordered install is **not** refused, and record it alongside the refusal — a gate that refuses everything is not a gate either. The `cuems-utils` stub for this case MUST provide `/usr/lib/cuems/bin/python3` (equivs `Links: /usr/bin/python3 /usr/lib/cuems/bin/python3`): `debian/postinst:204-208` exits 1 without it, so a bare stub would fail configuration for a reason unrelated to the gate. Stubs prove the relationship metadata only; the real packages' behaviour together is the manual verification's. Upgrade-and-purge testing of cuems-common itself (`piuparts`) is out of this task's scope

**Checkpoint**: the ecosystem's only mechanical edge is joined by a second, and both have been observed.

---

## Phase 6: Polish and cross-cutting

- [X] T029 [P] Write `docs/upgrade-verification.md`: the manual procedure the tests structurally cannot cover — the discovery daemon's live behaviour, the role-flip privilege on a pristine and on a locally modified sudoers host, the conffile prompts, and the package manager's refusal — performed on a controller **plus at least one node**, recording versions installed and what was observed; **and** a section for hosts the package manager never configures (file-copy deployment), giving the manual equivalent of every maintainer-script step this feature adds: running `cuems-migrate-avahi-service`, installing `99-cuems-avahi` and moving `99-cuems` aside to a dotted name, and reloading `avahi-daemon` (FR-021, FR-021a, SC-011, Constitution Testing Gate). **Cover `/etc/cuems/network_map.xml`'s conffile prompt explicitly, answered BOTH ways**, stating what becomes of the live topology in each. dpkg prompts only when the shipped content changed since the installed version **and** the local copy was modified — which this release satisfies on every hand-edited host, because commit `9eb094d` already changed the shipped map. Keep-local: the topology stays live and is converted; the maintainer's copy sits at `.dpkg-dist`. Take-maintainer: the live map becomes the empty shipped one and the operator's topology is at `.dpkg-old`, already converted by FR-027 — give the restore command (copy `.dpkg-old` back, then validate with the command T030 establishes — **not** `xmllint`, which no dependency of this package provides; see `dev/planning/xmllint-runtime-dependency.md`). An unmodified copy is replaced silently with no prompt; say so (FR-024, FR-027, SC-014)
- [X] T030 Patch T029's validation step to use `xmlschema` from the shared venv every host already has, instead of `xmllint`: the documented command is `/usr/lib/cuems/bin/python3 -c "import sys, xmlschema; xmlschema.XMLSchema11(sys.argv[1]).validate(sys.argv[2])" /etc/cuems/network_map.xsd /etc/cuems/network_map.xml` — `XMLSchema11`, the class `cuems-utils` itself validates with (`xml/schema.py`, `xml/xml_reader_writer.py`), because the ecosystem's schemas are XSD 1.1: `script.xsd:37` carries an `xs:assert` that libxml2, and so `xmllint`, cannot evaluate, placed in `docs/upgrade-verification.md` in a fenced block the test can extract. `cuems-utils` pins `xmlschema==3.4.3` (and `lxml==6.1.0`) and cuems-common already depends on `cuems-utils`, so the interpreter and the library are guaranteed on every host; `libxml2-utils` is not. Add `tests/test_documented_validation.py`, which extracts that block and runs its Python against `etc/cuems/network_map.xsd` with the shipped map, the T041 example and an empty `<node_list/>` (all valid) and one map missing a required field (rejected, non-zero). Measured 2026-09-17 with `xmlschema==3.4.3` and exactly that command: the shipped map and an empty map exit 0, a map missing `<ip>` exits 1. The suite invocation becomes `uv run --with pytest --with lxml --with xmlschema==3.4.3 python -m pytest tests/ -q` — T034 and `plan.md` already carry it; the constitution's Testing Gate states the invocation verbatim, so raise a `/speckit-constitution` PATCH for it when this task lands rather than editing the constitution here (FR-021, FR-027, SC-014)
- [X] T031 [P] State this package's position on the project library in `docs/upgrade-verification.md` and `README.md`: a CUEMS upgrade never rewrites an operator's project documents; the batch conversion is an operator command owned by `cuems-utils`, and a library nobody converts keeps loading because the shared library converts on read (FR-022, SC-012, OOS-1)
- [X] T032 [P] The `cuems-power-bridge` defect report half is **done outside this repository**: the node-role findings are stored in that repository for its own future fix, and nothing here needs them. What remains is this repository's half of FR-023 — state the operator-visible symptom where an operator of a converted controller will meet it, in `docs/upgrade-verification.md` and in the changelog entry: the orderly cluster power-off selects nodes by a vocabulary this package's own conversion has removed, so it can report success having powered off nothing, until `cuems-power-bridge` is fixed (FR-023, SC-013, OOS-2)
- [X] T033 Add the `debian/changelog` entry for this release in operator-observable terms: the discovery vocabulary changed and every host's live file is migrated on upgrade; the role-flip privilege moved to a new sudoers file and why; the version bounds tightened; what did **not** change (project libraries) (FR-020, Constitution VI)
- [ ] T034 Run the full suite — `uv run --with pytest --with lxml --with xmlschema==3.4.3 python -m pytest tests/ -q`, with `CUEMS_REQUIRE_TOOLS=1` so no tool-dependent test can pass by skipping — and confirm every case named in SC-010 is present and passing
- [ ] T035 **Deferred until after the coordinated merge with flow 04 (T019)**: the procedure needs both halves of the discovery cutover installed together, and the features this release builds on are already functional in the field. Perform the T029 procedure on a controller plus at least one node and record the result; the feature may merge before this runs, but is not done until this exists (SC-001, SC-004, SC-011). **Answer `/etc/cuems/network_map.xml`'s conffile prompt both ways across the two hosts** — keep-local on one, take-maintainer on the other. Before upgrading, copy each host's map aside outside `/etc/cuems/`; after, record each host's resulting topology, restore the take-maintainer host from `.dpkg-old` by the T029 procedure, and confirm the restored map validates and matches the saved copy in content. SC-001 and SC-014 are demonstrated only if the cluster is intact, or recovered by the documented copy, under both answers. On the node, also confirm SC-015 against its map before provisioning (FR-024, FR-027)

---

## Phase 7: The shipped node map cannot destroy a live topology

**Raised 2026-09-17 from `cuems-nodeconf`** (its feature 001 research,
`specs/planning/09-self-node-seeding.md` §6), **accepted the same day** — see the spec's
Clarifications, FR-024 to FR-028, SC-014 and SC-015. Not a user story: it protects SC-001 from a
file this feature ships.

**Why it belongs here.** `etc/cuems/network_map.xml` ships (`debian/install:203`) as a conffile
carrying one placeholder node: uuid `0367f391-…-0001`, `node_role controller`, ip
`192.168.1.10`, `adopted True`. dpkg offers the conffile prompt when the shipped content changed
since the installed version **and** the local copy was modified. **This release already meets the
first condition** — commit `9eb094d` converted the shipped map — so every hand-edited host is
prompted, and an unmodified copy is replaced silently. Taking the maintainer's version replaces
the cluster's topology with the placeholder: adopted state gone and a controller asserted at an
address nothing answers. That is SC-001 failing, from a file this feature ships.

Live today even without the prompt: on a host whose map has not been written yet, both readers
that select the first `node_role='controller'` — `scripts/cuems-write-chrony-source` and
`scripts/cuems-log-collector-url` — resolve to `192.168.1.10`. Latent: the engine's
`_controller_ip_from_map` and `find_hosts` still match the pre-007 `NodeType.master` spelling
and so reach nothing, but `find_hosts`' `Multiple controllers found in network map` guard
becomes reachable the moment feature 010 migrates `CONTROLLER_NETWORK_FLAG`.

Emptying the map makes both readers find no controller, which today makes each **fail its unit**:
the chrony hook is `ExecStartPre=+` with no `-`, so `chrony.service` would not start on such a
node, and the uploader's `ExecStart` consumes a URL that would never be written. FR-025 turns both
into warnings.

Separately, the postinst conversion loop has targeted `network_map.xml.dpkg-new` since feature 007.
dpkg resolves the prompt before `postinst` runs, leaving `.dpkg-dist` or `.dpkg-old` instead, so
on a take-maintainer host the operator's real topology is left unconverted at `.dpkg-old`. FR-027
fixes that.

### Tests (before implementation)

- [X] T036 [P] Add `tests/test_shipped_network_map.py`: the shipped `etc/cuems/network_map.xml` parses, validates against `etc/cuems/network_map.xsd`, and declares **no** `<node>` entries — so a placeholder host can never be reintroduced into a file that ships onto every node (FR-024, SC-014)
- [X] T037 [P] Add `tests/test_network_map_example.py`: the shipped example `etc/cuems/network_map.xml.example` validates against `etc/cuems/network_map.xsd` and carries exactly one complete `<node>` with every required field, and `docs/node-identity-contract.md` references its installed path (FR-026)
- [X] T038 [P] Extend `tests/test_controller_resolution.py` with the no-controller case for both helpers, against a map with an empty `<node_list/>`: each exits 0 and writes a warning naming the map to stderr; `cuems-write-chrony-source` removes a pre-existing `cuems-master.sources` and writes none; `cuems-log-collector-url` writes no `url.env`; and its `--check` mode exits 1 on that map and 0 on a map with a controller (FR-025, SC-015)
- [X] T039 [P] Extend `tests/test_network_map_conversion.py`: replace the `.dpkg-new` simulations (`test_conversion_works_on_a_dpkg_new_sibling_path`, `test_postinst_converts_both_the_live_file_and_its_dpkg_new_sibling`, `test_postinst_loop_is_a_noop_when_no_dpkg_new_sibling_exists`) with the names dpkg actually leaves: the loop converts the live file, `.dpkg-dist` and `.dpkg-old` together, and is a no-op for whichever are absent; and assert against `debian/postinst` itself that the loop names exactly those three paths (FR-027)

### Implementation

- [X] T040 Empty the node list in `etc/cuems/network_map.xml`: replace the placeholder node with an empty `<node_list/>`, keeping the file shipped and a conffile — only its content changes. Measured 2026-09-17: an empty `<node_list/>` validates against `etc/cuems/network_map.xsd` (`node_list` and `node` both `minOccurs="0"`) (FR-024)
- [X] T041 [P] Add `etc/cuems/network_map.xml.example` — one complete, schema-valid node entry with obviously illustrative values and an XML comment per field pointing to the field table in `docs/node-identity-contract.md` — and install it to `usr/share/doc/cuems-common/` in `debian/install`, following `etc/cuems/cluster.conf.example`'s precedent at `debian/install:221`; add a pointer to it in `docs/node-identity-contract.md`'s hand-editing procedure (FR-026)
- [X] T042 [P] Change `scripts/cuems-write-chrony-source`'s node path: when the map names no controller, keep installing the client template, remove `cuems-master.sources` if present (its own generated file, the same cleanup `apply_master()` already performs), log a warning naming the map, and exit 0. Missing or unparseable map, and a controller with an empty `<ip>`, keep their existing errors — only "no controller" becomes a warning (FR-025)
- [X] T043 [P] Change `scripts/cuems-log-collector-url`: when the map names no controller, log a warning naming the map and exit 0 without writing `url.env`; add a read-only `--check` mode that exits 0 when a controller with an address exists and 1 otherwise, printing the same warning (FR-025)
- [X] T044 In `etc/systemd/system/systemd-journal-upload.service.d/cuems-target.conf`, add `ExecCondition=/usr/lib/cuems/bin/cuems-log-collector-url --check` before the existing `ExecStartPre`, with a comment: an `ExecCondition` exit of 1 skips the unit without marking it failed — the idiom `cuems-wifi.service` already uses with `check-ip.sh` — whereas an `ExecStartPre` that merely exits 0 would leave `ExecStart` running with an empty `${URL}`. While in the file, correct its stale `network_map.xml::node_type` comment to `node_role` (FR-025, SC-015)
- [X] T045 Fix the conversion loop in `debian/postinst` (the block T021 rewrites): convert `/etc/cuems/network_map.xml`, `.dpkg-dist` and `.dpkg-old`, drop `.dpkg-new`, and correct the comment that says a kept local copy leaves the maintainer's version at `.dpkg-new` — dpkg resolves the prompt before `postinst`, leaving `.dpkg-dist` (kept) or `.dpkg-old` (taken). Keep the `[ -x ]` guard and `|| true` (FR-027, Constitution II)
- [X] T046 Record the no-controller behaviour in `docs/upgrade-ordering.md` (T022's file): on a node whose map names no controller, chrony runs with no cluster source and the journal uploader is skipped, each with a warning, and neither appears in `systemctl --failed`; this is the designed outcome, and provisioning the map (from the T041 example) ends it (FR-025, SC-015)
- [X] T047 Extend the T033 `debian/changelog` entry — same entry, one release: the shipped `network_map.xml` no longer carries a placeholder node; an operator who takes the maintainer's version gets an empty topology, with their own preserved and converted at `.dpkg-old`; an unprovisioned node warns instead of failing chrony and the journal uploader; an example node entry ships under `/usr/share/doc/cuems-common/` (FR-020)

### Follow-up, recorded not executed

- [X] T048 Record in `docs/upgrade-ordering.md` the follow-up this phase deliberately does **not** do: stop shipping `etc/cuems/network_map.xml` as a conffile, keeping an in-repo copy and letting `postinst` install a starter only when the file is absent — the class of object `etc/avahi/services/cuems.service` already is. State why the smaller change came first (emptying removes the damage; de-registering removes the prompt), and state the only acceptable mechanism: **not** a bare `dpkg-maintscript-helper rm_conffile`, which moves a modified live file to `.dpkg-bak` and deletes an unmodified one — the 1.3.0-20 outcome for `/etc/network/interfaces` — but the 1.3.0-22 pattern: snapshot in `debian/preinst`, deregister, restore-if-absent in `debian/postinst`, as that file now is (FR-028, Constitution I and VI)

**Checkpoint**: the shipped map can no longer overwrite a live topology with a wrong one; a
take-maintainer host keeps a converted, restorable copy of its own; an unprovisioned node warns
instead of failing two units; and the prompt's remaining effect is documented and demonstrated
by T035.

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
- T033 and T035 come last: the changelog describes what shipped, and the manual check verifies it.
- T032 is independent of everything — it can be written at any point.
- T029 → T030 → the manual verification: the validation command the procedure uses is established and tested before anyone performs it.
- The manual verification runs only after T019's coordinated merge.
- Phase 7 tests precede their implementation: T036 → T040; T037 → T041; T038 → T042, T043; T039 → T045.
- T043 blocks T044: the `ExecCondition` calls the `--check` mode T043 adds.
- T045 edits the same `debian/postinst` block T021 rewrites, so T045 follows T021 and is not parallel with it.
- T046 and T048 touch `docs/upgrade-ordering.md`, so both follow T022 and are not parallel with each other.
- T047 lands with T033 — one changelog entry, not two.
- T040, T041 and T045 block the node-map case in T029 and T035: answering the prompt before they land documents the old behaviour.

**Cross-repository**: T019 pairs with flow 04's T041/T042 (cuems-nodeconf numbering). Their merges are simultaneous (D33).
Nothing in the ecosystem releases until every 010 flow lands (D27).

## Parallel execution examples

**Phase 1** — all three at once: T001, T002, T003 (different files).

**US1 tests** — T005, T006, T007, T008 together, before any implementation task.

**US1 implementation** — after T009 lands, run T011, T014 and T018 in parallel (three
independent files); T010, T012, T013 touch files T009 renamed or the sudoers pair, so keep them
ordered.

**Across stories** — once Phase 2 clears, one worker can take US1 while another takes T020-T023
(US2) and a third takes T024-T026 (US3). Only T027/T028 need the build environment.

**Polish** — T029, T031, T032 in parallel; T033 after them; T034 and T035 last.

**Phase 7** — tests T036, T037, T038, T039 together; then T040, T041, T042, T043 in parallel (four different files); T044 after T043; T045 after T021; T046 after T022; T047 with T033; T048 after T046.

## Implementation strategy

**MVP = User Story 1 alone.** It is the only story with a silent failure mode and the only one
another repository is waiting on. Shipped by itself it delivers a cluster that discovers itself
correctly after an upgrade, on every host including the awkward ones.

**Increment 2 = US2.** Closes a deferral that has already outlived two renumberings, and the
test keeps it closed. No host-visible behaviour changes.

**Increment 3 = US3.** The bound is one line; the demonstration is the deliverable. It gates the
release rather than the code, so it can land last — but it must land before anything in the
ecosystem is released (D27).

**Phase 7 is cheapest now.** No task in this feature has started, and the change is a handful of
small files plus their tests. After release it is far more expensive: every host that answered the prompt
with the maintainer's version has a corrupted map, and removing a conffile's content later needs
maintainer-script handling rather than an edit.

**Do not batch the merge.** US1 merges in the same window as flow 04's half and only then; US2
and US3 may merge independently.
