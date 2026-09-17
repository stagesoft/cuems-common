# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T007 — every literal reference to a discovery template resolves (FR-003, FR-003a, FR-003b).

A template's filename is part of its interface: privileged ``cp`` rules and
``cuems-config-node`` name it literally, and sudoers matches a command
string exactly. A rename that misses one consumer revokes a privilege or
breaks a tool, silently. This test makes a half-landed rename a failing test.

It also pins how the privilege was moved: the role-flip rules live in a
sudoers file that had never been shipped before (so a locally modified old
file cannot block them), and the old file is retired whole in all three
maintainer scripts.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "usr" / "share" / "cuems"
SUDOERS_DIR = REPO_ROOT / "etc" / "sudoers.d"
NEW_SUDOERS = SUDOERS_DIR / "99-cuems-avahi"
OLD_SUDOERS = "etc/sudoers.d/99-cuems"

SHIPPED_TEMPLATES = sorted(p.name for p in TEMPLATE_DIR.glob("cuems.service.*"))
TEMPLATE_REF = re.compile(r"cuems\.service\.[a-z]+")


def test_the_shipped_templates_are_exactly_the_pinned_three():
    assert SHIPPED_TEMPLATES == [
        "cuems.service.controller",
        "cuems.service.firstrun",
        "cuems.service.node",
    ]


def test_every_sudoers_reference_names_an_existing_template():
    for rules in sorted(SUDOERS_DIR.iterdir()):
        for ref in TEMPLATE_REF.findall(rules.read_text(encoding="utf-8")):
            assert ref in SHIPPED_TEMPLATES, f"{rules.name} names missing template {ref}"


def test_config_node_names_only_existing_templates():
    text = (REPO_ROOT / "usr" / "bin" / "cuems-config-node").read_text(encoding="utf-8")
    listed = re.search(r"service_files\s*=\s*\[(.*?)\]", text, re.S).group(1)
    refs = TEMPLATE_REF.findall(listed)
    assert sorted(refs) == SHIPPED_TEMPLATES


def test_new_sudoers_file_carries_every_rule_the_old_one_did():
    rules = NEW_SUDOERS.read_text(encoding="utf-8")
    assert "cuems ALL=(root) NOPASSWD: /bin/systemctl reload avahi-daemon.service" in rules
    for template in SHIPPED_TEMPLATES:
        assert (
            f"cuems ALL=(root) NOPASSWD: /usr/bin/cp /usr/share/cuems/{template} "
            "/etc/avahi/services/cuems.service"
        ) in rules, f"no cp rule for {template}"


def test_new_sudoers_name_is_one_sudo_will_read():
    # sudo's #includedir skips names ending in '~' or containing a '.'.
    assert "." not in NEW_SUDOERS.name and not NEW_SUDOERS.name.endswith("~")


def test_old_sudoers_file_is_retired_whole():
    install = (REPO_ROOT / "debian" / "install").read_text(encoding="utf-8")
    assert not (REPO_ROOT / OLD_SUDOERS).exists()
    assert not re.search(rf"^{re.escape(OLD_SUDOERS)}\s", install, re.M)
    assert re.search(r"^etc/sudoers\.d/99-cuems-avahi\s", install, re.M)
    for script in ("preinst", "postinst", "postrm"):
        text = (REPO_ROOT / "debian" / script).read_text(encoding="utf-8")
        assert re.search(
            r"dpkg-maintscript-helper rm_conffile\s+\\?\s*/etc/sudoers\.d/99-cuems\s+\S+~\s+cuems-common",
            text,
        ), f"debian/{script} lacks the rm_conffile for /etc/sudoers.d/99-cuems"
