module("luci.controller.glanim", package.seeall)

local nixio = require "nixio"
local fs = require "nixio.fs"

local FRAMES_DEFAULT = "/usr/share/glanim/frames"
local CUSTOM_BG_DIR = "/usr/share/glanim/custom_bg"
local BG_HISTORY_DIR = "/usr/share/glanim/bg_history"
local MAX_BG_FRAMES = 300
local TMP_PACK = "/tmp/glanim-pack.tar.gz"
local TMP_IMAGE_DIR = "/tmp/glanim-frame-upload"
local FRAME_BYTES = 76 * 284 * 2
local MAX_PACK_BYTES = 32 * 1024 * 1024
local MAX_FRAMES = 600
local MAX_FRAME_MS = 1000
local MIN_FRAME_MS = 30

local MODES = { gif = true, still = true, slideshow = true, dashboard = true, custom = true, clash = true }
local TOUCH_ACTIONS = { next = true, wake = true, none = true }

local function uci_cursor()
	return require("luci.model.uci").cursor()
end

local function cfg_str(key, default)
	local uci = uci_cursor()
	local v = uci:get("glanim", "globals", key)
	if type(v) == "table" then v = v[1] end
	if v == nil or v == "" then return default end
	return tostring(v)
end

local function safe_dir(path)
	if type(path) ~= "string" then return nil end
	if #path < 2 or #path > 180 then return nil end
	if not path:match("^/[%w%._/%-]+$") then return nil end
	if path:find("%.%.") then return nil end
	-- keep the trailing slash out so shell paths and manifest joins stay simple
	path = path:gsub("/+$", "")
	if path == "" then return nil end
	return path
end

local function frames_dir()
	return safe_dir(cfg_str("frames_dir", FRAMES_DEFAULT)) or FRAMES_DEFAULT
end

local function safe_name(name)
	return type(name) == "string" and #name > 0 and #name <= 128
		and name:match("^[%w%._%-]+$") ~= nil and not name:find("%.%.")
end

local function json_lib()
	return require("luci.jsonc")
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

local function read_raw(path)
	local f = io.open(path, "r")
	if f then
		local v = f:read("*l")
		f:close()
		return v
	end
	return nil
end

local function read_manifest(dir)
	local f = io.open(dir .. "/manifest.json", "r")
	if not f then return nil end
	local text = f:read("*a")
	f:close()
	if not text or text == "" then return nil end
	local ok, m = pcall(json_lib().parse, text)
	if not ok or type(m) ~= "table" then return nil end
	return m
end

-- Normalize a manifest in place and optionally verify that every referenced
-- frame exists with the exact 76x284 RGB565 size. Returns true, manifest or
-- false, message-key.
local function validate_manifest(m, dir, require_files)
	if type(m) ~= "table" then return false, "manifest" end
	if type(m.frames) ~= "table" or #m.frames < 1 then return false, "manifest" end
	if #m.frames > MAX_FRAMES then return false, "toomany" end

	local seen = {}
	for i = 1, #m.frames do
		local fr = m.frames[i]
		if type(fr) ~= "table" or not safe_name(fr.file) then
			return false, "badname"
		end
		if seen[fr.file] then return false, "badname" end
		seen[fr.file] = true

		local delay = tonumber(fr.delay_ms) or 100
		delay = math.floor(delay)
		if delay < MIN_FRAME_MS then delay = MIN_FRAME_MS end
		if delay > MAX_FRAME_MS then delay = MAX_FRAME_MS end
		fr.delay_ms = delay

		if require_files then
			local st = fs.stat(dir .. "/" .. fr.file)
			if not st or st.size ~= FRAME_BYTES then
				return false, "badframe"
			end
		end
	end

	m.width = 76
	m.height = 284
	m.format = "rgb565le"
	return true, m
end

local function write_manifest(dir, m)
	local f = io.open(dir .. "/manifest.json", "w")
	if not f then return false end
	f:write(json_lib().stringify(m))
	f:close()
	return true
end

-- Replace dir with staging atomically enough for a read-mostly frame pack:
-- old dir -> backup, staging -> dir, then drop the backup. On the second
-- rename failing the old pack is restored.
local function swap_dir(staging, dir)
	local old = dir .. ".old-" .. tostring(os.time())
	luci.sys.call("rm -rf " .. old)
	if fs.access(dir) then
		local ok, err = os.rename(dir, old)
		if not ok then return false, err end
	end
	local ok, err = os.rename(staging, dir)
	if not ok then
		if fs.access(old) then os.rename(old, dir) end
		return false, err
	end
	luci.sys.call("rm -rf " .. old)
	return true
end

local function is_xhr()
	local h = luci.http.getenv("HTTP_X_REQUESTED_WITH") or ""
	local accept = luci.http.getenv("HTTP_ACCEPT") or ""
	return h == "XMLHttpRequest" or accept:find("application/json", 1, true) ~= nil
end

local function json_reply(data, code)
	if code then luci.http.status(code, code == 400 and "Bad Request" or "Error") end
	luci.http.prepare_content("application/json")
	luci.http.write(json_lib().stringify(data))
	return true
end

