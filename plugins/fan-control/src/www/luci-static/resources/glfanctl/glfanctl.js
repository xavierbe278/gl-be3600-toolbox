/* Fan Control page front-end. Independent save, no writeable CBI fields. */
(function () {
  "use strict";

  var CFG = window.GLFAN_CFG || {};
  var ZH = !!CFG.zh;
  var URLS = CFG.urls || {};
  var CURRENT = CFG.current || {};
  var INITIAL = CFG.initial || {};
  var MODE_LABEL = {
    auto: ZH ? "自动（原厂 PID）" : "Auto (OEM PID)",
    curve: ZH ? "温度曲线" : "Temperature curve",
    manual: ZH ? "固定 PWM" : "Fixed PWM",
    stop: ZH ? "已停转（调试）" : "Stopped (debug)"
  };
  var WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

  var S = {
    enabled: !!CURRENT.enabled,
    mode: CURRENT.mode || "auto",
    zone: num(CURRENT.zone, 0),
    poll: num(CURRENT.poll, 2),
    hysteresis: num(CURRENT.hysteresis, 2),
    manual: num(CURRENT.manual, 40),
    min: num(CURRENT.min, 0),
    max: num(CURRENT.max, 255),
    pct: []
  };
  S.pct = (CURRENT.pct || []).map(function (v) { return clamp(num(v, 0), 0, 100); });
  while (S.pct.length < 10) S.pct.push(0);
  var LAST = clone(S);
  var dirty = false;
  var pollBusy = false;
  var histPwm = [], histRpm = [], histTemp = [];
  var lastTemp = 0;
  var toastTimer = null;
  var dragIdx = null;

  var $ = function (id) { return document.getElementById(id); };
  function num(v, d) { var n = parseInt(v, 10); return isNaN(n) ? d : n; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function clone(o) { return JSON.parse(JSON.stringify(o || {})); }
  function setText(id, text) { var e = $(id); if (e) e.textContent = text; }
  function token() { return (typeof L !== "undefined" && L.env && L.env.token) ? L.env.token : ""; }

  function toast(message, kind) {
    var el = $("fan-toast");
    if (!el) return;
    el.textContent = message;
    el.className = "gl-toast is-on" + (kind ? " is-" + kind : "");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.className = "gl-toast"; }, 3200);
  }

  function setDirty(v) {
    dirty = !!v;
    var bar = document.querySelector("#fan-savebar .gl-save-state");
    if (bar) bar.className = "gl-save-state" + (dirty ? " is-dirty" : "");
    setText("fan-save-text", dirty ? (ZH ? "有未保存的修改" : "Unsaved changes") : (ZH ? "所有修改已保存" : "All changes saved"));
  }

  function api(url, options) {
    options = options || {};
    options.cache = "no-store";
    options.headers = options.headers || {};
    options.headers["X-Requested-With"] = "XMLHttpRequest";
    options.headers["Accept"] = "application/json";
    return fetch(url, options).then(function (r) {
      return r.text().then(function (text) {
        var data = null;
        try { data = JSON.parse(text); } catch (e) { data = null; }
        if (!r.ok || !data) throw new Error((data && (data.error || data.msg)) || ("HTTP " + r.status));
        if (data.ok === false) throw new Error(data.error || data.msg || "failed");
        return data;
      });
    });
  }

  function modeLabel(mode) { return MODE_LABEL[mode] || mode || "–"; }

  /* ---------------- status / chart ---------------- */

  function pollStatus() {
    if (!URLS.status || pollBusy) return;
    pollBusy = true;
    fetch(URLS.status, { cache: "no-store", headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        updateStatus(json || {});
      })
      .catch(function () { updateStatus({ daemon: "0" }); })
      .then(function () { pollBusy = false; });
  }

  function updateStatus(json) {
    var daemon = json.daemon === "1";
    var mode = modeLabel(json.mode || "auto");
    var rpm = num(json.rpm, 0);
    var pwm = clamp(num(json.pwm, 0), 0, 255);
    var pct = Math.round(pwm * 100 / 255);
    var temps = json.temps || {};
    var maxTemp = -1;
    for (var i = 0; i <= 4; i++) {
      var t = num(temps[i], -1);
      if (t > maxTemp) maxTemp = t;
      var z = $("fan-zone-" + i);
      if (z) z.textContent = (t < 0 ? "–" : t + "°C");
    }

    setText("fan-rpm", String(rpm));
    setText("fan-pwm", pwm + "/255");
    setText("fan-temp", (maxTemp < 0 ? "–" : maxTemp + "°C"));
    setText("fan-mode", mode);
    setText("fan-service", daemon ? (ZH ? "插件" : "plugin") : (json.oem_running ? (ZH ? "原厂" : "OEM") : (ZH ? "已停止" : "stopped")));
    setText("fan-pill-service", daemon ? (ZH ? "插件" : "plugin") : (json.oem_running ? (ZH ? "原厂" : "OEM") : (ZH ? "已停止" : "stopped")));
    setText("fan-pill-mode", mode);
    setText("fan-pill-rpm", rpm + " RPM");
    setText("fan-pill-pwm", pwm + "/255");
    setText("fan-pill-temp", (maxTemp < 0 ? "–" : maxTemp + "°C"));
    setText("fan-live-text", daemon ? (ZH ? "插件驱动 PWM" : "plugin driving PWM") : (ZH ? "原厂 gl_fan 运行中" : "OEM gl_fan running"));
    var badge = $("fan-live-badge");
    if (badge) {
      badge.className = "gl-badge" + (daemon ? " ok" : "");
      badge.textContent = daemon ? (ZH ? "实时" : "live") : (ZH ? "待机" : "idle");
    }
    var live = $("fan-live");
    if (live) live.className = "gl-live" + (daemon ? " is-on" : "");

    var fill = $("fan-pwm-fill");
    if (fill) fill.style.width = pct + "%";
    setText("fan-pwm-label", pct + "%");

    if (maxTemp >= 0) lastTemp = maxTemp;
    for (var zi = 0; zi <= 4; zi++) {
      var zt = num(temps[zi], -1);
      var bar = $("fan-zone-bar-" + zi);
      var zv = $("fan-zone-val-" + zi);
      if (bar) bar.style.width = (zt < 0 ? 0 : clamp(zt, 0, 100)) + "%";
      if (zv) zv.textContent = (zt < 0 ? "–" : zt + "°C");
    }
    histPwm.push(pct);
    histRpm.push(rpm);
    histTemp.push(maxTemp >= 0 ? maxTemp : 0);
    if (histPwm.length > 60) histPwm.shift();
    if (histRpm.length > 60) histRpm.shift();
    if (histTemp.length > 60) histTemp.shift();
    drawCurve();
    drawChart();
  }

  function drawChart() {
    var cv = $("fan-chart");
    if (!cv) return;
    var ctx = cv.getContext("2d");
    var W = cv.width, H = cv.height;
    ctx.clearRect(0, 0, W, H);
    var ml = 46, mr = 58, mt = 22, mb = 24;
    var pw = W - ml - mr, ph = H - mt - mb;
    var pMax = 100, rMax = 5600;
    ctx.font = "10px ui-monospace, monospace";
    for (var g = 0; g <= 4; g++) {
      var y = mt + g / 4 * ph;
      var p = pMax - g * 25;
      ctx.strokeStyle = "rgba(128,140,160,.16)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ml, y);
      ctx.lineTo(ml + pw, y);
      ctx.stroke();
      ctx.fillStyle = "#8898aa";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(p + "%", ml - 8, y);
      ctx.textAlign = "left";
      ctx.fillText(Math.round(rMax * (1 - g / 4)), ml + pw + 8, y);
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (var xg = 0; xg <= 3; xg++) {
      var x = ml + xg / 3 * pw;
      ctx.strokeStyle = "rgba(128,140,160,.08)";
      ctx.beginPath();
      ctx.moveTo(x, mt);
      ctx.lineTo(x, mt + ph);
      ctx.stroke();
      ctx.fillStyle = "#8898aa";
      var ago = Math.round((1 - xg / 3) * 118);
      ctx.fillText(xg === 3 ? "0s" : "-" + ago + "s", x, mt + ph + 6);
    }
    function line(arr, map, color) {
      if (!arr.length) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      arr.forEach(function (v, i) {
        var x = ml + i / 59 * pw;
        var y = map(v);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    line(histTemp, function (v) { return mt + (1 - clamp(v, 0, 100) / 100) * ph; }, "#f0be3c");
    line(histPwm, function (v) { return mt + (1 - clamp(v, 0, 100) / 100) * ph; }, "#5b6cff");
    line(histRpm, function (v) { return mt + (1 - clamp(v, 0, rMax) / rMax) * ph; }, "#28a745");
  }

  /* ---------------- curve editor ---------------- */

  function curveValue(i) {
    var e = $("fan-pct-" + (i + 1));
    return e ? clamp(num(e.value, 0), 0, 100) : S.pct[i];
  }

  function setCurveValue(i, v) {
    v = clamp(Math.round(v), 0, 100);
    var e = $("fan-pct-" + (i + 1));
    if (e) e.value = String(v);
    S.pct[i] = v;
    setDirty(true);
    drawCurve();
  }

  function drawCurve() {
    var svg = $("fan-curve-svg");
    if (!svg) return;
    var W0 = 720, H0 = 250, ML = 44, MR = 18, MT = 18, MB = 30;
    var W = W0 - ML - MR, H = H0 - MT - MB;
    var NS = "http://www.w3.org/2000/svg";
    function el(n, attrs) {
      var e = document.createElementNS(NS, n);
      for (var k in attrs) e.setAttribute(k, attrs[k]);
      return e;
    }
    svg.innerHTML = "";
    for (var g = 0; g <= 5; g++) {
      var v = 100 - g * 20, y = MT + g / 5 * H;
      svg.appendChild(el("line", { x1: ML, y1: y, x2: ML + W, y2: y, stroke: "rgba(128,140,160,.18)" }));
      var t = el("text", { x: ML - 8, y: y + 3, fill: "#8898aa", "font-size": 10, "text-anchor": "end" });
      t.textContent = v + "%";
      svg.appendChild(t);
    }
    for (var i = 0; i < 10; i++) {
      var x = ML + i / 9 * W;
      if (i % 2 === 1) svg.appendChild(el("line", { x1: x, y1: MT, x2: x, y2: MT + H, stroke: "rgba(128,140,160,.09)" }));
      var label = el("text", { x: x, y: MT + H + 18, fill: "#8898aa", "font-size": 9, "text-anchor": i === 9 ? "end" : (i === 0 ? "start" : "middle") });
      label.textContent = (10 * (i + 1)) + "°";
      svg.appendChild(label);
    }
    // current temperature marker on the 10..100 °C axis
    if (lastTemp > 0) {
      var tx = ML + clamp((lastTemp - 10) / 90, 0, 1) * W;
      svg.appendChild(el("line", {
        x1: tx, y1: MT, x2: tx, y2: MT + H,
        stroke: "#f0be3c", "stroke-width": 1.5, "stroke-dasharray": "4 3"
      }));
      var tl = el("text", {
        x: clamp(tx, 36, W0 - 40), y: MT - 5,
        fill: "#f0be3c", "font-size": 10, "text-anchor": "middle"
      });
      tl.textContent = lastTemp + "°C";
      svg.appendChild(tl);
    }
    var pts = [];
    for (var j = 0; j < 10; j++) {
      var pct = curveValue(j);
      pts.push([ML + j / 9 * W, MT + (1 - pct / 100) * H, pct, j]);
    }
    svg.appendChild(el("polyline", {
      fill: "none", stroke: "#5b6cff", "stroke-width": 2.5,
      points: pts.map(function (p) { return p[0] + "," + p[1]; }).join(" ")
    }));
    pts.forEach(function (p) {
      var c = el("circle", {
        cx: p[0], cy: p[1], r: 7, fill: "#5b6cff", stroke: "#fff",
        "stroke-width": 2, cursor: "grab", "data-i": p[3]
      });
      svg.appendChild(c);
    });
  }

  function svgPoint(ev) {
    var svg = $("fan-curve-svg");
    if (!svg) return { x: 0, y: 0 };
    var r = svg.getBoundingClientRect();
    var cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    var cy = (ev.touches ? ev.touches[0].clientY : ev.clientY) - r.top;
    return { x: cx * 720 / r.width, y: cy * 250 / r.height };
  }

  function bindCurve() {
    var svg = $("fan-curve-svg");
    if (!svg) return;
    svg.addEventListener("pointerdown", function (ev) {
      var t = ev.target;
      if (!t || t.tagName.toLowerCase() !== "circle") return;
      dragIdx = num(t.getAttribute("data-i"), 0);
      ev.preventDefault();
    });
    svg.addEventListener("pointermove", function (ev) {
      if (dragIdx == null) return;
      var p = svgPoint(ev);
      var pct = 100 - (p.y - 18) / (250 - 18 - 30) * 100;
      setCurveValue(dragIdx, pct);
      ev.preventDefault();
    });
    function end() { dragIdx = null; }
    window.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    for (var i = 1; i <= 10; i++) {
      (function (idx, input) {
        if (input) input.addEventListener("input", function () {
          S.pct[idx] = clamp(num(input.value, 0), 0, 100);
          setDirty(true);
          drawCurve();
        });
      })(i - 1, $("fan-pct-" + i));
    }
  }

  /* ---------------- form ---------------- */

  function syncForm() {
    var e = $("fan-enabled"); if (e) e.checked = S.enabled;
    e = $("fan-zone"); if (e) e.value = String(S.zone);
    e = $("fan-poll"); if (e) e.value = String(S.poll);
    e = $("fan-hyst"); if (e) e.value = String(S.hysteresis);
    e = $("fan-manual"); if (e) e.value = String(S.manual);
    e = $("fan-min"); if (e) e.value = String(S.min);
    e = $("fan-max"); if (e) e.value = String(S.max);
    for (var i = 0; i < 10; i++) {
      var p = $("fan-pct-" + (i + 1));
      if (p) p.value = String(S.pct[i]);
    }
    var cards = document.querySelectorAll("#fan-mode-grid .gl-mode");
    Array.prototype.forEach.call(cards, function (c) {
      var active = c.getAttribute("data-mode") === S.mode;
      c.className = "gl-mode" + (active ? " is-active" : "");
      c.setAttribute("aria-checked", active ? "true" : "false");
    });
    drawCurve();
  }

  function collect() {
    var fd = new FormData();
    fd.append("token", token());
    fd.append("enabled", S.enabled ? "1" : "0");
    fd.append("mode", S.mode);
    fd.append("temp_zone", String(S.zone));
    fd.append("poll", String(S.poll));
    fd.append("hysteresis", String(S.hysteresis));
    fd.append("pwm_manual", String(S.manual));
    fd.append("min_pwm", String(S.min));
    fd.append("max_pwm", String(S.max));
    for (var i = 0; i < 10; i++) fd.append("pct" + (i + 1), String(S.pct[i]));
    return fd;
  }

  function save() {
    var btn = $("fan-save");
    if (btn) btn.disabled = true;
    setText("fan-save-text", ZH ? "保存中…" : "Saving…");
    api(URLS.save, { method: "POST", body: collect() })
      .then(function () {
        LAST = clone(S);
        setDirty(false);
        toast(ZH ? "已保存并应用" : "Saved and applied", "ok");
        setTimeout(pollStatus, 800);
      })
      .catch(function (err) {
        toast((ZH ? "保存失败：" : "Save failed: ") + (err.message || ""), "error");
      })
      .then(function () { if (btn) btn.disabled = false; });
  }

  function restore() {
    if (!window.confirm(ZH ? "确定停用插件并把风扇交回原厂 gl_fan？" : "Disable the plugin and hand the fan back to gl_fan?")) return;
    api(URLS.restore, { method: "POST", body: (function () { var fd = new FormData(); fd.append("token", token()); return fd; })() })
      .then(function () {
        S.enabled = false;
        S.mode = "auto";
        LAST = clone(S);
        syncForm();
        setDirty(false);
        toast(ZH ? "已恢复原厂控制" : "OEM control restored", "ok");
        setTimeout(pollStatus, 800);
      })
      .catch(function (err) {
        toast((ZH ? "恢复失败：" : "Restore failed: ") + (err.message || ""), "error");
      });
  }

  function bindForm() {
    var grid = $("fan-mode-grid");
    if (grid) grid.addEventListener("click", function (ev) {
      var card = ev.target.closest ? ev.target.closest(".gl-mode") : null;
      if (!card) return;
      S.mode = card.getAttribute("data-mode");
      Array.prototype.forEach.call(grid.querySelectorAll(".gl-mode"), function (c) {
        var active = c.getAttribute("data-mode") === S.mode;
        c.className = "gl-mode" + (active ? " is-active" : "");
        c.setAttribute("aria-checked", active ? "true" : "false");
      });
      setDirty(true);
    });
    var en = $("fan-enabled");
    if (en) en.addEventListener("change", function () { S.enabled = en.checked; setDirty(true); });
    function bindNum(id, key, lo, hi) {
      var e = $(id);
      if (e) e.addEventListener("input", function () { S[key] = clamp(num(e.value, 0), lo, hi); setDirty(true); });
    }
    bindNum("fan-poll", "poll", 1, 30);
    bindNum("fan-hyst", "hysteresis", 0, 10);
    bindNum("fan-manual", "manual", 0, 255);
    bindNum("fan-min", "min", 0, 255);
    bindNum("fan-max", "max", 0, 255);
    var zone = $("fan-zone");
    if (zone) zone.addEventListener("change", function () { S.zone = num(zone.value, 0); setDirty(true); });
    var saveBtn = $("fan-save");
    if (saveBtn) saveBtn.addEventListener("click", save);
    var restoreBtn = $("fan-restore");
    if (restoreBtn) restoreBtn.addEventListener("click", restore);
    var form = document.querySelector('form[name="cbi"]');
    if (form) form.addEventListener("submit", function (ev) { ev.preventDefault(); });
    var actions = document.querySelector(".cbi-page-actions");
    if (actions) actions.style.display = "none";
  }

  function buildZones() {
    var host = $("fan-zones");
    if (host) {
      host.innerHTML = "";
      for (var i = 0; i <= 4; i++) {
        var s = document.createElement("span");
        s.className = "fan-zone";
        s.appendChild(document.createTextNode("Z" + i + " "));
        var b = document.createElement("b");
        b.id = "fan-zone-" + i;
        b.textContent = "–";
        s.appendChild(b);
        host.appendChild(s);
      }
    }
    var bars = $("fan-zone-bars");
    if (!bars) return;
    bars.innerHTML = "";
    for (var j = 0; j <= 4; j++) {
      var row = document.createElement("div");
      row.className = "fan-zone-row";
      var name = document.createElement("span");
      name.textContent = "Z" + j;
      var track = document.createElement("div");
      track.className = "fan-zone-track";
      var fill = document.createElement("i");
      fill.id = "fan-zone-bar-" + j;
      track.appendChild(fill);
      var val = document.createElement("b");
      val.id = "fan-zone-val-" + j;
      val.textContent = "–";
      row.appendChild(name);
      row.appendChild(track);
      row.appendChild(val);
      bars.appendChild(row);
    }
  }

  function beforeUnload(ev) {
    if (!dirty) return undefined;
    ev.preventDefault();
    ev.returnValue = "";
    return "";
  }

  function init() {
    buildZones();
    bindForm();
    bindCurve();
    syncForm();
    setDirty(false);
    drawChart();
    var temps = INITIAL.temps || {};
    updateStatus({
      daemon: INITIAL.daemon,
      mode: INITIAL.mode,
      rpm: INITIAL.rpm,
      pwm: INITIAL.pwm,
      temps: temps,
      oem_running: INITIAL.oem === "1"
    });
    pollStatus();
    setInterval(pollStatus, 2000);
    window.addEventListener("beforeunload", beforeUnload);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
