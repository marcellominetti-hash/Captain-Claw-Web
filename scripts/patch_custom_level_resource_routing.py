#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_custom_level_resource_routing.py <upstream-root>")

root = Path(sys.argv[1]) / "OpenClaw/Engine"

# Several older loaders/components still bypass ResourceMgr and read CLAW.REZ
# directly via BaseGameApp::GetResourceCache(). That prevents a selected
# custom-level archive from overriding WWD/PAL/PID/ANI/WAV/MIDI resources.
# Route only the ResourceCache operations for which ResourceMgr has an exact
# priority-aware equivalent. Normal builds keep the same result when no
# CUSTOM_LEVEL.ZIP exists; when it does exist, priority becomes:
# CUSTOM_LEVEL.ZIP -> ASSETS.ZIP -> CLAW.REZ.
replacements = {
    "g_pApp->GetResourceCache()->GetHandle(": "g_pApp->GetResourceMgr()->VGetHandle(",
    "g_pApp->GetResourceCache()->Match(": "g_pApp->GetResourceMgr()->VMatch(",
    "g_pApp->GetResourceCache()->Preload(": "g_pApp->GetResourceMgr()->VPreload(",
    "g_pApp->GetResourceCache()->GetAllFilesInDirectory(": "g_pApp->GetResourceMgr()->VGetAllFilesInDirectory(",
}

# BaseGameApp.h historically only forward-declared IResourceMgr because callers
# did not invoke methods through it. Once legacy loaders use GetResourceMgr(),
# they need the complete interface type. Include it centrally to keep the patch
# deterministic and avoid path-specific includes in every component/loader.
app_header = root / "GameApp/BaseGameApp.h"
header_text = app_header.read_text(encoding="utf-8", errors="surrogateescape")
needle = '#include "../SharedDefines.h"\n'
if needle not in header_text:
    raise RuntimeError("BaseGameApp.h include anchor not found")
if '#include "../Resource/ResourceMgr.h"' not in header_text:
    header_text = header_text.replace(
        needle,
        needle + '#include "../Resource/ResourceMgr.h"\n',
        1,
    )
    app_header.write_text(header_text, encoding="utf-8", errors="surrogateescape")

changed = []
counts = {k: 0 for k in replacements}
for path in sorted(root.rglob("*.cpp")):
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    new = text
    local = 0
    for old, repl in replacements.items():
        c = new.count(old)
        if c:
            new = new.replace(old, repl)
            counts[old] += c
            local += c
    if new != text:
        path.write_text(new, encoding="utf-8", errors="surrogateescape")
        changed.append((path.relative_to(root.parent.parent), local))

if counts["g_pApp->GetResourceCache()->GetHandle("] < 5:
    raise RuntimeError(f"unexpectedly few GetHandle routes patched: {counts}")
if counts["g_pApp->GetResourceCache()->Match("] < 1:
    raise RuntimeError(f"expected at least one wildcard Match route: {counts}")

print("priority-aware resource routing applied")
for path, count in changed:
    print(f"  {path}: {count}")
print(counts)
