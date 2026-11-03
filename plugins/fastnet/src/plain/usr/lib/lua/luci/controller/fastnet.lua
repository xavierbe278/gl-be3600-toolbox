module("luci.controller.fastnet", package.seeall)

function index()
	if not nixio.fs.access("/etc/config/fastnet") then return end

	entry({"admin", "services", "fastnet"}, cbi("fastnet"), _("FastNet"), 50).dependent = false
	entry({"admin", "services", "fastnet", "save"}, call("action_save")).leaf = true
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

	luci.sys.call("/etc/init.d/fastnet restart >/dev/null 2>&1")
	luci.http.redirect(luci.dispatcher.build_url("admin", "services", "fastnet"))
end
