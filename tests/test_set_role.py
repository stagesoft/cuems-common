# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""cuems-set-role on a temporary root.

The cases come from the manual lists that this command replaces. They prove what
is written and which units are switched; that a node then boots, finds its
controller and plays is AC22 and AC23, on rigs.
"""

import importlib.machinery
import importlib.util
import os
import pathlib
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from test_firstboot import BornBox, MINTED, SENTINEL, fb
from test_platform import PROFILES, cp

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / 'usr/bin/cuems-set-role'


def load_tool():
    loader = importlib.machinery.SourceFileLoader('cuems_set_role', str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sr = load_tool()

INTERFACES = 'etc/network/interfaces'
MAP = 'etc/cuems/network_map.xml'
NODE_ADDR = '169.254.0.11'

# What a standalone controller from the image has switched on.
BORN_UNITS = {
    'cuems-node.target': 'enabled',
    'cuems-controller.target': 'enabled',
    'cuems-controller-engine.service': 'enabled',
    'cuems-editor.service': 'enabled',
    'cuems-power-bridge.service': 'enabled',
    'cuems-cluster-poweroff.service': 'enabled',
    'systemd-journal-remote.service': 'enabled',
    'systemd-journal-remote.socket': 'enabled',
    'systemd-journal-upload.service': 'disabled',
    'cuems-nodeconf.service': 'disabled',
}


class Cluster(BornBox):
    """A box after its first boot, with the controller's switches on."""

    def __init__(self, root):
        super().__init__(root)
        self.units = {'cuems-gradient-motiond.service': 'disabled'}
        self.path_active, self.path_stops = False, True
        self.unowned, self.events = set(), []
        self.engine_version = None
        assert fb.first_boot(self.system(), cp, PROFILES, mint=lambda: MINTED, wait=0) == fb.DONE
        for name in ('interfaces.master', 'interfaces.node'):
            self.write(f'usr/share/cuems/{name}', (REPO / 'usr/share/cuems' / name).read_text())
        self.write(INTERFACES, self.read('usr/share/cuems/interfaces.master'))
        self.write('etc/cuems/master.ip', '')
        self.write('etc/cuems/master.lock', '')
        self.write('etc/avahi/avahi-daemon.conf', '[server]\nuse-ipv4=yes\n')
        self.units = dict(BORN_UNITS)
        self.path_active = True
        self.engine_version = '0.1.0rc6-5'
        self.engine_status = 'installed'
        self.calls = []

    def run(self, argv):
        # The first boot's own reboot request goes the plain way.
        if argv[:2] == ['dpkg-query', '-W'] and argv[-1] == 'cuems-engine':
            if not self.engine_version:
                return subprocess.CompletedProcess(argv, 1, '', '')
            # Removed but not purged keeps its version, with another status.
            out = argv[2].replace('-f=', '').replace('${db:Status-Status}', self.engine_status)
            return subprocess.CompletedProcess(
                argv, 0, out.replace('${Version}', self.engine_version), '')
        if argv[:2] == ['dpkg', '--compare-versions']:
            return subprocess.run(argv, capture_output=True, text=True)
        if argv[0] not in ('systemctl', 'dpkg') or argv[1] == '--no-block':
            return super().run(argv)
        self.calls.append(argv)

        def result(code, out=''):
            return subprocess.CompletedProcess(argv, code, out, '')

        if argv[0] == 'dpkg':
            return result(1 if argv[-1] in self.unowned else 0)
        verb, unit = argv[1], argv[-1]
        if verb == 'daemon-reload':
            return result(0)
        if unit == 'cuems-controller.path':
            if verb == 'stop':
                self.events.append(('stop path', self.exists('etc/cuems/master.lock')))
                self.path_active = not self.path_stops
                return result(0)
            if verb == 'is-active':
                return result(0 if self.path_active else 3)
        if verb == 'is-enabled':
            state = self.units.get(unit)
            return result(0 if state == 'enabled' else 1, f'{state}\n' if state else '')
        if verb in self.fail:
            return result(1)
        if verb == 'enable' and self.units.get(unit) == 'masked':
            return result(1)
        self.units[unit] = {'enable': 'enabled', 'disable': 'disabled',
                            'mask': 'masked', 'unmask': 'disabled'}[verb]
        return result(0)

    def role(self, role, **kwargs):
        if role == 'node':
            kwargs.setdefault('address', NODE_ADDR)
        return sr.set_role(self.system(), cp, role, **kwargs)

    def nodes(self):
        tree = ET.fromstring(self.read(MAP).encode())
        return [{c.tag: c.text for c in node} for node in tree.find('node_list')]

    def own(self):
        return next(n for n in self.nodes() if n['uuid'] == MINTED)

    def snapshot(self):
        """Every file under etc, by content."""
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in (self.root / 'etc').rglob('*') if p.is_file()}


