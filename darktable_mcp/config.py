"""Locating darktable's binaries.

darktable ships its own ``gdbus.exe``; we prefer that over any system copy so the DBus
session bus matches the one darktable registered on.
"""

from __future__ import annotations

import os
import shutil

# Default Windows install location. Override with the DARKTABLE_BIN_DIR env var.
DEFAULT_BIN_DIR = r"C:\Program Files\darktable\bin"

DBUS_DEST = "org.darktable.service"
DBUS_OBJECT_PATH = "/darktable"
DBUS_LUA_METHOD = "org.darktable.service.Remote.Lua"


def bin_dir() -> str:
    return os.environ.get("DARKTABLE_BIN_DIR", DEFAULT_BIN_DIR)


def gdbus_path() -> str:
    """Path to gdbus. Prefers darktable's bundled copy, falls back to PATH."""
    bundled = os.path.join(bin_dir(), "gdbus.exe")
    if os.path.exists(bundled):
        return bundled
    found = shutil.which("gdbus")
    return found or bundled


def darktable_exe() -> str:
    return os.path.join(bin_dir(), "darktable.exe")


def default_timeout() -> float:
    return float(os.environ.get("DARKTABLE_MCP_TIMEOUT", "30"))
