# dark-table-mcp

Goal: build an MCP server that lets AI agents drive [darktable](https://www.darktable.org/) —
the open-source (GPL) non-destructive RAW photo editor — for library queries, metadata edits,
style application, and headless exports.

## Research notes — read these first

All darktable research lives in the Obsidian vault, NOT in this repo:

```
C:\Users\CalebBennett\Documents\Notes\Caleb's Vault\Software\DarkTable\
```

Start at `DarkTable MOC.md` — it indexes ~100 atomized notes (one concept per note,
filenames like `DarkTable - <Concept>.md`). Most notes carry an "MCP relevance" line.

### Note conventions (follow when adding findings)

Any NEW darktable finding made while working in this repo goes into that Notes folder,
not into this repo's docs:

- One concept per note, filename `DarkTable - <Concept>.md`
- YAML frontmatter: `tags: [darktable, research]`, `source: <url>`, `created: <date>`
- 3–10 sentence self-contained body, wikilinks to related notes, `[[DarkTable MOC]]` at the bottom
- Add an "MCP relevance" line when the concept affects MCP design
- Add the new note to `DarkTable MOC.md` under the right section
- Check for an existing note on the concept first — update it rather than duplicating

## Key integration surfaces (details in the notes)

- **Lua API** (`[[DarkTable - Lua API Overview]]`, API v9.x): the primary automation surface —
  database, tags, styles, collection, export storage, events.
- **DBus `Remote.Lua`** (`[[DarkTable - Lua DBus Interface]]`): send a Lua string to a *live*
  darktable session, get a string back — the leading MCP bridge candidate. **Validated working
  on this machine** (darktable 5.6.0, Lua API 9.7.0, Windows) — see
  `[[DarkTable - DBus Validation (Local Install)]]`. Use the bundled
  `C:\Program Files\darktable\bin\gdbus.exe`; the GUI must be running; Lua must `require 'darktable'`
  (the global isn't preset); replies come back as a tuple `('...',)`. Issue #17896 does NOT affect
  this build.
- **`darktable-cli`** (`[[DarkTable - darktable-cli]]`): headless export/processing without a GUI.
- **Library database + XMP sidecars** (`[[DarkTable - Library Database]]`,
  `[[DarkTable - XMP Sidecar Files]]`): library.db is SQLite but **single-instance locked**
  (`[[DarkTable - Database Locking]]`) and takes precedence over XMPs — never write to it while
  darktable runs; prefer the Lua/DBus path or XMP + startup sync.
- **Companion Lua script** (`[[DarkTable - Lua Startup Scripts (luarc)]]`): the MCP server will
  likely ship a Lua helper loaded via luarc/script manager.

## Prior art (don't reinvent — study these first)

A darktable MCP already exists but only as early prototypes; the space is claimed but wide open.
See `[[DarkTable - Existing MCP Projects]]` for the full landscape. Key references:

- **w1ne/darktable-mcp** (Python+Lua) — drives a live session via a Lua plugin + file-based
  JSON-RPC + darktable-cli. Best live-control reference. Our DBus `Remote.Lua` approach is a
  cleaner bridge than its file-based polling.
- **YaddyVirus/darktable-mcp** (Python) — doesn't control darktable; emits `.xmp` sidecars only.
- **lucamarien/rawtherapee-mcp-server** — borrow its inline Base64 preview pattern (visual feedback
  loop for the LLM).
- **Automaat/lightroom-mcp** — most mature socket-plugin template (TS + Lua, CI/tests).