@pytest.fixture
def box(tmp_path):
    return Cluster(tmp_path)


def stanza(text, iface):
    """The `iface` line of an interface and the indented lines under it."""
    match = re.search(rf'^iface {iface} .*\n(?:[ \t]+.*\n)*', text, re.M)
    assert match, iface
    return match.group(0)


def pins(box):
    return [line for line in box.read('etc/hosts').splitlines() if 'controller.local' in line]


# --- becoming a node -------------------------------------------------------------

def test_a_node_has_no_role_flags(box):
    box.role('node')
    assert not box.exists('etc/cuems/master.ip')
    assert not box.exists('etc/cuems/master.lock')


def test_a_node_switches_the_controller_units_off_and_masks_its_engine(box):
    box.role('node')
    for unit in ('cuems-controller.target', 'cuems-editor.service', 'cuems-power-bridge.service',
                 'cuems-cluster-poweroff.service', 'systemd-journal-remote.service',
                 'systemd-journal-remote.socket'):
        assert box.units[unit] == 'disabled', unit
    # Masked: installing the engine package again cannot start it.
    assert box.units['cuems-controller-engine.service'] == 'masked'
    assert box.units['cuems-node.target'] == 'enabled'
    assert box.units['systemd-journal-upload.service'] == 'enabled'


def test_a_node_bridges_both_ports_with_its_own_address_and_no_router(box):
    box.role('node')
    text = box.read(INTERFACES)
    bridge = stanza(text, 'bridge0')
    assert bridge.startswith('iface bridge0 inet static\n')
    assert f'address {NODE_ADDR}\n' in bridge and 'netmask 255.255.0.0\n' in bridge
    assert 'bridge_ports ethernet0 ethernet1' in bridge
    assert not re.search(r'^\s*(gateway|dns-nameservers)\b', text, re.M)
    assert 'bond0' not in text


def test_a_node_leaves_the_wifi_down(box):
    box.role('node')
    auto = [line.split()[1:] for line in box.read(INTERFACES).splitlines()
            if line.startswith('auto ')]
    assert ['lo'] in auto and not any('wifi0' in words for words in auto)


def test_the_controller_network_file_is_kept(box):
    before = box.read(INTERFACES)
    box.role('node')
    assert box.read(INTERFACES + sr.KEPT_CONTROLLER) == before


def site_bond(box):
    own = box.read(INTERFACES).replace(
        'iface bond0 inet dhcp\n',
        'iface bond0 inet dhcp\n\thwaddress ether 02:00:00:00:00:09\n')
    box.write(INTERFACES, own)
    return own


def test_there_and_back_keeps_the_sites_bond(box):
    """A round trip must not lose what was set on the controller's bond."""
    site_bond(box)
    box.role('controller')
    before = box.read(INTERFACES)
    box.role('node')
    box.role('node', address='169.254.0.12')
    box.path_active = True
    result = box.role('controller')
    assert box.read(INTERFACES) == before
    assert any(sr.KEPT_CONTROLLER in w for w in result.warnings)


def test_a_second_trip_does_not_lose_the_kept_controller_file(box):
    own = site_bond(box)
    box.role('node')
    box.role('node', address='169.254.0.12')
    assert box.read(INTERFACES + sr.KEPT_CONTROLLER) == own


