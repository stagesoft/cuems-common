<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Contract — the release gate: what other repositories owe it

**Status**: recorded 2026-09-17 (T026). **Owner of each item**: the repository named in its heading.
**This repository's own edges** are in `debian/control` and are verified by
`tests/test_version_bounds.py`; this file records only what cuems-common **cannot** declare,
because a package relationship can only be written in the package that holds it (FR-019).

Paths are relative to this repository's root; `../<repo>` is a sibling checkout.

---

## 1. `cuems-utils` — the versioning contract this package's bound depends on (FR-016b)

cuems-common declares `cuems-utils (>= 0.1.0rc16), cuems-utils (<< 0.1.1~)`. That bound only
enforces the schema coupling if the library's version numbers cooperate:

| # | Rule | Why — measured with `dpkg --compare-versions` |
|---|---|---|
| 1 | Publish the rest of the 0.1.0 line as `0.1.0rcN`, **never a bare `0.1.0`**; a final, if one is wanted, is `0.1.0+final` | `0.1.0 < 0.1.0rc16` is **true**: a bare `0.1.0` sorts *below* every published rc, so apt treats it as a downgrade and this package's floor refuses it. `0.1.0+final > 0.1.0rc16` and `< 0.1.1~` are both true |
| 2 | Adopt the tilde spelling at **`0.1.1~rc1`** and use it from then on | In place it cannot work: `0.1.0~rc17 > 0.1.0rc16` is **false** (a downgrade to apt), and `0.1.0~rc17 >= 0.1.0rc4` / `>= 0.1.0rc5` are **false**, so `cuems-engine` and `cuems-nodeconf` would refuse it. An epoch would work but voids every epoch-less relationship in the ecosystem, permanently. `0.1.1~rc1 > 0.1.0rc16` is true |
| 3 | **Bump the minor** version for any schema change | A minor-release lock (`<< 0.1.1~`) only constrains schema drift if drift implies a new minor |
| 4 | Ship 0.1.1 **together with** the deprecated-surface removal | `src/cuemsutils/_deprecation.py:24` already announces `REMOVAL_RELEASE = "v0.1.1"`, asserted by `tests/contract/test_deprecation_shims.py`; rule 3 makes the next schema change 0.1.1 too, and D27 already requires every consumer to be migrated before release, so the two are one event (decided 2026-09-17) |

**Current state, measured 2026-09-17**: the newest *published* `cuems-utils` Debian package is
`0.1.0rc14` (`../cuems-utils` `origin/debian/bookworm`, `debian/changelog`); the Python package is
at `0.1.0rc16` (`src/cuemsutils/__init__.py`). No published package satisfies this package's floor
yet — `0.1.0rc14` is refused by it — so `cuems-utils` must publish `0.1.0rc16` or later before
cuems-common can be installed from packages. D27 already orders that release first.

**Accepted gap**: inside the remaining 0.1.0 rc line, a schema change passes the ceiling. Until
0.1.1, that window is covered only by `tests/test_schema_mirror.py` (byte identity with the
library's schema) and by D27.

## 2. `cuems-nodeconf` — the reverse edge of the discovery cutover

cuems-common's `Breaks: cuems-nodeconf (<< 0.1.0-8)` refuses an **un-renamed** nodeconf beside
this release. The opposite combination — a **renamed** nodeconf beside an **un-renamed**
cuems-common — is not refused by anything today:

- `../cuems-nodeconf/debian/control:19` declares `cuems-common (>= 1.0.0)`, which every
  cuems-common version satisfies, including the un-renamed `1.3.0-22`.
- A renamed listener beside un-renamed templates discovers nothing, silently (D33).

**Owed by flow 04**: its `0.1.0-8` must declare `cuems-common (>= <the cuems-common release
carrying the rename>)` — or an equivalent `Breaks: cuems-common (<< …)` — so the half-renamed
installation is refused in both directions. T027 attempts this combination and records the result
as observed, whatever it is.

## 3. Other consumers' own bounds

Recorded, not enforceable from here:

| Repository | `pyproject.toml` | `debian/control` | Owed |
|---|---|---|---|
| `cuems-engine` | `cuemsutils = ">=0.1.0rc10"` (`:41`) | `cuems-utils (>= 0.1.0rc4)` (`:18`) | The two disagree — the packaged floor is six release candidates behind the source one. Align them, and add a ceiling (constitution IV: a floor cannot refuse a library that moved past you) |
| `cuems-nodeconf` | — | `cuems-utils (>= 0.1.0rc5)` (`:18`) | Align with its source requirement and add a ceiling (its own T045) |
| `cuems-editor` | not checked out beside this repository | — | Unverified here; re-measure in its own flow |
| `cuems-wsclient` | not checked out beside this repository | — | Unverified here; re-measure in its own flow |

Every existing edge except cuems-common's is a lower bound only.
