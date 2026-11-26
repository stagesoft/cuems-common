# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
"""cuems-hdmi-audio-map: a box with no screen is not a failed box.

Hermetic: DRM and /proc/asound are never touched.

    /usr/lib/cuems/bin/python3 -B -m pytest -p no:cacheprovider tests/test_hdmi_audio_map.py
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # no __pycache__ next to the shipped script

SCRIPT = Path(__file__).resolve().parent.parent / 'usr/bin/cuems-hdmi-audio-map'


@pytest.fixture
def tool(tmp_path, monkeypatch):
    loader = importlib.machinery.SourceFileLoader('cuems_hdmi_audio_map', str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    conf = tmp_path / 'asound.conf'
    conf.write_text('previous\n')
    monkeypatch.setattr(module, 'ASOUND_CONF', str(conf))
    monkeypatch.setattr(module, 'detect_hda_card', lambda: 'Analog')
    monkeypatch.setattr(sys, 'argv', ['cuems-hdmi-audio-map'])
    module.conf = conf
    return module


def test_no_screen_succeeds_and_leaves_asound_conf(tool, monkeypatch):
    monkeypatch.setattr(tool, 'detect_mapping', lambda: [])
    tool.main()  # no SystemExit: the unit does not fail
    assert tool.conf.read_text() == 'previous\n'


def test_no_drm_device_succeeds_and_leaves_asound_conf(tool, monkeypatch):
    def gone():
        raise FileNotFoundError(2, 'No such file or directory', '/dev/dri/card0')
    monkeypatch.setattr(tool, 'detect_mapping', gone)
    tool.main()
    assert tool.conf.read_text() == 'previous\n'


def test_any_other_error_still_fails(tool, monkeypatch):
    def broken():
        raise PermissionError(13, 'Permission denied', '/dev/dri/card0')
    monkeypatch.setattr(tool, 'detect_mapping', broken)
    with pytest.raises(PermissionError):
        tool.main()


def test_a_screen_writes_the_mapping(tool, monkeypatch):
    monkeypatch.setattr(tool, 'detect_mapping', lambda: [('HDMI-A-1', 3)])
    tool.main()
    assert 'pcm "hw:Analog,3"' in tool.conf.read_text()
