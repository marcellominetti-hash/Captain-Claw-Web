#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()

def read(rel):
    return (root / rel).read_text(encoding='utf-8')

def write(rel, text):
    (root / rel).write_text(text, encoding='utf-8', newline='\n')

# Primary resource source: use OpenClaw's existing ZIP backend when the
# configured original-data archive ends in .zip, otherwise keep REZ behavior.
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

# OpenClaw's RequestResetLevelDelegate runs while EventMgr::VUpdate is already
# dispatching an event. Upstream VResetLevel() immediately calls VUpdate() again,
# which asserts on WebAssembly as a nested event update. Defer the reset until
# BaseGameLogic::VOnUpdate, which runs after the event manager finishes the tick.
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
update_replacement = '''void BaseGameLogic::VOnUpdate(uint32 msDiff)\n{\n    m_Lifetime += msDiff;\n\n    // A level-reset request can arrive as an EventMgr delegate. Running the\n    // reset from inside EventMgr::VUpdate recursively calls VUpdate and aborts\n    // in WASM. Execute it here, after the event-manager phase of the frame.\n    if (m_bResetLevelPending && !IEventMgr::Get()->VIsUpdating())\n    {\n        m_bResetLevelPending = false;\n        LOG("Executing deferred level reset after EventMgr update");\n        VResetLevel();\n        return;\n    }\n'''
if update_needle not in logic_cpp:
    raise SystemExit('BaseGameLogic.cpp VOnUpdate insertion point not found')
logic_cpp = logic_cpp.replace(update_needle, update_replacement, 1)

reset_needle = '''void BaseGameLogic::VResetLevel()\n{\n    // Handle all pending events before reset\n    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);\n'''
reset_replacement = '''void BaseGameLogic::VResetLevel()\n{\n    // RequestResetLevelDelegate is itself dispatched by EventMgr::VUpdate.\n    // Never recurse into the event manager; defer one frame instead.\n    if (IEventMgr::Get()->VIsUpdating())\n    {\n        LOG("Deferring level reset until EventMgr update completes");\n        m_bResetLevelPending = true;\n        return;\n    }\n\n    m_bResetLevelPending = false;\n\n    // Handle all pending events before reset\n    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);\n'''
if reset_needle not in logic_cpp:
    raise SystemExit('BaseGameLogic.cpp VResetLevel insertion point not found')
logic_cpp = logic_cpp.replace(reset_needle, reset_replacement, 1)

if 'm_bResetLevelPending = true;' not in logic_cpp or 'Executing deferred level reset after EventMgr update' not in logic_cpp:
    raise SystemExit('Deferred level-reset patch was not applied')
write(logic_cpp_path, logic_cpp)

