#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_android_controller_settings.py <MainActivity.java>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "Capitan Artiglio controller settings v1"
if marker in text:
    print(f"Controller settings already patched: {path}")
    raise SystemExit(0)

# This patch intentionally runs after patch_android_touch_settings.py.
anchor = "import android.widget.SeekBar;\n"
replacement = anchor + "import android.widget.ArrayAdapter;\nimport android.widget.Spinner;\nimport android.widget.Toast;\n"
if anchor not in text:
    raise RuntimeError("SeekBar import anchor missing; run touch settings patch first")
text = text.replace(anchor, replacement, 1)

anchor = '    private static final String PREF_TOUCH_INSET = "touch_inset_px";\n'
replacement = anchor + (
    '    // Capitan Artiglio controller settings v1\n'
    '    private static final String PREF_PAD_A = "pad_a_action";\n'
    '    private static final String PREF_PAD_B = "pad_b_action";\n'
    '    private static final String PREF_PAD_X = "pad_x_action";\n'
    '    private static final String PREF_PAD_Y = "pad_y_action";\n'
    '    private static final String PREF_PAD_DEADZONE = "pad_deadzone_pct";\n'
    '    private static final String PREF_PAD_SENSITIVITY = "pad_sensitivity_pct";\n'
    '    private static final String PREF_PAD_RUMBLE = "pad_rumble_pct";\n'
)
if anchor not in text:
    raise RuntimeError("touch preference anchor missing")
text = text.replace(anchor, replacement, 1)

anchor = "                applyTouchPreferencesToWeb();\n"
replacement = anchor + "                applyControllerPreferencesToWeb();\n"
if anchor not in text:
    raise RuntimeError("page-finished touch apply anchor missing")
text = text.replace(anchor, replacement, 1)

# Add controller UI after touch controls.
anchor = '''        box.addView(insetSeek);

        TextView note = text(
'''
controller_ui = '''        box.addView(insetSeek);

        TextView controllerTitle = text("Controller fisico", 15, Color.rgb(30, 30, 30));
        controllerTitle.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        controllerTitle.setPadding(0, dp(20), 0, dp(4));
        box.addView(controllerTitle);

        TextView controllerHelp = text(
                "Rimappa A/B/X/Y durante il gioco. Nei menu A resta Conferma e B resta Indietro.",
                12, Color.DKGRAY);
        controllerHelp.setPadding(0, 0, 0, dp(8));
        box.addView(controllerHelp);

        String[] controllerActions = new String[]{"Salto", "Fuoco", "Attacco", "Cambia arma"};
        ArrayAdapter<String> controllerAdapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, controllerActions);
        controllerAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);

        TextView aLabel = text("Pulsante A", 13, Color.DKGRAY);
        box.addView(aLabel);
        Spinner aSpinner = new Spinner(this);
        aSpinner.setAdapter(controllerAdapter);
        aSpinner.setSelection(clampInt(prefs.getInt(PREF_PAD_A, 0), 0, 3));
        box.addView(aSpinner);

        TextView bLabel = text("Pulsante B", 13, Color.DKGRAY);
        box.addView(bLabel);
        Spinner bSpinner = new Spinner(this);
        bSpinner.setAdapter(controllerAdapter);
        bSpinner.setSelection(clampInt(prefs.getInt(PREF_PAD_B, 1), 0, 3));
        box.addView(bSpinner);

        TextView xLabel = text("Pulsante X", 13, Color.DKGRAY);
        box.addView(xLabel);
        Spinner xSpinner = new Spinner(this);
        xSpinner.setAdapter(controllerAdapter);
        xSpinner.setSelection(clampInt(prefs.getInt(PREF_PAD_X, 2), 0, 3));
        box.addView(xSpinner);

        TextView yLabel = text("Pulsante Y", 13, Color.DKGRAY);
        box.addView(yLabel);
        Spinner ySpinner = new Spinner(this);
        ySpinner.setAdapter(controllerAdapter);
        ySpinner.setSelection(clampInt(prefs.getInt(PREF_PAD_Y, 3), 0, 3));
        box.addView(ySpinner);

        final int[] padDeadzone = {clampInt(prefs.getInt(PREF_PAD_DEADZONE, 15), 5, 35)};
        TextView deadzoneLabel = text("Deadzone stick: " + padDeadzone[0] + "%", 13, Color.DKGRAY);
        box.addView(deadzoneLabel);
        SeekBar deadzoneSeek = new SeekBar(this);
        deadzoneSeek.setMax(30);
        deadzoneSeek.setProgress(padDeadzone[0] - 5);
        deadzoneSeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            padDeadzone[0] = 5 + progress;
            deadzoneLabel.setText("Deadzone stick: " + padDeadzone[0] + "%");
        }));
        box.addView(deadzoneSeek);

        final int[] padSensitivity = {clampInt(prefs.getInt(PREF_PAD_SENSITIVITY, 100), 70, 140)};
        TextView sensitivityLabel = text("Sensibilità stick: " + padSensitivity[0] + "%", 13, Color.DKGRAY);
        box.addView(sensitivityLabel);
        SeekBar sensitivitySeek = new SeekBar(this);
        sensitivitySeek.setMax(70);
        sensitivitySeek.setProgress(padSensitivity[0] - 70);
        sensitivitySeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            padSensitivity[0] = 70 + progress;
            sensitivityLabel.setText("Sensibilità stick: " + padSensitivity[0] + "%");
        }));
        box.addView(sensitivitySeek);

        final int[] padRumble = {clampInt(prefs.getInt(PREF_PAD_RUMBLE, 100), 0, 100)};
        TextView rumbleLabel = text("Vibrazione controller: " + padRumble[0] + "%", 13, Color.DKGRAY);
        box.addView(rumbleLabel);
        SeekBar rumbleSeek = new SeekBar(this);
        rumbleSeek.setMax(100);
        rumbleSeek.setProgress(padRumble[0]);
        rumbleSeek.setOnSeekBarChangeListener(new SimpleSeekListener(progress -> {
            padRumble[0] = progress;
            rumbleLabel.setText("Vibrazione controller: " + padRumble[0] + "%");
        }));
        box.addView(rumbleSeek);

        TextView note = text(
'''
if anchor not in text:
    raise RuntimeError("touch settings UI tail anchor missing")
