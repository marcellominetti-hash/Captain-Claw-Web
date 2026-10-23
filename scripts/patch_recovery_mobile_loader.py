#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

def read(rel):
    return (root / rel).read_text(encoding="utf-8")

def write(rel, text):
    (root / rel).write_text(text, encoding="utf-8", newline="\n")

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"{label}: anchor not found")
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Use extracted CLAW_ASSETS.ZIP as the primary original-data archive.
# ---------------------------------------------------------------------------
app_cpp_path = "OpenClaw/Engine/GameApp/BaseGameApp.cpp"
app_cpp = read(app_cpp_path)
app_cpp = replace_once(
    app_cpp,
    "  IResourceFile *rezArchive = new ResourceRezArchive(rezArchivePath);",
    "  IResourceFile *rezArchive = new ResourceZipArchive(rezArchivePath);",
    "BaseGameApp primary archive",
)
app_cpp = app_cpp.replace(
    'XML_ADD_TEXT_ELEMENT("RezArchive", "CLAW.REZ", assets);',
    'XML_ADD_TEXT_ELEMENT("RezArchive", "CLAW_ASSETS.ZIP", assets);',
)
write(app_cpp_path, app_cpp)

for rel in [
    "OpenClaw/Engine/GameApp/BaseGameApp.h",
    "Build_Release/config.xml",
    "Build_Release/config_linux.xml",
    "Build_Release/config_linux_release.xml",
]:
    p = root / rel
    if p.exists():
        write(rel, read(rel).replace("CLAW.REZ", "CLAW_ASSETS.ZIP"))

# ---------------------------------------------------------------------------
# 2) EventMgr safety: defer level reset instead of nesting VUpdate.
# ---------------------------------------------------------------------------
logic_h_path = "OpenClaw/Engine/GameApp/BaseGameLogic.h"
logic_h = read(logic_h_path)
logic_h = replace_once(
    logic_h,
    "    bool m_Proxy;\n    bool m_bRunning;\n",
    "    bool m_Proxy;\n    bool m_bRunning;\n    bool m_bResetLevelPending;\n",
    "BaseGameLogic reset member",
)
write(logic_h_path, logic_h)

logic_cpp_path = "OpenClaw/Engine/GameApp/BaseGameLogic.cpp"
logic_cpp = read(logic_cpp_path)
logic_cpp = replace_once(
    logic_cpp,
    "    m_SelectedLevel = -1;\n    m_bRunning = true;\n",
    "    m_SelectedLevel = -1;\n    m_bRunning = true;\n    m_bResetLevelPending = false;\n",
    "BaseGameLogic constructor",
)

logic_cpp = replace_once(
    logic_cpp,
    "void BaseGameLogic::VOnUpdate(uint32 msDiff)\n{\n    m_Lifetime += msDiff;\n",
    """void BaseGameLogic::VOnUpdate(uint32 msDiff)
{
    m_Lifetime += msDiff;

    if (m_bResetLevelPending && !IEventMgr::Get()->VIsUpdating())
    {
        m_bResetLevelPending = false;
        LOG("Executing deferred level reset after EventMgr update");
        VResetLevel();
        return;
    }
""",
    "BaseGameLogic VOnUpdate",
)

logic_cpp = replace_once(
    logic_cpp,
    """void BaseGameLogic::VResetLevel()
{
    // Handle all pending events before reset
    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);
""",
    """void BaseGameLogic::VResetLevel()
{
    if (IEventMgr::Get()->VIsUpdating())
    {
        LOG("Deferring level reset until EventMgr update completes");
        m_bResetLevelPending = true;
        return;
    }

    m_bResetLevelPending = false;

    // Handle all pending events before reset
    IEventMgr::Get()->VUpdate(IEventMgr::kINFINITE);
""",
    "BaseGameLogic VResetLevel",
)

# ---------------------------------------------------------------------------
# 3) Cooperative mobile loading: yield while preloading and constructing actors.
#    ASYNCIFY is already enabled by the upstream WASM build.
# ---------------------------------------------------------------------------
if "#include <emscripten/emscripten.h>" not in logic_cpp:
    logic_cpp = """#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif

""" + logic_cpp

actor_loop_old = """    uint32 clawId = -1;
    for (TiXmlElement* pActorElem = pXmlLevelRoot->FirstChildElement("Actor"); 
        pActorElem != NULL;
        pActorElem = pActorElem->NextSiblingElement("Actor"))
    {
"""
actor_loop_new = """    uint32 clawId = -1;
    int webActorBatchCount = 0;
    for (TiXmlElement* pActorElem = pXmlLevelRoot->FirstChildElement("Actor"); 
        pActorElem != NULL;
        pActorElem = pActorElem->NextSiblingElement("Actor"))
    {
"""
logic_cpp = replace_once(
    logic_cpp, actor_loop_old, actor_loop_new, "BaseGameLogic actor loop"
)

