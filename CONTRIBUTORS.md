<!--
***
SPDX-FileCopyrightText: 2025 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# Contributing to cuems-common

Thank you for considering a contribution to `cuems-common`. This document covers the full contributing workflow. Read it before opening a pull request.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Development Setup](#2-development-setup)
3. [Contribution Tiers](#3-contribution-tiers)
4. [Branch Naming](#4-branch-naming)
5. [Spec-First Requirement](#5-spec-first-requirement)
6. [TDD Workflow — Non-Negotiable](#6-tdd-workflow--non-negotiable)
7. [Commit Hygiene](#7-commit-hygiene)
8. [Developer Certificate of Origin (DCO)](#8-developer-certificate-of-origin-dco)
9. [Pull Request Requirements](#9-pull-request-requirements)
10. [Acceptance Criteria](#10-acceptance-criteria)
11. [Review Process](#11-review-process)
12. [Changelog Line](#12-changelog-line)
13. [Dependency Governance](#13-dependency-governance)
14. [License](#14-license)

---

## 1. Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Debian GNU/Linux | 12 (bookworm) | Target OS; all systemd and packaging tools are Debian-versioned |
| `systemd` | 252 (bookworm default) | `systemd-analyze verify` for unit validation |
| `shellcheck` | 0.9 | Shell script static analysis |
| `bash` | 5.2 | Running the test suite |
| `debhelper` | 13 | Building the Debian package |
| `devscripts` (`debuild`, `dch`) | bookworm default | Debian package build tools |
| `git` | 2.39 | Version control and DCO sign-off (`-s` flag) |

**Optional (for the OLA flock-patch test suite):**

| Tool | Purpose |
|---|---|
| Patched OLA `0.10.9.nojsmin-2+cuems2` | Required by `scripts/test-ola-flock-patch.sh` |
| `ola-python` | `ola_plugin_info` / `ola_plugin_state` / `ola_dev_info` CLIs |

**Optional (for live systemd tests):**

Running `scripts/test-systemd-deps.sh --live` requires a machine with the `cuems-common` package installed and the relevant systemd targets available. Do not run live tests in CI without a dedicated test machine.

---

## 2. Development Setup

Clone the repository and ensure submodules are initialised (none currently, but the workspace Makefile references sibling repos):

```bash
git clone https://github.com/stagesoft/cuems-common.git
cd cuems-common
git submodule update --init --recursive
```

Install the build and test dependencies:

```bash
sudo apt-get install debhelper devscripts shellcheck
```

To build the package locally without the workspace Makefile:

```bash
# From the cuems-common/ directory, on the debian/bookworm branch:
git checkout debian/bookworm
debuild -b -uc -us
```

To use the workspace-level Makefile (recommended when working across multiple CUEMS packages):

```bash
# From the parent workspace root:
make cuems-common
```

Run the static test suite (no side effects, no package installation required):

```bash
bash scripts/test-systemd-units.sh
bash scripts/test-systemd-deps.sh
bash scripts/verify-package-structure.sh
shellcheck scripts/*.sh usr/bin/cuems-cluster-poweroff usr/bin/cuems-displays-on usr/bin/cuems-ola-profile usr/bin/cuems-healthcheck
bash -n scripts/*.sh usr/lib/cuems/bin/check-ip.sh usr/lib/cuems/bin/wifi-auto.sh
```

---

## 3. Contribution Tiers

### Tier 1 — Trivial changes

Definition: a change that touches exactly one file, has an immediately obvious correct outcome, and cannot break a running installation. Examples: fixing a typo in a comment, updating a URL, adding a missing `shellcheck` disable annotation.

**Workflow for Tier 1:**
1. Branch from `main` using the naming convention in [§4](#4-branch-naming).
2. Make the change.
3. Commit with a Conventional Commits message and DCO sign-off.
4. Open a PR against `main`.
5. No spec document required.

### Tier 2 — Non-trivial changes

Definition: everything that is not Tier 1. Examples: adding a systemd service unit, changing a service dependency, introducing a new operator tool, modifying configuration defaults, changing packaging scripts (`postinst`, `preinst`, `debian/install`).

**Workflow for Tier 2:**
1. Open a GitHub Issue describing the problem and the proposed solution before writing any code.
2. If the reviewers agree on the approach, create a spec (design document) as a comment on the issue or as a `docs/` file. The spec must cover: what is changing, what invariant it enforces, and how it will be validated.
3. Get at least one reviewer to acknowledge the spec before proceeding to implementation.
4. Follow the TDD workflow in [§6](#6-tdd-workflow--non-negotiable).
5. Open a PR against `main` and link it to the issue.

---

## 4. Branch Naming

```
<type>/<short-description>
```

| Type | When to use |
|---|---|
| `feat/` | Adding a new service unit, operator tool, or configuration feature |
| `fix/` | Correcting a bug in a unit file, script, or packaging script |
| `refactor/` | Restructuring without changing observable behaviour |
| `docs/` | Documentation-only changes (runbooks, README, this file) |
| `test/` | Adding or fixing validation scripts |
| `chore/` | Packaging metadata, Makefile, CI plumbing |

Examples:
- `feat/cuems-gradient-motiond-unit`
- `fix/videocomposer-cuems-conf-path`
- `docs/latency-tuning-runbook`
- `test/ola-flock-patch-suite`

Use lowercase, hyphens, no slashes within the description part.

---

## 5. Spec-First Requirement

For all **Tier 2** changes, a spec must exist and be acknowledged before any implementation code is written. The spec is a short document (comment, Markdown file, or GitHub issue body) that answers:

1. **What** is changing and why — one paragraph maximum.
2. **What invariant** the change enforces — one sentence, testable. Example: *"After this change, `cuems-node-engine.service` will not start until `jack-alsa-bridges.service` reports active."*
3. **How** it will be validated — which test script covers it, or what manual verification procedure applies.
4. **What is deferred** — if the change is incomplete by design, say so explicitly.

A reviewer acknowledging the spec does not imply approval of the implementation. Implementation review happens separately in the PR.

---

## 6. TDD Workflow — Non-Negotiable

Even for a configuration-only package, every non-trivial change must follow the red → green → refactor cycle:

1. **Red** — write a test that fails because the intended behaviour does not exist yet. For `cuems-common` this means: write a `bash`-based check in `scripts/test-systemd-deps.sh` or `scripts/test-systemd-units.sh` that produces a `FAIL` line against the current state of the repository.
2. **Green** — implement the minimum change that makes the test pass (the test now produces a `PASS` line).
3. **Refactor** — clean up the implementation (improve unit file comments, remove redundancy, tighten dependency declarations) without breaking the passing test.

For shell script changes, the equivalent cycle is:

1. **Red** — add a `shellcheck` or `bash -n` invocation that reports an error against the draft script.
2. **Green** — write the script so it passes.
3. **Refactor** — apply `shellcheck` suggestions and clean up.

For packaging changes (`debian/install`, `postinst`, `preinst`):

1. **Red** — add a check to `scripts/verify-package-structure.sh` that fails because the new file is not yet listed in `debian/install`.
2. **Green** — add the file and the `debian/install` line.
3. **Refactor** — verify `postinst`/`preinst` idempotency (run twice on the same system, expect no errors).

If no existing test script covers the change, create one. New test scripts belong in `scripts/` and must follow the naming convention `test-<component>.sh`.

---

## 7. Commit Hygiene

All commits must follow **Conventional Commits v1.0.0** (<https://www.conventionalcommits.org/en/v1.0.0/>).

```
<type>(<scope>): <short summary in imperative mood>

[optional body — explain the why, not the what]

[optional footer(s) — BREAKING CHANGE:, Fixes #N, Signed-off-by:]
```

### Types

| Type | When to use |
|---|---|
| `feat` | A new service, operator tool, configuration feature, or systemd unit |
| `fix` | Corrects a defect in a unit file, script, or packaging script |
| `refactor` | Restructures code/units without changing observable behaviour |
| `docs` | Documentation only (runbooks, README, CONTRIBUTORS) |
| `test` | Adds or modifies a validation script |
| `chore` | Packaging metadata, Makefile targets, CI plumbing |
| `revert` | Reverts a previous commit (include the reverted commit SHA in the body) |

### Scopes

Use the component name as the scope: `node-engine`, `videocomposer`, `audio`, `ola`, `packaging`, `systemd`, `display`, `wifi`, `deps`, `test`.

### Rules

- **Subject line ≤ 72 characters**, imperative mood, no trailing period.
- **Body** is optional for Tier 1 changes. For Tier 2, the body must explain _why_ the change is needed, referencing the spec or the issue that motivated it.
- **Breaking changes** must include a `BREAKING CHANGE:` footer with migration instructions.
- **No merge commits** in a feature branch — rebase onto `main` before opening a PR.
- Each commit should be atomic: one logical change per commit, fully passing tests.

### Examples

```
feat(gradient-motiond): package systemd unit using controller.local

Ships the gradient fade engine as a first-class node service.
Connects to the NNG hub on tcp://controller.local:9093 via Avahi mDNS.
No per-node IP configuration needed. Part of MTC-bias Phase 7.

Signed-off-by: Ion Reguera <ion@stagelab.coop>
```

```
fix(videocomposer): respect CUEMS_CONF_PATH in latency extractor

cuems-extract-video-latency hardcoded /etc/cuems/settings.xml,
diverging from cuemsutils.tools.ConfigManager which honours
$CUEMS_CONF_PATH. Align the two so operators who set the env var
via `systemctl edit cuems-videocomposer` get consistent resolution.

Fixes #42
Signed-off-by: Adrià Masip <adria@stagelab.coop>
```

---

## 8. Developer Certificate of Origin (DCO)

Every commit must carry a **Signed-off-by** trailer. This is your certification that you have the right to submit the code under the project's GPL-3.0-or-later license (full text at <https://developercertificate.org/>).

Add it automatically with:

```bash
git commit -s -m "feat(audio): mask pipewire per-user units system-wide"
```

Or add it manually as the last line of the commit message body:

```
Signed-off-by: Your Name <you@example.com>
```

The name and email must match your git configuration (`git config user.name` and `git config user.email`). PRs with commits missing the sign-off will not be merged.

---

## 9. Pull Request Requirements

Before marking a PR as "Ready for review":

- [ ] All commits follow Conventional Commits and carry a DCO sign-off.
- [ ] `bash scripts/test-systemd-units.sh` exits 0 (no `FAIL` lines).
- [ ] `bash scripts/test-systemd-deps.sh` exits 0.
- [ ] `shellcheck scripts/*.sh usr/bin/cuems-ola-profile usr/bin/cuems-healthcheck usr/bin/cuems-cluster-poweroff usr/bin/cuems-displays-on` produces no errors (SC2034, SC2046, and similar informational codes are acceptable if annotated).
- [ ] `bash scripts/verify-package-structure.sh` exits 0.
- [ ] New or modified unit files pass `systemd-analyze verify <path>` with no errors.
- [ ] New shell scripts pass `bash -n <script>`.
- [ ] Every new source file carries an SPDX header (see [§14](#14-license)).
- [ ] `CHANGELOG.md` has a new entry under `[Unreleased]` (see [§12](#12-changelog-line)).
- [ ] PR description links to the issue or spec that motivated the change (Tier 2 only).
- [ ] No angle-bracket placeholders remain in any file touched by the PR.

**Target branch:** `main`. Do not target `debian/bookworm` directly; that branch is used for Debian packaging only and is managed by the maintainers.

**PR size:** keep PRs focused. A PR that changes a systemd unit, a test script, and the documentation for that unit is appropriately scoped. A PR that reorganises the entire `etc/` tree in the same commit as a new feature is too large — split it.

**Draft PRs:** open a draft PR early for Tier 2 changes to get early feedback on the approach. Convert to "Ready for review" only when all checklist items above are met.

---

## 10. Acceptance Criteria

A PR is mergeable when **all** of the following are true:

| Gate | Criterion |
|---|---|
| Unit validation | `scripts/test-systemd-units.sh` exits 0 |
| Dependency graph | `scripts/test-systemd-deps.sh` exits 0 |
| Shell lint | `shellcheck` produces no errors on modified shell scripts |
| Package structure | `scripts/verify-package-structure.sh` exits 0 |
| Syntax | `bash -n` passes on all modified shell scripts |
| DCO | Every commit has a `Signed-off-by` matching the author |
| Conventional Commits | Every commit subject matches `<type>(<scope>): <summary>` |
| SPDX headers | Every new file has the correct SPDX header (see [§14](#14-license)) |
| CHANGELOG | `[Unreleased]` section in `CHANGELOG.md` updated |
| Review | At least one approval from a maintainer |

For Tier 2 changes, the spec must also be acknowledged before the PR is opened (see [§5](#5-spec-first-requirement)).

---

## 11. Review Process

Pull requests are reviewed by:

- **Ion Reguera** ([@ibiltari](https://github.com/ibiltari)) — lead maintainer
- **Adrià Masip** ([@backenv](https://github.com/backenv)) — co-maintainer

At least one approval from the above is required before merging. Both reviewers may be requested on a PR; either approval is sufficient.

**Response time:** maintainers aim to leave a first comment within 5 business days. If your PR has received no response after 7 days, ping the maintainers by commenting on the PR or opening a thread in the [stagesoft/cuems-common Issues](https://github.com/stagesoft/cuems-common/issues).

**Review etiquette:**
- Reviewers will leave comments using the GitHub suggestion feature where possible so they can be applied with a single click.
- Address every comment before re-requesting review. If you disagree, explain why in a reply; do not silently close the conversation.
- Avoid force-pushing to a branch that is under review — it makes review history harder to follow. Use new commits and squash before merge if requested.

---

## 12. Changelog Line

Every PR that changes runtime behaviour (adds a service, fixes a bug, changes a configuration default) must include an update to `CHANGELOG.md` under the `[Unreleased]` section.

**Format:**

```markdown
### Added
- `<unit-or-script-name>` — one sentence describing what it does and why it matters.

### Changed
- `<unit-or-script-name>`: <old behaviour> → <new behaviour>. Migration: <steps if any>.

### Fixed
- `<unit-or-script-name>`: <symptom>. Root cause: <explanation>.

### Removed
- `<item>` — deprecated since <version>. Removed because <reason>; superseded by <replacement if any>.
```

Use the exact file or unit name as the leading term. Keep each entry to one sentence where possible. Do not write "various improvements" or similar vague summaries.

---

## 13. Dependency Governance

`cuems-common` is a Debian `architecture: all` package. Its runtime dependencies are declared in `debian/control` (`Depends:` field). The rules for changing them:

**Adding a new runtime dependency:**
1. Verify the package exists in Debian 12 (bookworm): `apt-cache show <package>` on a bookworm system.
2. Check whether it is already pulled in transitively by an existing dependency.
3. Add it to `Depends:` in `debian/control`, alphabetically within the comma-separated list.
4. Document why it is needed in the PR description.
5. If the new dependency is a system daemon (e.g. `avahi-daemon`, `isc-dhcp-server`), also add the corresponding service to the appropriate `PartOf=` or `Wants=` in the relevant systemd unit.

**Removing a runtime dependency:**
1. Confirm that no unit file, script, or `postinst`/`preinst` references the package's binaries or services.
2. Confirm that removing it does not break any currently passing test.
3. Add a `### Removed` entry to `CHANGELOG.md` explaining the removal.

**Pinned third-party packages (e.g. patched OLA):**
- The patched OLA package (`0.10.9.nojsmin-2+cuems2`) is pinned via `/etc/apt/preferences.d/` on installed nodes, not via `debian/control`. This is intentional: `debian/control` only lists packages available in the standard Debian repository. Document pinning instructions in `docs/` (see `docs/ola-install.md`).

**No vendored code:**
- Do not copy third-party scripts or configuration fragments into this repository without (a) the original copyright and license information, (b) a clear note that it is vendored, and (c) a maintainer-approved plan for keeping it updated.

---

## 14. License

`cuems-common` is licensed under the **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). By submitting a contribution you agree that your contribution will be licensed under the same terms.

### SPDX headers

Every new source file you create must start with the following SPDX header block:

**Shell scripts and Python scripts:**

```bash
# SPDX-FileCopyrightText: <year> Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
```

**Markdown files:**

```markdown
<!--
***
SPDX-FileCopyrightText: <year> Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->
```

**XML files** (e.g. Avahi service files, network map):

```xml
<!-- SPDX-FileCopyrightText: <year> Stagelab Coop SCCL -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
```

Use the current calendar year as `<year>`. Use `Stagelab Coop SCCL` as the copyright entity — do not substitute your personal name or employer.

Files that already carry an SPDX header from a prior contributor should **not** have their `SPDX-FileCopyrightText` replaced — add a new `SPDX-FileCopyrightText` line alongside the existing one if you made substantial changes:

```bash
# SPDX-FileCopyrightText: 2025 Stagelab Coop SCCL
# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
```

Systemd unit files, ALSA configuration fragments, logrotate rules, sysctl drop-ins, and other plain-text configuration files that do not support comment syntax do not require SPDX headers; their licensing is covered by the `debian/copyright` file.
