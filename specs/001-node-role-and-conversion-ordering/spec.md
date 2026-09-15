<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Feature Specification: Node-role conversion ordering, the packaging gate, and the Avahi vocabulary cutover

**Feature Branch**: `feat/xml-refactor`

**Created**: 2026-09-15

**Status**: Draft — Q1/Q2/Q3 resolved 2026-09-15

**Input**: Feature 010 flow 03 (`cuems-common`), from
`dev/planning/cuems-utils-xml-refactor-consumer-migration.md` §5, with §4's context block as
corrected against the tree on 2026-09-15 (§0.5 of the same document).

**Pairs with**: `../cuems-nodeconf` flow 04
(`specs/001-network-map-object-adoption`). Their merges are simultaneous (D33).

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
2. **Given** a live discovery file the upgrade does not recognise — hand-edited, unusual, or
   absent — **When** the package is upgraded, **Then** the upgrade leaves it alone and reports
   the path and what to do, and the upgrade still succeeds.
3. **Given** an upgraded host, **When** the operator switches its role using the documented
   privileged command, **Then** the command succeeds: the privilege covers the template's
   current name.
4. **Given** the two repositories' halves of the cutover, **When** their pinned vocabularies
   are compared, **Then** key, all three values and all three filenames agree exactly.
5. **Given** a cluster where only one repository's half has been installed, **When** the
   package manager is asked to complete the installation, **Then** it refuses.
6. **Given** an upgraded cluster, **When** a node is adopted or re-adopted, **Then** it
   announces the new vocabulary and is discovered.
7. **Given** an upgrade that already migrated a host's live file, **When** the package is
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
  adds — not by mechanism.
- **A half-renamed cluster**, in either direction. The package relationship must make it
  unreachable; if it is reached anyway, the log must name the unexpected value and the
  accepted set.
- **A locally modified privileged-command file.** It is a conffile, so a host that modified it
  keeps the old rules through the upgrade — and those rules name the templates literally.
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
- **FR-004**: The package upgrade MUST bring an already-deployed host's **live** discovery file
  to the new vocabulary. A rename confined to the shipped templates does not satisfy this
  requirement, because the live file is not shipped by this package.
- **FR-005**: The live-file migration MUST preserve the host's identity in that file — its
  uuid and the role it announces. It converts vocabulary; it never changes what the host claims
  to be.
- **FR-006**: The live-file migration MUST be idempotent, MUST NOT fail the upgrade, and MUST
  report which of its outcomes occurred.
- **FR-007**: The migration MUST rewrite only a file it recognises. Anything else is left
  untouched and reported to the operator with its path and the action to take — never silently
  rewritten and never silently skipped.
- **FR-008**: After the upgrade the host MUST be announcing the new vocabulary without a
  reboot; the discovery daemon is made to see the change.
- **FR-009**: This repository's half MUST be reviewed and ready to merge in the same window as
  the paired repository's half, and the two vocabularies MUST be compared file-to-file before
  either merges. Neither merges alone.
- **FR-010**: Documentation describing the discovery records — this repository's README and its
  node-identity contract — MUST carry the new vocabulary when the feature lands.
- **FR-011**: A test MUST fail if any shipped or owned file reintroduces the retired key, so a
  later edit cannot silently undo the cutover.

### Functional Requirements — ordering (US2)

- **FR-012**: The relative order of the config conversion, the live discovery migration, and
  every in-package reader of either, MUST be stated in the maintainer script at the point of
  decision, with the reason — and MUST be verified by a test rather than asserted by a comment.
- **FR-013**: No maintainer script may defer a decision to a feature number. Existing deferrals
  MUST be resolved by deciding, or restated as a condition that can be checked.
- **FR-014**: The ordering record MUST state what this package does and does not restart during
  an upgrade, and MUST be corrected if that behaviour changes.
- **FR-015**: The feature MUST state explicitly whether a cluster may be upgraded host-by-host
  or must be upgraded as a unit, and MUST cover the path by which one host's documents reach
  another outside the package manager.

### Functional Requirements — the gate (US3)

- **FR-016**: This package's metadata MUST express the constraint it actually has against the
  shared library, including refusing a library version that has moved past what this package
  can read. A lower bound alone does not satisfy this requirement.
- **FR-017**: The existing constraint against the node-configuration daemon's package MUST be
  preserved and MUST remain true for the versions this feature releases.
- **FR-018**: An out-of-order installation MUST be attempted for real and the refusal captured
  — versions, command, output — and stored with the feature.
- **FR-019**: Where another repository is missing its own constraint, this feature MUST record
  it as that repository's deliverable rather than attempting to enforce it from here.

### Functional Requirements — release discipline

- **FR-020**: Every host-visible change in this feature MUST appear in the package changelog in
  terms of what an operator would observe.
- **FR-021**: The feature MUST produce a written upgrade-verification procedure covering what
  tests cannot: the discovery daemon's live behaviour, the privileged-command rules, the
  conffile prompts, and the package manager's refusal — performed on a controller plus at least
  one node.
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
  the upgrade, with no privilege granted by hand.
- **SC-005**: Re-running the upgrade on an already-migrated host rewrites no discovery file and
  reports that outcome.
- **SC-006**: A live discovery file the migration does not recognise survives the upgrade
  unchanged, and its path appears in the upgrade's output.
- **SC-007**: No maintainer script in this package defers a decision to a feature number.
- **SC-008**: Every ordering claim in the feature's record is verifiable against the files it
  describes, and at least one is enforced by a test.
- **SC-009**: An out-of-order installation is refused by the package manager, with the refusal
  recorded as observed output.
- **SC-010**: The test suite passes and covers: the config conversion's four cases (happy path,
  idempotence, whole-document refusal, backup fidelity), the retired key's absence, the
  live-file migration including the unrecognised-file case, and the ordering assertion.
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
  it does not own (Q2): nothing else will.
- Downgrade remains unsupported. No reverse conversion exists or is introduced; the only path
  back is the backup a conversion writes.
- The paired repository's contract is the authority for the discovery vocabulary. If it moves,
  this repository follows rather than negotiating a second spelling.
- The shared library's on-read conversion works as specified upstream. OOS-1's decision depends
  on it: if it did not work, skipping the batch conversion would not be safe.
- Hosts deployed by file-copy rather than by the package manager exist and will not run
  `postinst`; they are addressed by documentation.
- A controller plus at least one node is available for the manual verification. If it is not,
  the feature is not done — the verification is a deliverable, not a formality.
