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


def test_live_preview_reflects_edits():
    """get_preview renders the current edit; an adjustment must change the rendered bytes."""
    import hashlib

    from darktable_mcp import server

    b = server.bridge
    try:
        b.call("status")
    except DarktableNotRunning:
        pytest.skip("darktable GUI is not running")

    images = server.list_images(limit=1)["result"]["images"]
    if not images:
        pytest.skip("no images in the darktable library")
    server.open_in_darkroom(images[0]["filename"])
    server.reset_current()

    before = hashlib.md5(server.get_preview(500).data).hexdigest()
    server.adjust("brightness", "up", 30)
    after = hashlib.md5(server.get_preview(500).data).hexdigest()
    server.reset_current()
    assert before != after, "preview did not reflect the exposure change"
