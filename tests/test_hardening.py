"""Hardening tests: every failure path is caught and returns something diagnosable."""

import subprocess

import pytest

import darktable_mcp.bridge as bridge_mod
from darktable_mcp import server
from darktable_mcp.bridge import (
    Bridge,
    DarktableError,
    DarktableLuaError,
    DarktableNotRunning,
    DarktableTimeout,
)


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# -- bridge error classification -------------------------------------------

def test_timeout_is_diagnosable(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="gdbus", timeout=k.get("timeout", 30))

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableTimeout) as exc:
        Bridge(gdbus="gdbus").raw_lua("return 1")
    assert "DARKTABLE_MCP_TIMEOUT" in exc.value.hint


def test_crash_midsession_reports_lock_hint(monkeypatch):
    b = Bridge(gdbus="gdbus")
    b._helper_loaded = True  # we had a working session
    monkeypatch.setattr(bridge_mod, "_lock_files", lambda: [r"C:\x\library.db.lock"])

    def fake_run(*a, **k):
        return _completed(
            stderr="Error: GDBus.Error:org.freedesktop.DBus.Error.ServiceUnknown: "
            "The name org.darktable.service is unknown",
            returncode=1,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableNotRunning) as exc:
        b.raw_lua("return 1")
    assert "library.db.lock" in exc.value.hint
    assert b._helper_loaded is False  # reset so a reconnect re-bootstraps


def test_missing_gdbus_has_hint(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableError) as exc:
        Bridge(gdbus="nope").raw_lua("return 1")
    assert "DARKTABLE_BIN_DIR" in exc.value.hint


# -- server _guard never raises, always structured -------------------------

def test_guard_catches_arbitrary_exception():
    def boom():
        raise ValueError("kaboom")

    out = server._guard(boom)
    assert out["ok"] is False
    assert out["error"] == "internal_error"
    assert "kaboom" in out["message"]


def test_guard_surfaces_lua_error_dict():
    out = server._guard(lambda: {"error": "no image open", "where": "adjust"})
    assert out["ok"] is False
    assert out["message"] == "no image open"
    assert out["where"] == "adjust"


def test_guard_includes_hint_for_known_errors():
    def raise_not_running():
        raise DarktableNotRunning("darktable is not running.", hint="Open the GUI.")

    out = server._guard(raise_not_running)
    assert out["ok"] is False
    assert out["error"] == "darktable_not_running"
    assert out["hint"] == "Open the GUI."


def test_guard_maps_lua_error_type():
    def raise_lua():
        raise DarktableLuaError("bad", hint="from Lua")

    out = server._guard(raise_lua)
    assert out["error"] == "lua_error"


# -- tool-level input validation returns structured errors -----------------

def test_export_image_rejects_bad_format():
    out = server.export_image("x.gif", "gif")
    assert out["ok"] is False and out["error"] == "bad_format"


def test_export_image_rejects_missing_folder():
    out = server.export_image(r"Z:\definitely\missing\folder\pic.jpg", "jpeg")
    assert out["ok"] is False and out["error"] == "bad_path"


def test_adjust_rejects_unknown_control():
    out = server.adjust("sharpness", "up", 3)
    assert out["ok"] is False and out["error"] == "unknown_control"


def test_set_rating_rejects_out_of_range():
    out = server.set_rating(9)
    assert out["ok"] is False and out["error"] == "bad_rating"
