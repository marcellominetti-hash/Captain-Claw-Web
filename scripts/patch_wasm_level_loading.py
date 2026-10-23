#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
logic_path = root / 'OpenClaw/Engine/GameApp/BaseGameLogic.cpp'
text = logic_path.read_text(encoding='utf-8')

# The browser port already supports lazy resource loading, but upstream still
# performs two synchronous full-level Preload() passes before/during VLoadGame.
# Keep native behaviour; on WASM load resources on demand.
first = '''    // Preload level resources\n    std::string levelPath = "/LEVEL" + ToStr(m_pCurrentLevel->GetLevelNumber()) + "/*";\n    g_pApp->GetResourceCache()->Preload(levelPath, NULL);\n'''
first_repl = '''    // Native builds may bulk-preload. In WebAssembly this is intentionally\n    // skipped: ResourceCache::Preload is synchronous and blocks the browser\n    // main thread. All resource loaders already load missing assets lazily.\n#ifndef __EMSCRIPTEN__\n    std::string levelPath = "/LEVEL" + ToStr(m_pCurrentLevel->GetLevelNumber()) + "/*";\n    g_pApp->GetResourceCache()->Preload(levelPath, NULL);\n#else\n    PortLoadStatus("VLoadGame: bulk preload skipped");\n#endif\n'''
if first not in text:
    raise SystemExit('VLoadGame preload block not found')
text = text.replace(first, first_repl, 1)

second = '''        // Lazy loading: Preload level-specific assets on-demand\n        LOG("Loading assets for " + levelName + "...");\n        std::string levelAssetPath = "/" + levelName + "/*";\n        g_pApp->GetResourceCache()->Preload(levelAssetPath, NULL);\n        LOG("Level assets loaded for " + levelName);\n'''
second_repl = '''        // Do not bulk-preload in the browser. VLoadGame loads resources lazily.\n#ifndef __EMSCRIPTEN__\n        LOG("Loading assets for " + levelName + "...");\n        std::string levelAssetPath = "/" + levelName + "/*";\n        g_pApp->GetResourceCache()->Preload(levelAssetPath, NULL);\n        LOG("Level assets loaded for " + levelName);\n#else\n        PortLoadStatus("Entering " + levelName);\n#endif\n'''
if second not in text:
    raise SystemExit('VChangeState preload block not found')
text = text.replace(second, second_repl, 1)

# Allow C++ milestones to be shown directly on the phone, without DevTools.
emscripten_include = '''#ifdef __EMSCRIPTEN__\n#include "SaveBridge.h"\n#endif\n'''
emscripten_include_repl = '''#ifdef __EMSCRIPTEN__\n#include "SaveBridge.h"\n#include <emscripten/emscripten.h>\n#endif\n'''
if emscripten_include not in text:
    raise SystemExit('BaseGameLogic Emscripten include block not found')
text = text.replace(emscripten_include, emscripten_include_repl, 1)

helper_anchor = '#include <iostream>\n\n'
helper = r'''#include <iostream>

static void PortLoadStatus(const std::string& message)
{
    LOG("[PORT LOAD] " + message);
#ifdef __EMSCRIPTEN__
    EM_ASM({
        if (typeof window !== 'undefined' && typeof window.__setClawLoadStatus === 'function') {
            window.__setClawLoadStatus(UTF8ToString($0));
        }
    }, message.c_str());
#endif
}

'''
if helper_anchor not in text:
    raise SystemExit('BaseGameLogic helper insertion point not found')
text = text.replace(helper_anchor, helper, 1)

