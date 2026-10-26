# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
"""cuems-display-setup: re-authoring display.conf preserves what it does not own.

Hermetic: every path the tool touches is monkeypatched into a temp dir, the
operator's answers are injected, no real /etc, no DRM probe, no systemctl.
Run on a rig, never on casas:

    /usr/lib/cuems/bin/python3 -B -m pytest -p no:cacheprovider tests/

CUEMS_COMMON_BIN=<dir> points the tests at another copy of the scripts
(default: usr/lib/cuems/bin of this checkout).
"""

import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # no __pycache__ next to the shipped script

REPO = Path(__file__).resolve().parent.parent
BIN_DIR = Path(os.environ.get('CUEMS_COMMON_BIN', REPO / 'usr/lib/cuems/bin'))
SCRIPT = BIN_DIR / 'cuems-display-setup'
VENV_XSD = ('/usr/lib/cuems/lib/python3.11/site-packages/'
            'cuemsutils/xml/schemas/project_mappings.xsd')
TS = '2026-10-26T12:00:00'
HEADER = f'# Authored by cuems-display-setup on {TS}\n'


def _load():
    # The script is hyphenated and has no extension: import it by path.
    loader = importlib.machinery.SourceFileLoader('cuems_display_setup',
                                                  str(SCRIPT))
    spec = importlib.util.spec_from_loader('cuems_display_setup', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def mod(tmp_path, monkeypatch):
    m = _load()
    # Nothing may reach the real /etc or /tmp of the host.
    monkeypatch.setattr(m, 'DISPLAY_CONF', str(tmp_path / 'etc/display.conf'))
    monkeypatch.setattr(m, 'DEFAULT_MAPPINGS_XML',
                        str(tmp_path / 'etc/default_mappings.xml'))
    monkeypatch.setattr(m, 'SETTINGS_XML', str(tmp_path / 'etc/settings.xml'))
    monkeypatch.setattr(m, 'MASTER_IP_SENTINEL', str(tmp_path / 'etc/master.ip'))
    monkeypatch.setattr(m, 'SHOW_LOCK_PATH', str(tmp_path / 'cuems.show.lock'))
    (tmp_path / 'etc').mkdir()
    return m


def _outputs(*names):
    return [{'card': 'card0', 'connector': n, 'modes': [], 'edid_name': None}
            for n in names]


def _never_asked(*args):
    raise AssertionError(f'unexpected question: {args!r}')


def _run(mod, text, names, resolutions, regions, canvas_size=None,
         ask_drop=_never_asked, ask_keep=_never_asked):
    """One non-interactive run: parse, review (injected answers), compose."""
    outputs = _outputs(*names)
    conf = None
    if text is not None:
        conf = mod.parse_display_conf_raw(text)
        mod.review_existing_sections(conf, outputs, resolutions, regions,
                                     ask_drop_section=ask_drop,
                                     ask_keep_line=ask_keep)
    return mod.compose_display_conf(outputs, resolutions, regions,
                                    canvas_size, existing=conf, timestamp=TS)


def _keys(mod, text):
    return [mod.line_key(raw) for raw in mod.split_raw_lines(text)]


# ---------------------------------------------------------------------------
# Fresh file and unchanged re-runs
# ---------------------------------------------------------------------------


def test_fresh_file_format_unchanged(mod):
    out = _run(mod, None, ['HDMI-A-1', 'HDMI-A-2'],
               ['1920x1080', '1280x720'],
               [(0, 0, 1920, 1080), (1920, 0, 1280, 720)])
    assert out == (HEADER
                   + 'canvas_layout=custom\n'
                   + '\n'
                   + '[output:HDMI-A-1]\n'
                   + 'canvas_region=0,0,1920,1080\n'
                   + 'resolution=1920x1080\n'
                   + '\n'
                   + '[output:HDMI-A-2]\n'
                   + 'canvas_region=1920,0,1280,720\n'
                   + 'resolution=1280x720\n')


def test_fresh_file_with_canvas_size(mod):
    out = _run(mod, None, ['HDMI-A-1'], ['1920x1080'], [(0, 0, 1920, 1080)],
               canvas_size=(3840, 1080))
    assert out.startswith(HEADER + 'canvas_layout=custom\n'
                          'canvas_size=3840x1080\n\n[output:HDMI-A-1]\n')


def test_rerun_on_own_output_is_identical(mod):
    args = (['HDMI-A-1', 'HDMI-A-2'], ['1920x1080', '1280x720'],
            [(0, 0, 1920, 1080), (1920, 0, 1280, 720)])
    first = _run(mod, None, *args, canvas_size=(4000, 1080))
    second = _run(mod, first, *args, canvas_size=(4000, 1080))
    assert second == first


# ---------------------------------------------------------------------------
# Raw lines, byte for byte
# ---------------------------------------------------------------------------

# Owned lines are canonical (column 0, LF) and the geometry is unchanged, so
# a run must give back exactly these bytes: spaced keys, CRLF lines, a
# comment inside a section, unknown keys, color_*, a UTF-8 and a non-UTF-8
# byte, and a last line without a terminator.
ROUND_TRIP = (
    HEADER.encode()
    + b'canvas_layout=custom\n'
    + b'resolution_policy=native\n'
    + b'future_global = something\n'
    + b'\n'
    + b'[output:HDMI-A-1]\n'
    + b'canvas_region=0,0,1920,1080\n'
    + b'resolution=1920x1080\n'
    + b'refresh=30\n'
    + b'enabled = false\n'
    + b'  # operator note inside a section\n'
    + b'blend=0.1,0,0,0,2.2\n'
    + b'color_brightness=0.02\r\n'
    + b'color_lut=caf\xc3\xa9-\xff.cube\n'
    + b'future_key = 1 2 3\n'
    + b'\n'
    + b'[output:HDMI-A-2]\r\n'
    + b'canvas_region=1920,0,1920,1080\n'
    + b'resolution=1920x1080\n'
    + b'color_gamma=1.05\r\n'
    + b'color_hue=-3'
)


def test_raw_lines_round_trip_byte_for_byte(mod):
    conf_path = Path(mod.DISPLAY_CONF)
    conf_path.write_bytes(ROUND_TRIP)
    text = mod.read_display_conf_raw()
    out = _run(mod, text, ['HDMI-A-1', 'HDMI-A-2'],
               ['1920x1080', '1920x1080'],
               [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)])
    mod.install_display_conf(out, no_backup=True)
    assert conf_path.read_bytes() == ROUND_TRIP
    assert [p.name for p in conf_path.parent.iterdir()] == ['display.conf']


