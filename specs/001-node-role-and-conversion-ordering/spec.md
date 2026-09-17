<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Feature Specification: Node-role conversion ordering, the packaging gate, and the Avahi vocabulary cutover

**Feature Branch**: `feat/xml-refactor`

**Created**: 2026-09-15

**Status**: Draft — clarified 2026-09-15 (see Clarifications)

**Input**: Feature 010 flow 03 (`cuems-common`), from
`dev/planning/cuems-utils-xml-refactor-consumer-migration.md` §5, with §4's context block as
corrected against the tree on 2026-09-15 (§0.5 of the same document).

**Pairs with**: `../cuems-nodeconf` flow 04
(`specs/001-network-map-object-adoption`). Their merges are simultaneous (D33).

---

## Clarifications

### Session 2026-09-15

- Q: How should the upgrade decide that a host's live `/etc/avahi/services/cuems.service` is safe to rewrite? → A: Targeted key rewrite of any file carrying the retired key — rewrite only the TXT records, leave every other byte unchanged.
- Q: How should the role-flip privilege survive the template rename on hosts whose `99-cuems` conffile was locally modified? → A: Ship the rules in a NEW sudoers file naming the new templates; a new conffile installs unconditionally, so a kept local copy cannot block it. The old rules become inert.
- Q: What upper bound should this package declare against `cuems-utils`? → A: Lock by minor release — `>= 0.1.0~rc16, << 0.1.1` — and make that bound mean something with a cross-repo rule: `cuems-utils` bumps the minor version for any schema change. Measured with `dpkg --compare-versions`: `0.1.0rc17 < 0.1.1` is true, so the ceiling alone does not constrain the rc line; and `0.1.0 < 0.1.0rc16` is true, so the pre-release spelling must become `~rc` or the floor refuses the real 0.1.0 release. *(Superseded 2026-09-17 — the tilde floor this implied was measured to weaken the gate; see the next session.)*

### Session 2026-09-17

Opened by `/speckit-analyze` findings C2 and I1, which measured the 2026-09-15 answer as unworkable: a tilde floor (`>= 0.1.0~rc16`) admits `0.1.0rc15` and `0.1.0rc5`, and no tilde spelling cuems-utils could adopt sorts above its published `0.1.0rcN` packages without an epoch or a version jump — while an in-place `0.1.0~rc17` is refused by engine's and nodeconf's existing floors and is a downgrade to apt.

- Q: How should cuems-utils reach a correct Debian pre-release spelling, and what floor does this package ship meanwhile? → A: **Stay `rcN`, tilde from 0.1.1.** cuems-utils keeps publishing `0.1.0rcN` packages for the rest of the 0.1.0 line, never publishes a bare `0.1.0` package, and first uses the tilde at `0.1.1~rc1`. This package ships `>= 0.1.0rc16, << 0.1.1~`. The accepted gap: the ceiling cannot catch a schema change inside the remaining rc line; the mirror's byte-identity test and D27 cover that window.
- Q: The minor-bump rule makes the next schema change release 0.1.1, which cuems-utils' deprecation warnings promise as the removal release — how are they reconciled? → A: **Kept coupled.** The next schema change ships as 0.1.1 together with the removal of the deprecated surface; D27 already forbids release until every consumer flow has landed, so consumers are migrated by then regardless.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The discovery vocabulary changes everywhere a host can see it (Priority: P1)

An operator upgrades a cluster. Afterwards every host — controller and nodes — announces
itself with the new discovery vocabulary, every host's listener reads the same vocabulary, and
the cluster's topology is intact. No host is left announcing the retired word, including hosts
adopted long before the upgrade, whose live discovery file this package never placed.

**Why this priority**: it is the only part of this feature with a **silent** failure mode. A
publisher and a listener that disagree about the key discover nothing — no error, no
exception, nodes simply never appear — and it is the half of a two-repository cutover whose
counterpart is already specified and waiting. Everything else here fails loudly or fails late;
this fails invisibly, during a show.

