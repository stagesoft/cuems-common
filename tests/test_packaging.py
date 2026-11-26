# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""The package build must never run the Makefile at the root of this repository.

That Makefile builds and cleans the whole CUEMS workspace: its `clean` removes
git worktrees outside this repository. debhelper runs `make clean` (and
`install`, `test`) on its own when it finds one, unless the step is overridden
with an empty rule.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
STEPS = ('configure', 'build', 'test', 'install', 'clean')


def override_body(step):
    """The recipe lines of override_dh_auto_<step>, or None when there is none."""
    rules = (REPO / 'debian/rules').read_text()
    match = re.search(rf'^override_dh_auto_{step}:[ \t]*\n((?:\t.*\n|[ \t]*#.*\n)*)', rules, re.M)
    if not match:
        return None
    return [line for line in match.group(1).splitlines() if line.startswith('\t')]


@pytest.mark.parametrize('step', STEPS)
def test_debhelper_never_runs_make_here(step):
    body = override_body(step)
    assert body is not None, f'override_dh_auto_{step} is missing'
    assert body == [], f'override_dh_auto_{step} must do nothing, it runs: {body}'


def test_the_makefile_is_still_the_one_this_protects_against():
    text = (REPO / 'Makefile').read_text()
    assert re.search(r'^clean:', text, re.M) and 'rm -rf' in text
