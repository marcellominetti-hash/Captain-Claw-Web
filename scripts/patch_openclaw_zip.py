#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()

def read(rel):
    return (root / rel).read_text(encoding='utf-8')

def write(rel, text):
    (root / rel).write_text(text, encoding='utf-8', newline='\n')

# Primary resource source: use OpenClaw's ZIP backend when the configured
# original-data archive ends in .zip, otherwise keep REZ behavior.
cpp_path = 'OpenClaw/Engine/GameApp/BaseGameApp.cpp'
cpp = read(cpp_path)
needle = '  IResourceFile *rezArchive = new ResourceRezArchive(rezArchivePath);'
replacement = '''  IResourceFile *rezArchive = nullptr;\n  std::string primaryArchiveLower = rezArchivePath;\n  std::transform(primaryArchiveLower.begin(), primaryArchiveLower.end(),\n                 primaryArchiveLower.begin(),\n                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });\n  if (primaryArchiveLower.size() >= 4 &&\n      primaryArchiveLower.substr(primaryArchiveLower.size() - 4) == ".zip") {\n    LOG("Using ZIP resource archive as primary game-data source: " + rezArchivePath);\n    rezArchive = new ResourceZipArchive(rezArchivePath);\n  } else {\n    rezArchive = new ResourceRezArchive(rezArchivePath);\n  }'''
if needle not in cpp:
    raise SystemExit('BaseGameApp.cpp primary archive construction not found')
cpp = cpp.replace(needle, replacement, 1)
cpp = cpp.replace('XML_ADD_TEXT_ELEMENT("RezArchive", "CLAW.REZ", assets);',
                  'XML_ADD_TEXT_ELEMENT("RezArchive", "CLAW_ASSETS.ZIP", assets);')
write(cpp_path, cpp)

