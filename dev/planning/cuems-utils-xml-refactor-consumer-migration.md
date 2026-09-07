<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# cuems-common's share of the cuems-utils XML/object-model rebuild (feature 010)

**Status**: not started — planning only, copied here for reference
**Source of truth**: `cuems-utils` sibling checkout (`/disk/Projects/StageLab/cuems-utils`),
branch `feat/xml-refactor`, primarily
`specs/planning/xml-rebuild/010-consumer-prompts/03-cuems-common.md`
**Copied**: 2026-09-07, after inspecting the sibling checkout's actual state
**Coordinates with**: `cuems-nodeconf` flow 04 (same rebuild, Avahi rename — see D33 below)

This is a working copy of the cuems-common-specific slice of a six-repository
consumer migration (`cuems-utils`, `cuems-engine`, `cuems-editor`,
`cuems-common`, `cuems-nodeconf`, `cuems-wsclient`), consolidated so this
repository doesn't need a live sibling checkout on hand to pick the work back
up. The full rebuild's shared decision list, per-repo audits, and the other
five repos' prompts remain in `cuems-utils` — this file inlines only the
parts that bind `cuems-common`, plus enough surrounding context to orient
without the round trip. Where a fact might have moved on since it was copied,
that is flagged inline; verify against the sibling checkout before acting.

**Numbering note** (see §7 "C9" below): the sibling repo's own specs were
renumbered on 2026-08-25. Where quoted material below still says "feature
008" or "feature 009" for work now assigned to this migration, that is the
*pre-renumbering* name preserved verbatim from the source document — the
current name is **feature 010** throughout. Do not "fix" the quotes; the
renumbering itself is recorded as finding C9.

---

## 0. State of this repository — updated 2026-09-07, supersedes §0 below where they differ

The sibling prompt's own "measured 2026-09-03" state (§1 below) is preserved
verbatim for its reasoning, but three of its four action items are already
done as of today, ahead of when feature 010 actually starts:

| Item from the 2026-09-03 measurement | Status now |
|---|---|
| `007-node-model-migration` branch, 4 commits, unmerged | Still true — branch **rebased onto `rc_1`** (`d9e0cc3`) 2026-09-07, still local-only, per explicit instruction to keep it local for now |
| `debian/control` `cuems-utils (>= 0.1.0rc15)` | **Bumped to `>= 0.1.0rc16`** 2026-09-07 |
| Mirrored `etc/cuems/network_map.xsd` | **Re-synced** 2026-09-07 — cuems-utils rc16 added an optional `doc_version` attribute (feature 008 ITEM E, FR-048a) to all six schemas; the mirror now carries it and is byte-identical to the sibling's copy again |
| `CLAUDE.md:88`'s "migrated in feature 008" (C9, below) | **Corrected to "feature 010"** 2026-09-07, with an updated pointer |

Everything else in this document — the branch-and-bootstrap steps, the
constitution, the specify/plan/tasks prompts, the settled decisions — is
**still pending**. Nothing below has been executed.

---

## 1. Original "state of this repository, measured 2026-09-03" (verbatim)

| | |
|---|---|
| Current branch | `007-node-model-migration` @ `78b89ad`, clean, **unmerged and unreleased** |
| Base for `feat/xml-refactor` | **`007-node-model-migration`** — *not* `main` |
| Spec-kit | **absent** — added on first run (§2) |
| Constitution | **absent** — written on first run (§3) |
| Existing features | none → this becomes **`001-node-role-and-conversion-ordering`** |
| Tests | `pytest tests/` — no `pyproject.toml`, no `pytest.ini`, no `conftest.py`; **3 test files** |
| `cuems-utils` floor | `debian/control` `>= 0.1.0rc15` + `Breaks: cuems-nodeconf (<< 0.1.0-8)` (now `>= 0.1.0rc16` — §0) |

**Base on `007-node-model-migration`, not `main`.** Four commits live only
there and are this feature's foundation: the schema mirror and shipped-map
conversion (`9fc738e`), the conversion script wired into `postinst` with
three tools updated (`f4a8b3c`), versioned package dependencies (`6a9ec7f`),
and the documentation pass (`78b89ad`). Branching from `main` silently
discards feature 007's entire `cuems-common` phase. (These commits now carry
different hashes after the 2026-09-07 rebase onto `rc_1` — match by message,
not by the hashes above.)