text = text.replace(anchor, controller_ui, 1)

# Validate A/B/X/Y as a permutation so no action becomes unreachable.
anchor = '''        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            prefs.edit()
'''
replacement = '''        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            int padA = aSpinner.getSelectedItemPosition();
            int padB = bSpinner.getSelectedItemPosition();
            int padX = xSpinner.getSelectedItemPosition();
            int padY = ySpinner.getSelectedItemPosition();
            boolean uniquePadMap = padA != padB && padA != padX && padA != padY
                    && padB != padX && padB != padY && padX != padY;
            if (!uniquePadMap) {
                Toast.makeText(this, "Assegna Salto, Fuoco, Attacco e Cambia arma una sola volta ciascuno.", Toast.LENGTH_LONG).show();
                return;
            }
            prefs.edit()
'''
if anchor not in text:
    raise RuntimeError("settings save listener anchor missing")
text = text.replace(anchor, replacement, 1)

anchor = '''                    .putInt(PREF_TOUCH_SCALE, touchScale[0])
                    .putInt(PREF_TOUCH_OPACITY, touchOpacity[0])
                    .putInt(PREF_TOUCH_INSET, touchInset[0])
                    .apply();
            applyKeepAwakePreference();
            applyTouchPreferencesToWeb();
            hapticTick();
'''
replacement = '''                    .putInt(PREF_TOUCH_SCALE, touchScale[0])
                    .putInt(PREF_TOUCH_OPACITY, touchOpacity[0])
                    .putInt(PREF_TOUCH_INSET, touchInset[0])
                    .putInt(PREF_PAD_A, padA)
                    .putInt(PREF_PAD_B, padB)
                    .putInt(PREF_PAD_X, padX)
                    .putInt(PREF_PAD_Y, padY)
                    .putInt(PREF_PAD_DEADZONE, padDeadzone[0])
                    .putInt(PREF_PAD_SENSITIVITY, padSensitivity[0])
                    .putInt(PREF_PAD_RUMBLE, padRumble[0])
                    .apply();
            applyKeepAwakePreference();
            applyTouchPreferencesToWeb();
            applyControllerPreferencesToWeb();
            hapticTick();
'''
if anchor not in text:
    raise RuntimeError("touch settings persistence anchor missing")
text = text.replace(anchor, replacement, 1)

anchor = "    private Button menuButton(String label, boolean primary) {\n"
helper = '''    private void applyControllerPreferencesToWeb() {
        if (webView == null) return;
        int padA = clampInt(prefs.getInt(PREF_PAD_A, 0), 0, 3);
        int padB = clampInt(prefs.getInt(PREF_PAD_B, 1), 0, 3);
        int padX = clampInt(prefs.getInt(PREF_PAD_X, 2), 0, 3);
        int padY = clampInt(prefs.getInt(PREF_PAD_Y, 3), 0, 3);
        int deadzonePct = clampInt(prefs.getInt(PREF_PAD_DEADZONE, 15), 5, 35);
        int sensitivityPct = clampInt(prefs.getInt(PREF_PAD_SENSITIVITY, 100), 70, 140);
        int rumblePct = clampInt(prefs.getInt(PREF_PAD_RUMBLE, 100), 0, 100);

        double deadzone = deadzonePct / 100.0;
        double sensitivity = sensitivityPct / 100.0;
        double rumble = rumblePct / 100.0;
        String js = "(function(){" +
                "var cfg={buttonMap:[" + padA + "," + padB + "," + padX + "," + padY + "]," +
                "deadzone:" + deadzone + ",sensitivity:" + sensitivity + ",hapticStrength:" + rumble + "};" +
                "if(typeof window.setCapitanControllerConfig==='function'){window.setCapitanControllerConfig(cfg);}" +
                "else{window.__pendingCapitanControllerConfig=cfg;}" +
                "})();";
        webView.evaluateJavascript(js, null);
        webView.postDelayed(() -> webView.evaluateJavascript(js, null), 650);
    }

'''
if anchor not in text:
    raise RuntimeError("controller helper insertion anchor missing")
text = text.replace(anchor, helper + anchor, 1)

path.write_text(text, encoding="utf-8")
print(f"Android controller settings patched: {path}")
