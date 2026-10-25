(function () {
  "use strict";
  if (window.__GLUI_BRIDGE__) return;
  window.__GLUI_BRIDGE__ = true;

  var SCREEN_URL = "/cgi-bin/luci/admin/services/glanim/main";
  var FAN_URL = "/cgi-bin/luci/admin/services/glfanctl/main";
  var SCREEN_STATUS = "/cgi-bin/luci/admin/services/glanim/status";
  var STYLE_ID = "glui-bridge-style";
  var CARD_ID = "glui-bridge-screen-card";
  var FAN_BTN_ID = "glui-bridge-fan-btn";

  var ICON_SCREEN =
    '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
    '<rect x="2.5" y="5" width="19" height="12.5" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/>' +
    '<path d="M7 21h10M12 17.5V21" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
    '<path d="M6 9h5M6 12h3M14 9h4M14 12h2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>' +
    "</svg>";
  var ICON_FAN =
    '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<circle cx="12" cy="12" r="2.1" fill="currentColor"/>' +
    '<path d="M12 9.9c0-3 1-5 3.3-5 1.6 0 2.4 1.2 2.4 2.5 0 2.2-2.3 3.5-5.7 2.5z" fill="currentColor"/>' +
    '<path d="M14.1 12c3 0 5 1 5 3.3 0 1.6-1.2 2.4-2.5 2.4-2.2 0-3.5-2.3-2.5-5.7z" fill="currentColor"/>' +
    '<path d="M12 14.1c0 3-1 5-3.3 5-1.6 0-2.4-1.2-2.4-2.5 0-2.2 2.3-3.5 5.7-2.5z" fill="currentColor"/>' +
    '<path d="M9.9 12c-3 0-5-1-5-3.3 0-1.6 1.2-2.4 2.5-2.4 2.2 0 3.5 2.3 2.5 5.7z" fill="currentColor"/>' +
    "</svg>";
  var ICON_EXPAND =
    '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
    '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>' +
    "</svg>";
  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
    '<path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>' +
    "</svg>";
  var ICON_REFRESH =
    '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
    '<path d="M20 11a8 8 0 1 0-2.3 6.3M20 4v7h-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    "</svg>";
  var ICON_OPEN =
    '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
    '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    "</svg>";

  function byId(id) { return document.getElementById(id); }

  function ensureStyle() {
    if (byId(STYLE_ID)) return;
    var link = document.createElement("link");
    link.id = STYLE_ID;
    link.rel = "stylesheet";
    link.href = "/luci-static/resources/glui-bridge/glui-bridge.css";
    document.head.appendChild(link);
  }

  function node(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function openPanel(title, url) {
    closePanel();
    var overlay = node("div", "glui-bridge-overlay");
    overlay.id = "glui-bridge-overlay";
    overlay.innerHTML =
      '<div class="glui-bridge-modal" role="dialog" aria-modal="true">' +
        '<div class="glui-bridge-head">' +
          '<div class="glui-bridge-head-title"><span class="glui-bridge-dot"></span>' +
            '<div><strong>' + title + '</strong><small>LuCI · GL-BE3600</small></div></div>' +
          '<div class="glui-bridge-head-actions">' +
            '<button type="button" class="glui-bridge-iconbtn" data-act="refresh" title="刷新">' + ICON_REFRESH + '</button>' +
            '<a class="glui-bridge-iconbtn" data-act="external" target="_blank" rel="noopener" title="新窗口打开" href="' + url + '">' + ICON_OPEN + '</a>' +
            '<button type="button" class="glui-bridge-iconbtn" data-act="close" title="关闭">' + ICON_CLOSE + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="glui-bridge-body"><iframe title="' + title + '" src="' + url + '"></iframe>' +
          '<div class="glui-bridge-loading"><span></span><em>正在加载插件…</em></div></div>' +
      '</div>';
    document.body.appendChild(overlay);
    document.body.classList.add("glui-bridge-lock");

    var iframe = overlay.querySelector("iframe");
    var loading = overlay.querySelector(".glui-bridge-loading");
    var timer = setTimeout(function () {
      if (loading) loading.classList.add("is-slow");
    }, 12000);

    iframe.addEventListener("load", function () {
      clearTimeout(timer);
      if (loading) loading.style.display = "none";
      try {
        var d = iframe.contentDocument;
        if (d && d.body) {
          d.body.classList.add("glui-embed");
          var st = d.getElementById("glui-embed-style");
          if (!st) {
            st = d.createElement("style");
            st.id = "glui-embed-style";
            d.head.appendChild(st);
          }
          st.textContent =
            "body.glui-embed #header,body.glui-embed #mainmenu,body.glui-embed #footer," +
            "body.glui-embed .main-right>header,body.glui-embed .main-right>footer," +
            "body.glui-embed #tabmenu{display:none!important}" +
            "body.glui-embed .main{height:auto!important;overflow:visible!important}" +
            "body.glui-embed .main-right{float:none!important;width:100%!important;height:auto!important;margin-left:0!important}" +
            "body.glui-embed .main-left{display:none!important}" +
            "body.glui-embed #maincontent{margin:0!important;padding:0!important}" +
            "body.glui-embed #maincontent>.container{margin:0!important;padding:0!important;max-width:none!important}" +
            "body.glui-embed .gl-page{padding:14px 18px 22px!important}";
        }
      } catch (e) { /* cross-document access is guarded; same-origin normally works */ }
    });

    overlay.addEventListener("click", function (ev) {
      var t = ev.target;
      if (t === overlay) { closePanel(); return; }
      var btn = t.closest ? t.closest("[data-act]") : null;
      if (!btn) return;
      var act = btn.getAttribute("data-act");
      if (act === "close") closePanel();
      else if (act === "refresh") {
        if (loading) { loading.style.display = ""; loading.classList.remove("is-slow"); }
        iframe.src = url + (url.indexOf("?") > -1 ? "&" : "?") + "_gli=" + Date.now();
      }
    });
    setTimeout(function () {
      var b = overlay.querySelector('[data-act="close"]');
      if (b) b.focus();
    }, 30);
  }

  function closePanel() {
    var o = byId("glui-bridge-overlay");
    if (o) o.parentNode.removeChild(o);
    document.body.classList.remove("glui-bridge-lock");
  }

  function modeLabel(mode) {
    var map = {
      gif: "GIF 循环", still: "静态图片", slideshow: "幻灯片",
      dashboard: "系统面板", custom: "自定义面板"
    };
    return map[mode] || (mode || "—");
  }

  function setBadge(card, text, ok) {
    var b = card.querySelector(".glui-bridge-badge");
    if (!b) return;
    b.textContent = text;
    b.classList.toggle("is-on", !!ok);
  }

  function fillStatus(card) {
    fetch(SCREEN_STATUS + "?_gli=" + Date.now(), { credentials: "same-origin", cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (s) {
        var daemon = s && String(s.daemon) === "1";
        setBadge(card, daemon ? "运行中" : "未启用", daemon);
        var mode = card.querySelector("[data-k='mode']");
        var frames = card.querySelector("[data-k='frames']");
        var daemonEl = card.querySelector("[data-k='daemon']");
        if (mode) mode.textContent = modeLabel(s && s.mode);
        if (frames) {
          frames.textContent = (s && (s.mode === "custom" || s.mode === "dashboard"))
            ? "—"
            : (s && s.frame_count != null ? String(s.frame_count) : "0");
        }
        if (daemonEl) daemonEl.textContent = daemon ? "运行中" : "已停止";
      })
      .catch(function () {
        setBadge(card, "已安装", false);
        var d = card.querySelector("[data-k='daemon']");
        if (d) d.textContent = "需 LuCI 登录";
        if (!card.dataset.retried) {
          card.dataset.retried = "1";
          setTimeout(function () { if (document.body.contains(card)) fillStatus(card); }, 2500);
        }
      });
  }

  function mountScreenCard() {
    if (byId(CARD_ID)) return;
    var wrap = document.querySelector(".display-wrapper");
    if (!wrap) return;
    var main = wrap.querySelector(".card-main");
    if (!main) return;

    var card = node("section", "glui-bridge-card");
    card.id = CARD_ID;
    card.innerHTML =
      '<div class="glui-bridge-card-head">' +
        '<div class="glui-bridge-card-title"><span class="glui-bridge-appicon">' + ICON_SCREEN + '</span>' +
          '<div><h3>屏幕自定义</h3><p>Screen Custom · 284 × 76 ST7789</p></div></div>' +
        '<span class="glui-bridge-badge">已安装</span>' +
      '</div>' +
      '<p class="glui-bridge-desc">在长条屏上显示 GIF、静态图片、幻灯片、系统面板或自定义布局；支持实时数据、触屏翻页与图片工坊。</p>' +
      '<div class="glui-bridge-meta">' +
        '<span>模式 <b data-k="mode">—</b></span>' +
        '<span>帧/包 <b data-k="frames">—</b></span>' +
        '<span>守护进程 <b data-k="daemon">—</b></span>' +
      '</div>' +
      '<div class="glui-bridge-actions">' +
        '<button type="button" class="glui-bridge-primary" data-open>打开屏幕插件</button>' +
        '<a class="glui-bridge-link" href="' + SCREEN_URL + '" target="_blank" rel="noopener">在 LuCI 打开 ↗</a>' +
      '</div>';
    main.parentNode.insertBefore(card, main.nextSibling);

    var open = card.querySelector("[data-open]");
    if (open) open.addEventListener("click", function () { openPanel("屏幕自定义", SCREEN_URL); });
    fillStatus(card);
  }

  function mountFanButton() {
    if (byId(FAN_BTN_ID)) return;
    var cpu = document.querySelector(".cpu-card-wrapper");
    if (!cpu) return;
    var host = cpu.querySelector(".fan-setting-wrapper") || cpu.querySelector(".cpu-title");
    if (!host) return;
    var btn = node("button", "glui-bridge-fan-btn");
    btn.id = FAN_BTN_ID;
    btn.type = "button";
    btn.title = "风扇控制扩展";
    btn.setAttribute("aria-label", "风扇控制扩展");
    btn.innerHTML = ICON_EXPAND;
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      openPanel("风扇控制", FAN_URL);
    });
    host.insertBefore(btn, host.firstChild);
  }

  function tick() {
    var hash = location.hash || "";
    if (hash.indexOf("#/display") === 0) mountScreenCard();
    if (hash.indexOf("#/overview") === 0) mountFanButton();
  }

  var timer = 0;
  function schedule() {
    if (timer) return;
    timer = setTimeout(function () { timer = 0; tick(); }, 80);
  }

  function boot() {
    ensureStyle();
    tick();
    window.addEventListener("hashchange", function () { setTimeout(tick, 60); });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && byId("glui-bridge-overlay")) closePanel();
    });
    var app = byId("app") || document.body;
    if (window.MutationObserver) {
      new MutationObserver(schedule).observe(app, { childList: true, subtree: true });
    }
    setInterval(tick, 1200);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
