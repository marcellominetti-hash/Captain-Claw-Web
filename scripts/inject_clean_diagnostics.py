#!/usr/bin/env python3
from pathlib import Path
import sys

site = Path(sys.argv[1]).resolve()
html = site / "claw-web.html"
if not html.exists():
    raise SystemExit("claw-web.html not found")

text = html.read_text(encoding="utf-8")
needle = '<meta charset="UTF-8" />'
script_tag = '<script src="./clean-diagnostics.js"></script>'
if script_tag not in text:
    if needle not in text:
        raise SystemExit("HTML injection anchor not found")
    text = text.replace(needle, needle + "\n    " + script_tag, 1)
text = text.replace("<title>Claw Web</title>", "<title>Capitan Artiglio Clean Baseline</title>", 1)
html.write_text(text, encoding="utf-8", newline="\n")

# index.html is what GitHub Pages serves for the preview folder.
(site / "index.html").write_text(text, encoding="utf-8", newline="\n")

js = r'''(function () {
  "use strict";
  var logs = [];
  var maxLogs = 350;
  var started = Date.now();
  var original = {};

  function ts() {
    return ((Date.now() - started) / 1000).toFixed(3) + "s";
  }

  function safe(v) {
    try {
      if (v instanceof Error) return v.name + ": " + v.message + (v.stack ? "\n" + v.stack : "");
      if (typeof v === "string") return v;
      return JSON.stringify(v);
    } catch (_) {
      try { return String(v); } catch (_) { return "<unprintable>"; }
    }
  }

  function add(level, args) {
    var line = "[" + ts() + "] [" + level + "] " + Array.prototype.map.call(args, safe).join(" ");
    logs.push(line);
    if (logs.length > maxLogs) logs.shift();
    updateBadge(line);
  }

  ["log", "info", "warn", "error"].forEach(function (name) {
    original[name] = console[name] ? console[name].bind(console) : function () {};
    console[name] = function () {
      add(name.toUpperCase(), arguments);
      original[name].apply(console, arguments);
    };
  });

  function mark(msg) {
    add("STAGE", [msg]);
  }
  window.__clawDiagMark = mark;
  window.__clawDiagDump = function () { return logs.join("\n"); };

  window.addEventListener("error", function (e) {
    add("WINDOW_ERROR", [e.message || "error", e.filename || "", e.lineno || 0, e.colno || 0, e.error || ""]);
  });
  window.addEventListener("unhandledrejection", function (e) {
    add("PROMISE_REJECTION", [e.reason || "unknown rejection"]);
  });

  var badge, panel, pre;
  function updateBadge(line) {
    if (!badge) return;
    var shortLine = line.replace(/^\[[^\]]+\]\s*/, "");
    badge.textContent = "DBG " + logs.length + " · " + shortLine.slice(0, 55);
  }

  function buildUi() {
    if (document.getElementById("clawCleanDiagBadge")) return;
    badge = document.createElement("button");
    badge.id = "clawCleanDiagBadge";
    badge.type = "button";
    badge.textContent = "DBG · clean baseline";
    badge.style.cssText = "position:fixed;top:max(8px,env(safe-area-inset-top));right:8px;z-index:2147483647;background:rgba(20,20,20,.92);color:#7CFF7C;border:1px solid #7CFF7C;border-radius:8px;padding:7px 9px;font:11px/1.2 monospace;max-width:72vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";

    panel = document.createElement("div");
    panel.id = "clawCleanDiagPanel";
    panel.style.cssText = "display:none;position:fixed;inset:4%;z-index:2147483647;background:rgba(0,0,0,.97);border:1px solid #7CFF7C;border-radius:10px;padding:10px;color:#d8ffd8;font:11px/1.35 monospace;overflow:auto;";

    var header = document.createElement("div");
    header.style.cssText = "position:sticky;top:0;background:#000;padding:4px 0 8px;display:flex;gap:8px;align-items:center;";
    var title = document.createElement("strong");
    title.textContent = "CLEAN BASELINE DIAGNOSTICS";
    var close = document.createElement("button");
    close.textContent = "Close";
    close.style.cssText = "margin-left:auto;";
    var copy = document.createElement("button");
    copy.textContent = "Copy logs";
    header.appendChild(title);
    header.appendChild(copy);
    header.appendChild(close);

    pre = document.createElement("pre");
    pre.style.cssText = "white-space:pre-wrap;word-break:break-word;margin:0;";
    panel.appendChild(header);
    panel.appendChild(pre);
    document.body.appendChild(badge);
    document.body.appendChild(panel);

    badge.addEventListener("click", function () {
      pre.textContent = logs.join("\n");
      panel.style.display = "block";
    });
    close.addEventListener("click", function () { panel.style.display = "none"; });
    copy.addEventListener("click", function () {
      var txt = logs.join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(function () { copy.textContent = "Copied"; });
      }
    });

    mark("diagnostics-ui-ready");

    var canvas = document.getElementById("canvas");
    if (canvas) {
      canvas.addEventListener("webglcontextlost", function (e) { add("WEBGL", ["context-lost", e.statusMessage || ""]); });
      canvas.addEventListener("webglcontextrestored", function () { add("WEBGL", ["context-restored"]); });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", buildUi);
  else buildUi();

  mark("clean-baseline-script-loaded");
  add("ENV", [navigator.userAgent, location.pathname, "online=" + navigator.onLine]);

  setTimeout(function () {
    try {
      var mem = performance && performance.memory ? {
        used: performance.memory.usedJSHeapSize,
        total: performance.memory.totalJSHeapSize,
        limit: performance.memory.jsHeapSizeLimit
      } : "n/a";
      add("HEALTH", ["10s", mem]);
    } catch (_) {}
  }, 10000);
})();
'''
(site / "clean-diagnostics.js").write_text(js, encoding="utf-8", newline="\n")

marker = """mode=clean-baseline-v1
engine=exact-upstream-published-runtime
primary_archive=CLAW.REZ
custom_archive=ASSETS.ZIP
behavior_patches=none
diagnostics=javascript-console-window-errors-webgl
"""
(site / "CLEAN_BASELINE.txt").write_text(marker, encoding="utf-8", newline="\n")

print("Clean diagnostics injected")