def test_enabled_with_spaces_is_never_normalised(mod):
    text = ('[output:HDMI-A-1]\n'
            'canvas_region=0,0,1920,1080\n'
            'resolution=1920x1080\n'
            'enabled = false\n')
    out = _run(mod, text, ['HDMI-A-1'], ['1280x720'], [(0, 0, 1280, 720)])
    assert 'enabled = false\n' in out
    assert 'enabled=false' not in out


def test_crlf_lines_kept_and_own_lines_lf(mod):
    text = ('[output:HDMI-A-1]\r\n'
            'canvas_region=0,0,3840,2160\r\n'
            'resolution=3840x2160\r\n'
            'color_hue=-3\r\n')
    out = _run(mod, text, ['HDMI-A-1'], ['1920x1080'], [(0, 0, 1920, 1080)])
    # The VC compares some values untrimmed (canvas_layout=custom\r is not
    # "custom"), so the tool's own lines are LF even in a CRLF file.
    assert out == (HEADER
                   + 'canvas_layout=custom\n'
                   + '[output:HDMI-A-1]\r\n'
                   + 'canvas_region=0,0,1920,1080\n'
                   + 'resolution=1920x1080\n'
                   + 'color_hue=-3\r\n')


# ---------------------------------------------------------------------------
# Owned keys: recognised stripped, replaced, never duplicated (r7)
# ---------------------------------------------------------------------------


def test_spaced_owned_key_replaced_not_duplicated(mod):
    text = ('# Authored by cuems-display-setup on 2026-01-01T00:00:00\n'
            'canvas_layout = custom\n'
            ' canvas_size=9999x9999\n'
            '\n'
            '[output:HDMI-A-1]\n'
            'canvas_region = 0,0,1920,1080\n'
            'refresh=50\n'
            '  resolution=1920x1080\n'
            'canvas_region=7,7,7,7\n')
    out = _run(mod, text, ['HDMI-A-1'], ['1920x1080'], [(0, 0, 1920, 1080)],
               ask_keep=lambda c, line: True)
    assert out == (HEADER
                   + 'canvas_layout=custom\n'
                   + '\n'
                   + '[output:HDMI-A-1]\n'
                   + 'canvas_region=0,0,1920,1080\n'
                   + 'resolution=1920x1080\n'
                   + 'refresh=50\n')
    keys = _keys(mod, out)
    for key in ('canvas_region', 'resolution', 'canvas_layout'):
        assert keys.count(key) == 1, key
    assert 'canvas_size' not in keys