local function fail_reply(key, code)
	return json_reply({ ok = false, error = key }, code or 400)
end

local function redirect_msg(key)
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glanim",
		"main", { msg = key }))
end

local function numv(name, default, lo, hi)
	local v = tonumber(luci.http.formvalue(name))
	if not v then v = default end
	v = math.floor(v)
	if v < lo then v = lo end
	if v > hi then v = hi end
	return v
end

local function boolv(name, default)
	local v = luci.http.formvalue(name)
	if v == nil then return default and "1" or "0" end
	if v == "1" or v == "true" or v == "on" then return "1" end
	return "0"
end

function index()
	if not fs.access("/etc/config/glanim") then
		return
	end

	local page

	page = entry({"admin", "services", "glanim"}, alias("admin", "services", "glanim", "main"), _("Screen Custom"), 56)
	page.dependent = true
	page.acl_depends = { "luci-app-glanim" }

	entry({"admin", "services", "glanim", "main"},
		cbi("glanim/main"), _("Screen Custom"), 10).leaf = true
	entry({"admin", "services", "glanim", "status"}, call("action_status")).leaf = true
	entry({"admin", "services", "glanim", "apply"}, call("action_apply")).leaf = true
	entry({"admin", "services", "glanim", "save"}, call("action_save")).leaf = true
	entry({"admin", "services", "glanim", "frame"}, call("action_frame")).leaf = true
	entry({"admin", "services", "glanim", "bg_frame"}, call("action_bg_frame")).leaf = true
	entry({"admin", "services", "glanim", "mask"}, call("action_mask")).leaf = true
	entry({"admin", "services", "glanim", "brightness"}, call("action_brightness")).leaf = true
	entry({"admin", "services", "glanim", "blur"}, call("action_blur")).leaf = true
	entry({"admin", "services", "glanim", "content_alpha"}, call("action_content_alpha")).leaf = true
	entry({"admin", "services", "glanim", "page"}, call("action_page")).leaf = true
	entry({"admin", "services", "glanim", "bg_history"}, call("action_bg_history")).leaf = true
	entry({"admin", "services", "glanim", "bg_restore"}, call("action_bg_restore")).leaf = true
	entry({"admin", "services", "glanim", "download"}, call("action_download")).leaf = true
	entry({"admin", "services", "glanim", "openclash"}, call("action_openclash")).leaf = true
	entry({"admin", "services", "glanim", "fetch_url"}, call("action_fetch_url")).leaf = true
	entry({"admin", "services", "glanim", "upload"}, call("action_upload")).leaf = true
	entry({"admin", "services", "glanim", "upload_image"}, call("action_upload_image")).leaf = true
	entry({"admin", "services", "glanim", "clear"}, call("action_clear")).leaf = true
	entry({"admin", "services", "glanim", "clear_bg"}, call("action_clear_bg")).leaf = true
	entry({"admin", "services", "glanim", "restore_oem"}, call("action_restore_oem")).leaf = true
	entry({"admin", "services", "glanim", "set_lang"}, call("action_set_lang")).leaf = true
end

function action_openclash()
	local sys = require "luci.sys"
	local fs = require "nixio.fs"
	if not fs.access("/etc/init.d/openclash") then
		return json_reply({ ok = false, error = "not_installed" }, 400)
	end
	local enable = luci.http.formvalue("enable") == "1"
	local uci = uci_cursor()
	uci:set("openclash", "config", "enable", enable and "1" or "0")
	uci:commit("openclash")
	local act = enable and "start" or "stop"
	sys.call("(/etc/init.d/openclash " .. act .. " >/tmp/glanim-openclash.log 2>&1 &)")
	if is_xhr() then
		return json_reply({ ok = true, enable = enable and "1" or "0" })
	end
	redirect_msg(enable and "openclash_enabled" or "openclash_disabled")
end

function action_set_lang()
	local lang = luci.http.formvalue("lang") or ""
	local uci_lang = ({ ["zh-cn"] = "zh_cn", ["zh_cn"] = "zh_cn", ["en"] = "en" })[lang]
	if uci_lang then
		luci.sys.exec("uci set luci.main.lang='%s' && uci commit luci" % uci_lang)
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glanim", "main"))
end

