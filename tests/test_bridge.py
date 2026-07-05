"""Unit tests for the bridge reply parsing and error mapping (no darktable required)."""

import subprocess

import pytest

from darktable_mcp.bridge import (
    Bridge,
    DarktableError,
    DarktableLuaError,
    DarktableNotRunning,
    _lua_literal,
)


def _fake_completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_parse_single_string_tuple():
    assert Bridge._parse_reply("('4',)\n") == "4"


def test_parse_json_payload_tuple():
    assert Bridge._parse_reply("""('{"a": 1}',)""") == '{"a": 1}'


def test_parse_empty_tuple_is_none():
    assert Bridge._parse_reply("()\n") is None


def test_parse_blank_is_none():
    assert Bridge._parse_reply("   ") is None


def test_not_running_detected(monkeypatch):
    def fake_run(*a, **k):
        return _fake_completed(
            stderr="Error: GDBus.Error:org.freedesktop.DBus.Error.ServiceUnknown: "
            "The name org.darktable.service was not provided by any .service files",
            returncode=1,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableNotRunning):
        Bridge(gdbus="gdbus").raw_lua("return 1")


def test_lua_error_message_extracted(monkeypatch):
    def fake_run(*a, **k):
        return _fake_completed(
            stderr="Error: GDBus.Error:org.darktable.Error.LuaError: boom near 'x'",
            returncode=1,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableLuaError) as exc:
        Bridge(gdbus="gdbus").raw_lua("return nonsense")
    assert "boom" in str(exc.value)


def test_generic_error(monkeypatch):
    def fake_run(*a, **k):
        return _fake_completed(stderr="Error: something else", returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DarktableError):
        Bridge(gdbus="gdbus").raw_lua("return 1")


def test_call_decodes_json(monkeypatch):
    calls = []

    def fake_run(cmd, *a, **k):
        calls.append(cmd[-1])  # the lua string
        if "type(dtmcp)" in cmd[-1]:
            return _fake_completed(stdout="('table',)\n")
        return _fake_completed(stdout="""('{"version": "5.6.0", "images": 3}',)\n""")

    monkeypatch.setattr(subprocess, "run", fake_run)
    b = Bridge(gdbus="gdbus")
    result = b.call("status")
    assert result == {"version": "5.6.0", "images": 3}


def test_lua_literal_rendering():
    assert _lua_literal(None) == "nil"
    assert _lua_literal(True) == "true"
    assert _lua_literal(3) == "3"
    assert _lua_literal("hi") == '"hi"'
    assert _lua_literal('a"b') == '"a\\"b"'
