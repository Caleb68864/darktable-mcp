# dark-table-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#license)
[![darktable 5.6.0](https://img.shields.io/badge/darktable-5.6.0%20(Lua%209.7.0)-orange.svg)](https://www.darktable.org/)

> **Tell Claude how you want a photo to look — and watch darktable change it live.**

**dark-table-mcp** is a [Model Context Protocol](https://modelcontextprotocol.io) server that turns
Claude into a hands-on photo-editing and library assistant for [darktable](https://www.darktable.org/).
You describe the look you're after in plain language — *"open the barn photo, make it warmer and
moodier, and lift the shadows"* — and Claude drives the real sliders in your **live** darktable
darkroom. The image re-renders in front of you as it works. You never have to know which module or
slider does what; that knowledge lives in the server.

Beyond editing, Claude can browse and organize your library: rate and label photos, add tags and
metadata, geotag, apply and save styles, batch a look across a whole selection, and export finished
files.

Validated against **darktable 5.6.0** (Lua API 9.7.0) on Windows.

---

## Highlights

- **Live, conversational editing.** Claude nudges exposure, white balance, contrast, saturation,
  vibrance, shadows, highlights and more on the photo open in your darkroom — you see every change
  land in real time.
- **Semantic "looks."** One-word vibes like `moody`, `cinematic`, `golden`, `vivid`, or `faded`
  move several controls together for a coherent starting point, then Claude fine-tunes to taste.
- **See-the-result preview.** `get_preview` renders the current edit to an actual image Claude can
  *look at*, so it edits with its eyes open — make a change, check it, decide the next move.
- **Styles, including imported packs.** Apply, create, export, and delete darktable styles. Import
  downloaded `.dtstyle` files — including LUT-based look packs — and apply them live.
- **A ready-made starter pack.** `build_starter_styles` bakes 21 curated `MCP - …` styles straight
  from the live pipeline, so Claude has a rich palette of looks to reach for.
- **Full library organizing.** Star ratings, color labels, keyword tags, metadata
  (title/creator/…), read-only EXIF, and GPS geotagging.
- **Batch over a selection.** Most organizing tools and `apply_style` accept `all_selected=true`
  to act on the entire lighttable selection at once. `copy_edit` clones one good edit onto a burst.
- **Real exports.** Write the edited photo out to a genuine JPEG / PNG / TIFF at full or capped
  resolution.
- **Robust, diagnosable errors.** Tools never crash the conversation — they return structured
  results, and a dedicated `diagnose` tool troubleshoots the connection when something's off.

---

## How it works

Claude calls an MCP tool; the Python bridge shells out to darktable's own bundled `gdbus.exe` to
invoke the DBus `Remote.Lua` method, which runs a small companion Lua helper **inside your live
darktable session**. That helper moves the real GUI sliders (via darktable's action system), and
the darkroom re-renders. Results come back as JSON.

```
  You ──▶ Claude ──▶ MCP tool (server.py)
                          │
                          ▼
                   bridge.py  ──▶  gdbus.exe  ──▶  darktable DBus
                          │                        org.darktable.service.Remote.Lua
                          │                              │
                          │                              ▼
                          │                   dtmcp.lua helper  (in the LIVE session)
                          │                              │
                          │                              ▼
                          │                   darkroom re-renders  🖼️  (you see it change)
                          ▼                              │
                     JSON reply  ◀───────────────────────┘
```

The Lua helper (`darktable_mcp/lua/dtmcp.lua`) is **auto-injected over DBus on first use** — you do
**not** need to edit `luarc` or install anything into darktable. Because everything runs inside the
one already-open session, there's no second process and no database-lock contention.

For the full architecture and design rationale, see
[`docs/plans/2026-07-05-darktable-mcp-design.md`](docs/plans/2026-07-05-darktable-mcp-design.md).

---

## Requirements

- **darktable 5.x** with Lua support enabled (`LuaEnabled = true`) and the **GUI running**. This
  bridge drives a live session; `darktable-cli` does not expose it.
- **Python 3.10+**
- **Windows.** Paths default to `C:\Program Files\darktable\bin` (the folder containing
  `gdbus.exe` and `darktable.exe`); override with the `DARKTABLE_BIN_DIR` environment variable if
  darktable is installed elsewhere.

---

## Installation

Clone the repo, then install it (editable) into your environment:

```powershell
git clone https://github.com/yourname/dark-table-mcp.git
cd dark-table-mcp

# with uv (recommended)
uv venv
uv pip install -e .

# …or with plain pip
pip install -e .
```

This installs the `darktable-mcp` entry point (defined in `pyproject.toml`).

> **uv note:** `uv pip install` needs a virtual environment. Run `uv venv` first (as above), then
> `uv pip install -e .` installs into that venv.

---

## Configuration for an MCP client

Point your MCP client at the installed `darktable-mcp` entry point. On Windows this lives in your
venv's `Scripts` directory.

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "darktable": {
      "command": "C:\\path\\to\\dark-table-mcp\\.venv\\Scripts\\darktable-mcp.exe",
      "env": {
        "DARKTABLE_BIN_DIR": "C:\\Program Files\\darktable\\bin",
        "DARKTABLE_MCP_TIMEOUT": "30"
      }
    }
  }
}
```

Both `env` entries are optional — omit them to use the defaults (bin dir
`C:\Program Files\darktable\bin`, timeout 30 seconds).

**Claude Code** — register the same command as an MCP server, e.g.:

```powershell
claude mcp add darktable -- "C:\path\to\dark-table-mcp\.venv\Scripts\darktable-mcp.exe"
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DARKTABLE_BIN_DIR` | `C:\Program Files\darktable\bin` | darktable's `bin` folder — where `gdbus.exe` (and `darktable.exe`) live. The bundled `gdbus` is preferred so the DBus session bus matches the one darktable registered on. |
| `DARKTABLE_MCP_TIMEOUT` | `30` | Default per-call timeout, in seconds. Raise it for slow full-resolution exports of large raws. |

---

## Usage — the live loop

**Open darktable first.** The server talks to a running GUI session, so launch darktable and let
it finish loading before you start.

Then just talk to Claude. A realistic exchange:

> **You:** Open the barn photo and make it warmer and moodier.
>
> **Claude:** *calls `open_in_darkroom("barn")`, then `apply_look("moody")`, then `get_preview` to
> see the result* — "Here's the barn with a moodier grade: cooler-then-warm balance, deeper
> shadows, a touch less saturation. Want it warmer still, or should I open the shadows back up?"
>
> **You:** A bit warmer, and lift the shadows so the barn wall isn't so dark.
>
> **Claude:** *calls `adjust("warmth", "up", 2)` and `adjust("shadows", "up", 3)`, previews again* —
> "Warmer and the wall reads better now. Happy with this? I can save it as a reusable style."
>
> **You:** Love it — save it and give it 4 stars.
>
> **Claude:** *`create_style_from_current("Barn Dusk")`, `set_rating(4)`* — "Saved and rated."

The rhythm is: **open → apply a look → preview → nudge → preview → save/rate/export.** Claude reads
the built-in `darktable_guide` to translate your words ("moody", "faded", "punchier") into the
right controls.

---

## Tools reference

The server exposes **33 tools**. All editing/organizing tools act on the photo currently open in
the darkroom by default; those noted below accept `all_selected=true` to act on the entire
lighttable selection instead.

### Editing

| Tool | Parameters | Description |
|---|---|---|
| `open_in_darkroom` | `query` | Open the first photo whose filename contains `query` in the darkroom, so edits are visible. |
| `get_current_image` | — | Report which photo is open in the darkroom (the one edits apply to). |
| `adjust` | `control`, `direction`, `amount=3` | Nudge one control and watch it change live. `control`: brightness/exposure, warmth/temperature, tint, contrast, saturation, vibrance, shadows, highlights, filmic_contrast, whites, blacks. `direction`: up/down. `amount`: 1 (tiny) – 10 (large). |
| `reset_current` | — | Discard all edits on the current photo and start over. |

### Looks & styles

| Tool | Parameters | Description |
|---|---|---|
| `list_looks` | — | List the one-word semantic looks available to `apply_look`. |
| `apply_look` | `look` | Apply a one-word semantic look (e.g. `moody`, `golden`) by nudging several controls together. |
| `list_styles` | — | List the saved styles (looks) available in darktable. |
| `apply_style` | `name`, `all_selected=false` | Apply a saved style to the current photo — or the whole selection. |
| `create_style_from_current` | `name`, `description=""` | Save the current photo's edit as a reusable named style. |
| `build_starter_styles` | `image_query` | Build the 21 `MCP - …` starter styles on the given photo and save them (the photo's edits are reset afterward, leaving it untouched). |
| `import_style` | `path` | Import a `.dtstyle` file (e.g. a downloaded style or LUT-based look pack). |
| `export_style` | `name`, `directory` | Export a saved style to a `.dtstyle` file to share or back up. |
| `delete_style` | `name` | Delete a saved style by name. |
| `copy_edit` | `from_query`, `all_selected=false` | Copy the full edit from one photo (matched by filename substring) onto the current photo or the whole selection. |

### Preview

| Tool | Parameters | Description |
|---|---|---|
| `get_preview` | `max_size=1024` | Render the current darkroom edit to a JPEG (long edge capped at `max_size`, 64–4096) so Claude can **see** the result. |

### Organizing

| Tool | Parameters | Description |
|---|---|---|
| `set_rating` | `rating`, `all_selected=false` | Set the star rating: `-1` reject, `0` none, `1`–`5` stars. |
| `get_labels` | — | Get the current photo's star rating and color labels. |
| `set_color_label` | `color`, `on=true`, `all_selected=false` | Toggle a color label: red/yellow/green/blue/purple. |
| `add_tag` | `tag`, `all_selected=false` | Attach a keyword tag, creating it if needed. |
| `remove_tag` | `tag`, `all_selected=false` | Detach a tag from the current photo (or the selection). |
| `get_tags` | — | List the tags attached to the current photo. |
| `set_metadata` | `field`, `value` | Set a metadata field: title/creator/publisher/rights/description. |
| `get_metadata` | — | Get the current photo's metadata, key EXIF (camera, lens, ISO, aperture, exposure), and GPS. |
| `set_location` | `latitude`, `longitude`, `elevation=None` | Geotag the current photo with GPS coordinates (elevation in metres, optional). |

### Library & export

| Tool | Parameters | Description |
|---|---|---|
| `list_images` | `filter=""`, `limit=50` | List photos in the library, optionally filtered by a filename substring. |
| `list_collection` | `limit=100` | List photos in darktable's current collection (the active lighttable filter). |
| `get_selection` | — | List the photos currently selected in the lighttable. |
| `duplicate_image` | — | Create a virtual copy of the current photo with its own independent edits. |
| `import_images` | `path` | Import a photo file or a whole folder into the library. |
| `export_image` | `path`, `format="jpeg"`, `max_size=0` | Export the current edited photo to a real file. `format`: jpeg/png/tiff. `max_size`: cap the long edge in pixels (`0` = full resolution). The parent folder must already exist. |

### Diagnostics

| Tool | Parameters | Description |
|---|---|---|
| `dt_status` | — | Check whether darktable is running; report version, Lua API, and image count. |
| `diagnose` | — | Troubleshoot the connection: gdbus path, whether darktable is running, version, config directory, and any stale lock files. Call this first when other tools fail. |
| `darktable_guide` | — | Return the intent→control guide Claude uses to translate plain-language requests. (Also exposed as the `darktable://guide` MCP resource.) |

---

## Control vocabulary & semantic looks

### Controls (all validated live against darktable 5.6.0)

Friendly names you can ask Claude to `adjust`, and the darktable module/slider each maps to:

| Friendly name | darktable action path |
|---|---|
| `brightness` / `exposure` | `iop/exposure/exposure` |
| `warmth` / `temperature` | `iop/temperature/temperature` |
| `tint` | `iop/temperature/tint` |
| `contrast` | `iop/colorbalancergb/contrast` |
| `saturation` | `iop/colorbalancergb/global saturation` |
| `vibrance` | `iop/velvia/strength` |
| `shadows` | `iop/shadhi/shadows` |
| `highlights` | `iop/shadhi/highlights` |
| `filmic_contrast` | `iop/filmicrgb/contrast` |
| `whites` | `iop/filmicrgb/white relative exposure` |
| `blacks` | `iop/filmicrgb/black relative exposure` |

### Semantic looks (`apply_look`)

`warmer` · `cooler` · `brighter` · `darker` · `punchy` · `vivid` · `muted` · `faded` · `moody` ·
`golden` · `cinematic` · `soft`

Each is a curated sequence of nudges — for example, `moody` cools the white balance, dims the
image, drops saturation, adds contrast, and deepens the shadows.

### The `MCP - …` starter style pack (`build_starter_styles`)

Running `build_starter_styles` bakes **21** reusable styles from the live pipeline:

`Warm Punch` · `Golden Hour` · `Moody` · `Vivid Pop` · `Faded Film` · `Cinematic` ·
`Teal & Orange` · `Nordic Cool` · `Vintage Matte` · `Bright & Airy` · `Low Key` · `Autumn Warmth` ·
`Pastel Portrait` · `Landscape Pop` · `Sunset Glow` · `Clean Neutral` · `Stormy Sky` ·
`Retro Film` · `Punchy Street` · `Dreamy Soft` · `Rich & Deep`

They're saved in darktable prefixed with `MCP - ` (e.g. `MCP - Golden Hour`) so `list_styles` and
`apply_style` can find them.

---

## Troubleshooting

**Start with `diagnose`.** When any tool misbehaves, ask Claude to run `diagnose` — it reports the
gdbus path (and whether it exists), whether darktable is running, its version, the config
directory, the current timeout, and any stale lock files, all without assuming darktable is up.

| Symptom | Cause & fix |
|---|---|
| *"darktable is not running"* | The GUI isn't open. This bridge drives a live session; `darktable-cli` does not expose it. Open the darktable GUI and try again. |
| *"lost connection to darktable"* after it was working | darktable crashed or was closed. Reopen it. If a crash left stale `library.db.lock` / `data.db.lock` files in the config dir (`%LOCALAPPDATA%\darktable`), they'll block the next launch — delete them. `diagnose` lists their exact paths. |
| *"gdbus not found"* | The bridge couldn't find `gdbus.exe`. Set `DARKTABLE_BIN_DIR` to your darktable `bin` folder (the one with `gdbus.exe` and `darktable.exe`). |
| Timeout, especially on a full-resolution export | Large raws render slowly. `export_image` gets a generous 300s budget, but you can raise the general timeout via `DARKTABLE_MCP_TIMEOUT` (seconds) or export at a capped `max_size` (e.g. 2560). A mid-render abort can crash darktable, so the bridge reports the timeout rather than retrying. |

---

## Limitations / not yet supported

- **Relative nudges, not absolute values.** darktable's sliders read back in mixed units (some
  normalized, some native), so Claude adjusts controls up/down rather than setting exact numbers.
  This suits the conversational, watch-it-change loop.
- **A live GUI session is required.** This is not a headless renderer; it drives the running
  darktable GUI. (Headless export via `darktable-cli` is a possible later addition.)
- **Crop / rotate are deferred.** The geometry modules are reachable via the action system but
  produced no change in the exported render — they appear to need the interactive crop commit the
  action bridge doesn't trigger. Left out rather than shipped as no-ops.
- **LUTs only via styles.** There's no direct LUT tool; import a LUT-based `.dtstyle` look pack with
  `import_style`, then apply it.
- **No delete or move.** Removing images from the library or moving files on disk is intentionally
  omitted to keep the server safe to hand to an assistant.

---

## Development

### Project layout

```
dark-table-mcp/
├── darktable_mcp/
│   ├── server.py         # the MCP tools (FastMCP) — the source of truth for the tool list
│   ├── bridge.py         # DBus Remote.Lua transport via gdbus; error types; diagnose()
│   ├── controls.py       # control registry, semantic looks, starter styles, the intent guide
│   ├── config.py         # binary/gdbus location, DBus constants, timeout
│   ├── extra_styles.py   # 15 additional starter-style recipes (merged into the pack)
│   └── lua/
│       └── dtmcp.lua     # companion Lua helper, auto-injected into the live session
├── docs/plans/2026-07-05-darktable-mcp-design.md
├── tests/
└── pyproject.toml        # deps, entry point (darktable-mcp), Python 3.10+
```

### Running the tests

```powershell
pytest -m "not integration"     # unit tests — mocked gdbus, no darktable needed
pytest -m integration           # smoke tests — require a running darktable GUI
```

Unit tests cover bridge reply-parsing and error mapping and assert that the Python and Lua control
registries stay in sync. The integration marker is opt-in (skipped in CI) because it needs a live
session.

---

## License

MIT. See the license field in `pyproject.toml`.