`cuems-utils`'s `CLAUDE.md` claimed until 2026-09-03 that this work was "not
yet updated for the rename". It is done — on a branch, unmerged.

**This repository already holds the only mechanically enforced edge of the
release gate** (`Breaks: cuems-nodeconf (<< 0.1.0-8)`). Four more edges are
missing across the ecosystem (see §7 "C7" below), and the demonstration that
any of them actually works has been deferred twice.

---

## 2. Branch and bootstrap

```bash
cd /disk/Projects/StageLab/cuems-common
git checkout 007-node-model-migration
git checkout -b feat/xml-refactor

specify init --here --integration claude --script sh --force
```

Commit the scaffold as its own GPG-signed commit before `/speckit.constitution`.
**Commits here are GPG-signed** — retry on "gpg failed to sign", never
`--no-gpg-sign`.

Spec-kit's sequential branch numbering will want its own branch. Stay on
`feat/xml-refactor`; let it name
`specs/001-node-role-and-conversion-ordering/` only.

---

## 3. Constitution — write one, this repository has none

```
/speckit.constitution

Establish the constitution for cuems-common, grounded in what this repository actually is.
Read CLAUDE.md first; it is accurate and current.

WHAT THIS REPOSITORY IS: the system-level Debian package delivering all shared
configuration, systemd units, and operator tools for a CUEMS install. It carries NO
compiled code — every executable it ships is a shell or Python script; the compiled daemons
come from their own packages and are only wired into the systemd graph here. It ships:
systemd service/target/path/socket units for both host roles plus drop-ins for third-party
units (Apache2, hostapd, Avahi, rtpmidid); operator tools in usr/bin/; internal service
helpers in usr/lib/cuems/bin/; per-install config and XSD schemas in etc/cuems/;
Avahi/interface templates in usr/share/cuems/; and sysctl, JACK, DHCP/hostapd, ALSA,
rsyslog, logrotate, sudoers, tmpfiles and modules-load drop-ins in etc/. A CUEMS host is
either a controller (one per cluster) or a node (many), and roles are DYNAMIC — any host
can be promoted or demoted without a reinstall, decided only by <node_role> in
/etc/cuems/network_map.xml.

PRINCIPLES THE WORK ALREADY IMPLIES — derive from these, do not invent unrelated ones:
- Its unit of delivery is a PACKAGE UPGRADE ON A LIVE MACHINE, not a merge. Correctness
  means postinst leaves a working host — including a host that was mid-show, whose conffiles
  the operator has locally modified, and whose services are about to be restarted by
  dh_installsystemd. An upgrade that fails halfway is the failure mode to design against.
- It OWNS FILE-FORMAT MIGRATION for the ecosystem's config. It already ships
  cuems-migrate-network-map and runs it from postinst. Any conversion it runs MUST back up
  before it writes, MUST be idempotent (postinst runs again on every reinstall), and MUST
  NOT fail the upgrade.
- It is the ORDERING AUTHORITY. Nothing else in the ecosystem can sequence a conversion
  against a service restart. Ordering decisions belong here and get written down, not
  inherited.
- It enforces the RELEASE GATE mechanically. Versioned dependencies and Breaks are how this
  ecosystem refuses an out-of-order upgrade; prose in a migration guide is not enforcement.
  A gate that has never been demonstrated against a real install is a claim, not a gate.
- DOWNGRADE IS UNSUPPORTED and that is a deliberate position, not an oversight — the only
  path back from a converted node is the timestamped backup the conversion writes. Say so.
- Commits are GPG-signed.

Testing: this repository has three test files and no Python packaging. State a gate it can
actually meet — shell/Python tools and conversion scripts are testable; systemd unit
ordering largely is not, and pretending otherwise produces a rule that gets waived. Be
explicit about which half is covered by tests and which by a documented manual upgrade
check.

Do NOT weaken any rule to accommodate the migration that follows.
```

---

