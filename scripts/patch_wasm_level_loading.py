#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'OpenClaw/Engine/GameApp/BaseGameLogic.cpp'
text = path.read_text(encoding='utf-8')

# The browser port already supports lazy resource loading, but upstream still
# performs two synchronous full-level Preload() passes before/during VLoadGame.
# On mobile WASM that blocks the main thread before the loading screen can even
# be presented. Keep native behaviour, skip these bulk passes on Emscripten and
# let the existing loaders fetch resources on demand while VLoadGame progresses.
first = '''    // Preload level resources\n    std::string levelPath = "/LEVEL" + ToStr(m_pCurrentLevel->GetLevelNumber()) + "/*";\n    g_pApp->GetResourceCache()->Preload(levelPath, NULL);\n'''
first_repl = '''    // Native builds may bulk-preload. In WebAssembly this is intentionally\n    // skipped: ResourceCache::Preload is synchronous and blocks the browser\n    // main thread before the loading screen can be shown. All resource loaders\n    // already load missing assets lazily on demand.\n#ifndef __EMSCRIPTEN__\n    std::string levelPath = "/LEVEL" + ToStr(m_pCurrentLevel->GetLevelNumber()) + "/*";\n    g_pApp->GetResourceCache()->Preload(levelPath, NULL);\n#else\n    LOG("[PORT LOAD] Skipping blocking VLoadGame full-level preload (WASM)");\n#endif\n'''
if first not in text:
    raise SystemExit('VLoadGame preload block not found')
text = text.replace(first, first_repl, 1)

second = '''        // Lazy loading: Preload level-specific assets on-demand\n        LOG("Loading assets for " + levelName + "...");\n        std::string levelAssetPath = "/" + levelName + "/*";\n        g_pApp->GetResourceCache()->Preload(levelAssetPath, NULL);\n        LOG("Level assets loaded for " + levelName);\n'''
second_repl = '''        // Do not bulk-preload in the browser. The old synchronous pass scans\n        // and inflates hundreds of ZIP entries while the previous menu has\n        // already been cleared, producing an apparent permanent black screen\n        // on mobile. VLoadGame below performs progressive lazy loading instead.\n#ifndef __EMSCRIPTEN__\n        LOG("Loading assets for " + levelName + "...");\n        std::string levelAssetPath = "/" + levelName + "/*";\n        g_pApp->GetResourceCache()->Preload(levelAssetPath, NULL);\n        LOG("Level assets loaded for " + levelName);\n#else\n        LOG("[PORT LOAD] Starting " + levelName + " without blocking bulk preload");\n#endif\n'''
if second not in text:
    raise SystemExit('VChangeState preload block not found')
text = text.replace(second, second_repl, 1)

# Add high-signal milestones so a future phone screenshot can identify exactly
# where loading stopped without remote DevTools.
text = text.replace(
    '    WapWwd* pWwd = WwdResourceLoader::LoadAndReturnWwd(xmlLevelResource);\n',
    '    LOG("[PORT LOAD] Loading WWD: " + std::string(xmlLevelResource));\n'
    '    WapWwd* pWwd = WwdResourceLoader::LoadAndReturnWwd(xmlLevelResource);\n'
    '    LOG("[PORT LOAD] WWD loaded");\n',
    1,
)
text = text.replace(
    '    TiXmlElement* pXmlLevelRoot = WwdToXml(pWwd, m_pCurrentLevel->GetLevelNumber());\n',
    '    LOG("[PORT LOAD] Converting WWD to level XML");\n'
    '    TiXmlElement* pXmlLevelRoot = WwdToXml(pWwd, m_pCurrentLevel->GetLevelNumber());\n'
    '    LOG("[PORT LOAD] WWD conversion complete");\n',
    1,
)
text = text.replace(
    '    std::string palettePath = pLevelProperties->FirstChildElement("Palette")->GetText();\n',
    '    LOG("[PORT LOAD] Loading level palette");\n'
    '    std::string palettePath = pLevelProperties->FirstChildElement("Palette")->GetText();\n',
    1,
)
text = text.replace(
    '    loadingProgress = 95.0f;\n',
    '    LOG("[PORT LOAD] Actor construction complete");\n'
    '    loadingProgress = 95.0f;\n',
    1,
)
text = text.replace(
    '    LOG("Level loaded !");\n',
    '    LOG("[PORT LOAD] Level load complete");\n'
    '    LOG("Level loaded !");\n',
    1,
)

if text.count('[PORT LOAD]') < 7:
    raise SystemExit('Expected loading diagnostics were not injected')

path.write_text(text, encoding='utf-8', newline='\n')
print('WASM non-blocking level-loading patch applied successfully.')