**Independent Test**: upgrade a controller plus at least one node; confirm every announcement
carries the new key and value, that the node appears in the controller's discovery, and that
no file under `/etc/avahi/` or `/usr/share/cuems/` on either host still carries the retired
word. Delivers value even if nothing else in this feature ships.

**Acceptance Scenarios**:

1. **Given** a host running the previous package version whose live discovery file announces
   the retired key, **When** the package is upgraded, **Then** the host's live announcement
   carries the new key and the value matching its role, with no operator intervention.
2. **Given** a hand-edited live discovery file that still carries the retired key, **When** the
   package is upgraded, **Then** the key and its value are rewritten and every other byte —
   the operator's edits, comments, ordering and whitespace — is unchanged.
3. **Given** a live discovery file that is absent, unreadable, or carries the retired key in a
   shape the rewrite does not match, **When** the package is upgraded, **Then** it is left
   untouched, its path is reported with the action to take, and the upgrade still succeeds.
4. **Given** an upgraded host, **When** the operator switches its role using the documented
   privileged command, **Then** the command succeeds: the privilege covers the template's
   current name.
4a. **Given** a host whose privileged-command file was locally modified before the upgrade,
   **When** the package is upgraded and the operator switches its role, **Then** the command
   still succeeds, with no prompt resolved and no manual edit.
5. **Given** the two repositories' halves of the cutover, **When** their pinned vocabularies
   are compared, **Then** key, all three values and all three filenames agree exactly.
6. **Given** a cluster where only one repository's half has been installed, **When** the
   package manager is asked to complete the installation, **Then** it refuses.
7. **Given** an upgraded cluster, **When** a node is adopted or re-adopted, **Then** it
   announces the new vocabulary and is discovered.
8. **Given** an upgrade that already migrated a host's live file, **When** the package is
   reinstalled or upgraded again, **Then** the migration rewrites nothing and says so.

---

### User Story 2 - The upgrade's ordering is decided here, and written down (Priority: P2)

An engineer opening this package's maintainer scripts can tell what runs before what, and
why, without reading another repository's feature numbers.

**Why this priority**: the deferral has already outlived two renumberings and a closed
feature, and it sits in shipped code. It is this repository's constitutional job (Principle
III) and it is cheap to close. It ranks below the cutover because — per the 2026-09-15
measurement — nothing is actually mis-ordered today; what is missing is the decision and its
record.

**Independent Test**: read `debian/postinst` and the feature's ordering record; every ordering
claim is checkable against the file, and no maintainer script defers a decision to a feature
number.

**Acceptance Scenarios**:

1. **Given** the maintainer scripts, **When** they are searched for deferrals, **Then** no
   comment defers a decision to a feature number or to another repository's feature.
2. **Given** the ordering record, **When** each of its claims about what this package restarts
   is checked against the files, **Then** every claim holds.
3. **Given** a package upgrade on a live host, **When** the config conversion and every
   in-package reader of the converted document run, **Then** the conversion ran first, and a
   test asserts that order rather than a comment claiming it.
4. **Given** the live discovery migration added by User Story 1, **When** the ordering record
   is read, **Then** its position relative to the conversion and to the discovery daemon is
   stated with its reason.

---

### User Story 3 - The release gate is mechanical, and has been seen to work (Priority: P3)

Someone installing this ecosystem's packages in the wrong order is refused by the package
manager, and the refusal has been observed rather than asserted.

**Why this priority**: the constraint this repository can add is one line, and the
demonstration is the real deliverable — but neither changes what a correctly-ordered install
does, so it ranks last by risk while remaining a release blocker (D27).

**Independent Test**: build the packages, install a deliberately out-of-order combination in a
disposable environment, capture the refusal.

**Acceptance Scenarios**:

1. **Given** the package metadata, **When** an installation pairs this package with a library
   version it cannot read, **Then** the package manager refuses.
2. **Given** that refusal, **When** the feature is reviewed, **Then** a record of an actually
   observed refusal exists — versions, command, output — not a description of one.
3. **Given** a correctly-ordered install, **When** it runs, **Then** nothing is refused.

---

### Edge Cases