function action_status()
	local status = read_status_file() or {}
	local json = json_lib()
	local pid_daemon = luci.sys.exec("pgrep -f /usr/bin/glanimd")
	local pid_screen = luci.sys.exec("pidof gl_screen")
	local daemon_on = (pid_daemon and pid_daemon:gsub("%s", "") ~= "") and "1" or "0"
	local live = daemon_on == "1"
	local function st(key)
		return live and (status[key] or "") or ""
	end
	luci.http.prepare_content("application/json")
	luci.http.header("Cache-Control", "no-store")
	luci.http.write(json.stringify({
		daemon        = daemon_on,
		enabled       = cfg_str("enabled", "0"),
		mode          = live and (status.mode or "-") or "-",
		frame_count   = live and (tonumber(status.frame_count) or 0) or 0,
		current       = live and (tonumber(status.current) or 0) or 0,
		source        = live and (status.source or "") or "",
		dir           = live and (status.dir or "") or "",
		error         = live and (status.error or "") or "",
		brightness    = read_raw("/sys/class/backlight/soc:backlight/brightness") or "0",
		daemon_pid    = pid_daemon and pid_daemon:gsub("%s", "") or "",
		screen_pid    = pid_screen and pid_screen:gsub("%s", "") or "",
		-- dashboard panel live samples
		page          = st("page"),
		page_count    = st("page_count"),
		cpu           = st("cpu"),
		mem           = st("mem"),
		temp          = st("temp"),
		rx_kbps       = st("rx_kbps"),
		tx_kbps       = st("tx_kbps"),
		net_iface     = st("net_iface"),
		ip            = st("ip"),
		lan_ip        = st("lan_ip"),
		wan_ip        = st("wan_ip"),
		hostname      = st("hostname"),
		rx_total      = st("rx_total"),
		tx_total      = st("tx_total"),
		conn_count    = st("conn_count"),
		oc_running    = st("oc_running"),
		oc_mode       = st("oc_mode"),
		oc_mem        = st("oc_mem"),
		oc_uptime     = st("oc_uptime"),
		oc_group      = st("oc_group"),
		oc_group_count = st("oc_group_count"),
		oc_node       = st("oc_node"),
		oc_country    = st("oc_country"),
		oc_node_type  = st("oc_node_type"),
		oc_udp        = st("oc_udp"),
		oc_rate       = st("oc_rate"),
		oc_delay      = st("oc_delay"),
		fan_rpm       = st("fan_rpm"),
		fan_pwm       = st("fan_pwm"),
		clock         = st("clock"),
		date          = st("date"),
		weekday       = st("weekday"),
		uptime        = st("uptime"),
		-- touch
		touch_present = st("touch_present"),
		touch_action  = st("touch_action"),
		touch_x       = st("touch_x"),
		touch_y       = st("touch_y"),
		touch_gesture = st("touch_gesture"),
		touch_raw     = st("touch_raw"),
		touch_range   = st("touch_range")
	}))
end

function action_frame()
	local dir = frames_dir()
	local m = read_manifest(dir)
	local idx = tonumber(luci.http.formvalue("i")) or 0
	if not m or type(m.frames) ~= "table" or not m.frames[idx + 1] then
		luci.http.status(404, "Not Found")
		return
	end
	local name = m.frames[idx + 1].file
	if not safe_name(name) then
		luci.http.status(404, "Not Found")
		return
	end
	local f = io.open(dir .. "/" .. name, "rb")
	if not f then
		luci.http.status(404, "Not Found")
		return
	end
	local data = f:read("*a")
	f:close()
	if not data or #data ~= FRAME_BYTES then
		luci.http.status(404, "Not Found")
		return
	end
	luci.http.prepare_content("application/octet-stream")
	luci.http.header("Cache-Control", "no-store")
	luci.http.write(data)
end

function action_page()
	local page = luci.http.formvalue("page") or ""
	local allowed = {
		clock = true, status = true, clash = true,
		clash_info = true, clash_node = true,
	}
	if not allowed[page] then
		return json_reply({ ok = false, error = "bad_page" }, 400)
	end
	local f = io.open("/tmp/glanim.page", "w")
	if f then f:write(page); f:close() end
	local af = io.open("/tmp/glanim.auto", "w")
	if af then af:write("0"); af:close() end
	local uci = require("luci.model.uci").cursor()
	uci:set("glanim", "globals", "auto_rotate", "0")
	uci:commit("glanim")
	return json_reply({ ok = true, page = page, auto_rotate = "0" })
end


function action_blur()
	local value = tonumber(luci.http.formvalue("value") or "0") or 0
	if value < 0 then value = 0 end
	if value > 100 then value = 100 end
	local uci = require("luci.model.uci").cursor()
	uci:set("glanim", "globals", "bg_blur", tostring(value))
	uci:commit("glanim")
	local f = io.open("/tmp/glanim.blur", "w")
	if f then f:write(tostring(value)); f:close() end
	return json_reply({ ok = true, value = value })
end


function action_content_alpha()
	local value = tonumber(luci.http.formvalue("value") or "100") or 100
	value = math.max(0, math.min(100, value))
	local uci = require("luci.model.uci").cursor()
	uci:set("glanim", "globals", "content_alpha", tostring(value))
	uci:commit("glanim")
	local f = io.open("/tmp/glanim.content_alpha", "w")
	if f then f:write(tostring(value)); f:close() end
	return json_reply({ ok = true, value = value })
end


function action_brightness()
	local value = tonumber(luci.http.formvalue("value") or "4") or 4
	if value < 0 then value = 0 end
	if value > 11 then value = 11 end
	local uci = require("luci.model.uci").cursor()
	uci:set("glanim", "globals", "brightness", tostring(value))
	uci:commit("glanim")
	local f = io.open("/tmp/glanim.brightness", "w")
	if f then f:write(tostring(value)); f:close() end
	return json_reply({ ok = true, value = value })
end


