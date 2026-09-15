<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# cuems-common's share of the cuems-utils XML/object-model rebuild (feature 010)

**Status**: not started — planning only, copied here for reference
**Source of truth**: the `cuems-utils` sibling checkout (`../cuems-utils`),
branch `feat/xml-refactor`, primarily
`specs/planning/xml-rebuild/010-consumer-prompts/03-cuems-common.md`

**Path convention**: every path in this document is relative to **this
repository's root**, so `../cuems-utils` is the sibling checkout beside it. No
absolute path appears anywhere here on purpose — the layout is a convention, not
a machine: `tests/test_schema_mirror.py` already resolves the canonical schema
the same way (`REPO_ROOT.parent / "cuems-utils" / ...`). If your checkouts are
not siblings, that test skips and the paths below are the only thing to adjust.
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

## 0. Verified state — audited 2026-09-15 against the working tree

Supersedes both the 2026-09-07 note and §1's 2026-09-03 measurement wherever
they differ. Every row was checked against files in this checkout and the
sibling checkouts, not transcribed. §0.5 corrects claims this document itself
makes about the repository — read it before planning the Avahi cutover.

### 0.1 Branch and bootstrap (§2)

| Step | Status |
|---|---|
| `feat/xml-refactor` branch | **DONE, and pushed** — `origin/feat/xml-refactor` @ `9483bb9`; the 2026-09-07 "still local-only" note is stale. `007-node-model-migration` no longer exists as a branch: its four commits are here, rebased onto `rc_1` (`d9e0cc3`) and matched by message — `9eb094d` (T051/T052), `df4eb2b` (T053-T057), `d92317d` (T054a), `cc6207f` (T054c/T058/T059) — plus `c7500a6` (rc16 pin + mirror resync) and `9483bb9` (this document). Working tree clean. |
| `specify init` scaffold | **NOT DONE** — no `.specify/`, no `specs/` anywhere in the tree. |
| Constitution (§3) | **NOT DONE** — none written. |
| Sibling checkouts | The absolute paths this document was copied with have been replaced by `../<repo>` throughout (see the path convention in the header). Present beside this checkout: `../cuems-utils` (branch `feat/xml-refactor`, `d0340fc` = the rc16 bump), `../cuems-nodeconf` (branch `feat/xml-refactor`), `../cuems-engine`. **`../cuems-editor` and `../cuems-wsclient` are absent**, so C7's rows for those two could not be re-verified. |
| `debian/changelog` | No entry for this feature yet; top is `1.3.0-22`. |

### 0.2 The three 2026-09-07 items — all confirmed still true

- `debian/control:12` `cuems-utils (>= 0.1.0rc16)` ✅
- `etc/cuems/network_map.xsd` **byte-identical** to `../cuems-utils/src/cuemsutils/xml/schemas/network_map.xsd` (diffed 2026-09-15) and carries the optional `doc_version` attribute at `:12` ✅
- the feature-number correction ✅ — but it now sits at **`CLAUDE.md:94`**, not `:88`. Every "CLAUDE.md:88" below is a stale *anchor*, not an unmet requirement.

### 0.3 The §5 deliverables, one by one

