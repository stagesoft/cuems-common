# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""cuems-utils feature 011, FR-040a (research R7, shape B): cuems-config-node
is no longer a uuid minter and touches neither settings.xml's identity nor the
Avahi templates; the templates ship with the sentinel uuid."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "usr" / "bin" / "cuems-config-node"
SENTINEL = "00000000-0000-0000-0000-000000000000"


def _code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def test_config_node_mints_nothing():
    code = _code(TOOL.read_text(encoding="utf-8"))
    assert not re.search(r"uuid[145]\(|from uuid import|import uuid", code)


def test_config_node_writes_no_settings_xml_and_no_avahi_template():
    code = _code(TOOL.read_text(encoding="utf-8"))
    assert "/etc/cuems/settings.xml" not in code
    assert "cuems.service" not in code
    assert "txt-record" not in code


def test_shipped_templates_carry_the_sentinel_only():
    for role in ("firstrun", "controller", "node"):
        text = (REPO_ROOT / "usr/share/cuems" / f"cuems.service.{role}").read_text(encoding="utf-8")
        uuids = set(re.findall(r"uuid=([0-9a-f-]{36})", text))
        assert uuids == {SENTINEL}, (role, uuids)