## 4. Context block — paste verbatim into `/speckit.specify` and `/speckit.plan`

```
CONTEXT — read these before writing anything. They live in the SIBLING checkout
/disk/Projects/StageLab/cuems-utils, not in this repository:
  .../cuems-utils/specs/007-node-model-migration/migration-guide.md   §7 = THE RELEASE GATE, §9 = the
                                                                     Avahi files 007 deliberately excluded
  .../cuems-utils/specs/008-rebuild-extension/migration-guide.md      the conversion tool and its FR-042 entry
  .../cuems-utils/specs/planning/xml-rebuild/xml-rebuild-09-consumer-audit.md   C6, C7, C9, C11 are this repo's
  .../cuems-utils/specs/planning/xml-rebuild/xml-rebuild-07-speckit-prompts.md  §2 = the FULL decision list
  AND IN THIS REPOSITORY: docs/node-identity-contract.md, debian/postinst, debian/control

  (§§5-8 below inline the C6/C7/C9/C11 findings and the two migration-guide sections, so the
  sibling checkout is only needed for the full six-repo decision list and other repos' scope.)

SETTLED — the decisions that bind THIS repository. Do not reopen. Anything
outside this subset: read §2 of the prompts file above.
  D20 document compatibility is governed by an EXPLICIT version marker (doc_version), and
      008 built the conversion registry behind it
  D21 an OLD document converts on read; the same logic is also a standalone tool
  D33 the Avahi TXT-record vocabulary (node_type=master|slave|firstrun) is renamed in BOTH
      this repository AND cuems-nodeconf, inside feature 010, as ONE coordinated cutover --
      including the two template FILENAMES and the debian/install entries that place them.
      It cannot be half-renamed: a listener reading node_role against a publisher writing
      node_type discovers nothing, and discovery failure is how a cluster loses its topology.
  D27 nothing in the ecosystem releases until every 010 flow lands. This repository is where
      that gate is mechanically enforced.
  D30/D18b 008's duration promotion invalidates EVERY project document on disk, carried by
      the script 1->2 conversion. 007 converted ONE config file per node; this converts a
      whole library.

MEASURED STARTING STATE — verified against live files 2026-09-03, not transcribed (see §0
above for what has since changed):
  debian/postinst:35-58  the network_map node_type -> node_role conversion, run over BOTH
      /etc/cuems/network_map.xml and its .dpkg-new sibling, `|| true`, never fails the
      upgrade. Its own comment defers the ordering against dh_installsystemd's service
      restart to "feature 008" — a closed, cuems-utils-only feature. That deferral is THIS
      feature's to resolve (007 FR-011d-ii).
  debian/control:12  cuems-utils (>= 0.1.0rc16 as of 2026-09-07)     :38  Breaks: cuems-nodeconf (<< 0.1.0-8)
      ^ the ONLY mechanically enforced edge of the release gate in the whole ecosystem
  etc/cuems/network_map.xml:9   <node_role>controller</node_role>   (already converted)
  etc/cuems/network_map.xsd     the mirrored schema (re-synced 2026-09-07 to carry doc_version)
  etc/avahi/services/cuems.service:6,13          <txt-record>node_type=master</txt-record>
  usr/share/cuems/cuems.service.firstrun:6,13    node_type=firstrun
  usr/share/cuems/cuems.service.master:6,13      node_type=master
  usr/share/cuems/cuems.service.slave:6,13       node_type=slave
      ^ THE RETIRED WORD IS IN THE FILENAME of the last two, so the change reaches
        debian/install and anything resolving a template by name
  CLAUDE.md corrected 2026-09-07: CONTROLLER_NETWORK_FLAG etc. now correctly say
      "migrated in feature 010" (was stale at "feature 008" — see C9 below)
  tests/test_network_map_conversion.py, tests/test_controller_resolution.py,
  tests/test_schema_mirror.py   the three existing tests

ECOSYSTEM PIN STATE (C7), measured 2026-09-03 — this is what "the gate" currently is:
  cuems-engine    pyproject >=0.1.0rc10   debian/control >= 0.1.0rc4   (they disagree)
  cuems-editor    pyproject >=0.1.0rc10   no debian entry
  cuems-nodeconf  pyproject >=0.1.0rc15   debian/control >= 0.1.0rc5
  cuems-wsclient  pyproject >=0.1.0rc5 (optional)   debian/control >= 0.1.0rc5
  cuems-common    debian/control >= 0.1.0rc16 (bumped 2026-09-07) + Breaks: cuems-nodeconf (<< 0.1.0-8)
  Every one of those is a LOWER BOUND. A lower bound cannot express "refuse a library that
  moved past me", which is precisely what the gate says. Re-verify the other four repos'
  numbers before acting — only cuems-common's row was re-measured on 2026-09-07.
```

