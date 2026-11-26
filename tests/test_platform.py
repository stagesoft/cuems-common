# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""cuems-platform on a fake /sys and /proc.

These tests prove the decisions (which platform, which port, which card, what is
written, when it refuses). They do not prove that udev, GRUB or ALSA act on what
is written: that is checked on a rig.
"""

import importlib.machinery
import importlib.util
import os
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / 'usr/bin/cuems-platform'
PROFILES = REPO / 'usr/share/cuems/platform'


def load_tool():
    loader = importlib.machinery.SourceFileLoader('cuems_platform', str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cp = load_tool()

ETH, WIFI, VGA, HDA = '0x020000', '0x028000', '0x030000', '0x040300'

GPU_PIN_AS_SHIPPED = '# a comment that names enabled=true\n\nenabled=false\n\nlevel=high\n'


class FakeBox:
    """A directory tree that looks like the parts of a box the tool reads."""

    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.commands = []
        self.installed = set()
        self.fail = set()
        self.write('etc/cuems/gpu-pin.conf', GPU_PIN_AS_SHIPPED)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def read(self, rel):
        return (self.root / rel).read_text()

    def exists(self, rel):
        return (self.root / rel).exists()

    def cpu(self, model):
        self.write('proc/cpuinfo', f'processor\t: 0\nmodel name\t: {model}\n')

    def pci(self, bdf, cls, vendor, device, netdev=None):
        base = f'sys/bus/pci/devices/{bdf}'
        self.write(f'{base}/class', cls + '\n')
        self.write(f'{base}/vendor', f'0x{vendor}\n')
        self.write(f'{base}/device', f'0x{device}\n')
        if netdev:
            (self.root / base / 'net' / netdev).mkdir(parents=True)

    def card(self, number, bdf, card_id, codecs):
        self.write(f'proc/asound/card{number}/id', card_id + '\n')
        for i, codec in enumerate(codecs):
            self.write(f'proc/asound/card{number}/codec#{i}', f'Codec: {codec}\nAddress: {i}\n')
        target = self.root / f'sys/devices/pci0000:00/{bdf}'
        target.mkdir(parents=True, exist_ok=True)
        link = self.root / f'sys/class/sound/card{number}'
        link.mkdir(parents=True, exist_ok=True)
        (link / 'device').symlink_to(target)

    def run(self, argv):
        self.commands.append(argv[0])
        if argv[0] == 'dpkg-query':
            ok = argv[-1] in self.installed
            return subprocess.CompletedProcess(argv, 0 if ok else 1,
                                               'install ok installed' if ok else '', '')
        return subprocess.CompletedProcess(argv, 1 if argv[0] in self.fail else 0, '', '')

    def system(self):
        return cp.System(root=self.root, run=self.run)


def n97(box, wired=('0000:01:00.0', '0000:02:00.0'), wifi='0000:03:00.0'):
    box.cpu('Intel(R) N97')
    box.pci('0000:00:02.0', VGA, '8086', '46d1')
    box.pci('0000:00:1f.3', HDA, '8086', '54c8')
    for bdf in wired:
        box.pci(bdf, ETH, '10ec', '8168')
    if wifi:
        box.pci(wifi, WIFI, '8086', '2725')
    box.card(0, '0000:00:1f.3', 'PCH', ['Realtek ALC897', 'Intel Alderlake-N HDMI'])


def fp530(box, wired=('0000:01:00.0', '0000:02:00.0'), wifi='0000:03:00.0',
          audio_bus='04', analog_first=False):
    box.cpu('AMD Ryzen Embedded R2314 with Radeon Vega Gfx')
    box.pci(f'0000:{audio_bus}:00.0', VGA, '1002', '15d8')
    box.pci(f'0000:{audio_bus}:00.1', HDA, '1002', '15de')
    box.pci(f'0000:{audio_bus}:00.6', HDA, '1022', '15e3')
    for bdf in wired:
        box.pci(bdf, ETH, '10ec', '8168')
    if wifi:
        box.pci(wifi, WIFI, '8086', '2725')
    hdmi = (f'0000:{audio_bus}:00.1', ['ATI R6xx HDMI'])
    analog = (f'0000:{audio_bus}:00.6', ['Realtek ALC897'])
    first, second = (analog, hdmi) if analog_first else (hdmi, analog)
    box.card(0, first[0], 'Generic', first[1])
    box.card(1, second[0], 'Generic_1', second[1])


@pytest.fixture
def box(tmp_path):
    return FakeBox(tmp_path)


@pytest.fixture(scope='module')
def profiles():
    return cp.load_profiles(PROFILES)


def link_path(box, name):
    text = box.read(f'etc/systemd/network/10-{name}.link')
    return [line for line in text.splitlines() if line.startswith('Path=')][0][5:]


def apply(box, profiles):
    return cp.apply(box.system(), profiles)


# --- the shipped profiles ----------------------------------------------------

def test_every_profile_is_there_and_parses(profiles):
    assert set(profiles) == {'n97', 'n100', 'fp530', 'i3-1215u', 'core-ultra5-125u'}


def test_no_profile_claims_acceptance_before_a_rig_has_passed(profiles):
    assert [p for p in profiles if profiles[p].accepted] == []


def test_no_profile_adds_a_kernel_parameter_on_the_three_platforms(profiles):
    for name in ('n97', 'n100', 'fp530'):
        assert profiles[name].kernel_params == []


def test_the_gpu_pin_is_on_for_the_fp530_only(profiles):
    assert [n for n in sorted(profiles) if profiles[n].gpu_pin] == ['fp530']


def test_a_typo_in_a_profile_is_an_error(tmp_path):
    (tmp_path / 'x').mkdir()
    (tmp_path / 'x/platform.conf').write_text('cpu_model=X\naccepted=false\nkernel_parms=quiet\n')
    with pytest.raises(cp.ProfileError, match='kernel_parms'):
        cp.load_profiles(tmp_path)


# --- detect -------------------------------------------------------------------

def test_detects_the_n97(box, profiles):
    n97(box)
    assert cp.detect(box.system(), profiles).id == 'n97'


def test_detects_the_fp530(box, profiles):
    fp530(box)
    assert cp.detect(box.system(), profiles).id == 'fp530'


def test_an_unknown_cpu_is_unknown(box, profiles):
    n97(box)
    box.cpu('Intel(R) Core(TM) i7-9999X')
    assert cp.detect(box.system(), profiles) is None


def test_the_right_cpu_with_another_gpu_is_unknown(box, profiles):
    box.cpu('Intel(R) N97')
    box.pci('0000:00:02.0', VGA, '10de', '2204')
    assert cp.detect(box.system(), profiles) is None


def test_n970_is_not_an_n97(box, profiles):
    n97(box)
    box.cpu('Intel(R) N970')
    assert cp.detect(box.system(), profiles) is None


def test_exit_code_for_an_unknown_platform_is_3(box, capsys):
    box.cpu('Something else')
    code = cp.main(['detect'], system=box.system(), profile_dir=PROFILES)
    assert code == 3
    assert capsys.readouterr().out.strip() == 'unknown'


# --- ports ----------------------------------------------------------------------

def test_n97_ethernet0_is_the_higher_addressed_wired_port(box, profiles):
    n97(box)
    ports = cp.assign_ports(box.system(), profiles['n97'])
    assert ports == {'ethernet0': '0000:02:00.0', 'ethernet1': '0000:01:00.0',
                     'wifi0': '0000:03:00.0'}


@pytest.mark.parametrize('wired, wifi', [
    (('0000:01:00.0', '0000:02:00.0'), '0000:03:00.0'),
    (('0000:02:00.0', '0000:03:00.0'), '0000:04:00.0'),
])
def test_fp530_ethernet0_is_the_lower_wired_port_on_both_layouts(box, profiles, wired, wifi):
    fp530(box, wired=wired, wifi=wifi)
    ports = cp.assign_ports(box.system(), profiles['fp530'])
    assert ports == {'ethernet0': wired[0], 'ethernet1': wired[1], 'wifi0': wifi}


def test_ports_do_not_need_a_bound_driver(box, profiles):
    """The Wi-Fi card of some boards gets no network device on the stock kernel."""
    n97(box)
    assert cp.assign_ports(box.system(), profiles['n97'])['wifi0'] == '0000:03:00.0'


def test_a_box_with_no_wifi_card_still_fits(box, profiles):
    n97(box, wifi=None)
    assert cp.assign_ports(box.system(), profiles['n97'])['wifi0'] is None


@pytest.mark.parametrize('wired', [
    ('0000:01:00.0',),
    ('0000:01:00.0', '0000:02:00.0', '0000:05:00.0'),
])
def test_any_other_number_of_wired_ports_does_not_fit(box, profiles, wired):
    n97(box, wired=wired, wifi=None)
    with pytest.raises(cp.PortsDoNotFit):
        cp.assign_ports(box.system(), profiles['n97'])


def test_two_wifi_cards_do_not_fit(box, profiles):
    n97(box)
    box.pci('0000:06:00.0', WIFI, '8086', '2725')
    with pytest.raises(cp.PortsDoNotFit):
        cp.assign_ports(box.system(), profiles['n97'])


def test_a_platform_whose_ports_were_never_read_does_not_fit(box, profiles):
    n97(box)
    with pytest.raises(cp.PortsDoNotFit, match='not been read'):
        cp.assign_ports(box.system(), profiles['n100'])


# --- apply ------------------------------------------------------------------------

def test_apply_on_an_n97_writes_the_ports_and_asks_for_a_reboot(box, profiles):
    n97(box)
    result = apply(box, profiles)
    assert link_path(box, 'ethernet0') == 'pci-0000:02:00.0'
    assert link_path(box, 'ethernet1') == 'pci-0000:01:00.0'
    assert link_path(box, 'wifi0') == 'pci-0000:03:00.0'
    assert result.changed and result.reboot_needed
    assert box.commands == ['update-initramfs', 'update-grub']


def test_apply_a_second_time_changes_nothing_and_runs_nothing(box, profiles):
    n97(box)
    apply(box, profiles)
    box.commands.clear()
    result = apply(box, profiles)
    assert result.changed == [] and not result.reboot_needed
    assert box.commands == []


def test_a_box_with_no_wifi_gets_a_wifi_rule_that_matches_nothing(box, profiles):
    """The package's own rule would otherwise rename whatever sits at its path."""
    fp530(box, wired=('0000:02:00.0', '0000:03:00.0'), wifi=None)
    apply(box, profiles)
    assert link_path(box, 'wifi0') == cp.NO_WIFI_MATCH


