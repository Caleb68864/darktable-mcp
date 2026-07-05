"""Data-integrity tests for the control/look registries (no darktable required)."""

import re
from pathlib import Path

from darktable_mcp import controls


def _lua_control_keys() -> set[str]:
    """Parse the control names out of the Lua helper's CONTROLS table."""
    src = (Path(controls.__file__).parent / "lua" / "dtmcp.lua").read_text(encoding="utf-8")
    block = src.split("local CONTROLS = {", 1)[1].split("}", 1)[0]
    return set(re.findall(r"(\w+)\s*=", block))


def test_every_look_uses_known_controls():
    for look, steps in controls.LOOKS.items():
        for control, direction, amount in steps:
            assert control in controls.CONTROLS, f"look '{look}' uses unknown control '{control}'"
            assert direction in controls.DIRECTIONS
            assert 1 <= amount <= 10


def test_every_starter_style_uses_known_controls():
    for name, steps in controls.STARTER_STYLES.items():
        for control, direction, amount in steps:
            assert control in controls.CONTROLS, f"style '{name}' uses unknown control '{control}'"


def test_python_and_lua_control_registries_match():
    """Guards against the Python/Lua drift bug: both registries must expose the same names."""
    assert set(controls.CONTROLS) == _lua_control_keys()
