#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_gamepad_controller_config.py <gamepad-bridge.js>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "Capitan Artiglio controller config v1"
if marker in text:
    print(f"Controller bridge already patched: {path}")
    raise SystemExit(0)

anchor = "let hapticEnabled = true;\n"
block = r'''let hapticEnabled = true;

// Capitan Artiglio controller config v1.
// Physical A/B/X/Y can be remapped to the logical OpenClaw button indices
// (0=Jump, 1=Fire, 2=Attack, 3=ChangeAmmo) before events reach C++.
let capitanControllerConfig = {
    buttonMap: [0, 1, 2, 3],
    deadzone: 0.15,
    sensitivity: 1.0,
    hapticStrength: 1.0,
};

function capitanClamp(value, min, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) return min;
    return Math.max(min, Math.min(max, n));
}

function sanitizeButtonMap(value) {
    if (!Array.isArray(value) || value.length !== 4) return [0, 1, 2, 3];
    const result = value.map(v => Math.trunc(Number(v)));
    const valid = result.every(v => v >= 0 && v <= 3) && new Set(result).size === 4;
    return valid ? result : [0, 1, 2, 3];
}

function setCapitanControllerConfig(next) {
    next = next || {};
    capitanControllerConfig = {
        buttonMap: sanitizeButtonMap(next.buttonMap || capitanControllerConfig.buttonMap),
        deadzone: capitanClamp(next.deadzone ?? capitanControllerConfig.deadzone, 0.05, 0.35),
        sensitivity: capitanClamp(next.sensitivity ?? capitanControllerConfig.sensitivity, 0.70, 1.40),
        hapticStrength: capitanClamp(next.hapticStrength ?? capitanControllerConfig.hapticStrength, 0, 1),
    };
    window.__capitanControllerConfig = Object.assign({}, capitanControllerConfig, {
        buttonMap: capitanControllerConfig.buttonMap.slice(),
    });
    log('Controller config updated: ' + JSON.stringify(window.__capitanControllerConfig));
}

function remapGameButton(buttonIndex) {
    if (buttonIndex >= 0 && buttonIndex <= 3) {
        return capitanControllerConfig.buttonMap[buttonIndex];
    }
    return buttonIndex;
}

function shapeGameAxis(rawValue) {
    const raw = capitanClamp(rawValue, -1, 1);
    const abs = Math.abs(raw);
    const deadzone = capitanControllerConfig.deadzone;
    if (abs <= deadzone) return 0;
    const normalized = (abs - deadzone) / (1 - deadzone);
    const scaled = Math.min(1, normalized * capitanControllerConfig.sensitivity);
    return raw < 0 ? -scaled : scaled;
}

window.setCapitanControllerConfig = setCapitanControllerConfig;
window.getCapitanControllerConfig = function () {
    return Object.assign({}, capitanControllerConfig, {buttonMap: capitanControllerConfig.buttonMap.slice()});
};
if (window.__pendingCapitanControllerConfig) {
    setCapitanControllerConfig(window.__pendingCapitanControllerConfig);
    delete window.__pendingCapitanControllerConfig;
}
'''
if anchor not in text:
    raise RuntimeError("haptic config anchor missing")
text = text.replace(anchor, block, 1)

# Scale only controller motors. Touch vibration continues to use its original
# duration, while a 0% controller strength cleanly disables gamepad rumble.
anchor = "            weakMagnitude: Math.min(1, Math.max(0, weakMagnitude)),\n            strongMagnitude: Math.min(1, Math.max(0, strongMagnitude))\n"
replacement = "            weakMagnitude: Math.min(1, Math.max(0, weakMagnitude * capitanControllerConfig.hapticStrength)),\n            strongMagnitude: Math.min(1, Math.max(0, strongMagnitude * capitanControllerConfig.hapticStrength))\n"
if anchor not in text:
    raise RuntimeError("vibrationActuator anchor missing")
text = text.replace(anchor, replacement, 1)

anchor = "        const intensity = Math.max(weakMagnitude, strongMagnitude);\n"
replacement = "        const intensity = Math.max(weakMagnitude, strongMagnitude) * capitanControllerConfig.hapticStrength;\n"
if anchor not in text:
    raise RuntimeError("hapticActuators anchor missing")
text = text.replace(anchor, replacement, 1)

# Remap only gameplay buttons. Menu A/B semantics stay standard so navigation
# is never made inaccessible by a custom gameplay layout.
anchor = '''                } else if (cppReady) {
                    // In-game mode: send to C++
                    try {
                        if (pressed) {
                            Module._OnJSGamepadButtonDown(i, b, gp.buttons[b].value);
                        } else {
                            Module._OnJSGamepadButtonUp(i, b);
                        }
                    } catch (e) { log('C++ call error: ' + e); }
                }
'''
replacement = '''                } else if (cppReady) {
                    // In-game mode: remap A/B/X/Y, then send to C++.
                    const mappedButton = remapGameButton(b);
                    try {
                        if (pressed) {
                            Module._OnJSGamepadButtonDown(i, mappedButton, gp.buttons[b].value);
                        } else {
                            Module._OnJSGamepadButtonUp(i, mappedButton);
                        }
                    } catch (e) { log('C++ call error: ' + e); }
                }
'''
if anchor not in text:
    raise RuntimeError("gameplay button anchor missing")
text = text.replace(anchor, replacement, 1)

# Keep the menu stick behavior unchanged; apply deadzone/sensitivity only while
# gameplay is active.
anchor = '''        for (let a = 0; a < Math.min(gp.axes.length, 4); a++) {
            let value = gp.axes[a];
            if (Math.abs(value) < 0.15) value = 0;

            const prevValue = prev.axes[a] || 0;
'''
replacement = '''        for (let a = 0; a < Math.min(gp.axes.length, 4); a++) {
            const rawValue = gp.axes[a];
            let value = inMenu ? rawValue : shapeGameAxis(rawValue);
            if (inMenu && Math.abs(value) < 0.15) value = 0;

            const prevValue = prev.axes[a] || 0;
'''
if anchor not in text:
    raise RuntimeError("axis anchor missing")
text = text.replace(anchor, replacement, 1)

path.write_text(text, encoding="utf-8")
print(f"Controller bridge patched: {path}")
