"""darktable-mcp server: tools that let Claude edit photos live in darktable's darkroom."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import controls
from .bridge import Bridge, DarktableError, DarktableNotRunning

mcp = FastMCP("darktable")
bridge = Bridge()


def _guard(call) -> dict[str, Any]:
    """Run a bridge call, turning darktable errors into structured tool results."""
    try:
        return {"ok": True, "result": call()}
    except DarktableNotRunning as exc:
        return {"ok": False, "error": "darktable_not_running", "message": str(exc)}
    except DarktableError as exc:
        return {"ok": False, "error": "darktable_error", "message": str(exc)}


@mcp.tool()
def dt_status() -> dict[str, Any]:
    """Check whether darktable is running and report its version, Lua API, and image count."""
    return _guard(lambda: bridge.call("status"))


@mcp.tool()
def list_images(filter: str = "", limit: int = 50) -> dict[str, Any]:
    """List photos in the darktable library, optionally filtered by a filename substring."""
    return _guard(lambda: bridge.call("list_images", filter or None, limit))


@mcp.tool()
def open_in_darkroom(query: str) -> dict[str, Any]:
    """Open the first photo whose filename contains `query` in the darkroom so edits are visible."""
    return _guard(lambda: bridge.call("open_in_darkroom", query))


@mcp.tool()
def get_current_image() -> dict[str, Any]:
    """Report the photo currently open in the darkroom (the one edits apply to)."""
    return _guard(lambda: bridge.call("get_current_image"))


@mcp.tool()
def adjust(control: str, direction: str, amount: int = 3) -> dict[str, Any]:
    """Nudge a control on the current photo and watch it change live.

    control: one of brightness/exposure, warmth/temperature, tint, contrast, saturation, vibrance.
    direction: "up" or "down".
    amount: relative step size 1 (tiny) to 10 (large); default 3.

    Read the `darktable_guide` tool to translate a user's words (e.g. "moody", "warmer") into
    the right control and direction.
    """
    if control.lower() not in controls.CONTROLS:
        return {
            "ok": False,
            "error": "unknown_control",
            "message": f"'{control}' is not a known control. Valid: {sorted(set(controls.CONTROLS))}",
        }
    if direction.lower() not in controls.DIRECTIONS:
        return {"ok": False, "error": "bad_direction", "message": "direction must be 'up' or 'down'"}
    return _guard(lambda: bridge.call("adjust", control.lower(), direction.lower(), amount))


@mcp.tool()
def list_styles() -> dict[str, Any]:
    """List the saved styles (looks) available in darktable."""
    return _guard(lambda: bridge.call("list_styles"))


@mcp.tool()
def apply_style(name: str) -> dict[str, Any]:
    """Apply a saved style to the current darkroom photo, live."""
    return _guard(lambda: bridge.call("apply_style", name))


@mcp.tool()
def create_style_from_current(name: str, description: str = "") -> dict[str, Any]:
    """Save the current photo's edit as a reusable named style."""
    return _guard(lambda: bridge.call("create_style_from_current", name, description))


@mcp.tool()
def reset_current() -> dict[str, Any]:
    """Discard all edits on the current photo and start over."""
    return _guard(lambda: bridge.call("reset_current"))


@mcp.tool()
def darktable_guide() -> str:
    """Return guidance on translating plain-language photo requests into darktable controls."""
    return controls.INTENT_GUIDE


@mcp.resource("darktable://guide")
def guide_resource() -> str:
    """The intent->control guide, also available as a resource."""
    return controls.INTENT_GUIDE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
