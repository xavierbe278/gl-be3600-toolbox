/* Screen Custom (glanim) front-end.
 *
 * Loaded from /luci-static/resources/glanim/glanim.js by the CBI model.
 * The page keeps its own form state and its own Save & Apply endpoint; it never
 * registers a writeable CBI option, so LuCI's global change tracker and the
 * global Save & Apply button cannot touch this plugin.
 */
(function () {
  "use strict";

  var CFG = window.GLANIM_CFG || {};
  var ZH = !!CFG.zh;
  var URLS = CFG.urls || {};
  var CURRENT = CFG.current || {};
  var PACK = CFG.pack || { count: 0, delays: [], valid: false, source: "" };
  var STATUS = CFG.status || {};
  var CUSTOM = clone(CFG.custom || defaultCustomLayout());
  var customSelected = -1;

  var MAX_FRAMES = 300;              // browser-decoded GIF / video / background
  var MAX_DECODE_PIXELS = 24000000;  // total decoded RGBA pixels across all frames
  var MAX_SOURCE_SIDE = 480;         // long side of the decoded source frames
  var MAX_VIDEO_FRAMES = 300;        // a 60 s video at 10 fps is sampled to <=300
  var MAX_VIDEO_SECONDS = 60;
  var VIDEO_FPS = 10;
  var STAGE_W = 560;
  var STAGE_H = 168;
  var PANEL_W = 284;
  var PANEL_H = 76;
  var PIXEL_FONT = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00],
    "%": [0x23, 0x13, 0x08, 0x64, 0x62],
    "(": [0x00, 0x07, 0x08, 0x08, 0x00],
    ")": [0x00, 0x70, 0x08, 0x08, 0x00],
    "+": [0x08, 0x08, 0x7F, 0x08, 0x08],
    "-": [0x00, 0x08, 0x08, 0x08, 0x00],
    ".": [0x00, 0x00, 0x00, 0x30, 0x30],
    "/": [0x40, 0x20, 0x10, 0x08, 0x04],
    "0": [0x3E, 0x51, 0x49, 0x45, 0x3E],
    "1": [0x00, 0x42, 0x7F, 0x40, 0x00],
    "2": [0x42, 0x61, 0x51, 0x49, 0x46],
    "3": [0x21, 0x45, 0x49, 0x49, 0x36],
    "4": [0x18, 0x14, 0x12, 0x7F, 0x10],
    "5": [0x27, 0x45, 0x45, 0x45, 0x39],
    "6": [0x3C, 0x4A, 0x49, 0x49, 0x30],
    "7": [0x01, 0x71, 0x09, 0x05, 0x03],
    "8": [0x36, 0x49, 0x49, 0x49, 0x36],
    "9": [0x06, 0x49, 0x49, 0x29, 0x1E],
    ":": [0x00, 0x36, 0x36, 0x00, 0x00],
    "<": [0x11, 0x22, 0x44, 0x22, 0x11],
    "=": [0x08, 0x08, 0x08, 0x08, 0x08],
    ">": [0x44, 0x28, 0x10, 0x28, 0x44],
    "A": [0x7E, 0x11, 0x11, 0x11, 0x7E],
    "B": [0x7F, 0x49, 0x49, 0x49, 0x36],
    "C": [0x3E, 0x41, 0x41, 0x41, 0x22],
    "D": [0x7F, 0x41, 0x41, 0x22, 0x1C],
    "E": [0x7F, 0x49, 0x49, 0x49, 0x41],
    "F": [0x7F, 0x09, 0x09, 0x09, 0x01],
    "G": [0x3E, 0x41, 0x49, 0x49, 0x7A],
    "H": [0x7F, 0x08, 0x08, 0x08, 0x7F],
    "I": [0x41, 0x41, 0x7F, 0x41, 0x41],
    "J": [0x21, 0x41, 0x41, 0x41, 0x3E],
    "K": [0x7F, 0x08, 0x14, 0x22, 0x41],
    "L": [0x7F, 0x40, 0x40, 0x40, 0x40],
    "M": [0x7F, 0x02, 0x0C, 0x02, 0x7F],
    "N": [0x7F, 0x04, 0x08, 0x10, 0x7F],
    "O": [0x3E, 0x41, 0x41, 0x41, 0x3E],
    "P": [0x7F, 0x09, 0x09, 0x09, 0x06],
    "Q": [0x3E, 0x41, 0x51, 0x21, 0x5E],
    "R": [0x7F, 0x09, 0x19, 0x29, 0x46],
    "S": [0x26, 0x49, 0x49, 0x49, 0x32],
    "T": [0x01, 0x01, 0x7F, 0x01, 0x01],
    "U": [0x3F, 0x40, 0x40, 0x40, 0x3F],
    "V": [0x1F, 0x20, 0x40, 0x20, 0x1F],
    "W": [0x3F, 0x40, 0x38, 0x40, 0x3F],
    "X": [0x63, 0x14, 0x08, 0x14, 0x63],
    "Y": [0x07, 0x08, 0x70, 0x08, 0x07],
    "Z": [0x61, 0x51, 0x49, 0x45, 0x43],
    "_": [0x40, 0x40, 0x40, 0x40, 0x40],
  };

  var WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

  var MODE_LABEL = {
    gif: ZH ? "GIF 循环" : "GIF loop",
    still: ZH ? "静态图片" : "Still image",
    slideshow: ZH ? "幻灯片" : "Slideshow",
    dashboard: ZH ? "系统面板" : "System panel",
    custom: ZH ? "自定义面板" : "Custom panel"
  };
  var PAGE_LABEL = { clock: ZH ? "时钟" : "Clock", status: ZH ? "状态" : "Status" };
  var DATA_DEFS = [
    { key: "cpu", label: "CPU", unit: "%" },
    { key: "mem", label: ZH ? "内存" : "MEM", unit: "%" },
    { key: "temp", label: ZH ? "温度" : "TMP", unit: "C" },
    { key: "fan_rpm", label: ZH ? "风扇转速" : "FAN RPM", unit: "rpm" },
    { key: "fan_pwm", label: ZH ? "风扇 PWM" : "FAN PWM", unit: "%" },
    { key: "rx", label: ZH ? "下行" : "DL", unit: "KB/s" },
    { key: "tx", label: ZH ? "上行" : "UL", unit: "KB/s" },
    { key: "net", label: ZH ? "网速" : "NET", unit: "" },
    { key: "clock", label: ZH ? "时钟" : "CLOCK", unit: "" },
    { key: "date", label: ZH ? "日期" : "DATE", unit: "" },
    { key: "weekday", label: ZH ? "星期" : "DAY", unit: "" },
    { key: "uptime", label: ZH ? "运行时长" : "UPTIME", unit: "" },
    { key: "ip", label: "LAN IP", unit: "" },
    { key: "wan_ip", label: "WAN IP", unit: "" },
    { key: "iface", label: ZH ? "网卡" : "IFACE", unit: "" },
    { key: "hostname", label: ZH ? "主机名" : "HOST", unit: "" }
  ];

  var S = {
    enabled: !!CURRENT.enabled,
    mode: CURRENT.mode || "gif",
    fps: num(CURRENT.fps, 0),
    loop: !!CURRENT.loop,
    brightness: num(CURRENT.brightness, 4),
    keepOriginal: !!CURRENT.keepOriginal,
    framesDir: CURRENT.framesDir || "/usr/share/glanim/frames",
    interval: num(CURRENT.interval, 5),
    showTime: !!CURRENT.showTime,
    showCpu: !!CURRENT.showCpu,
    showMem: !!CURRENT.showMem,
    showTemp: !!CURRENT.showTemp,
    showNet: !!CURRENT.showNet,
    showUptime: !!CURRENT.showUptime,
    showIp: !!CURRENT.showIp,
    touchEnable: !!CURRENT.touchEnable,
    touchAction: CURRENT.touchAction || "next",
    touchSwap: !!CURRENT.touchSwap,
    touchFlip: !!CURRENT.touchFlip
  };
  var LAST = clone(S);
  var LAST_CUSTOM = clone(CUSTOM);
  var dirty = false;

  var STATUS_BUSY = false;
  var previewPage = null;
  var toastTimer = null;
  var saving = false;

  /* ---------------- small helpers ---------------- */

  function $(id) {
    return document.getElementById(id);
  }

  function num(value, fallback) {
    var n = parseInt(value, 10);
    return isNaN(n) ? fallback : n;
  }

  function clamp(value, lo, hi) {
    return Math.max(lo, Math.min(hi, value));
  }

  function pad2(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function clone(obj) {
    return JSON.parse(JSON.stringify(obj || {}));
  }

  function setText(id, text) {
    var el = $(id);
    if (el) el.textContent = text;
  }

  function setHtml(id, html) {
    var el = $(id);
    if (el) el.innerHTML = html;
  }

  function token() {
    return (typeof L !== "undefined" && L.env && L.env.token) ? L.env.token : "";
  }

  function withQuery(url, key, value) {
    if (!url) return "";
    return url + (url.indexOf("?") >= 0 ? "&" : "?") + encodeURIComponent(key) + "=" + encodeURIComponent(value);
  }

  function formBody(obj) {
    var fd = new FormData();
    Object.keys(obj).forEach(function (key) {
      fd.append(key, obj[key]);
    });
    fd.append("token", token());
    return fd;
  }

  function api(url, options) {
    options = options || {};
    options.cache = "no-store";
    options.headers = options.headers || {};
    options.headers["X-Requested-With"] = "XMLHttpRequest";
    options.headers["Accept"] = "application/json";
    return fetch(url, options).then(function (response) {
      return response.text().then(function (text) {
        var contentType = response.headers.get("content-type") || "";
        var data = null;
        try {
          data = JSON.parse(text);
        } catch (e) {
          data = null;
        }
        if (contentType.indexOf("application/json") < 0 || !data) {
          throw new Error(ZH ? "会话可能已过期，请刷新页面后重试" : "Session may have expired; reload the page");
        }
        if (!response.ok || data.ok === false) {
          var key = data.error || data.msg || ("HTTP " + response.status);
          throw new Error(errorText(key));
        }
        return data;
      });
    });
  }

  function errorText(key) {
    key = String(key || "");
    var map = {
      no_frames: ZH ? "请先上传可用的帧包，再启用 GIF / 静态图 / 幻灯片模式。" : "Upload a valid frame pack before enabling this mode.",
      no_dashboard_item: ZH ? "系统面板至少需要勾选一个显示项。" : "Select at least one dashboard item.",
      no_custom: ZH ? "自定义面板至少需要一个元素。" : "Add at least one custom element.",
      bad_layout: ZH ? "自定义布局数据无效，请重试。" : "The custom layout data is invalid.",
      bad_dir: ZH ? "帧目录必须是绝对路径，且只能包含字母、数字、点、下划线、斜杠和短横线。" : "The frame directory must be an absolute, safe path.",
      bad_mode: ZH ? "未知的播放模式。" : "Unknown play mode.",
      not_enabled: ZH ? "插件当前未启用；请先保存并启用。" : "The plugin is not enabled; save and enable it first.",
      nofile: ZH ? "没有收到文件。" : "No file was uploaded.",
      manifest: ZH ? "无效帧包：缺少或无法解析 manifest.json。" : "Invalid pack: missing or unreadable manifest.json.",
      badframe: ZH ? "无效帧包：存在不是 76×284 RGB565（43168 字节）的帧。" : "Invalid pack: a frame is not 76×284 RGB565 (43168 bytes).",
      badname: ZH ? "无效帧包：帧文件名不合法或重复。" : "Invalid pack: unsafe or duplicate frame filename.",
      toomany: ZH ? "帧数超过上限（300 帧）。" : "Too many frames (limit 300).",
      toobig: ZH ? "文件超过大小上限。" : "File exceeds the size limit.",
      unsafe: ZH ? "帧包包含不安全的路径，已拒绝。" : "The pack contains an unsafe path and was rejected.",
      install: ZH ? "写入帧目录失败；旧帧包已保留。" : "Could not write the frame directory; the old pack was kept.",
      cleared: ZH ? "当前帧包已移除。" : "Frame pack removed.",
      restored: ZH ? "已恢复原厂屏幕。" : "OEM screen restored."
    };
    if (map[key]) return map[key];
    if (key.indexOf("installed:") === 0) return key;
    return key;
  }

  function toast(message, kind) {
    var el = $("glanim-toast");
    if (!el) return;
    el.textContent = message;
    el.className = "gl-toast is-on" + (kind ? " is-" + kind : "");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.className = "gl-toast";
    }, 3600);
  }

  function setMsg(message, kind) {
    var el = $("glanim-msg");
    if (!el) return;
    el.textContent = message || "";
    el.className = "gl-msg" + (kind ? " is-" + kind : "");
  }

  function setDirty(value) {
    dirty = !!value;
    var bar = document.querySelector("#glanim-savebar .gl-save-state");
    if (bar) bar.className = "gl-save-state" + (dirty ? " is-dirty" : "");
    setText("glanim-save-text", dirty
      ? (ZH ? "有未保存的修改" : "Unsaved changes")
      : (ZH ? "所有修改已保存" : "All changes saved"));
  }

  function modeLabel(mode) {
    return MODE_LABEL[mode] || mode || "–";
  }


  function pixelWidth(text, scale) {
    return Math.max(0, String(text).length * 6 * scale - scale);
  }

  function drawPixelText(ctx, x, y, text, color, scale) {
    scale = Math.max(1, Math.min(4, Math.round(scale || 1)));
    ctx.fillStyle = color;
    var cx = Math.round(x);
    String(text).toUpperCase().split("").forEach(function (ch) {
      var cols = PIXEL_FONT[ch] || PIXEL_FONT[" "];
      for (var c = 0; c < 5; c++) {
        var bits = cols[c] || 0;
        for (var r = 0; r < 7; r++) {
          if ((bits >> r) & 1) {
            ctx.fillRect(cx + c * scale, Math.round(y) + r * scale, scale, scale);
          }
        }
      }
      cx += 6 * scale;
    });
    return cx;
  }

  function fmtSpeed(kbps) {
    var n = parseInt(kbps, 10) || 0;
    return n >= 1024 ? (n / 1024).toFixed(1) + "MB" : n + "KB";
  }

  function fetchStatus() {
    if (!URLS.status || STATUS_BUSY) return;
    STATUS_BUSY = true;
    fetch(URLS.status, { cache: "no-store", headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        STATUS = json || {};
        updateStatusUI();
        if (S.mode === "dashboard" || S.mode === "custom") drawPreview();
        if (S.mode === "custom") {
          drawCustomEditor();
          renderCustomPalette();
        }
      })
      .catch(function () {
        STATUS = { daemon: "0" };
        updateStatusUI();
      })
      .then(function () {
        STATUS_BUSY = false;
      });
  }

  function updateStatusUI() {
    var daemon = STATUS.daemon === "1";
    var error = STATUS.error || "";
    var live = $("gl-live");
    if (live) live.className = "gl-live" + (daemon ? " is-on" : "");
    setText("gl-live-text", daemon
      ? (ZH ? "面板在线" : "Panel online")
      : (STATUS.screen_pid ? (ZH ? "原厂屏幕运行中" : "OEM screen running") : (ZH ? "插件未运行" : "Plugin stopped")));

    setText("gl-pill-daemon", daemon ? (ZH ? "运行中" : "running") : (ZH ? "已停止" : "stopped"));
    setText("gl-pill-mode", daemon ? modeLabel(STATUS.mode) : modeLabel(S.mode));
    var frames = num(STATUS.frame_count, 0);
    if (frames > 0) {
      setText("gl-pill-frames", (num(STATUS.current, 0) + 1) + "/" + frames);
    } else {
      setText("gl-pill-frames", PACK.count > 0 ? String(PACK.count) : "–");
    }
    setText("gl-pill-bright", (STATUS.brightness || "–") + "/11");
    setText("gl-pill-state-v", daemon ? (ZH ? "插件" : "plugin")
      : (STATUS.screen_pid ? (ZH ? "原厂" : "OEM") : (ZH ? "未知" : "unknown")));

    var badge = $("glanim-preview-badge");
    if (badge) {
      badge.className = "gl-badge" + (error ? " bad" : (daemon ? " ok" : ""));
      badge.textContent = error ? (ZH ? "异常" : "error") : (daemon ? (ZH ? "实时" : "live") : (ZH ? "待机" : "idle"));
    }

    var caption = ZH ? "插件未运行" : "Plugin stopped";
    if (error) {
      caption = (ZH ? "错误：" : "Error: ") + error;
    } else if (daemon && STATUS.mode === "dashboard") {
      var pc = num(STATUS.page_count, 0);
      var page = PAGE_LABEL[STATUS.page] || STATUS.page || "–";
      caption = (ZH ? "系统面板 · " : "System panel · ") + page + (pc > 1 ? " (" + pc + ")" : "");
    } else if (daemon) {
      var fc = num(STATUS.frame_count, 0);
      caption = modeLabel(STATUS.mode) + (fc > 0 ? ((ZH ? " · 帧 " : " · frame ") + (num(STATUS.current, 0) + 1) + "/" + fc) : "");
    } else if (S.mode !== "dashboard" && PACK.count > 0) {
      caption = ZH ? "预览帧包 · 插件未运行" : "Pack preview · plugin stopped";
    }
    setText("glanim-preview-caption", caption);

    if (frames > 0) {
      setText("glanim-preview-count", (num(STATUS.current, 0) + 1) + "/" + frames);
    } else {
      setText("glanim-preview-count", S.mode === "custom" ? "" : (PACK.count > 0 ? (PACK.count + (ZH ? " 帧" : " frames")) : ""));
    }

    var empty = $("glanim-screen-empty");
    if (empty) {
      var showEmpty = S.mode !== "dashboard" && S.mode !== "custom" && PACK.count === 0;
      empty.className = "gl-screen-empty" + (showEmpty ? " is-on" : "");
    }

    var dash = daemon && STATUS.mode === "dashboard";
    setText("gl-kpi-cpu", dash ? (num(STATUS.cpu, 0) + "%") : "–");
    setText("gl-kpi-mem", dash ? (num(STATUS.mem, 0) + "%") : "–");
    setText("gl-kpi-temp", dash ? (num(STATUS.temp, 0) + "°C") : "–");
    setText("gl-kpi-net", dash
      ? ("↓ " + fmtSpeed(STATUS.rx_kbps) + "  ↑ " + fmtSpeed(STATUS.tx_kbps))
      : "–");

    var touch = $("glanim-touch-live");
    if (touch) {
      if (dash) {
        var present = STATUS.touch_present === "1";
        touch.textContent = (ZH ? "触屏" : "Touch") + " · "
          + (present ? (ZH ? "在线" : "online") : (ZH ? "未检测到" : "not found"))
          + " · raw " + (STATUS.touch_raw || "-")
          + " · " + (STATUS.touch_range || "-")
          + (STATUS.touch_gesture && STATUS.touch_gesture !== "none" ? " · " + STATUS.touch_gesture : "");
      } else {
        touch.textContent = ZH ? "触屏仅在系统面板模式下启用" : "Touch is active in system-panel mode only";
      }
    }

    var packBadge = $("glanim-pack-badge");
    if (packBadge && !PACK.valid) {
      packBadge.className = "gl-badge" + (PACK.count > 0 ? " warn" : "");
      packBadge.textContent = PACK.count > 0
        ? (ZH ? "帧包不完整" : "Pack incomplete")
        : (ZH ? "无帧包" : "No pack");
    }
  }

  /* ---------------- panel preview ---------------- */

  var pv = null;
  var pvCtx = null;
  var packFrames = [];
  var packIndex = 0;
  var packTimer = null;
  var packLoading = false;

  function previewCanvas() {
    if (!pv) {
      pv = $("glanim-preview-canvas");
      if (pv) pvCtx = pv.getContext("2d");
    }
    return pvCtx;
  }

  function drawPreview() {
    var ctx = previewCanvas();
    if (!ctx) return;
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, PANEL_W, PANEL_H);
    ctx.fillStyle = "#0a0c12";
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);

    if (S.mode === "dashboard") {
      drawDashboard(ctx);
      return;
    }
    if (S.mode === "custom") {
      drawCustomLayout(ctx, CUSTOM, dashData(), {});
      return;
    }
    if (PACK.count <= 0) {
      drawPanelText(ctx, ZH ? "NO FRAME PACK" : "NO FRAME PACK", ZH ? "UPLOAD IMAGE / PACK" : "UPLOAD IMAGE / PACK");
      return;
    }
    var cv = packFrames[packIndex] || packFrames[0];
    if (cv) {
      ctx.drawImage(cv, 0, 0, PANEL_W, PANEL_H);
    } else {
      drawPanelText(ctx, ZH ? "LOADING FRAMES" : "LOADING FRAMES", PACK.count + (ZH ? " FRAMES" : " FRAMES"));
    }
  }

  function drawPanelText(ctx, line1, line2) {
    ctx.fillStyle = "#0a0c12";
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);
    drawPixelText(ctx, (PANEL_W - pixelWidth(line1, 1)) / 2, 25, line1, "#c2ccdc", 1);
    drawPixelText(ctx, (PANEL_W - pixelWidth(line2, 1)) / 2, 42, line2, "#8e9bb0", 1);
  }

  function dashData() {
    var s = STATUS || {};
    var live = s.daemon === "1";
    var now = new Date();
    var clock = (live && typeof s.clock === "string") ? s.clock : "";
    var hm = clock.length >= 5 ? clock.substr(0, 5) : (pad2(now.getHours()) + ":" + pad2(now.getMinutes()));
    var sec = clock.length >= 8 ? clock.substr(6, 2) : pad2(now.getSeconds());
    return {
      hm: hm,
      sec: sec,
      clock: (live && clock) || (pad2(now.getHours()) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds())),
      date: (live && s.date) || (pad2(now.getMonth() + 1) + "/" + pad2(now.getDate())),
      weekday: (live && s.weekday) || WEEKDAYS[now.getDay()],
      uptime: (live && s.uptime) || "",
      ip: (live && (s.lan_ip || s.ip)) || "",
      lan_ip: (live && (s.lan_ip || s.ip)) || "",
      wan_ip: (live && s.wan_ip) || "",
      hostname: (live && s.hostname) || "",
      fan_rpm: live ? num(s.fan_rpm, 0) : 0,
      fan_pwm: live ? num(s.fan_pwm, 0) : 0,
      cpu: live ? num(s.cpu, 0) : 0,
      mem: live ? num(s.mem, 0) : 0,
      temp: live ? num(s.temp, 0) : 0,
      rx: live ? num(s.rx_kbps, 0) : 0,
      tx: live ? num(s.tx_kbps, 0) : 0,
      iface: (live && s.net_iface) || "",
      page: (live && s.page) || "status",
      page_count: live ? num(s.page_count, 0) : 0
    };
  }

  function defaultCustomLayout() {
    return {
      bg: "#0a0c12",
      elements: [
        { type: "text", x: 6, y: 4, size: 1, color: "#c2ccdc", text: "CPU" },
        { type: "bar", x: 36, y: 3, w: 150, h: 8, source: "cpu", color: "auto" },
        { type: "value", x: 192, y: 3, size: 1, color: "#eef2fa", source: "cpu", suffix: "%" },
        { type: "text", x: 6, y: 28, size: 1, color: "#c2ccdc", text: "MEM" },
        { type: "bar", x: 36, y: 27, w: 150, h: 8, source: "mem", color: "auto" },
        { type: "value", x: 192, y: 27, size: 1, color: "#eef2fa", source: "mem", suffix: "%" },
        { type: "text", x: 6, y: 52, size: 1, color: "#c2ccdc", text: "TMP" },
        { type: "bar", x: 36, y: 51, w: 150, h: 8, source: "temp", color: "auto" },
        { type: "value", x: 192, y: 51, size: 1, color: "#eef2fa", source: "temp", suffix: "C" },
        { type: "value", x: 232, y: 4, size: 1, color: "#eef2fa", source: "fan_rpm", suffix: " RPM" },
        { type: "value", x: 232, y: 28, size: 1, color: "#c2ccdc", source: "clock" },
        { type: "value", x: 232, y: 52, size: 1, color: "#c2ccdc", source: "date" }
      ]
    };
  }

  function hexColor(value, fallback) {
    if (typeof value !== "string" || !/^#[0-9a-fA-F]{6}$/.test(value)) return fallback;
    if (value.toLowerCase() === "#78849a") return "#c2ccdc";
    return value;
  }

  function customValue(source, d) {
    switch (source) {
      case "cpu": return String(d.cpu || 0);
      case "mem": return String(d.mem || 0);
      case "temp": return String(d.temp || 0);
      case "fan_rpm": return String(d.fan_rpm || 0);
      case "fan_pwm": return String(d.fan_pwm || 0);
      case "rx": return fmtSpeed(d.rx);
      case "tx": return fmtSpeed(d.tx);
      case "net": return "DL " + fmtSpeed(d.rx) + " UL " + fmtSpeed(d.tx);
      case "iface": return String(d.iface || "");
      case "ip":
      case "lan_ip": return String(d.lan_ip || d.ip || "");
      case "wan_ip": return String(d.wan_ip || "");
      case "hostname": return String(d.hostname || "");
      case "uptime": return String(d.uptime || "");
      case "clock": return String(d.clock || "");
      case "hm": return String(d.hm || "");
      case "date": return String(d.date || "");
      case "weekday": return String(d.weekday || "");
      default: return "";
    }
  }

  function customBarValue(source, d) {
    switch (source) {
      case "cpu": return clamp(d.cpu || 0, 0, 100);
      case "mem": return clamp(d.mem || 0, 0, 100);
      case "temp": return clamp(d.temp || 0, 0, 100);
      case "fan_pwm": return clamp(d.fan_pwm || 0, 0, 100);
      default: return 0;
    }
  }

  function customFont(size) {
    return "bold " + Math.max(7, Math.round(size * 7)) + "px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
  }

  function customElementText(el, d) {
    if (el.type === "text") return String(el.text || "").toUpperCase().slice(0, 64);
    if (el.type === "value" || el.type === "bar") {
      return (String(el.prefix || "") + customValue(el.source, d) + String(el.suffix || "")).slice(0, 64);
    }
    return "";
  }

  function customBox(ctx, el, d) {
    if (el.type === "bar") {
      return { x: el.x, y: el.y, w: Math.max(1, num(el.w, 120)), h: Math.max(1, num(el.h, 8)) };
    }
    if (el.type === "rect") {
      return { x: el.x, y: el.y, w: Math.max(1, num(el.w, 20)), h: Math.max(1, num(el.h, 2)) };
    }
    if (el.type === "line") {
      return { x: el.x, y: el.y, w: Math.max(1, num(el.w, 100)), h: 2 };
    }
    var text = customElementText(el, d);
    var size = clamp(num(el.size, 1), 1, 3);
    var w = pixelWidth(text, size);
    var h = size * 7 + 2;
    var x = el.x;
    if (el.align === "center") x -= w / 2;
    else if (el.align === "right") x -= w;
    return { x: x, y: el.y, w: Math.max(1, w), h: h };
  }

  function drawCustomLayout(ctx, layout, d, opts) {
    opts = opts || {};
    ctx.fillStyle = hexColor(layout.bg, "#0a0c12");
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);
    if (opts.grid) {
      ctx.strokeStyle = "rgba(110, 125, 255, 0.16)";
      ctx.lineWidth = 0.5;
      for (var gx = 0; gx <= PANEL_W; gx += 20) {
        ctx.beginPath();
        ctx.moveTo(gx + 0.5, 0);
        ctx.lineTo(gx + 0.5, PANEL_H);
        ctx.stroke();
      }
      for (var gy = 0; gy <= PANEL_H; gy += 20) {
        ctx.beginPath();
        ctx.moveTo(0, gy + 0.5);
        ctx.lineTo(PANEL_W, gy + 0.5);
        ctx.stroke();
      }
    }
    var elements = layout.elements || [];
    for (var i = 0; i < elements.length && i < 64; i++) {
      var el = elements[i];
      if (!el || ["text", "value", "bar", "rect", "line"].indexOf(el.type) < 0) continue;
      var color = hexColor(el.color, "#eef2fa");
      if (el.type === "text" || el.type === "value") {
        var text = customElementText(el, d);
        if (!text) continue;
        var size = clamp(num(el.size, 1), 1, 3);
        var tx = el.x;
        if (el.align === "center") tx -= pixelWidth(text, size) / 2;
        else if (el.align === "right") tx -= pixelWidth(text, size);
        drawPixelText(ctx, tx, el.y, text, color, size);
      } else if (el.type === "bar") {
        var w = clamp(num(el.w, 120), 1, PANEL_W);
        var h = clamp(num(el.h, 8), 1, PANEL_H);
        var pct = customBarValue(el.source, d);
        ctx.fillStyle = "#262a36";
        ctx.fillRect(el.x, el.y, w, h);
        ctx.fillStyle = color === "auto" || el.color === "auto"
          ? (el.source === "temp" ? tempColor(pct) : barColor(pct))
          : color;
        ctx.fillRect(el.x, el.y, Math.round(w * pct / 100), h);
        if (el.show_value) {
          var vt = customElementText(el, d);
          if (el.x + w + 4 + pixelWidth(vt, 1) <= PANEL_W) {
            drawPixelText(ctx, el.x + w + 4, el.y + 1, vt, "#eef2fa", 1);
          }
        }
      } else if (el.type === "rect") {
        ctx.fillStyle = color;
        ctx.fillRect(el.x, el.y, clamp(num(el.w, 20), 1, PANEL_W), clamp(num(el.h, 2), 1, PANEL_H));
      } else if (el.type === "line") {
        ctx.fillStyle = color;
        ctx.fillRect(el.x, el.y, clamp(num(el.w, 100), 1, PANEL_W), 1);
      }
    }
    if (opts.editor && opts.selected != null && opts.selected >= 0 && elements[opts.selected]) {
      var box = customBox(ctx, elements[opts.selected], d);
      ctx.strokeStyle = "#8b5cf6";
      ctx.lineWidth = 1;
      ctx.strokeRect(box.x - 1, box.y - 1, box.w + 2, box.h + 2);
      ctx.fillStyle = "rgba(139, 92, 246, 0.18)";
      ctx.fillRect(box.x - 1, box.y - 1, box.w + 2, box.h + 2);
    }
  }

  function drawDashboard(ctx) {
    var clockOn = S.showTime;
    var statusOn = S.showCpu || S.showMem || S.showTemp || S.showNet;
    var page = previewPage;
    if (page !== "clock" && page !== "status") {
      page = (STATUS && STATUS.page) || (clockOn ? "clock" : "status");
    }
    if (page === "clock" && !clockOn) page = "status";
    if (page === "status" && !statusOn) page = "clock";
    var d = dashData();
    if (page === "clock") {
      drawClockPage(ctx, d);
    } else {
      drawStatusPage(ctx, d);
    }
  }

  function drawClockPage(ctx, d) {
    ctx.fillStyle = "#0a0c12";
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);

    drawPixelText(ctx, 8, 6, d.date + " " + d.weekday, "#c2ccdc", 1);
    if (S.showUptime && d.uptime) {
      var ut = "UP " + d.uptime;
      drawPixelText(ctx, PANEL_W - 8 - pixelWidth(ut, 1), 6, ut, "#c2ccdc", 1);
    }

    var big = 3;
    var bw = pixelWidth(d.hm, big);
    var bx = (PANEL_W - bw) / 2;
    drawPixelText(ctx, bx, 22, d.hm, "#f4f7ff", big);
    drawPixelText(ctx, bx + bw + 6, 34, d.sec, "#c2ccdc", 1);

    if (S.showIp && d.ip) {
      drawPixelText(ctx, (PANEL_W - pixelWidth(d.ip, 1)) / 2, 60, d.ip, "#b9c4d8", 1);
    }
  }

  function barColor(pct) {
    if (pct >= 80) return "#e64646";
    if (pct >= 55) return "#f0be3c";
    return "#3cd26e";
  }

  function tempColor(t) {
    if (t >= 70) return "#e64646";
    if (t >= 50) return "#f0be3c";
    return "#3cd26e";
  }

  function drawBar(ctx, x, y, w, h, pct, color) {
    pct = clamp(pct, 0, 100);
    ctx.fillStyle = "#262a36";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = color;
    ctx.fillRect(x, y, Math.round(w * pct / 100), h);
  }

  function drawStatusPage(ctx, d) {
    ctx.fillStyle = "#0a0c12";
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);
    drawPixelText(ctx, 8, 5, "STATUS", "#9fb0c8", 1);
    if (d.iface) {
      var iface = d.iface.toUpperCase();
      drawPixelText(ctx, PANEL_W - 8 - pixelWidth(iface, 1), 5, iface, "#9fb0c8", 1);
    }

    var rows = [];
    if (S.showCpu) rows.push({ label: "CPU", pct: d.cpu, text: d.cpu + "%", color: barColor(d.cpu) });
    if (S.showMem) rows.push({ label: "MEM", pct: d.mem, text: d.mem + "%", color: barColor(d.mem) });
    if (S.showTemp) rows.push({ label: "TMP", pct: clamp(d.temp, 0, 100), text: d.temp + "C", color: tempColor(d.temp) });
    rows = rows.slice(0, 3);

    var y = 18;
    rows.forEach(function (row) {
      drawPixelText(ctx, 8, y, row.label, "#c2ccdc", 1);
      drawBar(ctx, 42, y, 154, 8, row.pct, row.color);
      var tw = pixelWidth(row.text, 1);
      drawPixelText(ctx, PANEL_W - 8 - tw, y, row.text, "#f4f7ff", 1);
      y += 16;
    });

    if (S.showNet) {
      drawPixelText(ctx, 8, 62, "DL " + fmtSpeed(d.rx) + "  UL " + fmtSpeed(d.tx), "#f4f7ff", 1);
    }
    if (S.showIp && d.ip) {
      drawPixelText(ctx, PANEL_W - 8 - pixelWidth(d.ip, 1), 62, d.ip, "#b9c4d8", 1);
    }
  }

  /* ---------------- pack frame preview ---------------- */

  function loadPackFrames() {
    if (packLoading || PACK.count <= 0) return;
    packLoading = true;
    var max = Math.min(PACK.count, 60);
    var i = 0;
    function next() {
      if (i >= max) {
        packLoading = false;
        startPackTimer();
        drawPreview();
        return;
      }
      var url = withQuery(URLS.frame, "i", i);
      fetch(url, { cache: "no-store" })
        .then(function (r) {
          if (!r.ok) throw new Error("frame " + i);
          return r.arrayBuffer();
        })
        .then(function (buffer) {
          packFrames[i] = decodeFrame(buffer);
        })
        .catch(function () {
          packFrames[i] = null;
        })
        .then(function () {
          i += 1;
          if (i === 1 && S.mode !== "dashboard") drawPreview();
          next();
        });
    }
    next();
  }

  function decodeFrame(buffer) {
    var bytes = new Uint8Array(buffer);
    var cv = document.createElement("canvas");
    cv.width = PANEL_W;
    cv.height = PANEL_H;
    var ctx = cv.getContext("2d");
    var img = ctx.createImageData(PANEL_W, PANEL_H);
    var data = img.data;
    for (var yf = 0; yf < 284; yf++) {
      for (var xf = 0; xf < 76; xf++) {
        var bi = (yf * 76 + xf) * 2;
        if (bi + 1 >= bytes.length) continue;
        var c = bytes[bi] | (bytes[bi + 1] << 8);
        var r = (c >> 11) & 0x1f;
        var g = (c >> 5) & 0x3f;
        var b = c & 0x1f;
        var px = 283 - yf;
        var py = xf;
        var pi = (py * PANEL_W + px) * 4;
        data[pi] = Math.round(r * 255 / 31);
        data[pi + 1] = Math.round(g * 255 / 63);
        data[pi + 2] = Math.round(b * 255 / 31);
        data[pi + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return cv;
  }

  function packDelay(index) {
    if (S.fps > 0) return clamp(Math.round(1000 / S.fps), 30, 1000);
    var d = num(PACK.delays && PACK.delays[index], 100);
    return clamp(d, 30, 1000);
  }

  function startPackTimer() {
    if (packTimer) {
      clearTimeout(packTimer);
      packTimer = null;
    }
    if (S.mode === "dashboard" || S.mode === "still" || S.mode === "custom") return;
    var total = Math.max(0, packFrames.length);
    var loaded = packFrames.filter(function (x) { return !!x; }).length;
    if (total < 2 || loaded < 2) return;
    packTimer = setTimeout(function () {
      var next = packIndex + 1;
      if (next >= total) {
        if (S.mode === "slideshow" || !S.loop) {
          packIndex = Math.max(0, total - 1);
          drawPreview();
          return;
        }
        next = 0;
      }
      packIndex = next;
      drawPreview();
      startPackTimer();
    }, packDelay(packIndex));
  }

  function resetPreviewAnimation() {
    if (packTimer) {
      clearTimeout(packTimer);
      packTimer = null;
    }
    packIndex = 0;
    if (S.mode === "dashboard" || S.mode === "custom") {
      drawPreview();
      return;
    }
    if (!packFrames.length && PACK.count > 0) loadPackFrames();
    drawPreview();
    startPackTimer();
  }

  /* ---------------- form sync / save ---------------- */

  function syncForm() {
    var el;
    el = $("gl-enabled"); if (el) el.checked = S.enabled;
    el = $("gl-brightness"); if (el) el.value = S.brightness;
    setText("gl-brightness-val", String(S.brightness));

    el = $("gl-loop"); if (el) el.checked = S.loop;
    el = $("gl-fps"); if (el) el.value = S.fps;
    setText("gl-fps-val", S.fps === 0 ? (ZH ? "原生" : "native") : (S.fps + " fps"));
    el = $("gl-dash-interval"); if (el) el.value = S.interval;
    setText("gl-dash-interval-val", S.interval + "s");

    el = $("gl-show-time"); if (el) el.checked = S.showTime;
    el = $("gl-show-cpu"); if (el) el.checked = S.showCpu;
    el = $("gl-show-mem"); if (el) el.checked = S.showMem;
    el = $("gl-show-temp"); if (el) el.checked = S.showTemp;
    el = $("gl-show-net"); if (el) el.checked = S.showNet;
    el = $("gl-show-uptime"); if (el) el.checked = S.showUptime;
    el = $("gl-show-ip"); if (el) el.checked = S.showIp;

    el = $("gl-touch-enable"); if (el) el.checked = S.touchEnable;
    el = $("gl-touch-action"); if (el) el.value = S.touchAction;
    el = $("gl-touch-swap"); if (el) el.checked = S.touchSwap;
    el = $("gl-touch-flip"); if (el) el.checked = S.touchFlip;
    el = $("gl-keep-original"); if (el) el.checked = S.keepOriginal;
    el = $("glanim-frames-dir"); if (el) el.value = S.framesDir;

    var cards = document.querySelectorAll("#gl-mode-grid .gl-mode");
    Array.prototype.forEach.call(cards, function (card) {
      var active = card.getAttribute("data-mode") === S.mode;
      card.className = "gl-mode" + (active ? " is-active" : "");
      card.setAttribute("aria-checked", active ? "true" : "false");
    });

    syncPanels();
    updatePreviewTabs();
  }

  function syncPanels() {
    var dash = $("glanim-panel-dashboard");
    var play = $("glanim-panel-playback");
    var custom = $("glanim-panel-custom");
    if (dash) dash.style.display = S.mode === "dashboard" ? "" : "none";
    if (play) play.style.display = (S.mode === "dashboard" || S.mode === "custom") ? "none" : "";
    if (custom) custom.style.display = S.mode === "custom" ? "" : "none";
    if (S.mode === "custom") {
      drawCustomEditor();
      renderCustomPalette();
      renderCustomInspector();
    }
  }

  function updatePreviewTabs() {
    var tabs = $("glanim-preview-tabs");
    if (!tabs) return;
    var clockOn = S.mode === "dashboard" && S.showTime;
    var statusOn = S.mode === "dashboard" && (S.showCpu || S.showMem || S.showTemp || S.showNet);
    var show = clockOn && statusOn;
    tabs.hidden = !show;
    if (!show) return;
    if (previewPage !== "clock" && previewPage !== "status") {
      previewPage = (STATUS && STATUS.page) || "clock";
    }
    Array.prototype.forEach.call(tabs.querySelectorAll("button"), function (b) {
      b.className = b.getAttribute("data-page") === previewPage ? "is-active" : "";
    });
  }

  function collect() {
    return {
      enabled: S.enabled ? "1" : "0",
      mode: S.mode,
      fps: String(S.fps),
      loop: S.loop ? "1" : "0",
      brightness: String(S.brightness),
      keep_original: S.keepOriginal ? "1" : "0",
      frames_dir: S.framesDir,
      show_time: S.showTime ? "1" : "0",
      show_cpu: S.showCpu ? "1" : "0",
      show_mem: S.showMem ? "1" : "0",
      show_temp: S.showTemp ? "1" : "0",
      show_net: S.showNet ? "1" : "0",
      show_uptime: S.showUptime ? "1" : "0",
      show_ip: S.showIp ? "1" : "0",
      dash_interval: String(S.interval),
      touch_enable: S.touchEnable ? "1" : "0",
      touch_action: S.touchAction,
      touch_swap_xy: S.touchSwap ? "1" : "0",
      touch_flip_x: S.touchFlip ? "1" : "0",
      custom_layout: JSON.stringify(CUSTOM)
    };
  }

  function validate() {
    if (!/^\/[A-Za-z0-9._\/-]+$/.test(S.framesDir) || S.framesDir.indexOf("..") >= 0) {
      toast(ZH ? "帧目录必须是绝对路径，且不能包含 .." : "Frame directory must be an absolute, safe path", "error");
      return false;
    }
    if (S.enabled && S.mode === "dashboard"
      && !S.showTime && !S.showCpu && !S.showMem && !S.showTemp && !S.showNet) {
      toast(ZH ? "系统面板至少勾选一个显示项" : "Select at least one dashboard item", "error");
      return false;
    }
    if (S.mode === "custom" && (!CUSTOM.elements || CUSTOM.elements.length === 0)) {
      toast(ZH ? "自定义面板至少需要一个元素" : "Add at least one element to the custom panel", "error");
      return false;
    }
    if (S.enabled && (S.mode === "gif" || S.mode === "still" || S.mode === "slideshow") && PACK.count <= 0) {
      toast(ZH ? "请先上传帧包，再启用该播放模式" : "Upload a frame pack before enabling this mode", "error");
      return false;
    }
    if ((S.mode === "gif" || S.mode === "still" || S.mode === "slideshow") && PACK.count > 0 && PACK.missing > 0) {
      toast(ZH ? "当前帧包不完整，请重新上传" : "The current pack is incomplete; upload it again", "error");
      return false;
    }
    return true;
  }

  function setSaving(value) {
    saving = value;
    var save = $("glanim-save");
    var revert = $("glanim-revert");
    if (save) {
      save.disabled = value;
      save.innerHTML = (value ? (ZH ? "保存中…" : "Saving…") : (ZH ? "保存并应用" : "Save & Apply"));
    }
    if (revert) revert.disabled = value;
  }

  function save() {
    if (saving) return;
    if (!validate()) return;
    setSaving(true);
    api(URLS.save, { method: "POST", body: formBody(collect()) })
      .then(function (data) {
        LAST = clone(S);
        LAST_CUSTOM = clone(CUSTOM);
        setDirty(false);
        toast(ZH ? "已保存并应用" : "Saved and applied", "ok");
        setTimeout(fetchStatus, 900);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "保存失败" : "Save failed"), "error");
      })
      .then(function () {
        setSaving(false);
      });
  }

  /* ---------------- image studio ---------------- */

  var studio = {
    frames: [],
    cur: 0,
    fit: "cover",
    zoom: 1,
    offX: 0,
    offY: 0,
    dragging: false,
    dpx: 0,
    dpy: 0,
    file: null,
    timer: null,
    playing: false
  };
  var stage = null;
  var sctx = null;
  var prev = null;
  var pctx = null;

  function studioEls() {
    if (!stage) {
      stage = $("glanim-stage");
      if (stage) sctx = stage.getContext("2d");
    }
    if (!prev) {
      prev = $("glanim-preview");
      if (prev) pctx = prev.getContext("2d");
    }
  }

  function currentFrame() {
    return studio.frames.length ? studio.frames[studio.cur] : null;
  }

  function layoutTarget(canvas, W, H) {
    var sw = canvas.width, sh = canvas.height;
    var s = studio.fit === "stretch" ? 1 : (studio.fit === "cover"
      ? Math.max(W / sw, H / sh) : Math.min(W / sw, H / sh));
    s *= studio.zoom;
    return { dw: sw * s, dh: sh * s, sw: sw, sh: sh };
  }

  function drawCanvasToStage(canvas) {
    if (!sctx) return;
    sctx.clearRect(0, 0, STAGE_W, STAGE_H);
    sctx.fillStyle = "#0d1017";
    sctx.fillRect(0, 0, STAGE_W, STAGE_H);
    var r = layoutTarget(canvas, STAGE_W, STAGE_H);
    sctx.imageSmoothingEnabled = true;
    sctx.drawImage(canvas, (STAGE_W - r.dw) / 2 + studio.offX, (STAGE_H - r.dh) / 2 + studio.offY, r.dw, r.dh);
  }

  function drawCanvasToPreview(canvas) {
    if (!pctx) return;
    pctx.fillStyle = "#000";
    pctx.fillRect(0, 0, PANEL_W, PANEL_H);
    var r = layoutTarget(canvas, PANEL_W, PANEL_H);
    var ox = (PANEL_W - r.dw) / 2 + studio.offX * (PANEL_W / STAGE_W);
    var oy = (PANEL_H - r.dh) / 2 + studio.offY * (PANEL_H / STAGE_H);
    pctx.imageSmoothingEnabled = true;
    pctx.drawImage(canvas, ox, oy, r.dw, r.dh);
  }

  function placeStudio() {
    studioEls();
    var fr = currentFrame();
    var empty = $("glanim-stage-empty");
    if (empty) empty.className = "gl-stage-empty" + (fr ? " is-off" : "");
    if (!fr) {
      if (sctx) {
        sctx.fillStyle = "#0d1017";
        sctx.fillRect(0, 0, STAGE_W, STAGE_H);
      }
      if (pctx) {
        pctx.fillStyle = "#000";
        pctx.fillRect(0, 0, PANEL_W, PANEL_H);
      }
      return;
    }
    drawCanvasToStage(fr.canvas);
    drawCanvasToPreview(fr.canvas);
  }

  function updateStudioUI() {
    var n = studio.frames.length;
    var info = $("glanim-frame-info");
    if (info) {
      if (!n) {
        info.textContent = ZH ? "未选择图片" : "No image selected";
      } else {
        var avg = 0;
        studio.frames.forEach(function (f) { avg += f.delay || 0; });
        avg = Math.round(avg / n);
        info.textContent = n + (ZH ? " 帧" : " frames") + " · " + avg + "ms";
      }
    }
    var scrubWrap = $("glanim-scrub-wrap");
    var scrub = $("glanim-scrub");
    if (scrubWrap && scrub) {
      scrubWrap.hidden = n <= 1;
      scrub.max = String(Math.max(1, n));
      scrub.value = String(studio.cur + 1);
      setText("glanim-scrub-val", (studio.cur + 1) + "/" + Math.max(1, n));
    }
    var play = $("glanim-play");
    if (play) {
      play.style.display = n > 1 ? "" : "none";
      play.textContent = studio.playing ? (ZH ? "暂停" : "Pause") : (ZH ? "播放" : "Play");
    }
    var name = $("glanim-file-name");
    if (name) name.textContent = studio.file ? studio.file.name : "";
    placeStudio();
  }

  function stopStudioPlay() {
    studio.playing = false;
    if (studio.timer) {
      clearTimeout(studio.timer);
      studio.timer = null;
    }
    var play = $("glanim-play");
    if (play) play.textContent = ZH ? "播放" : "Play";
  }

  function startStudioPlay() {
    if (studio.frames.length < 2) return;
    stopStudioPlay();
    studio.playing = true;
    var play = $("glanim-play");
    if (play) play.textContent = ZH ? "暂停" : "Pause";
    var tick = function () {
      if (!studio.playing) return;
      studio.cur = (studio.cur + 1) % studio.frames.length;
      updateStudioUI();
      studio.timer = setTimeout(tick, clamp(studio.frames[studio.cur].delay || 100, 30, 1000));
    };
    studio.timer = setTimeout(tick, clamp(studio.frames[studio.cur].delay || 100, 30, 1000));
  }

  function resetTransform() {
    studio.offX = 0;
    studio.offY = 0;
    studio.zoom = 1;
    var zoom = $("glanim-zoom");
    if (zoom) zoom.value = "1";
    setText("glanim-zoom-val", "1.00×");
  }

  function handleImageFile(file) {
    if (!file) return;
    studio.file = file;
    studio.frames = [];
    studio.cur = 0;
    stopStudioPlay();
    resetTransform();
    setMsg("");
    updateStudioUI();

    var fname = String(file.name || "");
    var isVideo = file.type.indexOf("video/") === 0 || /\.(mp4|webm|mov|m4v)($|\?)/i.test(fname);
    if (isVideo) {
      loadVideo(file);
      return;
    }
    var isGif = file.type === "image/gif" || /\.gif($|\?)/i.test(fname);
    if (isGif) {
      setMsg(ZH ? "正在解析 GIF…" : "Decoding GIF…");
      file.arrayBuffer().then(function (buffer) {
        var decoded = decodeGIF(buffer);
        studio.frames = decoded.frames;
        studio.cur = 0;
        if (decoded.limited) {
          setMsg((ZH ? "GIF 共 " : "GIF has ") + decoded.total
            + (ZH ? " 帧，已保留前 " : " frames; kept the first ")
            + decoded.frames.length
            + (ZH ? " 帧（受浏览器内存上限保护）。长动画建议用 PC 帧包通道。" : " frames (browser memory guard). Use the PC frame-pack channel for long animations."), "");
        } else {
          setMsg("");
        }
        updateStudioUI();
        if (studio.frames.length > 1) startStudioPlay();
      }).catch(function () {
        setMsg(ZH ? "GIF 解析失败" : "GIF decode failed", "error");
      });
      return;
    }

    var img = new Image();
    var url = URL.createObjectURL(file);
    img.onload = function () {
      var maxSide = 1800;
      var scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
      var cv = document.createElement("canvas");
      cv.width = Math.max(1, Math.round(img.naturalWidth * scale));
      cv.height = Math.max(1, Math.round(img.naturalHeight * scale));
      cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
      URL.revokeObjectURL(url);
      studio.frames = [{ canvas: cv, delay: 500 }];
      studio.cur = 0;
      updateStudioUI();
    };
    img.onerror = function () {
      URL.revokeObjectURL(url);
      setMsg(ZH ? "图片解析失败" : "Image decode failed", "error");
    };
    img.src = url;
  }

  function loadVideo(file) {
    var video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    var url = URL.createObjectURL(file);
    var done = false;

    function fail(msg) {
      if (done) return;
      done = true;
      URL.revokeObjectURL(url);
      setMsg(msg, "error");
    }

    video.onerror = function () {
      fail(ZH ? "视频解码失败，请换 MP4(H.264) 或 WebM" : "Video decode failed; try MP4(H.264) or WebM");
    };

    video.onloadedmetadata = function () {
      var duration = Number(video.duration);
      if (!isFinite(duration) || duration <= 0) {
        fail(ZH ? "无法读取视频时长" : "Cannot read video duration");
        return;
      }
      var useDur = Math.min(duration, MAX_VIDEO_SECONDS);
      var fps = VIDEO_FPS;
      var count = Math.max(1, Math.min(MAX_VIDEO_FRAMES, Math.min(MAX_FRAMES, Math.round(useDur * fps))));
      var step = useDur / count;
      var canvas = document.createElement("canvas");
      canvas.width = PANEL_W;
      canvas.height = PANEL_H;
      var ctx = canvas.getContext("2d");
      var frames = [];
      var i = 0;

      function nextFrame() {
        if (i >= count) {
          done = true;
          URL.revokeObjectURL(url);
          studio.frames = frames;
          studio.cur = 0;
          updateStudioUI();
          if (frames.length > 1) startStudioPlay();
          setMsg((ZH ? "视频已解析 " : "Video decoded: ") + frames.length
            + (ZH ? " 帧，可应用为屏幕或背景" : " frames; apply to screen or background"), "ok");
          return;
        }
        var t = Math.min(useDur - 0.001, i * step);
        var handled = false;
        var onSeek = function () {
          if (handled) return;
          handled = true;
          try {
            var sw = video.videoWidth || PANEL_W;
            var sh = video.videoHeight || PANEL_H;
            var scale = Math.max(PANEL_W / sw, PANEL_H / sh);
            var dw = sw * scale;
            var dh = sh * scale;
            ctx.fillStyle = "#000";
            ctx.fillRect(0, 0, PANEL_W, PANEL_H);
            ctx.imageSmoothingEnabled = true;
            ctx.drawImage(video, (PANEL_W - dw) / 2, (PANEL_H - dh) / 2, dw, dh);
            var fc = document.createElement("canvas");
            fc.width = PANEL_W;
            fc.height = PANEL_H;
            fc.getContext("2d").drawImage(canvas, 0, 0);
            frames.push({ canvas: fc, delay: clamp(Math.round(step * 1000), 30, 1000) });
          } catch (e) {
            fail((ZH ? "视频取帧失败：" : "Video frame failed: ") + (e.message || e));
            return;
          }
          i++;
          if (i === 1 || i % 10 === 0 || i === count) {
            setMsg((ZH ? "视频取帧 " : "Video frames ") + i + " / " + count + " …", "");
          }
          setTimeout(nextFrame, 0);
        };
        video.addEventListener("seeked", onSeek, { once: true });
        video.currentTime = t;
        // Some browsers do not emit seeked when the position is unchanged.
        setTimeout(function () { if (!handled) onSeek(); }, 700);
      }

      setMsg((ZH ? "视频取帧 0 / " : "Video frames 0 / ") + count + " …", "");
      nextFrame();
    };

    video.src = url;
    video.load();
  }

  function encodeFrame(canvas) {
    drawCanvasToPreview(canvas);
    var data = pctx.getImageData(0, 0, PANEL_W, PANEL_H).data;
    var frame = new Uint8Array(76 * 284 * 2);
    for (var yf = 0; yf < 284; yf++) {
      for (var xf = 0; xf < 76; xf++) {
        var px = 283 - yf;
        var py = xf;
        var pi = (py * PANEL_W + px) * 4;
        var r = data[pi], g = data[pi + 1], b = data[pi + 2];
        var c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
        var bi = (yf * 76 + xf) * 2;
        frame[bi] = c & 255;
        frame[bi + 1] = (c >> 8) & 255;
      }
    }
    return frame;
  }

  function loadUrl() {
    var input = $("glanim-url");
    if (!input) return;
    var raw = String(input.value || "").trim();
    if (!/^https?:\/\//i.test(raw)) {
      setMsg(ZH ? "请输入 http(s) 链接" : "Enter an http(s) URL", "error");
      return;
    }
    var shot = $("glanim-url-shot");
    var target = raw;
    if (shot && shot.checked) {
      target = "https://s0.wp.com/mshots/v1/" + encodeURIComponent(raw) + "?w=568&h=152";
    }
    if (!URLS.fetchUrl) {
      setMsg(ZH ? "后端缺少 URL 代理接口" : "URL proxy endpoint is missing", "error");
      return;
    }
    setMsg(ZH ? "正在通过路由器下载…" : "Downloading through the router…");
    fetch(URLS.fetchUrl + "?url=" + encodeURIComponent(target), { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.blob();
      })
      .then(function (blob) {
        var name = raw.split("?")[0].split("/").pop() || "url-image";
        if (shot && shot.checked) name = "webpage-shot.jpg";
        var type = blob.type && blob.type.indexOf("image/") === 0 ? blob.type : "";
        if (!type) {
          if (/\.gif$/i.test(name)) type = "image/gif";
          else if (/\.png$/i.test(name)) type = "image/png";
          else if (/\.bmp$/i.test(name)) type = "image/bmp";
          else type = "image/jpeg";
        }
        var file = new File([blob], name, { type: type });
        handleImageFile(file);
        setMsg(ZH ? "URL 已载入，可裁剪后应用" : "URL loaded; crop and apply", "ok");
      })
      .catch(function (err) {
        setMsg((ZH ? "URL 载入失败：" : "URL load failed: ") + (err.message || ""), "error");
      });
  }

  function applyBackground() {
    applyImage("bg");
  }

  function applyImage(target) {
    target = target === "bg" ? "bg" : "screen";
    if (!studio.frames.length) {
      setMsg(ZH ? "请先选择一张图片" : "Choose an image first", "error");
      return;
    }
    var btn = $(target === "bg" ? "glanim-apply-bg" : "glanim-apply");
    if (btn) btn.disabled = true;
    setMsg(ZH ? "正在编码并上传…" : "Encoding and uploading…");
    try {
      var manifest = {
        source: studio.file ? studio.file.name : "browser upload",
        orientation: "fb90m",
        frames: []
      };
      var fd = new FormData();
      fd.append("token", token());
      studio.frames.forEach(function (fr, i) {
        var buffer = encodeFrame(fr.canvas);
        manifest.frames.push({
          file: "frame_" + ("000" + (i + 1)).slice(-4) + ".rgb565",
          delay_ms: clamp(fr.delay || 100, 30, 1000)
        });
        fd.append("framefile_" + (i + 1), new Blob([buffer], { type: "application/octet-stream" }), "frame.rgb565");
      });
      fd.append("manifest", JSON.stringify(manifest));
      fd.append("target", target);
      if (target === "bg") fd.append("fps", "8");
      api(URLS.uploadImage, { method: "POST", body: fd })
        .then(function (data) {
          setMsg(ZH ? "上传成功，正在刷新…" : "Uploaded; refreshing…", "ok");
          toast(ZH ? "图片已写入帧包" : "Image written to the frame pack", "ok");
          dirty = false;
          dirty = false;
          setTimeout(function () { window.location.reload(); }, 900);
        })
        .catch(function (err) {
          setMsg(err.message || (ZH ? "上传失败" : "Upload failed"), "error");
          if (btn) btn.disabled = false;
        });
    } catch (e) {
      setMsg((ZH ? "编码失败：" : "Encoding failed: ") + (e.message || e), "error");
      if (btn) btn.disabled = false;
    }
  }

  /* ---------------- pack upload / service actions ---------------- */

  function uploadPack(file) {
    if (!file) return;
    var fd = new FormData();
    fd.append("packfile", file);
    fd.append("token", token());
    setMsg(ZH ? "正在上传帧包…" : "Uploading frame pack…");
    api(URLS.uploadPack, { method: "POST", body: fd })
      .then(function () {
        toast(ZH ? "帧包已安装，正在刷新…" : "Pack installed; refreshing…", "ok");
        dirty = false;
          setTimeout(function () { window.location.reload(); }, 900);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "帧包上传失败" : "Pack upload failed"), "error");
        if (fileInput()) fileInput().value = "";
      });
  }

  function fileInput() {
    return $("glanim-pack-file");
  }

  function clearPack() {
    if (!window.confirm(ZH ? "确定移除当前帧包并交回原厂屏幕？" : "Remove the current pack and restore the OEM screen?")) return;
    api(URLS.clear, { method: "POST", body: formBody({}) })
      .then(function () {
        toast(ZH ? "帧包已移除" : "Pack removed", "ok");
        dirty = false;
          setTimeout(function () { window.location.reload(); }, 700);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "移除失败" : "Remove failed"), "error");
      });
  }

  function restartService() {
    api(URLS.apply, { method: "POST", body: formBody({}) })
      .then(function () {
        toast(ZH ? "服务已重启" : "Service restarted", "ok");
        setTimeout(fetchStatus, 900);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "重启失败" : "Restart failed"), "error");
      });
  }

  function restoreOem() {
    if (!window.confirm(ZH ? "确定停用插件并恢复原厂屏幕？" : "Disable the plugin and restore the OEM screen?")) return;
    api(URLS.restore, { method: "POST", body: formBody({}) })
      .then(function () {
        toast(ZH ? "已恢复原厂屏幕" : "OEM screen restored", "ok");
        dirty = false;
          setTimeout(function () { window.location.reload(); }, 800);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "恢复失败" : "Restore failed"), "error");
      });
  }

  /* ---------------- GIF decoder ---------------- */

  function u16b(b, o) {
    return b[o] | (b[o + 1] << 8);
  }

  function parseGIF(ab) {
    var bytes = new Uint8Array(ab);
    if (bytes.length < 13 || bytes[0] !== 0x47 || bytes[1] !== 0x49 || bytes[2] !== 0x46) {
      throw new Error("not a GIF");
    }
    var width = u16b(bytes, 6), height = u16b(bytes, 8), packed = bytes[10];
    var gctFlag = (packed >> 7) & 1, gctSize = gctFlag ? 3 << ((packed & 7) + 1) : 0;
    var gct = [], p = 13;
    for (var i = 0; i < gctSize / 3; i++) {
      gct.push([bytes[p + i * 3], bytes[p + i * 3 + 1], bytes[p + i * 3 + 2]]);
    }
    p += gctSize;
    var frames = [], pendingGce = null;

    function skipSubBlocks() {
      var size = bytes[p];
      while (size !== 0 && p < bytes.length) {
        p += size + 1;
        size = bytes[p];
      }
      p += 1;
    }

    while (p < bytes.length) {
      var marker = bytes[p];
      if (marker === 0x3B) break;
      if (marker === 0x21) {
        p++;
        var label = bytes[p];
        p++;
        if (label === 0xF9) {
          var size = bytes[p];
          var gcePacked = bytes[p + 1];
          var delay = u16b(bytes, p + 2);
          var transparentIndex = bytes[p + 4];
          pendingGce = {
            delay: delay,
            disposal: (gcePacked >> 2) & 7,
            transparentIndex: (gcePacked & 1) ? transparentIndex : null
          };
          p += size + 2;
        } else {
          skipSubBlocks();
        }
      } else if (marker === 0x2C) {
        p++;
        var left = u16b(bytes, p), top = u16b(bytes, p + 2);
        var iw = u16b(bytes, p + 4), ih = u16b(bytes, p + 6), ipacked = bytes[p + 8];
        var lctFlag = (ipacked >> 7) & 1, inter = (ipacked >> 6) & 1;
        var lctSize = lctFlag ? 3 << ((ipacked & 7) + 1) : 0;
        p += 9;
        var lct = [];
        for (var j = 0; j < lctSize / 3; j++) {
          lct.push([bytes[p + j * 3], bytes[p + j * 3 + 1], bytes[p + j * 3 + 2]]);
        }
        p += lctSize;
        var minCode = bytes[p];
        p++;
        var blocks = [], size2 = bytes[p];
        while (size2 !== 0 && p < bytes.length) {
          blocks.push(bytes.slice(p + 1, p + 1 + size2));
          p += size2 + 1;
          size2 = bytes[p];
        }
        p += 1;
        frames.push({
          gce: pendingGce,
          image: {
            left: left, top: top, width: iw, height: ih,
            interlaced: inter, lct: lct, minCodeSize: minCode, blocks: blocks
          }
        });
        pendingGce = null;
      } else {
        break;
      }
    }
    return { width: width, height: height, gct: gct, frames: frames };
  }

  function lzwDecode(minCodeSize, data, pixelCount) {
    var MAX = 4096;
    var dataSize = minCodeSize;
    var clear = 1 << dataSize;
    var eoi = clear + 1;
    var available = clear + 2;
    var oldCode = -1;
    var codeSize = dataSize + 1;
    var codeMask = (1 << codeSize) - 1;
    var prefix = new Array(MAX), suffix = new Array(MAX);
    for (var c = 0; c < clear; c++) {
      prefix[c] = 0;
      suffix[c] = c;
    }
    var dst = new Array(pixelCount), stack = new Array(MAX + 1);
    var datum = 0, bits = 0, first = 0, top = 0, pi = 0, bi = 0;
    for (var i = 0; i < pixelCount; ) {
      if (top === 0) {
        if (bi >= data.length) break;
        if (bits < codeSize) {
          datum += data[bi] << bits;
          bits += 8;
          bi++;
          continue;
        }
        var code = datum & codeMask;
        datum >>= codeSize;
        bits -= codeSize;
        if (code > available || code === eoi) break;
        if (code === clear) {
          codeSize = dataSize + 1;
          codeMask = (1 << codeSize) - 1;
          available = clear + 2;
          oldCode = -1;
          continue;
        }
        if (oldCode === -1) {
          stack[top++] = suffix[code];
          oldCode = code;
          first = code;
          continue;
        }
        var inCode = code;
        if (code === available) {
          stack[top++] = first;
          code = oldCode;
        }
        while (code > clear) {
          stack[top++] = suffix[code];
          code = prefix[code];
        }
        first = suffix[code] & 0xff;
        stack[top++] = first;
        if (available < MAX) {
          prefix[available] = oldCode;
          suffix[available] = first;
          available++;
          if ((available & codeMask) === 0 && available < MAX) {
            codeSize++;
            codeMask += available;
          }
        }
        oldCode = inCode;
      }
      top--;
      dst[pi++] = stack[top];
      i++;
    }
    for (var k = pi; k < pixelCount; k++) dst[k] = 0;
    return dst;
  }

  function deinterlace(pixels, width) {
    var rows = pixels.length / width, out = new Array(pixels.length);
    var offs = [0, 4, 2, 1], steps = [8, 8, 4, 2], from = 0;
    for (var pass = 0; pass < 4; pass++) {
      for (var to = offs[pass]; to < rows; to += steps[pass]) {
        for (var c = 0; c < width; c++) out[to * width + c] = pixels[from * width + c];
        from++;
      }
    }
    return out;
  }

  function decodeGIF(ab) {
    var parsed = parseGIF(ab);
    var frameCount = Math.max(1, Math.min(MAX_FRAMES, parsed.frames.length));
    var budgetPixels = Math.max(4096, Math.floor(MAX_DECODE_PIXELS / frameCount));
    var sourcePixels = Math.max(1, parsed.width * parsed.height);
    var budgetScale = Math.min(1, Math.sqrt(budgetPixels / sourcePixels));
    var outScale = Math.min(1,
      MAX_SOURCE_SIDE / Math.max(parsed.width, parsed.height),
      budgetScale);
    var outW = Math.max(1, Math.round(parsed.width * outScale));
    var outH = Math.max(1, Math.round(parsed.height * outScale));
    var limit = Math.min(MAX_FRAMES, parsed.frames.length);
    var full = document.createElement("canvas");
    full.width = parsed.width;
    full.height = parsed.height;
    var fctx = full.getContext("2d");
    fctx.fillStyle = "#000";
    fctx.fillRect(0, 0, full.width, full.height);
    var out = [];
    for (var fi = 0; fi < parsed.frames.length; fi++) {
      var fr = parsed.frames[fi];
      var img = fr.image, total = img.width * img.height;
      if (!total) continue;
      var data = new Uint8Array(img.blocks.reduce(function (n, b) { return n + b.length; }, 0));
      var off = 0;
      img.blocks.forEach(function (b) { data.set(b, off); off += b.length; });
      var pixels = lzwDecode(img.minCodeSize, data, total);
      if (img.interlaced) pixels = deinterlace(pixels, img.width);
      var ct = img.lct.length ? img.lct : parsed.gct;
      var local = document.createElement("canvas");
      local.width = img.width;
      local.height = img.height;
      var lctx = local.getContext("2d"), patch = lctx.createImageData(img.width, img.height);
      var tr = fr.gce ? fr.gce.transparentIndex : null;
      for (var i = 0; i < total; i++) {
        var idx = pixels[i] || 0;
        var col = ct[idx] || [0, 0, 0];
        var q = i * 4;
        patch.data[q] = col[0];
        patch.data[q + 1] = col[1];
        patch.data[q + 2] = col[2];
        patch.data[q + 3] = (tr === idx) ? 0 : 255;
      }
      if (fr.gce && fr.gce.disposal === 2) {
        fctx.clearRect(img.left, img.top, img.width, img.height);
      }
      lctx.putImageData(patch, 0, 0);
      fctx.drawImage(local, img.left, img.top);
      var fc = document.createElement("canvas");
      fc.width = outW;
      fc.height = outH;
      fc.getContext("2d").drawImage(full, 0, 0, outW, outH);
      out.push({
        canvas: fc,
        delay: fr.gce ? clamp(fr.gce.delay * 10, 30, 1000) : 100
      });
      if (out.length >= limit) break;
    }
    return {
      width: parsed.width,
      height: parsed.height,
      frames: out,
      total: parsed.frames.length,
      limit: limit,
      limited: out.length < parsed.frames.length
    };
  }

  /* ---------------- custom panel editor ---------------- */

  var customCanvasEl = null;
  var customCanvasCtx = null;
  var customDrag = null;

  function customCtx() {
    if (!customCanvasCtx) {
      customCanvasEl = $("glanim-custom-canvas");
      if (customCanvasEl) customCanvasCtx = customCanvasEl.getContext("2d");
    }
    return customCanvasCtx;
  }

  function customTemplates() {
    return {
      status: defaultCustomLayout(),
      clock: {
        bg: "#0a0c12",
        elements: [
          { type: "text", x: 8, y: 4, size: 1, color: "#c2ccdc", text: "TIME" },
          { type: "value", x: 142, y: 14, size: 3, align: "center", color: "#eef2fa", source: "clock" },
          { type: "value", x: 8, y: 62, size: 1, color: "#c2ccdc", source: "date" },
          { type: "value", x: 58, y: 62, size: 1, color: "#c2ccdc", source: "weekday" },
          { type: "value", x: 276, y: 62, size: 1, align: "right", color: "#eef2fa", source: "net" }
        ]
      },
      fan: {
        bg: "#0a0c12",
        elements: [
          { type: "text", x: 8, y: 4, size: 1, color: "#c2ccdc", text: "FAN" },
          { type: "value", x: 8, y: 16, size: 3, color: "#eef2fa", source: "fan_rpm" },
          { type: "text", x: 118, y: 30, size: 1, color: "#c2ccdc", text: "RPM" },
          { type: "text", x: 8, y: 50, size: 1, color: "#c2ccdc", text: "PWM" },
          { type: "bar", x: 44, y: 49, w: 130, h: 8, source: "fan_pwm", color: "auto" },
          { type: "value", x: 184, y: 49, size: 1, color: "#eef2fa", source: "fan_pwm", suffix: "%" },
          { type: "value", x: 224, y: 8, size: 2, color: "#f0be3c", source: "temp", suffix: "C" },
          { type: "value", x: 224, y: 32, size: 1, color: "#c2ccdc", source: "hostname" }
        ]
      },
      minimal: {
        bg: "#0a0c12",
        elements: [
          { type: "value", x: 8, y: 4, size: 1, color: "#c2ccdc", source: "hostname" },
          { type: "value", x: 8, y: 18, size: 2, color: "#eef2fa", source: "clock" },
          { type: "text", x: 8, y: 44, size: 1, color: "#c2ccdc", text: "CPU" },
          { type: "value", x: 40, y: 44, size: 1, color: "#eef2fa", source: "cpu", suffix: "%" },
          { type: "text", x: 92, y: 44, size: 1, color: "#c2ccdc", text: "MEM" },
          { type: "value", x: 126, y: 44, size: 1, color: "#eef2fa", source: "mem", suffix: "%" },
          { type: "text", x: 180, y: 44, size: 1, color: "#c2ccdc", text: "TMP" },
          { type: "value", x: 212, y: 44, size: 1, color: "#eef2fa", source: "temp", suffix: "C" }
        ]
      },
      blank: { bg: "#0a0c12", elements: [] }
    };
  }

  function customPoint(ev) {
    if (!customCanvasEl) return { x: 0, y: 0 };
    var r = customCanvasEl.getBoundingClientRect();
    return {
      x: (ev.clientX - r.left) * PANEL_W / r.width,
      y: (ev.clientY - r.top) * PANEL_H / r.height
    };
  }

  function customHit(x, y) {
    var d = dashData();
    var ctx = customCtx();
    if (!ctx) return -1;
    for (var i = CUSTOM.elements.length - 1; i >= 0; i--) {
      var b = customBox(ctx, CUSTOM.elements[i], d);
      if (x >= b.x - 1 && x <= b.x + b.w + 1 && y >= b.y - 1 && y <= b.y + b.h + 1) return i;
    }
    return -1;
  }

  function drawCustomEditor() {
    var ctx = customCtx();
    if (!ctx) return;
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    ctx.imageSmoothingEnabled = false;
    drawCustomLayout(ctx, CUSTOM, dashData(), {
      editor: true,
      selected: customSelected,
      grid: true
    });
  }

  function renderCustomPalette() {
    var host = $("glanim-data-palette");
    if (!host) return;
    host.innerHTML = "";
    var d = dashData();
    DATA_DEFS.forEach(function (def) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "gl-data-chip";
      b.title = def.label + " · " + def.key;
      var name = document.createElement("b");
      name.textContent = def.label;
      var val = document.createElement("small");
      val.textContent = customValue(def.key, d) + (def.unit ? " " + def.unit : "");
      b.appendChild(name);
      b.appendChild(val);
      b.addEventListener("click", function () {
        addCustomElement("value", def.key);
      });
      host.appendChild(b);
    });
  }

  var INSPECTOR_LABEL = {
    size: ZH ? "字号" : "Size",
    align: ZH ? "对齐" : "Align",
    text: ZH ? "文本" : "Text",
    data: ZH ? "数据" : "Data",
    prefix: ZH ? "前缀" : "Prefix",
    suffix: ZH ? "后缀" : "Suffix",
    width: ZH ? "宽度" : "Width",
    height: ZH ? "高度" : "Height",
    value: ZH ? "数值" : "Value",
    auto: ZH ? "自动" : "Auto",
    color: ZH ? "颜色" : "Color"
  };

  function customField(label, control) {
    return '<div class="gl-custom-field"><label>' + label + '</label>' + control + '</div>';
  }

  function escAttr(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderCustomInspector() {
    var host = $("glanim-custom-inspector");
    var label = $("glanim-custom-selected-label");
    if (!host) return;
    var el = CUSTOM.elements[customSelected];
    if (!el) {
      host.innerHTML = '<div class="gl-custom-empty">'
        + (ZH ? "在上方画布中选择一个元素，或从右侧数据面板添加。" : "Select an element on the canvas, or add one from the data palette.")
        + '</div>';
      if (label) label.textContent = ZH ? "未选择" : "none selected";
      return;
    }
    if (label) label.textContent = (el.type || "").toUpperCase() + " #" + (customSelected + 1);
    var html = "";
    html += customField("X", '<input type="number" id="glc-x" min="0" max="283" value="' + num(el.x, 0) + '">');
    html += customField("Y", '<input type="number" id="glc-y" min="0" max="75" value="' + num(el.y, 0) + '">');
    if (el.type === "text" || el.type === "value") {
      html += customField(INSPECTOR_LABEL.size, '<select id="glc-size">'
        + [1, 2, 3].map(function (s) { return '<option value="' + s + '"' + (num(el.size, 1) === s ? " selected" : "") + ">" + s + "×</option>"; }).join("")
        + "</select>");
      html += customField(INSPECTOR_LABEL.align, '<select id="glc-align">'
        + ["left", "center", "right"].map(function (a) { return '<option value="' + a + '"' + ((el.align || "left") === a ? " selected" : "") + ">" + a + "</option>"; }).join("")
        + "</select>");
    }
    if (el.type === "text") {
      html += customField(INSPECTOR_LABEL.text, '<input type="text" id="glc-text" maxlength="64" value="' + escAttr(el.text) + '">');
    }
    if (el.type === "value" || el.type === "bar") {
      html += customField(INSPECTOR_LABEL.data, '<select id="glc-source">'
        + DATA_DEFS.map(function (def) {
          return '<option value="' + def.key + '"' + (el.source === def.key ? " selected" : "") + ">" + def.label + "</option>";
        }).join("")
        + "</select>");
      html += customField(INSPECTOR_LABEL.prefix, '<input type="text" id="glc-prefix" maxlength="16" value="' + escAttr(el.prefix) + '">');
      html += customField(INSPECTOR_LABEL.suffix, '<input type="text" id="glc-suffix" maxlength="16" value="' + escAttr(el.suffix) + '">');
    }
    if (el.type === "bar") {
      html += customField(INSPECTOR_LABEL.width, '<input type="number" id="glc-w" min="1" max="284" value="' + num(el.w, 120) + '">');
      html += customField(INSPECTOR_LABEL.height, '<input type="number" id="glc-h" min="1" max="76" value="' + num(el.h, 8) + '">');
      html += customField(INSPECTOR_LABEL.value, '<input type="checkbox" id="glc-show"' + (el.show_value ? " checked" : "") + ">");
      html += customField(INSPECTOR_LABEL.auto, '<input type="checkbox" id="glc-auto"' + (el.color === "auto" ? " checked" : "") + ">");
    }
    if (el.type === "rect") {
      html += customField(INSPECTOR_LABEL.width, '<input type="number" id="glc-w" min="1" max="284" value="' + num(el.w, 20) + '">');
      html += customField(INSPECTOR_LABEL.height, '<input type="number" id="glc-h" min="1" max="76" value="' + num(el.h, 2) + '">');
    }
    if (el.type === "line") {
      html += customField(INSPECTOR_LABEL.width, '<input type="number" id="glc-w" min="1" max="284" value="' + num(el.w, 100) + '">');
    }
    if (el.type !== "bar" || el.color !== "auto") {
      html += customField(INSPECTOR_LABEL.color, '<input type="color" id="glc-color" value="' + hexColor(el.color, "#eef2fa") + '">');
    }
    html += '<div class="gl-custom-actions">'
      + '<button type="button" class="gl-btn" id="glc-duplicate">' + (ZH ? "复制" : "Duplicate") + '</button>'
      + '<button type="button" class="gl-btn ghost is-danger" id="glc-delete">' + (ZH ? "删除" : "Delete") + '</button>'
      + '</div>';
    host.innerHTML = html;

    function changed() {
      setDirty(true);
      drawCustomEditor();
      drawPreview();
    }
    function bind(id, ev, fn) {
      var node = $(id);
      if (node) node.addEventListener(ev, fn);
    }
    bind("glc-x", "input", function (e) { el.x = clamp(num(e.target.value, 0), 0, 283); changed(); });
    bind("glc-y", "input", function (e) { el.y = clamp(num(e.target.value, 0), 0, 75); changed(); });
    bind("glc-size", "change", function (e) { el.size = clamp(num(e.target.value, 1), 1, 3); changed(); });
    bind("glc-align", "change", function (e) { el.align = e.target.value; changed(); });
    bind("glc-text", "input", function (e) { el.text = e.target.value.slice(0, 64); changed(); });
    bind("glc-source", "change", function (e) { el.source = e.target.value; changed(); });
    bind("glc-prefix", "input", function (e) { el.prefix = e.target.value.slice(0, 16); changed(); });
    bind("glc-suffix", "input", function (e) { el.suffix = e.target.value.slice(0, 16); changed(); });
    bind("glc-w", "input", function (e) { el.w = clamp(num(e.target.value, 1), 1, 284); changed(); });
    bind("glc-h", "input", function (e) { el.h = clamp(num(e.target.value, 1), 1, 76); changed(); });
    bind("glc-show", "change", function (e) { el.show_value = e.target.checked; changed(); });
    bind("glc-auto", "change", function (e) {
      el.color = e.target.checked ? "auto" : "#eef2fa";
      renderCustomInspector();
      changed();
    });
    bind("glc-color", "input", function (e) { el.color = hexColor(e.target.value, "#eef2fa"); changed(); });
    bind("glc-duplicate", "click", function () {
      var copy = clone(el);
      copy.x = clamp(num(copy.x, 0) + 6, 0, 283);
      copy.y = clamp(num(copy.y, 0) + 6, 0, 75);
      CUSTOM.elements.push(copy);
      customSelected = CUSTOM.elements.length - 1;
      changed();
      renderCustomInspector();
    });
    bind("glc-delete", "click", function () {
      CUSTOM.elements.splice(customSelected, 1);
      customSelected = -1;
      changed();
      renderCustomInspector();
    });
  }

  function addCustomElement(type, source) {
    var el = { type: type, x: 8, y: 6, size: 1, color: "#eef2fa", align: "left" };
    if (type === "text") {
      el.text = "TEXT";
    } else if (type === "value") {
      el.source = source || "cpu";
      if (el.source === "temp") el.suffix = "C";
      else if (el.source === "cpu" || el.source === "mem" || el.source === "fan_pwm") el.suffix = "%";
    } else if (type === "bar") {
      el.source = "cpu";
      el.w = 120;
      el.h = 8;
      el.color = "auto";
      el.show_value = false;
    } else if (type === "line") {
      el.w = 100;
      el.color = "#39445a";
    }
    var n = CUSTOM.elements.length;
    el.x = clamp(8 + (n % 3) * 70, 0, 283);
    el.y = clamp(6 + (Math.floor(n / 3) % 4) * 16, 0, 75);
    CUSTOM.elements.push(el);
    customSelected = CUSTOM.elements.length - 1;
    setDirty(true);
    drawCustomEditor();
    drawPreview();
    renderCustomInspector();
  }

  function bindCustomEditor() {
    customCtx();
    renderCustomPalette();
    drawCustomEditor();
    renderCustomInspector();

    var bg = $("glanim-custom-bg");
    if (bg) bg.addEventListener("input", function () {
      CUSTOM.bg = hexColor(bg.value, "#0a0c12");
      setDirty(true);
      drawCustomEditor();
      drawPreview();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".gl-bg-swatch"), function (sw) {
      sw.addEventListener("click", function () {
        CUSTOM.bg = hexColor(sw.getAttribute("data-bg"), "#0a0c12");
        if (bg) bg.value = CUSTOM.bg;
        setDirty(true);
        drawCustomEditor();
        drawPreview();
      });
    });

    var template = $("glanim-custom-template");
    if (template) template.value = "custom";
    if (template) template.addEventListener("change", function () {
      var t = customTemplates()[template.value];
      if (!t) return;
      CUSTOM = clone(t);
      customSelected = -1;
      setDirty(true);
      drawCustomEditor();
      drawPreview();
      renderCustomInspector();
    });

    function add(id, type, source) {
      var node = $(id);
      if (node) node.addEventListener("click", function () { addCustomElement(type, source); });
    }
    add("glanim-custom-add-text", "text");
    add("glanim-custom-add-value", "value", "cpu");
    add("glanim-custom-add-bar", "bar");
    add("glanim-custom-add-line", "line");

    if (!customCanvasEl) return;
    customCanvasEl.addEventListener("pointerdown", function (ev) {
      var p = customPoint(ev);
      var idx = customHit(p.x, p.y);
      customSelected = idx;
      drawCustomEditor();
      renderCustomInspector();
      if (idx >= 0) {
        var box = customBox(customCanvasCtx, CUSTOM.elements[idx], dashData());
        customDrag = { dx: p.x - box.x, dy: p.y - box.y };
        if (customCanvasEl.setPointerCapture) customCanvasEl.setPointerCapture(ev.pointerId);
        ev.preventDefault();
      }
    });
    customCanvasEl.addEventListener("pointermove", function (ev) {
      if (!customDrag || customSelected < 0) return;
      var p = customPoint(ev);
      var el = CUSTOM.elements[customSelected];
      if (!el) return;
      el.x = clamp(Math.round(p.x - customDrag.dx), 0, 283);
      el.y = clamp(Math.round(p.y - customDrag.dy), 0, 75);
      var xi = $("glc-x"), yi = $("glc-y");
      if (xi) xi.value = String(el.x);
      if (yi) yi.value = String(el.y);
      setDirty(true);
      drawCustomEditor();
      drawPreview();
      ev.preventDefault();
    });
    function endDrag() { customDrag = null; }
    customCanvasEl.addEventListener("pointerup", endDrag);
    customCanvasEl.addEventListener("pointercancel", endDrag);
  }

  function bindToggle(id, key) {
    var el = $(id);
    if (!el) return;
    el.addEventListener("change", function () {
      S[key] = el.checked;
      setDirty(true);
      if (key === "loop") startPackTimer();
      if (key.indexOf("show") === 0) {
        updatePreviewTabs();
        drawPreview();
      }
      if (key === "enabled") {
        // only affects service state on save
      }
    });
  }

  function bindForm() {
    var modeGrid = $("gl-mode-grid");
    if (modeGrid) {
      modeGrid.addEventListener("click", function (ev) {
        var card = ev.target.closest ? ev.target.closest(".gl-mode") : null;
        if (!card) return;
        var mode = card.getAttribute("data-mode");
        if (!mode || mode === S.mode) return;
        S.mode = mode;
        previewPage = null;
        syncPanels();
        Array.prototype.forEach.call(modeGrid.querySelectorAll(".gl-mode"), function (c) {
          var active = c.getAttribute("data-mode") === mode;
          c.className = "gl-mode" + (active ? " is-active" : "");
          c.setAttribute("aria-checked", active ? "true" : "false");
        });
        updatePreviewTabs();
        resetPreviewAnimation();
        setDirty(true);
      });
    }

    bindToggle("gl-enabled", "enabled");
    bindToggle("gl-loop", "loop");
    bindToggle("gl-show-time", "showTime");
    bindToggle("gl-show-cpu", "showCpu");
    bindToggle("gl-show-mem", "showMem");
    bindToggle("gl-show-temp", "showTemp");
    bindToggle("gl-show-net", "showNet");
    bindToggle("gl-show-uptime", "showUptime");
    bindToggle("gl-show-ip", "showIp");
    bindToggle("gl-touch-enable", "touchEnable");
    bindToggle("gl-touch-swap", "touchSwap");
    bindToggle("gl-touch-flip", "touchFlip");
    bindToggle("gl-keep-original", "keepOriginal");

    var bright = $("gl-brightness");
    if (bright) bright.addEventListener("input", function () {
      S.brightness = num(bright.value, 4);
      setText("gl-brightness-val", String(S.brightness));
      setDirty(true);
    });

    var fps = $("gl-fps");
    if (fps) fps.addEventListener("input", function () {
      S.fps = num(fps.value, 0);
      setText("gl-fps-val", S.fps === 0 ? (ZH ? "原生" : "native") : (S.fps + " fps"));
      setDirty(true);
      startPackTimer();
    });

    var interval = $("gl-dash-interval");
    if (interval) interval.addEventListener("input", function () {
      S.interval = num(interval.value, 5);
      setText("gl-dash-interval-val", S.interval + "s");
      setDirty(true);
    });

    var touchAction = $("gl-touch-action");
    if (touchAction) touchAction.addEventListener("change", function () {
      S.touchAction = touchAction.value;
      setDirty(true);
    });

    var framesDir = $("glanim-frames-dir");
    if (framesDir) framesDir.addEventListener("input", function () {
      S.framesDir = framesDir.value.trim();
      setDirty(true);
    });

    var revert = $("glanim-revert");
    if (revert) revert.addEventListener("click", function () {
      S = clone(LAST);
      CUSTOM = clone(LAST_CUSTOM);
      customSelected = -1;
      syncForm();
      drawCustomEditor();
      renderCustomInspector();
      resetPreviewAnimation();
      setDirty(false);
      toast(ZH ? "已还原到上次保存的状态" : "Reverted to the last saved state");
    });

    var saveBtn = $("glanim-save");
    if (saveBtn) saveBtn.addEventListener("click", save);

    var tabs = $("glanim-preview-tabs");
    if (tabs) tabs.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button") : null;
      if (!b) return;
      previewPage = b.getAttribute("data-page");
      updatePreviewTabs();
      drawPreview();
    });
  }

  function clearBackground() {
    if (!window.confirm(ZH ? "确定清除自定义背景，恢复纯色背景？" : "Clear the custom background and restore the solid color?")) return;
    api(URLS.clearBg, { method: "POST", body: formBody({}) })
      .then(function () {
        toast(ZH ? "背景已清除" : "Background cleared", "ok");
        setTimeout(function () { window.location.reload(); }, 700);
      })
      .catch(function (err) {
        toast(err.message || (ZH ? "清除失败" : "Clear failed"), "error");
      });
  }

  function bindStudio() {
    studioEls();
    var file = $("glanim-file");
    var drop = $("glanim-drop");
    if (drop && file) {
      drop.addEventListener("click", function (ev) {
        if (ev.target === file) return;
        file.click();
      });
      ["dragenter", "dragover"].forEach(function (name) {
        drop.addEventListener(name, function (ev) {
          ev.preventDefault();
          drop.classList.add("is-over");
        });
      });
      ["dragleave", "drop"].forEach(function (name) {
        drop.addEventListener(name, function (ev) {
          ev.preventDefault();
          drop.classList.remove("is-over");
        });
      });
      drop.addEventListener("drop", function (ev) {
        if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0]) {
          handleImageFile(ev.dataTransfer.files[0]);
        }
      });
    }
    if (file) file.addEventListener("change", function () {
      if (file.files && file.files[0]) handleImageFile(file.files[0]);
    });
    var urlLoad = $("glanim-url-load");
    if (urlLoad) urlLoad.addEventListener("click", loadUrl);
    var urlInput = $("glanim-url");
    if (urlInput) urlInput.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        loadUrl();
      }
    });

    document.querySelectorAll(".gl-fit").forEach(function (b) {
      b.addEventListener("click", function () {
        studio.fit = b.getAttribute("data-fit") || "cover";
        document.querySelectorAll(".gl-fit").forEach(function (x) {
          x.className = "gl-fit" + (x === b ? " is-active" : "");
        });
        placeStudio();
      });
    });

    var zoom = $("glanim-zoom");
    if (zoom) zoom.addEventListener("input", function () {
      studio.zoom = parseFloat(zoom.value) || 1;
      setText("glanim-zoom-val", studio.zoom.toFixed(2) + "×");
      placeStudio();
    });

    var reset = $("glanim-reset");
    if (reset) reset.addEventListener("click", function () {
      resetTransform();
      placeStudio();
    });

    var scrub = $("glanim-scrub");
    if (scrub) scrub.addEventListener("input", function () {
      stopStudioPlay();
      studio.cur = clamp(num(scrub.value, 1) - 1, 0, Math.max(0, studio.frames.length - 1));
      updateStudioUI();
    });

    var play = $("glanim-play");
    if (play) play.addEventListener("click", function () {
      if (studio.playing) stopStudioPlay();
      else startStudioPlay();
    });

    var apply = $("glanim-apply");
    if (apply) apply.addEventListener("click", function () { applyImage("screen"); });
    var applyBg = $("glanim-apply-bg");
    if (applyBg) applyBg.addEventListener("click", applyBackground);
    var clearBg = $("glanim-clear-bg");
    if (clearBg) clearBg.addEventListener("click", clearBackground);

    if (stage) {
      stage.addEventListener("pointerdown", function (ev) {
        if (!currentFrame()) return;
        studio.dragging = true;
        studio.dpx = ev.clientX;
        studio.dpy = ev.clientY;
        if (stage.setPointerCapture) stage.setPointerCapture(ev.pointerId);
        ev.preventDefault();
      });
      stage.addEventListener("pointermove", function (ev) {
        if (!studio.dragging) return;
        studio.offX += ev.clientX - studio.dpx;
        studio.offY += ev.clientY - studio.dpy;
        studio.dpx = ev.clientX;
        studio.dpy = ev.clientY;
        placeStudio();
      });
      function endDrag() { studio.dragging = false; }
      stage.addEventListener("pointerup", endDrag);
      stage.addEventListener("pointercancel", endDrag);
      stage.addEventListener("wheel", function (ev) {
        if (!currentFrame()) return;
        ev.preventDefault();
        studio.zoom = clamp(studio.zoom - ev.deltaY * 0.001, 1, 3);
        var z = $("glanim-zoom");
        if (z) z.value = String(studio.zoom);
        setText("glanim-zoom-val", studio.zoom.toFixed(2) + "×");
        placeStudio();
      }, { passive: false });
    }
  }

  function bindPack() {
    var upload = $("glanim-pack-upload");
    var input = fileInput();
    if (upload && input) upload.addEventListener("click", function () { input.click(); });
    if (input) input.addEventListener("change", function () {
      if (input.files && input.files[0]) uploadPack(input.files[0]);
    });
    var clear = $("glanim-pack-clear");
    if (clear) clear.addEventListener("click", clearPack);
    var restart = $("glanim-restart");
    if (restart) restart.addEventListener("click", restartService);
    var restore = $("glanim-restore");
    if (restore) restore.addEventListener("click", restoreOem);
  }

  function preventGlobalSubmit() {
    var form = document.querySelector('form[name="cbi"]');
    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        return false;
      });
    }
    var actions = document.querySelector(".cbi-page-actions");
    if (actions) actions.style.display = "none";
  }

  function markPageSection() {
    var page = $("glanim-page");
    if (!page) return;
    var section = page.closest ? page.closest(".cbi-section") : null;
    if (section) section.classList.add("gl-page-section");
    var descr = page.closest ? page.closest(".cbi-section-descr") : null;
    if (descr) {
      descr.style.padding = "0";
      descr.style.margin = "0";
      descr.style.fontSize = "inherit";
      descr.style.lineHeight = "inherit";
      descr.style.color = "inherit";
    }
  }

  function detectDark() {
    var dark = false;
    try {
      var bg = getComputedStyle(document.body).backgroundColor;
      var m = bg && bg.match(/\d+/g);
      if (m && m.length >= 3) {
        dark = (0.299 * +m[0] + 0.587 * +m[1] + 0.114 * +m[2]) < 110;
      }
    } catch (e) { /* ignore */ }
    if (!dark && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      dark = true;
    }
    if (dark) document.documentElement.classList.add("gl-dark");
  }

  function beforeUnload(ev) {
    if (!dirty) return undefined;
    ev.preventDefault();
    ev.returnValue = "";
    return "";
  }

  function init() {
    detectDark();
    markPageSection();
    preventGlobalSubmit();
    bindForm();
    bindStudio();
    bindPack();
    bindCustomEditor();
    syncForm();
    setDirty(false);
    updateStudioUI();
    drawPreview();
    fetchStatus();
    setInterval(fetchStatus, 2000);
    setInterval(function () {
      if (S.mode === "dashboard" || S.mode === "custom") drawPreview();
    }, 1000);
    if (PACK.count > 0 && (S.mode === "gif" || S.mode === "still" || S.mode === "slideshow")) loadPackFrames();
    window.addEventListener("beforeunload", beforeUnload);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
