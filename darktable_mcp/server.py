"""darktable-mcp server: tools that let Claude edit photos live in darktable's darkroom."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

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
def list_looks() -> dict[str, Any]:
    """List the one-word semantic looks available to `apply_look` (warmer, moody, cinematic, ...)."""
    return {"ok": True, "result": {"looks": sorted(controls.LOOKS)}}


@mcp.tool()
def apply_look(look: str) -> dict[str, Any]:
    """Apply a one-word semantic look to the current photo by nudging several controls together.

    look: one of warmer, cooler, brighter, darker, punchy, vivid, muted, faded, moody, golden,
    cinematic, soft. Use this for an overall vibe, then fine-tune with `adjust`.
    """
    seq = controls.LOOKS.get(look.lower())
    if seq is None:
        return {
            "ok": False,
            "error": "unknown_look",
            "message": f"'{look}' is not a known look. Valid: {sorted(controls.LOOKS)}",
        }

    def run() -> dict[str, Any]:
        steps = [bridge.call("adjust", c, d, a) for c, d, a in seq]
        return {"look": look.lower(), "steps": steps}

    return _guard(run)


@mcp.tool()
def build_starter_styles(image_query: str) -> dict[str, Any]:
    """Create the "MCP - ..." starter style pack by building each look on a photo and saving it.

    Pass a filename substring for any photo to build on (its edits are reset afterward, so the
    photo is left untouched). Adds reusable styles Claude can later `apply_style`.
    """

    def run() -> dict[str, Any]:
        opened = bridge.call("open_in_darkroom", image_query)
        if isinstance(opened, dict) and opened.get("error"):
            return opened
        created, skipped = [], []
        existing = {s["name"] for s in bridge.call("list_styles").get("styles", [])}
        for name, seq in controls.STARTER_STYLES.items():
            style_name = f"MCP - {name}"
            if style_name in existing:
                skipped.append(style_name)
                continue
            bridge.call("reset_current")
            for c, d, a in seq:
                bridge.call("adjust", c, d, a)
            bridge.call("create_style_from_current", style_name, f"darktable-mcp starter: {name}")
            created.append(style_name)
        bridge.call("reset_current")
        return {"created": created, "skipped": skipped}

    return _guard(run)


@mcp.tool()
def list_styles() -> dict[str, Any]:
    """List the saved styles (looks) available in darktable."""
    return _guard(lambda: bridge.call("list_styles"))


@mcp.tool()
def apply_style(name: str, all_selected: bool = False) -> dict[str, Any]:
    """Apply a saved style to the current darkroom photo (or the whole lighttable selection)."""
    return _guard(lambda: bridge.call("apply_style", name, all_selected))


@mcp.tool()
def import_style(path: str) -> dict[str, Any]:
    """Import a .dtstyle file (e.g. a downloaded style or LUT-based look pack) into darktable."""
    return _guard(lambda: bridge.call("import_style", path))


@mcp.tool()
def export_style(name: str, directory: str) -> dict[str, Any]:
    """Export a saved style to a .dtstyle file in `directory` (to share or back up)."""
    return _guard(lambda: bridge.call("export_style", name, directory))


@mcp.tool()
def delete_style(name: str) -> dict[str, Any]:
    """Delete a saved style by name."""
    return _guard(lambda: bridge.call("delete_style", name))


@mcp.tool()
def copy_edit(from_query: str, all_selected: bool = False) -> dict[str, Any]:
    """Copy the full edit from one photo onto the current photo (or the whole selection).

    from_query: a filename substring of the photo whose edit you want to copy.
    """
    return _guard(lambda: bridge.call("copy_edit", from_query, all_selected))


@mcp.tool()
def create_style_from_current(name: str, description: str = "") -> dict[str, Any]:
    """Save the current photo's edit as a reusable named style."""
    return _guard(lambda: bridge.call("create_style_from_current", name, description))


@mcp.tool()
def get_preview(max_size: int = 1024) -> Image:
    """Render the current darkroom edit to an image so you can SEE the result.

    Returns a JPEG of the photo with all current edits applied (long edge capped at `max_size`).
    Call this after making changes to check how the photo looks, then decide what to adjust next.
    """
    fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="dtmcp_preview_")
    os.close(fd)
    try:
        result = bridge.call("export_preview", Path(tmp).as_posix(), max_size)
        if isinstance(result, dict) and result.get("error"):
            raise DarktableError(result["error"])
        data = Path(tmp).read_bytes()
        return Image(data=data, format="jpeg")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


