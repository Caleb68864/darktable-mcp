# dark-table-mcp

An MCP server that lets Claude edit your photos **live in darktable**. Tell Claude how you want a
photo to look ("warmer, a bit moodier, more punch") and watch the darkroom change in front of you —
no need to know darktable's controls yourself.

## How it works

Claude → MCP tool → `gdbus` → darktable's DBus `Remote.Lua` method → a Lua helper running inside
your **live** darktable session → the darkroom re-renders. See
`docs/plans/2026-07-05-darktable-mcp-design.md` for the full design.

The bridge was validated against **darktable 5.6.0** (Lua API 9.7.0) on Windows.

## Requirements

- darktable 5.x with Lua support (`LuaEnabled` = true), **GUI running**
- Python 3.10+
- Windows (paths default to `C:\Program Files\darktable\bin`; override with `DARKTABLE_BIN_DIR`)

## Install

```powershell
uv pip install -e .
# or: pip install -e .
```

## Run

Open the darktable GUI first (the server talks to a live session). Then point your MCP client at:

```
darktable-mcp
```

Or configure Claude Desktop / Claude Code with the `darktable-mcp` command as an MCP server.

## Tools

| Tool | What it does |
|---|---|
| `dt_status` | Is darktable running? version / API / image count |
| `list_images` | Find photos in the library |
| `open_in_darkroom` | Load a photo into the darkroom so edits are visible |
| `get_current_image` | Which photo is being edited |
| `adjust` | Live nudge: brightness, warmth, tint, contrast, saturation, vibrance, shadows, highlights (up/down) |
| `apply_look` / `list_looks` | One-word vibe: warmer, moody, cinematic, golden, vivid, faded, ... |
| `get_preview` | Render the current edit to an image so Claude can **see** the result |
| `build_starter_styles` | Create the "MCP - ..." starter style pack from the live pipeline |
| `list_styles` / `apply_style` | Apply a saved look, live |
| `create_style_from_current` | Save the current look as a reusable style |
| `reset_current` | Discard edits and start over |
| `set_rating` / `get_labels` | Star rating (-1 reject … 5) and color labels |
| `set_color_label` | Red/yellow/green/blue/purple flags (single or whole selection) |
| `add_tag` / `remove_tag` / `get_tags` | Keyword tags (created on demand) |
| `set_metadata` / `get_metadata` | Title/creator/etc. + read-only EXIF (camera, lens, ISO) |
| `list_collection` / `get_selection` | Browse the active filter / the selected photos |
| `duplicate_image` | Virtual copy with independent edits |
| `import_images` | Import a file or folder into the library |
| `export_image` | Write the edited photo to a real JPEG/PNG/TIFF |
| `darktable_guide` | Intent→control guidance Claude uses to translate your words |

Most organizing tools take `all_selected=true` to act on the whole lighttable selection instead of
just the current photo.

## The live loop

> **You:** open the beach photo and make it warmer and punchier
> **Claude:** *opens it in the darkroom, nudges warmth up, contrast up, vibrance up*
> **You:** too warm, and lift it a bit
> **Claude:** *warmth down a touch, brightness up* — you watch each change land

## Notes & limits (v1)

- **Relative nudges only.** darktable sliders take normalized values, so Claude adjusts controls
  up/down rather than setting absolute numbers. This suits the conversational loop.
- **Live session required.** This drives the running GUI; it is not a headless renderer. (Headless
  export via `darktable-cli` is a possible later addition.)
- The Lua helper (`darktable_mcp/lua/dtmcp.lua`) is **auto-injected** over DBus on first use — you
  do not need to edit `luarc`.
- If you force-quit darktable, it can leave stale `*.db.lock` files in its config dir; delete them
  if the next launch complains.

## Tests

```powershell
pytest -m "not integration"     # unit tests, no darktable needed
pytest -m integration           # smoke test against a running darktable GUI
```
