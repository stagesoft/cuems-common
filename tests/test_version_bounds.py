# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T024 — the cuems-utils bound behaves as decided, checked by dpkg itself (FR-016a, SC-009a).

The bound is read out of ``debian/control`` — never a hardcoded copy — and every
candidate version is judged by ``dpkg --compare-versions``, because Debian version
ordering is not what the strings suggest: ``0.1.0 < 0.1.0rc16`` is true, and a tilde
floor ``>= 0.1.0~rc16`` would admit ``0.1.0rc15``. The rc15 case is the regression
guard for that (analysis C2).

``dpkg`` missing → skip, naming what was searched; ``CUEMS_REQUIRE_TOOLS=1`` turns
that skip into a failure (same policy as ``test_sudoers_syntax.py``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL = REPO_ROOT / "debian" / "control"
SEARCH_DIRS = ["/usr/bin", "/bin"]

_OPS = {">=": "ge", "<<": "lt", "<=": "le", ">>": "gt", "=": "eq"}

REFUSED = ["0.1.0rc14", "0.1.0rc15", "0.1.0", "0.1.1~rc1", "0.1.1"]
ADMITTED = ["0.1.0rc16", "0.1.0rc17", "0.1.0+final"]


def _dpkg() -> str:
    found = shutil.which("dpkg", path=os.pathsep.join([os.environ.get("PATH", ""), *SEARCH_DIRS]))
    if found:
        return found
    reason = f"dpkg not found on PATH or in {', '.join(SEARCH_DIRS)}"
    if os.environ.get("CUEMS_REQUIRE_TOOLS") == "1":
        pytest.fail(f"{reason} (CUEMS_REQUIRE_TOOLS=1)")
    pytest.skip(reason)


def _field(name: str) -> str:
    """A control field's value with continuation lines joined; comments dropped."""
    lines = [l for l in CONTROL.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    value, inside = [], False
    for line in lines:
        if re.match(rf"^{re.escape(name)}:", line):
            inside = True
            value.append(line.split(":", 1)[1])
        elif inside and line[:1] in (" ", "\t"):
            value.append(line)
        elif inside:
            break
    return " ".join(value)


def _utils_relations() -> list[tuple[str, str]]:
    relations = []
    for item in _field("Depends").split(","):
        m = re.fullmatch(r"\s*cuems-utils\s*\(\s*(>=|<<|<=|>>|=)\s*([^)\s]+)\s*\)\s*", item)
        if m:
            relations.append((m.group(1), m.group(2)))
    return relations


def _satisfies(candidate: str) -> bool:
    dpkg = _dpkg()
    return all(
        subprocess.run([dpkg, "--compare-versions", candidate, _OPS[op], bound]).returncode == 0
        for op, bound in _utils_relations()
    )


def test_control_declares_a_floor_and_a_ceiling():
    ops = sorted(op for op, _ in _utils_relations())
    assert ops == ["<<", ">="], f"expected one floor and one ceiling, found {_utils_relations()}"


@pytest.mark.parametrize("candidate", REFUSED)
def test_version_is_refused(candidate):
    assert not _satisfies(candidate), f"cuems-utils {candidate} should be refused"


@pytest.mark.parametrize("candidate", ADMITTED)
def test_version_is_admitted(candidate):
    assert _satisfies(candidate), f"cuems-utils {candidate} should be admitted"