| § 5 bullet | Status | Evidence |
|---|---|---|
| postinst ordering DECIDED AND WRITTEN DOWN | **NOT MET** | `debian/postinst:109-133` still defers it in its own comment (`:113-117`) to "feature 008" — the same C9 staleness this feature exists to clear, in shipped code rather than in docs. See §0.5-A: the question as posed is malformed, and the real answer is nearly free. |
| 008's second conversion (`cuems-convert-documents`) placed | **NOT STARTED** | Nothing in `debian/` mentions it. The upstream half is ready: `../cuems-utils/pyproject.toml:48` declares the `cuems-convert-documents` entry point and `src/cuemsutils/xml/convert_documents.py` exists. |
| convert-on-read alternative named and priced | **NOT STARTED** | No document in this repository weighs it. |
| release gate acquires its missing edges, and is demonstrated | **NOT MET** | Re-measured 2026-09-15: `cuems-engine` `pyproject.toml:41 >=0.1.0rc10` vs `debian/control:18 >= 0.1.0rc4` — **still disagreeing**; `cuems-nodeconf` `pyproject.toml:28 >=0.1.0rc15` vs `debian/control:18 >= 0.1.0rc5`; `cuems-common` `rc16` + the single `Breaks: cuems-nodeconf (<< 0.1.0-8)`. `cuems-editor`/`cuems-wsclient` unverifiable here. Still no upper bound anywhere, and no dpkg demonstration has been run. |
| this repository's half of the Avahi cutover (D33) | **NOT STARTED — and the counterpart is blocked on it** | All four files still carry `node_type` (`etc/avahi/services/cuems.service:6,13`; `usr/share/cuems/cuems.service.{firstrun,master,slave}:6,13`), both filenames unchanged. The counterpart is **fully specified**: `../cuems-nodeconf/specs/001-network-map-object-adoption/` (spec, plan, tasks, `contracts/avahi-txt.md`) pins the vocabulary — key **`node_role`**, values **`controller`/`node`/`firstrun`**, filenames **`cuems.service.{firstrun,controller,node}`** — and its T041/T042 are a blocking merge gate that reads *this* repository for a reviewed counterpart branch. Its task boxes are all unchecked: neither side has implemented anything. |
| `CLAUDE.md` feature number corrected | **MET** | §0.2. |
| `CuemsDeploy` exposure covered or excluded by a cluster-upgrades-as-a-unit statement | **NOT ADDRESSED** | Nothing here says it. |
| DOWNGRADE remains unsupported | **HELD** | No reverse conversion exists or is referenced; `usr/bin/cuems-migrate-network-map` backs up before writing and prunes old backups. |

### 0.4 Exit criteria (§9)

`pytest tests/` is **green — 23 passed** across the three test files. Note for
whoever runs it: the default interpreter here (pyenv 3.11.9) has no pytest;
what works is
`uv run --with pytest --with lxml python -m pytest tests/ -q`.
Every other exit criterion is unmet per §0.3.

### 0.5 Corrections to this document's own claims — measured 2026-09-15

**A. The postinst ordering question is malformed as written.** §5 asserts that
"the network-map conversion and dh_installsystemd's autogenerated service
restarts both run in postinst". They do not: **this package's `debian/postinst`
carries no `#DEBHELPER#` token** — only `debian/preinst:117` has one — so
dh_installsystemd injects nothing into it. The package already depends on that
fact elsewhere (`debian/changelog:38-41`: it is why `cuems-gpu-pin.service` is
enabled by hand rather than via `WantedBy=`). What the postinst actually touches
is `systemd-journald`, `rsyslog`, `apache2`, `hostapd` (`reenable`), `ssh`,
`rsync`, and `systemctl enable` — never `start` — for the CUEMS units. **No
map-reading CUEMS service is restarted by this postinst at all**, and the only
in-postinst reader, `cuems-write-chrony-source` near the end, is already
preceded by the conversion at `:109`. The deliverable is therefore to *write the
decision down* — including that the readers restart at reboot or by operator
action, never here — not to re-sequence anything.

**B. `debian/install` has no entries for the templates.** D33, §5 and §7 all
require renaming "the `debian/install` entries that place them". There are none:
`usr/share/cuems/` ships through a single glob at `debian/install:224`. Renaming
the templates needs no `debian/install` change.

**C. `etc/avahi/services/cuems.service` is not shipped by the package at all.**
No `debian/install` entry, nothing in `debian/rules`, nothing in the postinst
places it; the in-repo file is a checked-in copy of what a host ends up with.
The live file is created by copying a template — through the sudoers rules in D
below, or by nodeconf. The consequence the cutover plan does not cover:
**renaming both repositories' halves changes nothing about an already-deployed
host's active announcement.** Every running host keeps publishing `node_type=…`
until something re-copies a template, and nodeconf — which would — is disabled
cluster-wide. A correctly-simultaneous D33 merge therefore still leaves a
cluster that cannot discover itself. This feature needs an explicit step that
rewrites or replaces the live `/etc/avahi/services/cuems.service` (a postinst
migration, or an operator command with a written procedure).

**D. Two by-name resolvers C6 never listed**, both here:
- `etc/sudoers.d/99-cuems:3-5` — three `NOPASSWD` rules naming the exact
  template paths. sudoers matches a command literally, so renaming the files
  revokes the privilege silently. It is also a **conffile**, so a host with a
  locally modified sudoers keeps the old rules — the package's standing
  obsolete-conffile footgun applies.
- `usr/bin/cuems-config-node:64` —
  `service_files = ['cuems.service.firstrun', 'cuems.service.master', 'cuems.service.slave']`,
  hardcoded; the tool rewrites the `uuid=` TXT record in each.

