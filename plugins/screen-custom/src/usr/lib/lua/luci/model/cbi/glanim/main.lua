local uci = require("luci.model.uci").cursor()
local sys = require "luci.sys"
local util = require "luci.util"
local json = require "luci.jsonc"
local fs = require "nixio.fs"

local FRAMES_DEFAULT = "/usr/share/glanim/frames"
local FRAME_BYTES = 76 * 284 * 2
local VERSION = "1.9.6"
local ASSET_VERSION = "20261027-fps15"

local function h(value)
	return util.pcdata(tostring(value or ""))
end

local function cfg_str(key, default)
	local v = uci:get("glanim", "globals", key)
	if type(v) == "table" then v = v[1] end
	if v == nil or v == "" then return default end
	return tostring(v)
end

local function cfg_num(key, default, lo, hi)
	local v = tonumber(cfg_str(key, tostring(default))) or default
	v = math.floor(v)
	if v < lo then v = lo end
	if v > hi then v = hi end
	return v
end

local function cfg_bool(key, default)
	local v = cfg_str(key, default and "1" or "0")
	return v == "1"
end

local function safe_dir(path)
	if type(path) ~= "string" then return nil end
	if #path < 2 or #path > 180 then return nil end
	if not path:match("^/[%w%._/%-]+$") then return nil end
	if path:find("%.%.") then return nil end
	path = path:gsub("/+$", "")
	if path == "" then return nil end
	return path
end

local function read_raw(path)
	local f = io.open(path, "r")
	if f then
		local v = f:read("*l")
		f:close()
		return v
	end
	return nil
end

local function read_status_file()
	local f = io.open("/tmp/glanim.status", "r")
	if not f then return nil end
	local d = {}
	for line in f:lines() do
		local k, v = line:match("^([^=]+)=(.*)$")
		if k then d[k] = v end
	end
	f:close()
	return d
end

local function read_manifest(dir)
	local f = io.open(dir .. "/manifest.json", "r")
	if not f then return nil end
	local text = f:read("*a")
	f:close()
	if not text or text == "" then return nil end
	local ok, m = pcall(json.parse, text)
	if not ok or type(m) ~= "table" then return nil end
	return m
end

local status = read_status_file()
local dir = safe_dir(cfg_str("frames_dir", FRAMES_DEFAULT)) or FRAMES_DEFAULT
local manifest = read_manifest(dir)

