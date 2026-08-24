# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""M2 — the mirrored schema is byte-identical to cuems-utils's copy.

They have drifted before (measured during T051: this repository's copy
predated feature 007 with a different NodeDictType/NodeListType spelling and
a still-present PutType) — this test is what makes a future drift a failing
test instead of a silent divergence discovered on a node running
`xmllint --schema`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MIRROR = REPO_ROOT / "etc" / "cuems" / "network_map.xsd"

#: Sibling checkout — this repository and cuems-utils are developed together
#: (see specs/007-node-model-migration/migration-guide.md), so the canonical
#: copy is reachable at a fixed relative path in this development layout.
#: Skips rather than fails when the sibling isn't present (e.g. a CI checkout
#: of this repository alone) — M2 is then unverifiable, not violated.
CANONICAL = REPO_ROOT.parent / "cuems-utils" / "src" / "cuemsutils" / "xml" / "schemas" / "network_map.xsd"


def test_mirror_exists():
    assert MIRROR.is_file()


@pytest.mark.skipif(not CANONICAL.is_file(), reason="cuems-utils sibling checkout not found")
def test_mirror_is_byte_identical_to_the_canonical_schema():
    assert MIRROR.read_bytes() == CANONICAL.read_bytes()
