package com.flowcast.officialprobe;

import android.os.Bundle;
import android.text.format.DateFormat;
import android.widget.Button;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.mediarouter.app.MediaRouteButton;

import com.google.android.gms.cast.MediaInfo;
import com.google.android.gms.cast.MediaLoadRequestData;
import com.google.android.gms.cast.MediaMetadata;
import com.google.android.gms.cast.framework.CastButtonFactory;
import com.google.android.gms.cast.framework.CastContext;
import com.google.android.gms.cast.framework.CastSession;
import com.google.android.gms.cast.framework.SessionManager;
import com.google.android.gms.cast.framework.SessionManagerListener;
import com.google.android.gms.cast.framework.media.RemoteMediaClient;

import java.util.Date;

public class MainActivity extends AppCompatActivity {

    private static final String TEST_MP4 =
            "https://storage.googleapis.com/cpe-sample-media/content/big_buck_bunny/prog/big_buck_bunny_prog.mp4";
    private static final String TEST_HLS =
            "https://storage.googleapis.com/cpe-sample-media/content/big_buck_bunny/big_buck_bunny_m4s_master.m3u8";

    private TextView statusText;
    private TextView logText;
    private CastContext castContext;
    private SessionManager sessionManager;
    private CastSession castSession;

    private final SessionManagerListener<CastSession> sessionListener =
            new SessionManagerListener<CastSession>() {
                @Override
                public void onSessionStarting(CastSession session) {
                    log("SESSION: starting");
                }

                @Override
                public void onSessionStarted(CastSession session, String sessionId) {
                    castSession = session;
                    setStatus("Connected: " + safeDeviceName(session));
                    log("SESSION: started • " + safeDeviceName(session));
                }

                @Override
                public void onSessionStartFailed(CastSession session, int error) {
                    castSession = null;
                    setStatus("Cast session failed (" + error + ")");
                    log("SESSION START FAILED: status=" + error);
                }

                @Override
                public void onSessionEnding(CastSession session) {
                    log("SESSION: ending");
                }

                @Override
                public void onSessionEnded(CastSession session, int error) {
                    castSession = null;
                    setStatus("No Cast session");
                    log("SESSION: ended • status=" + error);
                }

                @Override
                public void onSessionResuming(CastSession session, String sessionId) {
                    log("SESSION: resuming");
                }

                @Override
                public void onSessionResumed(CastSession session, boolean wasSuspended) {
                    castSession = session;
                    setStatus("Reconnected: " + safeDeviceName(session));
                    log("SESSION: resumed • suspended=" + wasSuspended);
                }

                @Override
                public void onSessionResumeFailed(CastSession session, int error) {
                    castSession = null;
                    setStatus("Cast resume failed (" + error + ")");
                    log("SESSION RESUME FAILED: status=" + error);
                }

                @Override
                public void onSessionSuspended(CastSession session, int reason) {
                    castSession = session;
                    setStatus("Cast session suspended");
                    log("SESSION: suspended • reason=" + reason);
                }
            };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        statusText = findViewById(R.id.statusText);
        logText = findViewById(R.id.logText);
        Button mp4Button = findViewById(R.id.mp4Button);
        Button hlsButton = findViewById(R.id.hlsButton);
        MediaRouteButton castButton = findViewById(R.id.castButton);

        log("Native Google Cast probe starting");
        log("Sender SDK: play-services-cast-framework 23.0.0");
        log("Receiver: Google Default Media Receiver");
        log("Mi Box remains completely stock");

        try {
            castContext = CastContext.getSharedInstance(this);
            sessionManager = castContext.getSessionManager();
            CastButtonFactory.setUpMediaRouteButton(getApplicationContext(), castButton);
            castSession = sessionManager.getCurrentCastSession();
            if (castSession != null && castSession.isConnected()) {
                setStatus("Connected: " + safeDeviceName(castSession));
            } else {
                setStatus("Tap the Cast icon and choose Mi Box");
            }
            log("CastContext initialized. Discovery is now managed by Google CAF/MediaRouter.");
        } catch (Exception e) {
            setStatus("Cast SDK init error");
            log("INIT ERROR: " + e);
        }

        mp4Button.setOnClickListener(v -> loadMedia(TEST_MP4, "video/mp4", "Official Cast MP4 test"));
        hlsButton.setOnClickListener(v -> loadMedia(TEST_HLS, "application/x-mpegURL", "Official Cast HLS test"));
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (sessionManager != null) {
            sessionManager.addSessionManagerListener(sessionListener, CastSession.class);
            CastSession current = sessionManager.getCurrentCastSession();
            if (current != null && current.isConnected()) {
                castSession = current;
                setStatus("Connected: " + safeDeviceName(current));
            }
        }
    }

    @Override
    protected void onPause() {
        if (sessionManager != null) {
            sessionManager.removeSessionManagerListener(sessionListener, CastSession.class);
        }
        super.onPause();
    }

    private void loadMedia(String url, String contentType, String title) {
        CastSession session = castSession;
        if (session == null && sessionManager != null) {
            session = sessionManager.getCurrentCastSession();
            castSession = session;
        }

        if (session == null || !session.isConnected()) {
            setStatus("Not connected — tap the Cast icon first");
            log("LOAD ABORTED: no connected CastSession");
            return;
        }

        final CastSession activeSession = session;
        RemoteMediaClient client = activeSession.getRemoteMediaClient();
        if (client == null) {
            log("LOAD ABORTED: RemoteMediaClient unavailable");
            return;
        }

        MediaMetadata metadata = new MediaMetadata(MediaMetadata.MEDIA_TYPE_MOVIE);
        metadata.putString(MediaMetadata.KEY_TITLE, title);

        MediaInfo mediaInfo = new MediaInfo.Builder(url)
                .setStreamType(MediaInfo.STREAM_TYPE_BUFFERED)
                .setContentType(contentType)
                .setMetadata(metadata)
                .build();

        MediaLoadRequestData request = new MediaLoadRequestData.Builder()
                .setMediaInfo(mediaInfo)
                .setAutoplay(true)
                .build();

        log("LOAD → " + title + " • " + contentType);
        setStatus("Sending media to " + safeDeviceName(activeSession));

        client.load(request).setResultCallback(result -> {
            int code = result.getStatus().getStatusCode();
            boolean ok = result.getStatus().isSuccess();
            log("LOAD RESULT: success=" + ok + " • status=" + code);
            if (ok) {
                setStatus("Playing on " + safeDeviceName(activeSession));
            } else {
                setStatus("Media load failed • status " + code);
            }
        });
    }

    private String safeDeviceName(CastSession session) {
        try {
            if (session != null && session.getCastDevice() != null && session.getCastDevice().getFriendlyName() != null) {
                return session.getCastDevice().getFriendlyName();
            }
        } catch (Exception ignored) {
        }
        return "Cast device";
    }

    private void setStatus(String text) {
        runOnUiThread(() -> statusText.setText(text));
    }

    private void log(String message) {
        String time = DateFormat.format("HH:mm:ss", new Date()).toString();
        runOnUiThread(() -> {
            CharSequence old = logText.getText();
            String next = old.length() == 0
                    ? time + "  " + message
                    : old + "\n" + time + "  " + message;
            logText.setText(next);
        });
    }
}
