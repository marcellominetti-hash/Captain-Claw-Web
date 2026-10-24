from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path('upstream')

def replace_once(path, old, new):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if old not in s:
        raise SystemExit(f'pattern not found in {path}: {old[:120]!r}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

# 1) Custom WWD archive mounted as highest-priority resource cache.
p = ROOT/'OpenClaw/Engine/GameApp/BaseGameApp.cpp'
s = p.read_text(encoding='utf-8')
if '#include <fstream>' not in s:
    s = s.replace('#include <cctype>', '#include <cctype>\n#include <fstream>')
old = '''  m_pResourceMgr = new ResourceMgrImpl();
  // Custom cache first so ASSETS.ZIP can override CLAW.REZ assets
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''
new = '''  // Optional APK-selected custom level archive. It is mounted before ASSETS.ZIP
  // and CLAW.REZ so its WORLD.WWD overrides the original level slot.
  std::shared_ptr<ResourceCache> pSelectedLevelCache;
  {
    std::ifstream selectedLevelProbe("/CUSTOM_LEVEL.ZIP", std::ios::binary);
    if (selectedLevelProbe.good()) {
      IResourceFile *pSelectedLevelArchive = new ResourceZipArchive("/CUSTOM_LEVEL.ZIP");
      pSelectedLevelCache.reset(new ResourceCache(80, pSelectedLevelArchive, CUSTOM_RESOURCE));
      if (pSelectedLevelCache->Init()) {
        pSelectedLevelCache->RegisterLoader(DefaultResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(XmlResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(WwdResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(PalResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(PidResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(AniResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(WavResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(MidiResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(PcxResourceLoader::Create());
        pSelectedLevelCache->RegisterLoader(PngResourceLoader::Create());
        LOG("Selected custom level archive mounted");
      } else {
        LOG_WARNING("Failed to initialize CUSTOM_LEVEL.ZIP; continuing without it");
        pSelectedLevelCache.reset();
      }
    }
  }

  m_pResourceMgr = new ResourceMgrImpl();
  if (pSelectedLevelCache) m_pResourceMgr->VAddResourceCache(pSelectedLevelCache);
  // ASSETS.ZIP overrides CLAW.REZ assets.
  m_pResourceMgr->VAddResourceCache(pCustomCache);
  m_pResourceMgr->VAddResourceCache(m_pResourceCache);
'''
if old not in s: raise SystemExit('resource manager insertion pattern missing')
s=s.replace(old,new,1)
# Read the selected base slot after normal config parsing.
marker='''  return true;
}

void BaseGameApp::SaveGameOptions'''
insert='''#ifdef __EMSCRIPTEN__
  // Android/web wrapper writes the selected base slot before the engine starts.
  {
    std::ifstream selectedLevelNumberFile("/CUSTOM_LEVEL.NUM");
    int selectedLevelNumber = 0;
    if (selectedLevelNumberFile.good() && (selectedLevelNumberFile >> selectedLevelNumber) &&
        selectedLevelNumber >= 1 && selectedLevelNumber <= 14) {
      m_DebugOptions.skipMenuToLevel = selectedLevelNumber;
      m_DebugOptions.bSkipMenu = true;
      LOG("Starting selected custom level in base slot " + ToStr(selectedLevelNumber));
    }
  }
#endif

  return true;
}

void BaseGameApp::SaveGameOptions'''
if marker not in s: raise SystemExit('LoadGameOptions return marker missing')
s=s.replace(marker,insert,1)
p.write_text(s,encoding='utf-8')

# 2) Missing level metadata must never abort the whole runtime.
replace_once('OpenClaw/Engine/Util/ClawLevelUtil.cpp',
'''        const shared_ptr<LevelMetadata> pLevelMetadata = g_pApp->GetLevelMetadata(levelNumber);
        assert(pLevelMetadata != nullptr);

        auto findIt = pLevelMetadata->logicToActorPrototypeMap.find(logic);''',
'''        const shared_ptr<LevelMetadata> pLevelMetadata = g_pApp->GetLevelMetadata(levelNumber);
        if (!pLevelMetadata) {
            LOG_WARNING("No level metadata for level " + ToStr(levelNumber) + "; actor logic '" + logic + "' will be render-only");
            return ActorPrototype_None;
        }

        auto findIt = pLevelMetadata->logicToActorPrototypeMap.find(logic);''')

# 3) Unsupported custom pickup aliases degrade to a normal coin instead of assert.
replace_once('OpenClaw/Engine/Actor/ActorTemplates.cpp',
'''        if (findIt == s_ImageSetToPickupTypeMap.end())
        {
            LOG_ERROR("Could not find requested enum. Offending key: " + pickupImageSet);
            assert(false);
        }

        return findIt->second;''',
'''        if (findIt == s_ImageSetToPickupTypeMap.end())
        {
            LOG_WARNING("Unsupported custom pickup image set: " + pickupImageSet + "; using default treasure pickup");
            return PickupType_Default;
        }

        return findIt->second;''')

# 4) One unsupported actor must not reject an otherwise playable custom level.
p=ROOT/'OpenClaw/Engine/Util/Converters.cpp'
s=p.read_text(encoding='utf-8')
old='''        FAIL("Failed to load level " + ToStr(levelNumber) + " due to unimplemented actor prototypes");
    }

    root->LinkEndChild(CreateClawActor(wapWwd));'''
new='''        LOG_WARNING("Continuing level " + ToStr(levelNumber) + " with unsupported actors skipped");
    }

    root->LinkEndChild(CreateClawActor(wapWwd));'''
if old not in s: raise SystemExit('Converters FAIL pattern missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# 5) Physics components with a missing render image get a conservative fallback box.
p=ROOT/'OpenClaw/Engine/Actor/Components/PhysicsComponent.cpp'
s=p.read_text(encoding='utf-8')
old='''            shared_ptr<Image> pImage = MakeStrongPtr(pRenderComponent->GetCurrentImage());
            assert(pImage != nullptr);

            // Also offset position
            m_ActorBodyDef.position = Point(m_ActorBodyDef.position.x + pImage->GetOffsetX(), m_ActorBodyDef.position.y + pImage->GetOffsetY());

            m_ActorBodyDef.size.x = pImage->GetWidth();
            m_ActorBodyDef.size.y = pImage->GetHeight();

            //LOG("-------- X: " + ToStr(pImage->GetOffsetX()) + " Y: " + ToStr(pImage->GetOffsetY()));

            for (ActorFixtureDef fixture : m_ActorBodyDef.fixtureList)
            {
                if (fixture.size.IsZero())
                {
                    fixture.size = Point(pImage->GetWidth(), pImage->GetHeight());
                }
            }'''
new='''            shared_ptr<Image> pImage = MakeStrongPtr(pRenderComponent->GetCurrentImage());
            if (pImage)
            {
                // Also offset position
                m_ActorBodyDef.position = Point(m_ActorBodyDef.position.x + pImage->GetOffsetX(), m_ActorBodyDef.position.y + pImage->GetOffsetY());
                m_ActorBodyDef.size.x = pImage->GetWidth();
                m_ActorBodyDef.size.y = pImage->GetHeight();
            }
            else
            {
                LOG_WARNING("Missing render image for physics actor '" + m_pOwner->GetName() + "'; using 32x32 fallback body");
                m_ActorBodyDef.size = Point(32, 32);
            }

            for (ActorFixtureDef &fixture : m_ActorBodyDef.fixtureList)
            {
                if (fixture.size.IsZero()) fixture.size = m_ActorBodyDef.size;
            }'''
if old not in s: raise SystemExit('Physics fallback pattern missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# 6) Add level-14 compatibility metadata using level 13 plus generic base mappings.
meta_dir=ROOT/'Build_Release/ASSETS/LEVEL_METADATA'
level13=ET.parse(meta_dir/'LEVEL13.XML')
root=level13.getroot()
root.find('LevelNumber').text='14'
root.find('LevelName').text='Level - 14 compatibility (Tiger Island)'
sp=root.find('ClawSpawnPositions')
for child in list(sp): sp.remove(child)
for num,x,y in [(0,1723,3173),(1,9845,3037),(2,19892,3549)]:
    ET.SubElement(sp,'ClawSpawnPosition',spawnNumber=str(num),x=str(x),y=str(y))
logic_root=root.find('LogicsToActorPrototypes')
known={e.attrib.get('logic') for e in logic_root}
# Generic/base mappings from every implemented level are safe compatibility additions.
for f in sorted(meta_dir.glob('LEVEL*.XML')):
    if f.name=='LEVEL13.XML': continue
    rr=ET.parse(f).getroot().find('LogicsToActorPrototypes')
    if rr is None: continue
    for e in rr:
        logic=e.attrib.get('logic'); proto=e.attrib.get('actorPrototype','')
        if logic and logic not in known and (proto.startswith('ActorPrototype_Base') or proto=='ActorPrototype_Null'):
            ET.SubElement(logic_root,'LogicToActorPrototype',logic=logic,actorPrototype=proto)
            known.add(logic)
ET.indent(level13, space='    ')
level13.write(meta_dir/'LEVEL14.XML',encoding='utf-8',xml_declaration=False)

# 7) Original LOAD CUSTOM LEVEL menu item emits a unique two-event bridge chord.
for menu_path in [ROOT/'Build_Release/ASSETS/MENU.xml', ROOT/'Build_Release/MENU.xml']:
    if not menu_path.exists(): continue
    txt=menu_path.read_text(encoding='utf-8')
    pat=re.compile(r'(<Name>LOAD_CUSTOM_LEVEL_BUTTON</Name>.*?<Position[^>]+/>\s*)(<GeneratedEvent>.*?</GeneratedEvent>)',re.S)
    m=pat.search(txt)
    if not m: raise SystemExit(f'custom menu item missing in {menu_path}')
    events='''<GeneratedEvent>\n                <Type>ToggleFullscreen</Type>\n            </GeneratedEvent>\n            <GeneratedEvent>\n                <Type>ToggleAspectRatio</Type>\n            </GeneratedEvent>'''
    txt=txt[:m.start(2)]+events+txt[m.end(2):]
    menu_path.write_text(txt,encoding='utf-8')

print('runtime 2.4.9 robust patches applied')