# High-signal milestones throughout the synchronous level-load path.
replacements = [
    (
        '''bool BaseGameLogic::VLoadGame(const char* xmlLevelResource)\n{\n    // Stop all audio\n''',
        '''bool BaseGameLogic::VLoadGame(const char* xmlLevelResource)\n{\n    PortLoadStatus("VLoadGame: start");\n\n    // Stop all audio\n'''
    ),
    (
        '''    m_pPhysics.reset(CreateClawPhysics());\n\n    float loadingProgress = 0.0f;\n''',
        '''    m_pPhysics.reset(CreateClawPhysics());\n    PortLoadStatus("Physics ready");\n\n    float loadingProgress = 0.0f;\n'''
    ),
    (
        '''    std::string backgroundPath = "/LEVEL" + ToStr(m_pCurrentLevel->m_LeveNumber) + "/SCREENS/LOADING.PCX";\n    shared_ptr<Image> pBackgroundImage = PcxResourceLoader::LoadAndReturnImage(backgroundPath.c_str());\n''',
        '''    std::string backgroundPath = "/LEVEL" + ToStr(m_pCurrentLevel->m_LeveNumber) + "/SCREENS/LOADING.PCX";\n    PortLoadStatus("Loading loading-screen PCX");\n    shared_ptr<Image> pBackgroundImage = PcxResourceLoader::LoadAndReturnImage(backgroundPath.c_str());\n'''
    ),
    (
        '''    assert(pBackgroundImage->GetTexture() != NULL);\n\n    RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);\n''',
        '''    assert(pBackgroundImage->GetTexture() != NULL);\n    PortLoadStatus("Loading-screen PCX ready");\n\n    RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);\n'''
    ),
    (
        '''    WapWwd* pWwd = WwdResourceLoader::LoadAndReturnWwd(xmlLevelResource);\n    assert(pWwd != NULL);\n''',
        '''    PortLoadStatus("Loading WORLD.WWD");\n    WapWwd* pWwd = WwdResourceLoader::LoadAndReturnWwd(xmlLevelResource);\n    assert(pWwd != NULL);\n    PortLoadStatus("WORLD.WWD ready");\n'''
    ),
    (
        '''    TiXmlElement* pXmlLevelRoot = WwdToXml(pWwd, m_pCurrentLevel->GetLevelNumber());\n''',
        '''    PortLoadStatus("Converting WWD to level XML");\n    TiXmlElement* pXmlLevelRoot = WwdToXml(pWwd, m_pCurrentLevel->GetLevelNumber());\n    PortLoadStatus("WWD conversion ready");\n'''
    ),
    (
        '''    std::string palettePath = pLevelProperties->FirstChildElement("Palette")->GetText();\n    std::replace(palettePath.begin(), palettePath.end(), '\\\\', '/');\n    g_pApp->SetCurrentPalette(PalResourceLoader::LoadAndReturnPal(palettePath.c_str()));\n\n    uint32 clawId = -1;\n''',
        '''    PortLoadStatus("Loading level palette");\n    std::string palettePath = pLevelProperties->FirstChildElement("Palette")->GetText();\n    std::replace(palettePath.begin(), palettePath.end(), '\\\\', '/');\n    g_pApp->SetCurrentPalette(PalResourceLoader::LoadAndReturnPal(palettePath.c_str()));\n    PortLoadStatus("Palette ready");\n\n    uint32 clawId = -1;\n    int portActorIndex = 0;\n'''
    ),
    (
        '''        StrongActorPtr pActor = VCreateActor(pActorElem, NULL);\n''',
        '''        ++portActorIndex;\n        if (portActorIndex == 1 || portActorIndex == numActors || (portActorIndex % 25) == 0)\n        {\n            PortLoadStatus("Creating actors " + ToStr(portActorIndex) + "/" + ToStr(numActors));\n        }\n        StrongActorPtr pActor = VCreateActor(pActorElem, NULL);\n'''
    ),
    (
        '''    // Load game save data\n    const CheckpointSave* pCheckpointSave = m_pGameSaveMgr->GetCheckpointSave(\n''',
        '''    PortLoadStatus("Actors ready; loading checkpoint");\n\n    // Load game save data\n    const CheckpointSave* pCheckpointSave = m_pGameSaveMgr->GetCheckpointSave(\n'''
    ),
    (
        '''    assert(pCheckpointSave != NULL);\n\n    loadingProgress = 95.0f;\n''',
        '''    assert(pCheckpointSave != NULL);\n    PortLoadStatus("Checkpoint ready");\n\n    loadingProgress = 95.0f;\n'''
    ),
    (
        '''    m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);\n''',
        '''    PortLoadStatus("Setting player spawn");\n    m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);\n'''
    ),
    (
        '''    // Notify all human views\n    for (auto pGameView : m_GameViews)\n''',
        '''    PortLoadStatus("Building scene and HUD");\n\n    // Notify all human views\n    for (auto pGameView : m_GameViews)\n'''
    ),
    (
        '''    loadingProgress = 100.0f;   \n    RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);\n\n    LOG("Level loaded !");\n''',
        '''    PortLoadStatus("Scene and HUD ready");\n    loadingProgress = 100.0f;   \n    RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);\n\n    PortLoadStatus("LEVEL LOAD COMPLETE");\n    LOG("Level loaded !");\n'''
    ),
]
for old, new in replacements:
    if old not in text:
        raise SystemExit('Expected BaseGameLogic instrumentation anchor not found:\n' + old[:120])
    text = text.replace(old, new, 1)

logic_path.write_text(text, encoding='utf-8', newline='\n')

