"""Transport to a live darktable session over DBus ``Remote.Lua``.

Every call shells out to ``gdbus call ... org.darktable.service.Remote.Lua "<lua>"``. The reply
is a GVariant tuple such as ``('...',)`` which we parse with ``ast.literal_eval``. The Lua helper
(``lua/dtmcp.lua``) is injected into the session on first use, so the user never edits ``luarc``.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

from . import config

HELPER_PATH = Path(__file__).parent / "lua" / "dtmcp.lua"


class DarktableError(RuntimeError):
    """Base error for the darktable bridge."""


class DarktableNotRunning(DarktableError):
    """The darktable GUI is not running (the DBus service is absent)."""


class DarktableLuaError(DarktableError):
    """Lua raised inside the darktable session."""


def _lua_literal(value: Any) -> str:
    """Render a Python value as a Lua literal for embedding in a call expression."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    # json.dumps gives a double-quoted, escaped string that Lua also accepts.
    return json.dumps(str(value))


class Bridge:
    def __init__(self, gdbus: str | None = None, timeout: float | None = None) -> None:
        self._gdbus = gdbus or config.gdbus_path()
        self._timeout = timeout if timeout is not None else config.default_timeout()
        self._helper_loaded = False

    # -- low level ---------------------------------------------------------

    def raw_lua(self, lua: str) -> Any:
        """Execute a Lua string in the session; return the first tuple element (or None)."""
        cmd = [
            self._gdbus, "call", "--session",
            "--dest", config.DBUS_DEST,
            "--object-path", config.DBUS_OBJECT_PATH,
            "--method", config.DBUS_LUA_METHOD,
            # "--" ends option parsing so a Lua string starting with "-" (e.g. a "--" comment)
            # is never mistaken for a gdbus flag.
            "--", lua,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout
            )
        except FileNotFoundError as exc:
            raise DarktableError(
                f"gdbus not found at {self._gdbus!r}. Set DARKTABLE_BIN_DIR to your "
                f"darktable bin directory."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DarktableError(f"darktable did not respond within {self._timeout}s") from exc

        if proc.returncode != 0:
            self._raise_for_stderr(proc.stderr or proc.stdout)
        return self._parse_reply(proc.stdout)

    @staticmethod
    def _raise_for_stderr(stderr: str) -> None:
        text = stderr.strip()
        low = text.lower()
        if "serviceunknown" in low or "was not provided by any" in low or "name org.darktable" in low:
            raise DarktableNotRunning(
                "darktable is not running. Open the darktable GUI, then try again."
            )
        marker = "org.darktable.Error.LuaError:"
        if marker in text:
            msg = text.split(marker, 1)[1].strip()
            raise DarktableLuaError(msg)
        raise DarktableError(text)

    @staticmethod
    def _parse_reply(stdout: str) -> Any:
        out = stdout.strip()
        if not out:
            return None
        try:
            value = ast.literal_eval(out)
        except (ValueError, SyntaxError):
            # Best-effort fallback: strip the surrounding ('...',) wrapper.
            inner = out
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1].rstrip(",")
            return inner.strip().strip("'").strip('"')
        if isinstance(value, tuple):
            return value[0] if value else None
        return value

    # -- helper bootstrap --------------------------------------------------

    def ensure_helper(self) -> None:
        if self._helper_loaded:
            return
        kind = self.raw_lua("return type(dtmcp)")
        if kind != "table":
            # Load the helper by having darktable dofile() it from disk. We use a forward-slash
            # path (valid for Lua io on Windows) so the argument carries no backslashes or quotes
            # that Windows argv quoting would corrupt.
            helper_uri = HELPER_PATH.as_posix()
            self.raw_lua(f"return dofile('{helper_uri}')")
        self._helper_loaded = True

    def call(self, func: str, *args: Any) -> Any:
        """Call ``dtmcp.<func>(args...)`` and decode its JSON return value."""
        self.ensure_helper()
        arglist = ", ".join(_lua_literal(a) for a in args)
        result = self.raw_lua(f"return dtmcp.{func}({arglist})")
        if result is None or result == "":
            return None
        try:
            return json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return result