@mcp.tool()
def reset_current() -> dict[str, Any]:
    """Discard all edits on the current photo and start over."""
    return _guard(lambda: bridge.call("reset_current"))


# -- organizing: ratings, labels, tags, metadata ---------------------------

@mcp.tool()
def set_rating(rating: int, all_selected: bool = False) -> dict[str, Any]:
    """Set the star rating (-1 reject, 0 none, 1-5 stars) on the current photo.

    all_selected: if true, apply to every photo currently selected in the lighttable instead.
    """
    if not -1 <= rating <= 5:
        return {"ok": False, "error": "bad_rating", "message": "rating must be -1 to 5"}
    return _guard(lambda: bridge.call("set_rating", rating, all_selected))


@mcp.tool()
def set_color_label(color: str, on: bool = True, all_selected: bool = False) -> dict[str, Any]:
    """Toggle a color label (red/yellow/green/blue/purple) on the current photo (or selection)."""
    if color.lower() not in controls.COLOR_LABELS:
        return {"ok": False, "error": "bad_color", "message": f"color must be one of {sorted(controls.COLOR_LABELS)}"}
    return _guard(lambda: bridge.call("set_color_label", color.lower(), on, all_selected))


@mcp.tool()
def get_labels() -> dict[str, Any]:
    """Get the current photo's star rating and color labels."""
    return _guard(lambda: bridge.call("get_labels"))


@mcp.tool()
def add_tag(tag: str, all_selected: bool = False) -> dict[str, Any]:
    """Attach a tag (keyword) to the current photo, creating the tag if needed.

    all_selected: if true, tag every photo currently selected in the lighttable instead.
    """
    return _guard(lambda: bridge.call("add_tag", tag, all_selected))


@mcp.tool()
def remove_tag(tag: str, all_selected: bool = False) -> dict[str, Any]:
    """Detach a tag from the current photo (or the whole lighttable selection)."""
    return _guard(lambda: bridge.call("remove_tag", tag, all_selected))


@mcp.tool()
def get_tags() -> dict[str, Any]:
    """List the tags attached to the current photo."""
    return _guard(lambda: bridge.call("get_tags"))


@mcp.tool()
def set_metadata(field: str, value: str) -> dict[str, Any]:
    """Set a metadata field (title/creator/publisher/rights/description) on the current photo."""
    if field.lower() not in controls.METADATA_FIELDS:
        return {"ok": False, "error": "bad_field", "message": f"field must be one of {sorted(controls.METADATA_FIELDS)}"}
    return _guard(lambda: bridge.call("set_metadata", field.lower(), value))


@mcp.tool()
def get_metadata() -> dict[str, Any]:
    """Get the current photo's metadata (title/creator/...), key EXIF, and GPS location."""
    return _guard(lambda: bridge.call("get_metadata"))


@mcp.tool()
def set_location(latitude: float, longitude: float, elevation: float | None = None) -> dict[str, Any]:
    """Geotag the current photo with GPS latitude/longitude (and optional elevation in metres)."""
    return _guard(lambda: bridge.call("set_location", latitude, longitude, elevation))


# -- browsing & library ----------------------------------------------------

@mcp.tool()
def list_collection(limit: int = 100) -> dict[str, Any]:
    """List the photos in darktable's current collection (the active lighttable filter)."""
    return _guard(lambda: bridge.call("list_collection", limit))


@mcp.tool()
def get_selection() -> dict[str, Any]:
    """List the photos currently selected in the lighttable."""
    return _guard(lambda: bridge.call("get_selection"))


@mcp.tool()
def duplicate_image() -> dict[str, Any]:
    """Create a virtual copy (duplicate) of the current photo with its own independent edits."""
    return _guard(lambda: bridge.call("duplicate_image"))


@mcp.tool()
def import_images(path: str) -> dict[str, Any]:
    """Import a photo file or a whole folder into the darktable library."""
    return _guard(lambda: bridge.call("import_images", path))


@mcp.tool()
def export_image(path: str, format: str = "jpeg", max_size: int = 0) -> dict[str, Any]:
    """Export the current photo (with its edits) to a real file.

    format: jpeg/png/tiff. max_size: cap the long edge in pixels (0 = full resolution).
    """
    if format.lower() not in controls.EXPORT_FORMATS:
        return {"ok": False, "error": "bad_format", "message": f"format must be one of {sorted(controls.EXPORT_FORMATS)}"}
    size = max_size if max_size > 0 else None
    return _guard(lambda: bridge.call("export_image", path, format.lower(), size))


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
