"""Opt-in smoke test against a live darktable GUI.

Run with:  pytest -m integration
Requires the darktable GUI to be open. Does not modify any image (it only reads status/styles).
"""

import pytest

from darktable_mcp.bridge import Bridge, DarktableNotRunning

pytestmark = pytest.mark.integration


def test_live_status():
    b = Bridge()
    try:
        status = b.call("status")
    except DarktableNotRunning:
        pytest.skip("darktable GUI is not running")
    assert "version" in status
    assert isinstance(status.get("images"), int)


def test_live_list_styles():
    b = Bridge()
    try:
        result = b.call("list_styles")
    except DarktableNotRunning:
        pytest.skip("darktable GUI is not running")
    assert "styles" in result