# Instrument the menu -> level handoff too. If the hang occurs before VLoadGame,
# the phone will still show the exact last completed handoff step.
human_path = root / 'OpenClaw/Engine/UserInterface/HumanView.cpp'
human = human_path.read_text(encoding='utf-8')
human_anchor = 'const uint32 g_InvalidGameViewId = 0xFFFFFFFF;\n\n'
human_helper = r'''static void PortViewLoadStatus(const char* message)
{
#ifdef __EMSCRIPTEN__
    EM_ASM({
        if (typeof window !== 'undefined' && typeof window.__setClawLoadStatus === 'function') {
            window.__setClawLoadStatus(UTF8ToString($0));
        }
    }, message);
#endif
}

'''
if human_anchor not in human:
    raise SystemExit('HumanView helper insertion point not found')
human = human.replace(human_anchor, human_anchor + human_helper, 1)

load_delegate_old = '''void HumanView::LoadGameDelegate(IEventDataPtr pEventData)\n{\n    shared_ptr<EventData_Menu_LoadGame> pCastEventData =\n'''
load_delegate_new = '''void HumanView::LoadGameDelegate(IEventDataPtr pEventData)\n{\n    PortViewLoadStatus("LoadGame event received");\n    shared_ptr<EventData_Menu_LoadGame> pCastEventData =\n'''
if load_delegate_old not in human:
    raise SystemExit('HumanView LoadGameDelegate entry not found')
human = human.replace(load_delegate_old, load_delegate_new, 1)

handoff_repls = [
    ('        m_ScreenElements.clear();\n        m_pMenu.reset();\n',
     '        PortViewLoadStatus("Clearing menu screen elements");\n        m_ScreenElements.clear();\n        m_pMenu.reset();\n        PortViewLoadStatus("Menu cleared");\n'),
    ('        m_pScene->SetCamera(m_pCamera);\n\n        // Go to menu after finishing last implemented level\n',
     '        m_pScene->SetCamera(m_pCamera);\n        PortViewLoadStatus("Empty game scene created");\n\n        // Go to menu after finishing last implemented level\n'),
    ('            g_pApp->GetGameLogic()->SetLevelData(pLevelData);\n\n            g_pApp->GetGameLogic()->VChangeState(GameState_LoadingLevel);\n',
     '            g_pApp->GetGameLogic()->SetLevelData(pLevelData);\n            PortViewLoadStatus("Calling GameState_LoadingLevel");\n\n            g_pApp->GetGameLogic()->VChangeState(GameState_LoadingLevel);\n'),
]
for old, new in handoff_repls:
    if old not in human:
        raise SystemExit('Expected HumanView handoff anchor not found:\n' + old[:100])
    human = human.replace(old, new, 1)
human_path.write_text(human, encoding='utf-8', newline='\n')

# Visible mobile diagnostic badge. It also persists the last executed status so
# a browser that stops repainting during a long synchronous WASM call cannot
# hide the real final milestone from the next page load.
html_path = root / 'Build_Release/claw-web.html'
html = html_path.read_text(encoding='utf-8')
body_anchor = '  <body>\n'
badge = '''  <body>\n    <div id="portLoadStatus" style="display:none;position:fixed;z-index:2147483647;left:50%;top:12px;transform:translateX(-50%);max-width:92vw;padding:8px 12px;border:1px solid #ffd166;border-radius:9px;background:rgba(0,0,0,.92);color:#ffd166;font:700 12px/1.3 monospace;text-align:center;pointer-events:none;box-shadow:0 2px 12px rgba(0,0,0,.55)"></div>\n    <script>\n      (function () {\n        try {\n          var previous = localStorage.getItem('clawLastLoadStatus');\n          if (previous && previous.indexOf('LEVEL LOAD COMPLETE') === -1) {\n            var el = document.getElementById('portLoadStatus');\n            if (el) {\n              el.textContent = 'PREV LOAD: ' + previous;\n              el.style.display = 'block';\n            }\n          }\n        } catch (e) {}\n      })();\n      window.__setClawLoadStatus = function (message) {\n        var el = document.getElementById('portLoadStatus');\n        var text = String(message == null ? '' : message);\n        try {\n          localStorage.setItem('clawLastLoadStatus', text);\n          localStorage.setItem('clawLastLoadStatusAt', String(Date.now()));\n        } catch (e) {}\n        if (!el) return;\n        el.textContent = 'LOAD: ' + text;\n        el.style.display = 'block';\n        if (text.indexOf('LEVEL LOAD COMPLETE') !== -1) {\n          setTimeout(function () { el.style.display = 'none'; }, 1800);\n        }\n      };\n    </script>\n'''
if body_anchor not in html:
    raise SystemExit('HTML body insertion point not found')
html = html.replace(body_anchor, badge, 1)
html_path.write_text(html, encoding='utf-8', newline='\n')

if text.count('PortLoadStatus(') < 12:
    raise SystemExit('Expected C++ loading diagnostics were not injected')
if human.count('PortViewLoadStatus(') < 5:
    raise SystemExit('Expected HumanView loading diagnostics were not injected')
