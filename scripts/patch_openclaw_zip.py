#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()


def read(rel):
    return (root / rel).read_text(encoding='utf-8')


def write(rel, text):
    p = root / rel
    p.write_text(text, encoding='utf-8', newline='\n')

# 1) Make the primary/original resource cache accept ZIP archives in addition
# to the original Monolith REZ container. ResourceZipArchive is already part of
# OpenClaw; this only selects the right backend from the filename extension.
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

# 2) Default/config archive name.
for rel in [
    'OpenClaw/Engine/GameApp/BaseGameApp.h',
    'Build_Release/config.xml',
]:
    text = read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
    write(rel, text)

# 3) Browser loader: retain its IndexedDB/offline architecture, but store and
# mount the extracted-assets ZIP instead of CLAW.REZ.
loader_path = 'Build_Release/asset-loader.js'
loader = read(loader_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
loader = loader.replace(r'/^CLAW\\.REZ$/i', r'/^CLAW_ASSETS\\.ZIP$/i')

# Replace legacy REZ size/signature constants with a ZIP-safe range.
loader = re.sub(
    r"// CLAW_ASSETS\.ZIP is a Monolith resource archive\..*?const REZ_MAX_SIZE = .*?;\s*",
    "// CLAW_ASSETS.ZIP contains the user's extracted Captain Claw game data.\n"
    "// Keep validation deliberately structural: filename, sensible size and ZIP magic.\n"
    "const REZ_MIN_SIZE = 10 * 1024 * 1024;\n"
    "const REZ_MAX_SIZE = 512 * 1024 * 1024;\n\n",
    loader,
    flags=re.S,
)

loader = re.sub(
    r"// Read the header and confirm it carries one of the known-valid signatures\..*?async function hasRezSignature\(file\) \{.*?\n\}\n",
    "// Check the standard ZIP local-file header (PK\\x03\\x04).\n"
    "async function hasZipSignature(file) {\n"
    "  try {\n"
    "    const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());\n"
    "    return head.length === 4 && head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04;\n"
    "  } catch (e) {\n"
    "    console.error('Failed to read CLAW_ASSETS.ZIP header:', e);\n"
    "    return false;\n"
    "  }\n"
    "}\n",
    loader,
    flags=re.S,
)
loader = loader.replace('hasRezSignature(file)', 'hasZipSignature(file)')
loader = loader.replace('about 113MB', 'the extracted game-data archive')
loader = loader.replace('from the original Captain Claw (1997) game', 'prepared from your Captain Claw game files')
loader = loader.replace('missing the expected archive header', 'missing the expected ZIP header')
write(loader_path, loader)

# 4) First-run UI and branding. Existing IDs/functions are intentionally kept
# so upstream game-init.js needs no invasive changes.
html_path = 'Build_Release/claw-web.html'
html = read(html_path).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP')
html = html.replace('The game requires <strong>CLAW_ASSETS.ZIP</strong> from the original Captain Claw (1997) game.',
                    'Import <strong>CLAW_ASSETS.ZIP</strong> once to load the original Captain Claw game data on this device.')
html = html.replace('<title>Claw Web</title>', '<title>Capitan Artiglio Web</title>')
html = html.replace('Claw Web', 'Capitan Artiglio Web')
write(html_path, html)

# The source branch may include docs/config variants. Keep them coherent when present.
for rel in ['Build_Release/config_linux.xml', 'Build_Release/config_linux_release.xml']:
    p = root / rel
    if p.exists():
        write(rel, read(rel).replace('CLAW.REZ', 'CLAW_ASSETS.ZIP'))

print('OpenClaw ZIP-primary patch applied successfully.')
