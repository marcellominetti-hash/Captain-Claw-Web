from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path('upstream')

# BaseGameLogic: custom levels start at the coordinates authored in the WWD,
# not at the checkpoint coordinates of the original base level.
p=ROOT/'OpenClaw/Engine/GameApp/BaseGameLogic.cpp'
s=p.read_text(encoding='utf-8')
if '#include <fstream>' not in s:
    anchor='#include <cassert>'
    if anchor in s:
        s=s.replace(anchor, anchor+'\n#include <fstream>',1)
    else:
        s='#include <fstream>\n'+s
old='''    // Set claw to spawn location
    m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
    pEventMgr->VTriggerEvent(IEventDataPtr(new EventData_Teleport_Actor(clawId, m_CurrentSpawnPosition)));
'''
new='''    // Set Claw to spawn location. A selected custom WWD owns its own StartX/StartY;
    // base-level checkpoint coordinates are only valid for the original campaign.
    bool useCustomWwdSpawn = false;
#ifdef __EMSCRIPTEN__
    {
        std::ifstream selectedCustomArchive("/CUSTOM_LEVEL.ZIP", std::ios::binary);
        useCustomWwdSpawn = selectedCustomArchive.good() && m_pCurrentLevel->m_LoadedCheckpoint == 0;
    }
#endif
    if (useCustomWwdSpawn)
    {
        m_CurrentSpawnPosition = Point(pWwd->properties.startX, pWwd->properties.startY);
        LOG_WARNING("CUSTOM_LEVEL_SPAWN " + ToStr((int)pWwd->properties.startX) + "," + ToStr((int)pWwd->properties.startY));
    }
    else
    {
        m_CurrentSpawnPosition = GetSpawnPosition(m_pCurrentLevel->m_LeveNumber, m_pCurrentLevel->m_LoadedCheckpoint);
    }
    pEventMgr->VTriggerEvent(IEventDataPtr(new EventData_Teleport_Actor(clawId, m_CurrentSpawnPosition)));
'''
if old not in s: raise SystemExit('spawn block not found')
s=s.replace(old,new,1)
# Deterministic warning-level signal survives Release logging and is used by CI/runtime smoke tests.
old2='''    LOG("Level loaded !");
    LOG("Level name: " + m_pCurrentLevel->m_LevelName);'''
new2='''    LOG("Level loaded !");
#ifdef __EMSCRIPTEN__
    {
        std::ifstream selectedCustomArchive("/CUSTOM_LEVEL.ZIP", std::ios::binary);
        if (selectedCustomArchive.good()) LOG_WARNING("CUSTOM_LEVEL_READY");
    }
#endif
    LOG("Level name: " + m_pCurrentLevel->m_LevelName);'''
if old2 not in s: raise SystemExit('ready signal block not found')
s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8')

# Level 14 compatibility: TProjectile in real level-14/custom content is not the
# level-13 puff-dart spawner. Removing the inherited mapping is safer than
# instantiating dozens of invalid level-13 actors; unsupported actors are skipped
# by the robust converter instead of aborting the level.
meta=ROOT/'Build_Release/ASSETS/LEVEL_METADATA/LEVEL14.XML'
tree=ET.parse(meta); root=tree.getroot(); lr=root.find('LogicsToActorPrototypes')
for e in list(lr):
    if e.attrib.get('logic')=='TProjectile': lr.remove(e)
ET.indent(tree,space='    ')
tree.write(meta,encoding='utf-8',xml_declaration=False)
print('follow-up runtime patches applied')
