# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""The one rule for "where is the controller", and the two helpers that use it."""

import importlib.machinery
import importlib.util
import pathlib
import socket

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


def load(name, rel):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / rel))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ca = load('cuems_controller_address', 'usr/lib/cuems/cuems_controller_address.py')


def netmap(tmp_path, master_ip=None):
    entry = (f'<node><uuid>u</uuid><node_type>NodeType.master</node_type><ip>{master_ip}</ip></node>'
             if master_ip is not None else '')
    path = tmp_path / 'network_map.xml'
    path.write_text('<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/"><node_list>'
                    '<node><uuid>me</uuid><node_type>NodeType.slave</node_type>'
                    f'<ip>169.254.0.11</ip></node>{entry}</node_list></cms:CuemsNetworkMap>')
    return path


def names(answer):
    def resolve(name):
        assert name == 'controller.local'
        if answer is None:
            raise socket.gaierror('no such name')
        return answer
    return resolve


def test_the_name_wins_over_the_map(tmp_path):
    """A map that says 127.0.0.1 for the controller made a node log to itself."""
    assert ca.controller_address(netmap(tmp_path, '127.0.0.1'),
                                 names('169.254.0.1')) == '169.254.0.1'


@pytest.mark.parametrize('answer', [None, '127.0.0.1', '127.0.1.1', '0.0.0.0', 'garbage'])
def test_a_name_that_is_no_use_falls_back_to_the_map(tmp_path, answer):
    assert ca.controller_address(netmap(tmp_path, '169.254.7.7'), names(answer)) == '169.254.7.7'


def test_the_map_needs_no_controller_when_the_name_answers(tmp_path):
    assert ca.controller_address(netmap(tmp_path), names('169.254.0.1')) == '169.254.0.1'


def test_nor_does_the_map_need_to_be_there(tmp_path):
    assert ca.controller_address(tmp_path / 'missing.xml', names('169.254.0.1')) == '169.254.0.1'


@pytest.mark.parametrize('make', [
    lambda p: netmap(p), lambda p: netmap(p, ''), lambda p: p / 'missing.xml',
    lambda p: (p / 'bad.xml', (p / 'bad.xml').write_text('<oops'))[0]])
def test_with_neither_it_fails_and_says_both(tmp_path, make):
    with pytest.raises(LookupError) as e:
        ca.controller_address(make(tmp_path), names(None))
    assert 'controller.local' in str(e.value) and '.xml' in str(e.value)


def test_log_upload_uses_the_rule(tmp_path, monkeypatch):
    helper = load('log_collector', 'scripts/cuems-log-collector-url')
    monkeypatch.setattr(helper, 'NETWORK_MAP', netmap(tmp_path))
    monkeypatch.setattr(helper, 'ENV_FILE', tmp_path / 'url.env')
    monkeypatch.setattr(helper.socket, 'gethostbyname', names('169.254.0.1'))
    helper.main()
    assert (tmp_path / 'url.env').read_text() == 'URL=http://169.254.0.1:19532\n'


def test_chrony_uses_the_rule(tmp_path, monkeypatch):
    helper = load('chrony_source', 'scripts/cuems-write-chrony-source')
    template = tmp_path / 'client.conf'
    template.write_text('makestep 1 -1\n')
    monkeypatch.setattr(helper, 'NETWORK_MAP', netmap(tmp_path, '127.0.0.1'))
    monkeypatch.setattr(helper, 'CLIENT_TEMPLATE', template)
    monkeypatch.setattr(helper, 'CUEMS_CONF', tmp_path / 'conf.d' / 'cuems.conf')
    monkeypatch.setattr(helper, 'SOURCES_FILE', tmp_path / 'sources.d' / 'c.sources')
    monkeypatch.setattr(helper.socket, 'gethostbyname', names('169.254.0.1'))
    helper.apply_slave()
    assert (tmp_path / 'sources.d' / 'c.sources').read_text().startswith('server 169.254.0.1 ')


def test_a_helper_with_no_controller_at_all_still_fails_loudly(tmp_path, monkeypatch, capsys):
    helper = load('log_collector_2', 'scripts/cuems-log-collector-url')
    monkeypatch.setattr(helper, 'NETWORK_MAP', netmap(tmp_path))
    monkeypatch.setattr(helper, 'ENV_FILE', tmp_path / 'url.env')
    monkeypatch.setattr(helper.socket, 'gethostbyname', names(None))
    with pytest.raises(SystemExit) as e:
        helper.main()
    assert e.value.code == 1 and 'controller.local' in capsys.readouterr().err
    assert not (tmp_path / 'url.env').exists()


def test_the_package_installs_the_rule_where_the_helpers_look():
    install = (REPO / 'debian/install').read_text()
    assert 'usr/lib/cuems/cuems_controller_address.py usr/lib/cuems/\n' in install
    for rel in ('scripts/cuems-log-collector-url', 'scripts/cuems-write-chrony-source'):
        text = (REPO / rel).read_text()
        assert 'controller_address' in text
        # A root service must not leave a __pycache__ inside the package's tree.
        assert 'sys.dont_write_bytecode = True' in text
