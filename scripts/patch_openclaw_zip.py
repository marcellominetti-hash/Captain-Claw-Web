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
if 'accept=".ZIP,.zip,application/zip"' not in html:
    raise SystemExit('ZIP file input accept filter was not patched')
if '<section id="assetUpload" class="onboard" style="display:flex">' not in html:
    raise SystemExit('First-run upload card was not made immediately visible')
write(html_path, html)

for rel in ['Build_Release/config_linux.xml', 'Build_Release/config_linux_release.xml']:
    if (root / rel).exists():
        write(rel, read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

print('OpenClaw ZIP-primary patch applied successfully.')