def test_absent_section_spaced_owned_key_made_canonical(mod, capsys):
    text = ('[output:HDMI-A-1]\n'
            'canvas_region=0,0,1920,1080\n'
            'resolution=1920x1080\n'
            '\n'
            '[output:HDMI-A-3]\n'
            'canvas_region = 1920,0,1920,1080\n'
            'color_gamma=1.1\n'
            'resolution=1920x1080\n')
    out = _run(mod, text, ['HDMI-A-1'], ['1920x1080'], [(0, 0, 1920, 1080)],
               ask_drop=lambda c: False)
    assert out.endswith('[output:HDMI-A-3]\n'
                        'canvas_region=1920,0,1920,1080\n'
                        'resolution=1920x1080\n'
                        'color_gamma=1.1\n')
    assert 'canvas_region = ' not in out
    assert 'rewritten as one canonical line' in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The tool's header
# ---------------------------------------------------------------------------


def test_one_header_line_after_three_runs(mod):
    text = ('# Authored by cuems-display-setup on 2026-01-01T00:00:00\n'
            '# Authored by cuems-display-setup on 2026-01-02T00:00:00\n'
            '# a comment of the operator\n'
            'canvas_layout=custom\n')
    args = (['HDMI-A-1'], ['1920x1080'], [(0, 0, 1920, 1080)])
    for _ in range(3):
        text = _run(mod, text, *args)
    lines = mod.split_raw_lines(text)
    headers = [ln for ln in lines if ln.startswith('# Authored by')]
    assert headers == [HEADER]
    assert lines[0] == HEADER
    assert '# a comment of the operator\n' in lines


# ---------------------------------------------------------------------------
# Connectors not detected now (t12)
# ---------------------------------------------------------------------------

ABSENT = (HEADER
          + 'canvas_layout=custom\n'
          + '\n'
          + '[output:HDMI-A-1]\n'
          + 'canvas_region=0,0,1920,1080\n'
          + 'resolution=1920x1080\n'
          + '\n'
          + '[output:HDMI-A-3]\n'
          + 'canvas_region=1920,0,1920,1080\n'
          + 'resolution=1920x1080\n'
          + 'refresh=30\n'
          + 'color_lut=p2.cube\n')


def test_absent_connector_section_kept(mod, capsys):
    asked = []
    out = _run(mod, ABSENT, ['HDMI-A-1'], ['1920x1080'],
               [(0, 0, 1920, 1080)],
               ask_drop=lambda c: asked.append(c) or False)
    assert out == ABSENT
    assert asked == ['HDMI-A-3']
    assert 'HDMI-A-3 not detected now -- section kept' in capsys.readouterr().out


def test_absent_connector_dropped_only_on_drop(mod):
    out = _run(mod, ABSENT, ['HDMI-A-1'], ['1920x1080'],
               [(0, 0, 1920, 1080)], ask_drop=lambda c: True)
    assert 'HDMI-A-3' not in out
    assert 'color_lut' not in out
    assert '[output:HDMI-A-1]\ncanvas_region=0,0,1920,1080\n' in out


def test_new_connector_appended_after_kept_sections(mod):
    out = _run(mod, ABSENT, ['HDMI-A-1', 'HDMI-A-2'],
               ['1920x1080', '1280x720'],
               [(0, 0, 1920, 1080), (1920, 0, 1280, 720)],
               ask_drop=lambda c: False)
    assert out == (ABSENT
                   + '\n'
                   + '[output:HDMI-A-2]\n'
                   + 'canvas_region=1920,0,1280,720\n'
                   + 'resolution=1280x720\n')


