#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
render_path = root / 'OpenClaw/Engine/Actor/Components/RenderComponent.cpp'
render = render_path.read_text(encoding='utf-8')

# PortRenderStatus is injected by patch_actor_diagnostics.py before this patch runs.
if 'static void PortRenderStatus' not in render:
    raise SystemExit('PortRenderStatus helper not found; run patch_actor_diagnostics.py first')

start = '''bool TilePlaneRenderComponent::VDelegateInit(TiXmlElement* pXmlData)\n{\n    TiXmlElement* pPlaneProperties = pXmlData->FirstChildElement("PlaneProperties");\n'''
start_repl = '''bool TilePlaneRenderComponent::VDelegateInit(TiXmlElement* pXmlData)\n{\n    PortRenderStatus("Plane TilePlane: VDelegateInit start");\n    TiXmlElement* pPlaneProperties = pXmlData->FirstChildElement("PlaneProperties");\n'''
if start not in render:
    raise SystemExit('TilePlane VDelegateInit start anchor not found')
render = render.replace(start, start_repl, 1)

props = '''        LOG_ERROR("Could not locate PlaneProperties.");\n        return false;\n    }\n\n    // If anyone knows a better way, tell me\n'''
props_repl = '''        PortRenderStatus("Plane TilePlane: PlaneProperties MISSING");\n        LOG_ERROR("Could not locate PlaneProperties.");\n        return false;\n    }\n    PortRenderStatus("Plane TilePlane: PlaneProperties found");\n\n    // If anyone knows a better way, tell me\n'''
if props not in render:
    raise SystemExit('TilePlane PlaneProperties anchor not found')
render = render.replace(props, props_repl, 1)

geometry = '''    m_PlaneProperties.tilesOnAxisX = m_PlaneProperties.planePixelWidth / m_PlaneProperties.tilePixelWidth;\n    m_PlaneProperties.tilesOnAxisY = m_PlaneProperties.planePixelHeight / m_PlaneProperties.tilePixelHeight;\n\n    // Filler tile - for the background plane\n\n    WapPal* pPallette = g_pApp->GetCurrentPalette();\n'''
geometry_repl = '''    PortRenderStatus("Plane TilePlane: properties parsed");\n    m_PlaneProperties.tilesOnAxisX = m_PlaneProperties.planePixelWidth / m_PlaneProperties.tilePixelWidth;\n    m_PlaneProperties.tilesOnAxisY = m_PlaneProperties.planePixelHeight / m_PlaneProperties.tilePixelHeight;\n    PortRenderStatus("Plane TilePlane: geometry ready " + std::to_string(m_PlaneProperties.tilesOnAxisX) + "x" + std::to_string(m_PlaneProperties.tilesOnAxisY));\n\n    // Filler tile - for the background plane\n\n    PortRenderStatus("Plane TilePlane: creating filler image");\n    WapPal* pPallette = g_pApp->GetCurrentPalette();\n'''
if geometry not in render:
    raise SystemExit('TilePlane geometry anchor not found')
render = render.replace(geometry, geometry_repl, 1)

fill = '''        g_pApp->GetRenderer()));\n    assert(m_pFillImage != nullptr);\n\n    //-------------------------------------------------------------------------\n    // Fill plane tiles\n'''
fill_repl = '''        g_pApp->GetRenderer()));\n    assert(m_pFillImage != nullptr);\n    PortRenderStatus("Plane TilePlane: filler image ready");\n\n    //-------------------------------------------------------------------------\n    // Fill plane tiles\n'''
if fill not in render:
    raise SystemExit('TilePlane filler-image anchor not found')
render = render.replace(fill, fill_repl, 1)

render_path.write_text(render, encoding='utf-8', newline='\n')

if 'Plane TilePlane: geometry ready' not in render or 'Plane TilePlane: filler image ready' not in render:
    raise SystemExit('Granular TilePlane diagnostics were not injected')

print('Granular TilePlane runtime diagnostics patch applied successfully.')
