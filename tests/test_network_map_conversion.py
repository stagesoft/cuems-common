# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""M3 — the shipped conversion script (T047, T048).

Exercises ``usr/bin/cuems-migrate-network-map`` directly (imported via path,
since it has no ``.py`` extension and is not a package). The core behaviour
(both legacy spellings, refusal, backup/restore, idempotence, positive
evidence) is ported near-verbatim from ``cuems-utils``'s reference
implementation and its test suite — this is the same code, relocated
(T054's commit) rather than rewritten, so the same tests apply.

Run with:

    pyenv exec python -m pytest tests/ -v
"""

from __future__ import annotations

import importlib.util
import re
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = REPO_ROOT / "usr" / "bin" / "cuems-migrate-network-map"

# The script has no .py extension (it's a usr/bin/ entry point, not a
# package) so spec_from_file_location can't infer a loader from the
# extension alone — passed explicitly instead.
_loader = SourceFileLoader("cuems_migrate_network_map", str(_SCRIPT_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
migrate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = migrate
_loader.exec_module(migrate)


def _doc(uuid: str, node_type: str) -> str:
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="https://stagelab.coop/cuems/ network_map.xsd">'
        "<node_list><node>"
        f"<uuid>{uuid}</uuid><mac>2cf05d21cca3</mac><name>n</name>"
        f"<node_type>{node_type}</node_type><ip>192.168.1.10</ip>"
        "<adopted>True</adopted><online>True</online>"
        "</node></node_list></cms:CuemsNetworkMap>"
    )


@pytest.fixture
def netmap_file(tmp_path):
    def _make(node_type: str = "NodeType.master", uuid: str = "0367f391-ebf4-48b2-9f26-000000000001", name: str = "network_map.xml"):
        path = tmp_path / name
        path.write_text(_doc(uuid, node_type))
        return path

    return _make


@pytest.mark.parametrize(
    "spelling,expected_role",
    [
        ("NodeType.master", "controller"),
        ("master", "controller"),
        ("NodeType.slave", "node"),
        ("slave", "node"),
        ("NodeType.firstrun", "firstrun"),
        ("firstrun", "firstrun"),
    ],
)
def test_both_legacy_spellings_convert(netmap_file, spelling, expected_role):
    path = netmap_file(node_type=spelling)
    outcome = migrate.convert(str(path))
    assert outcome.status == "converted"
    after = path.read_text()
    assert f"<node_role>{expected_role}</node_role>" in after
    assert "<node_type>" not in after


def test_absent_file(tmp_path):
    outcome = migrate.convert(str(tmp_path / "network_map.xml"))
    assert outcome.status == "absent"


def test_idempotent(netmap_file):
    path = netmap_file()
    migrate.convert(str(path))
    once = path.read_text()
    second = migrate.convert(str(path))
    assert second.status == "already_converted"
    assert path.read_text() == once


def test_unrecognised_value_refuses_whole_file(netmap_file):
    path = netmap_file(node_type="gibberish")
    before = path.read_text()
    outcome = migrate.convert(str(path))
    assert outcome.status == "refused"
    assert path.read_text() == before


def test_backup_precedes_write_and_restores_exact_bytes(netmap_file):
    path = netmap_file()
    before = path.read_text()
    outcome = migrate.convert(str(path))
    backup = Path(outcome.backup_path)
    assert backup.exists()
    assert backup.read_text() == before


def test_all_four_outcomes_are_distinguishable(netmap_file, tmp_path):
    converted = migrate.convert(str(netmap_file(name="a.xml")))
    already_path = netmap_file(name="b.xml")
    migrate.convert(str(already_path))
    already = migrate.convert(str(already_path))
    absent = migrate.convert(str(tmp_path / "missing.xml"))
    refused = migrate.convert(str(netmap_file(name="c.xml", node_type="nonsense")))

    statuses = {converted.status, already.status, absent.status, refused.status}
    assert statuses == {"converted", "already_converted", "absent", "refused"}
    renders = {converted.render(), already.render(), absent.render(), refused.render()}
    assert len(renders) == 4


# -- T047 / feature 001 FR-027: the copies dpkg really leaves ---------------
#
# dpkg resolves a conffile prompt BEFORE postinst runs. Keep-local leaves the
# maintainer's version at <file>.dpkg-dist; take-maintainer moves the
# operator's own map to <file>.dpkg-old. A .dpkg-new exists only while
# unpacking, never when postinst runs — the loop used to wait for it.

DPKG_COPIES = ("network_map.xml", "network_map.xml.dpkg-dist", "network_map.xml.dpkg-old")


def _postinst_loop(tmp_path: Path):
    outcomes = {}
    for name in DPKG_COPIES:
        candidate = tmp_path / name
        if candidate.exists():
            outcomes[name] = migrate.convert(str(candidate))
    return outcomes


def test_conversion_works_on_the_dpkg_old_copy(netmap_file):
    """Take-maintainer: the operator's real topology sits at .dpkg-old and must
    be converted, so restoring it is a copy rather than a conversion."""
    path = netmap_file(name="network_map.xml.dpkg-old")
    outcome = migrate.convert(str(path))
    assert outcome.status == "converted"
    assert "<node_role>controller</node_role>" in path.read_text()


def test_postinst_loop_converts_all_three_copies(tmp_path):
    for i, name in enumerate(DPKG_COPIES, 1):
        (tmp_path / name).write_text(_doc(f"0367f391-ebf4-48b2-9f26-00000000000{i}", "NodeType.master"))

    outcomes = _postinst_loop(tmp_path)

    assert set(outcomes) == set(DPKG_COPIES)
    for name in DPKG_COPIES:
        assert "<node_role>controller</node_role>" in (tmp_path / name).read_text()


@pytest.mark.parametrize("present", [("network_map.xml",), ("network_map.xml", "network_map.xml.dpkg-old")])
def test_postinst_loop_is_a_noop_for_absent_copies(tmp_path, present):
    for name in present:
        (tmp_path / name).write_text(_doc("0367f391-ebf4-48b2-9f26-000000000001", "NodeType.master"))

    outcomes = _postinst_loop(tmp_path)

    assert set(outcomes) == set(present)
    assert all(o.status == "converted" for o in outcomes.values())
    for name in set(DPKG_COPIES) - set(present):
        assert not (tmp_path / name).exists()


def test_debian_postinst_loop_names_exactly_those_three_paths():
    text = (REPO_ROOT / "debian" / "postinst").read_text(encoding="utf-8")
    loop = re.search(
        r"^\s*for f in (.*?); do\s*\n\s*\[ -f \"\$f\" \] && /usr/bin/cuems-migrate-network-map",
        text,
        re.M,
    )
    assert loop, "network-map conversion loop not found in debian/postinst"
    assert loop.group(1).split() == [f"/etc/cuems/{name}" for name in DPKG_COPIES]


# -- T048: absent, already-converted, unparseable never fail the upgrade -----


def test_absent_exits_zero_via_main(tmp_path):
    rc = migrate.main([str(tmp_path / "missing.xml")])
    assert rc == 0


def test_already_converted_exits_zero_via_main(netmap_file):
    path = netmap_file()
    migrate.main([str(path)])
    rc = migrate.main([str(path)])
    assert rc == 0


def test_unparseable_content_is_treated_as_already_converted(tmp_path):
    """Not valid XML at all (corrupt file). The script's contract only
    looks for the literal ``<node_type>`` substring — it has no XML parser
    to fail, so garbage without that substring is indistinguishable from an
    already-converted file, and the upgrade proceeds (M3: never fails)."""
    path = tmp_path / "network_map.xml"
    path.write_text("this is not xml at all {{{")
    rc = migrate.main([str(path)])
    assert rc == 0
    outcome = migrate.convert(str(path))
    assert outcome.status == "already_converted"


def test_refusal_exits_zero_via_main(netmap_file):
    path = netmap_file(node_type="gibberish")
    rc = migrate.main([str(path)])
    assert rc == 0
