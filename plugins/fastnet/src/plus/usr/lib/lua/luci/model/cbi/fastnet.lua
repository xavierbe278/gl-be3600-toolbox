local m = Map("fastnet", translate("FastNet"),
	translate("FastNet 网络体检工具，内置 0.7.6 / 0.7.7 双版本，同一时间运行其中一个。"))

-- 页面整体由模板渲染：顶部左右两栏（运行状态 | 插件设置）
local st = m:section(SimpleSection)
st.template = "fastnet/status"

return m