**E. A `node_type` reader outside the six-repo scope.**
`usr/bin/cuems-cluster-poweroff:275` filters `n.node_type != "NodeType.slave"`,
through `cuemspowerbridge.network_map` (imported at `:209`) — i.e. the
**cuems-power-bridge** package, which this migration does not enumerate and
which is not checked out here. The 007 conversion already shipping on this
branch retires that vocabulary from every live `network_map.xml`, so either that
parser still reads `<node_type>` (the tool finds zero nodes and powers off
nothing, silently) or it exposes `node_role` (`AttributeError`). It was not
among the "three tools updated" by `df4eb2b` — those were
`cuems-write-chrony-source`, `cuems-log-collector-url` and `cuems-logs`. Verify
against a cuems-power-bridge checkout before the release.

**F. Occurrence counts are stale.** C6's "27 `node_type` occurrences" predates
this branch. Measured today: **45 across 15 tracked files** (59 counting this
document). `README.md` carries 6 (`:227,231,232,264,306,307`) and
`docs/node-identity-contract.md` 5 — documentation the rename has to follow,
which neither C6 nor §7's per-file scope lists.

### 0.6 The audit split by scope

The same findings as §0.3-§0.5, sorted by what they are *about*, because the
three groups have different owners and different merge windows. **A** is the
`node_type` → `node_role` vocabulary and the node-identity model; **B** is
everything else feature 010 asks of this repository (mostly 008's document
conversion and the packaging gate); **C** belongs to a sibling repository and is
listed only so it is tracked, not fixed here.

#### A — NodeType-related

