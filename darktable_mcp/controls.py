"""The knowledge layer: what controls exist and how plain-language intent maps to them.

This is what lets the user stay ignorant of darktable's internals — Claude reads the guide and
translates "make it moody" into concrete ``adjust`` calls. Every control here was validated live
against darktable 5.6.0 (Lua API 9.7.0).
"""

from __future__ import annotations

# Friendly control names Claude can pass to `adjust`. All confirmed drivable via the action system.
CONTROLS: dict[str, str] = {
    "brightness": "iop/exposure/exposure",
    "exposure": "iop/exposure/exposure",
    "warmth": "iop/temperature/temperature",
    "temperature": "iop/temperature/temperature",
    "tint": "iop/temperature/tint",
    "contrast": "iop/colorbalancergb/contrast",
    "saturation": "iop/colorbalancergb/global saturation",
    "vibrance": "iop/velvia/strength",
}

# Directions accepted by `adjust`.
DIRECTIONS = {"up", "down"}

INTENT_GUIDE = """\
# darktable live-edit guide (for Claude)

You control a live darktable darkroom. Edits appear on screen as you make them. You cannot set
absolute values; you *nudge* controls up or down and observe. Loop with the user: nudge, let them
react, nudge again.

## Available controls (adjust(control, direction, amount))
- brightness / exposure — overall lightness. up = brighter.
- warmth / temperature — white balance warmth. up = warmer (more orange), down = cooler (more blue).
- tint — green/magenta balance. up = more magenta.
- contrast — tonal contrast. up = punchier.
- saturation — overall color intensity (subtle). up = more colorful.
- vibrance — stronger color boost (velvia). up = vivid, punchy color.

`amount` is a relative step size, 1 (tiny) to 10 (large). Default to 3 for a first move, then
adjust based on the user's reaction ("too much" -> smaller opposite nudge).

## Translating common requests
- "warmer" -> warmth up.        "cooler" -> warmth down.
- "brighter" -> brightness up.  "darker" -> brightness down.
- "punchier" / "more pop" -> contrast up, then vibrance up a little.
- "moody" / "cinematic" -> warmth down (cooler), brightness down slightly, saturation down,
  contrast up a touch.
- "vivid" / "vibrant" -> vibrance up, saturation up.
- "flat" / "muted" / "faded" -> contrast down, saturation down.
- "golden hour" / "cozy" -> warmth up, vibrance up slightly.

## Workflow tips
- Call `open_in_darkroom` first so the user can see the photo. Confirm with `get_current_image`.
- After a few nudges, ask if they like it. If they want to keep the look, offer
  `create_style_from_current` so it becomes reusable.
- `reset_current` discards all edits — use it when the user wants to start over.
- Prefer existing saved styles (`list_styles` / `apply_style`) as a fast starting point, then
  fine-tune with nudges.
"""