def test_the_n97_usb_audio_index(box, profiles):
    n97(box)
    apply(box, profiles)
    text = box.read('etc/modprobe.d/cuems-platform.conf')
    assert 'options snd_hda_intel index=0\n' in text
    assert 'options snd_usb_audio index=1\n' in text


def test_the_fp530_usb_audio_index_leaves_room_for_two_hda_cards(box, profiles):
    fp530(box)
    apply(box, profiles)
    text = box.read('etc/modprobe.d/cuems-platform.conf')
    assert 'options snd_usb_audio index=2\n' in text
    assert 'snd_hda_intel' not in text


@pytest.mark.parametrize('audio_bus, analog_first', [('04', False), ('05', False), ('05', True)])
def test_the_analog_card_is_found_by_its_codec_not_by_a_fixed_address(
        box, profiles, audio_bus, analog_first):
    fp530(box, audio_bus=audio_bus, analog_first=analog_first)
    apply(box, profiles)
    rule = box.read(cp.ANALOG_RULE)
    assert f'KERNELS=="0000:{audio_bus}:00.6", ATTR{{id}}="Analog"' in rule
    assert f'0000:{audio_bus}:00.1' not in rule


def test_on_the_n97_the_one_card_is_the_analog_card(box, profiles):
    n97(box)
    apply(box, profiles)
    assert 'KERNELS=="0000:00:1f.3", ATTR{id}="Analog"' in box.read(cp.ANALOG_RULE)