def test_a_hand_edited_node_file_is_kept(box):
    box.role('node')
    edited = box.read(INTERFACES) + '# by hand\n'
    box.write(INTERFACES, edited)
    box.role('node', address='169.254.0.12')
    assert box.read(INTERFACES + sr.KEPT_NODE) == edited


def test_an_unknown_file_is_kept_once_and_never_overwritten(box):
    box.write(INTERFACES, 'auto eth0\niface eth0 inet dhcp\n')
    box.role('node')
    assert box.read(INTERFACES + sr.KEPT_OTHER) == 'auto eth0\niface eth0 inet dhcp\n'
    box.write(INTERFACES, 'auto eth1\niface eth1 inet dhcp\n')
    box.role('node')
    assert box.read(INTERFACES + sr.KEPT_OTHER) == 'auto eth0\niface eth0 inet dhcp\n'


@pytest.mark.parametrize('controller', ['169.254.0.1', '169.254.7.7'])
def test_a_node_pins_controller_local_to_its_controller(box, controller):
    box.role('node', controller=controller)
    assert pins(box) == [f'{controller}\tcontroller.local\t# cuems-set-role']


def test_a_node_publishes_itself_as_a_node_with_its_own_uuid(box):
    box.role('node')
    record = box.read('etc/avahi/services/cuems.service')
    assert 'node_type=slave' in record and 'node_type=master' not in record
    assert re.findall(r'uuid=([^<]*)', record) == [MINTED]


def test_a_template_that_lost_the_uuid_still_publishes_this_box(box):
    """An upgrade of the package puts the sentinel back in the templates."""
    path = 'usr/share/cuems/cuems.service.slave'
    box.write(path, box.read(path).replace(MINTED, SENTINEL))
    box.role('node')
    assert re.findall(r'uuid=([^<]*)', box.read('etc/avahi/services/cuems.service')) == [MINTED]


def test_the_node_map_gets_no_invented_controller(box):
    """nodeconf accepts on a node only the controller its map lists: an invented
    one would make it ignore the real one."""
    result = box.role('node')
    own = box.own()
    assert (own['node_type'], own['ip'], own['role_id']) == ('NodeType.slave', NODE_ADDR, 'node01')
    assert [n['uuid'] for n in box.nodes()] == [MINTED]
    assert any('not listed' in w and 'controller.local' in w for w in result.warnings)


def test_a_controller_already_listed_gets_the_link_address(box):
    other = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    box.write(MAP, box.read(MAP).replace('</node_list>', f'''    <node>
            <uuid>{other}</uuid>
            <mac>020000000001</mac>
            <name>x</name>
            <node_type>NodeType.master</node_type>
            <ip>127.0.0.1</ip>
            <role_id>controller</role_id>
        </node>
    </node_list>'''))
    box.role('node')
    masters = [n for n in box.nodes() if n['node_type'] == 'NodeType.master']
    assert [(m['uuid'], m['ip']) for m in masters] == [(other, '169.254.0.1')]


@pytest.mark.parametrize('address, role_id', [
    ('169.254.0.11', 'node01'), ('169.254.0.12', 'node02'), ('169.254.0.26', 'node16')])
def test_the_role_id_follows_the_link_address(box, address, role_id):
    box.role('node', address=address)
    assert box.own()['role_id'] == role_id


@pytest.mark.parametrize('address', [None, '', '169.254.0.1', '169.254.0.10', '169.254.0.27',
                                     '192.168.1.20', '169.254.0.011', 'node01'])
def test_only_the_addresses_the_jump_allows_are_accepted(box, address):
    before = box.snapshot()
    with pytest.raises(sr.RoleError):
        box.role('node', address=address)
    assert box.snapshot() == before and box.calls == []


def test_the_accepted_addresses_are_the_ones_the_ssh_jump_ships():
    config = (REPO / 'etc/ssh/sshd_config.d/50-cuems.conf').read_text()
    assert sorted(re.findall(r'(169\.254\.0\.\d+):22', config)) == sorted(sr.NODE_ADDRESSES)


