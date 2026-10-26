local uci = require("luci.model.uci").cursor()
local sys = require "luci.sys"
local util = require "luci.util"
local json = require "luci.jsonc"

local VERSION = "1.0.7"

local function h(value)
	return util.pcdata(tostring(value or ""))
end

local function cfg_str(key, default)
	local v = uci:get("glfanctl", "globals", key)
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
	return cfg_str(key, default and "1" or "0") == "1"
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
	local f = io.open("/tmp/glfanctl.status", "r")
	if not f then return nil end
	local d = {}
	for line in f:lines() do
		local k, v = line:match("^([^=]+)=(.*)$")
		if k then d[k] = v end
	end
	f:close()
	return d
end

local status = read_status_file()
local daemon_pid = (sys.exec("pidof glfanctl") or ""):gsub("%s+", "")
local oem_pid = (sys.exec("pidof gl_fan") or ""):gsub("%s+", "")
local daemon_on = #daemon_pid > 0
local oem_on = #oem_pid > 0
local rpm = read_raw("/sys/class/hwmon/hwmon0/fan1_input") or "0"
local pwm = read_raw("/sys/class/hwmon/hwmon0/pwm1") or "0"
local temps = {}
for i = 0, 4 do
	local v = read_raw("/sys/devices/virtual/thermal/thermal_zone" .. i .. "/temp")
	temps[i] = v and math.floor(tonumber(v) / 1000) or -1
end

local cur_enabled = cfg_bool("enabled", false)
local cur_mode = cfg_str("mode", "auto")
if cur_mode ~= "auto" and cur_mode ~= "curve" and cur_mode ~= "manual" and cur_mode ~= "stop" then
	cur_mode = "auto"
end
local cur_zone = cfg_num("temp_zone", 0, 0, 4)
local cur_poll = cfg_num("poll", 2, 1, 30)
local cur_hyst = cfg_num("hysteresis", 2, 0, 10)
local cur_manual = cfg_num("pwm_manual", 40, 0, 255)
local cur_min = cfg_num("min_pwm", 0, 0, 255)
local cur_max = cfg_num("max_pwm", 255, 0, 255)
local STEP_T = { 10, 20, 30, 40, 50, 60, 70, 80, 90, 100 }
local PCT_SEED = { "0", "0", "0", "0", "7", "25", "49", "75", "94", "100" }
local pct = {}
for i = 1, 10 do
	pct[i] = cfg_num("pct" .. i, tonumber(PCT_SEED[i]) or 0, 0, 100)
end

local PAGE = { "admin", "services", "glfanctl" }
local function page_url(...)
	return luci.dispatcher.build_url(PAGE[1], PAGE[2], PAGE[3], ...)
end

local cur_lang = (luci.i18n.context and luci.i18n.context.lang) or "zh-cn"
local is_zh = (cur_lang:sub(1, 2) == "zh")

local MODE_TITLE = {
	auto = translate("Auto (OEM PID)"),
	curve = translate("Temperature curve"),
	manual = translate("Fixed PWM"),
	stop = translate("Stopped (debug)"),
}

local function icon(name)
	local paths = {
		fan = '<circle cx="12" cy="12" r="3"/><path d="M12 9c0-3 1-5 4-6 2 2 2 5 0 7M15 12c3 0 5 1 6 4-2 2-5 2-7 0M12 15c0 3-1 5-4 6-2-2-2-5 0-7M9 12c-3 0-5-1-6-4 2-2 5-2 7 0"/>',
		chip = '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>',
		thermo = '<path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z"/><path d="M12 8v7"/>',
		speed = '<path d="M4 17h16M7 17a5 5 0 0 1 10 0M10 17a2 2 0 0 1 4 0"/><path d="M12 4v6"/>',
		power = '<path d="M12 3v8"/><path d="M7 6a8 8 0 1 0 10 0"/>',
		curve = '<path d="M4 20V4M4 20h16"/><path d="M6 16l4-6 4 3 5-7"/>',
		save = '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v6h7V4M8 20v-6h8v6"/>',
		undo = '<path d="M9 7L4 12l5 5"/><path d="M4 12h9a6 6 0 1 1 0 12"/>',
		gear = '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>',
	}
	return '<svg class="gl-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
		.. (paths[name] or paths.fan) .. '</svg>'
