(() => {
  'use strict';

  const keyMap = {
    left: { code: 'ArrowLeft', key: 'ArrowLeft', keyCode: 37 },
    right: { code: 'ArrowRight', key: 'ArrowRight', keyCode: 39 },
    jump: { code: 'Space', key: ' ', keyCode: 32 },
    attack: { code: 'KeyX', key: 'x', keyCode: 88 }
  };

  const active = new Set();

  function emit(type, binding) {
    const evt = new KeyboardEvent(type, {
      key: binding.key,
      code: binding.code,
      keyCode: binding.keyCode,
      which: binding.keyCode,
      bubbles: true,
      cancelable: true,
      repeat: false
    });
    window.dispatchEvent(evt);
  }

  function press(name) {
    const binding = keyMap[name];
    if (!binding || active.has(name)) return;
    active.add(name);
    emit('keydown', binding);
    if (navigator.vibrate) {
      try { navigator.vibrate(name === 'attack' ? 24 : 12); } catch (_) {}
    }
  }

  function release(name) {
    const binding = keyMap[name];
    if (!binding || !active.has(name)) return;
    active.delete(name);
    emit('keyup', binding);
  }

  function releaseAll() {
    [...active].forEach(release);
  }

  document.querySelectorAll('[data-hold]').forEach((btn) => {
    const name = btn.dataset.hold;
    const down = (e) => {
      e.preventDefault();
      e.stopPropagation();
      press(name);
      btn.classList.add('pressed');
    };
    const up = (e) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      release(name);
      btn.classList.remove('pressed');
    };

    btn.addEventListener('pointerdown', down, { passive: false });
    btn.addEventListener('pointerup', up, { passive: false });
    btn.addEventListener('pointercancel', up, { passive: false });
    btn.addEventListener('lostpointercapture', up, { passive: false });

    // Android/WebView fallback: some devices are more reliable with Touch Events.
    btn.addEventListener('touchstart', down, { passive: false });
    btn.addEventListener('touchend', up, { passive: false });
    btn.addEventListener('touchcancel', up, { passive: false });
  });

  document.querySelectorAll('[data-action]').forEach((btn) => {
    const name = btn.dataset.action;
    const fire = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const binding = keyMap[name];
      if (!binding) return;
      // Edge-triggered event so jump/attack always fires once per tap.
      emit('keydown', binding);
      requestAnimationFrame(() => emit('keyup', binding));
      btn.classList.add('pressed');
      setTimeout(() => btn.classList.remove('pressed'), 90);
      if (navigator.vibrate) {
        try { navigator.vibrate(name === 'attack' ? 24 : 12); } catch (_) {}
      }
    };
    btn.addEventListener('pointerdown', fire, { passive: false });
    btn.addEventListener('touchstart', fire, { passive: false });
  });

  window.addEventListener('blur', releaseAll);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) releaseAll();
  });

  // Prevent the browser from interpreting the game area as scrolling/zooming UI.
  const gameShell = document.getElementById('gameShell');
  if (gameShell) {
    gameShell.addEventListener('touchmove', (e) => e.preventDefault(), { passive: false });
  }

  console.info('[Corsair Cat] Android input compatibility layer active');
})();