if 'clawLastLoadStatus' not in html:
    raise SystemExit('Persistent browser loading diagnostic was not injected')

# ResourceCache::Match performs a complete archive scan for every wildcard
# lookup. Level loading creates many actors of the same prototypes, so the same
# patterns (for example /LEVEL1/ANIS/RAT/*) are evaluated repeatedly. Cache
# immutable match results per ResourceCache instance to turn those repeats into
# inexpensive map lookups without changing resource or gameplay semantics.
cache_h_path = root / 'OpenClaw/Engine/Resource/ResourceCache.h'
cache_h = cache_h_path.read_text(encoding='utf-8')
cache_member_anchor = '''    ResourceHandleList _lruList;\n    ResourceLoaderList _resourceLoaderList;\n    ResourceHandleMap _resourceMap;\n};\n'''
cache_member_repl = '''    ResourceHandleList _lruList;\n    ResourceLoaderList _resourceLoaderList;\n    ResourceHandleMap _resourceMap;\n    std::map<std::string, std::vector<std::string>> _matchCache;\n};\n'''
if cache_member_anchor not in cache_h:
    raise SystemExit('ResourceCache member anchor not found')
cache_h = cache_h.replace(cache_member_anchor, cache_member_repl, 1)
cache_h_path.write_text(cache_h, encoding='utf-8', newline='\n')

cache_cpp_path = root / 'OpenClaw/Engine/Resource/ResourceCache.cpp'
cache_cpp = cache_cpp_path.read_text(encoding='utf-8')
match_old = '''std::vector<std::string> ResourceCache::Match(const std::string pattern)\n{\n    std::vector<std::string> matchingNames;\n\n    if (_resourceFile == NULL)\n    {\n        return matchingNames;\n    }\n\n    // Everything is converted into lower case so maintain consistency\n    std::string patternCopy = pattern;\n    std::transform(patternCopy.begin(), patternCopy.end(), patternCopy.begin(), (int(*)(int)) std::tolower);\n\n    uint32 numFiles = _resourceFile->VGetNumResources();\n    for (uint32 fileIdx = 0; fileIdx < numFiles; ++fileIdx)\n    {\n        std::string fileNamePath = _resourceFile->VGetResourceName(fileIdx);\n        // Everything is converted into lower case so maintain consistency\n        std::transform(fileNamePath.begin(), fileNamePath.end(), fileNamePath.begin(), (int(*)(int)) std::tolower);\n\n        //std::cout << "Filename: " << fileNamePath << ", Pattern: " << pattern << std::endl;\n\n        if (WildcardMatch(patternCopy.c_str(), fileNamePath.c_str()))\n        {\n            matchingNames.push_back(fileNamePath);\n        }\n    }\n\n    return matchingNames;\n}\n'''
match_new = '''std::vector<std::string> ResourceCache::Match(const std::string pattern)\n{\n    std::vector<std::string> matchingNames;\n\n    if (_resourceFile == NULL)\n    {\n        return matchingNames;\n    }\n\n    // Everything is converted into lower case so maintain consistency.\n    // Match results depend only on the immutable archive and pattern, so cache\n    // them for repeated actor-prototype lookups during level construction.\n    std::string patternCopy = pattern;\n    std::transform(patternCopy.begin(), patternCopy.end(), patternCopy.begin(), (int(*)(int)) std::tolower);\n\n    auto cachedMatch = _matchCache.find(patternCopy);\n    if (cachedMatch != _matchCache.end())\n    {\n        return cachedMatch->second;\n    }\n\n    uint32 numFiles = _resourceFile->VGetNumResources();\n    for (uint32 fileIdx = 0; fileIdx < numFiles; ++fileIdx)\n    {\n        std::string fileNamePath = _resourceFile->VGetResourceName(fileIdx);\n        // Everything is converted into lower case so maintain consistency\n        std::transform(fileNamePath.begin(), fileNamePath.end(), fileNamePath.begin(), (int(*)(int)) std::tolower);\n\n        if (WildcardMatch(patternCopy.c_str(), fileNamePath.c_str()))\n        {\n            matchingNames.push_back(fileNamePath);\n        }\n    }\n\n    _matchCache[patternCopy] = matchingNames;\n    return matchingNames;\n}\n'''
if match_old not in cache_cpp:
    raise SystemExit('ResourceCache::Match anchor not found')
cache_cpp = cache_cpp.replace(match_old, match_new, 1)
cache_cpp_path.write_text(cache_cpp, encoding='utf-8', newline='\n')

if '_matchCache.find(patternCopy)' not in cache_cpp or '_matchCache' not in cache_h:
    raise SystemExit('ResourceCache match memoization was not injected')

print('WASM persistent diagnostics + ResourceCache Match memoization applied successfully.')