---

## 5. Specify

```
/speckit.specify <PASTE CONTEXT BLOCK>

Settle the conversion ordering, make the release gate real, and rename this repository's
half of the Avahi discovery vocabulary.

WHAT MUST BE TRUE WHEN DONE:
- The postinst ordering is DECIDED AND WRITTEN DOWN, not inherited. The network-map
  conversion and dh_installsystemd's autogenerated service restarts both run in postinst,
  and their relative order decides whether a service reads the converted map or the old one.
  007 deferred this here because the services doing the reading are the ones feature 010
  migrates — they are migrated now, so the deferral has expired.
- 008's SECOND conversion is placed, and placed differently. cuems-convert-documents
  rewrites every project document in the library, not one config file per node. It has
  different timing characteristics entirely: it runs over user data at scale, it takes real
  time, and it writes a timestamped backup per document. DECIDE whether postinst is the
  right place for it AT ALL — and if it is not, say what is (a first-boot unit, an operator
  command, a one-shot service ordered before the readers) and why. State what an operator
  sees while it works, what happens to a library that is interrupted mid-conversion, and how
  the backups are retained and eventually reclaimed. This is a first-class deliverable, not
  a note.
- The alternative to converting on disk is named and priced. 008 made convert-on-read work
  (an old document loads and converts in memory, the file untouched), so "never run the
  batch tool" is a real option with a real cost: every load re-runs the conversion forever.
  Choose, and record the reasoning — both paths exist and are tested, which is exactly why
  the choice must be explicit.
- The release gate acquires the edges it is missing (C7). Today exactly ONE is mechanical:
  this repository's Breaks against cuems-nodeconf. Every other consumer declares only a
  lower bound. Supply the missing bounds — and RUN 007's twice-deferred mechanical
  demonstration (its T054b, guide §13): install an out-of-order combination and watch dpkg
  actually refuse it. It was deferred because no releasable .deb of any of the three
  repositories existed; feature 010 is the release, so the excuse has expired. A gate that
  has never been demonstrated is a claim.
- This repository's half of the Avahi cutover lands (D33): the node_type TXT record in
  etc/avahi/services/cuems.service (:6, :13) and in
  usr/share/cuems/cuems.service.{firstrun,master,slave} (:6, :13 each), INCLUDING the
  master/slave FILENAMES and the debian/install entries that place them. Coordinate with
  flow 04 (cuems-nodeconf), which owns the publisher, the listener and its own copies of
  these three templates. The two halves MERGE TOGETHER: a half-renamed intermediate state
  is a cluster that cannot discover itself.
- CLAUDE.md:88's "migrated in feature 008" is corrected to 010 (C9) — DONE 2026-09-07, see §0.
- The cluster-upgrade story covers the ENGINE'S DEPLOY PATH, not only dpkg. cuems-engine
  rsyncs each project's script.xml from controller to node (CuemsDeploy.py:329/:649). A
  controller whose library is converted pushes version-2 documents to every node it deploys
  to, and a node on older cuemsutils fails at SHOW-LOAD time — not at upgrade time, and not
  through any channel a package manager mediates (C11).  Whatever ordering this spec picks
  must survive that path, or say explicitly that the cluster upgrades as a unit and this
  path is therefore never mixed-version.

DOWNGRADE remains unsupported (007 T087b): no reverse conversion exists or is planned, and
the only path back for a converted node is the timestamped backup. Do not quietly introduce
one; if this spec changes that position, it does so explicitly.
```