function action_mask()
	local mask = tonumber(luci.http.formvalue("mask") or "45") or 45
	if mask < 0 then mask = 0 end
	if mask > 100 then mask = 100 end
	local uci = require("luci.model.uci").cursor()
	uci:set("glanim", "globals", "bg_mask", tostring(mask))
	uci:commit("glanim")
	local f = io.open("/tmp/glanim.mask", "w")
	if f then f:write(tostring(mask)); f:close() end
	return json_reply({ ok = true, mask = mask })
end


function action_bg_frame()
	local dir = CUSTOM_BG_DIR
	local m = read_manifest(dir)
	local idx = tonumber(luci.http.formvalue("i")) or 0
	if not m or type(m.frames) ~= "table" or not m.frames[idx + 1] then
		luci.http.status(404, "Not Found")
		return
	end
	local name = m.frames[idx + 1].file
	if not safe_name(name) then
		luci.http.status(404, "Not Found")
		return
	end
	local f = io.open(dir .. "/" .. name, "rb")
	if not f then
		luci.http.status(404, "Not Found")
		return
	end
	local data = f:read("*a")
	f:close()
	if not data or #data ~= FRAME_BYTES then
		luci.http.status(404, "Not Found")
		return
	end
	luci.http.prepare_content("application/octet-stream")
	luci.http.header("Cache-Control", "no-store")
	luci.http.write(data)
end

function action_fetch_url()
	local url = luci.http.formvalue("url") or ""
	if not url:match("^https?://[%w%._%-/:?&=%+~#%%]+$") then
		luci.http.status(400, "Bad Request")
		return
	end
	local tmp = "/tmp/glanim-url.bin"
	fs.remove(tmp)
	local rc
	if luci.sys.call("command -v uclient-fetch >/dev/null 2>&1") == 0 then
		rc = luci.sys.call("uclient-fetch -q -T 20 -O " .. tmp .. " '" .. url .. "' 2>/dev/null")
	else
		rc = luci.sys.call("wget -q -T 20 -O " .. tmp .. " '" .. url .. "' 2>/dev/null")
	end
	if rc ~= 0 or not fs.access(tmp) then
		luci.http.status(502, "Bad Gateway")
		return
	end
	local st = fs.stat(tmp)
	if not st or not st.size or st.size < 1 or st.size > 8 * 1024 * 1024 then
		fs.remove(tmp)
		luci.http.status(413, "Payload Too Large")
		return
	end
	local f = io.open(tmp, "rb")
	if not f then
		fs.remove(tmp)
		luci.http.status(502, "Bad Gateway")
		return
	end
	local data = f:read("*a")
	f:close()
	fs.remove(tmp)
	luci.http.prepare_content("application/octet-stream")
	luci.http.header("Cache-Control", "no-store")
	luci.http.write(data)
end

function action_apply()
	local enabled = cfg_str("enabled", "0")
	if enabled ~= "1" then
		return fail_reply("not_enabled", 400)
	end
	luci.sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
	return json_reply({ ok = true })
end

-- Independent save endpoint for the screen page. The page intentionally does
-- not register any writeable CBI option, so LuCI's global change tracker and
-- the global Save & Apply button never touch this plugin's configuration.
local function hex_color(v, default)
	if type(v) ~= "string" or not v:match("^#%x%x%x%x%x%x$") then return default end
	v = v:lower()
	if v == "#78849a" then return "#c2ccdc" end
	return v
end

local function layout_int(v, default, lo, hi)
	local n = tonumber(v)
	if not n then n = default end
	n = math.floor(n)
	if n < lo then n = lo end
	if n > hi then n = hi end
	return n
end

local CUSTOM_SOURCES = {
	cpu = true, mem = true, temp = true, rx = true, tx = true, net = true,
	iface = true, ip = true, lan_ip = true, wan_ip = true, hostname = true,
	uptime = true, clock = true, hm = true, date = true, weekday = true,
	fan_rpm = true, fan_pwm = true,
	oc_status = true, oc_rx = true, oc_tx = true, oc_total = true,
	oc_conns = true, oc_mode = true, oc_mem = true, oc_uptime = true,
}