@pytest.mark.parametrize('controller', [NODE_ADDR, '10.1.2.3', 'controller.local', '169.254.0.999'])
def test_a_controller_address_must_be_another_link_local_one(box, controller):
    with pytest.raises(sr.RoleError):
        box.role('node', controller=controller)


def test_an_unowned_rtpmidid_override_is_set_aside(box):
    """A hand-made copy in /etc hides the packaged one, and the role with it."""
    rel = 'etc/systemd/system/rtpmidid.service.d/cuems-node-group.conf'
    box.write(rel, '[Service]\n')
    box.unowned.add('/' + rel)
    box.role('node')
    assert not box.exists(rel) and box.exists(rel + '.cuems-disabled')


def test_an_rtpmidid_file_a_package_owns_stays(box):
    rel = 'etc/systemd/system/rtpmidid.service.d/cuems-node-group.conf'
    box.write(rel, '[Service]\n')
    box.role('node')
    assert box.exists(rel)


# --- becoming a controller --------------------------------------------------------

def test_a_controller_puts_its_link_address_on_the_cluster_port(box):
    box.role('controller')
    cluster = stanza(box.read(INTERFACES), 'ethernet1')
    assert cluster.startswith('iface ethernet1 inet static\n')
    assert 'address 169.254.0.1\n' in cluster and 'netmask 255.255.0.0\n' in cluster
    assert 'wol g' in cluster
    assert stanza(box.read(INTERFACES), 'bond0').startswith('iface bond0 inet dhcp')


def test_a_controller_keeps_the_bond_stanza_the_site_set(box):
    """cuems-net-mode and sites edit bond0; only the cluster port is the role's."""
    own = box.read(INTERFACES).replace(
        'iface bond0 inet dhcp\n', 'iface bond0 inet static\n\taddress 192.168.9.2/24\n')
    box.write(INTERFACES, own)
    box.role('controller')
    assert 'address 192.168.9.2/24' in stanza(box.read(INTERFACES), 'bond0')


def test_there_and_back_gives_the_same_controller(box):
    box.role('controller')
    born = box.snapshot()
    born_units = dict(box.units)
    box.role('node')
    box.path_active = True
    box.role('controller')
    after = {k: v for k, v in box.snapshot().items()
             if not k.startswith(INTERFACES + '.cuems-')}
    born = {k: v for k, v in born.items() if not k.startswith(INTERFACES + '.cuems-')}
    assert after == born
    assert box.units == born_units


def test_a_controller_switches_its_units_on_and_unmasks_the_engine(box):
    box.role('node')
    box.path_active = True
    box.role('controller')
    for unit, state in BORN_UNITS.items():
        assert box.units[unit] == state, unit


def test_a_controller_is_pinned_to_itself_and_publishes_itself_as_one(box):
    box.role('controller')
    assert pins(box) == ['127.0.0.1\tcontroller.local\t# cuems-set-role']
    assert 'node_type=master' in box.read('etc/avahi/services/cuems.service')
    own = box.own()
    assert (own['node_type'], own['ip'], own['role_id']) == (
        'NodeType.master', '127.0.0.1', 'controller')
    assert [n['uuid'] for n in box.nodes()] == [MINTED]


def test_another_listed_controller_is_demoted_with_a_warning(box):
    other = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    box.write(MAP, box.read(MAP).replace('</node_list>', f'''    <node>
            <uuid>{other}</uuid><mac>02</mac><name>x</name>
            <node_type>NodeType.master</node_type><ip>169.254.0.1</ip>
            <role_id>controller</role_id>
        </node>
    </node_list>'''))
    result = box.role('controller')
    entry = next(n for n in box.nodes() if n['uuid'] == other)
    assert entry['node_type'] == 'NodeType.slave' and 'role_id' not in entry
    assert any(other in w for w in result.warnings)


def test_the_controller_path_is_stopped_before_the_lock_file_appears(box):
    """systemd watches that file: creating it would start the controller at once."""
    box.role('node')
    box.path_active, box.events = True, []
    box.role('controller')
    assert box.events == [('stop path', False)]