def test_default_drop_asker(mod, monkeypatch):
    answers = iter(['maybe', 'drop'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(answers))
    assert mod._ask_drop_section('HDMI-A-3') is True
    monkeypatch.setattr('builtins.input', lambda _prompt: '')
    assert mod._ask_drop_section('HDMI-A-3') is False


# ---------------------------------------------------------------------------
# Geometry change: refresh=/blend= asked, color_* kept without a question
# ---------------------------------------------------------------------------

CHANGED = ('[output:HDMI-A-2]\n'
           'canvas_region=0,0,3840,2160\n'
           'resolution=3840x2160\n'
           'refresh=30\n'
           'blend=0.1,0,0,0,2.2\n'
           'color_brightness=0.02\n'
           'color_lut=p2-christie.cube\n')


def test_resolution_change_asks_refresh_and_blend_not_color(mod, capsys):
    asked = []

    def ask_keep(connector, line):
        asked.append((connector, line))
        return not line.startswith('refresh')

    out = _run(mod, CHANGED, ['HDMI-A-2'], ['1920x1080'],
               [(0, 0, 1920, 1080)], ask_keep=ask_keep)
    assert asked == [('HDMI-A-2', 'refresh=30'),
                     ('HDMI-A-2', 'blend=0.1,0,0,0,2.2')]
    assert out == (HEADER
                   + 'canvas_layout=custom\n'
                   + '[output:HDMI-A-2]\n'
                   + 'canvas_region=0,0,1920,1080\n'
                   + 'resolution=1920x1080\n'
                   + 'blend=0.1,0,0,0,2.2\n'
                   + 'color_brightness=0.02\n'
                   + 'color_lut=p2-christie.cube\n')
    printed = capsys.readouterr().out
    assert 'carried "refresh=30"' in printed
    assert 'color_brightness, color_lut' in printed


def test_region_change_alone_also_asks(mod):
    asked = []
    _run(mod, CHANGED, ['HDMI-A-2'], ['3840x2160'], [(3840, 0, 3840, 2160)],
         ask_keep=lambda c, line: asked.append(line) or True)
    assert asked == ['refresh=30', 'blend=0.1,0,0,0,2.2']


def test_unchanged_geometry_asks_nothing(mod, capsys):
    out = _run(mod, CHANGED, ['HDMI-A-2'], ['3840x2160'],
               [(0, 0, 3840, 2160)])
    assert out == HEADER + 'canvas_layout=custom\n' + CHANGED
    assert 'NOTICE' not in capsys.readouterr().out


def test_default_keep_asker(mod, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _prompt: '')
    assert mod._ask_keep_line('HDMI-A-2', 'refresh=30') is True
    monkeypatch.setattr('builtins.input', lambda _prompt: 'n')
    assert mod._ask_keep_line('HDMI-A-2', 'refresh=30') is False


# ---------------------------------------------------------------------------
# --update-mappings (r14): venv schema, validate before replacing, no crash
# without xmllint
# ---------------------------------------------------------------------------

MAPPINGS = """<?xml version='1.0' encoding='utf-8'?>
<cms:CuemsProjectMappings xmlns:cms="https://stagelab.coop/cuems/">
    <number_of_nodes>1</number_of_nodes>
    <default_audio_input />
    <default_audio_output />
    <default_video_input />
    <default_video_output>uuid-1_0</default_video_output>
    <default_dmx_input />
    <default_dmx_output />
    <nodes>
        <node>
            <uuid>uuid-1</uuid>
            <mac>2cf05d21cca3</mac>
            <video>
                <outputs>
                    <output>
                        <id>0</id>
                        <name>Left</name>
                        <mappings>
                            <mapped_to>HDMI-A-1</mapped_to>
                        </mappings>
                    </output>
                </outputs>
            </video>
        </node>
    </nodes>
    <new_nodes />
</cms:CuemsProjectMappings>
"""


@pytest.fixture
def mappings(mod, tmp_path):
    path = Path(mod.DEFAULT_MAPPINGS_XML)
    path.write_text(MAPPINGS, encoding='utf-8')
    return path


def _fake_bin(tmp_path, monkeypatch, xmllint_script=None):
    """PATH holds only a temp dir, with a fake xmllint or none at all."""
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    if xmllint_script is not None:
        tool = bindir / 'xmllint'
        tool.write_text(xmllint_script)
        tool.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir))


def _leftovers(path):
    return sorted(p.name for p in path.parent.iterdir()
                  if p.name != path.name and p.name.startswith(path.name))


def test_mappings_schema_is_the_venv_copy(mod):
    assert mod.PROJECT_MAPPINGS_XSD == VENV_XSD
    assert not mod.PROJECT_MAPPINGS_XSD.startswith('/etc/')


