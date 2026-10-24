#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_custom_levels.py <upstream-root>")

root = Path(sys.argv[1])


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    if old not in text:
        raise RuntimeError(f"expected block not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}, got {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", errors="surrogateescape")

# 1) Give the transient per-level archive its own cache name.
shared = root / "OpenClaw/Engine/SharedDefines.h"
replace_once(
    shared,
    '#define ORIGINAL_RESOURCE "CLAW_REZ"\n#define CUSTOM_RESOURCE   "ASSETS_ZIP"',
    '#define ORIGINAL_RESOURCE     "CLAW_REZ"\n#define CUSTOM_RESOURCE       "ASSETS_ZIP"\n#define CUSTOM_LEVEL_RESOURCE "CUSTOM_LEVEL_ZIP"',
)

# 2) Register CUSTOM_LEVEL.ZIP ahead of ASSETS.ZIP and CLAW.REZ when present.
app = root / "OpenClaw/Engine/GameApp/BaseGameApp.cpp"
replace_once(app, '#include <cctype>\n', '#include <cctype>\n#include <fstream>\n')

old_cache_block = '''  pCustomCache->RegisterLoader(DefaultResourceLoader::Create());
  pCustomCache->RegisterLoader(XmlResourceLoader::Create());
  pCustomCache->RegisterLoader(WavResourceLoader::Create());
  pCustomCache->RegisterLoader(PcxResourceLoader::Create());
  pCustomCache->RegisterLoader(PngResourceLoader::Create());

  m_pResourceMgr = new ResourceMgrImpl();
  // Custom cache first so ASSETS.ZIP can override CLAW.REZ assets
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''

new_cache_block = '''  pCustomCache->RegisterLoader(DefaultResourceLoader::Create());
  pCustomCache->RegisterLoader(XmlResourceLoader::Create());
  pCustomCache->RegisterLoader(WavResourceLoader::Create());
  pCustomCache->RegisterLoader(PcxResourceLoader::Create());
  pCustomCache->RegisterLoader(PngResourceLoader::Create());

  // Optional transient archive used by the Android Custom Levels library.
  // It contains exactly one selected WWD plus that level's private overrides.
  std::shared_ptr<ResourceCache> pCustomLevelCache;
  {
    std::ifstream customLevelProbe("CUSTOM_LEVEL.ZIP", std::ios::binary);
    if (customLevelProbe.good()) {
      customLevelProbe.close();
      IResourceFile *pCustomLevelArchive = new ResourceZipArchive("CUSTOM_LEVEL.ZIP");
      pCustomLevelCache.reset(new ResourceCache(75, pCustomLevelArchive, CUSTOM_LEVEL_RESOURCE));
      if (!pCustomLevelCache->Init()) {
        LOG_ERROR("Failed to initialize CUSTOM_LEVEL.ZIP");
        return false;
      }

      // A custom level may override any resource family, including its WWD,
      // palette, tiles, animations, sounds and XML definitions.
      pCustomLevelCache->RegisterLoader(DefaultResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(XmlResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(WwdResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(PalResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(PidResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(AniResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(WavResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(MidiResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(PcxResourceLoader::Create());
      pCustomLevelCache->RegisterLoader(PngResourceLoader::Create());
      LOG("CUSTOM_LEVEL.ZIP detected; custom level override cache enabled");
    }
  }

  m_pResourceMgr = new ResourceMgrImpl();
  // Priority: selected custom level -> web overrides -> original CLAW.REZ.
  if (pCustomLevelCache) m_pResourceMgr->VAddResourceCache(pCustomLevelCache);
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''
replace_once(app, old_cache_block, new_cache_block)

# 3) If JS writes CUSTOM_LEVEL.NUM before boot, skip the normal menu and load
#    the matching original level slot. The selected WWD in CUSTOM_LEVEL.ZIP
#    overrides /LEVELN/WORLDS/WORLD.WWD.
logic = root / "OpenClaw/Engine/GameApp/BaseGameLogic.cpp"
old_init = '''        case GameState_Initializing:
        {
#ifdef ANDROID
            VChangeState(GameState_LoadingLevel);
#else
            if (g_pApp->GetDebugOptions()->bSkipMenu)
            {
                VChangeState(GameState_LoadingLevel);
            }
            else
            {
                // Try to play intro movie
                VPlayCutscene("videos/INTRO.mp4");
                // If it failed/skipped immediately, it will fall through or we check state
                if (m_GameState == GameState_Initializing)
                {
                    VChangeState(GameState_Menu);
                }
            }
#endif
            break;
        }
'''
new_init = '''        case GameState_Initializing:
        {
#ifdef __EMSCRIPTEN__
            // Android Collection wrapper writes this tiny file before loading
            // openclaw.js.  It lets custom levels reuse the correct LEVEL1..14
            // engine rules without altering normal browser behavior.
            std::ifstream customLevelNumberFile("CUSTOM_LEVEL.NUM");
            int customLevelNumber = 0;
            if (customLevelNumberFile.good() &&
                (customLevelNumberFile >> customLevelNumber) &&
                customLevelNumber >= 1 && customLevelNumber <= 14)
            {
                LOG("Starting selected custom level in base slot " + ToStr(customLevelNumber));
                m_pCurrentLevel.reset(new LevelData(customLevelNumber, false, 0));
                VChangeState(GameState_LoadingLevel);
                break;
            }
#endif
#ifdef ANDROID
            VChangeState(GameState_LoadingLevel);
#else
            if (g_pApp->GetDebugOptions()->bSkipMenu)
            {
                VChangeState(GameState_LoadingLevel);
            }
            else
            {
                // Try to play intro movie
                VPlayCutscene("videos/INTRO.mp4");
                // If it failed/skipped immediately, it will fall through or we check state
                if (m_GameState == GameState_Initializing)
                {
                    VChangeState(GameState_Menu);
                }
            }
#endif
            break;
        }
'''
replace_once(logic, old_init, new_init)

# 4) Custom levels may not have campaign save entries.  Use clean default
#    player stats rather than asserting, while leaving campaign behavior intact.
old_checkpoint = '''    const CheckpointSave* pCheckpointSave = m_pGameSaveMgr->GetCheckpointSave(
        m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
    assert(pCheckpointSave != NULL);

    loadingProgress = 95.0f;
'''
new_checkpoint = '''    const CheckpointSave* pCheckpointSave = m_pGameSaveMgr->GetCheckpointSave(
        m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
    CheckpointSave customLevelDefaultSave;
    if (pCheckpointSave == NULL && g_pApp->GetResourceMgr()->VHasResourceCache(CUSTOM_LEVEL_RESOURCE))
    {
        customLevelDefaultSave.checkpointIdx = 0;
        customLevelDefaultSave.score = 0;
        customLevelDefaultSave.health = 100;
        customLevelDefaultSave.lives = 6;
        customLevelDefaultSave.bulletCount = 10;
        customLevelDefaultSave.magicCount = 5;
        customLevelDefaultSave.dynamiteCount = 3;
        pCheckpointSave = &customLevelDefaultSave;
        LOG("Using default player stats for custom level");
    }
    assert(pCheckpointSave != NULL);

    loadingProgress = 95.0f;
'''
replace_once(logic, old_checkpoint, new_checkpoint)

# 5) For a custom WWD, checkpoint zero must be the WWD's own startX/startY,
#    not the hard-coded campaign spawn.  Later checkpoint flags already update
#    m_CurrentSpawnPosition through the existing checkpoint event path.
old_spawn = '''    // Set claw to spawn location
    m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
    pEventMgr->VTriggerEvent(IEventDataPtr(new EventData_Teleport_Actor(clawId, m_CurrentSpawnPosition)));
'''
new_spawn = '''    // Set Claw to the correct initial spawn.  Campaign uses the existing
    // checkpoint table; custom levels use the Spawn coordinates embedded in
    // their WWD (the actor was already created at those coordinates).
    if (g_pApp->GetResourceMgr()->VHasResourceCache(CUSTOM_LEVEL_RESOURCE))
    {
        TiXmlElement* pSpawnElem = pLevelProperties->FirstChildElement("Spawn");
        int spawnX = 0;
        int spawnY = 0;
        if (pSpawnElem &&
            pSpawnElem->Attribute("x", &spawnX) &&
            pSpawnElem->Attribute("y", &spawnY))
        {
            m_CurrentSpawnPosition = Point(spawnX, spawnY);
            pEventMgr->VTriggerEvent(IEventDataPtr(new EventData_Teleport_Actor(clawId, m_CurrentSpawnPosition)));
        }
        else
        {
            LOG_WARNING("Custom level has no Spawn node; keeping actor WWD position");
        }
    }
    else
    {
        m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
        pEventMgr->VTriggerEvent(IEventDataPtr(new EventData_Teleport_Actor(clawId, m_CurrentSpawnPosition)));
    }
'''
replace_once(logic, old_spawn, new_spawn)

print("custom-level engine patch applied")