- **A host the package manager never configures.** Where an operator has no privileged `dpkg`,
  packages are deployed by copying files, so `postinst` never runs: the live discovery
  migration does not happen there and the host's package database reports the old version.
  Addressed by documentation — the manual equivalent of every `postinst` step this feature
  adds — not by mechanism (FR-021a).
- **A half-renamed cluster**, in either direction. The package relationship must make it
  unreachable; if it is reached anyway, the log must name the unexpected value and the
  accepted set. Only one direction is this package's to enforce: its `Breaks:` refuses an
  un-renamed discovery daemon, while refusing a renamed daemon beside an un-renamed version of
  this package needs a relationship in the daemon's own package (FR-019).
- **A locally modified privileged-command file.** It is a conffile, so a host that modified it
  keeps the old rules through the upgrade — and those rules name the templates literally.
  Resolved by FR-003a: the working rules arrive in a file that has never been shipped, which
  the package manager installs unconditionally. The kept file's rules become inert, not
  wrong-but-active.
- **A live discovery file that is hand-edited, absent, or belongs to a role the host no longer
  has.**
- **A role flip during or immediately after the upgrade**, before a reboot.
- **An upgrade interrupted between the template rename and the live-file migration.**
- **A downgrade attempt** — unsupported by decision; the only path back is the backup.
- **A node re-adopted after the cutover** whose on-disk template predates it.

---

## Requirements *(mandatory)*

### Functional Requirements — the discovery cutover (US1)

- **FR-001**: The discovery TXT key MUST become `node_role` in every file this repository ships
  or owns, with values `controller`, `node` and `firstrun`, exactly matching the vocabulary
  pinned by the paired repository's contract.
- **FR-002**: Both service types in each template MUST carry the record; the `uuid` record MUST
  be left untouched.
- **FR-003**: The two templates whose filenames carry the retired word MUST be renamed to the
  pinned names, and the rename MUST reach every consumer that names a template literally —
  including the privileged-command rules and the node-configuration tool.
- **FR-003a**: The role-flip privilege MUST work after the upgrade on **every** host, including
  one whose existing privileged-command file was locally modified and is therefore kept by the
  package manager. The rules naming the renamed templates MUST therefore be delivered in a file
  that has not been shipped before, so that delivering them cannot depend on resolving a
  conflict in an existing one.
- **FR-003b**: The previously shipped privileged-command file MUST be retired **whole**, not
  edited. Every rule it still carries — including the discovery-daemon reload rule and the rule
  for the template whose name does not change — moves into the new file (FR-003a), so no rule
  is left behind or duplicated across files. The old file is then retired with this package's
  established conffile-retirement discipline in all three maintainer scripts. A partial edit
  cannot satisfy this requirement: on a host whose copy was locally modified, the package
  manager keeps that copy, so rules removed only from the shipped version would survive there
  indefinitely. Retirement renames a modified copy to a backup name, and the privilege system
  skips include files whose names contain a dot, so no retired rule stays active on any host.
- **FR-003c**: Every privileged-command file this package ships MUST pass the privilege
  system's own syntax check as part of the test suite, so a malformed rule is caught before it
  reaches a host where it affects every privileged command.
- **FR-004**: The package upgrade MUST bring an already-deployed host's **live** discovery file
  to the new vocabulary. A rename confined to the shipped templates does not satisfy this
  requirement, because the live file is not shipped by this package.
- **FR-005**: The live-file migration MUST preserve the host's identity in that file — its
  uuid and the role it announces. It converts vocabulary; it never changes what the host claims
  to be.
- **FR-006**: The live-file migration MUST be idempotent, MUST NOT fail the upgrade, and MUST
  report which of its outcomes occurred.
- **FR-006a**: Before any rewrite, the migration MUST write a timestamped backup that
  reproduces the pre-migration bytes exactly (Constitution II). The backup's name MUST NOT end
  in `.service`, so the discovery daemon never loads it as a second service definition.
  Accumulation MUST be bounded by a stated retention policy — following the network-map
  conversion's precedent of keeping the newest five — and a run that rewrites nothing writes no
  backup.
