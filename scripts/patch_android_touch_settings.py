#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_android_touch_settings.py <MainActivity.java>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "Capitan Artiglio touch settings v1"
if marker in text:
    print(f"Touch settings already patched: {path}")
    raise SystemExit(0)

# Imports.
anchor = "import android.widget.LinearLayout;\nimport android.widget.ScrollView;\n"
replacement = "import android.widget.LinearLayout;\nimport android.widget.ScrollView;\nimport android.widget.SeekBar;\n"
if anchor not in text:
    raise RuntimeError("widget import anchor missing")
text = text.replace(anchor, replacement, 1)

# Preferences.
anchor = '    private static final String PREF_KEEP_AWAKE = "keep_awake";\n'
replacement = anchor + (
    '    // Capitan Artiglio touch settings v1\n'
    '    private static final String PREF_TOUCH_SCALE = "touch_scale_pct";\n'
    '    private static final String PREF_TOUCH_OPACITY = "touch_opacity_pct";\n'
    '    private static final String PREF_TOUCH_INSET = "touch_inset_px";\n'
)
if anchor not in text:
    raise RuntimeError("preference anchor missing")
text = text.replace(anchor, replacement, 1)

# Apply the preferences after every web page load. Inline style values override
# touch-controls.js defaults without changing the engine input mapping.
anchor = "                dispatchLaunchModeToWeb();\n"
replacement = anchor + "                applyTouchPreferencesToWeb();\n"
if anchor not in text:
    raise RuntimeError("onPageFinished anchor missing")
text = text.replace(anchor, replacement, 1)

# Insert UI controls into the native settings dialog after Keep Awake.
anchor = '''        keepAwake.setChecked(prefs.getBoolean(PREF_KEEP_AWAKE, true));
        box.addView(keepAwake);

        TextView note = text(
                "Fullscreen immersivo e orientamento orizzontale sono sempre attivi. " +
                        "Le prossime versioni aggiungeranno dimensione/posizione dei controlli touch e mapping controller.",
                12, Color.DKGRAY);
'''
replacement = '''        keepAwake.setChecked(prefs.getBoolean(PREF_KEEP_AWAKE, true));
        box.addView(keepAwake);

        TextView touchTitle = text("Controlli touch", 15, Color.rgb(30, 30, 30));
        touchTitle.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        touchTitle.setPadding(0, dp(18), 0, dp(4));
        box.addView(touchTitle);

        final int[] touchScale = {clampInt(prefs.getInt(PREF_TOUCH_SCALE, 100), 70, 130)};
        final int[] touchOpacity = {clampInt(prefs.getInt(PREF_TOUCH_OPACITY, 72), 40, 100)};
        final int[] touchInset = {clampInt(prefs.getInt(PREF_TOUCH_INSET, 40), 20, 80)};

        TextView scaleLabel = text("Dimensione: " + touchScale[0] + "%", 13, Color.DKGRAY);
        box.addView(scaleLabel);
        SeekBar scaleSeek = new SeekBar(this);
        scaleSeek.setMax(60);
        scaleSeek.setProgress(touchScale[0] - 70);
        scaleSeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            touchScale[0] = 70 + progress;
            scaleLabel.setText("Dimensione: " + touchScale[0] + "%");
        }));
        box.addView(scaleSeek);

        TextView opacityLabel = text("Opacità: " + touchOpacity[0] + "%", 13, Color.DKGRAY);
        box.addView(opacityLabel);
        SeekBar opacitySeek = new SeekBar(this);
        opacitySeek.setMax(60);
        opacitySeek.setProgress(touchOpacity[0] - 40);
        opacitySeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            touchOpacity[0] = 40 + progress;
            opacityLabel.setText("Opacità: " + touchOpacity[0] + "%");
        }));
        box.addView(opacitySeek);

        TextView insetLabel = text("Distanza dai bordi: " + touchInset[0] + " px", 13, Color.DKGRAY);
        box.addView(insetLabel);
        SeekBar insetSeek = new SeekBar(this);
        insetSeek.setMax(60);
        insetSeek.setProgress(touchInset[0] - 20);
        insetSeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            touchInset[0] = 20 + progress;
            insetLabel.setText("Distanza dai bordi: " + touchInset[0] + " px");
        }));
        box.addView(insetSeek);

        TextView note = text(
                "Fullscreen immersivo e orientamento orizzontale sono sempre attivi. " +
                        "Le regolazioni touch vengono applicate a joystick e pulsanti senza cambiare i comandi del motore.",
                12, Color.DKGRAY);
'''
if anchor not in text:
    raise RuntimeError("settings UI anchor missing")
