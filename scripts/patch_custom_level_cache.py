#!/usr/bin/env python3
from pathlib import Path

root = Path('.')
shared = root / 'OpenClaw/Engine/SharedDefines.h'
app = root / 'OpenClaw/Engine/GameApp/BaseGameApp.cpp'

s = shared.read_text(encoding='utf-8', errors='ignore')
needle = '#define CUSTOM_RESOURCE   "ASSETS_ZIP"'
if needle not in s:
    raise SystemExit('CUSTOM_RESOURCE marker not found')
s = s.replace(needle, needle + '\n#define CUSTOM_LEVEL_RESOURCE "CUSTOM_LEVEL_ZIP"', 1)
shared.write_text(s, encoding='utf-8')

a = app.read_text(encoding='utf-8', errors='ignore')
needle = '''  m_pResourceMgr = new ResourceMgrImpl();
  // Custom cache first so ASSETS.ZIP can override CLAW.REZ assets
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''
replacement = '''  // Optional per-level override archive. The Android Collection launcher writes
  // the selected package to /CUSTOM_LEVEL.ZIP before main() starts. Its cache
  // is registered first so a custom WWD/assets override ASSETS.ZIP and CLAW.REZ.
  std::shared_ptr<ResourceCache> pCustomLevelCache;
  IResourceFile *pCustomLevelArchive = new ResourceZipArchive("CUSTOM_LEVEL.ZIP");
  pCustomLevelCache.reset(new ResourceCache(50, pCustomLevelArchive, CUSTOM_LEVEL_RESOURCE));
  bool customLevelReady = pCustomLevelCache->Init();
  if (!customLevelReady) {
    pCustomLevelCache.reset();
    LOG("No CUSTOM_LEVEL.ZIP mounted; using original campaign resources.");
  } else {
    pCustomLevelCache->RegisterLoader(DefaultResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(WavResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(MidiResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(PidResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(AniResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(PalResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(WwdResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(XmlResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(PcxResourceLoader::Create());
    pCustomLevelCache->RegisterLoader(PngResourceLoader::Create());
    LOG("Mounted CUSTOM_LEVEL.ZIP override archive.");
  }

  m_pResourceMgr = new ResourceMgrImpl();
  if (pCustomLevelCache) m_pResourceMgr->VAddResourceCache(pCustomLevelCache);
  // ASSETS.ZIP precedes CLAW.REZ, preserving existing override behavior.
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''
if needle not in a:
    raise SystemExit('Resource manager insertion marker not found')
a = a.replace(needle, replacement, 1)
app.write_text(a, encoding='utf-8')
print('Custom-level cache patch applied.')