---

## 6. Clarify

```
/speckit.clarify
```

Force the one question everything else hangs on: **does the document conversion
run in `postinst` at all?** Every other ordering decision in this spec is
downstream of it.

---

## 7. Plan

```
/speckit.plan <PASTE CONTEXT BLOCK>

Per-file scope:
- debian/postinst — the ordering decision, and wherever cuems-convert-documents ends up
  if it ends up here.
- debian/control — the missing gate edges; keep the existing Breaks.
- debian/install — the renamed template filenames.
- etc/avahi/services/cuems.service, usr/share/cuems/cuems.service.{firstrun,master,slave}
  — the TXT records and the two filenames.
- CLAUDE.md — the stale feature number (already corrected 2026-09-07, verify still current).
- tests/ — the conversion-ordering and gate tests, alongside the three that exist.
- possibly a new unit or operator tool, if the conversion does not belong in postinst.

Sequencing: pairs with flow 04. Their specs are separate because the repositories are;
their MERGES are simultaneous (D33). Nothing here releases before every other 010 flow
lands (D27) — and this repository is where that is enforced rather than described.

Constitution check, against the constitution written in §3:
- The live-upgrade principle governs the whole conversion-ordering question.
- The ordering-authority principle is why the deferral stops here rather than moving again.
- The mechanical-gate principle is what makes the dpkg demonstration a deliverable rather
  than a nice-to-have.
- Testing: state which half is covered by tests and which by a documented manual upgrade
  check, per the constitution — and make the manual half a written procedure, not a memory.
```

---

## 8. Tasks, checklist, analyze, implement

```
/speckit.tasks
```
```
/speckit.checklist Upgrade readiness: the postinst-vs-service-restart ordering DECIDED and
written, not inherited; the document conversion's placement decided with the mid-conversion,
backup-retention and operator-visibility questions answered; the convert-on-read alternative
priced rather than ignored; the release gate's missing edges present AND demonstrated
against a real out-of-order dpkg install, not asserted; the Avahi TXT records, both template
FILENAMES and the debian/install entries renamed, verified against flow 04's half so no
half-renamed state ships; the CuemsDeploy version exposure covered by the chosen ordering or
explicitly excluded by a cluster-upgrades-as-a-unit statement; CLAUDE.md:88 corrected; and a
controller-plus-node cluster upgrade performed, not just a single-node one.
```
```
/speckit.analyze
```
```
/speckit.implement
```

---

## 9. Exit criteria

`pytest tests/` green; the postinst ordering decided and written down; the
document conversion's placement decided with mid-conversion, backup and operator
visibility answered; the release gate's missing edges present **and** demonstrated
against a real out-of-order install; this repository's half of the Avahi rename
complete including both filenames and `debian/install`, merged simultaneously with
flow 04; `CLAUDE.md:88` corrected (done, see §0); and a controller-plus-node cluster
upgrade that comes back with its topology intact.

**This repository is where D27 is enforced.** Nothing in the ecosystem releases
until every 010 flow lands, and after this feature that sentence is a package
relationship rather than a paragraph.

---

## 10. Background — extracted findings from the shared cuems-utils audit

These are excerpts from `specs/planning/xml-rebuild/xml-rebuild-09-consumer-audit.md`
in the sibling checkout (a document shared across all six repos' migration
prompts), limited to the items the audit itself flags as this repository's.

### C6 — the Avahi TXT-record vocabulary has two owners, and §8 assigns one

