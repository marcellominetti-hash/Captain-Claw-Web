#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
render_path = root / 'OpenClaw/Engine/Actor/Components/RenderComponent.cpp'
render = render_path.read_text(encoding='utf-8')

# PortRenderStatus is injected by patch_actor_diagnostics.py before this patch runs.
if 'static void PortRenderStatus' not in render:
    raise SystemExit('PortRenderStatus helper not found; run patch_actor_diagnostics.py first')

# The original main-plane pass allocates a temporary TileList for every run of
# equal collision tiles. That is needlessly expensive on the browser main
# thread. Preserve the exact event semantics while scanning runs in-place.
process_old = '''void TilePlaneRenderComponent::ProcessMainPlaneTiles(const TileList& tileList)
{
    const int tilesCount = tileList.size();
    int currentTileIdx = 0;
    
    while (currentTileIdx < tilesCount)
    {
        TileList continuousTiles = GetAllContinuousTiles(tileList, currentTileIdx);
        assert(continuousTiles.size() >= 1);

        // Discard all empty tiles
        if (continuousTiles[0] > -1)
        {
            int tileWidth = m_PlaneProperties.tilePixelWidth;
            TileInfo firstTileInfo = GetTileInfo(tileList, currentTileIdx);
            int currentX = firstTileInfo.x;
            int currentY = firstTileInfo.y;

            shared_ptr<EventData_Collideable_Tile_Created> pEvent(
                new EventData_Collideable_Tile_Created(firstTileInfo.tileId, currentX, currentY, continuousTiles.size()));
            IEventMgr::Get()->VTriggerEvent(pEvent);

            /*for (int tileId : continuousTiles)
            {
                shared_ptr<EventData_Collideable_Tile_Created> pEvent(
                    new EventData_Collideable_Tile_Created(tileId, currentX, currentY, 1));
                IEventMgr::Get()->VTriggerEvent(pEvent);

                currentX += tileWidth;
            }*/
        }

        currentTileIdx += continuousTiles.size();
    }
}
'''
process_new = '''void TilePlaneRenderComponent::ProcessMainPlaneTiles(const TileList& tileList)
{
    const int tilesCount = static_cast<int>(tileList.size());
    int currentTileIdx = 0;
    int runCount = 0;
    bool firstCollisionEvent = true;

    PortRenderStatus("Plane TilePlane: collision scan start " + std::to_string(tilesCount) + " tiles");

    while (currentTileIdx < tilesCount)
    {
        const TileInfo firstTileInfo = GetTileInfo(tileList, currentTileIdx);
        int runLength = 1;

        while (currentTileIdx + runLength < tilesCount)
        {
            const TileInfo nextTileInfo = GetTileInfo(tileList, currentTileIdx + runLength);
            if (nextTileInfo.tileId != firstTileInfo.tileId || nextTileInfo.y != firstTileInfo.y)
            {
                break;
            }
            ++runLength;
        }

        // Preserve the original behaviour: one collision event for every
        // horizontal run of the same non-empty tile.
        if (firstTileInfo.tileId > -1)
        {
            if (firstCollisionEvent)
            {
                PortRenderStatus("Plane TilePlane: first collision event");
            }

            shared_ptr<EventData_Collideable_Tile_Created> pEvent(
                new EventData_Collideable_Tile_Created(
                    firstTileInfo.tileId,
                    firstTileInfo.x,
                    firstTileInfo.y,
                    runLength));
            IEventMgr::Get()->VTriggerEvent(pEvent);

            if (firstCollisionEvent)
            {
                PortRenderStatus("Plane TilePlane: first collision event returned");
                firstCollisionEvent = false;
            }
        }

        currentTileIdx += runLength;
        ++runCount;

        if ((runCount % 512) == 0)
        {
            PortRenderStatus(
                "Plane TilePlane: collision scan " +
                std::to_string(currentTileIdx) + "/" + std::to_string(tilesCount));
        }
    }

    PortRenderStatus("Plane TilePlane: collision scan complete " + std::to_string(runCount) + " runs");
}
'''
if process_old not in render:
    raise SystemExit('TilePlane ProcessMainPlaneTiles anchor not found')
render = render.replace(process_old, process_new, 1)

start = '''bool TilePlaneRenderComponent::VDelegateInit(TiXmlElement* pXmlData)
{
    TiXmlElement* pPlaneProperties = pXmlData->FirstChildElement("PlaneProperties");
'''
start_repl = '''bool TilePlaneRenderComponent::VDelegateInit(TiXmlElement* pXmlData)
{
    PortRenderStatus("Plane TilePlane: VDelegateInit start");
    TiXmlElement* pPlaneProperties = pXmlData->FirstChildElement("PlaneProperties");
'''
if start not in render:
    raise SystemExit('TilePlane VDelegateInit start anchor not found')
render = render.replace(start, start_repl, 1)

props = '''        LOG_ERROR("Could not locate PlaneProperties.");
        return false;
    }

    // If anyone knows a better way, tell me
'''
props_repl = '''        PortRenderStatus("Plane TilePlane: PlaneProperties MISSING");
        LOG_ERROR("Could not locate PlaneProperties.");
        return false;
    }
    PortRenderStatus("Plane TilePlane: PlaneProperties found");

    // If anyone knows a better way, tell me
'''
if props not in render:
    raise SystemExit('TilePlane PlaneProperties anchor not found')
