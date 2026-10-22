#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()

# Instrument ActorFactory so the phone shows the exact first component that stalls.
actor_path = root / 'OpenClaw/Engine/Actor/ActorFactory.cpp'
actor = actor_path.read_text(encoding='utf-8')

inc_anchor = '#include <tinyxml.h>\n\n'
inc_repl = '#include <tinyxml.h>\n#ifdef __EMSCRIPTEN__\n#include <emscripten/emscripten.h>\n#endif\n\n'
if inc_anchor not in actor:
    raise SystemExit('ActorFactory include anchor not found')
actor = actor.replace(inc_anchor, inc_repl, 1)

helper_anchor = '#include "../Resource/Loaders/XmlLoader.h"\n\n'
helper = r'''#include "../Resource/Loaders/XmlLoader.h"

static void PortActorStatus(const std::string& message)
{
#ifdef __EMSCRIPTEN__
    EM_ASM({
        if (typeof window !== 'undefined' && typeof window.__setClawLoadStatus === 'function') {
            window.__setClawLoadStatus(UTF8ToString($0));
        }
    }, message.c_str());
#endif
}

'''
if helper_anchor not in actor:
    raise SystemExit('ActorFactory helper anchor not found')
actor = actor.replace(helper_anchor, helper, 1)

entry = '''StrongActorPtr ActorFactory::CreateActor(TiXmlElement* pActorRoot, TiXmlElement* overrides)\n{\n    //PROFILE_CPU("Create actor");\n    uint32 nextActorGUID = GetNextActorGUID();\n    StrongActorPtr actor(new Actor(nextActorGUID));\n    if (!actor->Init(pActorRoot))\n'''
entry_repl = '''StrongActorPtr ActorFactory::CreateActor(TiXmlElement* pActorRoot, TiXmlElement* overrides)\n{\n    //PROFILE_CPU("Create actor");\n    uint32 nextActorGUID = GetNextActorGUID();\n    const char* portTypeRaw = pActorRoot ? pActorRoot->Attribute("Type") : nullptr;\n    std::string portType = portTypeRaw ? portTypeRaw : "(unknown)";\n    bool portDiag = (nextActorGUID <= 4);\n    if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: Actor::Init");\n    StrongActorPtr actor(new Actor(nextActorGUID));\n    if (!actor->Init(pActorRoot))\n'''
if entry not in actor:
    raise SystemExit('ActorFactory CreateActor entry anchor not found')
actor = actor.replace(entry, entry_repl, 1)

init_ready = '''    }\n\n    // Loop through each child element and load the component\n    for (TiXmlElement* node = pActorRoot->FirstChildElement(); node != NULL; node = node->NextSiblingElement())\n    {\n        StrongActorComponentPtr component = VCreateComponent(node);\n'''
init_ready_repl = '''    }\n\n    if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: Actor::Init ready");\n\n    // Loop through each child element and load the component\n    for (TiXmlElement* node = pActorRoot->FirstChildElement(); node != NULL; node = node->NextSiblingElement())\n    {\n        std::string portComponentName = node && node->Value() ? node->Value() : "(unknown component)";\n        if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: " + portComponentName + " VInit");\n        StrongActorComponentPtr component = VCreateComponent(node);\n        if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: " + portComponentName + " VInit returned");\n'''
if init_ready not in actor:
    raise SystemExit('ActorFactory component-loop anchor not found')
actor = actor.replace(init_ready, init_ready_repl, 1)

post = '''    // Place for some hacks\n\n    actor->PostInit();\n    actor->PostPostInit();\n\n    return actor;\n}\n'''
post_repl = '''    // Place for some hacks\n\n    if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: PostInit");\n    actor->PostInit();\n    if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: PostInit ready");\n    actor->PostPostInit();\n    if (portDiag) PortActorStatus("Actor " + std::to_string(nextActorGUID) + " [" + portType + "]: COMPLETE");\n\n    return actor;\n}\n'''
if post not in actor:
    raise SystemExit('ActorFactory PostInit anchor not found')
actor = actor.replace(post, post_repl, 1)
actor_path.write_text(actor, encoding='utf-8', newline='\n')

# Instrument BaseRenderComponent for Plane actors. The first WWD actor is a plane,
# so this reveals whether the stall is directory enumeration, PID loading, or
# TilePlaneRenderComponent::VDelegateInit.
render_path = root / 'OpenClaw/Engine/Actor/Components/RenderComponent.cpp'
render = render_path.read_text(encoding='utf-8')

