# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
"""cuems-generate-display-conf: the operator override is copied byte for byte.

Pins today's behaviour, which per-output color relies on: whenever
/etc/cuems/display.conf exists it is copied verbatim to /run/cuems and the XML
is NOT read (the override freezes the host's layout). Hermetic: every path is
monkeypatched into a temp dir. Run on a rig, never on casas.
"""

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # no __pycache__ next to the shipped script

REPO = Path(__file__).resolve().parent.parent
BIN_DIR = Path(os.environ.get('CUEMS_COMMON_BIN', REPO / 'usr/lib/cuems/bin'))
SCRIPT = BIN_DIR / 'cuems-generate-display-conf'

OVERRIDE = (
    b'# Authored by cuems-display-setup on 2026-10-26T12:00:00\n'
    b'canvas_layout=custom\n'
    b'\n'
    b'[output:HDMI-A-1]\r\n'
    b'canvas_region=0,0,1920,1080\n'
    b'resolution=1920x1080\n'
    b'refresh=30\n'
    b'enabled = false\n'
    b'  # a comment inside a section\n'
    b'blend=0.1,0,0,0,2.2\n'
    b'color_brightness=0.02\r\n'
    b'color_lut=caf\xc3\xa9-\xff.cube\n'
    b'future_key = 1 2 3'
)

MAPPINGS = """<?xml version='1.0' encoding='utf-8'?>
<cms:CuemsProjectMappings xmlns:cms="https://stagelab.coop/cuems/">
    <nodes>
        <node>
            <uuid>uuid-1</uuid>
            <video>
                <outputs>
                    <output>
                        <id>0</id>
                        <name>Left</name>
                        <mappings><mapped_to>HDMI-A-1</mapped_to></mappings>
                    </output>
                    <output>
                        <id>1</id>
                        <name>Right</name>
                        <mappings><mapped_to>HDMI-A-2</mapped_to></mappings>
                    </output>
                </outputs>
            </video>
        </node>
    </nodes>
</cms:CuemsProjectMappings>
"""


def _load():
    # The script is hyphenated and has no extension: import it by path.
    name = 'cuems_generate_display_conf'
    loader = importlib.machinery.SourceFileLoader(name, str(SCRIPT))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def gen(tmp_path, monkeypatch):
    m = _load()
    run_dir = tmp_path / 'run/cuems'
    monkeypatch.setattr(m, 'OUTPUT_DIR', str(run_dir))
    monkeypatch.setattr(m, 'OUTPUT_FILE', str(run_dir / 'display.conf'))
    monkeypatch.setattr(m, 'OPERATOR_OVERRIDE',
                        str(tmp_path / 'etc/display.conf'))
    monkeypatch.setattr(m, 'MAPPINGS_XML',
                        str(tmp_path / 'etc/default_mappings.xml'))
    monkeypatch.setattr(m, 'SETTINGS_XML', str(tmp_path / 'etc/settings.xml'))
    (tmp_path / 'etc').mkdir()
    return m


def test_copy_operator_override_is_byte_for_byte(gen):
    Path(gen.OPERATOR_OVERRIDE).write_bytes(OVERRIDE)
    gen.copy_operator_override()
    assert Path(gen.OUTPUT_FILE).read_bytes() == OVERRIDE
    assert os.listdir(gen.OUTPUT_DIR) == ['display.conf']  # no temp left


def test_override_replaces_a_previous_runtime_file(gen):
    Path(gen.OUTPUT_DIR).mkdir(parents=True)
    Path(gen.OUTPUT_FILE).write_bytes(b'stale\n' * 100)
    Path(gen.OPERATOR_OVERRIDE).write_bytes(OVERRIDE)
    gen.copy_operator_override()
    assert Path(gen.OUTPUT_FILE).read_bytes() == OVERRIDE


def test_main_with_override_does_not_read_the_xml(gen, monkeypatch):
    Path(gen.OPERATOR_OVERRIDE).write_bytes(OVERRIDE)
    Path(gen.MAPPINGS_XML).write_text(MAPPINGS, encoding='utf-8')

    def must_not_run(*args, **kwargs):
        raise AssertionError('the XML was read although an override exists')

    monkeypatch.setattr(gen, 'parse_video_outputs', must_not_run)
    assert gen.main() == 0
    assert Path(gen.OUTPUT_FILE).read_bytes() == OVERRIDE


def test_main_without_override_emits_canvas_region_only(gen):
    Path(gen.MAPPINGS_XML).write_text(MAPPINGS, encoding='utf-8')
    assert gen.main() == 0
    assert Path(gen.OUTPUT_FILE).read_text() == (
        '# Auto-generated from {}\n'.format(gen.MAPPINGS_XML)
        + 'canvas_layout=custom\n\n'
        + '[output:HDMI-A-1]\ncanvas_region=0,0,1920,1080\n\n'
        + '[output:HDMI-A-2]\ncanvas_region=1920,0,1920,1080\n\n')