end

local function mode_card(key, ico, title, sub)
	return '<button type="button" class="gl-mode' .. (cur_mode == key and " is-active" or "")
		.. '" data-mode="' .. key .. '" role="radio" aria-checked="' .. (cur_mode == key and "true" or "false") .. '">'
		.. '<span class="gl-mode-icon">' .. icon(ico) .. '</span>'
		.. '<span class="gl-mode-body"><strong>' .. h(title) .. '</strong><small>' .. h(sub) .. '</small></span>'
		.. '<span class="gl-mode-check">' .. icon("save") .. '</span></button>'
end

local page = {}
local add = function(s) page[#page + 1] = s end

add('<link rel="stylesheet" href="/luci-static/resources/glfanctl/glfanctl.css?v=' .. VERSION .. '">')
add('<div class="gl-page fan-page" id="glfanctl-page">')

-- hero
add('<div class="gl-hero"><div class="gl-hero-main"><div class="gl-hero-icon">' .. icon("fan") .. '</div>'
	.. '<div class="gl-hero-text"><div class="gl-kicker">GL-BE3600 <span></span> PWM FAN <span></span> v' .. VERSION .. '</div>'
	.. '<h1>' .. h(translate("Fan Control")) .. '</h1>'
	.. '<p>' .. h(translate("Custom fan policy for GL-BE3600. Auto keeps the OEM PID; curve and manual drive the PWM from this daemon; disabling hands the fan back to gl_fan.")) .. '</p>'
	.. '</div></div><div class="gl-hero-side">'
	.. '<div class="gl-langbar"><a class="gl-lang' .. (is_zh and " is-active" or "") .. '" href="' .. page_url("set_lang") .. '?lang=zh-cn">中文</a>'
	.. '<a class="gl-lang' .. (not is_zh and " is-active" or "") .. '" href="' .. page_url("set_lang") .. '?lang=en">EN</a></div>'
	.. '<div class="gl-live' .. (daemon_on and " is-on" or "") .. '" id="fan-live"><span class="gl-live-dot"></span><span id="fan-live-text">'
	.. h(daemon_on and translate("plugin driving PWM") or translate("OEM gl_fan running")) .. '</span></div>'
	.. '</div></div>')

-- pills
add('<div class="gl-pills">')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Service")) .. '</span><strong id="fan-pill-service">' .. h(daemon_on and translate("plugin") or (oem_on and translate("OEM") or translate("stopped"))) .. '</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Mode")) .. '</span><strong id="fan-pill-mode">' .. h(MODE_TITLE[cur_mode]) .. '</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Fan speed")) .. '</span><strong id="fan-pill-rpm">' .. h(rpm) .. ' RPM</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">PWM</span><strong id="fan-pill-pwm">' .. h(pwm) .. '/255</strong></span>')
add('<span class="gl-pill"><span class="gl-pill-k">' .. h(translate("Temperature")) .. '</span><strong id="fan-pill-temp">' .. h(temps[0]) .. '°C</strong></span>')
add('</div>')

-- grid: live + policy
add('<div class="gl-grid">')
add('<section class="gl-card fan-live"><div class="gl-card-head"><div><h2>' .. h(translate("Live status")) .. '</h2><p>'
	.. h(translate("PWM, RPM and the five thermal zones update every two seconds.")) .. '</p></div><span class="gl-badge" id="fan-live-badge">'
	.. h(daemon_on and translate("live") or translate("idle")) .. '</span></div>')
