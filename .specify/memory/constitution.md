<!--
SYNC IMPACT REPORT
Version change: 1.0.1 → 1.0.2 (PATCH)
Rationale: factual corrections after feature 001's implementation (1.3.0-23), raised by its
task T030. No principle is added, removed or redefined.

Modified sections:
  - Testing Gate and Development Workflow — the suite invocation gains
    `--with xmlschema==3.4.3` (tests now run the validation command operators are told to use,
    over the xmlschema version cuems-utils pins); the stale "three test files and twenty-three
    tests" count is replaced by a description that does not go out of date.
  - III. This Package Is The Ordering Authority — its example deferral ("feature 008" in
    debian/postinst) was resolved in 1.3.0-23; the example is kept, in the past tense.
  - IV. The Gate Is Mechanical Or It Is Not A Gate — the cuems-utils floor-and-ceiling is now a
    second enforced edge beside the cuems-nodeconf Breaks, and both have been observed refusing
    (tests/packaging/release-gate-demo.sh).

Added sections: none
Removed sections: none
Deferred placeholders: none

Not done here, would be MINOR: codifying the tool-resolution rule (tests resolve system tools
themselves and fail rather than skip under CUEMS_REQUIRE_TOOLS=1), and moving "dpkg refusal of
an out-of-order install" from the manual half of the Testing Gate to a scripted demonstration.

Templates reading this constitution at runtime were not modified.

--- Previous report (1.0.1, 2026-09-17) ---
Version change: 1.0.0 → 1.0.1 (PATCH)
Rationale: clarification of Principle VI. Its conffile-retirement rule, read literally, applies
`dpkg-maintscript-helper rm_conffile` to every retired conffile — including one that holds
host-owned live state, where that helper moves a modified live file aside and deletes an
unmodified one. That is the 1.3.0-20 outcome Principle I already cites, and it surfaced again
when feature 001's analysis found a task recording rm_conffile as the future path for
network_map.xml. The amendment names the exception and the pattern that already exists in
debian/preinst + debian/postinst for /etc/network/interfaces. No principle is removed or
redefined, and the rule's scope for ordinary conffiles is unchanged — hence PATCH.

Modified principles:
  - VI. Every Shipped File Is Owned, Retired, And Signed — conffile retirement now excludes
    host-owned live state, which is de-registered by snapshot and restore-if-absent instead.

Added sections: none
Removed sections: none
Deferred placeholders: none

Templates reading this constitution at runtime were not modified.

--- Previous report (1.0.0, 2026-09-15) ---
Version change: (none) → 1.0.0
Rationale: initial ratification. No prior constitution existed in this repository;
.specify/memory/constitution.md was the unfilled core template until today.

Modified principles: none (initial adoption)

Added sections:
  - Core Principles I–VI
  - Operating Constraints
  - Testing Gate and Development Workflow
  - Governance

Removed sections: none

Principles derived from: CLAUDE.md (role model, the conffile footgun, the GRUB recovery
rules, the dpkg-db drift note), from debian/{preinst,postinst,postrm,control,install,rules},
and from the 2026-09-15 audit recorded in
dev/planning/cuems-utils-xml-refactor-consumer-migration.md §0.

Deferred placeholders: none.

Templates reading this constitution at runtime (plan-template.md's Constitution Check,
spec-template.md, tasks-template.md) were not modified — they resolve it when they run.
-->

# cuems-common Constitution

This repository is the system-level Debian package delivering all shared configuration,
systemd units, and operator tools for a CUEMS install. It carries **no compiled code**:
every executable it ships is a shell or Python script, and the compiled daemons come from
their own packages and are only wired into the systemd graph here. A CUEMS host is either a
controller (one per cluster) or a node (many), and **roles are dynamic** — any host can be
promoted or demoted without a reinstall, decided only by `<node_role>` in
`/etc/cuems/network_map.xml`.

Everything below follows from that. The principles are not general engineering advice; they
are the rules this particular delivery mechanism has already been bitten by.

## Core Principles

### I. The Unit Of Delivery Is A Package Upgrade On A Live Machine (NON-NEGOTIABLE)

Correctness is not "the change is right". Correctness is **`postinst` left a working host**
— a host that may be mid-show, whose conffiles the operator has locally modified, whose
services are running, and which may not reboot for weeks.

- Every maintainer-script step MUST be safe to run against a live, in-use system, and MUST
  assume the operator edited whatever it is about to touch.
- An upgrade that fails halfway is the failure mode to design against. A step that cannot be
  made safe MUST be guarded (`|| true`, a `[ -x ]` test, a `command -v` probe) so it degrades
  instead of aborting `dpkg` and leaving the package half-configured.
- A change whose damage appears **later** — at the next reboot, at the next show — is worse
  than one that fails loudly now. `1.3.0-22` exists because a conffile retirement deleted a
  host's live `/etc/network/interfaces` and nothing failed at the time; the host came up with
  no network days later, at a venue.
- Anything host-specific that the package has ever owned MUST survive `purge`.