def test_if_the_path_cannot_be_stopped_nothing_is_written(box):
    box.role('node')
    box.path_active, box.path_stops = True, False
    before = box.snapshot()
    with pytest.raises(sr.RoleError, match='cuems-controller.path'):
        box.role('controller')
    assert box.snapshot() == before


def test_nothing_is_ever_started_or_restarted(box):
    box.role('node')
    box.path_active = True
    box.role('controller')
    verbs = {c[1] for c in box.calls if c[0] == 'systemctl'}
    assert not verbs & {'start', 'restart', 'reload', 'isolate', 'reboot'}
    assert not any('--now' in c for c in box.calls)
    assert [c for c in box.calls if c[:2] == ['systemctl', 'stop']] == [
        ['systemctl', 'stop', 'cuems-controller.path']]


def test_a_site_network_mode_is_pointed_out_when_the_bond_is_rewritten(box):
    box.role('node')
    box.path_active = True
    box.write('etc/cuems/net-mode.conf', 'NET_MODE=cable-static\n')
    (box.root / (INTERFACES + sr.KEPT_CONTROLLER)).unlink()
    assert any('cuems-net-mode cable-static' in w for w in box.role('controller').warnings)


# --- the name ------------------------------------------------------------------------

def avahi_pin(box, name):
    box.write('etc/avahi/avahi-daemon.conf', f'[server]\nhost-name={name}\nuse-ipv4=yes\n')


def test_one_run_writes_the_name_everywhere(box):
    avahi_pin(box, box.read('etc/hostname').strip())
    box.role('node', hostname='sala-node01')
    assert box.read('etc/hostname') == 'sala-node01\n'
    assert '127.0.1.1\tsala-node01' in box.read('etc/hosts').splitlines()
    assert 'host-name=sala-node01' in box.read('etc/avahi/avahi-daemon.conf').splitlines()
    assert box.own()['hostname'] == 'sala-node01'


def test_with_no_name_given_the_box_keeps_its_own_and_the_map_says_it(box):
    name = box.read('etc/hostname').strip()
    box.role('node')
    assert box.read('etc/hostname').strip() == name
    assert box.own()['hostname'] == name


def test_without_a_host_name_line_avahi_conf_is_left_alone(box):
    before = box.read('etc/avahi/avahi-daemon.conf')
    box.role('node', hostname='sala-node01')
    assert box.read('etc/avahi/avahi-daemon.conf') == before


@pytest.mark.parametrize('name', ['Sala', 'sala_1', '-sala', 'sala.local', 'a' * 64, 'localhost'])
def test_a_bad_name_is_refused(box, name):
    with pytest.raises(sr.RoleError):
        box.role('controller', hostname=name)


def test_a_node_cannot_be_called_controller(box):
    with pytest.raises(sr.RoleError):
        box.role('node', hostname='controller')


# --- the rules ------------------------------------------------------------------------

def test_it_refuses_while_a_project_is_loaded(box):
    box.write('tmp/cuems.show.lock', '')
    before = box.snapshot()
    with pytest.raises(cp.ProjectLoaded):
        box.role('node')
    assert box.snapshot() == before and box.calls == []


def test_it_refuses_while_the_first_boot_is_pending(box):
    box.write('var/lib/cuems/firstboot.armed', '')
    with pytest.raises(sr.RoleError, match='first boot'):
        box.role('node')


def test_a_box_without_an_identity_cannot_become_a_node(box):
    box.write('etc/cuems/settings.xml', box.read('etc/cuems/settings.xml').replace(MINTED, SENTINEL))
    box.write(MAP, box.read(MAP).replace(MINTED, SENTINEL))
    with pytest.raises(sr.RoleError, match='identity'):
        box.role('node')


def test_the_recipe_can_set_the_born_controller_before_there_is_an_identity(box):
    box.write('etc/cuems/settings.xml', box.read('etc/cuems/settings.xml').replace(MINTED, SENTINEL))
    box.write(MAP, box.read(MAP).replace(MINTED, SENTINEL))
    (box.root / 'etc/avahi/services/cuems.service').unlink()
    box.role('controller')
    assert not box.exists('etc/avahi/services/cuems.service')
    assert [n['uuid'] for n in box.nodes()] == [SENTINEL]


