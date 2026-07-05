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
  brightness  = "iop/exposure/exposure",
  exposure    = "iop/exposure/exposure",
  warmth      = "iop/temperature/temperature",
  temperature = "iop/temperature/temperature",
  tint        = "iop/temperature/tint",
  contrast    = "iop/colorbalancergb/contrast",
  saturation  = "iop/colorbalancergb/global saturation",
  vibrance    = "iop/velvia/strength",
}

-- ---- internal helpers ----------------------------------------------------

local function current_image()
  if dtmcp._current then return dtmcp._current end
  local sel = dt.gui.selection()
  return sel and sel[1] or nil
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
      dt.gui.action("views/darkroom", 0, "", 1)
      dt.gui.views.darkroom.display_image(img)
      dtmcp._current = img
      return encode({ opened = image_info(img) })
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

function dtmcp.apply_style(name)
  local img = current_image()
  if not img then return encode({ error = "no image open in the darkroom" }) end
  for i = 1, #dt.styles do
    if dt.styles[i].name == name then
      dt.styles.apply(dt.styles[i], img)
      return encode({ applied = name, image = img.filename })
    end
  end
  return encode({ error = "style not found: " .. tostring(name) })
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

return "dtmcp loaded"