*Rationale: this package has no test environment that resembles production. Production is a
controller in a venue, and the feedback loop is a physical trip.*

### II. Conversions Back Up, Repeat, And Never Fail The Upgrade

This package OWNS file-format migration for the ecosystem's config. It already ships
`usr/bin/cuems-migrate-network-map` and runs it from `debian/postinst`.

Any conversion this package runs MUST:

- **back up before it writes**, to a timestamped copy that reproduces the pre-conversion
  bytes exactly — that backup is the only supported way back (see V), so it is not optional;
- **be idempotent** — `postinst` runs again on every reinstall and every upgrade, and
  converting an already-converted document MUST be a no-op that says so;
- **never fail the upgrade** — it exits 0 even when it refuses a document, and its call site
  is guarded besides;
- **refuse a document whole** rather than half-convert it, and name the offending value and
  the accepted set in the message;
- **state its retention policy**. A conversion that writes a backup per document MUST say how
  those backups are pruned and by what.

### III. This Package Is The Ordering Authority

Nothing else in the ecosystem can sequence a conversion against a service start. Ordering
decisions belong here, and they are **written down at the point of decision**, never
inherited and never deferred to another repository's feature number.

- A deferral MUST name what it is waiting for in terms that can be checked, not a feature
  number that can be renumbered or closed. `debian/postinst`'s ordering comment deferred to
  "feature 008" — a feature that closed and was renumbered — from feature 007 until 1.3.0-23,
  which is exactly the failure this rule forbids; `tests/test_postinst_ordering.py` now keeps
  it from recurring.
- Ordering claims MUST be stated against what this package actually does. This `postinst`
  carries **no `#DEBHELPER#` token** (only `debian/preinst` does), so `dh_installsystemd`
  generates nothing into it: units are enabled explicitly, and no map-reading CUEMS service is
  restarted from `postinst` at all. Any statement about "the autogenerated restarts" MUST be
  verified against the file before it is written.
- Where a decision is that *nothing* needs re-sequencing, that is a decision and it gets
  recorded with its reasoning, not left implicit.

### IV. The Gate Is Mechanical Or It Is Not A Gate

Versioned dependencies and `Breaks:` are how this ecosystem refuses an out-of-order upgrade.
Prose in a migration guide is not enforcement.

- A cross-package ordering requirement MUST be expressed in `debian/control`. This package
  holds the ecosystem's mechanically enforced edges — `Breaks: cuems-nodeconf (<< 0.1.0-8)` and
  `cuems-utils (>= 0.1.0rc16), cuems-utils (<< 0.1.1~)` — and that is the pattern, not the
  exception.
- A **lower bound cannot express "refuse a library that moved past me"**. Where the
  requirement is an upper bound, it MUST be written as one — a `Breaks:` or a version ceiling
  — not approximated with a floor.
- **A gate that has never been demonstrated against a real install is a claim.** A gate is
  complete when an out-of-order combination has actually been installed and `dpkg` was
  watched refusing it; until then it is recorded as asserted-not-demonstrated.
