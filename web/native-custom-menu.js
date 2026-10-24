(() => {
  'use strict';

  let manifestPromise = null;

  function getManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch('custom-levels/manifest.json', { cache: 'no-store' })
        .then(r => {
          if (!r.ok) throw new Error('Custom level manifest HTTP ' + r.status);
          return r.json();
        })
        .then(data => {
          if (!data || !Array.isArray(data.levels) || data.levels.length !== 623) {
            throw new Error('Invalid custom level manifest');
          }
          return data;
        });
    }
    return manifestPromise;
  }

  async function launch(index) {
    try {
      const data = await getManifest();
      const level = data.levels[index];
      if (!level) throw new Error('Custom level index out of range: ' + index);

      const token = ['custom', level.id, String(level.baseLevel), level.archive].join('|');
      try {
        if (window.CapitanAndroid && typeof window.CapitanAndroid.saveMode === 'function') {
          window.CapitanAndroid.saveMode(token);
        }
      } catch (_) {}

      const url = new URL('index.html', location.href);
      url.searchParams.set('android', '1');
      url.searchParams.set('build', 'native-menu-v1');
      url.searchParams.set('mode', 'custom');
      url.searchParams.set('level', level.id);
      url.searchParams.set('base', String(level.baseLevel));
      url.searchParams.set('archive', level.archive);
      location.replace(url.href);
    } catch (err) {
      console.error('[CapitanCustomMenu] unable to launch level', index, err);
      if (typeof window.showCustomLevelError === 'function') {
        window.showCustomLevelError(err && err.message ? err.message : String(err));
      }
    }
  }

  window.CapitanCustomMenu = { launch, getManifest };
})();