def test_validation_runs_xmllint_on_the_venv_schema(mod, tmp_path,
                                                    monkeypatch):
    xsd = tmp_path / 'project_mappings.xsd'
    xsd.write_text('<schema/>')
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(xsd))
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '', '')

    monkeypatch.setattr(mod.subprocess, 'run', fake_run)
    assert mod.validate_mappings_xml('/x/m.xml') is True
    assert calls == [['xmllint', '--noout', '--schema', str(xsd), '/x/m.xml']]


def test_validation_finds_schema_by_glob(mod, tmp_path, monkeypatch):
    found = tmp_path / 'lib/python3.13/schemas/project_mappings.xsd'
    found.parent.mkdir(parents=True)
    found.write_text('<schema/>')
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(tmp_path / 'none'))
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD_GLOB',
                        str(tmp_path / 'lib/python3*/schemas/project_mappings.xsd'))
    assert mod.find_project_mappings_xsd() == str(found)


def test_validation_skipped_without_schema(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(tmp_path / 'none'))
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD_GLOB', str(tmp_path / 'no*'))
    monkeypatch.setattr(mod.subprocess, 'run', _never_asked)
    assert mod.validate_mappings_xml('/x/m.xml') is None
    assert 'skipping validation' in capsys.readouterr().out


def test_update_mappings_survives_missing_xmllint(mod, mappings, tmp_path,
                                                  monkeypatch, capsys):
    xsd = tmp_path / 'project_mappings.xsd'
    xsd.write_text('<schema/>')
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(xsd))
    _fake_bin(tmp_path, monkeypatch, xmllint_script=None)
    mod.update_default_mappings('HDMI-A-2', 'Right')
    xml = mappings.read_text(encoding='utf-8')
    assert '<mapped_to>HDMI-A-2</mapped_to>' in xml
    assert '<id>1</id>' in xml
    assert 'cannot run xmllint' in capsys.readouterr().out
    left = _leftovers(mappings)
    assert len(left) == 1 and left[0].startswith('default_mappings.xml.bak-')


def test_update_mappings_invalid_leaves_original(mod, mappings, tmp_path,
                                                 monkeypatch, capsys):
    xsd = tmp_path / 'project_mappings.xsd'
    xsd.write_text('<schema/>')
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(xsd))
    _fake_bin(tmp_path, monkeypatch,
              xmllint_script='#!/bin/sh\necho "fake schema error" >&2\nexit 1\n')
    before = mappings.read_bytes()
    with pytest.raises(SystemExit) as exc:
        mod.update_default_mappings('HDMI-A-2', 'Right')
    assert 'NOT changed' in str(exc.value)
    assert mappings.read_bytes() == before
    assert _leftovers(mappings) == []  # no temp file, no backup
    assert 'fake schema error' in capsys.readouterr().out


def _real_schema():
    if os.path.isfile(VENV_XSD):
        return VENV_XSD
    spec = importlib.util.find_spec('cuemsutils')
    if spec is None or not spec.submodule_search_locations:
        return None
    path = (Path(list(spec.submodule_search_locations)[0])
            / 'xml/schemas/project_mappings.xsd')
    return str(path) if path.is_file() else None


def test_update_mappings_passes_the_real_venv_schema(mod, mappings, tmp_path,
                                                     monkeypatch, capsys):
    schema = _real_schema()
    if schema is None or shutil.which('xmllint') is None:
        pytest.skip('needs xmllint and the cuemsutils schema (run on a rig)')
    copy = tmp_path / 'project_mappings.xsd'
    shutil.copy(schema, copy)
    monkeypatch.setattr(mod, 'PROJECT_MAPPINGS_XSD', str(copy))
    mod.update_default_mappings('HDMI-A-2', 'Right')
    assert 'xmllint --schema passed' in capsys.readouterr().out
    xml = mappings.read_text(encoding='utf-8')
    assert '<id>1</id>' in xml and '<mapped_to>HDMI-A-2</mapped_to>' in xml


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------


def test_shipped_executable_in_debian_install():
    install = REPO / 'debian/install'
    if not install.is_file():
        pytest.skip('debian/install not in this copy')
    lines = [ln.split() for ln in install.read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith('#')]
    assert ['usr/lib/cuems/bin/cuems-display-setup',
            'usr/lib/cuems/bin/'] in lines
    assert os.access(SCRIPT, os.X_OK)
