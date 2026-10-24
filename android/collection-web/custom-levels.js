(() => {
  'use strict';

  const params = new URLSearchParams(location.search);
  const mode = params.get('mode') || 'campaign';
  const levelId = params.get('level') || '';
  const baseLevel = Number(params.get('base') || 0);
  const archive = params.get('archive') || '';

  // Native Android home opens index.html with a mode.  If the user asked for
  // the custom library (or favorites) and did not choose a level yet, route to
  // the lightweight library page before the WASM runtime starts.
  if (!levelId && (mode === 'custom' || mode === 'favorites')) {
    const filter = mode === 'favorites' ? 'favorites' : 'all';
    location.replace('levels.html?filter=' + encodeURIComponent(filter));
    return;
  }

  function isSafeArchive(path) {
    return /^custom-levels\/packs\/[A-Za-z0-9._-]+\.zip$/.test(String(path || ''));
  }

  const selected = mode === 'custom' &&
    !!levelId && baseLevel >= 1 && baseLevel <= 14 && isSafeArchive(archive);

  window.ClawCustomLevels = {
    isSelected: () => selected,
    selectedId: () => levelId,
    baseLevel: () => baseLevel,

    mountSelected: function () {
      if (!selected) return true;
      if (typeof FS === 'undefined') {
        console.error('[custom-levels] Emscripten FS is not available in preRun');
        return false;
      }

      try {
        try { FS.unlink('/CUSTOM_LEVEL.ZIP'); } catch (_) {}
        try { FS.unlink('/CUSTOM_LEVEL.NUM'); } catch (_) {}

        FS.writeFile('/CUSTOM_LEVEL.NUM', String(baseLevel));

        const url = new URL(archive, location.href).href;
        console.info('[custom-levels] preloading', levelId, 'base', baseLevel, url);

        // createPreloadedFile adds an Emscripten run dependency, so the engine
        // waits for this ZIP even though the asset is loaded asynchronously.
        FS.createPreloadedFile(
          '/',
          'CUSTOM_LEVEL.ZIP',
          url,
          true,
          false,
          function () {
            console.info('[custom-levels] CUSTOM_LEVEL.ZIP ready for', levelId);
          },
          function (err) {
            console.error('[custom-levels] failed to preload selected level', err);
          }
        );

        try {
          if (window.CapitanAndroid && typeof window.CapitanAndroid.saveMode === 'function') {
            window.CapitanAndroid.saveMode('custom');
          }
        } catch (_) {}

        return true;
      } catch (err) {
        console.error('[custom-levels] mountSelected failed', err);
        return false;
      }
    }
  };
})();