add('<div class="fan-big"><strong id="fan-rpm">' .. h(rpm) .. '</strong><span>RPM</span></div>')
add('<div class="fan-metrics">'
	.. '<div class="fan-metric">' .. icon("speed") .. '<span>PWM</span><strong id="fan-pwm">' .. h(pwm) .. '/255</strong></div>'
	.. '<div class="fan-metric">' .. icon("thermo") .. '<span>' .. h(translate("Temperature")) .. '</span><strong id="fan-temp">' .. h(temps[0]) .. '°C</strong></div>'
	.. '<div class="fan-metric">' .. icon("chip") .. '<span>' .. h(translate("Mode")) .. '</span><strong id="fan-mode">' .. h(MODE_TITLE[cur_mode]) .. '</strong></div>'
	.. '<div class="fan-metric">' .. icon("power") .. '<span>' .. h(translate("Service")) .. '</span><strong id="fan-service">'
	.. h(daemon_on and translate("plugin") or (oem_on and translate("OEM") or translate("stopped"))) .. '</strong></div>'
	.. '</div>')
add('<div class="fan-pwmbar"><div class="fan-pwmbar-fill" id="fan-pwm-fill" style="width:0%"></div><span id="fan-pwm-label">0%</span></div>')
add('<div class="fan-zones" id="fan-zones"></div>')
add('<div class="fan-chart-wrap"><div class="fan-chart-head"><span>' .. h(translate("Recent PWM / RPM")) .. '</span>'
	.. '<span class="fan-legend"><i class="fan-leg-pwm"></i>PWM % <i class="fan-leg-rpm"></i>RPM <i class="fan-leg-temp"></i>TEMP °C</span></div>'
	.. '<canvas id="fan-chart" width="720" height="220"></canvas></div>')
add('<div class="fan-zone-bars" id="fan-zone-bars"></div>')
add('</section>')

add('<section class="gl-card fan-policy"><div class="gl-card-head"><div><h2>' .. h(translate("Policy")) .. '</h2><p>'
	.. h(translate("Choose who drives the fan. The plugin only touches PWM in curve/manual/stop mode.")) .. '</p></div></div>')
add('<label class="gl-switch" for="fan-enabled"><span class="gl-switch-text"><strong>' .. h(translate("Enabled")) .. '</strong>'
	.. '<small>' .. h(translate("Start the plugin daemon and take over the fan.")) .. '</small></span>'
	.. '<input type="checkbox" id="fan-enabled"' .. (cur_enabled and ' checked="checked"' or '') .. '><span class="gl-switch-ui" aria-hidden="true"></span></label>')
add('<div class="fan-mode-grid gl-mode-grid" id="fan-mode-grid" role="radiogroup" aria-label="' .. h(translate("Control mode")) .. '">')
add(mode_card("auto", "gear", translate("Auto (OEM PID)"), translate("Leave gl_fan in control; the daemon only reports.")))
add(mode_card("curve", "curve", translate("Temperature curve"), translate("Drive PWM from the 10-step curve below.")))
add(mode_card("manual", "speed", translate("Fixed PWM"), translate("Drive a constant PWM value.")))
add(mode_card("stop", "power", translate("Stopped (debug)"), translate("Cut power to the fan; overheat risk.")))
add('</div>')
add('<div class="fan-fields">')
add('<div class="gl-field"><label for="fan-zone">' .. h(translate("Temperature sensor")) .. '</label><select id="fan-zone">')
for i = 0, 4 do
	add('<option value="' .. i .. '"' .. (cur_zone == i and ' selected="selected"' or '') .. '>Zone ' .. i .. '</option>')
end
add('</select><small>' .. h(translate("Thermal zone used by curve mode.")) .. '</small></div>')
local function num_field(id, label, hint, lo, hi, value)
	add('<div class="gl-field"><label for="' .. id .. '">' .. h(label) .. '</label>'
		.. '<input type="number" id="' .. id .. '" min="' .. lo .. '" max="' .. hi .. '" value="' .. value .. '">'
		.. '<small>' .. h(hint) .. '</small></div>')
