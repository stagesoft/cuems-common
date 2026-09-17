# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T036 — the shipped network map cannot install a topology (FR-024, SC-014).

``etc/cuems/network_map.xml`` is a conffile shipped onto every host. An operator
who takes the maintainer's version at the conffile prompt — or a host whose copy
was never modified, which dpkg replaces without asking — gets exactly this file.
It must therefore describe no nodes: an empty topology is recoverable and loud,
a placeholder controller at an address nothing answers is silently wrong.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED = REPO_ROOT / "etc" / "cuems" / "network_map.xml"
SCHEMA = REPO_ROOT / "etc" / "cuems" / "network_map.xsd"


def test_shipped_map_is_schema_valid():
    schema = etree.XMLSchema(etree.parse(str(SCHEMA)))
    doc = etree.parse(str(SHIPPED))
    assert schema.validate(doc), schema.error_log


def test_shipped_map_declares_no_nodes():
    doc = etree.parse(str(SHIPPED))
    assert doc.getroot().findall(".//node") == []