def test_a_second_run_changes_nothing_and_says_so(box):
    box.role('node')
    before = box.snapshot()
    box.calls.clear()
    result = box.role('node')
    assert result.changes == []
    assert box.snapshot() == before
    assert not [c for c in box.calls if c[1] in ('enable', 'disable', 'mask', 'unmask')]


def test_a_dry_run_lists_the_changes_and_makes_none(box):
    before = box.snapshot()
    result = box.role('node', dry_run=True)
    assert result.changes and box.snapshot() == before
    assert box.units == BORN_UNITS


def test_a_unit_that_cannot_be_switched_is_an_error_to_run_again(box):
    box.fail.add('mask')
    with pytest.raises(sr.RoleError, match='again'):
        box.role('node')
    box.fail.clear()
    box.role('node')
    assert box.units['cuems-controller-engine.service'] == 'masked'


def test_a_unit_of_a_package_that_is_not_installed_is_skipped(box):
    del box.units['cuems-power-bridge.service']
    box.role('node')
    assert 'cuems-power-bridge.service' not in box.units


def test_a_missing_engine_unit_is_an_error_before_anything_is_written(box):
    del box.units['cuems-node.target']
    before = box.snapshot()
    with pytest.raises(sr.RoleError, match='cuems-node.target'):
        box.role('node')
    assert box.snapshot() == before


def test_exit_codes_and_the_call_for_a_reboot(box, capsys):
    run = lambda *argv: sr.main(list(argv), system=box.system(), platform=cp)
    assert run('node', NODE_ADDR, '--hostname', 'sala-node01') == 0
    out = capsys.readouterr().out
    assert 'Reboot' in out and 'etc/network/interfaces' in out
    assert run('node', '169.254.0.99') == 1
    box.write('tmp/cuems.show.lock', '')
    assert run('node', NODE_ADDR) == 6
    with pytest.raises(SystemExit) as e:
        run('node')
    assert e.value.code == 2


def test_the_engine_is_masked_even_when_its_package_is_absent(box):
    """A later install must not find it free to start."""
    del box.units['cuems-controller-engine.service']
    box.role('node')
    assert box.units['cuems-controller-engine.service'] == 'masked'


def test_a_local_copy_of_the_engine_unit_stops_it_before_anything_is_written(box):
    box.write('etc/systemd/system/cuems-controller-engine.service', '[Service]\n')
    before = box.snapshot()
    with pytest.raises(sr.RoleError, match='etc/systemd/system/cuems-controller-engine'):
        box.role('node')
    assert box.snapshot() == before
    assert not [c for c in box.calls if c[1] in ('enable', 'disable', 'mask', 'unmask')]


def test_the_reboot_is_asked_for_as_a_must(box, capsys):
    assert sr.main(['node', NODE_ADDR], system=box.system(), platform=cp) == 0
    assert 'Reboot now' in capsys.readouterr().out


@pytest.mark.parametrize('state', ['disabled', 'enabled', 'masked', None])
def test_nodeconf_is_left_alone_in_both_roles(box, state):
    """Whether it runs is not the role command's to decide: some controllers run
    it, and it is how boxes will get their role later."""
    if state is None:
        del box.units['cuems-nodeconf.service']
    else:
        box.units['cuems-nodeconf.service'] = state
    box.calls.clear()
    box.role('node')
    box.path_active = True
    box.role('controller')
    assert box.units.get('cuems-nodeconf.service') == state
    assert not [c for c in box.calls if 'cuems-nodeconf.service' in c]


# --- found on the first rig test ---------------------------------------------------

@pytest.mark.parametrize('version, warned', [
    ('0.1.0rc2-1', True), ('0.1.0rc3-9', True), ('0.1.0rc4-1', False),
    ('0.1.0rc6-5', False), ('0.1.1-1', False), (None, False)])
