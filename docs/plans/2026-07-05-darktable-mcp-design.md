# dark-table-mcp — v1 Design

**Date:** 2026-07-05
**Status:** Approved, scaffolding
**Goal:** Let a user tell Claude how they want a photo to look in plain language and watch
darktable change it live in the darkroom — without the user knowing darktable's controls.

## Background

Research (see the Obsidian vault `Software/DarkTable/`) plus live validation on the target
machine established the integration surface:

- **DBus `org.darktable.service.Remote.Lua`** executes arbitrary Lua in a *running* darktable
  session and returns a string. Validated on darktable **5.6.0**, Lua API **9.7.0**, Windows.
- The GUI **action system** is drivable from Lua: `dt.gui.action('iop/<module>/<slider>', 0,
  'value', 'up'|'down', speed)` moves real sliders on the live image. Confirmed for exposure,
  temperature, tint, contrast, saturation, velvia strength — the image re-renders in the darkroom.
- Values read back in mixed units (some normalized 0–1, some native), so **relative nudges**
  (up/down) are used rather than absolute values. Direction is all v1 needs.
- Styles apply live (`dt.styles.apply`) and can be created from the current edit
  (`dt.styles.create`). `img:reset()` clears an edit — the "try again" safety net.

## Architecture

Three layers:

1. **MCP server** (`darktable_mcp/server.py`) — Python, official `mcp` SDK (FastMCP). Exposes tools.
2. **Bridge** (`darktable_mcp/bridge.py`) — runs darktable's bundled `gdbus.exe` to call
   `Remote.Lua`, parses the `('...',)` reply, maps `org.darktable.Error.LuaError` and
   service-unknown (darktable not running) to clean Python exceptions.
3. **Lua helper** (`darktable_mcp/lua/dtmcp.lua`) — defines a global `dtmcp` table of functions
   that do the darktable work and `return` JSON. **Self-installing:** the bridge injects the
   helper source over `Remote.Lua` on first use, so the user does not have to edit `luarc`.

Data flow: Claude → tool → bridge → `gdbus Remote.Lua` → `dtmcp.*` in the live session →
darkroom re-renders → JSON reply → Claude.

## Tool surface (v1)

| Tool | Purpose |
|---|---|
| `dt_status` | darktable running? version / API / image count |
| `list_images(filter, limit)` | find photos in the library |
| `open_in_darkroom(query)` | load a photo into the darkroom (so edits are visible) |
| `get_current_image` | the photo currently being edited |
| `adjust(control, direction, amount)` | **live nudge** of a single control |
| `apply_look(look)` | one-word semantic move nudging several controls together (moody, golden, ...) |
| `list_looks` | enumerate the semantic looks |
| `list_styles` / `apply_style(name)` | apply a saved look live |
| `create_style_from_current(name)` | save the current look as a reusable style |
| `build_starter_styles(image_query)` | build the "MCP - ..." starter style pack from the live pipeline |
| `get_preview(max_size)` | render the current edit to a JPEG Claude can **see** (feedback loop) |
| `reset_current` | discard edits and start over |
| `set_rating` / `get_labels` / `set_color_label` | ratings + color labels (single or `all_selected`) |
| `add_tag` / `remove_tag` / `get_tags` | keyword tags |
| `set_metadata` / `get_metadata` | title/creator/... + read-only EXIF |
| `list_collection` / `get_selection` | browse the active filter / selected photos |
| `duplicate_image` / `import_images` / `export_image` | library + real file export |
| `darktable_guide` | intent→control knowledge Claude reads to translate words to modules |

### Controls (all validated live)

brightness/exposure, warmth/temperature, tint, contrast, filmic_contrast, saturation, vibrance,
shadows, highlights, whites, blacks. Paths are in `controls.py` (Python) and `lua/dtmcp.lua`
(Lua) — a unit test asserts the two registries stay in sync.

> Note: `iop/colorbalancergb/shadows luminance` / `highlights luminance` were probed and **hung
> darktable** — avoided. Shadows/highlights are driven via the `shadhi` module instead.

### Semantic looks & starter styles

`apply_look` maps a word (moody, cinematic, golden, faded, vivid, punchy, soft, ...) to a sequence
of nudges — the "warmer/cooler" convenience layer. `build_starter_styles` runs curated sequences on
a photo and saves them as reusable `MCP - <name>` styles, sidestepping darktable's binary style
format by building looks through the live pipeline.

## Knowledge layer

`darktable_mcp/controls.py` holds the confirmed control registry (friendly name → action path)
and an intent guide ("moody" = cooler + lifted shadows + lower saturation, etc.) distilled from
the research notes, exposed as the `darktable_guide` tool/resource. This is what lets the user
stay ignorant of darktable's internals.

## Error handling

- darktable not running → tool returns a clear "open darktable first" message (v1 does not
  auto-launch, to avoid the stale-lock problem seen when force-killing).
- Lua errors surfaced verbatim.
- DBus call timeout (default 30s).

## Testing

- Unit: bridge reply-parsing and error mapping with a mocked `gdbus` (no darktable needed).
- Lua syntax check on the helper.
- Opt-in integration smoke test requiring a live darktable (skipped in CI).

## Preview feedback loop

`get_preview` exports the current darkroom edit to a JPEG via Lua (`dt.new_format('jpeg')` +
`write_image`, long edge capped) and returns it as an MCP image. This runs inside the live
session — no second process, no DB-lock issue. Verified: an exposure change alters the rendered
bytes, so Claude can look at the result and decide the next move instead of editing blind.

## Deferred: crop / rotate

Investigated and **deferred**. The crop-angle slider and the flip module's rotate/flip buttons
are reachable via the action system but produced **no change in the exported render** — geometry
modules appear to need the interactive crop commit that the action API does not trigger over the
bridge. Left out rather than shipped as no-ops. A later approach would manipulate the crop module's
parameters or history directly.

## Out of scope for v1 (YAGNI)

Absolute-unit slider control (needs per-module calibration), text→style synthesis, camera
import, batch export. Code leaves room for a later "style generation" phase.

## Confirmed control registry

| Friendly name | Action path |
|---|---|
| brightness / exposure | `iop/exposure/exposure` |
| warmth / temperature | `iop/temperature/temperature` |
| tint | `iop/temperature/tint` |
| contrast | `iop/colorbalancergb/contrast` |
| saturation | `iop/colorbalancergb/global saturation` |
| vibrance | `iop/velvia/strength` |
