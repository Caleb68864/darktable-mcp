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

    server.get_preview(500)  # warm the pipeline so renders are stable
    before = hashlib.md5(server.get_preview(500).data).hexdigest()
    server.adjust("brightness", "up", 30)
    after = hashlib.md5(server.get_preview(500).data).hexdigest()
    server.reset_current()
    assert before != after, "preview did not reflect the exposure change"


def test_live_rating_and_tag_roundtrip():
    """Rating and tag writes land and are reversible (restores original state)."""
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

    original = server.get_labels()["result"]["rating"]
    server.set_rating(3)
    assert server.get_labels()["result"]["rating"] == 3

    server.add_tag("dtmcp_pytest_tag")
    assert "dtmcp_pytest_tag" in server.get_tags()["result"]["tags"]
    server.remove_tag("dtmcp_pytest_tag")
    assert "dtmcp_pytest_tag" not in server.get_tags()["result"]["tags"]

    server.set_rating(original)  # restore


def test_live_geotag_and_style_management():
    """Geotag round-trips and style import/export/delete work end to end."""
    import os
    import tempfile

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

    # geotag round-trip
    server.set_location(51.5, -0.12, 20.0)
    gps = server.get_metadata()["result"]["gps"]
    assert round(gps["latitude"], 1) == 51.5
    # clear
    b.raw_lua(
        "local dt=require'darktable'; local i=dt.database[1]; "
        "i.latitude=nil; i.longitude=nil; i.elevation=nil; return 'ok'"
    )

    # export a known style, confirm the file, delete it from disk
    styles = [s["name"] for s in server.list_styles()["result"]["styles"]]
    if styles:
        name = styles[0]
        d = tempfile.gettempdir()
        server.export_style(name, d.replace("\\", "/"))
        path = os.path.join(d, f"{name}.dtstyle")
        assert os.path.exists(path)
        os.remove(path)