def test_a_usb_card_with_the_same_codec_is_not_the_analog_card(box, profiles):
    n97(box)
    box.card(1, '1-3:1.0', 'HID', ['Realtek ALC897'])
    apply(box, profiles)
    assert '0000:00:1f.3' in box.read(cp.ANALOG_RULE)


def test_no_analog_card_warns_and_the_rest_is_still_applied(box, profiles):
    n97(box)
    box.write('proc/asound/card0/codec#0', 'Codec: Something else\n')
    result = apply(box, profiles)
    assert not box.exists(cp.ANALOG_RULE)
    assert any('ALC897' in w for w in result.warnings)
    assert link_path(box, 'ethernet0') == 'pci-0000:02:00.0'


def test_fp530_turns_the_gpu_pin_on_and_keeps_the_comments(box, profiles):
    fp530(box)
    apply(box, profiles)
    assert box.read('etc/cuems/gpu-pin.conf') == GPU_PIN_AS_SHIPPED.replace(
        '\nenabled=false\n', '\nenabled=true\n')


def test_intel_leaves_the_gpu_pin_off_and_untouched(box, profiles):
    n97(box)
    apply(box, profiles)
    assert box.read('etc/cuems/gpu-pin.conf') == GPU_PIN_AS_SHIPPED


def test_no_kernel_parameter_means_the_grub_file_adds_nothing(box, profiles):
    n97(box)
    apply(box, profiles)
    text = box.read(cp.GRUB_CFG)
    assert 'GRUB_CMDLINE' not in text


