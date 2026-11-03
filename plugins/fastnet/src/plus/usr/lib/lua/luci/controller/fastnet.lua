module("luci.controller.fastnet", package.seeall)

function index()
	if not nixio.fs.access("/etc/config/fastnet") then return end

	entry({"admin", "services", "fastnet"}, cbi("fastnet"), _("FastNet"), 50).dependent = false
	entry({"admin", "services", "fastnet", "switch"}, call("action_switch")).leaf = true
	entry({"admin", "services", "fastnet", "save"}, call("action_save")).leaf = true
end

local function commit_and_restart()
	luci.sys.call("/etc/init.d/fastnet restart >/dev/null 2>&1")
end

-- 版本切换：写 uci 后重启
function action_switch()
	local ver = luci.http.formvalue("ver")
	if ver == "0.7.6" or ver == "0.7.7" then
		local uci = require "luci.model.uci".cursor()
		uci:set("fastnet", "fastnet", "version", ver)
		uci:commit("fastnet")
		commit_and_restart()
	end
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "fastnet"))
end

-- 插件设置：开关 / 端口 / token / 日志
function action_save()
	local uci = require "luci.model.uci".cursor()

	local enabled = luci.http.formvalue("enabled")
	local logger  = luci.http.formvalue("logger")
	local port    = luci.http.formvalue("port")
	local token   = luci.http.formvalue("token")

	uci:set("fastnet", "fastnet", "enabled", (enabled == "1") and "1" or "0")
	uci:set("fastnet", "fastnet", "logger",  (logger  == "1") and "1" or "0")
	uci:set("fastnet", "fastnet", "token",   token or "")
	if port and port:match("^%d+$") then
		uci:set("fastnet", "fastnet", "port", port)
	end
	uci:commit("fastnet")
	commit_and_restart()

	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "fastnet"))
end