# Keep the upstream IndexedDB/offline loader, but switch its user-provided file
# from CLAW.REZ to an extracted-data ZIP.
loader_path = 'Build_Release/asset-loader.js'
loader = read(loader_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')

# The JS source escapes the dot with ONE backslash. The previous patch looked
# for two backslashes, so Android kept validating CLAW_ASSETS.ZIP as CLAW.REZ.
loader = loader.replace(r'/^CLAW\.REZ$/i', r'/^CLAW_ASSETS\.ZIP$/i')

loader = re.sub(
    r"// CLAW_ASSETS\.ZIP is a Monolith resource archive\..*?const REZ_MAX_SIZE = .*?;\s*",
    lambda _: (
        "// CLAW_ASSETS.ZIP contains the user's extracted Captain Claw game data.\n"
        "// Validate filename, a sensible size range and standard ZIP magic.\n"
        "const REZ_MIN_SIZE = 10 * 1024 * 1024;\n"
        "const REZ_MAX_SIZE = 512 * 1024 * 1024;\n\n"
    ),
    loader,
    flags=re.S,
)

loader = re.sub(
    r"// Read the header and confirm it carries one of the known-valid signatures\..*?async function hasRezSignature\(file\) \{.*?\n\}\n",
    lambda _: (
        "// Check the standard ZIP local-file header bytes: 50 4B 03 04.\n"
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

# Fail the build rather than shipping a first-run picker that silently rejects
# the ZIP. There are two filename checks: selection and upload re-validation.
zip_name_check = r'/^CLAW_ASSETS\.ZIP$/i'
if loader.count(zip_name_check) < 2:
    raise SystemExit('CLAW_ASSETS.ZIP filename validator was not patched correctly')
if r'/^CLAW\.REZ$/i' in loader:
    raise SystemExit('Legacy CLAW.REZ filename validator still present')
write(loader_path, loader)

# Keep browser-side cache checks/storage aligned with the new filename.
game_init_path = 'Build_Release/game-init.js'
game_init = read(game_init_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')

# On first run the upstream upload card starts hidden and only appears after an
# async IndexedDB bootstrap. If that bootstrap stalls/fails on mobile, the user
# sees a totally black page. Our HTML shows the picker immediately; hide it only
# when the ZIP is already cached, then continue with the normal play overlay.
init_needle = "    const hasCached = await checkClawRezCached();\n\n    let success;"
init_replacement = """    const hasCached = await checkClawRezCached();\n\n    if (hasCached) {\n      const upload = document.getElementById('assetUpload');\n      if (upload) upload.style.display = 'none';\n    }\n\n    let success;"""
if init_needle not in game_init:
    raise SystemExit('game-init.js cache-check insertion point not found')
game_init = game_init.replace(init_needle, init_replacement, 1)
write(game_init_path, game_init)

asset_storage_path = 'Build_Release/asset-storage.js'
if (root / asset_storage_path).exists():
    write(asset_storage_path, read(asset_storage_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

# First-run page: same upstream UI and game bridges, but the ZIP picker is
# visible immediately so a failed storage/bootstrap step can never look like a
# dead black page.
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

# The upstream recovery overlay says every runtime failure is a bad game file,
# which is misleading once we use a ZIP backend. Make it a real diagnostic
# screen and show the actual WASM abort plus the last engine log lines.
old_failure_text = '''<p>This usually means the uploaded <strong>CLAW_ASSETS.ZIP</strong> is not the
           correct file from Captain Claw (1997), or it was corrupted.</p>'''
new_failure_text = '''<p>The OpenClaw engine stopped while loading or running the game.</p>
        <pre id="loadErrorDetails" style="white-space:pre-wrap;text-align:left;max-height:32vh;overflow:auto;font-size:12px;background:#0b0f14;padding:12px;border-radius:10px;color:#ffb4ab">No diagnostic details yet.</pre>'''
if old_failure_text not in html:
    raise SystemExit('Load-error text block not found')
html = html.replace(old_failure_text, new_failure_text, 1)

# Capture stdout/stderr produced by Emscripten/OpenClaw. ResourceZipArchive
# already logs ZIP lookup misses, so this gives us the exact missing resource
# on a phone without requiring DevTools.
module_needle = '      var Module = {\n'
module_replacement = '''      window.__clawDiag = [];
      window.__pushClawDiag = function (line) {
        line = String(line == null ? '' : line);
        window.__clawDiag.push(line);
        if (window.__clawDiag.length > 120) window.__clawDiag.shift();
      };
      var Module = {
        print: function (text) { console.log(text); window.__pushClawDiag(text); },
        printErr: function (text) { console.error(text); window.__pushClawDiag(text); },
'''
if module_needle not in html:
    raise SystemExit('Module bootstrap not found for diagnostics')
html = html.replace(module_needle, module_replacement, 1)

html = html.replace(
    "if (window.showLoadError) window.showLoadError();",
    "if (window.showLoadError) window.showLoadError('WASM abort: ' + what);",
    1,
)

show_error_old = '''        window.showLoadError = function () {
          if (shown) return;
          shown = true;
          if (watchdog) { clearTimeout(watchdog); watchdog = null; }
          if (overlay) overlay.classList.add('visible');
        };'''
show_error_new = '''        window.showLoadError = function (reason) {
          if (shown) return;
          shown = true;
          if (watchdog) { clearTimeout(watchdog); watchdog = null; }
          var details = document.getElementById('loadErrorDetails');
          if (details) {
            var lines = (window.__clawDiag || []).slice(-18);
            var msg = reason ? String(reason) : 'Unknown runtime failure';
            if (lines.length) msg += '\\n\\nRecent engine log:\\n' + lines.join('\\n');
            details.textContent = msg;
          }
          if (overlay) overlay.classList.add('visible');
        };'''
if show_error_old not in html:
    raise SystemExit('showLoadError controller not found')
html = html.replace(show_error_old, show_error_new, 1)

# The 20-second watchdog can produce a false "bad file" overlay on slower
# Android devices even while the game is already drawing. Keep a warning for
# diagnostics but never cover a working game; genuine aborts/errors still show.
watchdog_old = '''          watchdog = setTimeout(function () {
            if (!window.__captainClawWebRunning) window.showLoadError();
          }, 20000);'''
watchdog_new = '''          watchdog = setTimeout(function () {
            if (!window.__captainClawWebRunning) {
              console.warn('[Watchdog] OpenClaw has not reached postRun yet; leaving the canvas visible.');
            }
          }, 60000);'''
if watchdog_old not in html:
    raise SystemExit('Load watchdog block not found')
html = html.replace(watchdog_old, watchdog_new, 1)

if 'accept=".ZIP,.zip,application/zip"' not in html:
    raise SystemExit('ZIP file input accept filter was not patched')
if '<section id="assetUpload" class="onboard" style="display:flex">' not in html:
    raise SystemExit('First-run upload card was not made immediately visible')
if 'id="loadErrorDetails"' not in html or 'window.__clawDiag' not in html:
    raise SystemExit('Runtime diagnostics were not injected')
write(html_path, html)

for rel in ['Build_Release/config_linux.xml', 'Build_Release/config_linux_release.xml']:
    if (root / rel).exists():
        write(rel, read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

print('OpenClaw ZIP-primary patch applied successfully.')
