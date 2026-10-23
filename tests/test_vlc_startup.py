"""Exercise cold VLC discovery rather than an already initialized player."""
import builtins
import os
from types import SimpleNamespace

import pytest

from ui import player


def test_availability_prepares_bundle_before_first_import(monkeypatch, tmp_path):
    runtime = tmp_path / "_internal" / "vlc"
    (runtime / "plugins").mkdir(parents=True)
    (runtime / "libvlc.dll").write_bytes(b"test")
    monkeypatch.setattr(player.sys, "_MEIPASS", str(runtime.parent), raising=False)
    monkeypatch.setattr(player.sys, "platform", "test")
    monkeypatch.setattr(player, "_instance", None)
    monkeypatch.setattr(player, "_log_sink", None)
    for name in ("PYTHON_VLC_LIB_PATH", "PYTHON_VLC_MODULE_PATH", "VLC_PLUGIN_PATH"):
        monkeypatch.delenv(name, raising=False)
    original_import = builtins.__import__
    imports = []
    fake_instance = object()

    def cold_import(name, *args, **kwargs):
        if name == "vlc":
            # This assertion fails on the released availability entry point.
            assert os.environ.get("PYTHON_VLC_LIB_PATH") == str(runtime / "libvlc.dll")
            assert os.environ.get("PYTHON_VLC_MODULE_PATH") == str(runtime)
            assert os.environ.get("VLC_PLUGIN_PATH") == str(runtime / "plugins")
            imports.append(name)
            return SimpleNamespace(Instance=lambda *args: fake_instance)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", cold_import)
    assert player.available() == (True, "")
    assert imports
    assert player._instance is fake_instance


@pytest.mark.parametrize("failure", [ImportError("missing binding"), OSError("missing DLL")])
def test_unavailable_vlc_is_reported_without_crashing(monkeypatch, failure):
    monkeypatch.setattr(player, "_instance", None)

    def fail():
        raise failure

    monkeypatch.setattr(player, "_import_vlc", fail)
    ok, reason = player.available()
    assert not ok
    assert reason
    assert player._libvlc() is None