def test_a_profile_kernel_parameter_is_appended(box, profiles):
    box.cpu('Intel(R) Core(TM) Ultra 5 125U')
    box.pci('0000:00:02.0', VGA, '8086', '7d45')
    prof = profiles['core-ultra5-125u']
    files = cp.planned_files(box.system(), prof, {'ethernet0': 'a', 'ethernet1': 'b',
                                                  'wifi0': None}, None)
    assert ('GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT i915.force_probe=7d45"'
            in files[cp.GRUB_CFG])


def test_apply_never_writes_a_mappings_file(box, profiles):
    n97(box)
    apply(box, profiles)
    assert not box.exists('etc/cuems/default_mappings.xml')


@pytest.mark.parametrize('prepare, error', [
    (lambda b: b.cpu('Something else'), 'UnknownPlatform'),
    (lambda b: b.pci('0000:07:00.0', ETH, '10ec', '8168'), 'PortsDoNotFit'),
])
def test_a_box_that_does_not_fit_gets_nothing_written(box, profiles, prepare, error):
    n97(box)
    prepare(box)
    with pytest.raises(getattr(cp, error)):
        apply(box, profiles)
    assert not box.exists('etc/systemd/network')
    assert not box.exists('etc/modprobe.d')
    assert box.commands == []


def test_apply_refuses_while_a_project_is_loaded(box, profiles):
    n97(box)
    box.write('tmp/cuems.show.lock', '')
    with pytest.raises(cp.ProjectLoaded):
        apply(box, profiles)
    assert not box.exists('etc/systemd/network')
    assert box.commands == []


def test_exit_codes_of_apply(box):
    box.cpu('Something else')
    run = lambda: cp.main(['apply'], system=box.system(), profile_dir=PROFILES)
    assert run() == 3
    n97(box, wired=('0000:01:00.0',))
    assert run() == 4
    box.write('tmp/cuems.show.lock', '')
    assert run() == 6


def test_a_dry_run_writes_and_runs_nothing(box, profiles):
    n97(box)
    result = cp.apply(box.system(), profiles, dry_run=True)
    assert result.changed
    assert not box.exists('etc/systemd/network')
    assert box.commands == []


def test_a_failed_rebuild_is_remembered_and_run_again(box, profiles):
    """The files are right after the first try, so only the note says what is owed."""
    n97(box)
    box.fail.add('update-initramfs')
    with pytest.raises(cp.RebuildFailed):
        apply(box, profiles)
    box.fail.clear()
    box.commands.clear()
    result = apply(box, profiles)
    assert result.changed == [] and result.reboot_needed
    assert box.commands == ['update-initramfs', 'update-grub']
    assert not box.exists(cp.PENDING)


# --- what apply could break on a box that is already in use ----------------------

def jack_file(box, device):
    box.write('etc/default/jack', f'DAEMON_ARGS="-R -dalsa -d{device} -r48000 -p512 -n3"\n')


@pytest.mark.parametrize('device', ['hw:PCH,0', 'hw:CARD=PCH,DEV=0'])
def test_apply_refuses_when_jack_names_the_card_by_the_id_it_would_lose(box, profiles, device):
    n97(box)
    jack_file(box, device)
    with pytest.raises(cp.JackNamesOldCard, match='hw:Analog'):
        apply(box, profiles)
    assert not box.exists('etc/systemd/network')
    assert box.commands == []
    assert cp.JackNamesOldCard.exit_code == 7


@pytest.mark.parametrize('device', ['hw:Analog,0', 'hw:HID,0', 'hw:0,0', 'multi_hdmi'])
def test_apply_goes_on_when_jack_does_not_depend_on_the_old_id(box, profiles, device):
    n97(box)
    jack_file(box, device)
    assert apply(box, profiles).changed