local function sanitize_layout(l)
	if type(l) ~= "table" or type(l.elements) ~= "table" then return nil end
	local out = {
		bg = hex_color(l.bg, "#0a0c12"),
		elements = {},
	}
	local allowed = { text = true, value = true, bar = true, rect = true, line = true }
	for i = 1, #l.elements do
		if #out.elements >= 40 then break end
		local el = l.elements[i]
		if type(el) == "table" and allowed[el.type] then
			local e = {
				type = el.type,
				x = layout_int(el.x, 0, 0, 283),
				y = layout_int(el.y, 0, 0, 75),
				size = layout_int(el.size, 1, 1, 3),
				color = hex_color(el.color, "#eef2fa"),
				align = (el.align == "center" or el.align == "right") and el.align or "left",
			}
			if el.type == "bar" and el.color == "auto" then e.color = "auto" end
			if el.type == "text" then
				e.text = tostring(el.text or ""):sub(1, 64)
			end
			if el.type == "value" or el.type == "bar" then
				e.source = CUSTOM_SOURCES[el.source] and el.source or "cpu"
				e.prefix = tostring(el.prefix or ""):sub(1, 16)
				e.suffix = tostring(el.suffix or ""):sub(1, 16)
			end
			if el.type == "bar" then
				e.w = layout_int(el.w, 120, 1, 284)
				e.h = layout_int(el.h, 8, 1, 76)
				e.show_value = el.show_value and true or false
			elseif el.type == "rect" then
				e.w = layout_int(el.w, 20, 1, 284)
				e.h = layout_int(el.h, 2, 1, 76)
			elseif el.type == "line" then
				e.w = layout_int(el.w, 100, 1, 284)
			end
			out.elements[#out.elements + 1] = e
		end
	end
	if #out.elements == 0 then return nil end
	return out
end

function action_save()
	local uci = uci_cursor()

	local mode = luci.http.formvalue("mode") or "gif"
	if not MODES[mode] then return fail_reply("bad_mode", 400) end

	local enabled = boolv("enabled", false)
	local loop = boolv("loop", true)
	local keep_original = boolv("keep_original", true)
	local show_time = boolv("show_time", true)
	local show_cpu = boolv("show_cpu", true)
	local show_mem = boolv("show_mem", true)
	local show_temp = boolv("show_temp", true)
	local show_net = boolv("show_net", true)
	local show_uptime = boolv("show_uptime", false)
	local show_ip = boolv("show_ip", false)
	local touch_enable = boolv("touch_enable", true)
	local touch_swap_xy = boolv("touch_swap_xy", false)
	local touch_flip_x = boolv("touch_flip_x", false)

	local touch_action = luci.http.formvalue("touch_action") or "next"
	if not TOUCH_ACTIONS[touch_action] then touch_action = "next" end

	local fps = numv("fps", 0, 0, 30)
	local brightness = numv("brightness", 4, 0, 11)
	local dash_interval = numv("dash_interval", 5, 2, 30)
	local auto_rotate = boolv("auto_rotate", true)
	local bg_mask = numv("bg_mask", 20, 0, 100)
	local bg_blur = numv("bg_blur", 0, 0, 100)
	local content_alpha = numv("content_alpha", 100, 0, 100)

	local dir = safe_dir(luci.http.formvalue("frames_dir") or "")
	if not dir then return fail_reply("bad_dir", 400) end

	local layout_text = luci.http.formvalue("custom_layout") or ""
	local custom_layout = nil
	if layout_text ~= "" then
		if #layout_text > 12000 then return fail_reply("bad_layout", 400) end
		local ok, parsed = pcall(json_lib().parse, layout_text)
		if not ok or type(parsed) ~= "table" then
			return fail_reply("bad_layout", 400)
		end
		custom_layout = sanitize_layout(parsed)
		if not custom_layout then return fail_reply("bad_layout", 400) end
	end

	if enabled == "1" then
		if mode == "dashboard" then
			if show_time ~= "1" and show_cpu ~= "1" and show_mem ~= "1"
				and show_temp ~= "1" and show_net ~= "1" then
				return fail_reply("no_dashboard_item", 400)
			end
		elseif mode == "custom" then
			if not custom_layout then return fail_reply("no_custom", 400) end
		elseif mode == "clash" then
			-- OpenClash page is generated from live status; no frame pack needed.
		else
			local m = read_manifest(dir)
			local ok = m and validate_manifest(m, dir, true)
			if not ok then return fail_reply("no_frames", 400) end
		end
	end

	uci:set("glanim", "globals", "enabled", enabled)
	uci:set("glanim", "globals", "mode", mode)
	uci:set("glanim", "globals", "fps", tostring(fps))
	uci:set("glanim", "globals", "loop", loop)
	uci:set("glanim", "globals", "brightness", tostring(brightness))
	local bf = io.open("/tmp/glanim.brightness", "w")
	if bf then bf:write(tostring(brightness)); bf:close() end
	uci:set("glanim", "globals", "keep_original", keep_original)
	uci:set("glanim", "globals", "frames_dir", dir)
	uci:set("glanim", "globals", "show_time", show_time)
	uci:set("glanim", "globals", "show_cpu", show_cpu)
	uci:set("glanim", "globals", "show_mem", show_mem)
	uci:set("glanim", "globals", "show_temp", show_temp)
	uci:set("glanim", "globals", "show_net", show_net)
	uci:set("glanim", "globals", "show_uptime", show_uptime)
	uci:set("glanim", "globals", "show_ip", show_ip)
	uci:set("glanim", "globals", "dash_interval", tostring(dash_interval))
	uci:set("glanim", "globals", "auto_rotate", auto_rotate)
	local af = io.open("/tmp/glanim.auto", "w")
	if af then af:write(auto_rotate); af:close() end
	if auto_rotate == "1" then
		os.remove("/tmp/glanim.page")
	end
	uci:set("glanim", "globals", "bg_mask", tostring(bg_mask))
	uci:set("glanim", "globals", "bg_blur", tostring(bg_blur))
	uci:set("glanim", "globals", "content_alpha", tostring(content_alpha))
	local mf = io.open("/tmp/glanim.mask", "w")
	if mf then mf:write(tostring(bg_mask)); mf:close() end
	local blf = io.open("/tmp/glanim.blur", "w")
	if blf then blf:write(tostring(bg_blur)); blf:close() end
	local alf = io.open("/tmp/glanim.content_alpha", "w")
	if alf then alf:write(tostring(content_alpha)); alf:close() end
	uci:set("glanim", "globals", "touch_enable", touch_enable)
	uci:set("glanim", "globals", "touch_action", touch_action)
	uci:set("glanim", "globals", "touch_swap_xy", touch_swap_xy)
	uci:set("glanim", "globals", "touch_flip_x", touch_flip_x)
	if custom_layout then
		uci:set("glanim", "globals", "custom_layout", json_lib().stringify(custom_layout))
	end
	uci:commit("glanim")

	if enabled == "1" then
		luci.sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
	else
		luci.sys.call("/etc/init.d/glanim stop >/dev/null 2>&1")
		luci.sys.call("rm -f /tmp/glanim.status")
		luci.sys.call("/etc/init.d/gl_screen enable >/dev/null 2>&1")
		luci.sys.call("/etc/init.d/gl_screen start >/dev/null 2>&1")
	end

	return json_reply({
		ok = true,
		enabled = enabled == "1",
		mode = mode,
		pack = { count = 0 },
	})
end

-- Validate a tar listing before extraction. Rejects absolute paths, parent
-- traversal, backslashes and unexpected entry types.
local function tar_listing_ok()
	local out = luci.sys.exec("tar -tzf " .. TMP_PACK .. " 2>/dev/null")
	if not out or out == "" then return false, "manifest" end
	local count = 0
	for name in out:gmatch("[^\r\n]+") do
		count = count + 1
		if count > 400 then return false, "toomany" end
		if name:sub(1, 1) == "/" or name:find("..", 1, true) or name:find("\\", 1, true) then
			return false, "unsafe"
		end
	end
	-- Reject symlinks / hardlinks / device entries; a frame pack is regular
	-- files and directories only.
	local verbose = luci.sys.exec("tar -tvzf " .. TMP_PACK .. " 2>/dev/null")
	for line in verbose:gmatch("[^\r\n]+") do
		local t = line:sub(1, 1)
		if t ~= "-" and t ~= "d" then
			return false, "unsafe"
		end
	end
	return count > 0, nil
end

function action_upload()
	local sys = require "luci.sys"
	local fs = require "nixio.fs"
	local uci = uci_cursor()
	local dir = frames_dir()
	local staging = dir .. ".new"
	local fd = nil
	local bytes = 0
	local too_big = false

	luci.http.setfilehandler(function(meta, chunk, eof)
		if not fd then
			if not meta or not meta.file then return end
			fd = nixio.open(TMP_PACK, "w")
			if not fd then return end
		end
		if chunk and fd then
			bytes = bytes + #chunk
			if bytes > MAX_PACK_BYTES then
				too_big = true
			else
				fd:write(chunk)
			end
		end
		if eof and fd then
			fd:close()
			fd = nil
		end
	end)

	-- consume multipart body so the file handler runs
	luci.http.formvalue("__trigger")

	local function finish(key, ok)
		fs.remove(TMP_PACK)
		sys.call("rm -rf " .. staging)
		if is_xhr() then
			if ok then
				return json_reply({ ok = true, msg = key })
			end
			return json_reply({ ok = false, msg = key }, 400)
		end
		redirect_msg(key)
	end

	if too_big then return finish("toobig", false) end
	if not fs.access(TMP_PACK) then return finish("nofile", false) end

	local listed, why = tar_listing_ok()
	if not listed then return finish(why or "manifest", false) end

	sys.call("rm -rf " .. staging)
	sys.call("mkdir -p " .. staging)
	local rc = sys.call("tar -xzf " .. TMP_PACK .. " -C " .. staging .. " 2>/dev/null")
	if rc ~= 0 then return finish("manifest", false) end

	local m = read_manifest(staging)
	local ok, msg = validate_manifest(m, staging, true)
	if not ok then return finish(msg or "badframe", false) end
	if not write_manifest(staging, m) then return finish("manifest", false) end

	local swapped, err = swap_dir(staging, dir)
	if not swapped then return finish("install", false) end

	uci:set("glanim", "globals", "frames_dir", dir)
	uci:set("glanim", "globals", "enabled", "1")
	uci:commit("glanim")
	sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")

	return finish("installed:" .. tostring(#m.frames), true)
end

function action_upload_image()
	local sys = require "luci.sys"
	local fs = require "nixio.fs"
	local uci = uci_cursor()
	local target, is_bg, dir, staging

	sys.call("rm -rf " .. TMP_IMAGE_DIR .. " && mkdir -p " .. TMP_IMAGE_DIR)

	local fd = nil
	local cur_file = nil
	local bytes = 0
	local too_big = false

	luci.http.setfilehandler(function(meta, chunk, eof)
		if not meta or not (meta.name or meta.file) then return end
		local key = meta.name or meta.file
		if not key:match("^framefile_%d+$") then return end
		local tmp = TMP_IMAGE_DIR .. "/" .. key
		if not cur_file or cur_file ~= tmp then
			if fd then fd:close() end
			fd = nixio.open(tmp, "w")
			cur_file = tmp
			bytes = 0
		end
		if chunk and fd then
			bytes = bytes + #chunk
			if bytes > FRAME_BYTES + 1 then too_big = true else fd:write(chunk) end
		end
		if eof and fd then
			fd:close()
			fd = nil
			cur_file = nil
		end
	end)

	-- consume multipart body so the file handler runs
	luci.http.formvalue("__trigger")
	local manifest_text = luci.http.formvalue("manifest") or ""
	target = luci.http.formvalue("target") or "screen"
	is_bg = target == "bg"
	dir = is_bg and CUSTOM_BG_DIR or frames_dir()
	staging = dir .. ".new"

	local function cleanup()
		sys.call("rm -rf " .. TMP_IMAGE_DIR .. " " .. (staging or ""))
	end

	local function finish(key, ok)
		cleanup()
		if is_xhr() then
			if ok then
				return json_reply({ ok = true, msg = key })
			end
			return json_reply({ ok = false, msg = key }, 400)
		end
		redirect_msg(key)
	end

	if too_big then return finish("badframe", false) end
	if manifest_text == "" then return finish("nofile", false) end

	local ok, m = pcall(json_lib().parse, manifest_text)
	if not ok or type(m) ~= "table" then return finish("manifest", false) end
	if type(m.frames) ~= "table" or #m.frames < 1 then return finish("manifest", false) end
	if #m.frames > MAX_FRAMES then return finish("toomany", false) end
	if is_bg and #m.frames > MAX_BG_FRAMES then
		local kept = {}
		for i = 1, MAX_BG_FRAMES do kept[i] = m.frames[i] end
		m.frames = kept
	end

	local seen = {}
	for i = 1, #m.frames do
		local fr = m.frames[i]
		if type(fr) ~= "table" or not safe_name(fr.file) then
			return finish("badname", false)
		end
		if seen[fr.file] then return finish("badname", false) end
		seen[fr.file] = true

		local tmp = TMP_IMAGE_DIR .. "/framefile_" .. i
		local st = fs.stat(tmp)
		if not st or st.size ~= FRAME_BYTES then return finish("badframe", false) end

		local delay = tonumber(fr.delay_ms) or 100
		delay = math.max(MIN_FRAME_MS, math.min(MAX_FRAME_MS, math.floor(delay)))
		fr.delay_ms = delay
	end

	m.width = 76
	m.height = 284
	m.format = "rgb565le"
	if type(m.source) ~= "string" or m.source == "" then m.source = "browser upload" end

	sys.call("rm -rf " .. staging)
	sys.call("mkdir -p " .. staging)
	for i = 1, #m.frames do
		local src = TMP_IMAGE_DIR .. "/framefile_" .. i
		local dst = staging .. "/" .. m.frames[i].file
		if sys.call("cp " .. src .. " " .. dst .. " 2>/dev/null") ~= 0 then
			return finish("install", false)
		end
	end
	if not write_manifest(staging, m) then return finish("manifest", false) end

	local swapped, err = swap_dir(staging, dir)
	if not swapped then return finish("install", false) end

	if is_bg then
		-- Keep the last three uploaded backgrounds as selectable presets.
		sys.call("mkdir -p " .. BG_HISTORY_DIR)
		sys.call("rm -rf " .. BG_HISTORY_DIR .. "/3")
		sys.call("mv " .. BG_HISTORY_DIR .. "/2 " .. BG_HISTORY_DIR .. "/3 2>/dev/null")
		sys.call("mv " .. BG_HISTORY_DIR .. "/1 " .. BG_HISTORY_DIR .. "/2 2>/dev/null")
		sys.call("cp -a " .. dir .. " " .. BG_HISTORY_DIR .. "/1")
		local fps = tonumber(luci.http.formvalue("fps")) or 8
		fps = math.max(1, math.min(15, math.floor(fps)))
		uci:set("glanim", "globals", "custom_bg_dir", dir)
		uci:set("glanim", "globals", "custom_bg_frames", tostring(#m.frames))
		uci:set("glanim", "globals", "custom_bg_fps", tostring(fps))
		uci:commit("glanim")
		if cfg_str("enabled", "0") == "1" and cfg_str("mode", "") == "custom" then
			sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
		end
	else
		uci:set("glanim", "globals", "frames_dir", dir)
		uci:set("glanim", "globals", "enabled", "1")
		uci:commit("glanim")
		sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
	end

	return finish("installed:" .. tostring(#m.frames), true)
end

function action_download()
	local sys = require "luci.sys"
	local fs = require "nixio.fs"
	local kind = luci.http.formvalue("type") or "frames"
	local dir, name
	if kind == "frames" then
		dir = frames_dir()
		name = "glanim-frames.tar.gz"
	elseif kind == "bg" then
		dir = CUSTOM_BG_DIR
		name = "glanim-background.tar.gz"
	elseif kind == "history" then
		local slot = tonumber(luci.http.formvalue("slot")) or 0
		if slot < 1 or slot > 3 then
			luci.http.status(400, "Bad Request")
			return
		end
		dir = BG_HISTORY_DIR .. "/" .. slot
		name = "glanim-background-" .. slot .. ".tar.gz"
	else
		luci.http.status(400, "Bad Request")
		return
	end
	local m = read_manifest(dir)
	if not m or type(m.frames) ~= "table" or #m.frames < 1 then
		luci.http.status(404, "Not Found")
		return
	end
	local tmp = "/tmp/glanim-download.tar.gz"
	sys.call("rm -f " .. tmp)
	if sys.call("tar -czf " .. tmp .. " -C " .. dir .. " . 2>/dev/null") ~= 0 or not fs.access(tmp) then
		luci.http.status(500, "Internal Server Error")
		return
	end
	luci.http.header("Content-Disposition", 'attachment; filename="' .. name .. '"')
	luci.http.header("Cache-Control", "no-store")
	luci.http.prepare_content("application/gzip")
	local f = io.open(tmp, "rb")
	if not f then
		luci.http.status(500, "Internal Server Error")
		return
	end
	while true do
		local chunk = f:read(65536)
		if not chunk then break end
		luci.http.write(chunk)
	end
	f:close()
	os.remove(tmp)
end

function action_bg_history()
	local slots = {}
	for i = 1, 3 do
		local m = read_manifest(BG_HISTORY_DIR .. "/" .. i)
		if m and type(m.frames) == "table" and #m.frames > 0 then
			slots[#slots + 1] = {
				slot = i,
				frames = #m.frames,
				source = type(m.source) == "string" and m.source or "",
			}
		end
	end
	return json_reply({ ok = true, slots = slots })
end

function action_bg_restore()
	local sys = require "luci.sys"
	local slot = tonumber(luci.http.formvalue("slot")) or 0
	if slot < 1 or slot > 3 then
		return json_reply({ ok = false, error = "bad_slot" }, 400)
	end
	local src = BG_HISTORY_DIR .. "/" .. slot
	local m = read_manifest(src)
	if not m or type(m.frames) ~= "table" or #m.frames < 1 then
		return json_reply({ ok = false, error = "empty" }, 404)
	end
	sys.call("rm -rf " .. CUSTOM_BG_DIR .. " " .. CUSTOM_BG_DIR .. ".new")
	if sys.call("cp -a " .. src .. " " .. CUSTOM_BG_DIR) ~= 0 then
		return json_reply({ ok = false, error = "copy" }, 500)
	end
	local uci = uci_cursor()
	uci:set("glanim", "globals", "custom_bg_dir", CUSTOM_BG_DIR)
	uci:set("glanim", "globals", "custom_bg_frames", tostring(#m.frames))
	uci:set("glanim", "globals", "custom_bg_fps", tostring(math.max(1, math.min(15, tonumber(m.fps) or 8))))
	uci:commit("glanim")
	if cfg_str("enabled", "0") == "1" then
		sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
	end
	return json_reply({ ok = true, slot = slot, frames = #m.frames })
end


function action_clear_bg()
	local sys = require "luci.sys"
	local uci = uci_cursor()
	sys.call("rm -rf " .. CUSTOM_BG_DIR .. " " .. CUSTOM_BG_DIR .. ".new 2>/dev/null")
	uci:delete("glanim", "globals", "custom_bg_dir")
	uci:delete("glanim", "globals", "custom_bg_frames")
	uci:delete("glanim", "globals", "custom_bg_fps")
	uci:commit("glanim")
	if cfg_str("enabled", "0") == "1" and cfg_str("mode", "") == "custom" then
		sys.call("/etc/init.d/glanim restart >/dev/null 2>&1")
	end
	if is_xhr() then
		return json_reply({ ok = true, cleared = true })
	end
	redirect_msg("background_cleared")
end

function action_clear()
	local sys = require "luci.sys"
	local uci = uci_cursor()
	local dir = frames_dir()

	-- Only remove this plugin's own pack files, never arbitrary files in a
	-- user-chosen frames directory.
	sys.call("rm -f " .. dir .. "/manifest.json " .. dir .. "/*.rgb565 2>/dev/null")
	sys.call("rm -f /tmp/glanim.status")
	uci:set("glanim", "globals", "enabled", "0")
	uci:commit("glanim")
	sys.call("/etc/init.d/glanim stop >/dev/null 2>&1")
	sys.call("/etc/init.d/gl_screen enable >/dev/null 2>&1")
	sys.call("/etc/init.d/gl_screen start >/dev/null 2>&1")

	if is_xhr() then
		return json_reply({ ok = true, msg = "cleared" })
	end
	redirect_msg("cleared")
end

function action_restore_oem()
	local sys = require "luci.sys"
	local uci = uci_cursor()

	uci:set("glanim", "globals", "enabled", "0")
	uci:commit("glanim")
	luci.sys.init.stop("glanim")
	sys.call("rm -f /tmp/glanim.status")
	sys.call("/etc/init.d/gl_screen enable >/dev/null 2>&1")
	sys.call("/etc/init.d/gl_screen start >/dev/null 2>&1")

	if is_xhr() then
		return json_reply({ ok = true, msg = "restored" })
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glanim", "main"))
end
