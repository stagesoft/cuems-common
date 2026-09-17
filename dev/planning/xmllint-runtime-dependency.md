<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# `xmllint`: an undeclared runtime tool, and the wrong validator for this ecosystem

**Status**: findings recorded, fix not started — planned for a future feature
**Measured**: 2026-09-17, on `feat/xml-refactor`
**Raised by**: feature 001 (`specs/001-node-role-and-conversion-ordering`) readiness check
**Already handled inside feature 001**: only T030, which moves that feature's own restore
procedure off `xmllint`. Everything else below is out of feature 001's scope.

Paths are relative to this repository's root; `../cuems-utils` is the sibling checkout.

---

## 1. The question that started this

Is `xmllint` a build dependency, a test requirement, or something else? **It is neither of the
first two.** It is a **runtime** tool that shipped documentation and one in-repo script expect
to find on a host, while no dependency of this package guarantees it — and, separately, it is
not able to validate every schema this ecosystem uses.

| Role | Uses `xmllint`? | Evidence |
|---|---|---|
| Build | **No** | `debian/control:5` `Build-Depends: debhelper-compat (= 13)` only; `debian/rules` never calls it |
| Tests | **No** | `tests/test_schema_mirror.py:9` names it in a docstring; the test compares bytes |
| Runtime — operator docs | **Yes** | `CLAUDE.md:50`, `CLAUDE.md:73`; `docs/node-identity-contract.md:211`, `:384` |
| Runtime — a script | **Yes** | `usr/lib/cuems/bin/cuems-display-setup:612` via `subprocess.run` |
| Declared by this package | **No** | `libxml2-utils` appears in no `Depends:`/`Recommends:`/`Suggests:` |

On the development machine where this was measured, `libxml2-utils` is not installed. Nothing
here establishes whether production hosts have it; that is the first thing to check (§6).

## 2. Finding A — it is the wrong validator, not just an undeclared one

`xmllint` validates with libxml2, which implements **XSD 1.0 only**. This ecosystem's schemas are
authored and validated as **XSD 1.1**:

- `../cuems-utils/src/cuemsutils/xml/schemas/script.xsd:37` carries
  `<xs:assert test="modified &gt;= created" />` — an XSD 1.1 assertion.
- `cuems-utils` validates with `xmlschema.XMLSchema11` everywhere
  (`../cuems-utils/src/cuemsutils/xml/schema.py`, `xml/xml_reader_writer.py`).
- `docs/latency-tuning.md:88-89` in this repository already documents the `XMLSchema11` idiom.

Today `network_map.xsd` and `project_mappings.xsd` happen to contain no 1.1 constructs, so
`xmllint` works on them by coincidence. It cannot validate `script.xsd`, and nothing stops a 1.1
construct from being added to the others. **A documented validation procedure should use the
same validator the library does**, or it will disagree with the software it is checking.

## 3. Finding B — `cuems-display-setup` writes before it validates, and cannot revert

`usr/lib/cuems/bin/cuems-display-setup` rewrites `/etc/cuems/default_mappings.xml`
(`DEFAULT_MAPPINGS_XML`, `:29`) and then validates it against `/etc/cuems/project_mappings.xsd`
(`PROJECT_MAPPINGS_XSD`, `:30`):

```
:598-601  copy the current file to <path>.bak-<timestamp>
:603-606  write to <path>.tmp.<pid>, then os.rename() it over the live file   ← live file replaced
:609-623  if the XSD exists: subprocess.run(['xmllint', ...], check=True)
          except subprocess.CalledProcessError: restore from backup, exit 1
```

Three defects, in increasing order of consequence:

1. **The handler catches only `CalledProcessError`.** If `xmllint` is absent, `subprocess.run`
   raises `FileNotFoundError`, which propagates as a traceback — **after** the live file was
   replaced. The revert path never runs, and the operator sees a crash rather than "validation
   unavailable". (The script's other subprocess call, `:121-127`, does catch
   `FileNotFoundError`; this one was simply not given the same treatment.)
2. **It validates after replacing the live file.** Even when `xmllint` exists, a reader between
   `:606` and `:621` sees an unvalidated document, and correctness depends on the revert working.
   Validating the temporary file *before* `os.rename()` removes the need to revert at all.
3. **Validation is silently optional.** The whole block is guarded by
   `os.path.isfile(PROJECT_MAPPINGS_XSD)`, and this package ships no `project_mappings.xsd` (its
   `etc/cuems/` carries only `network_map.xsd`). On a host without that file, the tool writes and
   never validates, and says nothing.