def test_a_node_with_an_engine_too_old_to_find_its_controller_is_warned(box, version, warned):
    """Before 0.1.0rc4-1 the engine only read the map: with no controller listed
    it restarted for ever."""
    box.engine_version = version
    result = box.role('node', dry_run=True)
    assert any('0.1.0rc4-1' in w for w in result.warnings) is warned


def test_a_controller_is_not_warned_about_the_engine(box):
    box.engine_version = '0.1.0rc2-1'
    assert not any('0.1.0rc4-1' in w for w in box.role('controller').warnings)


@pytest.mark.parametrize('hostname, pinned', [
    ('controller', None), ('controller', '021122334402'), ('sala', 'controller')])
def test_a_node_is_refused_while_it_would_still_be_called_controller(box, hostname, pinned):
    box.write('etc/hostname', hostname + '\n')
    if pinned:
        avahi_pin(box, pinned)
    before = box.snapshot()
    with pytest.raises(sr.RoleError, match='--hostname'):
        box.role('node')
    assert box.snapshot() == before
    box.role('node', hostname='sala-node01')


@pytest.mark.parametrize('old_pin', ['0013a1b2c3d4', 'stage-left'])
def test_a_name_pinned_in_avahi_is_kept_by_a_rename(box, old_pin):
    """A pin that does not follow the host name was set on purpose (the MAC, so
    that the box is always reachable by it)."""
    avahi_pin(box, old_pin)
    before = box.read('etc/avahi/avahi-daemon.conf')
    result = box.role('node', hostname='sala-node01')
    assert box.read('etc/avahi/avahi-daemon.conf') == before
    assert any(old_pin in w and 'sala-node01' in w for w in result.warnings)
    assert box.read('etc/hostname') == 'sala-node01\n'


def test_a_pin_called_controller_follows_the_rename(box):
    avahi_pin(box, 'controller')
    box.role('node', hostname='sala-node01')
    assert 'host-name=sala-node01' in box.read('etc/avahi/avahi-daemon.conf').splitlines()


BRIDGE = 'cuems-power-bridge.service'


def test_a_power_bridge_that_was_off_stays_off(box):
    box.units[BRIDGE] = 'disabled'
    box.role('controller')
    assert box.units[BRIDGE] == 'disabled'
    box.role('node')
    box.path_active = True
    box.role('controller')
    assert box.units[BRIDGE] == 'disabled'


def test_a_power_bridge_the_command_switched_off_comes_back_once(box):
    box.role('node')
    assert box.units[BRIDGE] == 'disabled'
    box.role('node', address='169.254.0.12')
    box.path_active = True
    box.role('controller')
    assert box.units[BRIDGE] == 'enabled'
    # Switched off by hand afterwards: that is somebody's decision.
    box.units[BRIDGE] = 'disabled'
    box.role('controller')
    assert box.units[BRIDGE] == 'disabled'


def test_the_memory_of_the_bridge_survives_a_failed_run(box):
    box.fail.add('mask')
    with pytest.raises(sr.RoleError):
        box.role('node')
    box.fail.clear()
    box.role('node')
    box.path_active = True
    box.role('controller')
    assert box.units[BRIDGE] == 'enabled'


def test_a_dry_run_does_not_touch_that_memory(box):
    box.role('node', dry_run=True)
    assert not box.exists(sr.REMEMBERED)


def test_a_removed_engine_is_not_warned_about(box):
    box.engine_version, box.engine_status = '0.1.0rc2-1', 'config-files'
    assert not any('0.1.0rc4-1' in w for w in box.role('node', dry_run=True).warnings)


@pytest.mark.parametrize('hostname, pinned', [('Controller', None), ('sala', 'CONTROLLER')])
def test_controller_in_any_case_is_still_controller(box, hostname, pinned):
    """mDNS names match whatever the case."""
    box.write('etc/hostname', hostname + '\n')
    if pinned:
        avahi_pin(box, pinned)
    with pytest.raises(sr.RoleError, match='--hostname'):
        box.role('node')
    box.role('node', hostname='sala-node01')
    assert 'CONTROLLER' not in box.read('etc/avahi/avahi-daemon.conf')