def test_apply_never_writes_the_jack_file(box, profiles):
    n97(box)
    jack_file(box, 'hw:Analog,0')
    before = box.read('etc/default/jack')
    apply(box, profiles)
    assert box.read('etc/default/jack') == before


def test_renaming_the_card_warns_about_the_saved_mixer_levels(box, profiles):
    n97(box)
    assert any('mixer' in w and 'PCH' in w for w in apply(box, profiles).warnings)


def test_a_card_that_already_has_the_id_warns_nothing(box, profiles):
    n97(box)
    box.write('proc/asound/card0/id', 'Analog\n')
    assert apply(box, profiles).warnings == []


def test_apply_warns_when_a_port_name_in_use_moves_to_another_port(box, profiles):
    n97(box)
    for bdf, name in (('0000:01:00.0', 'ethernet0'), ('0000:02:00.0', 'ethernet1')):
        (box.root / f'sys/bus/pci/devices/{bdf}/net/{name}').mkdir(parents=True)
    warnings = apply(box, profiles).warnings
    assert any('ethernet0' in w and '0000:01:00.0' in w and '0000:02:00.0' in w
               for w in warnings)


def test_kernel_names_in_use_do_not_count_as_a_move(box, profiles):
    n97(box)
    (box.root / 'sys/bus/pci/devices/0000:01:00.0/net/enp1s0').mkdir(parents=True)
    assert not any('ethernet' in w for w in apply(box, profiles).warnings)


def test_a_link_file_that_was_not_ours_is_kept_beside(box, profiles):
    n97(box)
    own = '[Match]\nPath=pci-0000:01:00.0\n\n[Link]\nName=ethernet0\n'
    box.write('etc/systemd/network/10-ethernet0.link', own)
    apply(box, profiles)
    kept = 'etc/systemd/network/10-ethernet0.link.cuems-before-apply'
    assert box.read(kept) == own
    # Our own file is never saved over the one that was there first.
    box.write('etc/systemd/network/10-ethernet0.link',
              cp.link_text(profiles['n97'], 'ethernet0', '0000:09:00.0'))
    assert apply(box, profiles).changed
    assert box.read(kept) == own
    assert not box.exists('etc/systemd/network/10-ethernet1.link.cuems-before-apply')


def test_a_dry_run_says_when_only_a_rebuild_is_owed(box, profiles, capsys):
    n97(box)
    apply(box, profiles)
    box.write(cp.PENDING, 'update-grub\n')
    assert cp.main(['apply', '--dry-run'], system=box.system(), profile_dir=PROFILES) == 0
    assert 'update-grub' in capsys.readouterr().out


# --- check ---------------------------------------------------------------------

def healthy_n97(box, profiles):
    """An N97 after apply and a reboot."""
    n97(box)
    apply(box, profiles)
    for bdf, name in (('0000:02:00.0', 'ethernet0'), ('0000:01:00.0', 'ethernet1'),
                      ('0000:03:00.0', 'wifi0')):
        (box.root / f'sys/bus/pci/devices/{bdf}/net/{name}').mkdir(parents=True)
    box.write('proc/asound/card0/id', 'Analog\n')
    box.write('proc/cmdline', 'BOOT_IMAGE=/boot/vmlinuz-6.1.0 root=UUID=x ro quiet splash\n')
    box.installed.update(profiles['n97'].firmware)
    box.write('sys/bus/pci/devices/0000:00:02.0/resource',
              '0x0000006000000000 0x0000006000ffffff 0x0000000000140204\n'
              '0x0000000000000000 0x0000000000000000 0x0000000000000000\n'
              '0x0000004000000000 0x000000403fffffff 0x000000000014220c\n')
    (box.root / 'sys/class/tpm/tpm0').mkdir(parents=True)


def results(box, profiles):
    return cp.check(box.system(), profiles)


def failures(box, profiles):
    return [f'{name}: {detail}' for status, name, detail in results(box, profiles)
            if status == 'FAIL']


def test_check_passes_on_a_box_that_matches(box, profiles):
    healthy_n97(box, profiles)
    assert failures(box, profiles) == []
    assert any(s == 'MANUAL' for s, _, _ in results(box, profiles))