actor_yield_anchor = """        if ((loadingProgress - lastProgress) > 1.0f)
        {
            RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);
            lastProgress = loadingProgress;
        }
    }

    // Load game save data
"""
actor_yield_repl = """        if ((loadingProgress - lastProgress) > 1.0f)
        {
            RenderLoadingScreen(pBackgroundImage, backgroundRect, scale, loadingProgress);
            lastProgress = loadingProgress;
        }

#ifdef __EMSCRIPTEN__
        // Keep the browser event loop responsive on mobile. ASYNCIFY preserves
        // this C++ stack while yielding and resumes at the next actor batch.
        ++webActorBatchCount;
        if ((webActorBatchCount % 20) == 0)
        {
            emscripten_sleep(0);
        }
#endif
    }

    // Load game save data
"""
logic_cpp = replace_once(
    logic_cpp, actor_yield_anchor, actor_yield_repl, "BaseGameLogic actor yield"
)
write(logic_cpp_path, logic_cpp)

event_path = "OpenClaw/Engine/Events/EventMgrImpl.cpp"
event_cpp = read(event_path)
event_cpp = replace_once(
    event_cpp,
    """bool EventMgr::VUpdate(unsigned long maxMillis)
{
    assert(!m_bIsUpdating && "Attempted to nest updating events - EventMgr::VUpdate inside EventMgr::VUpdate");

    m_bIsUpdating = true;
""",
    """bool EventMgr::VUpdate(unsigned long maxMillis)
{
    if (m_bIsUpdating)
    {
        LOG_WARNING("Nested EventMgr::VUpdate request ignored; outer update remains active");
        return false;
    }

    m_bIsUpdating = true;
""",
    "EventMgr nested update guard",
)
write(event_path, event_cpp)

cache_cpp_path = "OpenClaw/Engine/Resource/ResourceCache.cpp"
cache_cpp = read(cache_cpp_path)
if "#include <emscripten/emscripten.h>" not in cache_cpp:
    cache_cpp = replace_once(
        cache_cpp,
        "#include <cctype>\n",
        """#include <cctype>
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif
""",
        "ResourceCache emscripten include",
    )

# Memoize immutable wildcard matches. Repeated actor prototypes otherwise scan
# the full archive over and over.
cache_h_path = "OpenClaw/Engine/Resource/ResourceCache.h"
cache_h = read(cache_h_path)
cache_h = replace_once(
    cache_h,
    """    ResourceHandleList _lruList;
    ResourceLoaderList _resourceLoaderList;
    ResourceHandleMap _resourceMap;
};
""",
    """    ResourceHandleList _lruList;
    ResourceLoaderList _resourceLoaderList;
    ResourceHandleMap _resourceMap;
    std::map<std::string, std::vector<std::string>> _matchCache;
};
""",
    "ResourceCache match cache member",
)
write(cache_h_path, cache_h)

match_old = """std::vector<std::string> ResourceCache::Match(const std::string pattern)
{
    std::vector<std::string> matchingNames;

    if (_resourceFile == NULL)
    {
        return matchingNames;
    }

    // Everything is converted into lower case so maintain consistency
    std::string patternCopy = pattern;
    std::transform(patternCopy.begin(), patternCopy.end(), patternCopy.begin(), (int(*)(int)) std::tolower);

    uint32 numFiles = _resourceFile->VGetNumResources();
    for (uint32 fileIdx = 0; fileIdx < numFiles; ++fileIdx)
    {
        std::string fileNamePath = _resourceFile->VGetResourceName(fileIdx);
        // Everything is converted into lower case so maintain consistency
        std::transform(fileNamePath.begin(), fileNamePath.end(), fileNamePath.begin(), (int(*)(int)) std::tolower);

        //std::cout << "Filename: " << fileNamePath << ", Pattern: " << pattern << std::endl;

        if (WildcardMatch(patternCopy.c_str(), fileNamePath.c_str()))
        {
            matchingNames.push_back(fileNamePath);
        }
    }

    return matchingNames;
}
"""
match_new = """std::vector<std::string> ResourceCache::Match(const std::string pattern)
{
    std::vector<std::string> matchingNames;

    if (_resourceFile == NULL)
    {
        return matchingNames;
    }

    std::string patternCopy = pattern;
    std::transform(patternCopy.begin(), patternCopy.end(), patternCopy.begin(), (int(*)(int)) std::tolower);

    auto cached = _matchCache.find(patternCopy);
    if (cached != _matchCache.end())
    {
        return cached->second;
    }

    uint32 numFiles = _resourceFile->VGetNumResources();
    for (uint32 fileIdx = 0; fileIdx < numFiles; ++fileIdx)
    {
        std::string fileNamePath = _resourceFile->VGetResourceName(fileIdx);
        std::transform(fileNamePath.begin(), fileNamePath.end(), fileNamePath.begin(), (int(*)(int)) std::tolower);

        if (WildcardMatch(patternCopy.c_str(), fileNamePath.c_str()))
        {
            matchingNames.push_back(fileNamePath);
        }
    }

    _matchCache[patternCopy] = matchingNames;
    return matchingNames;
}
"""
cache_cpp = replace_once(
    cache_cpp, match_old, match_new, "ResourceCache Match memoization"
)

