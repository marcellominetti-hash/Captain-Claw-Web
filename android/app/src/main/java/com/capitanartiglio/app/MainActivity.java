package com.capitanartiglio.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Space;
import android.widget.Switch;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 1701;
    private static final String APP_HOST = "appassets.androidplatform.net";
    private static final String GAME_URL =
            "https://appassets.androidplatform.net/assets/www/index.html?android=1";
    private static final String PREFS = "capitan_artiglio_collection";
    private static final String PREF_LAST_MODE = "last_mode";
    private static final String PREF_HAS_PLAYED = "has_played";
    private static final String PREF_HAPTICS = "haptics";
    private static final String PREF_KEEP_AWAKE = "keep_awake";
    private static final String STATE_GAME_VISIBLE = "game_visible";
    private static final String STATE_MODE = "current_mode";

    private FrameLayout root;
    private View homeView;
    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private SharedPreferences prefs;
    private boolean gameVisible = false;
    private String currentMode = "campaign";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (!prefs.contains(PREF_HAPTICS)) {
            prefs.edit().putBoolean(PREF_HAPTICS, true).apply();
        }
        if (!prefs.contains(PREF_KEEP_AWAKE)) {
            prefs.edit().putBoolean(PREF_KEEP_AWAKE, true).apply();
        }

        applyKeepAwakePreference();
        enterImmersiveMode();

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(4, 8, 14));
        setContentView(root);

        createWebView();
        homeView = createHomeView();
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        root.addView(homeView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        if (savedInstanceState != null) {
            currentMode = savedInstanceState.getString(STATE_MODE, "campaign");
            gameVisible = savedInstanceState.getBoolean(STATE_GAME_VISIBLE, false);
            webView.restoreState(savedInstanceState);
            if (gameVisible) {
                showGameSurface();
            } else {
                showHome();
            }
        } else {
            showHome();
        }
    }

    private void createWebView() {
        webView = new WebView(this);
        webView.setBackgroundColor(Color.BLACK);
        webView.setVisibility(View.GONE);
        webView.setFocusable(true);
        webView.setFocusableInTouchMode(true);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        }

        final WebViewAssetLoader assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        webView.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(
                    WebView view, WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            @SuppressWarnings("deprecation")
            public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
                return assetLoader.shouldInterceptRequest(Uri.parse(url));
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (APP_HOST.equals(uri.getHost())) {
                    return false;
                }
                openExternalUrl(uri);
                return true;
            }

            @Override
            @SuppressWarnings("deprecation")
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                Uri uri = Uri.parse(url);
                if (APP_HOST.equals(uri.getHost())) {
                    return false;
                }
                openExternalUrl(uri);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                dispatchLaunchModeToWeb();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView view,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams fileChooserParams) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;

                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                return true;
            }
        });

        webView.addJavascriptInterface(new AndroidBridge(), "CapitanAndroid");
    }

    private View createHomeView() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);

        GradientDrawable background = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{Color.rgb(5, 10, 18), Color.rgb(14, 24, 36), Color.rgb(4, 8, 14)});
        scroll.setBackground(background);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER_HORIZONTAL);
        column.setPadding(dp(28), dp(30), dp(28), dp(24));
        scroll.addView(column, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView kicker = text("CAPTAIN CLAW · ANDROID COLLECTION", 12, Color.rgb(113, 174, 218));
        kicker.setLetterSpacing(0.12f);
        kicker.setGravity(Gravity.CENTER);
        column.addView(kicker);

        addVerticalSpace(column, 10);

        TextView title = text("CAPITAN\nARTIGLIO", 34, Color.WHITE);
        title.setGravity(Gravity.CENTER);
        title.setLetterSpacing(0.04f);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        column.addView(title);

        addVerticalSpace(column, 8);

        TextView subtitle = text("COLLECTION", 15, Color.rgb(229, 177, 74));
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setLetterSpacing(0.2f);
        subtitle.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        column.addView(subtitle);

        addVerticalSpace(column, 14);

        TextView badge = text("Campagna originale  •  623 livelli extra  •  Offline", 13,
                Color.rgb(196, 208, 220));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(16), dp(9), dp(16), dp(9));
        GradientDrawable badgeBg = rounded(Color.argb(92, 29, 49, 66), 18, Color.argb(90, 102, 151, 183));
        badge.setBackground(badgeBg);
        column.addView(badge, wrapContentParams());

        addVerticalSpace(column, 26);

        Button continueButton = menuButton("▶   CONTINUA", true);
        continueButton.setEnabled(prefs.getBoolean(PREF_HAS_PLAYED, false));
        continueButton.setAlpha(continueButton.isEnabled() ? 1f : 0.45f);
        continueButton.setOnClickListener(v -> {
            hapticTick();
            launchGame(prefs.getString(PREF_LAST_MODE, "campaign"));
        });
        column.addView(continueButton, fullButtonParams());

        addVerticalSpace(column, 10);

        Button campaignButton = menuButton("⚔   CAMPAGNA ORIGINALE", false);
        campaignButton.setOnClickListener(v -> {
            hapticTick();
            launchGame("campaign");
        });
        column.addView(campaignButton, fullButtonParams());

        addVerticalSpace(column, 10);

        Button customButton = menuButton("☠   623 LIVELLI EXTRA", false);
        customButton.setOnClickListener(v -> {
            hapticTick();
            launchGame("custom");
        });
        column.addView(customButton, fullButtonParams());

        addVerticalSpace(column, 10);

        Button favoritesButton = menuButton("★   PREFERITI", false);
        favoritesButton.setOnClickListener(v -> {
            hapticTick();
            launchGame("favorites");
        });
        column.addView(favoritesButton, fullButtonParams());

        addVerticalSpace(column, 10);

        Button settingsButton = menuButton("⚙   IMPOSTAZIONI", false);
        settingsButton.setOnClickListener(v -> {
            hapticTick();
            showSettingsDialog();
        });
        column.addView(settingsButton, fullButtonParams());

        addVerticalSpace(column, 22);

        TextView footer = text("Collection v2 · wrapper Android nativo · motore OpenClaw", 11,
                Color.rgb(112, 128, 143));
        footer.setGravity(Gravity.CENTER);
        column.addView(footer);

        return scroll;
    }

    private void launchGame(String mode) {
        currentMode = mode == null ? "campaign" : mode;
        prefs.edit()
                .putBoolean(PREF_HAS_PLAYED, true)
                .putString(PREF_LAST_MODE, currentMode)
                .apply();

        showGameSurface();
        String target = GAME_URL + "&mode=" + Uri.encode(currentMode) + "&shell=v2";
        webView.loadUrl(target);
        webView.requestFocus();
    }

    private void showGameSurface() {
        gameVisible = true;
        homeView.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        enterImmersiveMode();
        webView.postDelayed(() -> webView.requestFocus(), 120);
    }

    private void showHome() {
        gameVisible = false;
        if (webView != null) {
            webView.onPause();
            webView.setVisibility(View.GONE);
        }
        if (homeView != null) {
            homeView.setVisibility(View.VISIBLE);
            homeView.bringToFront();
        }
        enterImmersiveMode();
    }

    private void dispatchLaunchModeToWeb() {
        if (webView == null) return;
        String mode = currentMode.replace("\\", "").replace("'", "");
        String js = "(function(){" +
                "var mode='" + mode + "';" +
                "try{window.dispatchEvent(new CustomEvent('capitan-artiglio-launch',{detail:{mode:mode}}));}catch(e){}" +
                "try{if(window.CapitanArtiglio&&typeof window.CapitanArtiglio.openSection==='function'){window.CapitanArtiglio.openSection(mode);}}catch(e){}" +
                "})();";
        webView.evaluateJavascript(js, null);
    }

    private void showSettingsDialog() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(24), dp(10), dp(24), dp(4));

        Switch haptics = new Switch(this);
        haptics.setText("Vibrazione interfaccia");
        haptics.setTextSize(16);
        haptics.setChecked(prefs.getBoolean(PREF_HAPTICS, true));
        box.addView(haptics);

        Switch keepAwake = new Switch(this);
        keepAwake.setText("Schermo sempre acceso durante il gioco");
        keepAwake.setTextSize(16);
        keepAwake.setChecked(prefs.getBoolean(PREF_KEEP_AWAKE, true));
        box.addView(keepAwake);

        TextView note = text(
                "Fullscreen immersivo e orientamento orizzontale sono sempre attivi. " +
                        "Le prossime versioni aggiungeranno dimensione/posizione dei controlli touch e mapping controller.",
                12, Color.DKGRAY);
        note.setPadding(0, dp(14), 0, 0);
        box.addView(note);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Impostazioni")
                .setView(box)
                .setNegativeButton("Annulla", null)
                .setPositiveButton("Salva", null)
                .create();

        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            prefs.edit()
                    .putBoolean(PREF_HAPTICS, haptics.isChecked())
                    .putBoolean(PREF_KEEP_AWAKE, keepAwake.isChecked())
                    .apply();
            applyKeepAwakePreference();
            hapticTick();
            dialog.dismiss();
        }));
        dialog.show();
    }

    private Button menuButton(String label, boolean primary) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(15);
        button.setTextColor(primary ? Color.rgb(5, 12, 18) : Color.WHITE);
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER_VERTICAL | Gravity.CENTER_HORIZONTAL);
        button.setPadding(dp(18), 0, dp(18), 0);
        button.setMinHeight(dp(54));

        int fill = primary ? Color.rgb(229, 177, 74) : Color.argb(205, 24, 39, 54);
        int stroke = primary ? Color.rgb(246, 205, 111) : Color.argb(150, 83, 126, 156);
        button.setBackground(rounded(fill, 14, stroke));
        return button;
    }

    private TextView text(String value, int sp, int color) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        return text;
    }

    private GradientDrawable rounded(int fillColor, int radiusDp, int strokeColor) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), strokeColor);
        return drawable;
    }

    private LinearLayout.LayoutParams fullButtonParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                Math.min(dp(520), getResources().getDisplayMetrics().widthPixels - dp(56)),
                dp(56));
        params.gravity = Gravity.CENTER_HORIZONTAL;
        return params;
    }

    private LinearLayout.LayoutParams wrapContentParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.gravity = Gravity.CENTER_HORIZONTAL;
        return params;
    }

    private void addVerticalSpace(LinearLayout parent, int heightDp) {
        Space space = new Space(this);
        parent.addView(space, new LinearLayout.LayoutParams(1, dp(heightDp)));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void applyKeepAwakePreference() {
        if (prefs.getBoolean(PREF_KEEP_AWAKE, true)) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
    }

    private void hapticTick() {
        if (!prefs.getBoolean(PREF_HAPTICS, true)) return;
        Vibrator vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        if (vibrator == null || !vibrator.hasVibrator()) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(18, 70));
        } else {
            vibrator.vibrate(18);
        }
    }

    private void openExternalUrl(Uri uri) {
        if (uri == null) return;
        String scheme = uri.getScheme();
        if (!"https".equalsIgnoreCase(scheme) && !"http".equalsIgnoreCase(scheme)) return;
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) return;

        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            try {
                getContentResolver().takePersistableUriPermission(
                        uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) {
            }
            result = new Uri[]{uri};
        }

        filePathCallback.onReceiveValue(result);
        filePathCallback = null;
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (gameVisible && webView != null) webView.onResume();
        enterImmersiveMode();
    }

    @Override
    protected void onPause() {
        if (webView != null) webView.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.removeJavascriptInterface("CapitanAndroid");
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        outState.putBoolean(STATE_GAME_VISIBLE, gameVisible);
        outState.putString(STATE_MODE, currentMode);
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (gameVisible) {
            showHome();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) enterImmersiveMode();
    }

    private void enterImmersiveMode() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }

    public class AndroidBridge {
        @JavascriptInterface
        public void goHome() {
            runOnUiThread(() -> showHome());
        }

        @JavascriptInterface
        public void saveMode(String mode) {
            if (mode == null || mode.trim().isEmpty()) return;
            prefs.edit()
                    .putBoolean(PREF_HAS_PLAYED, true)
                    .putString(PREF_LAST_MODE, mode)
                    .apply();
        }

        @JavascriptInterface
        public String getLastMode() {
            return prefs.getString(PREF_LAST_MODE, "campaign");
        }

        @JavascriptInterface
        public void vibrate(int milliseconds) {
            if (!prefs.getBoolean(PREF_HAPTICS, true)) return;
            int safeMs = Math.max(1, Math.min(milliseconds, 120));
            runOnUiThread(() -> {
                Vibrator vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (vibrator == null || !vibrator.hasVibrator()) return;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(VibrationEffect.createOneShot(safeMs, 80));
                } else {
                    vibrator.vibrate(safeMs);
                }
            });
        }
    }
}