render_inc_anchor = '#include <cctype>\n\n'
render_inc_repl = '#include <cctype>\n#ifdef __EMSCRIPTEN__\n#include <emscripten/emscripten.h>\n#endif\n\n'
if render_inc_anchor not in render:
    raise SystemExit('RenderComponent include anchor not found')
render = render.replace(render_inc_anchor, render_inc_repl, 1)

render_helper_anchor = 'const char* HUDRenderComponent::g_Name = "HUDRenderComponent";\n\n'
render_helper = r'''const char* HUDRenderComponent::g_Name = "HUDRenderComponent";

static void PortRenderStatus(const std::string& message)
{
#ifdef __EMSCRIPTEN__
    EM_ASM({
        if (typeof window !== 'undefined' && typeof window.__setClawLoadStatus === 'function') {
            window.__setClawLoadStatus(UTF8ToString($0));
        }
    }, message.c_str());
#endif
}

'''
if render_helper_anchor not in render:
    raise SystemExit('RenderComponent helper anchor not found')
render = render.replace(render_helper_anchor, render_helper, 1)

start_anchor = '''bool BaseRenderComponent::VInit(TiXmlElement* pXmlData)\n{\n    assert(pXmlData != NULL);\n\n    WapPal* palette = g_pApp->GetCurrentPalette();\n'''
start_repl = '''bool BaseRenderComponent::VInit(TiXmlElement* pXmlData)\n{\n    assert(pXmlData != NULL);\n\n    const char* portParentTypeRaw = (pXmlData->Parent() && pXmlData->Parent()->ToElement()) ? pXmlData->Parent()->ToElement()->Attribute("Type") : nullptr;\n    bool portPlaneDiag = portParentTypeRaw && std::string(portParentTypeRaw) == "Plane";\n    if (portPlaneDiag) PortRenderStatus("Plane render: BaseRenderComponent::VInit start");\n\n    WapPal* palette = g_pApp->GetCurrentPalette();\n'''
if start_anchor not in render:
    raise SystemExit('RenderComponent VInit start anchor not found')
render = render.replace(start_anchor, start_repl, 1)

enum_anchor = '''        std::vector<std::string> matchingPathNames =\n            g_pApp->GetResourceCache()->GetAllFilesInDirectory(imageDir.c_str());\n\n        // Skip if directory is empty'''
enum_repl = '''        if (portPlaneDiag) PortRenderStatus("Plane render: enumerate " + imageDir);\n        std::vector<std::string> matchingPathNames =\n            g_pApp->GetResourceCache()->GetAllFilesInDirectory(imageDir.c_str());\n        if (portPlaneDiag) PortRenderStatus("Plane render: directory count " + std::to_string(matchingPathNames.size()));\n\n        // Skip if directory is empty'''
if enum_anchor not in render:
    raise SystemExit('RenderComponent directory enumeration anchor not found')
render = render.replace(enum_anchor, enum_repl, 1)

pid_loop_anchor = '''        for (std::string& imagePath : matchingPathNames)\n        {\n            // Only load known image formats\n'''
pid_loop_repl = '''        int portPidIndex = 0;\n        for (std::string& imagePath : matchingPathNames)\n        {\n            ++portPidIndex;\n            if (portPlaneDiag && (portPidIndex <= 5 || (portPidIndex % 10) == 0 || portPidIndex == (int)matchingPathNames.size()))\n            {\n                PortRenderStatus("Plane render: PID " + std::to_string(portPidIndex) + "/" + std::to_string(matchingPathNames.size()) + " " + imagePath);\n            }\n            // Only load known image formats\n'''
if pid_loop_anchor not in render:
    raise SystemExit('RenderComponent PID loop anchor not found')
render = render.replace(pid_loop_anchor, pid_loop_repl, 1)

return_anchor = '''    return VDelegateInit(pXmlData);\n}\n'''
return_repl = '''    if (portPlaneDiag) PortRenderStatus("Plane render: entering TilePlane VDelegateInit");\n    bool portInitResult = VDelegateInit(pXmlData);\n    if (portPlaneDiag) PortRenderStatus("Plane render: TilePlane VDelegateInit returned");\n    return portInitResult;\n}\n'''
if return_anchor not in render:
    raise SystemExit('RenderComponent VDelegateInit return anchor not found')
render = render.replace(return_anchor, return_repl, 1)

render_path.write_text(render, encoding='utf-8', newline='\n')

if 'PortActorStatus' not in actor or 'PortRenderStatus' not in render:
    raise SystemExit('Actor/render diagnostics were not injected')

print('ActorFactory + Plane RenderComponent diagnostics patch applied successfully.')