def test_check_says_the_profile_is_not_accepted(box, profiles):
    healthy_n97(box, profiles)
    assert any(s == 'MANUAL' and 'not accepted' in d for s, _, d in results(box, profiles))


@pytest.mark.parametrize('extra', ['pci=nommconf', 'i915.enable_dc=0', 'systemd.mask=x.service'])
def test_check_fails_on_a_kernel_parameter_no_profile_declares(box, profiles, extra):
    healthy_n97(box, profiles)
    box.write('proc/cmdline', f'root=UUID=x ro quiet splash {extra}\n')
    assert any(extra in f for f in failures(box, profiles))


def test_check_fails_on_a_modprobe_option_no_profile_declares(box, profiles):
    healthy_n97(box, profiles)
    box.write('etc/modprobe.d/old.conf', '# c\noptions amdgpu dpm=0\nblacklist ftdi_sio\n')
    found = failures(box, profiles)
    assert len(found) == 1 and 'options amdgpu dpm=0' in found[0]


def test_check_accepts_a_duplicate_of_a_declared_option(box, profiles):
    healthy_n97(box, profiles)
    box.write('etc/modprobe.d/alsa-card-order.conf',
              'options snd_hda_intel index=0\noptions snd_usb_audio index=1\n')
    assert failures(box, profiles) == []


def test_check_reads_past_a_comment_at_the_end_of_an_option_line(box, profiles):
    """Seen on a rig: `options snd_usb_audio index=2 # why`."""
    healthy_n97(box, profiles)
    box.write('etc/modprobe.d/alsa-card-order.conf',
              'options snd_usb_audio index=1 # two HDA cards\n')
    assert failures(box, profiles) == []


def test_check_fails_when_a_port_name_is_not_in_force(box, profiles):
    healthy_n97(box, profiles)
    os.rmdir(box.root / 'sys/bus/pci/devices/0000:02:00.0/net/ethernet0')
    assert any('ethernet0' in f for f in failures(box, profiles))


def test_check_fails_on_the_package_default_link_file(box, profiles):
    healthy_n97(box, profiles)
    box.write('etc/systemd/network/10-ethernet0.link',
              '[Match]\nPath=pci-0000:01:00.0\n\n[Link]\nName=ethernet0\n')
    assert any('10-ethernet0.link' in f for f in failures(box, profiles))


def test_check_fails_on_missing_firmware(box, profiles):
    healthy_n97(box, profiles)
    box.installed.discard('firmware-realtek')
    assert any('firmware-realtek' in f for f in failures(box, profiles))


def test_check_fails_on_a_small_gpu_aperture(box, profiles):
    healthy_n97(box, profiles)
    box.write('sys/bus/pci/devices/0000:00:02.0/resource',
              '0x0 0x0 0x0\n0x0 0x0 0x0\n0x0000004000000000 0x000000400fffffff 0x14220c\n')
    assert any('aperture' in f and '256' in f for f in failures(box, profiles))


def test_check_fails_when_the_gpu_pin_is_off_on_an_fp530(box, profiles):
    fp530(box)
    apply(box, profiles)
    box.write('etc/cuems/gpu-pin.conf', GPU_PIN_AS_SHIPPED)
    assert any('gpu pin' in f for f in failures(box, profiles))


def test_check_exit_code(box, profiles, capsys):
    healthy_n97(box, profiles)
    run = lambda: cp.main(['check'], system=box.system(), profile_dir=PROFILES)
    assert run() == 0
    box.write('proc/cmdline', 'root=UUID=x ro pci=nommconf\n')
    assert run() == 1
    assert 'FAIL' in capsys.readouterr().out


@pytest.mark.parametrize('device, bad', [
    ('hw:Analog,0', False), ('hw:0,0', False), ('multi_hdmi', False), ('hw:PCH,0', True),
])
def test_check_fails_when_jack_names_a_card_that_is_not_there(box, profiles, device, bad):
    healthy_n97(box, profiles)
    jack_file(box, device)
    assert any(f.startswith('JACK') for f in failures(box, profiles)) is bad


def test_check_prints_a_line_for_an_unreadable_video_memory(box, profiles):
    fp530(box)
    (box.root / 'sys/class/drm/card0/device/mem_info_vram_total').mkdir(parents=True)
    assert ('MANUAL', 'BIOS video memory') in [(s, n) for s, n, _ in results(box, profiles)]