render = render.replace(props, props_repl, 1)

geometry = '''    m_PlaneProperties.tilesOnAxisX = m_PlaneProperties.planePixelWidth / m_PlaneProperties.tilePixelWidth;
    m_PlaneProperties.tilesOnAxisY = m_PlaneProperties.planePixelHeight / m_PlaneProperties.tilePixelHeight;

    // Filler tile - for the background plane

    WapPal* pPallette = g_pApp->GetCurrentPalette();
'''
geometry_repl = '''    PortRenderStatus("Plane TilePlane: properties parsed");
    m_PlaneProperties.tilesOnAxisX = m_PlaneProperties.planePixelWidth / m_PlaneProperties.tilePixelWidth;
    m_PlaneProperties.tilesOnAxisY = m_PlaneProperties.planePixelHeight / m_PlaneProperties.tilePixelHeight;
    PortRenderStatus("Plane TilePlane: geometry ready " + std::to_string(m_PlaneProperties.tilesOnAxisX) + "x" + std::to_string(m_PlaneProperties.tilesOnAxisY));

    // Filler tile - for the background plane

    PortRenderStatus("Plane TilePlane: creating filler image");
    WapPal* pPallette = g_pApp->GetCurrentPalette();
'''
if geometry not in render:
    raise SystemExit('TilePlane geometry anchor not found')
render = render.replace(geometry, geometry_repl, 1)

fill = '''        g_pApp->GetRenderer()));
    assert(m_pFillImage != nullptr);

    //-------------------------------------------------------------------------
    // Fill plane tiles
'''
fill_repl = '''        g_pApp->GetRenderer()));
    assert(m_pFillImage != nullptr);
    PortRenderStatus("Plane TilePlane: filler image ready");

    //-------------------------------------------------------------------------
    // Fill plane tiles
'''
if fill not in render:
    raise SystemExit('TilePlane filler-image anchor not found')
render = render.replace(fill, fill_repl, 1)

tile_setup = '''    int32 tileIdx = 0;

    TileList tileList;
    for (TiXmlElement* pTileNode = pTileElements->FirstChildElement(); 
'''
tile_setup_repl = '''    int32 tileIdx = 0;

    TileList tileList;
    const long long portExpectedTiles =
        static_cast<long long>(m_PlaneProperties.tilesOnAxisX) *
        static_cast<long long>(m_PlaneProperties.tilesOnAxisY);
    if (portExpectedTiles > 0 && portExpectedTiles <= 10000000)
    {
        tileList.reserve(static_cast<size_t>(portExpectedTiles));
        m_TileImageList.reserve(static_cast<size_t>(portExpectedTiles));
    }
    PortRenderStatus(
        "Plane TilePlane: tile decode start expected " +
        std::to_string(portExpectedTiles));

    for (TiXmlElement* pTileNode = pTileElements->FirstChildElement(); 
'''
if tile_setup not in render:
    raise SystemExit('TilePlane tile setup anchor not found')
render = render.replace(tile_setup, tile_setup_repl, 1)

tile_progress = '''        tileIdx++;
    }

    if (m_PlaneProperties.isMainPlane)
    {
        ProcessMainPlaneTiles(tileList);
    }

    if (m_TileImageList.empty())
'''
tile_progress_repl = '''        tileIdx++;

        if ((tileIdx % 4096) == 0)
        {
            PortRenderStatus("Plane TilePlane: decoded " + std::to_string(tileIdx) + " tiles");
        }
    }

    PortRenderStatus(
        "Plane TilePlane: tile decode complete " +
        std::to_string(tileIdx) + " tiles");

    if (m_PlaneProperties.isMainPlane)
    {
        PortRenderStatus("Plane TilePlane: processing main-plane collisions");
        ProcessMainPlaneTiles(tileList);
        PortRenderStatus("Plane TilePlane: main-plane collisions ready");
    }

    if (m_TileImageList.empty())
'''
if tile_progress not in render:
    raise SystemExit('TilePlane tile progress anchor not found')
render = render.replace(tile_progress, tile_progress_repl, 1)

success = '''    m_PositionRect = { 0, 0, planeWidth, planeHeight };

    return true;
}
'''
success_repl = '''    m_PositionRect = { 0, 0, planeWidth, planeHeight };

    PortRenderStatus("Plane TilePlane: VDelegateInit complete");
    return true;
}
'''
if success not in render:
    raise SystemExit('TilePlane success anchor not found')
render = render.replace(success, success_repl, 1)

render_path.write_text(render, encoding='utf-8', newline='\n')

required = [
    'Plane TilePlane: geometry ready',
    'Plane TilePlane: filler image ready',
    'Plane TilePlane: tile decode complete',
    'Plane TilePlane: collision scan complete',
    'Plane TilePlane: VDelegateInit complete',
]
if any(marker not in render for marker in required):
    raise SystemExit('Granular TilePlane diagnostics/optimization were not injected')

print('Granular TilePlane diagnostics + browser collision-scan optimization applied successfully.')
