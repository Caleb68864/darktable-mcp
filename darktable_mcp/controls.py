"""The knowledge layer: what controls exist and how plain-language intent maps to them.

This is what lets the user stay ignorant of darktable's internals — Claude reads the guide and
translates "make it moody" into concrete `adjust`/`apply_look` calls. Every control here was
validated live against darktable 5.6.0 (Lua API 9.7.0).
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
    # tonal controls via the shadows/highlights module
    "shadows": "iop/shadhi/shadows",
    "highlights": "iop/shadhi/highlights",
    # tone-mapping controls via filmic
    "filmic_contrast": "iop/filmicrgb/contrast",
    "whites": "iop/filmicrgb/white relative exposure",
    "blacks": "iop/filmicrgb/black relative exposure",
}

# Directions accepted by `adjust`.
DIRECTIONS = {"up", "down"}

# Semantic "looks": one word -> a sequence of (control, direction, amount) nudges.
# This is the convenience layer so the user can say "moodier" and get a coherent multi-control move.
LOOKS: dict[str, list[tuple[str, str, int]]] = {
    "warmer": [("warmth", "up", 3)],
    "cooler": [("warmth", "down", 3)],
    "brighter": [("brightness", "up", 3)],
    "darker": [("brightness", "down", 3)],
    "punchy": [("contrast", "up", 3), ("vibrance", "up", 2)],
    "vivid": [("vibrance", "up", 4), ("saturation", "up", 2)],
    "muted": [("contrast", "down", 2), ("saturation", "down", 3)],
    "faded": [("contrast", "down", 3), ("saturation", "down", 2), ("blacks", "up", 2)],
    "moody": [
        ("warmth", "down", 2), ("brightness", "down", 2), ("saturation", "down", 2),
        ("contrast", "up", 2), ("shadows", "down", 2),
    ],
    "golden": [("warmth", "up", 3), ("vibrance", "up", 2), ("highlights", "up", 1)],
    "cinematic": [
        ("warmth", "down", 2), ("filmic_contrast", "up", 2),
        ("saturation", "down", 1), ("shadows", "down", 2),
    ],
    "soft": [("contrast", "down", 2), ("highlights", "down", 1), ("shadows", "up", 1)],
}

# Starter styles built from the live pipeline (name -> nudge sequence). Running `build_starter_styles`
# applies each sequence to a photo and saves it as a reusable "MCP - <name>" style, so Claude has
# richer looks to apply without hand-authoring darktable's style format.
STARTER_STYLES: dict[str, list[tuple[str, str, int]]] = {
    "Warm Punch": [("warmth", "up", 3), ("contrast", "up", 3), ("vibrance", "up", 3)],
    "Golden Hour": LOOKS["golden"],
    "Moody": LOOKS["moody"],
    "Vivid Pop": LOOKS["vivid"],
    "Faded Film": LOOKS["faded"],
    "Cinematic": LOOKS["cinematic"],
}

INTENT_GUIDE = """\
# darktable live-edit guide (for Claude)

You control a live darktable darkroom. Edits appear on screen as you make them. You cannot set
absolute values; you *nudge* controls up or down and observe. Loop with the user: nudge, let them
react, nudge again.

## Two ways to edit
- `apply_look(look)` — a one-word semantic move that nudges several controls together. Best first
  step for a vibe: warmer, cooler, brighter, darker, punchy, vivid, muted, faded, moody, golden,
  cinematic, soft.
- `adjust(control, direction, amount)` — fine-tune a single control after the user reacts.

## Single controls (adjust)
- brightness / exposure — overall lightness. up = brighter.
- warmth / temperature — white balance warmth. up = warmer, down = cooler.
- tint — green/magenta balance. up = more magenta.
- contrast — tonal contrast (color balance). up = punchier.
- filmic_contrast — contrast via the tone mapper; a more cinematic contrast.
- saturation — overall color intensity (subtle). up = more colorful.
- vibrance — stronger color boost (velvia). up = vivid, punchy color.
- shadows — lift/lower the dark tones. up = brighter shadows (opens them up).
- highlights — lift/lower the bright tones. down = tames blown highlights.
- whites / blacks — the white/black points via filmic (advanced; small nudges).

`amount` is a relative step, 1 (tiny) to 10 (large). Default 3 for a first move; smaller for
fine-tuning.

## Seeing the result
- `get_preview` renders the current edit to an image you can actually look at. Use it to close the
  loop: make a change, call `get_preview`, judge it, then decide the next nudge — rather than
  editing blind. Especially call it before telling the user something looks a certain way.

## Workflow tips
- Call `open_in_darkroom` first so the user sees the photo. Confirm with `get_current_image`.
- Start with `apply_look` for the overall vibe, call `get_preview` to check, then `adjust` to taste.
- Prefer a saved style as a fast starting point: `list_styles` then `apply_style` (styles named
  "MCP - ..." are the starter pack). Fine-tune with nudges afterward.
- If the user likes the result, offer `create_style_from_current` to save it.
- `reset_current` discards all edits — use it to start over.
"""