preload_anchor = """        if (progressCallback != NULL)
        {
            progressCallback((fileIdx / numFiles) * 100, cancel);
        }
    }

    return loaded;
}
"""
preload_repl = """        if (progressCallback != NULL)
        {
            progressCallback((fileIdx / numFiles) * 100, cancel);
        }

#ifdef __EMSCRIPTEN__
        // Preload scans the whole archive synchronously. Yield occasionally so
        // Android/iOS browsers can paint, process input and avoid long-task kills.
        if ((fileIdx & 255) == 255)
        {
            emscripten_sleep(0);
        }
#endif
    }

    return loaded;
}
"""
cache_cpp = replace_once(
    cache_cpp, preload_anchor, preload_repl, "ResourceCache preload yield"
)
write(cache_cpp_path, cache_cpp)

# ---------------------------------------------------------------------------
# 4) Browser storage: keep the ZIP as a Blob until preRun, then copy it to
#    MEMFS in 2 MiB chunks. This removes the extra full-size ArrayBuffer peak.
# ---------------------------------------------------------------------------
loader_path = "Build_Release/asset-loader.js"
loader = read(loader_path).replace("CLAW.REZ", "CLAW_ASSETS.ZIP")

# Validation becomes ZIP signature + broad extracted-data size bounds.
loader = re.sub(
    r"const REZ_VALID_SIGNATURES = .*?const REZ_MAX_SIZE = .*?;\n",
    """const REZ_MIN_SIZE = 10 * 1024 * 1024;
const REZ_MAX_SIZE = 512 * 1024 * 1024;
""",
    loader,
    count=1,
    flags=re.S,
)

loader = re.sub(
    r"async function hasRezSignature\(file\) \{.*?\n\}",
    """async function hasZipSignature(file) {
  try {
    const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());
    return head.length === 4 &&
      head[0] === 0x50 && head[1] === 0x4b &&
      head[2] === 0x03 && head[3] === 0x04;
  } catch (e) {
    console.error('Failed to read CLAW_ASSETS.ZIP header:', e);
    return false;
  }
}""",
    loader,
    count=1,
    flags=re.S,
)
loader = loader.replace("hasRezSignature(file)", "hasZipSignature(file)")
loader = loader.replace(
    "but CLAW_ASSETS.ZIP is about 113MB. Please select the correct file from the original Captain Claw (1997) game.",
    "which is outside the expected range for the extracted game-data archive."
)
loader = loader.replace(
    "It is missing the expected archive header. Please select the correct CLAW_ASSETS.ZIP from the original Captain Claw (1997) game.",
    "It is missing the standard ZIP header."
)

loader = loader.replace(
    "let clawRezData = null;",
    "let clawRezBlob = null;"
)

prepare_old = """    // Retrieve CLAW_ASSETS.ZIP from IndexedDB. It is stored uncompressed, so it can be
    // used directly with no decompression step.
    console.log('Retrieving CLAW_ASSETS.ZIP from IndexedDB...');
    const clawRezBlob = await assetStorage.getFile('CLAW_ASSETS.ZIP');
    if (!clawRezBlob) {
      throw new Error('Failed to retrieve CLAW_ASSETS.ZIP from storage');
    }

    // CRITICAL: Convert Blob to ArrayBuffer and store BEFORE returning
    // This ensures clawRezData is populated before loadGame() is called
    console.log('Loading CLAW_ASSETS.ZIP into memory...');
    const arrayBuffer = await clawRezBlob.arrayBuffer();
    clawRezData = new Uint8Array(arrayBuffer);
    console.log(`CLAW_ASSETS.ZIP ready to mount (${(clawRezData.length / 1024 / 1024).toFixed(2)}MB)`);
"""
prepare_new = """    // Keep the archive as a Blob. Do not materialize a second full-size
    // ArrayBuffer here; preRun streams it to MEMFS in small chunks.
    console.log('Retrieving CLAW_ASSETS.ZIP from IndexedDB...');
    clawRezBlob = await assetStorage.getFile('CLAW_ASSETS.ZIP');
    if (!clawRezBlob) {
      throw new Error('Failed to retrieve CLAW_ASSETS.ZIP from storage');
    }
    console.log(`CLAW_ASSETS.ZIP ready to mount (${(clawRezBlob.size / 1024 / 1024).toFixed(2)}MB)`);
"""
loader = replace_once(
    loader, prepare_old, prepare_new, "asset-loader Blob preparation"
)

