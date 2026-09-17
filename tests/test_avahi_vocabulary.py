# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T005 — the Avahi discovery vocabulary cannot be silently reverted (FR-002, FR-011, SC-002).

Three checks, from narrowest to widest:

1. Every shipped template, and the in-repo copy of the live file, carries the
   new key in **both** service types — so a deleted record fails instead of
   passing as "no retired key found".
2. A retired TXT record (``node_type=master|slave|firstrun``, or ``node_type=``
   inside a ``<txt-record>``) appears only in the files that exist to convert
   it or to document the conversion — enumerated below, one reason each, never
   matched by pattern.
3. Operator-facing prose (README, CLAUDE.md, docs/) never describes the TXT
   record by its retired name.

The ``<node_type>`` *XML element* of ``network_map.xml`` is feature 007's
vocabulary, converted by ``cuems-migrate-network-map``; it is not this test's
subject.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

TEMPLATES = {
    "usr/share/cuems/cuems.service.firstrun": "firstrun",
    "usr/share/cuems/cuems.service.controller": "controller",
    "usr/share/cuems/cuems.service.node": "node",
    # The in-repo copy of a controller's live file. Not shipped (FR-004), but
    # the repository must not contradict the hosts.
    "etc/avahi/services/cuems.service": "controller",
}

SERVICE_TYPES = ("_cuems_nodeconf._tcp", "_cuems_osc._tcp")

#: Files allowed to contain the retired TXT form ``node_type=``, each with the
#: reason it is allowed. Anything else carrying it fails the test.
RETIRED_TXT_KEY_ALLOWED = {
    "usr/bin/cuems-migrate-avahi-service": "the migration that converts it",
    "tests/test_avahi_live_migration.py": "tests the migration",
    "tests/test_avahi_vocabulary.py": "this test",
    "debian/changelog": "records the rename",
    "docs/node-identity-contract.md": "documents the renamed record and its migration",
}
RETIRED_TXT_KEY_ALLOWED_DIRS = {
    "tests/fixtures/avahi/": "pre-migration inputs to the migration tests",
    "specs/": "feature specifications describing the cutover",
    "dev/planning/": "planning documents describing the cutover",
}

#: Directories that are not part of what this repository ships or owns.
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".specify", ".claude", "debian/cuems-common", "debian/.debhelper"}

#: An actual retired record: a retired value after the key, or the key inside a
#: <txt-record>. Deliberately not bare "node_type=", which also matches Python
#: keyword arguments and prose that names the key while describing its removal.
RETIRED_TXT_KEY = re.compile(rb"\bnode_type=(?:master|slave|firstrun)\b|<txt-record>node_type=")
PROSE_FILES = ("README.md", "CLAUDE.md")
PROSE_DIRS = ("docs/",)
#: A line that describes a TXT record by the retired key name.
RETIRED_KEY_IN_TXT_PROSE = re.compile(r"`node_type`[^\n]*TXT|TXT[^\n]*`node_type`", re.I)


def _repo_files():
    for path in sorted(REPO_ROOT.rglob("*")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.is_file():
            yield rel, path


@pytest.mark.parametrize("rel,role", sorted(TEMPLATES.items()))
def test_template_carries_the_new_key_in_both_service_types(rel, role):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    services = re.findall(r"<service\b.*?</service>", text, re.S)
    found_types = {re.search(r"<type>(.*?)</type>", s).group(1) for s in services}
    assert found_types == set(SERVICE_TYPES), f"{rel}: expected both service types"
    for service in services:
        assert f"<txt-record>node_role={role}</txt-record>" in service, (
            f"{rel}: a service is missing <txt-record>node_role={role}</txt-record>"
        )
        assert re.search(r"<txt-record>uuid=[^<]+</txt-record>", service), f"{rel}: uuid record missing"
    assert "node_type" not in text, f"{rel}: still carries the retired key"


def test_retired_templates_are_gone():
    for old in ("usr/share/cuems/cuems.service.master", "usr/share/cuems/cuems.service.slave"):
        assert not (REPO_ROOT / old).exists(), f"{old} should have been renamed"


def test_retired_txt_key_appears_only_where_it_is_converted_or_documented():
    offenders = []
    for rel, path in _repo_files():
        if rel in RETIRED_TXT_KEY_ALLOWED:
            continue
        if any(rel.startswith(d) for d in RETIRED_TXT_KEY_ALLOWED_DIRS):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if RETIRED_TXT_KEY.search(data):
            offenders.append(rel)
    assert offenders == [], f"retired TXT record found in: {offenders}"


def test_operator_prose_does_not_describe_the_txt_record_by_its_retired_name():
    offenders = []
    for rel, path in _repo_files():
        if not (rel in PROSE_FILES or any(rel.startswith(d) for d in PROSE_DIRS)):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if RETIRED_KEY_IN_TXT_PROSE.search(line):
                offenders.append(f"{rel}:{lineno}")
    assert offenders == [], f"prose still names the TXT record node_type: {offenders}"
