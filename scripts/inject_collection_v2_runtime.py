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

# The native Collection v2 home launches index.html with mode=custom/favorites.
# Route those *library* requests to levels.html before the game runtime starts.
# A selected level also uses mode=custom, but carries level/archive; never redirect it.
router_marker = 'Collection v2 mode router'
router_anchor = '</head>'
router_block = '''    <script>
      // Collection v2 mode router.
      (() => {
        const params = new URLSearchParams(window.location.search);
        if (params.get('android') !== '1' || params.get('shell') !== 'v2') return;
        const mode = params.get('mode');
        const selectedLevel = params.get('level') || params.get('archive');
        if (!selectedLevel && (mode === 'custom' || mode === 'favorites')) {
          const filter = mode === 'favorites' ? 'favorites' : 'all';
          window.location.replace(`levels.html?android=1&shell=v2&filter=${filter}`);
        }
      })();
    </script>
'''

asset_marker = 'Collection v2 Android embedded CLAW.REZ bridge'
asset_anchor = '''async function prepareAssetStorage() {
  try {
'''
asset_replacement = '''async function prepareAssetStorage() {
  try {
    // Collection v2 Android embedded CLAW.REZ bridge.
    // The private APK contains the original archive under assets/www, served
    // through WebViewAssetLoader on the same appassets origin. Prefer it over
    // IndexedDB so campaign and custom levels always share one authoritative
    // CLAW.REZ and the Android build never asks the user to upload it again.
    const androidEmbedded = new URLSearchParams(window.location.search).get('android') === '1';
    if (androidEmbedded) {
      try {
        const response = await fetch('CLAW.REZ', {
          cache: 'no-store',
          credentials: 'same-origin'
        });
        if (response.ok) {
          const bundledRez = await response.blob();
          const sizeOk = bundledRez.size >= REZ_MIN_SIZE && bundledRez.size <= REZ_MAX_SIZE;
          const signatureOk = sizeOk && await hasRezSignature(bundledRez);
          if (sizeOk && signatureOk) {
            clawRezData = new Uint8Array(await bundledRez.arrayBuffer());
            hideAssetUpload();
            console.log(`[android-apk] Bundled CLAW.REZ ready (${(clawRezData.length / 1024 / 1024).toFixed(2)}MB)`);
            // openclaw.wasm/.data are APK assets too. Do not consult
            // navigator.onLine here: appassets remains readable while offline.
            return true;
          }
          console.warn('[android-apk] Bundled CLAW.REZ failed size/signature validation; falling back to normal storage flow.');
        } else {
          console.warn(`[android-apk] Bundled CLAW.REZ unavailable (HTTP ${response.status}); falling back to normal storage flow.`);
        }
      } catch (embeddedError) {
        console.warn('[android-apk] Could not read bundled CLAW.REZ; falling back to normal storage flow.', embeddedError);
      }
    }
'''

patched_asset_dirs = set()

for arg in sys.argv[1:]:
    path = Path(arg)
    text = path.read_text(encoding='utf-8')

    if router_marker not in text:
        if router_anchor not in text:
            raise RuntimeError(f"head anchor missing in {path}")
        text = text.replace(router_anchor, router_block + router_anchor, 1)

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

    asset_dir = path.parent.resolve()
    if asset_dir in patched_asset_dirs:
        continue
    patched_asset_dirs.add(asset_dir)

    asset_loader = asset_dir / 'asset-loader.js'
    if not asset_loader.is_file():
        raise RuntimeError(f"asset-loader.js missing next to {path}")
    asset_text = asset_loader.read_text(encoding='utf-8')
    if asset_marker not in asset_text:
        if asset_text.count(asset_anchor) != 1:
            raise RuntimeError(
                f"expected exactly one prepareAssetStorage anchor in {asset_loader}, "
                f"got {asset_text.count(asset_anchor)}"
            )
        asset_text = asset_text.replace(asset_anchor, asset_replacement, 1)
        asset_loader.write_text(asset_text, encoding='utf-8')
        print(f"Android embedded CLAW.REZ bridge injected: {asset_loader}")
