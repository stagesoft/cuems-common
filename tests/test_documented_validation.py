# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T030 — the validation command the upgrade procedure documents actually works (FR-021, FR-027).

``docs/upgrade-verification.md`` tells an operator to validate a restored
``network_map.xml`` with a one-line command over the ``cuems-utils`` venv's
``xmlschema`` — not ``xmllint``, which no dependency installs and which cannot
evaluate XSD 1.1. This test extracts that exact command from the document and
runs its Python, so the documentation cannot drift into a command that does not
work. ``XMLSchema11`` matches how ``cuems-utils`` itself validates.

``xmlschema`` missing → skip; ``CUEMS_REQUIRE_TOOLS=1`` → fail. The suite's
invocation pins ``xmlschema==3.4.3``, the version ``cuems-utils`` pins.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "upgrade-verification.md"
#: The canonical schema lives in cuems-utils (feature 011, D4): this repository
#: ships no mirror any more. Skips rather than fails when the sibling checkout
#: is absent (a CI checkout of this repository alone) — unverifiable, not violated.
CANONICAL = REPO_ROOT.parent / "cuems-utils" / "src" / "cuemsutils" / "xml" / "schemas" / "network_map.xsd"
SCHEMA = CANONICAL
_needs_sibling = pytest.mark.skipif(not CANONICAL.is_file(), reason="cuems-utils sibling checkout not found")
#: The empty map cuems-common used to ship (byte-identical to the retired
#: conffile), kept as a fixture: cuems-utils's postinst creates an equivalent
#: when no map exists, and the documented command must still accept it.
EMPTY_MAP = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/"\n'
    '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    "    <node_list/>\n"
    "</cms:CuemsNetworkMap>\n"
)
EXAMPLE = REPO_ROOT / "etc" / "cuems" / "network_map.xml.example"


def _documented_command() -> list[str]:
    text = DOC.read_text(encoding="utf-8")
    m = re.search(r"<!-- validate-command -->\s*```sh\n(.+?)\n```", text, re.S)
    assert m, "no <!-- validate-command --> block in docs/upgrade-verification.md"
    return shlex.split(m.group(1))


def _require_xmlschema() -> None:
    if importlib.util.find_spec("xmlschema") is None:
        if os.environ.get("CUEMS_REQUIRE_TOOLS") == "1":
            pytest.fail("xmlschema not importable (CUEMS_REQUIRE_TOOLS=1)")
        pytest.skip("xmlschema not importable; run with --with xmlschema==3.4.3")


def _run(document: Path) -> subprocess.CompletedProcess:
    argv = _documented_command()
    code = argv[2]
    return subprocess.run(
        [sys.executable, "-c", code, str(SCHEMA), str(document)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_documented_command_has_the_expected_shape():
    argv = _documented_command()
    assert argv[0] == "/usr/lib/cuems/bin/python3"
    assert argv[1] == "-c"
    assert "XMLSchema11" in argv[2] and "xmllint" not in argv[2]
    assert argv[3:] == ["/etc/cuems/network_map.xsd", "/etc/cuems/network_map.xml"]


@_needs_sibling
@pytest.mark.parametrize("which", ["empty-map", "example"])
def test_documented_command_accepts_valid_maps(which, tmp_path):
    _require_xmlschema()
    if which == "example":
        document = EXAMPLE
    else:
        document = tmp_path / "network_map.xml"
        document.write_text(EMPTY_MAP, encoding="utf-8")
    result = _run(document)
    assert result.returncode == 0, result.stderr


@_needs_sibling
def test_documented_command_rejects_a_map_missing_a_required_field(tmp_path):
    _require_xmlschema()
    broken = tmp_path / "network_map.xml"
    broken.write_text(re.sub(r"\s*<ip>[^<]*</ip>", "", EXAMPLE.read_text(encoding="utf-8")))
    result = _run(broken)
    assert result.returncode != 0