- `debian/control` and any source-level pin (a sibling's `pyproject.toml`) MUST agree, and a
  disagreement is a defect to report even when it lives in another repository.

### V. Downgrade Is Unsupported, By Decision

No reverse conversion exists or is planned. The only path back from a converted host is the
timestamped backup the conversion wrote.

This is a deliberate position, not an oversight, and it is stated plainly in operator-facing
documentation rather than implied. A feature that changes this position does so **explicitly**,
with the reverse conversion as a deliverable — it is never introduced quietly as a
convenience.

### VI. Every Shipped File Is Owned, Retired, And Signed

What `dpkg` remembers about this package is this package's problem.

- **Dropping a file from `debian/install` does not remove it from installed hosts.** dpkg
  marks it `obsolete` and keeps it on disk forever, so upgraded boxes and fresh installs
  diverge with nothing in any log to say so. A retired conffile MUST be retired with
  `dpkg-maintscript-helper rm_conffile` in **all three** of `preinst`, `postinst` and
  `postrm`, hand-written for the reason recorded at the top of `debian/postinst`.
- **Except a conffile that holds host-owned live state** — cluster topology, network
  configuration, anything a host or operator writes after installation. `rm_conffile` moves a
  modified copy to `.dpkg-bak` and deletes an unmodified one, so on such a file it removes the
  host's live state: the 1.3.0-20 upgrade did exactly that to `/etc/network/interfaces`. Such a
  file MUST be de-registered by **snapshotting it in `preinst`, de-registering it, and restoring
  it in `postinst` only when the path is empty** — the pattern 1.3.0-22 adopted, and the only
  acceptable one. The rule is about the file's role, not its location: being under `/etc` does
  not make a file safe to retire.
- A conffile is **not** an experiment surface. Trying something out by editing a shipped
  conffile on a host makes dpkg keep the local version on the next non-interactive install
  and say almost nothing — which reads as "the `.deb` didn't install".
- A file the package does **not** ship MUST NOT be reasoned about as if it did. Renaming a
  template changes nothing on a host whose live copy the package never placed; reaching that
  copy is a separate, explicit step.
- Scripts that run inside another package's hook (`/etc/grub.d/*`, `ExecStartPre=` helpers)
  MUST NOT exit non-zero on missing input — a non-zero exit there breaks the host, not just
  the feature. Missing input ⇒ `exit 0`.
- **Commits are GPG-signed.** On "gpg failed to sign", retry; never `--no-gpg-sign`.
- Every host-visible change ships with a `debian/changelog` entry that says what an operator
  would observe, not what the diff did.

## Operating Constraints

- **Role is decided only by `<node_role>`** in `/etc/cuems/network_map.xml`. Role-aware hooks
  detect via the presence of `/etc/cuems/master.ip`, MUST be idempotent, and MUST clean up the
  files belonging to the opposite role when invoked — a promotion and a demotion both run the
  same hook.
- **Standardize on controller/node** for all new code, docs, strings, log messages, config
  fields and paths. Legacy `master`/`slave` survives only in identifiers awaiting a separate
  coordinated migration (`/etc/cuems/master.ip`, `master.lock`, and consumer-side enum
  constants). Reading them is fine; introducing new occurrences is not.
- **Wire contracts are cross-repository and cannot be half-changed.** The Avahi TXT
  vocabulary is read by a daemon in another package; a listener reading one key against a
  publisher writing another discovers nothing, silently. Such a change lands as one cutover,
  with the package relationship (IV) making a half-renamed installation impossible.
- **`dpkg-query` is not ground truth on every host.** Where an operator has no sudo password
  for `dpkg`, packages are deployed by file-copy, so the database reports stale versions while
  the binaries are new. Audit by binary file date or `/proc/<pid>/exe`.
- **Third-party units are extended by drop-in, never by replacement**, except where no drop-in
  mechanism exists (`avahi-daemon.conf`, `dhcpd.conf`) — those install from a
  `/usr/share/cuems/` template on first install only, so operator edits survive upgrades.

## Testing Gate and Development Workflow

This repository has no Python packaging; its tests are a pytest suite under `tests/` that needs
no installed package and no root. The gate is stated so it can actually be met, because a rule
that gets waived is worse than no rule.

**Covered by tests — required.** Shell and Python tools under `usr/bin/` and
`usr/lib/cuems/bin/`, conversion scripts, and anything that parses or rewrites a config
document. Every conversion MUST carry tests for: the happy path, an already-converted input
(idempotence), an unrecognised value (whole-document refusal), and the backup reproducing the
original bytes. Schema mirrors MUST carry a byte-identity test against the canonical copy,
skipping — not failing — when the sibling checkout is absent.

Run them with:

```
uv run --with pytest --with lxml --with xmlschema==3.4.3 python -m pytest tests/ -q
```

The default interpreter on a development machine may have no pytest; that invocation is the
one this repository is known to pass under, and it is what "tests are green" means here.
`xmlschema` is pinned to the version `cuems-utils` pins, because the suite runs the validation
command the upgrade documentation tells operators to use against that library.

**Not covered by tests — required as a written manual procedure.** systemd unit ordering,
`dh_installsystemd` behaviour, conffile prompts, `dpkg` refusal of an out-of-order install,
and anything whose subject is a running host. These are verified by a **documented upgrade
check**, and the document is a deliverable of the feature that needs it, not a memory:

- the exact package versions installed, in order;
- what was observed (unit states, journal excerpts, the file the conversion rewrote);
- and — for a cluster-affecting change — that the check was run on a **controller plus at
  least one node**, not a single host.

A feature MAY NOT claim an upgrade-affecting outcome that neither half of this gate covers.

**Work is recorded where it is checkable.** Cross-repository agreements (a wire key, a
version bound, a filename) are written into this repository as a contract file, so "the two
halves agree" is a file comparison rather than a conversation.

## Governance

This constitution supersedes ad-hoc practice in this repository. Where it and a planning
document disagree, this document wins and the planning document is corrected.

- **Amendments** are proposed as a diff to this file with the rationale in the commit
  message, and take effect when merged. The Sync Impact Report at the top of this file is
  updated in the same commit.
- **Versioning** is semantic: MAJOR for a principle removed or redefined incompatibly, MINOR
  for a principle or section added or materially expanded, PATCH for clarifications and
  wording.
- **Compliance review** happens at two points: a feature's plan records how each principle is
  satisfied or why it does not apply, and the review before merge checks the packaging files
  (`debian/control`, `debian/install`, the three maintainer scripts, `debian/changelog`)
  against Principles I, II, IV and VI specifically — they are where this package's failures
  have actually occurred.
- **No rule here is weakened to accommodate the migration in progress.** A migration that
  cannot meet a principle records the gap as a deliverable, not as an exception.
- Runtime development guidance — the role model, the field notes, the gotchas — lives in
  `CLAUDE.md` and is kept current; this constitution governs, `CLAUDE.md` informs.

**Version**: 1.0.2 | **Ratified**: 2026-09-15 | **Last Amended**: 2026-09-17