local pack_count, pack_missing = 0, 0
local pack_source = ""
local pack_delays = {}
local pack_valid = false
if manifest and type(manifest.frames) == "table" then
	for i = 1, #manifest.frames do
		local fr = manifest.frames[i]
		if type(fr) == "table" and type(fr.file) == "string" and fr.file ~= "" then
			pack_count = pack_count + 1
			if #pack_delays < 60 then
				local d = tonumber(fr.delay_ms) or 100
				pack_delays[#pack_delays + 1] = math.max(30, math.min(1000, math.floor(d)))
			end
			local st = fs.stat(dir .. "/" .. fr.file)
			if not st or st.size ~= FRAME_BYTES then pack_missing = pack_missing + 1 end
		end
	end
	pack_source = tostring(manifest.source or "")
	pack_valid = pack_count > 0 and pack_missing == 0
end

local DEFAULT_LAYOUT = {
	bg = "#0a0c12",
	elements = {
		{ type = "text", x = 6, y = 4, size = 1, color = "#c2ccdc", text = "CPU" },
		{ type = "bar", x = 36, y = 3, w = 150, h = 8, source = "cpu", color = "auto" },
		{ type = "value", x = 192, y = 3, size = 1, color = "#eef2fa", source = "cpu", suffix = "%" },
		{ type = "text", x = 6, y = 28, size = 1, color = "#c2ccdc", text = "MEM" },
		{ type = "bar", x = 36, y = 27, w = 150, h = 8, source = "mem", color = "auto" },
		{ type = "value", x = 192, y = 27, size = 1, color = "#eef2fa", source = "mem", suffix = "%" },
		{ type = "text", x = 6, y = 52, size = 1, color = "#c2ccdc", text = "TMP" },
		{ type = "bar", x = 36, y = 51, w = 150, h = 8, source = "temp", color = "auto" },
		{ type = "value", x = 192, y = 51, size = 1, color = "#eef2fa", source = "temp", suffix = "C" },
		{ type = "value", x = 232, y = 4, size = 1, color = "#eef2fa", source = "fan_rpm", suffix = " RPM" },
		{ type = "value", x = 232, y = 28, size = 1, color = "#c2ccdc", source = "clock" },
		{ type = "value", x = 232, y = 52, size = 1, color = "#c2ccdc", source = "date" },
	},
}

local custom_layout = nil
local custom_raw = cfg_str("custom_layout", "")
if custom_raw ~= "" then
	local ok, parsed = pcall(json.parse, custom_raw)
	if ok and type(parsed) == "table" then custom_layout = parsed end
end
if type(custom_layout) ~= "table" then custom_layout = DEFAULT_LAYOUT end

local custom_bg_dir = cfg_str("custom_bg_dir", "/usr/share/glanim/custom_bg")
local custom_bg_frames = tonumber(cfg_str("custom_bg_frames", "0")) or 0
local custom_bg_fps = tonumber(cfg_str("custom_bg_fps", "8")) or 8
local bg_mask = tonumber(cfg_str("bg_mask", "20")) or 45
local bg_blur = tonumber(cfg_str("bg_blur", "0")) or 0
local content_alpha = tonumber(cfg_str("content_alpha", "100")) or 100
local menu_lang = cfg_str("menu_lang", "auto")
local menu_pages = tonumber(cfg_str("menu_pages", "2")) or 2
local menu_page1 = cfg_str("menu_page1", "poweroff,reboot,wifi,next")
local menu_page2 = cfg_str("menu_page2", "clash,brightness,fan,back")
local menu_page3 = cfg_str("menu_page3", "wifi,brightness,clash,exit")
if bg_mask < 0 then bg_mask = 0 end
if bg_mask > 100 then bg_mask = 100 end

local PAGE = { "admin", "services", "glanim" }
local function page_url(...)
	return luci.dispatcher.build_url(PAGE[1], PAGE[2], PAGE[3], ...)
end

local cur_lang = (luci.i18n.context and luci.i18n.context.lang) or "zh-cn"
local is_zh = (cur_lang:sub(1, 2) == "zh")
local cur_enabled = cfg_bool("enabled", false)
local cur_mode = cfg_str("mode", "gif")
if cur_mode ~= "gif" and cur_mode ~= "dashboard" and cur_mode ~= "custom" and cur_mode ~= "clash" then
	cur_mode = "gif"
end
local cur_fps = cfg_num("fps", 0, 0, 30)
local cur_loop = cfg_bool("loop", true)
local cur_bright = cfg_num("brightness", 4, 0, 11)
local cur_keep = cfg_bool("keep_original", true)
local cur_show_time = cfg_bool("show_time", true)
local cur_show_cpu = cfg_bool("show_cpu", true)
local cur_show_mem = cfg_bool("show_mem", true)
local cur_show_temp = cfg_bool("show_temp", true)
local cur_show_net = cfg_bool("show_net", true)
local cur_show_uptime = cfg_bool("show_uptime", false)
local cur_show_ip = cfg_bool("show_ip", false)
local cur_interval = cfg_num("dash_interval", 5, 2, 30)
local cur_auto_rotate = cfg_bool("auto_rotate", true)
local cur_touch = cfg_bool("touch_enable", true)
local cur_touch_action = cfg_str("touch_action", "next")
if cur_touch_action ~= "next" and cur_touch_action ~= "wake" and cur_touch_action ~= "none" then
	cur_touch_action = "next"
end
local cur_touch_swap = cfg_bool("touch_swap_xy", false)
local cur_touch_flip = cfg_bool("touch_flip_x", true)

local daemon_pid = (sys.exec("pgrep -f /usr/bin/glanimd") or ""):gsub("%s+", "")
local screen_pid = (sys.exec("pidof gl_screen") or ""):gsub("%s+", "")
local daemon_on = #daemon_pid > 0
local screen_on = #screen_pid > 0
local bright = read_raw("/sys/class/backlight/soc:backlight/brightness") or "-"
local live_error = (status and status.error) or ""
local oc_installed = fs.access("/etc/init.d/openclash")
local oc_enabled = uci:get("openclash", "config", "enable") == "1"
local oc_running = #((sys.exec("pidof clash") or ""):gsub("%s+", "")) > 0
local oc_mode = (sys.exec("uci -q get openclash.config.proxy_mode") or "rule"):gsub("%s+", "")

local function icon(name, cls)
	local paths = {
		download = '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/>',
		screen = '<rect x="3" y="4.5" width="18" height="12.5" rx="2.2"/><path d="M8.5 21h7M12 17v4"/><path d="M7 9.5h5M7 12.5h3"/>',
		gif = '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="M7 9h4M7 12h6M7 15h3"/><circle cx="16.5" cy="9" r="1.2" fill="currentColor" stroke="none"/>',
		still = '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><circle cx="8.5" cy="10" r="1.6"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
		slideshow = '<rect x="5" y="3.5" width="14" height="13" rx="2"/><path d="M9 20.5h6M12 16.5v4"/><path d="M9 10l3-2.2L15 10v4.2H9z"/>',
		dashboard = '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="M3 11h18M11 11v8.5"/><path d="M7 7.5h2M14 14.5h4M14 17.5h4"/>',
		custom = '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h12M20 17h0"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="18" cy="17" r="2"/>',
		clash = '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
		save = '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v6h7V4M8 20v-6h8v6"/>',
		refresh = '<path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 4v7h-7"/>',
		undo = '<path d="M9 7L4 12l5 5"/><path d="M4 12h9a6 6 0 1 1 0 12"/>',
		upload = '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
		image = '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><circle cx="8.5" cy="10" r="1.6"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
		chip = '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>',
		thermo = '<path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z"/><path d="M12 8v7"/>',
		net = '<path d="M4 17h16M7 17a5 5 0 0 1 10 0M10 17a2 2 0 0 1 4 0"/><path d="M12 4v6"/>',
		clock = '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
		check = '<path d="M4 12l5 5L20 6"/>',
		sliders = '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
	}
	return '<svg class="gl-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
		.. (paths[name] or paths.screen) .. '</svg>'
end

local function badge(text, cls)
	return '<span class="gl-badge ' .. (cls or "") .. '">' .. h(text) .. '</span>'
end

local mode_cards = {
	{ key = "gif", icon = "gif", title = translate("Frames / GIF / image"), sub = translate("Loop a frame pack; a one-frame pack holds as a still image.") },
	{ key = "dashboard", icon = "dashboard", title = translate("System panel"), sub = translate("Live clock, CPU, memory, temperature and network speed.") },
	{ key = "clash", icon = "clash", title = translate("OpenClash status"), sub = translate("Clash state, live rates, total traffic, connections and resources.") },
	{ key = "custom", icon = "custom", title = translate("Custom panel"), sub = translate("Design your own labels, values and progress bars.") },
}

local MODE_TITLE = {
	gif = translate("Frames / GIF / image"),
	still = translate("Still image"),
	slideshow = translate("Slideshow"),
	dashboard = translate("System panel"),
	clash = translate("OpenClash status"),
	custom = translate("Custom panel"),
}

local function mode_grid()
	local out = { '<div class="gl-mode-grid" id="gl-mode-grid" role="radiogroup" aria-label="' .. h(translate("Play mode")) .. '">' }
	for _, item in ipairs(mode_cards) do
		out[#out + 1] = '<button type="button" class="gl-mode' .. (cur_mode == item.key and " is-active" or "")
			.. '" data-mode="' .. item.key .. '" role="radio" aria-checked="'
			.. (cur_mode == item.key and "true" or "false") .. '">'
			.. '<span class="gl-mode-icon">' .. icon(item.icon) .. '</span>'
			.. '<span class="gl-mode-body"><strong>' .. h(item.title) .. '</strong><small>' .. h(item.sub) .. '</small></span>'
			.. '<span class="gl-mode-check">' .. icon("check") .. '</span></button>'
	end
	out[#out + 1] = '</div>'
	return table.concat(out)
end

local function switch_row(id, label, desc, checked)
	return '<label class="gl-switch" for="' .. id .. '">'
		.. '<span class="gl-switch-text"><strong>' .. h(label) .. '</strong>'
		.. (desc and ('<small>' .. h(desc) .. '</small>') or '') .. '</span>'
		.. '<input type="checkbox" id="' .. id .. '"' .. (checked and ' checked="checked"' or '') .. '>'
		.. '<span class="gl-switch-ui" aria-hidden="true"></span></label>'
end

local function check_tile(id, label, desc, checked)
	return '<label class="gl-check-tile" for="' .. id .. '">'
		.. '<input type="checkbox" id="' .. id .. '"' .. (checked and ' checked="checked"' or '') .. '>'
		.. '<span class="gl-check-box">' .. icon("check") .. '</span>'
		.. '<span class="gl-check-text"><strong>' .. h(label) .. '</strong>'
		.. (desc and ('<small>' .. h(desc) .. '</small>') or '') .. '</span></label>'
end

local lane_opts = {
	{ "next", translate("Switch page (tap left third = previous, rest = next)") },
	{ "wake", translate("Only record touch, do not switch pages") },
	{ "none", translate("Ignore touch") },
}
local function touch_options()
	local out = {}
	for _, item in ipairs(lane_opts) do
		out[#out + 1] = '<option value="' .. item[1] .. '"'
			.. (cur_touch_action == item[1] and ' selected="selected"' or '') .. '>'
			.. h(item[2]) .. '</option>'
	end
	return table.concat(out)
end

local pack_state = pack_valid and translate("Pack ready") or (pack_count > 0 and translate("Pack incomplete") or translate("No pack"))
local pack_state_cls = pack_valid and "ok" or (pack_count > 0 and "warn" or "")

local page_html = {}
local add = function(s) page_html[#page_html + 1] = s end

add('<link rel="stylesheet" href="/luci-static/resources/glanim/glanim.css?v=' .. ASSET_VERSION .. '">')
add('<div class="gl-page" id="glanim-page">')

-- ---------------- hero ----------------
add('<div class="gl-hero">')
add('<div class="gl-hero-main">')
add('<div class="gl-hero-icon">' .. icon("screen") .. '</div>')
add('<div class="gl-hero-text">')
add('<div class="gl-kicker">GL-BE3600 <span></span> 284 × 76 ST7789 <span></span> v' .. VERSION .. '</div>')
add('<h1>' .. h(translate("Screen Custom")) .. '</h1>')
add('<p>' .. h(translate("Replace the OEM gl_screen pages on the 284x76 ST7789 bar panel. Play an uploaded frame pack / GIF / image, or run a live system information panel.")) .. '</p>')
add('</div></div>')
add('<div class="gl-hero-side">')
add('<div class="gl-langbar">'
	.. '<a class="gl-lang' .. (is_zh and " is-active" or "") .. '" href="' .. page_url("set_lang") .. '?lang=zh-cn">中文</a>'
	.. '<a class="gl-lang' .. (not is_zh and " is-active" or "") .. '" href="' .. page_url("set_lang") .. '?lang=en">EN</a>'
	.. '</div>')
add('<div class="gl-live" id="gl-live"><span class="gl-live-dot" id="gl-live-dot"></span><span id="gl-live-text">'
	.. h(daemon_on and translate("Panel online") or translate("OEM screen")) .. '</span></div>')
add('</div></div>')

-- ---------------- status pills ----------------
add('<div class="gl-pills">')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Daemon")) .. '</span><strong id="gl-pill-daemon">' .. h(daemon_on and translate("running") or translate("stopped")) .. '</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Mode")) .. '</span><strong id="gl-pill-mode">' .. h(MODE_TITLE[cur_mode] or cur_mode) .. '</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Frames")) .. '</span><strong id="gl-pill-frames">' .. (pack_count > 0 and (pack_count .. "") or "–") .. '</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Backlight")) .. '</span><strong id="gl-pill-bright">' .. h(bright) .. '/11</strong></span>')
add('<span class="gl-pill gl-pill-state ' .. (daemon_on and "ok" or "") .. '" id="gl-pill-state"><span class="gl-pill-k">' .. h(translate("Screen")) .. '</span><strong id="gl-pill-state-v">'
	.. h(daemon_on and translate("plugin") or (screen_on and translate("OEM") or translate("unknown"))) .. '</strong></span>')
add('</div>')

-- ---------------- preview + basic settings ----------------
add('<div class="gl-grid">')
add('<section class="gl-card gl-preview-card">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Panel preview")) .. '</h2><p>' .. h(translate("A live 284 × 76 simulation of what the bar panel is showing.")) .. '</p></div>'
	.. '<span class="gl-badge ' .. (daemon_on and "ok" or "") .. '" id="glanim-preview-badge">' .. h(daemon_on and translate("live") or translate("idle")) .. '</span></div>')
add('<div class="gl-screen"><div class="gl-screen-bezel">'
	.. '<canvas id="glanim-preview-canvas" width="568" height="152" aria-label="' .. h(translate("Panel preview")) .. '"></canvas>'
	.. '<div class="gl-screen-empty" id="glanim-screen-empty"><span>' .. h(translate("No frame pack")) .. '</span><small>' .. h(translate("Upload an image or a frame pack to light up the panel.")) .. '</small></div>'
	.. '</div></div>')
add('<div class="gl-preview-foot"><span id="glanim-preview-caption">' .. h(translate("Waiting for status…")) .. '</span>'
	.. '<span id="glanim-preview-count"></span></div>')

add('<div class="gl-bg-tools">')
add('<div class="gl-bg-tools-head"><span>' .. h(translate("Background")) .. '</span>'
	.. '<span class="gl-bg-status" id="glanim-bg-status">' .. (custom_bg_frames > 0 and (h(custom_bg_frames) .. ' frames') or h(translate("Color background"))) .. '</span>'
	.. '<a class="gl-link" id="glanim-bg-download" href="#">' .. h(translate("Download")) .. '</a>'
	.. '<button type="button" class="gl-link" id="glanim-clear-bg">' .. h(translate("Clear background")) .. '</button></div>')
add('<div class="gl-range"><div class="gl-range-head"><label for="glanim-bg-mask">' .. h(translate("Background mask")) .. '</label><output id="glanim-bg-mask-val">' .. bg_mask .. '</output></div>'
	.. '<input type="range" id="glanim-bg-mask" min="0" max="100" step="1" value="' .. bg_mask .. '">'
	.. '<div class="gl-range-hint"><span>0 ' .. h(translate("original")) .. '</span><span>100 ' .. h(translate("black")) .. '</span></div></div>')
add('<div class="gl-range"><div class="gl-range-head"><label for="glanim-bg-blur">' .. h(translate("Frosted glass")) .. '</label><output id="glanim-bg-blur-val">' .. bg_blur .. '</output></div>'
	.. '<input type="range" id="glanim-bg-blur" min="0" max="100" step="1" value="' .. bg_blur .. '">'
	.. '<div class="gl-range-hint"><span>0 ' .. h(translate("off")) .. '</span><span>100 ' .. h(translate("strong")) .. '</span></div></div>')
add('<div class="gl-range"><div class="gl-range-head"><label for="glanim-content-alpha">' .. h(translate("Status opacity")) .. '</label><output id="glanim-content-alpha-val">' .. content_alpha .. '</output></div>'
	.. '<input type="range" id="glanim-content-alpha" min="0" max="100" step="1" value="' .. content_alpha .. '">'
	.. '<div class="gl-range-hint"><span>0 ' .. h(translate("transparent")) .. '</span><span>100 ' .. h(translate("opaque")) .. '</span></div></div>')
add('</div>')

add('<div class="gl-preview-tabs" id="glanim-preview-tabs" hidden>'
	.. '<button type="button" data-page="clock" class="is-active">' .. h(translate("Clock")) .. '</button>'
	.. '<button type="button" data-page="status">' .. h(translate("Status")) .. '</button>'
	.. '<button type="button" data-page="clash">' .. h(translate("Clash status")) .. '</button>'
	.. '<button type="button" data-page="clash_info">' .. h(translate("Clash info")) .. '</button>'
	.. '<button type="button" data-page="clash_node">' .. h(translate("Clash node")) .. '</button></div>')
add('</section>')

add('<section class="gl-card gl-basic-card">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Quick settings")) .. '</h2></div></div>')
add(switch_row("gl-enabled", translate("Screen enabled"), translate("Master switch: ON = third-party screen, OFF = disabled/OEM. Long-press the panel to return to OEM."), cur_enabled))
add('<div class="gl-range"><div class="gl-range-head"><label for="gl-brightness">' .. h(translate("Brightness")) .. '</label><output id="gl-brightness-val">' .. cur_bright .. '</output></div>'
	.. '<input type="range" id="gl-brightness" min="0" max="11" step="1" value="' .. cur_bright .. '">'
	.. '<div class="gl-range-hint"><span>0 · ' .. h(translate("off")) .. '</span><span>11 · ' .. h(translate("full")) .. '</span></div></div>')

add('<div class="gl-section-sep"></div>')
add('<div class="gl-section-label">' .. h(translate("Device monitoring")) .. '</div>')
add('<div class="gl-kpis">')
add('<div class="gl-kpi">' .. icon("chip") .. '<strong id="gl-kpi-cpu">–</strong><small>CPU</small></div>')
add('<div class="gl-kpi">' .. icon("chip") .. '<strong id="gl-kpi-mem">–</strong><small>' .. h(translate("Memory")) .. '</small></div>')
add('<div class="gl-kpi">' .. icon("thermo") .. '<strong id="gl-kpi-temp">–</strong><small>' .. h(translate("Temperature")) .. '</small></div>')
add('<div class="gl-kpi">' .. icon("net") .. '<strong id="gl-kpi-net">–</strong><small>' .. h(translate("Network")) .. '</small></div>')
add('</div>')
add('<div class="gl-mini-note"><span id="glanim-touch-live">Touch: -</span></div>')
add(switch_row("gl-auto-rotate", translate("Auto page rotation"), translate("Automatically rotate multi-page panels; touch still switches manually."), cur_auto_rotate))
add('<div class="gl-range"><div class="gl-range-head"><label for="gl-dash-interval">' .. h(translate("Page rotation interval")) .. '</label><output id="gl-dash-interval-val">' .. cur_interval .. 's</output></div>'
	.. '<input type="range" id="gl-dash-interval" min="2" max="30" step="1" value="' .. cur_interval .. '"></div>')
add('<div class="gl-mini-note">' .. icon("sliders") .. '<span>' .. h(translate("Tip: the panel preview follows the selected mode; the status row below updates every two seconds.")) .. '</span></div>')
add('</section>')
add('</div>')

-- ---------------- mode cards ----------------
add('<section class="gl-card gl-modes-card">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Play mode")) .. '</h2><p>' .. h(translate("Choose what the panel should do when the plugin is enabled.")) .. '</p></div></div>')
add(mode_grid())
add('</section>')

-- ---------------- dashboard settings ----------------
add('<section class="gl-card gl-panel" id="glanim-panel-dashboard">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("System panel settings")) .. '</h2><p>' .. h(translate("Pick the pages and items shown on the live panel.")) .. '</p></div>'
	.. '<span class="gl-badge" id="glanim-dash-badge">' .. h(translate("dashboard")) .. '</span></div>')
add('<div class="gl-toggle-grid">')
add(check_tile("gl-show-time", translate("Show clock"), translate("Clock HH:MM with date, weekday and seconds."), cur_show_time))
add(check_tile("gl-show-cpu", translate("Show CPU usage"), translate("CPU load bar and percentage."), cur_show_cpu))
add(check_tile("gl-show-mem", translate("Show memory usage"), translate("Memory load bar and percentage."), cur_show_mem))
add(check_tile("gl-show-temp", translate("Show temperature"), translate("Highest SoC zone temperature bar."), cur_show_temp))
add(check_tile("gl-show-net", translate("Show network speed"), translate("WAN down/up rate in KB/s or MB/s."), cur_show_net))
add(check_tile("gl-show-uptime", translate("Show uptime"), translate("Router uptime on the clock page."), cur_show_uptime))
add(check_tile("gl-show-ip", translate("Show LAN IP"), translate("br-lan IPv4 address on the panel."), cur_show_ip))
add('</div>')
add('<div class="gl-subcard"><div class="gl-subhead">' .. icon("screen") .. '<h3>' .. h(translate("Touch control")) .. '</h3></div>')
add(switch_row("gl-touch-enable", translate("Enable touch control"), translate("Read the CST816X touch panel (/dev/input/event0)."), cur_touch))
add('<div class="gl-select-row"><label for="gl-touch-action">' .. h(translate("Touch action")) .. '</label><select id="gl-touch-action">' .. touch_options() .. '</select></div>')
add('<div class="gl-two-col">'
	.. switch_row("gl-touch-swap", translate("Swap touch X/Y"), translate("Use if the axis is wrong after calibration."), cur_touch_swap)
	.. switch_row("gl-touch-flip", translate("Flip touch X"), translate("Use if the touch position is mirrored left/right."), cur_touch_flip)
	.. '</div>')
add('<div class="gl-touch-live" id="glanim-touch-live">' .. h(translate("Touch: waiting for data")) .. '</div>')
add('</div></section>')

-- ---------------- custom panel designer ----------------
add('<section class="gl-card gl-panel" id="glanim-panel-custom">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Custom panel designer")) .. '</h2><p>'
	.. h(translate("Place labels, live values and progress bars on the 284 × 76 canvas. Drag elements to move them; the JSON layout is saved with the plugin."))
	.. '</p></div><span class="gl-badge" id="glanim-custom-badge">' .. h(translate("free layout")) .. '</span></div>')
add('<div class="gl-custom-toolbar">')
add('<label class="gl-custom-template"><span>' .. h(translate("Template")) .. '</span><select id="glanim-custom-template">'
	.. '<option value="custom">' .. h(translate("Custom layout")) .. '</option>'
	.. '<option value="status">' .. h(translate("Status rows")) .. '</option>'
	.. '<option value="clock">' .. h(translate("Clock + network")) .. '</option>'
	.. '<option value="fan">' .. h(translate("Fan + temperature")) .. '</option>'
	.. '<option value="minimal">' .. h(translate("Minimal")) .. '</option>'
	.. '<option value="blank">' .. h(translate("Empty canvas")) .. '</option>'
	.. '</select></label>')
add('<span class="gl-custom-add">'
	.. '<button type="button" class="gl-btn" id="glanim-custom-add-text">+ ' .. h(translate("Label")) .. '</button>'
	.. '<button type="button" class="gl-btn" id="glanim-custom-add-value">+ ' .. h(translate("Value")) .. '</button>'
	.. '<button type="button" class="gl-btn" id="glanim-custom-add-bar">+ ' .. h(translate("Bar")) .. '</button>'
	.. '<button type="button" class="gl-btn" id="glanim-custom-add-line">+ ' .. h(translate("Line")) .. '</button>'
	.. '</span>')
add('</div>')
add('<div class="gl-custom-bgrow"><label>' .. h(translate("Background")) .. '</label>'
	.. '<input type="color" id="glanim-custom-bg" value="' .. h(custom_layout.bg or "#0a0c12") .. '">'
	.. '<span class="gl-bg-swatches">'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#0a0c12" style="background:#0a0c12" aria-label="dark"></button>'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#000000" style="background:#000000" aria-label="black"></button>'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#0b1a2a" style="background:#0b1a2a" aria-label="navy"></button>'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#0d1f16" style="background:#0d1f16" aria-label="forest"></button>'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#201014" style="background:#201014" aria-label="wine"></button>'
	.. '<button type="button" class="gl-bg-swatch" data-bg="#e9eef7" style="background:#e9eef7" aria-label="light"></button>'
	.. '</span>'
	.. '</div>')

add('<div class="gl-custom-grid">')
add('<div class="gl-custom-left">')
add('<div class="gl-custom-canvas-wrap"><canvas id="glanim-custom-canvas" width="568" height="152"></canvas>'
	.. '<div class="gl-custom-grid-label">284 × 76 · ' .. h(translate("snap 1 px")) .. '</div></div>')
add('<div class="gl-custom-hint">' .. h(translate("Click an element to edit it; drag to move. The preview above uses the same renderer as the panel.")) .. '</div>')
add('<div class="gl-custom-hint">' .. h(translate("Panel uses a 5×7 blocky bitmap font; only uppercase English, digits and symbols are available.")) .. '</div>')
add('<div class="gl-custom-palette">')
add('<div class="gl-custom-subhead">' .. h(translate("Available data")) .. '<span>' .. h(translate("click to add")) .. '</span></div>')
add('<div class="gl-data-palette" id="glanim-data-palette"></div>')
add('</div>')
add('</div>')
add('<div class="gl-custom-right">')
add('<div class="gl-custom-subhead">' .. h(translate("Element")) .. '<span id="glanim-custom-selected-label">' .. h(translate("none selected")) .. '</span></div>')
add('<div class="gl-custom-inspector" id="glanim-custom-inspector"></div>')
add('</div></div></section>')

-- ---------------- playback settings ----------------
add('<section class="gl-card gl-panel" id="glanim-panel-playback">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Playback")) .. '</h2></div>'
	.. '<span class="gl-badge ' .. pack_state_cls .. '" id="glanim-pack-badge">' .. h(pack_state) .. '</span></div>')
add('<div class="gl-two-col">')
add(switch_row("gl-loop", translate("Loop animation"), translate("Off: stop after the last frame."), cur_loop))
add('<div class="gl-range"><div class="gl-range-head"><label for="gl-fps">' .. h(translate("Force FPS")) .. '</label>'
	.. '<span class="gl-fps-num"><input type="number" id="gl-fps-number" min="0" max="50" step="1" value="' .. cur_fps .. '"><em>fps</em></span></div>'
	.. '<input type="range" id="gl-fps" min="0" max="50" step="1" value="' .. cur_fps .. '">'
	.. '<div class="gl-range-hint"><span>0 = ' .. h(translate("native")) .. '</span><span>50 fps</span></div></div>')
add('</div>')
add('<div class="gl-pack">')
add('<div class="gl-pack-main"><div class="gl-pack-icon">' .. icon("gif") .. '</div><div><strong id="glanim-pack-source">' .. h(pack_source ~= "" and pack_source or translate("No frame pack")) .. '</strong>'
	.. '<small id="glanim-pack-detail">' .. h((pack_count > 0 and (string.format(translate("%s frames"), tostring(pack_count))) or translate("Upload a frame pack to start."))) .. (pack_missing > 0 and (" · " .. h(string.format(translate("%s missing"), tostring(pack_missing)))) or "") .. '</small></div></div>')
add('<div class="gl-pack-actions">'
	.. '<button type="button" class="gl-btn" id="glanim-pack-upload">' .. icon("upload") .. h(translate("Upload pack")) .. '</button>'
	.. '<a class="gl-btn" id="glanim-pack-download" href="#">' .. icon("download") .. h(translate("Download")) .. '</a>'
	.. '<button type="button" class="gl-btn ghost is-danger" id="glanim-pack-clear">' .. h(translate("Remove")) .. '</button>'
	.. '<input type="file" id="glanim-pack-file" accept=".tar.gz,.tgz,application/gzip" hidden>'
	.. '</div>')
add('</div>')
add('<div class="gl-play-history" id="glanim-bg-history" hidden><div class="gl-play-history-head"><strong>' .. h(translate("Playback mode 1 · recent uploads")) .. '</strong><span>' .. h(translate("Last 3 saved backgrounds / GIFs, download or restore.")) .. '</span></div><div class="gl-bg-history-slots" id="glanim-bg-history-slots"></div></div>')
add('<div class="gl-hint-line">' .. h(translate("Frame packs are produced by glanim-convert.py and must contain manifest.json plus 76×284 RGB565 frames.")) .. '</div>')
add('</section>')

-- ---------------- image studio ----------------
add('<section class="gl-card gl-panel gl-studio" id="glanim-panel-studio">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Image studio")) .. '</h2><p>' .. h(translate("Drop an image, crop it in the preview, then apply it to the panel. GIF frames are decoded in your browser.")) .. '</p></div>'
	.. '<span class="gl-badge" id="glanim-studio-badge">' .. h(translate("browser-side")) .. '</span></div>')
add('<div class="gl-studio-grid">')
add('<div class="gl-studio-left">')
add('<div class="gl-drop" id="glanim-drop">'
	.. '<input type="file" id="glanim-file" accept="image/jpeg,image/png,image/gif,image/bmp,video/mp4,video/webm" hidden>'
	.. '<div class="gl-drop-icon">' .. icon("image") .. '</div>'
	.. '<strong>' .. h(translate("Drop an image here")) .. '</strong>'
	.. '<small>' .. h(translate("or click to choose · JPG / PNG / GIF / BMP / MP4 / WebM · GIF/video up to 600 frames (resolution-aware)")) .. '</small>'
	.. '<span class="gl-drop-name" id="glanim-file-name"></span></div>')
add('<div class="gl-url-row"><input type="url" id="glanim-url" placeholder="https://example.com/image.gif · https://example.com/page">'
	.. '<label class="gl-url-shot"><input type="checkbox" id="glanim-url-shot" checked> ' .. h(translate("web screenshot")) .. '</label>'
	.. '<button type="button" class="gl-btn" id="glanim-url-load">' .. h(translate("Load URL")) .. '</button></div>')
add('<div class="gl-url-hint">' .. h(translate("Paste a direct image/GIF URL, or paste a webpage URL with web screenshot enabled (uses WordPress mShots).")) .. '</div>')
add('<div class="gl-stage-wrap"><canvas id="glanim-stage" width="560" height="168"></canvas>'
	.. '<div class="gl-stage-empty" id="glanim-stage-empty">' .. h(translate("No image selected")) .. '</div></div>')
add('</div>')
add('<div class="gl-studio-right">')
add('<div class="gl-mini-screen"><canvas id="glanim-preview" width="284" height="76"></canvas><span>' .. h(translate("Panel preview")) .. '</span></div>')
add('<div class="gl-fit-group" role="group" aria-label="' .. h(translate("Fit mode")) .. '">'
	.. '<button type="button" class="gl-fit is-active" data-fit="cover">' .. h(translate("Cover")) .. '</button>'
	.. '<button type="button" class="gl-fit" data-fit="contain">' .. h(translate("Contain")) .. '</button>'
	.. '<button type="button" class="gl-fit" data-fit="stretch">' .. h(translate("Stretch")) .. '</button></div>')
add('<div class="gl-range compact"><div class="gl-range-head"><label for="glanim-zoom">' .. h(translate("Zoom")) .. '</label><output id="glanim-zoom-val">1.00×</output></div>'
	.. '<input type="range" id="glanim-zoom" min="1" max="3" step="0.05" value="1"></div>')
add('<div class="gl-range compact"><div class="gl-range-head"><label for="glanim-pos-x">' .. h(translate("Position X")) .. '</label><output id="glanim-pos-x-val">0</output></div>'
	.. '<input type="range" id="glanim-pos-x" min="-280" max="280" step="1" value="0"></div>')
add('<div class="gl-range compact"><div class="gl-range-head"><label for="glanim-pos-y">' .. h(translate("Position Y")) .. '</label><output id="glanim-pos-y-val">0</output></div>'
	.. '<input type="range" id="glanim-pos-y" min="-84" max="84" step="1" value="0"></div>')
add('<div class="gl-studio-meta"><span id="glanim-frame-info">' .. h(translate("No frames")) .. '</span>'
	.. '<span class="gl-studio-links"><button type="button" class="gl-link" id="glanim-play">' .. h(translate("Pause")) .. '</button>'
	.. '<button type="button" class="gl-link" id="glanim-reset">' .. h(translate("Reset crop")) .. '</button></span></div>')
add('<div class="gl-bg-trim" id="glanim-bg-trim">'
	.. '<div class="gl-bg-trim-row">'
	.. '<label>' .. h(translate("Background start")) .. '<input type="number" id="glanim-bg-start" min="1" max="300" step="1" value="1"></label>'
	.. '<label>' .. h(translate("Background frames")) .. '<input type="number" id="glanim-bg-count" min="1" max="300" step="1" value="300"></label>'
	.. '</div>'
	.. '<div class="gl-bg-trim-hint" id="glanim-bg-trim-info">' .. h(translate("300 frames ≈ 00:30 of the source")) .. '</div>'
	.. '</div>')
add('<div class="gl-range compact" id="glanim-scrub-wrap" hidden><div class="gl-range-head"><label for="glanim-scrub">' .. h(translate("Frame")) .. '</label><output id="glanim-scrub-val">1/1</output></div>'
	.. '<input type="range" id="glanim-scrub" min="1" max="1" step="1" value="1"></div>')
add('<button type="button" class="gl-btn primary block" id="glanim-apply">' .. icon("upload") .. h(translate("Apply to screen")) .. '</button>')
add('<button type="button" class="gl-btn block" id="glanim-apply-bg">' .. icon("image") .. h(translate("Set as custom background")) .. '</button>')
add('<div class="gl-msg" id="glanim-msg" role="status"></div>')
add('</div></div></section>')

-- ---------------- advanced ----------------
add('<section class="gl-card gl-advanced"><details>')
add('<summary>' .. icon("sliders") .. '<span>' .. h(translate("Advanced & maintenance")) .. '</span></summary>')
add('<div class="gl-adv-grid">')
add('<div class="gl-field"><label for="glanim-frames-dir">' .. h(translate("Frame directory")) .. '</label>'
	.. '<input type="text" id="glanim-frames-dir" value="' .. h(dir) .. '" spellcheck="false">'
	.. '<small>' .. h(translate("Directory holding manifest.json and .rgb565 frames.")) .. '</small></div>')
add(switch_row("gl-keep-original", translate("Restore OEM screen on exit"), translate("Stop gl_screen while playing; restore it when the daemon stops or this plugin is disabled."), cur_keep))
add('<div class="gl-note">' .. icon("screen") .. '<div><strong>' .. h(translate("Orientation")) .. '</strong><p>'
	.. h(translate("Panel rotation and mirroring are baked into the frame pack by the PC tool (--orientation). If the picture is sideways or mirrored, regenerate the pack with the matching option.")) .. '</p></div></div>')
add('<div class="gl-adv-actions">'
	.. '<a class="gl-btn ghost" href="' .. page_url("status") .. '" target="_blank" rel="noopener">' .. h(translate("JSON status")) .. '</a>'
	.. '<button type="button" class="gl-btn" id="glanim-restart">' .. icon("refresh") .. h(translate("Restart service")) .. '</button>'
	.. '<button type="button" class="gl-btn ghost is-danger" id="glanim-restore">' .. icon("undo") .. h(translate("Restore OEM screen")) .. '</button>'
	.. '</div>')
add('</div>')
-- ---------------- long-press menu ----------------
add('<div class="gl-subcard" id="glanim-panel-menu">')
add('<div class="gl-card-head"><div><h2>' .. h(translate("Long-press menu")) .. '</h2><p>'
	.. h(translate("Left preview, right current-page buttons. Drag or use arrows to reorder.")) .. '</p></div>'
	.. '<span class="gl-badge" id="glanim-menu-pages-badge">' .. h(string.format(translate("%s pages"), tostring(menu_pages))) .. '</span></div>')
add('<div class="gl-menu-editor">')
add('<div class="gl-menu-left">')
add('<div class="gl-menu-preview">')
add('<div class="gl-menu-preview-head"><span>' .. h(translate("Menu preview")) .. '</span>'
	.. '<span class="gl-menu-preview-tabs">'
	.. '<button type="button" data-menu-page="1" class="is-active">1</button>'
	.. '<button type="button" data-menu-page="2">2</button>'
	.. '<button type="button" data-menu-page="3" class="gl-menu-page3">3</button>'
	.. '</span></div>')
add('<div id="glanim-menu-preview" class="gl-menu-screen">')
add('<div class="gl-menu-screen-head"><span id="gl-menu-screen-title">' .. h(translate("Menu")) .. '</span>'
	.. '<span id="gl-menu-screen-page">1/2</span>'
	.. '<span id="gl-menu-screen-exit">' .. h(translate("Exit menu")) .. '</span></div>')
add('<div class="gl-menu-screen-body" id="gl-menu-screen-buttons"></div>')
add('</div>')
add('</div>')
add('<div class="gl-menu-grid">')
add('<div class="gl-field"><label for="gl-menu-lang">' .. h(translate("Menu language")) .. '</label><select id="gl-menu-lang">'
	.. '<option value="auto"' .. (menu_lang ~= "zh" and menu_lang ~= "en" and " selected" or "") .. '>' .. h(translate("Follow LuCI language")) .. '</option>'
	.. '<option value="zh"' .. (menu_lang == "zh" and " selected" or "") .. '>' .. h(translate("Chinese")) .. '</option>'
	.. '<option value="en"' .. (menu_lang == "en" and " selected" or "") .. '>' .. h(translate("English")) .. '</option></select></div>')
add('<div class="gl-field"><label for="gl-menu-pages">' .. h(translate("Menu pages")) .. '</label><select id="gl-menu-pages">'
	.. '<option value="2"' .. (menu_pages == 2 and " selected" or "") .. '>2</option>'
	.. '<option value="3"' .. (menu_pages == 3 and " selected" or "") .. '>3</option></select></div>')
add('</div>')
add('</div>')
add('<div class="gl-menu-side">')
add('<div class="gl-menu-preview-head"><span id="gl-menu-side-title">' .. h(translate("Page 1 buttons")) .. '</span>'
	.. '<span class="gl-menu-preview-tabs">'
	.. '<button type="button" data-menu-page="1" class="is-active">1</button>'
	.. '<button type="button" data-menu-page="2">2</button>'
	.. '<button type="button" data-menu-page="3" class="gl-menu-page3">3</button>'
	.. '</span></div>')
add('<div class="gl-menu-queue-items" id="gl-menu-queue-active"></div>')
add('<div class="gl-menu-queue-tip">' .. h(translate("Drag or use arrows to reorder. Each page has 4 buttons.")) .. '</div>')
add('</div>')
add('</div>')

add('</details></section>')

-- ---------------- save bar + toast ----------------
add('<div class="gl-savebar" id="glanim-savebar">')
add('<div class="gl-save-state"><span class="gl-save-dot" id="glanim-save-dot"></span><span id="glanim-save-text">' .. h(translate("All changes saved")) .. '</span></div>')
add('<div class="gl-save-actions">'
	.. '<button type="button" class="gl-btn ghost" id="glanim-revert">' .. h(translate("Revert")) .. '</button>'
	.. '<button type="button" class="gl-btn primary" id="glanim-save">' .. icon("save") .. h(translate("Save & Apply")) .. '</button>'
	.. '</div></div>')
add('<div class="gl-toast" id="glanim-toast" role="status" aria-live="polite"></div>')
add('<footer class="gl-author">' .. h(translate("Author")) .. ' <strong>@xavierbe278</strong><span>·</span><a href="https://github.com/xavierbe278/gl-be3600-toolbox" target="_blank" rel="noopener">' .. h(translate("GitHub project")) .. '</a><span>·</span>v' .. VERSION .. '</footer>')
add('</div>')

-- ---------------- config bootstrap ----------------
local cfg_json = {
	version = VERSION,
	zh = is_zh,
	current = {
		enabled = cur_enabled,
		mode = cur_mode,
		fps = cur_fps,
		loop = cur_loop,
		brightness = cur_bright,
		keepOriginal = cur_keep,
		framesDir = dir,
		interval = cur_interval,
		autoRotate = cur_auto_rotate,
		showTime = cur_show_time,
		showCpu = cur_show_cpu,
		showMem = cur_show_mem,
		showTemp = cur_show_temp,
		showNet = cur_show_net,
		showUptime = cur_show_uptime,
		showIp = cur_show_ip,
		touchEnable = cur_touch,
		touchAction = cur_touch_action,
		touchSwap = cur_touch_swap,
		touchFlip = cur_touch_flip,
	},
	pack = {
		count = pack_count,
		missing = pack_missing,
		valid = pack_valid,
		source = pack_source,
		delays = pack_delays,
	},
	menuLang = menu_lang,
	menuPages = menu_pages,
	menuPage1 = menu_page1,
	menuPage2 = menu_page2,
	menuPage3 = menu_page3,
	custom = custom_layout,
	customBg = {
		dir = custom_bg_dir,
		frames = custom_bg_frames,
		fps = custom_bg_fps,
		mask = bg_mask,
		blur = bg_blur,
		alpha = content_alpha,
	},
	openclash = {
		installed = oc_installed and true or false,
		enabled = oc_enabled and true or false,
		running = oc_running and true or false,
		mode = oc_mode,
	},
	status = {
		daemon = daemon_on and "1" or "0",
		mode = (status and status.mode) or "",
		error = live_error,
		brightness = bright,
	},
	urls = {
		status = page_url("status"),
		save = page_url("save"),
		frame = page_url("frame"),
		apply = page_url("apply"),
		restore = page_url("restore_oem"),
		uploadImage = page_url("upload_image"),
		uploadPack = page_url("upload"),
		clear = page_url("clear"),
		clearBg = page_url("clear_bg"),
		bgFrame = page_url("bg_frame"),
		bgHistory = page_url("bg_history"),
		bgRestore = page_url("bg_restore"),
		bgDelete = page_url("bg_delete"),
		download = page_url("download"),
		mask = page_url("mask"),
		blur = page_url("blur"),
		contentAlpha = page_url("content_alpha"),
		page = page_url("page"),
		brightness = page_url("brightness"),
		openclash = page_url("openclash"),
		fetchUrl = page_url("fetch_url"),
	},
}
local cfg_text = json.stringify(cfg_json)
cfg_text = cfg_text:gsub("<", "\\u003c"):gsub(">", "\\u003e"):gsub("&", "\\u0026")

add('<script>window.GLANIM_CFG=' .. cfg_text .. ';</script>')
add('<script src="/luci-static/resources/glanim/glanim.js?v=' .. ASSET_VERSION .. '"></script>')

local f = Map("glanim", "", "")
f.reset = false
-- This page owns its Save & Apply action. Hiding the framework buttons keeps
-- the plugin out of LuCI's global dirty-state / global save path entirely.
f.hideapplybtn = true
f.hidesavebtn = true
f.hideresetbtn = true
f.pageaction = false
f.flow.hideapplybtn = true
f.flow.hidesavebtn = true
f.flow.hideresetbtn = true
f.submit = false
f.reset = false

local sec = f:section(SimpleSection, nil, "")
sec.description = table.concat(page_html)

return f