**Blast radius today is small**: `cuems-display-setup` has **never been listed in
`debian/install`** (`git log -S cuems-display-setup -- debian/install` is empty), and no glob
covers it. `usr/lib/cuems/bin/cuems-generate-display-conf:116` mentions it only in a comment. It
is an in-repository operator tool, not a shipped one. That makes this a latent defect — but the
file lives under a shipped path, and shipping it later would ship the defect with it.

## 4. Finding C — every host already has a correct validator

`cuems-common` depends on `cuems-utils` (`debian/control:12`), and `cuems-utils`' venv pins
`xmlschema==3.4.3` and `lxml==6.1.0` (`../cuems-utils/pyproject.toml:38-39`) behind
`/usr/lib/cuems/bin/python3`. So on every host this package can be installed on, this works with
no additional dependency:

```
/usr/lib/cuems/bin/python3 -c "import sys, xmlschema; xmlschema.XMLSchema11(sys.argv[1]).validate(sys.argv[2])" <schema.xsd> <document.xml>
```

Measured 2026-09-17 with `xmlschema==3.4.3`: the shipped `etc/cuems/network_map.xml` and an empty
`<node_list/>` document exit 0; the same map with `<ip>` removed exits 1.

## 5. Options

| # | Option | For | Against |
|---|---|---|---|
| 1 | **Replace every `xmllint` use with the venv `XMLSchema11` validator** | Zero new dependencies; guaranteed present; agrees with the library on XSD 1.1 | The one-liner is long for operators — see option 4 |
| 2 | `Suggests: libxml2-utils` | Honest about optional operator convenience; no install cost | Keeps a validator that is wrong for XSD 1.1 schemas in the documentation |
| 3 | `Recommends:`/`Depends: libxml2-utils` | Makes the existing docs work as written | Adds a dependency to fix a tool that should not be used; still XSD 1.0 only |
| 4 | Ship a small operator command (e.g. `cuems-validate-xml <xsd> <xml>`) wrapping option 1 | Short, memorable, one place to fix; exits non-zero with a readable message; reusable by scripts | One more shipped file, needs its own test and a `debian/install` line |

**Recommended: 1 + 4.** Ship `cuems-validate-xml` as the single validation entry point, point all
documentation and `cuems-display-setup` at it, and declare no `libxml2-utils` relationship at
all. Option 2 is acceptable as a temporary step only if the documentation cannot be updated in
the same release.

## 6. Fix plan (for the future feature)

1. **Verify on real hosts first** — do controllers and nodes in the field have `libxml2-utils`?
   Audit by file (`ls /usr/bin/xmllint`), not by `dpkg-query`, per the dpkg-db drift note in
   `CLAUDE.md`. This decides whether existing operator habits are currently working or failing.
2. Add `usr/bin/cuems-validate-xml`: stdlib argument handling, `/usr/lib/cuems/bin/python3`
   interpreter, `xmlschema.XMLSchema11`, exit 0 valid / 1 invalid / 2 unusable input, the
   validator's own message on failure. Test it against the shipped map (valid), an empty map
   (valid), a map missing a required field (invalid), and `script.xsd` with an `xs:assert`
   violation (invalid) — the case `xmllint` cannot detect.
3. Fix `cuems-display-setup`: validate `<path>.tmp.<pid>` **before** `os.rename()`, using
   `cuems-validate-xml`; delete the post-write revert path it no longer needs; and report,
   rather than silently skip, when the schema is absent.
4. Decide `project_mappings.xsd`'s deployer — it is a class D file in
   `dev/planning/systemd-service-split-architecture.md` §7: required at runtime, shipped by no
   package. Validation that depends on it cannot be guaranteed until someone ships it.
5. Replace `xmllint` in `CLAUDE.md:50`, `CLAUDE.md:73`, `docs/node-identity-contract.md:211`
   and `:384`; align `docs/latency-tuning.md:88-89` on the same command.
6. Only then decide whether `cuems-display-setup` should ship — as a separate question, with
   its own tests.
7. Add a repository test that fails if a shipped file or shipped documentation invokes
   `xmllint`, so the fix cannot be undone by a copy-pasted command.

## 7. Relationship to feature 001

Feature 001 takes only the slice it needs: **T030** makes its own restore procedure
(`docs/upgrade-verification.md`, T029) validate with the venv `XMLSchema11` command and tests
that the documented command works. It does not add `cuems-validate-xml`, does not touch
`cuems-display-setup`, and does not rewrite the existing documentation. When the future feature
ships `cuems-validate-xml`, T030's documented command should be replaced by it.
