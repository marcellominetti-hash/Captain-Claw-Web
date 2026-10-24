#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) < 2:
    raise SystemExit("usage: inject_collection_v2_runtime.py <html> [<html> ...]")

script_tag = '    <script src="custom-levels.js"></script>\n'
module_anchor = '    <script type="text/javascript">\n      var loadingElement = document.getElementById("loading");'
watchdog_anchor = '            if (window.startLoadWatchdog) window.startLoadWatchdog();'
mount_block = '''            if (window.ClawCustomLevels && typeof window.ClawCustomLevels.mountSelected === 'function') {
              const customSuccess = window.ClawCustomLevels.mountSelected();
              if (!customSuccess) console.error('Failed to mount selected custom level');
            }
'''

for arg in sys.argv[1:]:
    path = Path(arg)
    text = path.read_text(encoding='utf-8')

    if 'src="custom-levels.js"' not in text:
        if module_anchor not in text:
            raise RuntimeError(f"module anchor missing in {path}")
        text = text.replace(module_anchor, script_tag + module_anchor, 1)

    if 'ClawCustomLevels.mountSelected' not in text:
        if watchdog_anchor not in text:
            raise RuntimeError(f"preRun watchdog anchor missing in {path}")
        text = text.replace(watchdog_anchor, mount_block + watchdog_anchor, 1)

    # APK branding only; this does not affect engine/runtime behavior.
    text = text.replace('<title>Claw Web</title>', '<title>Capitan Artiglio</title>')
    text = text.replace('apple-mobile-web-app-title" content="Claw Web"',
                        'apple-mobile-web-app-title" content="Capitan Artiglio"')

    path.write_text(text, encoding='utf-8')
    print(f"Collection v2 runtime injected: {path}")
