# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""The custody transfer of /etc/cuems/network_map.{xml,xsd} to cuems-utils
(1.3.0-23; cuems-utils feature 011, research R3, contract
cuems-common-handover.md §1). Pins the recipe rather than describing it."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEBIAN = REPO_ROOT / "debian"
PATHS = ("/etc/cuems/network_map.xml", "/etc/cuems/network_map.xsd")


def test_neither_path_is_shipped_any_more():
    install = (DEBIAN / "install").read_text(encoding="utf-8")
    code = [l.split("#", 1)[0] for l in install.splitlines()]
    assert not any(re.match(r"^etc/cuems/network_map\.(xml|xsd)\s", l) for l in code)
    assert not (REPO_ROOT / "etc/cuems/network_map.xsd").exists()
    assert not (REPO_ROOT / "etc/cuems/network_map.xml").exists()
    assert (REPO_ROOT / "etc/cuems/network_map.xml.example").exists(), "the documentation example stays"


def test_all_three_scripts_run_rm_conffile_for_both_paths():
    for name in ("preinst", "postinst", "postrm"):
        text = (DEBIAN / name).read_text(encoding="utf-8")
        assert "rm_conffile" in text, name
        for path in PATHS:
            assert path in text, f"{name} does not name {path}"
        assert "1.3.0-23~" in text, f"{name}: prior-version must be 1.3.0-23~"


def test_preinst_snapshots_the_live_map_before_the_move():
    text = (DEBIAN / "preinst").read_text(encoding="utf-8")
    snapshot = text.index("cuems-common.network_map.xml.presave")
    move = text.index('rm_conffile "$_cf" 1.3.0-23~')
    assert snapshot < move, "the snapshot must precede rm_conffile"


def test_postinst_restores_then_converts():
    text = (DEBIAN / "postinst").read_text(encoding="utf-8")
    restore = text.index("cuems-common.network_map.xml.presave")
    reinstall = text.index("/usr/share/cuems/schemas/network_map.xsd")
    convert = text.index("cuems-migrate-network-map \"$f\"")
    assert restore < convert and reinstall < convert, "the map must be back before the conversion loop"
    assert "cmp -s /etc/cuems/network_map.xml.dpkg-bak" in text, "only an identical .dpkg-bak is removed"