- **FR-007**: The migration MUST be a **targeted key rewrite**: it rewrites the retired TXT
  records in place — mapping the retired role words to the pinned values — and leaves every
  other byte of the file unchanged, including operator edits, comments, ordering and
  whitespace. It MUST NOT re-serialise the document. A file that does not carry the retired key
  is already current and is left alone.
- **FR-007a**: A file the migration cannot rewrite — unreadable, or carrying the retired key in
  a shape the rewrite does not match — MUST be left untouched and reported to the operator with
  its path and the action to take. Never silently rewritten, never silently skipped.
- **FR-007b**: A file carrying a retired-key value outside the accepted set (`master`, `slave`,
  `firstrun`), or whose records would convert inconsistently — one record mapped, another
  refused — MUST be refused **whole** (Constitution II): left byte-identical, with the offending
  value and the accepted set named in the report. The migration never produces a partially
  converted file.
- **FR-008**: After the upgrade the host MUST be announcing the new vocabulary without a
  reboot; the discovery daemon is made to see the change.
- **FR-009**: This repository's half MUST be reviewed and ready to merge in the same window as
  the paired repository's half, and the two vocabularies MUST be compared file-to-file before
  either merges. Neither merges alone.
- **FR-010**: Documentation describing the discovery records — this repository's README and its
  node-identity contract — MUST carry the new vocabulary when the feature lands.
- **FR-011**: A test MUST fail if any shipped or owned file reintroduces the retired key, so a
  later edit cannot silently undo the cutover — and MUST fail if any shipped template lacks the
  new key in either of its two service types, so a deleted record cannot pass as a clean one.

### Functional Requirements — ordering (US2)

- **FR-012**: The relative order of the config conversion, the live discovery migration, and
  every in-package reader of either, MUST be stated in the maintainer script at the point of
  decision, with the reason — and MUST be verified by a test rather than asserted by a comment.
- **FR-013**: No maintainer script may defer a decision to a feature number. Existing deferrals
  MUST be resolved by deciding, or restated as a condition that can be checked. A **deferral**
  is a statement postponing a decision — "deferred to feature N", "until feature N", "left for
  feature N" and their equivalents. A provenance label naming the feature that introduced a
  block, such as `(feature 007, M3)`, is not a deferral and remains allowed.
- **FR-014**: The ordering record MUST state what this package does and does not restart during
  an upgrade, and MUST be corrected if that behaviour changes.
- **FR-015**: The feature MUST state explicitly whether a cluster may be upgraded host-by-host
  or must be upgraded as a unit, and MUST cover the path by which one host's documents reach
  another outside the package manager.

### Functional Requirements — the gate (US3)

- **FR-016**: This package's metadata MUST express the constraint it actually has against the
  shared library, including refusing a library version that has moved past what this package
  can read. A lower bound alone does not satisfy this requirement. The bound is **locked to the
  library's minor release** — a floor at the version this package's mirrored schema came from,
  and a ceiling that excludes every pre-release and release of the next minor:
  `cuems-utils (>= 0.1.0rc16), cuems-utils (<< 0.1.1~)`.
- **FR-016a**: Each bound's behaviour MUST be verified by version comparison rather than by
  reading, against the versions that actually matter: the floor MUST refuse `0.1.0rc14` (the
  newest published package) and `0.1.0rc15`, and admit `0.1.0rc16` and later `0.1.0rcN`; the
  ceiling MUST admit `0.1.0rcN` and `0.1.0+final`, and exclude `0.1.1~rc1` and `0.1.1`. The
  floor keeps the library's current non-tilde spelling **on purpose**: a tilde floor was
  measured to admit every older `rcN`. A bare `0.1.0` is refused by these bounds, because it
  sorts below every `rcN` — which enforces the library's no-bare-`0.1.0` rule (FR-016b) as a
  side effect.
