# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""cuems-firstboot on a temporary root.

These prove what the first boot decides and writes. They do not prove that the
minimal boot target, the rescue DHCP, the root growth or the keys work on a box:
that is AC5 to AC10, on a rig.
"""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from test_platform import FakeBox, PROFILES, cp, fp530, n97

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / 'usr/lib/cuems/bin/cuems-firstboot'
GENERATOR = REPO / 'usr/lib/cuems/systemd/cuems-firstboot-generator'


def load_tool():
    loader = importlib.machinery.SourceFileLoader('cuems_firstboot', str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


fb = load_tool()

SENTINEL = '00000000-0000-0000-0000-000000000000'
MINTED = '6f1d2c1e-8a54-4a30-9a0e-3d2b7c9e1f42'
SEEDED = '1b2c3d4e-0000-4111-8222-333344445555'
OTHER = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'

SETTINGS = f'''<?xml version="1.0" encoding="UTF-8"?>
<cms:CuemsSettings xmlns:cms="https://stagelab.coop/cuems/">
    <Settings>
        <library_path>/opt/cuems_library</library_path>
        <node>
            <uuid>{SENTINEL}</uuid>
            <mac>REPLACE-WITH-NODE-MAC</mac>
        </node>
    </Settings>
</cms:CuemsSettings>
'''

NETWORK_MAP = f'''<?xml version='1.0' encoding='utf-8'?>
<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/">
    <node_list>
        <node>
            <uuid>{SENTINEL}</uuid>
            <mac>REPLACE-WITH-NODE-MAC</mac>
            <name>REPLACE-WITH-NODE-MAC._cuems_nodeconf._tcp.local.</name>
            <node_type>NodeType.master</node_type>
            <ip>192.168.1.10</ip>
            <adopted>True</adopted>
            <online>True</online>
        </node>
    </node_list>
</cms:CuemsNetworkMap>
'''

AVAHI = (f'<service-group><service><txt-record>node_type={{role}}</txt-record>'
         f'<txt-record>uuid={SENTINEL}</txt-record></service></service-group>\n')

HOSTS = '127.0.0.1\tlocalhost\n127.0.1.1\tlocalhost\n::1\tlocalhost ip6-localhost\n'

MACS = {'ethernet0': '02:11:22:33:44:55', 'ethernet1': '02:11:22:33:44:66'}


class BornBox(FakeBox):
    """A box just written from the image: sealed documents and no keys."""

    def __init__(self, root, platform=n97):
        super().__init__(root)
        platform(self)
        # Kernel names: nothing has renamed the ports yet.
        for bdf, name in (('0000:01:00.0', 'enp1s0'), ('0000:02:00.0', 'enp2s0')):
            (self.root / f'sys/bus/pci/devices/{bdf}/net/{name}').mkdir(parents=True)
        self.macs = {'enp1s0': '02:11:22:33:44:01', 'enp2s0': '02:11:22:33:44:02'}
        for name, mac in self.macs.items():
            self.write(f'sys/class/net/{name}/address', mac + '\n')
        self.write('etc/cuems/settings.xml', SETTINGS)
        self.write('etc/cuems/network_map.xml', NETWORK_MAP)
        for kind, role in (('firstrun', 'firstrun'), ('master', 'master'), ('slave', 'slave')):
            self.write(f'usr/share/cuems/cuems.service.{kind}', AVAHI.format(role=role))
        for path in PROFILES.glob('*/default_mappings.xml'):
            self.write(f'usr/share/cuems/platform/{path.parent.name}/default_mappings.xml',
                       path.read_text())
        self.write('etc/hosts', HOSTS)
        self.write('etc/hostname', 'localhost\n')
        self.write('etc/cuems/image-release', 'IMAGE_ID=cuems-test-1\nBUILD_DATE=2026-01-01\n')
        self.write('var/lib/cuems/firstboot.armed', '')
        (self.root / 'etc/avahi/services').mkdir(parents=True)
        (self.root / 'opt/cuems_library/projects').mkdir(parents=True)
        self.calls = []
        self.bridge_installed = True
        self.root_fstype = 'ext4'
        self.growpart = (0, 'CHANGED: partition=2')

    def run(self, argv):
        self.calls.append(argv)
        out, code = '', 0
        name = os.path.basename(argv[0])
        if name in self.fail:
            code = 1
        elif name == 'ssh-keygen' and '-A' in argv:
            self.write('etc/ssh/ssh_host_ed25519_key', 'host key\n')
        elif name == 'ssh-keygen':
            key = pathlib.Path(argv[argv.index('-f') + 1])
            key.write_text('bridge key\n')
            pathlib.Path(f'{key}.pub').write_text('pub\n')
        elif name == 'ethtool':
            out = f'Permanent address: {self.macs.get(argv[-1], "00:00:00:00:00:00")}\n'
        elif name == 'cuems-make-tls-cert':
            self.write('etc/ssl/certs/apache-selfsigned.crt', 'cert\n')
        elif name == 'findmnt':
            out = {'SOURCE': '/dev/sda2\n', 'FSTYPE': f'{self.root_fstype}\n'}[argv[argv.index('-no') + 1]]
        elif name == 'lsblk':
            out = 'sda\n'
        elif name == 'growpart':
            code, out = self.growpart
        elif name == 'dpkg-query':
            ok = self.bridge_installed if argv[-1] == 'cuems-power-bridge' else True
            code, out = (0, 'install ok installed') if ok else (1, '')
        return subprocess.CompletedProcess(argv, code, out, '')

    def ran(self, name):
        return [c for c in self.calls if os.path.basename(c[0]) == name]

    def report(self):
        return json.loads(self.read('var/lib/cuems/firstboot.json'))

    def boot(self, mint=lambda: MINTED):
        return fb.first_boot(self.system(), cp, PROFILES, mint=mint, wait=0)

    def seed(self, text):
        self.write('boot/efi/cuems-seed.txt', text)

    def uuids(self):
        """The uuid in each of the four places."""
        found = {}
        for key, rel in (('settings', 'etc/cuems/settings.xml'),
                         ('map', 'etc/cuems/network_map.xml'),
                         ('mappings', 'etc/cuems/default_mappings.xml')):
            tree = ET.fromstring(self.read(rel).encode())
            found[key] = next(e.text for e in tree.iter('uuid'))
        record = self.read('etc/avahi/services/cuems.service')
        found['avahi'] = record.split('uuid=')[1].split('<')[0]
        return found


@pytest.fixture
def born(tmp_path):
    return BornBox(tmp_path)


def node_of(box):
    tree = ET.fromstring(box.read('etc/cuems/network_map.xml').encode())
    return {child.tag: child.text for child in tree.find('node_list/node')}


# --- the good path ------------------------------------------------------------

def test_a_new_box_gets_one_identity_in_all_four_places(born):
    assert born.boot() == fb.DONE
    assert set(born.uuids().values()) == {MINTED}


def test_no_sentinel_or_placeholder_is_left(born):
    born.boot()
    for path in (born.root / 'etc').rglob('*'):
        if path.is_file():
            text = path.read_text()
            assert SENTINEL not in text and 'REPLACE-WITH' not in text, path
    for path in (born.root / 'usr/share/cuems').glob('cuems.service.*'):
        assert SENTINEL not in path.read_text()


def test_mac_and_hostname_come_from_the_port_that_will_be_ethernet0(born):
    """On the N97 that is the higher-addressed port: enp2s0 here."""
    born.boot()
    node = node_of(born)
    assert node['mac'] == '021122334402'
    assert node['hostname'] == '021122334402'
    assert node['name'] == '021122334402._cuems_nodeconf._tcp.local.'
    assert node['ip'] == '127.0.0.1'
    assert born.read('etc/hostname') == '021122334402\n'
    assert '<mac>021122334402</mac>' in born.read('etc/cuems/settings.xml')


def test_hosts_gets_the_name_and_the_controller_pin_once(born):
    born.write('etc/hosts', HOSTS + '10.9.9.9\tcontroller.local\n')
    born.boot()
    lines = born.read('etc/hosts').splitlines()
    assert '127.0.1.1\t021122334402' in lines
    assert [line for line in lines if 'controller.local' in line] == [fb.CONTROLLER_PIN]
    assert fb.CONTROLLER_PIN == '127.0.0.1\tcontroller.local\t# cuems-firstboot'
    assert '127.0.0.1\tlocalhost' in lines


def test_the_born_record_is_a_standalone_controller(born):
    born.boot()
    assert 'node_type=master' in born.read('etc/avahi/services/cuems.service')


@pytest.mark.parametrize('platform, connectors', [(n97, 3), (fp530, 4)])
def test_the_starting_mappings_have_every_video_output_of_the_platform(
        tmp_path, platform, connectors):
    box = BornBox(tmp_path, platform)
    assert box.boot() == fb.DONE
    text = box.read('etc/cuems/default_mappings.xml')
    assert [f'HDMI-A-{i}' in text for i in range(1, connectors + 2)] == (
        [True] * connectors + [False])
    assert 'system:playback_1' in text and 'system:playback_2' in text
    assert f'<default_video_output>{MINTED}_0</default_video_output>' in text


def test_a_mappings_file_that_has_this_identity_is_left_alone(born):
    born.seed(SEEDED + '\n')
    mine = born.read('usr/share/cuems/platform/n97/default_mappings.xml').replace(
        SENTINEL, SEEDED).replace('HDMI 1', 'Left wall')
    born.write('etc/cuems/default_mappings.xml', mine)
    assert born.boot() == fb.DONE
    assert born.read('etc/cuems/default_mappings.xml') == mine


def test_keys_certificate_root_and_services(born):
    born.boot()
    assert born.exists('etc/ssh/ssh_host_ed25519_key')
    assert born.ran('cuems-make-tls-cert')
    assert born.exists('etc/cuems/power-bridge.key')
    assert born.ran('growpart') == [['growpart', '/dev/sda', '2']]
    assert born.ran('resize2fs') == [['resize2fs', '/dev/sda2']]
    assert ['systemctl', 'enable', 'cuems-gradient-motiond.service'] in born.calls


def test_keys_that_exist_are_not_made_again(born):
    born.write('etc/ssh/ssh_host_rsa_key', 'old\n')
    born.write('etc/cuems/power-bridge.key', 'old\n')
    born.boot()
    assert born.ran('ssh-keygen') == []


def test_no_bridge_key_on_a_box_without_the_bridge(born):
    born.bridge_installed = False
    born.boot()
    assert not born.exists('etc/cuems/power-bridge.key')


def test_a_root_that_already_fills_the_disk_is_not_an_error(born):
    born.growpart = (1, 'NOCHANGE: partition 2 is size 1. it cannot be grown')
    assert born.boot() == fb.DONE


def test_success_disarms_reports_and_reboots(born, capsys):
    born.boot()
    assert not born.exists('var/lib/cuems/firstboot.armed')
    report = born.report()
    assert report['status'] == 'done'
    assert (report['platform'], report['uuid'], report['uuid_source'], report['image_id']) == (
        'n97', MINTED, 'minted', 'cuems-test-1')
    assert report['platform_accepted'] is False
    assert born.calls[-1] == ['systemctl', '--no-block', 'reboot']
    assert f'done platform=n97 uuid={MINTED}' in capsys.readouterr().out


def test_the_platform_is_applied(born):
    born.boot()
    assert born.exists(cp.ANALOG_RULE)
    assert 'pci-0000:02:00.0' in born.read('etc/systemd/network/10-ethernet0.link')


# --- the seed ------------------------------------------------------------------------

@pytest.mark.parametrize('text', [SEEDED + '\n', SEEDED.upper() + '\r\n', '  ' + SEEDED])
def test_a_seed_gives_the_uuid_and_is_removed_when_done(born, text):
    born.seed(text)
    assert born.boot() == fb.DONE
    assert set(born.uuids().values()) == {SEEDED}
    assert born.report()['uuid_source'] == 'seed'
    assert not born.exists('boot/efi/cuems-seed.txt')


@pytest.mark.parametrize('text', ['', 'not a uuid\n', SENTINEL, f'{SEEDED}\n{OTHER}\n',
                                  'a3811d78-0000-0000-0000-000000000000',
                                  '0367f391-ebf4-48b2-9f26-000000000001'])
def test_a_bad_seed_fails_and_never_mints_instead(born, text):
    born.seed(text)
    assert born.boot() == fb.FAILED
    assert born.read('etc/cuems/settings.xml') == SETTINGS
    assert born.exists('var/lib/cuems/firstboot.armed')
    assert 'seed' in born.report()['reason']


# --- a box that is not new -------------------------------------------------------------

def refused(box):
    before = {p: p.read_bytes() for p in (box.root / 'etc').rglob('*') if p.is_file()}
    code = box.boot()
    after = {p: p.read_bytes() for p in (box.root / 'etc').rglob('*') if p.is_file()}
    new = {p.name for p in set(after) - set(before)}
    assert all(name.startswith('ssh_host_') for name in new), new
    assert all(after[p] == before[p] for p in before)
    return code


def test_a_box_with_a_real_uuid_is_refused_and_left_alone(born):
    born.write('etc/cuems/settings.xml', SETTINGS.replace(SENTINEL, OTHER))
    assert refused(born) == fb.REFUSED
    assert born.ran('growpart') == [] and born.ran('cuems-make-tls-cert') == []
    assert born.report()['status'] == 'refused'
    assert not born.exists('var/lib/cuems/firstboot.armed')
    assert born.calls[-2:] == [['systemctl', 'daemon-reload'],
                               ['systemctl', '--no-block', 'start', 'default.target']]
    assert fb.REFUSED != 0


def test_a_box_with_a_project_is_refused(born):
    (born.root / 'opt/cuems_library/projects/show').mkdir()
    assert refused(born) == fb.REFUSED
    assert 'project' in born.report()['reason']


def test_the_uuid_the_seed_names_is_not_a_reason_to_refuse(born):
    born.write('etc/cuems/settings.xml', SETTINGS.replace(SENTINEL, SEEDED))
    born.write('etc/cuems/network_map.xml', NETWORK_MAP.replace(SENTINEL, SEEDED))
    born.seed(SEEDED)
    assert born.boot() == fb.DONE


def test_arming_a_box_that_already_finished_is_refused(born):
    born.boot()
    born.write('var/lib/cuems/firstboot.armed', '')
    born.write('etc/hostname', 'controller\n')
    assert born.boot() == fb.REFUSED
    assert born.read('etc/hostname') == 'controller\n'


@pytest.mark.parametrize('example', ['a3811d78-1111-4222-8333-444455556666',
                                     '0367f391-ebf4-48b2-9f26-000000000001'])
def test_an_example_uuid_left_by_the_seal_fails_and_does_not_disarm(born, example):
    born.write('etc/cuems/settings.xml', SETTINGS.replace(SENTINEL, example))
    assert born.boot() == fb.FAILED
    assert born.exists('var/lib/cuems/firstboot.armed')


def test_an_upper_case_uuid_that_the_seed_names_is_this_box(born):
    born.write('etc/cuems/settings.xml', SETTINGS.replace(SENTINEL, SEEDED.upper()))
    born.write('etc/cuems/network_map.xml', NETWORK_MAP.replace(SENTINEL, SEEDED.upper()))
    born.seed(SEEDED)
    assert born.boot() == fb.DONE
    assert set(born.uuids().values()) == {SEEDED}


# --- failure and resume ------------------------------------------------------------

def test_a_failure_keeps_the_box_armed_and_does_not_reboot(born):
    born.fail.add('growpart')
    born.growpart = (2, 'FAILED')
    assert born.boot() == fb.FAILED
    assert born.exists('var/lib/cuems/firstboot.armed')
    assert born.report()['status'] == 'failed'
    assert born.report()['step'] == 'grow the root partition'
    assert not [c for c in born.calls if 'reboot' in c]


def test_a_boot_after_a_failure_resumes_with_the_same_uuid(born):
    born.fail.add('cuems-make-tls-cert')
    assert born.boot() == fb.FAILED
    born.fail.clear()
    assert born.boot(mint=lambda: OTHER) == fb.DONE
    assert set(born.uuids().values()) == {MINTED}


def test_the_uuid_is_saved_before_the_first_document_changes(born, monkeypatch):
    seen = {}
    real = fb.write_identity

    def spy(system, *args):
        seen['state'] = json.loads(born.read('var/lib/cuems/firstboot.state'))
        seen['settings'] = born.read('etc/cuems/settings.xml')
        return real(system, *args)

    monkeypatch.setattr(fb, 'write_identity', spy)
    born.boot()
    assert seen['state']['uuid'] == MINTED and seen['settings'] == SETTINGS


def test_a_seed_changed_after_a_failure_is_an_error(born):
    born.seed(SEEDED)
    born.fail.add('cuems-make-tls-cert')
    born.boot()
    born.fail.clear()
    born.seed(OTHER)
    assert born.boot() == fb.FAILED
    reason = born.report()['reason']
    assert 'seed' in reason
    # Without the state file the half-born box would be refused: never advise it.
    assert 'firstboot.state' not in reason


@pytest.mark.parametrize('rel, text', [
    ('etc/cuems/settings.xml', None),
    ('etc/cuems/settings.xml', SETTINGS.replace(SENTINEL, 'REPLACE-WITH-NODE-UUID')),
    ('etc/cuems/network_map.xml', NETWORK_MAP.replace(SENTINEL, OTHER)),
    ('usr/share/cuems/cuems.service.master', '<service-group/>\n'),
])
def test_documents_the_seal_did_not_prepare_are_a_failure(born, rel, text):
    if text is None:
        (born.root / rel).unlink()
    else:
        born.write(rel, text)
    assert born.boot() == fb.FAILED


def test_a_mappings_file_with_another_identity_is_a_failure(born):
    born.write('etc/cuems/default_mappings.xml', born.read(
        'usr/share/cuems/platform/n97/default_mappings.xml').replace(SENTINEL, OTHER))
    assert born.boot() == fb.FAILED


def test_a_root_that_is_not_ext4_is_a_failure(born):
    born.root_fstype = 'btrfs'
    assert born.boot() == fb.FAILED
    assert born.ran('growpart') == []


@pytest.mark.parametrize('prepare', [
    lambda b: b.cpu('Something else'),
    lambda b: b.pci('0000:07:00.0', '0x020000', '10ec', '8168'),
])
def test_a_box_that_does_not_fit_takes_the_packaged_port_files_out_of_force(born, prepare):
    packaged = '[Match]\nPath=pci-0000:01:00.0\n\n[Link]\nName=ethernet0\n'
    born.write('etc/systemd/network/10-ethernet0.link', packaged)
    prepare(born)
    assert born.boot() == fb.FAILED
    assert not born.exists('etc/systemd/network/10-ethernet0.link')
    assert born.read('etc/systemd/network/10-ethernet0.link.cuems-disabled') == packaged
    assert born.ran('update-initramfs')
    assert born.read('etc/cuems/settings.xml') == SETTINGS


def test_a_port_with_no_network_device_is_a_failure(born):
    os.rmdir(born.root / 'sys/bus/pci/devices/0000:02:00.0/net/enp2s0')
    assert born.boot() == fb.FAILED
    assert born.read('etc/cuems/settings.xml') == SETTINGS


def test_an_unarmed_box_is_not_touched(born):
    (born.root / 'var/lib/cuems/firstboot.armed').unlink()
    assert born.boot() == fb.DONE
    assert born.calls == [] and born.read('etc/cuems/settings.xml') == SETTINGS


# --- the boot-time pieces -------------------------------------------------------------

def run_generator(tmp_path, armed):
    arm = tmp_path / 'armed'
    if armed:
        arm.write_text('')
    early = tmp_path / 'early'
    early.mkdir()
    subprocess.run(['sh', str(GENERATOR), str(tmp_path / 'normal'), str(early),
                    str(tmp_path / 'late')], check=True,
                   env={**os.environ, 'CUEMS_FIRSTBOOT_ARMED': str(arm)})
    return early / 'default.target'


def test_an_armed_box_boots_the_first_boot_target(tmp_path):
    link = run_generator(tmp_path, armed=True)
    assert os.readlink(link) == '/lib/systemd/system/cuems-firstboot.target'


def test_an_unarmed_box_is_left_to_its_normal_boot(tmp_path):
    assert not run_generator(tmp_path, armed=False).is_symlink()


def unit(name):
    return (REPO / 'etc/systemd/system' / name).read_text()


def test_the_target_pulls_in_nothing_but_the_first_boot():
    text = unit('cuems-firstboot.target')
    pulled = [line for line in text.splitlines()
              if line.startswith(('Wants=', 'Requires='))]
    assert pulled == ['Requires=basic.target', 'Wants=cuems-firstboot.service']
    assert 'AllowIsolate=yes' in text


def test_the_service_runs_only_when_armed_and_rescues_on_failure():
    text = unit('cuems-firstboot.service')
    assert 'ConditionPathExists=/var/lib/cuems/firstboot.armed' in text
    assert 'OnFailure=cuems-firstboot-rescue.service' in text
    assert f'SuccessExitStatus={fb.REFUSED}' in text
    assert 'Before=network-pre.target' in text
    assert '[Install]' not in text.splitlines()


# --- what the early boot targets could still pull in -----------------------------
# basic.target brings timers and sockets with it, so these two reach an armed box.

NOT_ARMED = 'ConditionPathExists=!/var/lib/cuems/firstboot.armed'


@pytest.mark.parametrize('rel', ['etc/systemd/system/avahi-daemon.d/20-cuems-firstboot.conf',
                                 'etc/systemd/system/avahi-daemon.socket.d/20-cuems-firstboot.conf'])
def test_mdns_cannot_be_woken_on_an_armed_box(rel):
    assert NOT_ARMED in (REPO / rel).read_text().splitlines()
    source = rel.rsplit('/', 1)[0]
    assert f'{source}/*' in (REPO / 'debian/install').read_text()


def test_the_network_guard_does_nothing_on_an_armed_box(tmp_path):
    """It must leave before it reads or touches anything of the network."""
    armed = tmp_path / 'armed'
    armed.write_text('')
    done = subprocess.run([shutil.which('bash'), str(REPO / 'scripts/cuems-net-guard')], capture_output=True,
                          text=True, env={'PATH': '/nonexistent',
                                          'CUEMS_FIRSTBOOT_ARMED': str(armed)})
    assert (done.returncode, done.stdout, done.stderr) == (0, '', '')
    script = (REPO / 'scripts/cuems-net-guard').read_text()
    assert script.index('CUEMS_FIRSTBOOT_ARMED') < script.index('. /usr/lib/cuems/net-mode.sh')


@pytest.mark.parametrize('service', ['ifup@.service', 'networking.service'])
def test_ifupdown_configures_nothing_on_an_armed_box(service):
    rel = f'etc/systemd/system/{service}.d/20-cuems-firstboot.conf'
    assert NOT_ARMED in (REPO / rel).read_text().splitlines()
    assert f'etc/systemd/system/{service}.d/* lib/systemd/system/{service}.d/' in (
        REPO / 'debian/install').read_text()


def test_the_rescue_cannot_be_started_on_a_box_in_service():
    assert 'ConditionPathExists=/var/lib/cuems/firstboot.armed' in unit(
        'cuems-firstboot-rescue.service').splitlines()
