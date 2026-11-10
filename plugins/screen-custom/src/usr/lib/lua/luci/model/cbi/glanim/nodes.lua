local sys = require "luci.sys"

local m = Map("glanim", translate("节点策略"),
	translate("决定 OpenClash 里哪些节点可以被选中，以及是否允许自动切换。"))

local s = m:section(TypedSection, "globals", translate("OpenClash 节点"))
s.anonymous = true
s.addremove = false

local auto = s:option(Flag, "oc_auto_switch", translate("自动切换节点"))
auto.default = "0"
auto.rmempty = false
auto.description = translate("开启后 Clash 会按延迟自动换节点；关闭后分组改为手动，只有手动选择才会切换。")

local kw = s:option(Value, "oc_exclude_keywords", translate("排除关键字"))
kw.default = "防失联,官网,剩余流量,套餐到期,距离下次重置,收藏"
kw.rmempty = true
kw.description = translate("逗号分隔。节点名包含任一关键字的，从所有分组中移除，无法被选中。")

function m.on_after_commit(self)
	sys.call("/usr/bin/glanim-clash-guard apply >/tmp/glanim-guard.log 2>&1 &")
end

return m