end
num_field("fan-poll", translate("Poll interval (s)"), translate("Seconds between PWM updates."), 1, 30, cur_poll)
num_field("fan-hyst", translate("Hysteresis (°C)"), translate("Prevents PWM hunting near a threshold."), 0, 10, cur_hyst)
num_field("fan-manual", translate("Fixed PWM"), translate("manual mode: 0 = off, 255 = full speed."), 0, 255, cur_manual)
num_field("fan-min", translate("Minimum PWM"), translate("Curve mode lower clamp."), 0, 255, cur_min)
num_field("fan-max", translate("Maximum PWM"), translate("Curve mode upper clamp."), 0, 255, cur_max)
add('</div>')
add('<div class="fan-note">' .. icon("power") .. '<span>' .. h(translate("Disable the plugin or use Restore OEM to hand the fan back to gl_fan.")) .. '</span></div>')
add('</section></div>')

-- curve editor
add('<section class="gl-card fan-curve"><div class="gl-card-head"><div><h2>' .. h(translate("Temperature / fan speed curve")) .. '</h2><p>'
	.. h(translate("Drag the nodes or edit the 10 values. Percent is converted to PWM = pct × 255 / 100, then clamped by min/max PWM.")) .. '</p></div>'
	.. '<span class="gl-badge" id="fan-curve-badge">' .. h(translate("10 steps")) .. '</span></div>')
add('<div class="fan-curve-grid"><div class="fan-curve-canvas"><svg id="fan-curve-svg" viewBox="0 0 720 250" preserveAspectRatio="xMidYMid meet"></svg></div>'
	.. '<div class="fan-curve-inputs" id="fan-curve-inputs">')
for i = 1, 10 do
	add('<label class="fan-curve-cell"><span>' .. STEP_T[i] .. '°C</span><input type="number" id="fan-pct-' .. i
		.. '" min="0" max="100" value="' .. pct[i] .. '"></label>')
end
add('</div></div></section>')

-- save bar
add('<div class="gl-savebar" id="fan-savebar"><div class="gl-save-state"><span class="gl-save-dot" id="fan-save-dot"></span><span id="fan-save-text">'
	.. h(translate("All changes saved")) .. '</span></div><div class="gl-save-actions">'
	.. '<button type="button" class="gl-btn ghost is-danger" id="fan-restore">' .. icon("undo") .. h(translate("Restore OEM control")) .. '</button>'
	.. '<button type="button" class="gl-btn primary" id="fan-save">' .. icon("save") .. h(translate("Save & Apply")) .. '</button>'
	.. '</div></div>')
add('<div class="gl-toast" id="fan-toast" role="status" aria-live="polite"></div>')
add('<footer class="gl-author">' .. h(translate("Author")) .. ' <strong>@xavierbe278</strong><span>·</span><a href="https://github.com/xavierbe278/gl-be3600-toolbox" target="_blank" rel="noopener">' .. h(translate("GitHub project")) .. '</a><span>·</span>v' .. VERSION .. '</footer>')
add('</div>')

local cfg_json = {
	version = VERSION,
	zh = is_zh,
	current = {
		enabled = cur_enabled,
		mode = cur_mode,
		zone = cur_zone,
		poll = cur_poll,
		hysteresis = cur_hyst,
		manual = cur_manual,
		min = cur_min,
		max = cur_max,
		pct = pct,
	},
	initial = {
		daemon = daemon_on and "1" or "0",
		oem = oem_on and "1" or "0",
		mode = cur_mode,
		rpm = tonumber(rpm) or 0,
		pwm = tonumber(pwm) or 0,
		temps = temps,
	},
	urls = {
		status = page_url("status"),
		save = page_url("save"),
		restore = page_url("restore_oem"),
	},
}
local cfg_text = json.stringify(cfg_json)
cfg_text = cfg_text:gsub("<", "\\u003c"):gsub(">", "\\u003e"):gsub("&", "\\u0026")
add('<script>window.GLFAN_CFG=' .. cfg_text .. ';</script>')
add('<script src="/luci-static/resources/glfanctl/glfanctl.js?v=' .. VERSION .. '"></script>')

local f = Map("glfanctl", "", "")
f.reset = false
f.hideapplybtn = true
f.hidesavebtn = true
f.hideresetbtn = true
f.pageaction = false
f.submit = false

local sec = f:section(SimpleSection, nil, "")
sec.description = table.concat(page)
return f
