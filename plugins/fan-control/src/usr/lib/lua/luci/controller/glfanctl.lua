module("luci.controller.glfanctl", package.seeall)

function index()
	if not nixio.fs.access("/etc/config/glfanctl") then
		return
	end

	local page

	page = entry({"admin", "services", "glfanctl"}, alias("admin", "services", "glfanctl", "main"), _("Fan Control"), 55)
	page.dependent = true
	page.acl_depends = { "luci-app-glfanctl" }

	entry({"admin", "services", "glfanctl", "main"},
		cbi("glfanctl/main"), _("Fan Policy"), 10).leaf = true

	entry({"admin", "services", "glfanctl", "status"}, call("action_status")).leaf = true
	entry({"admin", "services", "glfanctl", "apply"}, call("action_apply")).leaf = true
	entry({"admin", "services", "glfanctl", "save"}, call("action_save")).leaf = true
	entry({"admin", "services", "glfanctl", "restore_oem"}, call("action_restore_oem")).leaf = true
	entry({"admin", "services", "glfanctl", "set_lang"}, call("action_set_lang")).leaf = true
end

function action_set_lang()
	local lang = luci.http.formvalue("lang") or ""
	local uci_lang = ({ ["zh-cn"] = "zh_cn", ["zh_cn"] = "zh_cn", ["en"] = "en" })[lang]
	if uci_lang then
		luci.sys.exec("uci set luci.main.lang='%s' && uci commit luci" % uci_lang)
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glfanctl", "main"))
end

local function read_status_file()
	local f = io.open("/tmp/glfanctl.status", "r")
	if not f then return nil end
	local data = {}
	for line in f:lines() do
		local k, v = line:match("^([^=]+)=(.*)$")
		if k then data[k] = v end
	end
	f:close()
	return data
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

function action_status()
	local status = read_status_file() or {}
	local temps = {}
	for i = 0, 4 do
		local v = read_raw("/sys/devices/virtual/thermal/thermal_zone" .. i .. "/temp")
		temps[i] = v and math.floor(tonumber(v) / 1000) or -1
	end
	local rpm = read_raw("/sys/class/hwmon/hwmon0/fan1_input") or "0"
	local pwm = read_raw("/sys/class/hwmon/hwmon0/pwm1") or "0"

	local pid_daemon = luci.sys.exec("pidof glfanctl")
	local pid_oem = luci.sys.exec("pidof gl_fan")
	local daemon_on = (pid_daemon and pid_daemon:gsub("%s", "") ~= "") and "1" or "0"
	local oem_on = (pid_oem and pid_oem:gsub("%s", "") ~= "") and 1 or 0
	local uci = require("luci.model.uci").cursor()
	local enabled = uci:get("glfanctl", "globals", "enabled") or "0"

	local json = require "luci.jsonc"
	luci.http.prepare_content("application/json")
	luci.http.header("Cache-Control", "no-store")
	luci.http.write(json.stringify({
		daemon   = daemon_on,
		enabled  = enabled,
		mode     = (daemon_on == "1") and (status.mode or "auto") or "auto",
		temp     = tonumber(status.temp),
		temps    = temps,
		pwm      = tonumber(pwm),
		rpm      = tonumber(rpm),
		oem_running = oem_on,
		uptime   = tonumber(status.uptime) or 0
	}))
end

function action_apply()
	luci.sys.init.stop("glfanctl")
	luci.sys.init.enable("glfanctl")
	luci.sys.init.start("glfanctl")
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glfanctl", "main"))
end

-- Fixed 10-step curve seed percentages (10..100 °C), same as the model defaults.
local PCT_SEED = { "0", "0", "0", "0", "7", "25", "49", "75", "94", "100" }

local function is_xhr()
	local h = luci.http.getenv("HTTP_X_REQUESTED_WITH") or ""
	local accept = luci.http.getenv("HTTP_ACCEPT") or ""
	return h == "XMLHttpRequest" or accept:find("application/json", 1, true) ~= nil
end

local function json_reply(data, code)
	if code then luci.http.status(code, "Error") end
	luci.http.prepare_content("application/json")
	luci.http.write(require("luci.jsonc").stringify(data))
end

-- Standalone form submission: the page keeps its own <form> posting here instead
-- of the global CBI Apply button, so LuCI never marks the page dirty and the
-- global Save cannot reach this plugin. Every value is clamped and written as a
-- single option (any leftover list for pct* is removed first).
function action_save()
	local uci = require("luci.model.uci").cursor()
	local http = luci.http

	local function num(key, default, lo, hi)
		local v = tonumber(http.formvalue(key)) or default
		if v < lo then v = lo end
		if v > hi then v = hi end
		return math.floor(v)
	end

	local ev = http.formvalue("enabled")
	local enabled = (ev == "1" or ev == "on" or ev == "true") and "1" or "0"
	local mode = http.formvalue("mode") or "auto"
	if mode ~= "auto" and mode ~= "curve" and mode ~= "manual" and mode ~= "stop" then
		mode = "auto"
	end

	local zone = num("temp_zone", 0, 0, 4)
	local poll = num("poll", 2, 1, 30)
	local hyst = num("hysteresis", 2, 0, 10)
	local manual = num("pwm_manual", 40, 0, 255)
	local minp = num("min_pwm", 0, 0, 255)
	local maxp = num("max_pwm", 255, 0, 255)
	if minp > maxp then local t = minp; minp = maxp; maxp = t end

	uci:set("glfanctl", "globals", "enabled", enabled)
	uci:set("glfanctl", "globals", "mode", mode)
	uci:set("glfanctl", "globals", "temp_zone", tostring(zone))
	uci:set("glfanctl", "globals", "poll", tostring(poll))
	uci:set("glfanctl", "globals", "hysteresis", tostring(hyst))
	uci:set("glfanctl", "globals", "pwm_manual", tostring(manual))
	uci:set("glfanctl", "globals", "min_pwm", tostring(minp))
	uci:set("glfanctl", "globals", "max_pwm", tostring(maxp))

	for i = 1, 10 do
		local v = num("pct" .. i, tonumber(PCT_SEED[i]), 0, 100)
		uci:delete("glfanctl", "globals", "pct" .. i)
		uci:set("glfanctl", "globals", "pct" .. i, tostring(v))
	end
	uci:commit("glfanctl")

	luci.sys.init.stop("glfanctl")
	luci.sys.init.enable("glfanctl")
	luci.sys.init.start("glfanctl")

	if is_xhr() then
		return json_reply({ ok = true, enabled = enabled, mode = mode })
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glfanctl", "main"))
end

function action_restore_oem()
	local uci = require("luci.model.uci").cursor()
	uci:set("glfanctl", "globals", "enabled", "0")
	uci:commit("glfanctl")
	luci.sys.init.stop("glfanctl")
	luci.sys.call("/etc/init.d/gl_fan start >/dev/null 2>&1")

	if is_xhr() then
		return json_reply({ ok = true, enabled = "0" })
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "glfanctl", "main"))
end