| | Item | Status |
|---|---|---|
| A1 | Shipped default map converted; `usr/bin/cuems-migrate-network-map` shipped and wired at `debian/postinst:109-133`; the three controller-resolving tools read `node_role` | **MET** (007, on this branch) |
| A2 | `etc/cuems/network_map.xsd` mirrors the `node_role` enumeration byte-for-byte | **MET** |
| A3 | `CLAUDE.md:94` assigns the role constants to feature 010 (C9 item 2) | **MET** |
| A4 | `debian/control` `Breaks: cuems-nodeconf (<< 0.1.0-8)` — refuses a nodeconf still writing `<node_type>` | **MET** (the ecosystem's only mechanical edge) |
| A5 | Downgrade unsupported; the timestamped backup is the only way back | **HELD** |
| A6 | 23 tests covering the conversion, the mirror and controller resolution | **MET** |
| A7 | The Avahi TXT rename (D33): `etc/avahi/services/cuems.service:6,13` and `usr/share/cuems/cuems.service.{firstrun,master,slave}:6,13`, **plus the two filenames** | **NOT STARTED** |
| A8 | The rename must also reach the **live** `/etc/avahi/services/cuems.service`, which this package does not ship — see §0.5-C. Without it a correctly-simultaneous cutover still leaves every deployed host announcing `node_type=` | **NOT PLANNED ANYWHERE** |
| A9 | The by-name resolvers: `etc/sudoers.d/99-cuems:3-5` (a conffile; sudoers matches the command literally) and `usr/bin/cuems-config-node:64` — §0.5-D | **NOT LISTED IN ANY PLAN** |
| A10 | Documentation follow-through: `README.md` ×6 (`:227,231,232,264,306,307`), `docs/node-identity-contract.md` ×5 — §0.5-F | **NOT STARTED** |
| A11 | `debian/postinst:113-117` still defers the conversion-vs-restart ordering to "feature 008" — a stale number *and* an undecided question | **NOT MET** — and cheap to close, see §0.5-A |
| A12 | `usr/bin/cuems-cluster-poweroff:275` still filters on `n.node_type != "NodeType.slave"` — the call site is ours, the parser is not (→ C6) | **BROKEN OR ABOUT TO BE** |
| A13 | "the `debian/install` entries that place them" — there are none (§0.5-B) | **NO WORK REQUIRED** |

#### B — NodeType-unrelated, still this repository's

| | Item | Status |
|---|---|---|
| B1 | Where `cuems-convert-documents` runs — postinst, a first-boot unit, or an operator command — and over which directories | **NOT STARTED**; the tool is ready at `../cuems-utils/pyproject.toml:48` |
| B2 | The convert-on-read alternative named and priced against B1 | **NOT STARTED** |
| B3 | What an operator sees during B1, what an interrupted library looks like, how the per-document backups are retained and reclaimed | **NOT STARTED** (part of B1's deliverable, not a footnote) |
| B4 | The gate edge this repository can actually add: an **upper bound or `Breaks:` against `cuems-utils`** in our own `debian/control`. Today we declare only `>= 0.1.0rc16` | **NOT DONE** |
| B5 | 007's twice-deferred T054b demonstration: build the `.deb`s, install an out-of-order combination, watch dpkg refuse | **NOT RUN** |
| B6 | `doc_version` (008's marker, not a NodeType concern) present in the mirrored schema at `:12` | **MET** |
| B7 | Spec-kit scaffold (§2) and constitution (§3) | **NOT DONE** — see §0.7 |
| B8 | A `debian/changelog` entry for this feature | **NOT DONE** (top is `1.3.0-22`) |
| B9 | The `#DEBHELPER#` finding (§0.5-A) governs the ordering of **both** conversions, not only the node-map one | **MEASURED** |
| B10 | The testing gate the constitution has to state: the default interpreter has no pytest; `uv run --with pytest --with lxml python -m pytest tests/ -q` is what runs here | **RECORD IT** |

#### C — Out of scope for this repository

| | Item | Owner |
|---|---|---|
| C1 | The other half of D33: publisher `CuemsSettings.py:27`, listener `CuemsAvahiListener.py:96-155`, **both** `_AVAHI_NODE_TYPE_TO_ROLE` copies, `AvahiTool.py`, test fixtures, the three unshipped root duplicates | `../cuems-nodeconf` flow 04 — fully specified, nothing implemented |
| C2 | The stale "deferred to feature 008" comments at `AvahiTool.py:12` and `CuemsAvahiListener.py:19-24` (C9 item 3) | `../cuems-nodeconf` |
| C3 | `../cuems-utils/CLAUDE.md`'s claim that this repository's node-identity work is "not yet updated for the rename" (C9 item 1) | `../cuems-utils`, its T063 |
| C4 | The other consumers' pins — `cuems-engine`'s `rc10` (pyproject) vs `rc4` (debian/control) disagreement, `cuems-editor`, `cuems-wsclient`. **This repository cannot add a bound to another package's `debian/control`**; §5's "supply the missing bounds" is only B4's worth of ours | each consumer repo |
| C5 | The deploy-path exposure (C11): `CuemsDeploy.py:329/:649`, `NodeEngine.py:730,805`. Ours is only to state the cluster-upgrades-as-a-unit position | `../cuems-engine` |
| C6 | `cuemspowerbridge.network_map`'s parser, behind A12 — a repository the six-repo migration never enumerated and which is not checked out beside this one | `cuems-power-bridge` |
| C7 | `cuems-convert-documents` itself — ours is only *whether and where* to run it (B1) | `../cuems-utils` |
| C8 | `../cuems-editor` and `../cuems-wsclient` are not checked out beside this repository, so their C7 rows stay unverified | whoever runs those flows |

### 0.7 Spec-kit: not instantiated here, and whether it should be

**Measured state — DONE 2026-09-15** (`41b085b`). The scaffold is installed:
`specify init --here --force --non-interactive --integration claude --script sh`
(CLI 1.0.4) added `.specify/` (bash scripts, templates, workflows, the unfilled
`memory/constitution.md`) and ten `.claude/skills/speckit-*` — 30 files, ~380 KB,
the same footprint `../cuems-nodeconf` and `../cuems-utils` carry. It touched no
tracked file, and `debian/install` names every shipped path explicitly, so none
of it reaches a `.deb`. `specs/` is still empty: no feature has been created.

⚠️ **The command names in §§3-8 below are stale.** CLI 1.0.4 installs the chain
as **skills with hyphens** — `/speckit-constitution`, `/speckit-specify`,
`/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-checklist`,
`/speckit-analyze`, `/speckit-implement` — not the dotted `/speckit.constitution`
spelling those prompts were written against. The prompt *bodies* are unaffected;
only the invocation changed. There is also a `/speckit-converge` (assess the tree
and append the remainder as tasks) and a `/speckit-taskstoissues` that the
prompts predate.

**The upstream process expects it.**
`../cuems-utils/specs/planning/xml-rebuild/010-consumer-prompts/README.md` is
explicit: feature 010 is **seven independent spec-kit flows, one release**, and
it notes that five of the seven repositories had no spec-kit installed — the
bootstrap step exists precisely for that. Our paired flow has already run the
chain: `../cuems-nodeconf/specs/001-network-map-object-adoption/` is ~1400 lines
across spec, plan, research, data-model, tasks, quickstart, two contracts and a
checklist.

**Verdict — instantiate, but trimmed.** Three things earn it:

1. **The pairing needs something to check against.** Flow 04's T041 and T042 are
   a blocking merge gate that reads *this* repository for a reviewed counterpart
   before either side merges. Right now there is nothing here to read but code
   that has not been written. A local `contracts/avahi-txt.md` mirroring
   nodeconf's — key, three values, three filenames — makes "the two halves
   agree" a file comparison instead of a conversation.
2. **The open items are decisions, not code.** B1/B2/B3 and A8 are exactly what
   `specify` + `clarify` produce, and §6 already names the one question
   everything hangs on. A11's whole failure mode is a decision that was never
   written down and then rotted in a code comment through two renumberings.
3. **The constitution is a real deliverable regardless** — B10's testing gate and
   the live-upgrade principle have nowhere else to live.

**What to skip.** This package has no object model, no importable API and no
build step, so `research.md`, `data-model.md` and a quickstart at flow 04's scale
would be ceremony. `plan.md` is thin here too: §0.5-A already settles the ordering
question, which §7 treats as the plan's centrepiece. Aim at
**constitution → specify → clarify → tasks → checklist → implement**, with one
contracts file.

**If it is declined**, the honest fallback is this document as the decision
record plus the decisions written into `debian/postinst` and `docs/` — which
costs the cross-repo checkable contract (1) and leaves the testing gate (3)
unstated, but changes nothing about the work itself.

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
cd <this repository>
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

## 3. Constitution — DONE 2026-09-15 (`c238e74`), v1.0.0, six principles

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

## 4. Context block — paste verbatim into `/speckit-specify` and `/speckit-plan`

**Corrected 2026-09-15** against the working tree. The 2026-09-03 measurements
this block shipped with are preserved only where they still hold; everything
else carries its current line anchor. §0.5's corrections are folded in here, so
this block no longer asserts the two things the audit disproved.

```
CONTEXT — read these before writing anything. They live in the SIBLING checkout
../cuems-utils (paths relative to this repository's root), not in this repository:
  ../cuems-utils/specs/007-node-model-migration/migration-guide.md   §7 = THE RELEASE GATE, §9 = the
                                                                    Avahi files 007 deliberately excluded
  ../cuems-utils/specs/008-rebuild-extension/migration-guide.md      the conversion tool and its FR-042 entry
  ../cuems-utils/specs/planning/xml-rebuild/xml-rebuild-09-consumer-audit.md   C6, C7, C9, C11 are this repo's
  ../cuems-utils/specs/planning/xml-rebuild/xml-rebuild-07-speckit-prompts.md  §2 = the FULL decision list
  ../cuems-nodeconf/specs/001-network-map-object-adoption/contracts/avahi-txt.md  flow 04's half of D33,
                                                                    and the vocabulary it pins
  AND IN THIS REPOSITORY: .specify/memory/constitution.md (ratified 2026-09-15 — this spec is
      checked against it), docs/node-identity-contract.md, debian/postinst, debian/control,
      dev/planning/cuems-utils-xml-refactor-consumer-migration.md §0 (the audit this block is
      corrected from)

  (§§5-8 below inline the C6/C7/C9/C11 findings and the two migration-guide sections, so the
  sibling checkout is only needed for the full six-repo decision list and other repos' scope.)

SETTLED — the decisions that bind THIS repository. Do not reopen. Anything
outside this subset: read §2 of the prompts file above.
  D20 document compatibility is governed by an EXPLICIT version marker (doc_version), and
      008 built the conversion registry behind it
  D21 an OLD document converts on read; the same logic is also a standalone tool
  D33 the Avahi TXT-record vocabulary (node_type=master|slave|firstrun) is renamed in BOTH
      this repository AND cuems-nodeconf, inside feature 010, as ONE coordinated cutover --
      including the two template FILENAMES. It cannot be half-renamed: a listener reading
      node_role against a publisher writing node_type discovers nothing, and discovery
      failure is how a cluster loses its topology.
      (D33 as originally written also said "and the debian/install entries that place them".
      There are none -- see the measured state below. Renaming the templates needs no
      debian/install change; what it DOES need is a step that reaches the live file, which
      D33 never mentioned.)
      TARGET VOCABULARY, pinned by flow 04's contract -- must agree exactly, both halves:
        TXT key     node_role
        values      controller | node | firstrun     (master->controller, slave->node)
        filenames   cuems.service.{firstrun,controller,node}
        both service types carry it: _cuems_nodeconf._tcp:9000 and _cuems_osc._tcp:9090,
        i.e. TWO records per template. uuid is untouched.
  D27 nothing in the ecosystem releases until every 010 flow lands. This repository is where
      that gate is mechanically enforced.
  D30/D18b 008's duration promotion invalidates EVERY project document on disk, carried by
      the script 1->2 conversion. 007 converted ONE config file per node; this converts a
      whole library.

MEASURED STARTING STATE — re-verified against live files 2026-09-15:
  debian/postinst:109-133  the network_map node_type -> node_role conversion, run over BOTH
      /etc/cuems/network_map.xml and its .dpkg-new sibling, `|| true`, never fails the
      upgrade. Its comment at :113-117 STILL defers the ordering against dh_installsystemd's
      service restart to "feature 008" — a closed, renumbered, cuems-utils-only feature.
      That deferral is THIS feature's to resolve (007 FR-011d-ii).
  ^^ BUT THE DEFERRAL'S PREMISE IS FALSE, measured 2026-09-15:
      this package's debian/postinst carries NO #DEBHELPER# token (only debian/preinst:117
      does), so dh_installsystemd generates NOTHING into it. The package already relies on
      this elsewhere — debian/changelog:38-41 is why cuems-gpu-pin.service is enabled by hand
      rather than via WantedBy=. What postinst actually touches: systemd-journald, rsyslog,
      apache2, hostapd (reenable), ssh, rsync, and `systemctl enable` — never `start` — for
      the CUEMS units. NO map-reading CUEMS service is restarted from this postinst at all,
      and the one in-postinst reader (cuems-write-chrony-source, near the end) is already
      preceded by the conversion. So the ordering deliverable is a DECISION WRITTEN DOWN,
      not a re-sequencing. Do not spec work that does not exist.
  debian/control:12  cuems-utils (>= 0.1.0rc16)     :50  Breaks: cuems-nodeconf (<< 0.1.0-8)
      ^ the ONLY mechanically enforced edge of the release gate in the whole ecosystem, and
        a LOWER bound is the only thing this repository declares against cuems-utils
  etc/cuems/network_map.xml:9   <node_role>controller</node_role>   (already converted)
  etc/cuems/network_map.xsd     the mirrored schema — byte-identical to
      ../cuems-utils/src/cuemsutils/xml/schemas/network_map.xsd as of 2026-09-15, carries the
      optional doc_version attribute at :12
  THE AVAHI SURFACE, and how much of it the package actually owns:
  etc/avahi/services/cuems.service:6,13          <txt-record>node_type=master</txt-record>
      ^ NOT SHIPPED. No debian/install entry, nothing in debian/rules, nothing in postinst
        places it. The in-repo file is a checked-in copy of what a host ends up with; the LIVE
        file is only ever created by copying a template. CONSEQUENCE: renaming both
        repositories' halves changes NOTHING about an already-deployed host's announcement.
        Every running host keeps publishing node_type= until something re-copies a template,
        and cuems-nodeconf — which would — is disabled cluster-wide. A correctly-simultaneous
        D33 merge still leaves a cluster that cannot discover itself. THIS IS A DELIVERABLE.
  usr/share/cuems/cuems.service.firstrun:6,13    node_type=firstrun
  usr/share/cuems/cuems.service.master:6,13      node_type=master
  usr/share/cuems/cuems.service.slave:6,13       node_type=slave
      ^ THE RETIRED WORD IS IN THE FILENAME of the last two. These three DO ship — but
        through a single glob, debian/install:224 `usr/share/cuems/* usr/share/cuems/`.
        There are no per-file entries to rename.
  TWO RESOLVERS THAT NAME THE TEMPLATES, which the consumer audit never listed:
  etc/sudoers.d/99-cuems:3-5   three NOPASSWD rules naming the exact template paths
      (`/usr/bin/cp /usr/share/cuems/cuems.service.<x> /etc/avahi/services/cuems.service`).
      sudoers matches a command LITERALLY, so renaming the files revokes the privilege
      silently. It is also a CONFFILE — a host with a locally modified sudoers keeps the old
      rules, and the obsolete-conffile footgun applies.
  usr/bin/cuems-config-node:64  service_files = ['cuems.service.firstrun',
      'cuems.service.master', 'cuems.service.slave'] — hardcoded; rewrites the uuid= record.
  A NODE_TYPE READER OUTSIDE THE SIX-REPO SCOPE:
  usr/bin/cuems-cluster-poweroff:275  `if n.node_type != "NodeType.slave": continue`, through
      cuemspowerbridge.network_map (imported :209) — the cuems-power-bridge package, which
      this migration never enumerated and which is not checked out beside this repository.
      The 007 conversion already shipping on this branch retires that vocabulary from every
      live network_map.xml, so either that parser still reads <node_type> (the tool finds
      zero nodes and powers off nothing, silently) or it exposes node_role (AttributeError).
      It was NOT among the "three tools updated" by feature 007 (those were
      cuems-write-chrony-source, cuems-log-collector-url, cuems-logs).
  DOCUMENTATION CARRYING THE RETIRED WORD: README.md:227,231,232,264,306,307 and
      docs/node-identity-contract.md (5 occurrences). 45 occurrences across 15 tracked files
      in total — C6's "27" predates this branch.
  CLAUDE.md:94 (was :88): CONTROLLER_NETWORK_FLAG etc. correctly say "migrated in feature
      010". C9 item 2 is DONE.
  tests/test_network_map_conversion.py, tests/test_controller_resolution.py,
  tests/test_schema_mirror.py   the three existing test files — 23 tests, green. The default
      interpreter may have no pytest; the invocation this repository passes under is
      `uv run --with pytest --with lxml python -m pytest tests/ -q`.
  debian/changelog  top entry is 1.3.0-22. No entry exists for this feature.

ECOSYSTEM PIN STATE (C7) — re-measured 2026-09-15 where the checkout exists:
  cuems-engine    pyproject:41 >=0.1.0rc10   debian/control:18 >= 0.1.0rc4   (still disagree)
  cuems-nodeconf  pyproject:28 >=0.1.0rc15   debian/control:18 >= 0.1.0rc5
  cuems-common    debian/control:12 >= 0.1.0rc16 + :50 Breaks: cuems-nodeconf (<< 0.1.0-8)
  cuems-editor, cuems-wsclient   NOT CHECKED OUT beside this repository — their 2026-09-03
      rows (editor: pyproject >=0.1.0rc10, no debian entry; wsclient: >=0.1.0rc5 optional,
      debian >= 0.1.0rc5) are UNVERIFIED. Re-check before relying on them.
  Every one of those is a LOWER BOUND. A lower bound cannot express "refuse a library that
  moved past me", which is precisely what the gate says.
  SCOPE LIMIT: this repository CANNOT add a bound to another package's debian/control. Its
  share of "supply the missing edges" is (a) an upper bound or Breaks against cuems-utils in
  its OWN control file, and (b) running the demonstration. The other repos' edges belong to
  their own 010 flows.
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
  [VERIFIED 2026-09-15 — FALSE PREMISE, see §0.5-A: this postinst carries no #DEBHELPER#
  token, so dh_installsystemd injects nothing into it and no map-reading CUEMS service is
  restarted here at all. The deliverable is to write the decision down, not to re-sequence.]
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
  [VERIFIED 2026-09-15 — §0.5-B/C/D: there are NO debian/install entries (a glob at :224
  ships them) and etc/avahi/services/cuems.service is not shipped at all, so the rename does
  NOT reach deployed hosts' live announcement; add a live-file migration step. Two by-name
  resolvers the audit missed also move: etc/sudoers.d/99-cuems:3-5 (a conffile, exact-command
  NOPASSWD rules) and usr/bin/cuems-config-node:64. Target vocabulary is pinned by the
  counterpart's contracts/avahi-txt.md: key node_role, values controller/node/firstrun,
  filenames cuems.service.{firstrun,controller,node}.]
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
- debian/install — the renamed template filenames. [§0.5-B: no entries exist; glob at :224.]
- etc/sudoers.d/99-cuems and usr/bin/cuems-config-node — the by-name template resolvers
  (§0.5-D), plus wherever the LIVE /etc/avahi/services/cuems.service gets migrated (§0.5-C).
- README.md (6 occurrences) and docs/node-identity-contract.md (5) — §0.5-F.
- usr/bin/cuems-cluster-poweroff:275 + the cuems-power-bridge parser behind it — §0.5-E.
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