for rel in ['OpenClaw/Engine/GameApp/BaseGameApp.h', 'Build_Release/config.xml']:
    write(rel, read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

# Defer level reset if requested while EventMgr is dispatching.
logic_h_path = 'OpenClaw/Engine/GameApp/BaseGameLogic.h'
logic_h = read(logic_h_path)
logic_h_needle = '    bool m_Proxy;\n    bool m_bRunning;\n'
logic_h_replacement = '    bool m_Proxy;\n    bool m_bRunning;\n    bool m_bResetLevelPending;\n'
if logic_h_needle not in logic_h:
    raise SystemExit('BaseGameLogic.h reset-pending insertion point not found')
logic_h = logic_h.replace(logic_h_needle, logic_h_replacement, 1)
write(logic_h_path, logic_h)

logic_cpp_path = 'OpenClaw/Engine/GameApp/BaseGameLogic.cpp'
logic_cpp = read(logic_cpp_path)
ctor_needle = '    m_bRunning = true;\n'
ctor_replacement = '    m_bRunning = true;\n    m_bResetLevelPending = false;\n'
if ctor_needle not in logic_cpp:
    raise SystemExit('BaseGameLogic.cpp constructor reset-pending insertion point not found')
logic_cpp = logic_cpp.replace(ctor_needle, ctor_replacement, 1)

update_needle = '''void BaseGameLogic::VOnUpdate(uint32 msDiff)\n{\n    m_Lifetime += msDiff;\n'''
update_replacement = '''void BaseGameLogic::VOnUpdate(uint32 msDiff)\n{\n    m_Lifetime += msDiff;\n\n    if (m_bResetLevelPending && !IEventMgr::Get()->VIsUpdating())\n    {\n        m_bResetLevelPending = false;\n        LOG("Executing deferred level reset after EventMgr update");\n        VResetLevel();\n        return;\n    }\n'''
if update_needle not in logic_cpp:
    raise SystemExit('BaseGameLogic.cpp VOnUpdate insertion point not found')
logic_cpp = logic_cpp.replace(update_needle, update_replacement, 1)

reset_needle = '''void BaseGameLogic::VResetLevel()\n{\n    // Handle all pending events before reset\n    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);\n'''
reset_replacement = '''void BaseGameLogic::VResetLevel()\n{\n    if (IEventMgr::Get()->VIsUpdating())\n    {\n        LOG("Deferring level reset until EventMgr update completes");\n        m_bResetLevelPending = true;\n        return;\n    }\n\n    m_bResetLevelPending = false;\n\n    // Handle all pending events before reset\n    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);\n'''
if reset_needle not in logic_cpp:
    raise SystemExit('BaseGameLogic.cpp VResetLevel insertion point not found')
logic_cpp = logic_cpp.replace(reset_needle, reset_replacement, 1)
write(logic_cpp_path, logic_cpp)

# Belt-and-suspenders protection: nested event updates must never abort the
# whole browser runtime. A nested request is skipped; the outer update keeps
# processing and any queued work remains for the next tick.
event_path = 'OpenClaw/Engine/Events/EventMgrImpl.cpp'
event = read(event_path)
event_needle = '''bool EventMgr::VUpdate(unsigned long maxMillis)\n{\n    assert(!m_bIsUpdating && "Attempted to nest updating events - EventMgr::VUpdate inside EventMgr::VUpdate");\n'''
event_replacement = '''bool EventMgr::VUpdate(unsigned long maxMillis)\n{\n    if (m_bIsUpdating)\n    {\n        LOG_WARNING("Nested EventMgr::VUpdate request ignored; outer update is still active");\n        return false;\n    }\n'''
if event_needle not in event:
    raise SystemExit('EventMgrImpl.cpp nested-update assertion not found')
event = event.replace(event_needle, event_replacement, 1)
write(event_path, event)

# Switch browser-side user data from CLAW.REZ to CLAW_ASSETS.ZIP.
loader_path = 'Build_Release/asset-loader.js'
loader = read(loader_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
loader = loader.replace(r'/^CLAW\.REZ$/i', r'/^CLAW_ASSETS\.ZIP$/i')
loader = re.sub(
    r"// CLAW_ASSETS\.ZIP is a Monolith resource archive\..*?const REZ_MAX_SIZE = .*?;\s*",
    lambda _: (
        "// CLAW_ASSETS.ZIP contains the user's extracted Captain Claw game data.\n"
        "const REZ_MIN_SIZE = 10 * 1024 * 1024;\n"
        "const REZ_MAX_SIZE = 512 * 1024 * 1024;\n\n"
    ),
    loader,
    flags=re.S,
)
loader = re.sub(
    r"// Read the header and confirm it carries one of the known-valid signatures\..*?async function hasRezSignature\(file\) \{.*?\n\}\n",
    lambda _: (
        "// Check standard ZIP local-file header bytes: 50 4B 03 04.\n"
        "async function hasZipSignature(file) {\n"
        "  try {\n"
        "    const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());\n"
        "    return head.length === 4 && head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04;\n"
        "  } catch (e) {\n"
        "    console.error('Failed to read CLAW_ASSETS.ZIP header:', e);\n"
        "    return false;\n"
        "  }\n"
        "}\n"
    ),
    loader,
    flags=re.S,
)
loader = loader.replace('hasRezSignature(file)', 'hasZipSignature(file)')
loader = loader.replace('about 113MB', 'the extracted game-data archive')
loader = loader.replace('from the original Captain Claw (1997) game', 'prepared from your Captain Claw game files')
loader = loader.replace('missing the expected archive header', 'missing the expected ZIP header')
zip_name_check = r'/^CLAW_ASSETS\.ZIP$/i'
if loader.count(zip_name_check) < 2:
    raise SystemExit('CLAW_ASSETS.ZIP filename validator was not patched correctly')
if r'/^CLAW\.REZ$/i' in loader:
    raise SystemExit('Legacy CLAW.REZ filename validator still present')
write(loader_path, loader)

game_init_path = 'Build_Release/game-init.js'
game_init = read(game_init_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
init_needle = "    const hasCached = await checkClawRezCached();\n\n    let success;"
init_replacement = """    const hasCached = await checkClawRezCached();\n\n    if (hasCached) {\n      const upload = document.getElementById('assetUpload');\n      if (upload) upload.style.display = 'none';\n    }\n\n    let success;"""
if init_needle not in game_init:
    raise SystemExit('game-init.js cache-check insertion point not found')
game_init = game_init.replace(init_needle, init_replacement, 1)
write(game_init_path, game_init)

asset_storage_path = 'Build_Release/asset-storage.js'
if (root / asset_storage_path).exists():
    write(asset_storage_path, read(asset_storage_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

# Patch first-run HTML, diagnostics, and binary cache-busting.
html_path = 'Build_Release/claw-web.html'
html = read(html_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
html = html.replace(
    'The game requires <strong>CLAW_ASSETS.ZIP</strong> from the original Captain Claw (1997) game.',
    'Import <strong>CLAW_ASSETS.ZIP</strong> once to load the original Captain Claw game data on this device.'
)
html = html.replace('<title>Claw Web</title>', '<title>Capitan Artiglio Web</title>')
html = html.replace('Claw Web', 'Capitan Artiglio Web')
html = html.replace('accept=".REZ,.rez"', 'accept=".ZIP,.zip,application/zip"')
html = html.replace(
    '<section id="assetUpload" class="onboard">',
    '<section id="assetUpload" class="onboard" style="display:flex">',
    1,
)

old_failure_text = '''<p>This usually means the uploaded <strong>CLAW_ASSETS.ZIP</strong> is not the\n           correct file from Captain Claw (1997), or it was corrupted.</p>'''
new_failure_text = '''<p>The OpenClaw engine stopped while loading or running the game.</p>\n        <pre id="loadErrorDetails" style="white-space:pre-wrap;text-align:left;max-height:32vh;overflow:auto;font-size:12px;background:#0b0f14;padding:12px;border-radius:10px;color:#ffb4ab">No diagnostic details yet.</pre>'''
if old_failure_text not in html:
    raise SystemExit('Load-error text block not found')
html = html.replace(old_failure_text, new_failure_text, 1)

module_needle = '      var Module = {\n'
module_replacement = '''      window.__clawDiag = [];\n      window.__pushClawDiag = function (line) {\n        line = String(line == null ? '' : line);\n        window.__clawDiag.push(line);\n        if (window.__clawDiag.length > 120) window.__clawDiag.shift();\n      };\n      var __runtimeBuild = (new URLSearchParams(window.location.search).get('build') || String(Date.now()));\n      var Module = {\n        locateFile: function (path, prefix) {\n          if (path.indexOf('openclaw.wasm') !== -1 || path.indexOf('openclaw.data') !== -1) {\n            var sep = path.indexOf('?') === -1 ? '?' : '&';\n            return (prefix || '') + path + sep + 'v=' + encodeURIComponent(__runtimeBuild);\n          }\n          return (prefix || '') + path;\n        },\n        print: function (text) { console.log(text); window.__pushClawDiag(text); },\n        printErr: function (text) { console.error(text); window.__pushClawDiag(text); },\n'''
if module_needle not in html:
    raise SystemExit('Module bootstrap not found for diagnostics/cache busting')
html = html.replace(module_needle, module_replacement, 1)

html = html.replace(
    "if (window.showLoadError) window.showLoadError();",
    "if (window.showLoadError) window.showLoadError('WASM abort: ' + what);",
    1,
)
show_error_old = '''        window.showLoadError = function () {\n          if (shown) return;\n          shown = true;\n          if (watchdog) { clearTimeout(watchdog); watchdog = null; }\n          if (overlay) overlay.classList.add('visible');\n        };'''
show_error_new = '''        window.showLoadError = function (reason) {\n          if (shown) return;\n          shown = true;\n          if (watchdog) { clearTimeout(watchdog); watchdog = null; }\n          var details = document.getElementById('loadErrorDetails');\n          if (details) {\n            var lines = (window.__clawDiag || []).slice(-18);\n            var msg = reason ? String(reason) : 'Unknown runtime failure';\n            if (lines.length) msg += '\\n\\nRecent engine log:\\n' + lines.join('\\n');\n            details.textContent = msg;\n          }\n          if (overlay) overlay.classList.add('visible');\n        };'''
if show_error_old not in html:
    raise SystemExit('showLoadError controller not found')
html = html.replace(show_error_old, show_error_new, 1)

watchdog_old = '''          watchdog = setTimeout(function () {\n            if (!window.__captainClawWebRunning) window.showLoadError();\n          }, 20000);'''
watchdog_new = '''          watchdog = setTimeout(function () {\n            if (!window.__captainClawWebRunning) {\n              console.warn('[Watchdog] OpenClaw has not reached postRun yet; leaving the canvas visible.');\n            }\n          }, 60000);'''
if watchdog_old not in html:
    raise SystemExit('Load watchdog block not found')
html = html.replace(watchdog_old, watchdog_new, 1)

if 'accept=".ZIP,.zip,application/zip"' not in html:
    raise SystemExit('ZIP file input accept filter was not patched')
if '<section id="assetUpload" class="onboard" style="display:flex">' not in html:
    raise SystemExit('First-run upload card was not made immediately visible')
if 'locateFile:' not in html or '__runtimeBuild' not in html:
    raise SystemExit('WASM/data cache busting was not injected')
write(html_path, html)

for rel in ['Build_Release/config_linux.xml', 'Build_Release/config_linux_release.xml']:
    if (root / rel).exists():
        write(rel, read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

print('OpenClaw ZIP-primary patch applied successfully.')
