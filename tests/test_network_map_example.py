# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T037 — operators have a node entry to copy once the shipped map has none (FR-026).

While cuems-nodeconf is disabled, operators hand-author ``network_map.xml``. The
placeholder node used to double as their template; with the shipped map empty
(FR-024), a complete example ships as documentation instead, and the
node-identity contract points to it.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "etc" / "cuems" / "network_map.xml.example"
SCHEMA = REPO_ROOT / "etc" / "cuems" / "network_map.xsd"
INSTALLED = "/usr/share/doc/cuems-common/network_map.xml.example"
REQUIRED = ("uuid", "mac", "name", "node_role", "ip")


def test_example_is_schema_valid():
    schema = etree.XMLSchema(etree.parse(str(SCHEMA)))
    assert schema.validate(etree.parse(str(EXAMPLE))), schema.error_log


def test_example_has_exactly_one_complete_node():
    nodes = etree.parse(str(EXAMPLE)).getroot().findall(".//node")
    assert len(nodes) == 1
    for field in REQUIRED:
        value = nodes[0].findtext(field)
        assert value and value.strip(), f"example node is missing {field}"


def test_example_is_installed_as_documentation():
    install = (REPO_ROOT / "debian" / "install").read_text(encoding="utf-8")
    assert re.search(r"^etc/cuems/network_map\.xml\.example\s+usr/share/doc/cuems-common/\s*$", install, re.M)


def test_contract_points_to_the_example():
    assert INSTALLED in (REPO_ROOT / "docs" / "node-identity-contract.md").read_text(encoding="utf-8")