> §8 hands 010 `cuems-common`'s four files. But the retired vocabulary lives in
> **both** repositories, and the TXT key is the wire between two daemons:
>
> **`cuems-common`** (27 `node_type` occurrences total):
> `etc/avahi/services/cuems.service:6,13`,
> `usr/share/cuems/cuems.service.{firstrun,master,slave}:6,13` — the last two
> carry the retired word in the **filename**, so `debian/install` and anything
> resolving a template by name moves too.
>
> **`cuems-nodeconf`** (30 occurrences — *more* than common):
> its own copies at repo root, `cuems.service.{firstrun,master,slave}:12,19`;
> the producer `CuemsSettings.py:27`
> (`settings_dict['properties'] = {'node_type': 'slave'}`); the consumer
> `CuemsAvahiListener.py:96-155` (two blocks, `add_service` and
> `update_service`, both keying on `b'node_type'` through
> `_AVAHI_NODE_TYPE_TO_ROLE`); and the installer
> `CuemsNodeConf._install_master_service_template` + the inline slave-template
> copy in `set_node_role`.
>
> `AvahiTool.py:12` and `CuemsAvahiListener.py:19-24` both carry comments
> deferring this "to feature 008" — the pre-renumbering name. 008 was
> cuems-utils-only, so the work is currently assigned to a feature that has
> closed.
>
> **Decision (D33, 2026-09-03):** both halves land **inside 010**, as one
> coordinated cutover. The TXT key cannot be half-renamed: a listener reading
> `node_role` against a publisher writing `node_type` discovers nothing, and
> discovery failure is how a cluster loses its topology. This is the largest
> single sub-scope 010 acquires from this audit; the plan sequences it as one
> unit (publisher, template files, filenames, `debian/install`, listener,
> `_AVAHI_NODE_TYPE_TO_ROLE`'s removal) rather than per-repo.

### C7 — the release gate has exactly one mechanically enforced edge

> Measured 2026-09-03:
>
> | Repo | `pyproject.toml` | `debian/control` |
> |---|---|---|
> | `cuems-engine` | `cuemsutils = ">=0.1.0rc10"` | `cuems-utils (>= 0.1.0rc4)` |
> | `cuems-editor` | `cuemsutils>=0.1.0rc10` | — |
> | `cuems-nodeconf` | `cuemsutils = ">=0.1.0rc15"` | `cuems-utils (>= 0.1.0rc5)` |
> | `cuems-wsclient` | `cuemsutils = ">=0.1.0rc5"` (optional) | `cuems-utils (>= 0.1.0rc5)` |
> | `cuems-common` | — | `cuems-utils (>= 0.1.0rc15)`, `Breaks: cuems-nodeconf (<< 0.1.0-8)` |
>
> Only `cuems-common` enforces anything, and only against `cuems-nodeconf`
> (007's FR-030d / T054a). Three observations:
>
> 1. **A `>=` floor cannot express the gate.** The gate says "an unmigrated
>    consumer must refuse a library that has moved past it" — that is an upper
>    bound or a `Breaks`, and no consumer declares one. Installing
>    `cuems-utils` rc16 beside an editor pinned `>=0.1.0rc10` succeeds, and the
>    editor then fails at import (C2).
> 2. **`cuems-engine`'s two floors disagree** — `rc4` in `debian/control`
>    against `rc10` in `pyproject.toml`. The packaged floor is six release
>    candidates behind the source one.
> 3. **007 moved the mechanical demonstration here** (T054b, its guide §13):
>    no packaging sandbox existed to install an out-of-order combination and
>    watch `dpkg` refuse it. 008 then added a second, larger breaking change to
>    the same gate without adding an edge. 010 both *runs* that demonstration
>    and *supplies the missing edges*.

*(cuems-common's own row is now `>= 0.1.0rc16` as of 2026-09-07 — still only a
lower bound, same limitation. The other four repos' numbers were not
re-measured; re-check before relying on them.)*

### C9 — three stale documents that are 010's own inputs

> 1. **`cuems-utils/CLAUDE.md`** states the cuems-common node-identity field
>    contract is *"not yet updated for the rename"*. **False as of 2026-08-24**:
>    `cuems-common`'s local `007-node-model-migration` branch carries four
>    commits — schema mirror + shipped-map conversion (`9fc738e`), the conversion
>    script wired into `postinst` with three tools updated (`f4a8b3c`), versioned
>    package dependencies (`6a9ec7f`), and the documentation pass (`78b89ad`).
>    `etc/cuems/network_map.xml:9` already reads `<node_role>controller</node_role>`;
>    `debian/postinst:35-58` runs `cuems-migrate-network-map` over both the live
>    file and its `.dpkg-new` sibling; `tests/test_network_map_conversion.py`
>    covers it. Unmerged and unreleased — but "landed on a branch", not
>    "not started".
> 2. **`cuems-common/CLAUDE.md:88`** says `CONTROLLER_NETWORK_FLAG` and the enum
>    constants are *"migrated in feature 008"*. The 2026-08-25 renumbering makes
>    that **010**. — **Corrected in this repository 2026-09-07.**
> 3. **`cuems-nodeconf/cuemsnodeconf/AvahiTool.py:12`** and
>    **`CuemsAvahiListener.py:19-24`** defer the TXT-record change *"to feature
>    008"* — see C6; now 010's, by D33.
>
> All three are read by whoever executes 010. Correcting them is part of the
> feature, not housekeeping after it.

### C11 — a third document-distribution surface for the conversion

> §8 plans 008's duration conversion as two paths: `postinst` (batch, via
> `cuems-convert-documents`) and convert-on-load. There is a third, and it is
> node-to-node rather than package-to-disk: **`cuems-engine` deploys project
> files across the cluster.** `tools/CuemsDeploy.py:329` and `:649` build
> `/projects/<project>/script.xml` into the rsync manifest;
> `NodeEngine.py:730,805` receive them.
>
> So a controller whose library has been converted to `script` version 2 pushes
> version-2 documents to every node it deploys to. A node running an older
> `cuemsutils` cannot read them — and unlike the postinst case, this happens at
> **show-load time**, not upgrade time. The reverse order (nodes upgraded first)
> is safe, because ITEM E converts version-1 documents in memory.
>
> This is a third ordering constraint alongside 007's postinst-vs-service-restart
> question, and it argues the same way the cluster-upgrades-as-a-unit rule does
> (007's guide §7): the deploy path gives a mixed-version cluster a way to fail
> that no package manager mediates.

---

## 11. Background — the release gate's history, from the 007/008 migration guides

Excerpted from `specs/007-node-model-migration/migration-guide.md` (§7, §9,
§13) and `specs/008-rebuild-extension/migration-guide.md` (FR-042) in the
sibling checkout. **These guides predate the 2026-08-25 renumbering** — every
"feature 009" mention below is what C9 (above) says is now feature 010.

### 007 guide §7 — the release gate (T087, T087a, T087b)

> **Stated as a gate, per M5** (`contracts/schema-migration.md`):
>
> 1. `cuems-utils` — schema, model, engine, write path. **Landed.**
> 2. `cuems-nodeconf` — model and serializers deleted; the sole writer follows
>    the schema. **Landed on a local `007-node-model-migration` branch**
>    (Phase 7 / US5) — not pushed, not merged, not released.
> 3. `cuems-common` — mirror, conversion, tools, documentation. **Landed on a
>    local `007-node-model-migration` branch** (Phase 5 / US3) — not pushed,
>    not merged, not released.
> 4. **Feature 009** [→ 010] — `cuems-engine` and `cuems-editor` readers.
>    **Not started.**
>
> **No release of any of the three repositories ships before step 4.** The
> hard cutover has no working partially-deployed state: a converted map meets
> an unmigrated reader (silent, not loud), or an unconverted map meets the
> migrated schema (`SchemaError`) — either way a node stops functioning, not
> gracefully.
>
> **The cluster, not just one machine** (T087a): a staged rollout — some nodes
> converted, some not, or a controller upgraded ahead of its nodes — is **not
> supported**. `network_map.xml` is the controller's view of every node; a
> controller running the migrated schema and reading an unconverted map fails
> closed rather than partially. The cluster upgrades as a unit, once
> `cuems-common`'s branch ships the conversion in `postinst` via an actual
> release.
>
> **Enforcement status, honestly**: FR-030d's versioned package dependencies
> (T054a) are present in `cuems-common`'s `debian/control` on its local branch
> (`Breaks: cuems-nodeconf (<< 0.1.0-8)`, alongside `cuems-utils (>=
> 0.1.0rc15)` [now `rc16`]). **Mechanical demonstration is moved to feature
> 009** [→ 010] (T054b, §13): no packaging/build sandbox was available to
> actually install an out-of-order combination and watch `dpkg` refuse it —
> and no releasable `.deb` of any of the three repositories exists until then
> anyway.
>
> **Downgrade is unsupported** (T087b): no reverse conversion (`node_role` →
> `node_type`) is provided or planned — `NodeRoleType`'s enumeration is a
> narrower vocabulary than free text was, and a value written as `controller`
> has no principled string to revert to. The only path back for a converted
> node is restoring the timestamped backup the conversion script writes
> before any change (FR-011i) — which is why that backup is not optional and
> is asserted to reproduce the pre-conversion bytes exactly (SC-011).

### 007 guide §9 — Avahi discovery files excluded from SC-004a (T060, T060a)

> Named here as the explicit exclusion set SC-004a's occurrence count is
> measured against — never a pattern, always these four files:
>
> | File | Carries |
> |---|---|
> | `etc/avahi/services/cuems.service` | `node_type` TXT record |
> | `usr/share/cuems/cuems.service.master` | TXT record **and** the retired word in its filename |
> | `usr/share/cuems/cuems.service.slave` | TXT record **and** the retired word in its filename |
> | `usr/share/cuems/cuems.service.firstrun` | TXT record |
>
> Deferred to feature 009 [→ 010] (a discovery surface, not the XML document).
> Renaming `cuems.service.master`/`cuems.service.slave` reaches
> `debian/install` and anything resolving a template by name, which is why it
> is not done incidentally here.

### 007 guide §13 — the out-of-order-upgrade enforcement demonstration (T054b)

> **Moved to feature 009 [→ 010], not completed here — recorded as a
> deliberate move, not silently dropped.** T054a's versioned package
> constraint is written and reviewed by inspection. T054b asks for more: an
> actual `dpkg -i` of an out-of-order combination, showing the refusal
> happen. That requires a Debian packaging/build sandbox (a `.deb` built from
> each of the three repositories, installed in sequence) that was not
> available — and all three repositories only exist as unreleased local
> branches until feature 009 [→ 010] lands, so there is no built `.deb` of any
> of them yet to install in the wrong order. SC-012 is therefore satisfied by
> feature 007's scope (the constraint exists and is reviewed) but its
> *demonstration* is 010's to run, alongside the release it is gating.

### 008 guide — FR-041/FR-041a and FR-042/SC-019 — the conversion tool

> This closes the obligation "any production `script.xml` written before this
> feature will fail to load". As of ITEM E, it no longer fails:
> `CuemsScript.load` detects a `doc_version` of 1 (or absent), applies the
> registered `script` 1→2 conversion in memory, and returns a loaded, valid
> object — the file on disk is **not** rewritten by the load path (FR-041a).
> **009 [→ 010] still has a sequencing decision**: whether to run the
> standalone `cuems-convert-documents` tool as part of the `.deb`
> post-install step (rewriting every on-disk document once, with a backup per
> FR-042) or to rely on convert-on-every-load indefinitely. The former pays a
> one-time backup+rewrite cost per document and then every subsequent load is
> the cheap, already-current path; the latter re-runs the conversion on every
> single load forever. Not decided — a 010 choice, now that both paths exist
> and are tested.
>
> **FR-042/SC-019**: new entry point (`pyproject.toml`'s `[project.scripts]`),
> implemented in `cuemsutils.xml.convert_documents`. Takes one or more file
> paths, converts each whose version precedes its schema's current one, and
> writes a timestamped `.bak` copy before rewriting. 009's [→ 010's] packaging
> work should decide where in the `.deb`'s postinst this runs (candidate:
> immediately after the package's own files are in place, before any CUEMS
> service that reads these documents is (re)started) and over which
> directories (`/etc/cuems/*.xml`, every project's
> `script.xml`/`mappings.xml`/`settings.xml` under the library path).

---

## 12. Where to look for more

The full six-repo decision list (D1-D35), the other five repos' consumer
prompts, and the rest of the audit (C1-C5, C8, C10, C12) live only in the
`cuems-utils` sibling checkout under `specs/planning/xml-rebuild/`. This
document does not attempt to duplicate the parts that don't bind
`cuems-common` — re-read the sibling checkout directly if the scope above
turns out to be incomplete, since it may have moved since 2026-09-07.
