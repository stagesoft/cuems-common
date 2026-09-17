# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T006 — the live discovery-file migration (FR-004 to FR-007b, SC-005, SC-006, SC-010).

Exercises ``usr/bin/cuems-migrate-avahi-service`` directly, imported by path
(it has no ``.py`` extension). Covers the four cases the constitution owes
every conversion — happy path, idempotence, whole-file refusal, backup
fidelity — plus this migration's own: byte preservation of a hand-edited file,
absent and unreadable files, and an exit status that never fails an upgrade.

Pre-migration inputs live in ``tests/fixtures/avahi/``: byte-exact copies of
the templates as hosts carry them before the cutover.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "avahi"
_SCRIPT = REPO_ROOT / "usr" / "bin" / "cuems-migrate-avahi-service"

_loader = SourceFileLoader("cuems_migrate_avahi_service", str(_SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
migrate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = migrate
_loader.exec_module(migrate)


@pytest.fixture
def live(tmp_path):
    """Place a fixture where a host's live file would be, return its path."""

    def _place(fixture: str) -> Path:
        dest = tmp_path / "cuems.service"
        shutil.copyfile(FIXTURES / fixture, dest)
        return dest

    return _place


def _backups(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.name}.*.bak"))


# -- happy path --------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture,old,new",
    [
        ("pristine-master.xml", b"node_type=master", b"node_role=controller"),
        ("pristine-slave.xml", b"node_type=slave", b"node_role=node"),
        ("pristine-firstrun.xml", b"node_type=firstrun", b"node_role=firstrun"),
    ],
)
def test_pristine_file_is_rewritten_key_and_value_only(live, fixture, old, new):
    path = live(fixture)
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    assert outcome.status == "converted"
    assert outcome.records_converted == 2
    assert path.read_bytes() == original.replace(old, new)
    assert b"node_type" not in path.read_bytes()


def test_hand_edited_file_keeps_every_other_byte(live):
    path = live("hand-edited-master.xml")
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    assert outcome.status == "converted"
    # Comments, reordered elements, tabs, trailing whitespace and the extra
    # venue record all survive exactly.
    assert path.read_bytes() == original.replace(b"node_type=master", b"node_role=controller")


def test_crlf_line_endings_are_preserved(tmp_path):
    path = tmp_path / "cuems.service"
    original = (FIXTURES / "pristine-slave.xml").read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(original)

    assert migrate.migrate(str(path)).status == "converted"
    assert path.read_bytes() == original.replace(b"node_type=slave", b"node_role=node")


def test_uuid_and_role_are_preserved(live):
    path = live("pristine-master.xml")
    uuid_lines = [l for l in path.read_bytes().splitlines() if b"uuid=" in l]

    migrate.migrate(str(path))

    assert [l for l in path.read_bytes().splitlines() if b"uuid=" in l] == uuid_lines
    assert path.read_bytes().count(b"node_role=controller") == 2


# -- idempotence -------------------------------------------------------------

def test_second_run_rewrites_nothing_and_writes_no_backup(live):
    path = live("pristine-master.xml")
    migrate.migrate(str(path))
    after_first = path.read_bytes()
    backups_after_first = _backups(path)

    outcome = migrate.migrate(str(path))

    assert outcome.status == "already_current"
    assert path.read_bytes() == after_first
    assert _backups(path) == backups_after_first
    assert "already" in outcome.render()


@pytest.mark.parametrize("fixture", ["already-migrated-controller.xml", "unrelated.txt"])
def test_file_without_the_retired_key_is_left_alone(live, fixture):
    path = live(fixture)
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    assert outcome.status == "already_current"
    assert path.read_bytes() == original
    assert _backups(path) == []


# -- whole-file refusal ------------------------------------------------------

@pytest.mark.parametrize(
    "fixture,offending",
    [
        ("refuse-unknown-value.xml", "bogus"),
        # One record maps, the other does not: never half-converted.
        ("refuse-inconsistent.xml", "wrong"),
    ],
)
def test_unrecognised_value_refuses_the_whole_file(live, fixture, offending):
    path = live(fixture)
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    assert outcome.status == "refused"
    assert path.read_bytes() == original
    assert _backups(path) == []
    rendered = outcome.render()
    assert offending in rendered
    for accepted in ("master", "slave", "firstrun"):
        assert accepted in rendered
    assert str(path) in rendered


def test_retired_key_in_an_unmatched_shape_is_refused(live):
    path = live("refuse-unmatched-shape.xml")
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    assert outcome.status == "refused"
    assert path.read_bytes() == original
    assert _backups(path) == []
    assert str(path) in outcome.render()


# -- backup fidelity ---------------------------------------------------------

def test_backup_reproduces_the_original_bytes_and_is_not_a_service_file(live):
    path = live("hand-edited-master.xml")
    original = path.read_bytes()

    outcome = migrate.migrate(str(path))

    backup = Path(outcome.backup_path)
    assert backup.read_bytes() == original
    # avahi-daemon loads every *.service file in its directory.
    assert not backup.name.endswith(".service")
    assert backup in _backups(path)


def test_backups_are_pruned_to_the_newest_five(live):
    path = live("pristine-master.xml")
    for i in range(7):
        (path.parent / f"{path.name}.2020010{i}T000000Z.bak").write_bytes(b"old")

    outcome = migrate.migrate(str(path))

    remaining = _backups(path)
    assert len(remaining) == 5
    assert Path(outcome.backup_path) in remaining


# -- absent / unreadable -----------------------------------------------------

def test_absent_file_is_reported_and_not_created(tmp_path):
    path = tmp_path / "cuems.service"

    outcome = migrate.migrate(str(path))

    assert outcome.status == "absent"
    assert not path.exists()
    assert str(path) in outcome.render()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a mode-000 file")
def test_unreadable_file_is_left_untouched_and_reported(live):
    path = live("pristine-master.xml")
    path.chmod(0)
    try:
        outcome = migrate.migrate(str(path))
    finally:
        path.chmod(0o644)

    assert outcome.status == "refused"
    assert str(path) in outcome.render()
    assert b"node_type=master" in path.read_bytes()


# -- never fails the upgrade -------------------------------------------------

@pytest.mark.parametrize(
    "fixture",
    sorted(p.name for p in FIXTURES.iterdir()) + ["<absent>"],
)
def test_main_always_exits_zero(tmp_path, fixture, capsys):
    path = tmp_path / "cuems.service"
    if fixture != "<absent>":
        shutil.copyfile(FIXTURES / fixture, path)

    assert migrate.main([str(path)]) == 0
    assert str(path) in capsys.readouterr().out
