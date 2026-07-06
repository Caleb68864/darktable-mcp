-- dtmcp.lua -- helper functions for darktable-mcp.
-- Injected into a live darktable session over DBus Remote.Lua by the Python bridge.
-- Every function returns a JSON string (the bridge decodes it). No external deps.

local dt = require "darktable"

dtmcp = dtmcp or {}
dtmcp._current = dtmcp._current or nil  -- last image opened in the darkroom by us

-- ---- minimal JSON encoder ------------------------------------------------

local function esc(s)
  return (s:gsub('[%z\1-\31\\"]', function(c)
    local map = { ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n',
                  ['\r'] = '\\r', ['\t'] = '\\t' }
    return map[c] or string.format('\\u%04x', c:byte())
  end))
end

local function encode(v)
  local t = type(v)
  if v == nil then return "null"
  elseif t == "boolean" then return tostring(v)
  elseif t == "number" then
    if v ~= v then return "null" end        -- NaN -> null
    return string.format("%.6g", v)
  elseif t == "string" then return '"' .. esc(v) .. '"'
  elseif t == "table" then
    local n = 0
    for _ in pairs(v) do n = n + 1 end
    if n == #v then                          -- array
      local parts = {}
      for i = 1, #v do parts[i] = encode(v[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    local parts = {}                         -- object
    for k, val in pairs(v) do
      parts[#parts + 1] = '"' .. esc(tostring(k)) .. '":' .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return "null"
end

dtmcp._encode = encode

-- ---- control registry (validated live) ----------------------------------

local CONTROLS = {
  brightness      = "iop/exposure/exposure",
  exposure        = "iop/exposure/exposure",
  warmth          = "iop/temperature/temperature",
  temperature     = "iop/temperature/temperature",
  tint            = "iop/temperature/tint",
  contrast        = "iop/colorbalancergb/contrast",
  saturation      = "iop/colorbalancergb/global saturation",
  vibrance        = "iop/velvia/strength",
  shadows         = "iop/shadhi/shadows",
  highlights      = "iop/shadhi/highlights",
  filmic_contrast = "iop/filmicrgb/contrast",
  whites          = "iop/filmicrgb/white relative exposure",
  blacks          = "iop/filmicrgb/black relative exposure",
}

-- ---- internal helpers ----------------------------------------------------

local function current_image()
  if dtmcp._current then return dtmcp._current end
  local sel = dt.gui.selection()
  return sel and sel[1] or nil
end

-- Images to act on: the lighttable selection if `all_selected` and non-empty, else current image.
local function targets(all_selected)
  if all_selected then
    local s = dt.gui.selection()
    if s and #s > 0 then return s end
  end
  local img = current_image()
  return img and { img } or {}
end

local function image_info(img)
  if not img then return nil end
  return {
    filename = img.filename,
    path = img.path,
    rating = img.rating,
    id = img.id,
  }
end

-- ---- public API ----------------------------------------------------------

function dtmcp.status()
  local c = dt.configuration
  return encode({
    version = c.version,
    api = c.api_version_string,
    os = c.running_os,
    images = #dt.database,
  })
end

function dtmcp.list_images(filter, limit)
  filter = filter and filter:lower() or nil
  limit = limit or 50
  local out = {}
  for i = 1, #dt.database do
    local img = dt.database[i]
    if (not filter) or img.filename:lower():find(filter, 1, true) then
      out[#out + 1] = { filename = img.filename, path = img.path, rating = img.rating }
      if #out >= limit then break end
    end
  end
  return encode({ count = #out, images = out })
end

function dtmcp.open_in_darkroom(query)
  query = query and query:lower() or ""
  for i = 1, #dt.database do
    local img = dt.database[i]
    if img.filename:lower():find(query, 1, true) then
      dt.gui.views.darkroom.display_image(img)
      dtmcp._current = img
      -- The view switch + image load is asynchronous; wait until darkroom is actually active
      -- (and the pixelpipe has the image) before returning, so a following adjust lands.
      local darkroom = dt.gui.views.darkroom
      for _ = 1, 40 do
        if dt.gui.current_view() == darkroom then break end
        dt.control.sleep(50)
      end
      dt.control.sleep(200)
      return encode({ opened = image_info(img), view = dt.gui.current_view().id })
    end
  end
  return encode({ error = "no image matching '" .. query .. "'" })
end

function dtmcp.get_current_image()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  return encode({ image = image_info(img) })
end

function dtmcp.adjust(control, direction, amount)
  local path = CONTROLS[control and control:lower() or ""]
  if not path then return encode({ error = "unknown control: " .. tostring(control) }) end
  local effect = (direction == "down") and "down" or "up"
  amount = tonumber(amount) or 3
  local module = path:gsub("/[^/]*$", "")
  dt.gui.action(module, 0, "on", 1)                 -- ensure module enabled
  dt.gui.action(path, 0, "value", effect, amount)   -- the live nudge
  local value = dt.gui.action(path, 0, "value", "", 0)
  return encode({ control = control, direction = effect, amount = amount, value = value })
end

function dtmcp.list_styles()
  local out = {}
  for i = 1, #dt.styles do
    local s = dt.styles[i]
    out[#out + 1] = { name = s.name, description = s.description }
  end
  return encode({ count = #out, styles = out })
end

function dtmcp.apply_style(name, all_selected)
  local style
  for i = 1, #dt.styles do
    if dt.styles[i].name == name then style = dt.styles[i] end
  end
  if not style then return encode({ error = "style not found: " .. tostring(name) }) end
  local imgs = targets(all_selected)
  if #imgs == 0 then return encode({ error = "no image open in the darkroom" }) end
  for _, img in ipairs(imgs) do dt.styles.apply(style, img) end
  return encode({ applied = name, count = #imgs })
end

function dtmcp.import_style(path)
  if not path or path == "" then return encode({ error = "path required" }) end
  local before = #dt.styles
  dt.styles.import(path)
  return encode({ imported = path, styles_added = #dt.styles - before, total = #dt.styles })
end

function dtmcp.export_style(name, directory)
  for i = 1, #dt.styles do
    if dt.styles[i].name == name then
      dt.styles.export(dt.styles[i], directory)
      return encode({ exported = name, directory = directory })
    end
  end
  return encode({ error = "style not found: " .. tostring(name) })
end

function dtmcp.delete_style(name)
  for i = 1, #dt.styles do
    if dt.styles[i].name == name then
      dt.styles.delete(dt.styles[i])
      return encode({ deleted = name })
    end
  end
  return encode({ error = "style not found: " .. tostring(name) })
end

-- Copy the full edit from one photo onto the current image (or the whole selection), via a
-- temporary style. `from_query` is a filename substring of the source photo.
function dtmcp.copy_edit(from_query, all_selected)
  from_query = from_query and from_query:lower() or ""
  local source
  for i = 1, #dt.database do
    if dt.database[i].filename:lower():find(from_query, 1, true) then source = dt.database[i]; break end
  end
  if not source then return encode({ error = "no source image matching '" .. from_query .. "'" }) end
  local imgs = targets(all_selected)
  if #imgs == 0 then return encode({ error = "no target image" }) end
  local tmp = "__dtmcp_copyedit__"
  for i = #dt.styles, 1, -1 do if dt.styles[i].name == tmp then dt.styles.delete(dt.styles[i]) end end
  dt.styles.create(source, tmp, "")
  local style
  for i = 1, #dt.styles do if dt.styles[i].name == tmp then style = dt.styles[i] end end
  for _, img in ipairs(imgs) do dt.styles.apply(style, img) end
  dt.styles.delete(style)
  return encode({ copied_from = source.filename, count = #imgs })
end

function dtmcp.create_style_from_current(name, description)
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  dt.styles.create(img, name, description or "")
  return encode({ created = name })
end

function dtmcp.reset_current()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  img:reset()
  return encode({ reset = img.filename })
end

-- Export the current edit to a JPEG at `path` (forward-slash path). `max_size` caps the long edge.
function dtmcp.export_preview(path, max_size)
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  max_size = tonumber(max_size) or 1024
  local fmt = dt.new_format("jpeg")
  fmt.quality = 88
  fmt.max_width = max_size
  fmt.max_height = max_size
  -- high_quality=true forces a complete render through the export pipeline (deterministic),
  -- instead of grabbing the darkroom's still-rendering preview cache.
  fmt:write_image(img, path, true)
  return encode({ path = path, image = img.filename })
end

-- Export the current edit to a real file at `path`, format inferred from `ext` (jpeg/png/tiff).
function dtmcp.export_image(path, ext, max_size)
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  ext = (ext or "jpeg"):lower()
  local fmt = dt.new_format(ext)
  if ext == "jpeg" or ext == "jpg" then fmt.quality = 95 end
  if max_size and tonumber(max_size) then
    fmt.max_width = tonumber(max_size)
    fmt.max_height = tonumber(max_size)
  end
  fmt:write_image(img, path, true)
  return encode({ exported = path, image = img.filename })
end

-- ---- organizing: ratings, labels, tags, metadata --------------------------

local COLOR_LABELS = { red = true, yellow = true, green = true, blue = true, purple = true }

function dtmcp.set_rating(rating, all_selected)
  rating = tonumber(rating)
  if not rating or rating < -1 or rating > 5 then
    return encode({ error = "rating must be -1 (reject) to 5" })
  end
  local imgs = targets(all_selected)
  for _, img in ipairs(imgs) do img.rating = rating end
  return encode({ rating = rating, count = #imgs })
end

function dtmcp.set_color_label(color, on, all_selected)
  color = color and color:lower() or ""
  if not COLOR_LABELS[color] then
    return encode({ error = "color must be red/yellow/green/blue/purple" })
  end
  local imgs = targets(all_selected)
  for _, img in ipairs(imgs) do img[color] = (on and true or false) end
  return encode({ color = color, on = (on and true or false), count = #imgs })
end

function dtmcp.get_labels()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  local labels = {}
  for c in pairs(COLOR_LABELS) do if img[c] then labels[#labels + 1] = c end end
  return encode({ rating = img.rating, labels = labels })
end

function dtmcp.add_tag(tag, all_selected)
  if not tag or tag == "" then return encode({ error = "tag name required" }) end
  local t = dt.tags.create(tag)
  local imgs = targets(all_selected)
  for _, img in ipairs(imgs) do img:attach_tag(t) end
  return encode({ tag = tag, attached = #imgs })
end

function dtmcp.remove_tag(tag, all_selected)
  local t = dt.tags.find(tag)
  if not t then return encode({ error = "tag not found: " .. tostring(tag) }) end
  local imgs = targets(all_selected)
  for _, img in ipairs(imgs) do img:detach_tag(t) end
  return encode({ tag = tag, detached = #imgs })
end

function dtmcp.get_tags()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  local out = {}
  for _, t in ipairs(img:get_tags()) do out[#out + 1] = t.name end
  return encode({ tags = out })
end

local META_FIELDS = { title = true, creator = true, publisher = true, rights = true, description = true }

function dtmcp.set_metadata(field, value)
  field = field and field:lower() or ""
  if not META_FIELDS[field] then
    return encode({ error = "field must be title/creator/publisher/rights/description" })
  end
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  img[field] = value or ""
  return encode({ field = field, value = img[field], image = img.filename })
end

function dtmcp.get_metadata()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  return encode({
    filename = img.filename,
    title = img.title, creator = img.creator, publisher = img.publisher,
    rights = img.rights, description = img.description,
    exif = {
      maker = img.exif_maker, model = img.exif_model, lens = img.exif_lens,
      iso = img.exif_iso, aperture = img.exif_aperture, exposure = img.exif_exposure,
      focal_length = img.exif_focal_length, datetime = img.exif_datetime_taken,
    },
    gps = { latitude = img.latitude, longitude = img.longitude, elevation = img.elevation },
  })
end

function dtmcp.set_location(latitude, longitude, elevation)
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  if latitude ~= nil then img.latitude = tonumber(latitude) end
  if longitude ~= nil then img.longitude = tonumber(longitude) end
  if elevation ~= nil then img.elevation = tonumber(elevation) end
  return encode({ latitude = img.latitude, longitude = img.longitude, elevation = img.elevation })
end

-- ---- browsing: collection, selection, duplicate, import ------------------

function dtmcp.list_collection(limit)
  limit = tonumber(limit) or 100
  local out = {}
  for i = 1, #dt.collection do
    local img = dt.collection[i]
    out[#out + 1] = { filename = img.filename, rating = img.rating }
    if #out >= limit then break end
  end
  return encode({ count = #out, images = out })
end

function dtmcp.get_selection()
  local s = dt.gui.selection()
  local out = {}
  for i = 1, #s do out[#out + 1] = s[i].filename end
  return encode({ count = #out, selection = out })
end

function dtmcp.duplicate_image()
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  local dup = img:duplicate()
  return encode({ duplicated = img.filename, new_id = dup.id })
end

function dtmcp.import_images(path)
  if not path or path == "" then return encode({ error = "path required" }) end
  local imported = dt.database.import(path)
  local n = 0
  if type(imported) == "table" then n = #imported elseif imported then n = 1 end
  return encode({ imported = n, path = path })
end

return "dtmcp loaded"
