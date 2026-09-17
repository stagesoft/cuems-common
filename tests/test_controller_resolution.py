# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
"""T050 — the three tools resolve the controller's IP from a converted map.

Each tool's ``network_map.xml`` path is a hardcoded constant (an
ExecStartPre/operator tool, not a library — no config injection point), so
each is exercised by monkeypatching that constant (the two Python scripts)
or by running its embedded lookup logic against a redirected ``NETWORK_MAP``
env var (``cuems-logs``, a bash script with an embedded Python heredoc).
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CONVERTED_MAP = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<node_list>"
    "<node><uuid>0367f391-ebf4-48b2-9f26-000000000001</uuid><mac>2cf05d21cca3</mac>"
    "<name>controller-node</name><node_role>controller</node_role>"
    "<ip>192.168.1.10</ip><adopted>True</adopted><online>True</online></node>"
    "<node><uuid>0367f391-ebf4-48b2-9f26-000000000002</uuid><mac>aabbccddeeff</mac>"
    "<name>a-node</name><node_role>node</node_role>"
    "<ip>192.168.1.11</ip><adopted>True</adopted><online>True</online></node>"
    "</node_list></cms:CuemsNetworkMap>"
)


NO_CONTROLLER_MAP = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<node_list/>"
    "</cms:CuemsNetworkMap>"
)


def _load(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_cuems_write_chrony_source_finds_the_controller_ip(tmp_path, monkeypatch):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(CONVERTED_MAP)

    module = _load("cuems_write_chrony_source", REPO_ROOT / "scripts" / "cuems-write-chrony-source")
    monkeypatch.setattr(module, "NETWORK_MAP", fixture)
    assert module.read_master_ip() == "192.168.1.10"


def test_cuems_log_collector_url_finds_the_controller_ip(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(CONVERTED_MAP)
    env_file = tmp_path / "url.env"

    module = _load("cuems_log_collector_url", REPO_ROOT / "scripts" / "cuems-log-collector-url")
    monkeypatch.setattr(module, "NETWORK_MAP", fixture)
    monkeypatch.setattr(module, "ENV_FILE", env_file)
    module.main([])
    assert env_file.read_text() == "URL=http://192.168.1.10:19532\n"


def _cuems_logs_heredoc_body() -> str:
    """The embedded Python block that lists nodes (the second ``<<'PY'``),
    extracted from the real script so this test cannot drift from what
    actually ships."""
    text = (REPO_ROOT / "usr" / "bin" / "cuems-logs").read_text()
    blocks = re.findall(r"<<'PY'\n(.*?)\nPY", text, re.S)
    assert len(blocks) == 2, "expected two heredocs in cuems-logs; extraction logic may be stale"
    # The second is the node-listing block (the first handles -n resolution).
    return blocks[1]


def test_cuems_logs_node_listing_identifies_the_controller(tmp_path):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(CONVERTED_MAP)

    result = subprocess.run(
        [sys.executable, "-c", _cuems_logs_heredoc_body()],
        env={"NETWORK_MAP": str(fixture), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "controller" in result.stdout
    assert "node_type" not in result.stdout
    assert "NodeType." not in result.stdout
    # Exactly one controller in the fixture — the multi-controller warning
    # must not fire.
    assert "WARNING" not in result.stdout


# -- T038: a map that names no controller warns, it does not fail (FR-025, SC-015)


def test_chrony_source_warns_and_removes_its_source_when_no_controller(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(NO_CONTROLLER_MAP)
    template = tmp_path / "chrony-client.conf.template"
    template.write_text("# client\n")
    sources = tmp_path / "sources.d" / "cuems-master.sources"
    sources.parent.mkdir()
    sources.write_text("server 192.168.1.10 iburst minpoll 4 maxpoll 6\n")

    module = _load("cuems_write_chrony_source_nc", REPO_ROOT / "scripts" / "cuems-write-chrony-source")
    monkeypatch.setattr(module, "NETWORK_MAP", fixture)
    monkeypatch.setattr(module, "MASTER_MARKER", tmp_path / "master.ip")  # absent: node role
    monkeypatch.setattr(module, "CLIENT_TEMPLATE", template)
    monkeypatch.setattr(module, "CUEMS_CONF", tmp_path / "conf.d" / "cuems.conf")
    monkeypatch.setattr(module, "SOURCES_FILE", sources)

    module.main()  # returns normally: exit status 0

    err = capsys.readouterr().err
    assert "WARNING" in err and str(fixture) in err
    assert not sources.exists()
    assert (tmp_path / "conf.d" / "cuems.conf").read_text() == "# client\n"


def test_chrony_source_still_errors_on_a_missing_map(tmp_path, monkeypatch):
    module = _load("cuems_write_chrony_source_missing", REPO_ROOT / "scripts" / "cuems-write-chrony-source")
    monkeypatch.setattr(module, "NETWORK_MAP", tmp_path / "absent.xml")
    with pytest.raises(SystemExit) as exc:
        module.read_master_ip()
    assert exc.value.code != 0


def test_log_collector_url_warns_and_writes_nothing_when_no_controller(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(NO_CONTROLLER_MAP)
    env_file = tmp_path / "url.env"

    module = _load("cuems_log_collector_url_nc", REPO_ROOT / "scripts" / "cuems-log-collector-url")
    monkeypatch.setattr(module, "NETWORK_MAP", fixture)
    monkeypatch.setattr(module, "ENV_FILE", env_file)

    module.main([])  # returns normally: exit status 0

    err = capsys.readouterr().err
    assert "WARNING" in err and str(fixture) in err
    assert not env_file.exists()


@pytest.mark.parametrize("document,expected", [(NO_CONTROLLER_MAP, 1), (CONVERTED_MAP, 0)])
def test_log_collector_url_check_mode(tmp_path, monkeypatch, capsys, document, expected):
    fixture = tmp_path / "network_map.xml"
    fixture.write_text(document)
    env_file = tmp_path / "url.env"

    module = _load("cuems_log_collector_url_check", REPO_ROOT / "scripts" / "cuems-log-collector-url")
    monkeypatch.setattr(module, "NETWORK_MAP", fixture)
    monkeypatch.setattr(module, "ENV_FILE", env_file)

    with pytest.raises(SystemExit) as exc:
        module.main(["--check"])
    assert exc.value.code == expected
    assert not env_file.exists()  # --check only reads
    if expected == 1:
        assert "WARNING" in capsys.readouterr().err