- **FR-016b**: A minor-release lock only enforces the schema coupling if the library's versioning
  cooperates. The following MUST be recorded as a cross-repository contract and carried to the
  library's own flow as its deliverable (FR-019): (1) the rest of the 0.1.0 line publishes as
  `0.1.0rcN`, never as a bare `0.1.0` — a final, if one is needed, is spelled `0.1.0+final`;
  (2) the tilde spelling starts at `0.1.1~rc1` and is used from then on; (3) any schema change
  bumps the minor; (4) the next minor, 0.1.1, is also the library's announced removal release
  for its deprecated surface, and the two ship together. The bound is documented as **partial
  within the 0.1.0 rc line** — a schema change there passes the ceiling, and is covered only by
  the schema mirror's byte-identity test and D27 — and complete from 0.1.1 onward.
- **FR-017**: The existing constraint against the node-configuration daemon's package MUST be
  preserved and MUST remain true for the versions this feature releases.
- **FR-018**: An out-of-order installation MUST be attempted for real and the refusal captured
  — versions, command, output — and stored with the feature.
- **FR-019**: Where another repository is missing its own constraint — or owes a release rule
  this package's bounds depend on (FR-016b) — this feature MUST record it as that repository's
  deliverable rather than attempting to enforce it from here. This explicitly includes the
  **reverse edge of the discovery cutover**: the discovery daemon's package currently declares
  only a floor against this package that every current version satisfies, so a renamed daemon
  installs beside an un-renamed version of this package. Only a relationship in the daemon's own
  package can refuse that combination.

### Functional Requirements — release discipline

- **FR-020**: Every host-visible change in this feature MUST appear in the package changelog in
  terms of what an operator would observe.
- **FR-021**: The feature MUST produce a written upgrade-verification procedure covering what
  tests cannot: the discovery daemon's live behaviour, the privileged-command rules, the
  conffile prompts, and the package manager's refusal — performed on a controller plus at least
  one node.
- **FR-021a**: The upgrade documentation MUST give the manual equivalent of every
  maintainer-script step this feature adds, for hosts the package manager never configures. The
  live-file migration MUST therefore be runnable by an operator by hand, as an operator-facing
  command, not only from the maintainer script.
- **FR-022**: The upgrade documentation MUST state this package's position on the project
  library (see OOS-1) so an operator knows the upgrade does not touch their show data.
- **FR-023**: The excluded power-off defect (OOS-2) MUST be reported with evidence, and its
  operator-visible symptom stated where operators of a converted controller will encounter it.

### Key Entities

- **Discovery announcement**: what a host publishes about itself on the local network — a key,
  a role value, and the host's uuid, published once per service type. The wire contract between
  this package's files and a daemon in another package.
- **Discovery template**: a shipped file, named by role, that a host's live announcement is
  copied from. Its name is part of its interface: privileged rules and a configuration tool
  both name it literally.
- **Live discovery file**: the host's actual announcement. Not shipped by this package —
  created by copying a template — which is why it needs its own migration.
- **Node map**: the controller's record of every node, keyed by uuid, carrying each node's
  role. Converted by this package during upgrade; read by this package's own tools.
- **Gate edge**: a package relationship that makes an unsupported combination uninstallable.

---

## Out of Scope — decided 2026-09-15

Recorded here rather than dropped, because both were live findings of the 2026-09-15 audit and
both have an owner elsewhere.

### OOS-1 — the batch project-document conversion

**Decision**: it is an **operator command, and its responsibility is `cuems-utils`'** — never
something this package needs to handle. This package does not invoke it from `postinst`, does
not wrap it in a unit, and does not own its procedure, its progress reporting or its backup
retention. A CUEMS upgrade therefore never rewrites an operator's project library.

**Why this is safe**: the shared library converts an old document on read, so a library nobody
ever batch-converts keeps loading. The batch tool is an optimisation over that, and the cost of
skipping it is paid in read time, not in correctness.

**This repository's only remaining obligation** is FR-022: say so in the upgrade documentation,
so an operator is not left wondering what happened to their library.

### OOS-2 — the cluster power-off regression

**Decision**: **report only.** `usr/bin/cuems-cluster-poweroff` selects its targets by the
retired vocabulary, through a parser owned by `cuems-power-bridge` — a package the six-repo
migration never enumerated and which is not checked out beside this repository. The fix belongs
there, and this feature does not attempt it.

