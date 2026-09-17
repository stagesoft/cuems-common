# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T008 — every shipped sudoers file passes sudo's own syntax check (FR-003c).

``visudo`` lives in ``/usr/sbin``, which Debian puts on root's ``PATH`` but not
on an ordinary user's (``ENV_SUPATH`` vs ``ENV_PATH`` in ``/etc/login.defs``).
A plain ``PATH`` lookup would therefore check sudoers when the suite runs as
root and silently skip it otherwise. The test resolves the tool itself instead
of depending on the caller's environment; no symlink, no exported ``PATH``.

``visudo -cf`` runs unprivileged. When it is genuinely absent the test skips,
naming where it looked — unless ``CUEMS_REQUIRE_TOOLS=1``, in which case a
missing tool is a failure: the environment meant to enforce FR-003c must not be
able to pass it by skipping.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SUDOERS_DIR = REPO_ROOT / "etc" / "sudoers.d"
SEARCH_DIRS = ["/usr/sbin", "/sbin"]


def _visudo() -> str:
    search = os.pathsep.join([os.environ.get("PATH", ""), *SEARCH_DIRS])
    found = shutil.which("visudo", path=search)
    if found:
        return found
    reason = f"visudo not found on PATH or in {', '.join(SEARCH_DIRS)}"
    if os.environ.get("CUEMS_REQUIRE_TOOLS") == "1":
        pytest.fail(f"{reason} (CUEMS_REQUIRE_TOOLS=1)")
    pytest.skip(reason)


@pytest.mark.parametrize("rules", sorted(p.name for p in SUDOERS_DIR.iterdir()))
def test_sudoers_file_parses(rules):
    result = subprocess.run(
        [_visudo(), "-cf", str(SUDOERS_DIR / rules)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{rules}: {result.stdout}{result.stderr}"
