"""Tes tidak boleh melihat atau menulis ke flashdisk asli yang kebetulan tertancap."""
import pytest

from backend import dongle_guard


@pytest.fixture(autouse=True)
def hide_real_drives(monkeypatch):
    monkeypatch.setattr(dongle_guard.psutil, "disk_partitions", lambda all=False: [])