**Consequence, stated plainly**: on a converted controller the orderly cluster power-off is
unreliable until that package is fixed — it selects by a vocabulary that this package's own
conversion has already removed from the map. FR-023 makes reporting it, with evidence and with
its operator-visible symptom, a deliverable of this feature.

### Also out of scope

- The paired repository's half of the cutover: its publisher, listener, translation tables and
  fixtures.
- The other consumers' version constraints — they cannot be added from this repository
  (FR-019 records them as theirs).
- The document-distribution path between hosts, owned by the engine. FR-015 requires this
  feature to state its position on it, not to fix it.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After upgrading a controller and at least one node, the cluster's topology is
  intact: the controller lists the node, and the node finds the controller.
- **SC-002**: Zero occurrences of the retired discovery key remain in any file this repository
  ships or owns, and zero remain in an upgraded host's live discovery file. The named
  exceptions are the files that exist to *convert* the retired vocabulary and the documentation
  describing the migration itself.
- **SC-003**: The two repositories' pinned vocabularies match on all seven points — one key,
  three values, three filenames — verified before either merges.
- **SC-004**: An operator can flip a host's role with the documented privileged command after
  the upgrade, with no privilege granted by hand — on a host with a pristine privileged-command
  file and on one whose copy was locally modified alike.
- **SC-005**: Re-running the upgrade on an already-migrated host rewrites no discovery file and
  reports that outcome.
- **SC-006**: A hand-edited live discovery file comes through the upgrade with its retired key
  rewritten and every other byte identical to before; a file the rewrite cannot handle survives
  unchanged with its path in the upgrade's output.
- **SC-007**: No maintainer script in this package defers a decision to a feature number.
- **SC-008**: Every ordering claim in the feature's record is verifiable against the files it
  describes, and at least one is enforced by a test.
- **SC-009**: An out-of-order installation is refused by the package manager, with the refusal
  recorded as observed output.
- **SC-009a**: Every version bound this package declares is verified by direct version
  comparison rather than by inspection of the string: `0.1.0rc14`, `0.1.0rc15`, bare `0.1.0`,
  `0.1.1~rc1` and `0.1.1` refused; `0.1.0rc16`, `0.1.0rc17` and `0.1.0+final` admitted.
- **SC-010**: The test suite passes and covers: the config conversion's four cases (happy path,
  idempotence, whole-document refusal, backup fidelity); the **same four cases for the live-file
  migration**, plus its byte-preservation and unreadable-file cases; the retired key's absence
  and the new key's presence; the syntax check of every shipped privileged-command file; and
  the ordering assertion.
- **SC-011**: The upgrade-verification procedure has been performed on a controller plus at
  least one node, and its record names the versions installed and what was observed.
- **SC-012**: An operator reading the upgrade documentation can state, before upgrading, that
  their project library will not be touched — and what to run if they want it converted.
- **SC-013**: The power-off defect is reported against the package that owns it, with the
  evidence that reproduces it.

---

## Assumptions

- The cluster upgrades as a unit. A staged rollout — some hosts converted, some not — is not
  supported, consistent with the node-model migration's position.
- The node-configuration daemon remains disabled cluster-wide for the lifetime of this feature.
  That is what makes it acceptable for this package's upgrade to migrate a live discovery file
  it does not own (FR-004): nothing else will.
- Downgrade remains unsupported. No reverse conversion exists or is introduced; the only path
  back is the backup a conversion writes.
- The paired repository's contract is the authority for the discovery vocabulary. If it moves,
  this repository follows rather than negotiating a second spelling.
- The shared library follows the versioning contract in FR-016b. Until it publishes a package
  at or above `0.1.0rc16` — the newest published package on 2026-09-17 is `0.1.0rc14` — this
  package's floor is unsatisfiable by any published library package; D27 already sequences the
  library's release first.
- The shared library's on-read conversion works as specified upstream. OOS-1's decision depends
  on it: if it did not work, skipping the batch conversion would not be safe.
- Hosts deployed by file-copy rather than by the package manager exist and will not run
  `postinst`; they are addressed by documentation.
- A controller plus at least one node is available for the manual verification. If it is not,
  the feature is not done — the verification is a deliverable, not a formality.
