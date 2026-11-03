local m = Map("fastnet", translate("FastNet"),
	translate("FastNet 网络体检工具。"))

local st = m:section(SimpleSection)
st.template = "fastnet/status"

return m
