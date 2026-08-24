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


# -- T047: the .dpkg-new / .dpkg-dist sibling --------------------------------


def test_conversion_works_on_a_dpkg_new_sibling_path(netmap_file):
    """convert() is path-agnostic — a .dpkg-new suffix is just part of the
    path string, so the same conversion logic applies unmodified. This is
    what makes postinst's "run the script on both candidate paths" strategy
    (debian/postinst) sufficient without a special case in the script."""
    path = netmap_file(name="network_map.xml.dpkg-new")
    outcome = migrate.convert(str(path))
    assert outcome.status == "converted"
    assert "<node_role>controller</node_role>" in path.read_text()


def test_postinst_converts_both_the_live_file_and_its_dpkg_new_sibling(tmp_path):
    """Simulates postinst's loop: both /etc/cuems/network_map.xml and a
    .dpkg-new sibling present at once (an operator kept local modifications
    at the prompt, leaving the packaged default proposed alongside it) are
    each converted independently."""
    live = tmp_path / "network_map.xml"
    live.write_text(_doc("0367f391-ebf4-48b2-9f26-000000000001", "NodeType.master"))
    dpkg_new = tmp_path / "network_map.xml.dpkg-new"
    dpkg_new.write_text(_doc("0367f391-ebf4-48b2-9f26-000000000002", "NodeType.slave"))

    for candidate in (live, dpkg_new):
        if candidate.exists():
            migrate.convert(str(candidate))

    assert "<node_role>controller</node_role>" in live.read_text()
    assert "<node_role>node</node_role>" in dpkg_new.read_text()


def test_postinst_loop_is_a_noop_when_no_dpkg_new_sibling_exists(tmp_path):
    """The common case — no conffile prompt happened, so only the live file
    exists. postinst's `[ -f "$f" ]` guard (debian/postinst) must not fail
    or fabricate a .dpkg-new outcome."""
    live = tmp_path / "network_map.xml"
    live.write_text(_doc("0367f391-ebf4-48b2-9f26-000000000001", "NodeType.master"))
    dpkg_new = tmp_path / "network_map.xml.dpkg-new"
    assert not dpkg_new.exists()

    results = []
    for candidate in (live, dpkg_new):
        if candidate.exists():
            results.append(migrate.convert(str(candidate)))
    assert len(results) == 1
    assert results[0].status == "converted"


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