text = text.replace(anchor, replacement, 1)

# Persist settings and apply immediately to a currently loaded game.
anchor = '''            prefs.edit()
                    .putBoolean(PREF_HAPTICS, haptics.isChecked())
                    .putBoolean(PREF_KEEP_AWAKE, keepAwake.isChecked())
                    .apply();
            applyKeepAwakePreference();
            hapticTick();
'''
replacement = '''            prefs.edit()
                    .putBoolean(PREF_HAPTICS, haptics.isChecked())
                    .putBoolean(PREF_KEEP_AWAKE, keepAwake.isChecked())
                    .putInt(PREF_TOUCH_SCALE, touchScale[0])
                    .putInt(PREF_TOUCH_OPACITY, touchOpacity[0])
                    .putInt(PREF_TOUCH_INSET, touchInset[0])
                    .apply();
            applyKeepAwakePreference();
            applyTouchPreferencesToWeb();
            hapticTick();
'''
if anchor not in text:
    raise RuntimeError("settings save anchor missing")
text = text.replace(anchor, replacement, 1)

# Helpers go before menuButton so they stay private implementation details.
anchor = "    private Button menuButton(String label, boolean primary) {\n"
helpers = '''    private interface SeekProgressCallback {
        void onProgress(int progress);
    }

    private static class SimpleSeekListener implements SeekBar.OnSeekBarChangeListener {
        private final SeekProgressCallback callback;

        SimpleSeekListener(SeekProgressCallback callback) {
            this.callback = callback;
        }

        @Override
        public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
            callback.onProgress(progress);
        }

        @Override
        public void onStartTrackingTouch(SeekBar seekBar) {
        }

        @Override
        public void onStopTrackingTouch(SeekBar seekBar) {
        }
    }

    private int clampInt(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private void applyTouchPreferencesToWeb() {
        if (webView == null) return;
        int scalePct = clampInt(prefs.getInt(PREF_TOUCH_SCALE, 100), 70, 130);
        int opacityPct = clampInt(prefs.getInt(PREF_TOUCH_OPACITY, 72), 40, 100);
        int insetPx = clampInt(prefs.getInt(PREF_TOUCH_INSET, 40), 20, 80);

        double scaleMultiplier = scalePct / 100.0;
        double opacity = opacityPct / 100.0;
        String js = "(function(){" +
                "var minDim=Math.min(window.innerWidth||0,window.innerHeight||0);" +
                "var auto=Math.max(0.72,Math.min(2,((minDim-320)/1600)+0.72));" +
                "var scale=Math.max(0.5,Math.min(2.4,auto*" + scaleMultiplier + "));" +
                "var root=document.documentElement;" +
                "if(root){root.style.setProperty('--tc-scale',String(scale));" +
                "root.style.setProperty('--tc-corner-dist','calc(" + insetPx + "px * var(--tc-scale))');}" +
                "var controls=document.getElementById('touchControls');" +
                "if(controls){controls.style.opacity='" + opacity + "';}" +
                "window.__capitanTouchPrefs={scalePct:" + scalePct + ",opacityPct:" + opacityPct + ",insetPx:" + insetPx + "};" +
                "})();";
        webView.evaluateJavascript(js, null);
        webView.postDelayed(() -> webView.evaluateJavascript(js, null), 450);
    }

'''
if anchor not in text:
    raise RuntimeError("helper insertion anchor missing")
text = text.replace(anchor, helpers + anchor, 1)

path.write_text(text, encoding="utf-8")
print(f"Android touch settings patched: {path}")