mount_pattern = re.compile(
    r"function mountClawRezToFS\(\) \{.*?\n\}\n\n/\*\*\n \* Get storage statistics",
    re.S,
)
mount_replacement = """function mountClawRezToFS() {
  if (!clawRezBlob) {
    console.error('CLAW_ASSETS.ZIP Blob not prepared!');
    return false;
  }

  try {
    const dependency = 'claw-assets-zip-mount';
    addRunDependency(dependency);

    (async function () {
      let stream = null;
      try {
        const target = '/CLAW_ASSETS.ZIP';
        const chunkSize = 2 * 1024 * 1024;
        stream = FS.open(target, 'w+');

        let offset = 0;
        while (offset < clawRezBlob.size) {
          const end = Math.min(offset + chunkSize, clawRezBlob.size);
          const chunk = new Uint8Array(
            await clawRezBlob.slice(offset, end).arrayBuffer()
          );
          FS.write(stream, chunk, 0, chunk.length, offset);
          offset = end;

          if ((offset % (8 * 1024 * 1024)) === 0 || offset === clawRezBlob.size) {
            console.log(
              `Mounting CLAW_ASSETS.ZIP: ${((offset / clawRezBlob.size) * 100).toFixed(0)}%`
            );
          }

          // Give the browser a paint/input opportunity between chunks.
          await new Promise(resolve => setTimeout(resolve, 0));
        }

        FS.close(stream);
        stream = null;
        clawRezBlob = null;
        console.log('CLAW_ASSETS.ZIP mounted successfully');
      } catch (error) {
        if (stream) {
          try { FS.close(stream); } catch (_) {}
        }
        console.error('Failed to mount CLAW_ASSETS.ZIP to FS:', error);
        if (typeof abort === 'function') {
          abort('CLAW_ASSETS.ZIP mount failed: ' + error.message);
        }
      } finally {
        removeRunDependency(dependency);
      }
    })();

    return true;
  } catch (error) {
    console.error('Failed to start CLAW_ASSETS.ZIP mount:', error);
    return false;
  }
}

/**
 * Get storage statistics"""
loader, count = mount_pattern.subn(mount_replacement, loader, count=1)
if count != 1:
    raise SystemExit("asset-loader chunked mount: function block not found")

write(loader_path, loader)

# Other browser code only needs the storage key / UI name changed; keep the
# public function names stable to minimize the diff.
for rel in [
    "Build_Release/game-init.js",
    "Build_Release/asset-storage.js",
    "Build_Release/claw-web.html",
]:
    p = root / rel
    if p.exists():
        text = read(rel).replace("CLAW.REZ", "CLAW_ASSETS.ZIP")
        if rel.endswith("claw-web.html"):
            text = text.replace('accept=".REZ,.rez"', 'accept=".ZIP,.zip,application/zip"')
            text = text.replace("<title>Claw Web</title>", "<title>Capitan Artiglio Recovery</title>")
        write(rel, text)

# ---------------------------------------------------------------------------
# Recovery-build assertions.
# ---------------------------------------------------------------------------
checks = {
    app_cpp_path: ["ResourceZipArchive(rezArchivePath)", "CLAW_ASSETS.ZIP"],
    logic_cpp_path: ["emscripten_sleep(0)", "m_bResetLevelPending"],
    event_path: ["Nested EventMgr::VUpdate request ignored"],
    cache_cpp_path: ["_matchCache.find(patternCopy)", "emscripten_sleep(0)"],
    loader_path: ["clawRezBlob", "addRunDependency(dependency)", "CLAW_ASSETS.ZIP"],
}
for rel, needles in checks.items():
    text = read(rel)
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{rel}: recovery assertion missing: {needle}")

if "FS.writeFile('/CLAW_ASSETS.ZIP'" in read(loader_path):
    raise SystemExit("asset-loader still contains whole-file FS.writeFile path")

print("Recovery mobile-loader patch applied successfully.")
