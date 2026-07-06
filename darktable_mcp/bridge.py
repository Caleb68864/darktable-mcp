"""Transport to a live darktable session over DBus ``Remote.Lua``.

Every call shells out to ``gdbus call ... org.darktable.service.Remote.Lua "<lua>"``. The reply
is a GVariant tuple such as ``('...',)`` which we parse with ``ast.literal_eval``. The Lua helper
(``lua/dtmcp.lua``) is injected into the session on first use, so the user never edits ``luarc``.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from . import config

HELPER_PATH = Path(__file__).parent / "lua" / "dtmcp.lua"


class DarktableError(RuntimeError):
    """Base error for the darktable bridge. Carries a `hint` for diagnosis."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


class DarktableNotRunning(DarktableError):
    """The darktable GUI is not running (the DBus service is absent)."""


class DarktableLuaError(DarktableError):
    """Lua raised inside the darktable session."""


class DarktableTimeout(DarktableError):
    """A call exceeded its timeout (often a slow full-resolution export)."""


def _config_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "darktable")


def _lock_files() -> list[str]:
    d = _config_dir()
    return [os.path.join(d, n) for n in ("library.db.lock", "data.db.lock") if os.path.exists(os.path.join(d, n))]


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

    def raw_lua(self, lua: str, timeout: float | None = None) -> Any:
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
        t = timeout if timeout is not None else self._timeout
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        except FileNotFoundError as exc:
            raise DarktableError(
                f"gdbus not found at {self._gdbus!r}.",
                hint="Set the DARKTABLE_BIN_DIR environment variable to your darktable "
                "'bin' directory (the folder containing gdbus.exe and darktable.exe).",
            ) from exc
        except OSError as exc:  # pragma: no cover - unexpected spawn failure
            raise DarktableError(f"failed to run gdbus: {exc}", hint="Check the gdbus path and permissions.") from exc
        except subprocess.TimeoutExpired as exc:
            # A mid-render abort can crash darktable, so surface this clearly rather than retrying.
            raise DarktableTimeout(
                f"darktable did not respond within {t:g}s.",
                hint="If this was a full-resolution export, it can take longer than the default "
                "timeout; raise it with the DARKTABLE_MCP_TIMEOUT env var (seconds) or export at "
                "a capped size. If darktable seems frozen, it may have crashed.",
            ) from exc

        if proc.returncode != 0:
            self._raise_for_stderr(proc.stderr or proc.stdout)
        return self._parse_reply(proc.stdout)

    def _raise_for_stderr(self, stderr: str) -> None:
        text = stderr.strip()
        low = text.lower()
        if "serviceunknown" in low or "was not provided by any" in low or "name org.darktable" in low:
            # If we had a working session and it vanished, darktable likely crashed/closed.
            crashed = self._helper_loaded
            locks = _lock_files()
            self._helper_loaded = False  # force re-bootstrap on reconnect
            if crashed:
                hint = "The darktable session ended unexpectedly (it may have crashed or been closed)."
                if locks:
                    hint += (
                        " Stale lock files remain and will block the next launch — delete them: "
                        + "; ".join(locks)
                    )
                else:
                    hint += " Reopen the darktable GUI and try again."
                raise DarktableNotRunning("lost connection to darktable.", hint=hint)
            raise DarktableNotRunning(
                "darktable is not running.",
                hint="Open the darktable GUI (this bridge drives a live session; darktable-cli "
                "does not expose it), then try again.",
            )
        marker = "org.darktable.Error.LuaError:"
        if marker in text:
            msg = text.split(marker, 1)[1].strip()
            raise DarktableLuaError(msg, hint="This is an error from inside darktable's Lua engine.")
        raise DarktableError(text or "unknown gdbus error", hint="Raw gdbus/DBus error; see message.")

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
        # Reload if absent OR if an older helper (missing the _call dispatcher) is present.
        kind = self.raw_lua("return type(dtmcp) .. '/' .. type(rawget(dtmcp or {}, '_call'))")
        if kind != "table/function":
            # Load the helper by having darktable dofile() it from disk. We use a forward-slash
            # path (valid for Lua io on Windows) so the argument carries no backslashes or quotes
            # that Windows argv quoting would corrupt.
            helper_uri = HELPER_PATH.as_posix()
            self.raw_lua(f"return dofile('{helper_uri}')")
        self._helper_loaded = True

    def call(self, func: str, *args: Any, timeout: float | None = None) -> Any:
        """Call ``dtmcp.<func>(args...)`` via the safe dispatcher; decode its JSON return value.

        Uses ``dtmcp._call`` so a Lua error inside the helper comes back as a structured
        ``{"error": ...}`` result instead of a raw DBus error.
        """
        self.ensure_helper()
        arglist = ", ".join(_lua_literal(a) for a in (func, *args))
        result = self.raw_lua(f"return dtmcp._call({arglist})", timeout=timeout)
        if result is None or result == "":
            return None
        try:
            return json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return result

    def diagnose(self) -> dict[str, Any]:
        """Collect troubleshooting facts without assuming darktable is up."""
        info: dict[str, Any] = {
            "gdbus_path": self._gdbus,
            "gdbus_exists": os.path.exists(self._gdbus),
            "bin_dir": config.bin_dir(),
            "config_dir": _config_dir(),
            "lock_files": _lock_files(),
            "timeout_seconds": self._timeout,
        }
        try:
            self._helper_loaded = False
            status = self.call("status", timeout=10)
            info["darktable_running"] = True
            info["darktable"] = status
        except DarktableError as exc:
            info["darktable_running"] = False
            info["error"] = str(exc)
            info["hint"] = getattr(exc, "hint", "")
        return info
