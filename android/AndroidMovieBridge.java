package com.mkxpz.launcher;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.SurfaceTexture;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;
import java.io.File;
import java.io.IOException;

/** MP4 decoding on Android's media stack, with a modal surface above touch controls. */
public final class AndroidMovieBridge implements AutoCloseable {
    private final Activity activity;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final MovieMailbox mailbox;
    private Dialog dialog;
    private TextureView video;
    private TextView hint, loading;
    private MediaPlayer player;
    private Surface surface;
    private MovieMailbox.Request request;
    private MovieMailbox.Completion completion;
    private boolean resumed, focusPaused, muted, prepared, closed;
    private long openedAt, heldAt, lastSample, hintUntil;
    private long lastProgressAt;
    private int lastPosition = -1;
    private int heldKey;
    private boolean touchHeld;

    private final Runnable pump = new Runnable() {
        @Override public void run() {
            if (closed) return;
            mailbox.tick();
            updatePlayer();
            handler.postDelayed(this, 50);
        }
    };

    public AndroidMovieBridge(Activity activity, File game) throws IOException {
        this.activity = activity;
        mailbox = new MovieMailbox(game, new MovieMailbox.Player() {
            @Override public void start(MovieMailbox.Request movie, MovieMailbox.Completion done) throws Exception {
                open(movie, done);
            }
            @Override public void setResumed(boolean value) { resumed = value; updatePlaybackState(); }
            @Override public void cancel() { finish(null); }
        });
        handler.post(pump);
    }

    public void setResumed(boolean value) { mailbox.setResumed(value); }
    public void setAudioFocusPaused(boolean value) { focusPaused = value; updatePlaybackState(); }
    public void setMuted(boolean value) { muted = value; updatePlayer(); }
    private boolean canPlay() { return resumed && !focusPaused && surface != null; }

    private void open(MovieMailbox.Request movie, MovieMailbox.Completion done) throws Exception {
        if (dialog != null || activity.isFinishing()) throw new IOException("Player de video indisponivel.");
        request = movie; completion = done;
        openedAt = hintUntil = SystemClock.uptimeMillis();
        lastProgressAt = openedAt; lastPosition = -1;
        hintUntil += 3000;
        resetHold();
        try {
            dialog = new Dialog(activity, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
            dialog.setCancelable(false);
            dialog.setCanceledOnTouchOutside(false);
            FrameLayout root = new FrameLayout(activity);
            root.setBackgroundColor(Color.BLACK);
            video = new TextureView(activity);
            root.addView(video, new FrameLayout.LayoutParams(-1, -1));
            loading = new TextView(activity);
            loading.setText("Carregando video..."); loading.setTextColor(Color.WHITE);
            loading.setGravity(Gravity.CENTER);
            root.addView(loading, new FrameLayout.LayoutParams(-1, -1));
            hint = new TextView(activity);
            hint.setTextColor(Color.WHITE); hint.setTextSize(14);
            hint.setGravity(Gravity.CENTER);
            hint.setBackgroundColor(0xCC142423);
            hint.setContentDescription("Segure para pular o video");
            FrameLayout.LayoutParams hintLayout = new FrameLayout.LayoutParams(-2, dp(48), Gravity.BOTTOM | Gravity.RIGHT);
            hintLayout.setMargins(dp(16), dp(16), dp(24), dp(24));
            hint.setPadding(dp(16), 0, dp(16), 0);
            root.addView(hint, hintLayout);
            hint.setVisibility(movie.skippable ? View.VISIBLE : View.GONE);
            root.setOnTouchListener((view, event) -> {
                hintUntil = SystemClock.uptimeMillis() + 3000;
                return true;
            });
            hint.setOnTouchListener((view, event) -> {
                if (request == null || !request.skippable) return true;
                int action = event.getActionMasked();
                if (action == MotionEvent.ACTION_DOWN) {
                    resetHold(); touchHeld = true; heldAt = SystemClock.uptimeMillis();
                } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL ||
                        action == MotionEvent.ACTION_POINTER_DOWN) resetHold();
                else if (action == MotionEvent.ACTION_MOVE && (event.getX() < 0 || event.getY() < 0 ||
                        event.getX() >= view.getWidth() || event.getY() >= view.getHeight())) resetHold();
                hintUntil = SystemClock.uptimeMillis() + 3000;
                return true;
            });
            dialog.setOnKeyListener((window, code, event) -> {
                if (request == null) return false;
                boolean skipKey = code == KeyEvent.KEYCODE_BACK || code == KeyEvent.KEYCODE_ESCAPE ||
                    code == KeyEvent.KEYCODE_ENTER || code == KeyEvent.KEYCODE_DPAD_CENTER ||
                    code == KeyEvent.KEYCODE_SPACE || code == KeyEvent.KEYCODE_BUTTON_A || code == KeyEvent.KEYCODE_BUTTON_B;
                if (!skipKey) return false; // Volume/media keys keep their system behavior.
                if (!request.skippable) return true;
                if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0 && heldKey == 0) {
                    resetHold(); heldKey = code; heldAt = SystemClock.uptimeMillis();
                } else if (event.getAction() == KeyEvent.ACTION_UP && heldKey == code) resetHold();
                hintUntil = SystemClock.uptimeMillis() + 3000;
                return true;
            });
            dialog.setOnDismissListener(window -> { if (completion != null) finish("ERROR\nVideo interrompido."); });
            dialog.setContentView(root);
            dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED);
            video.setSurfaceTextureListener(new TextureView.SurfaceTextureListener() {
                @Override public void onSurfaceTextureAvailable(SurfaceTexture texture, int width, int height) {
                    if (dialog == null || completion == null) return;
                    surface = new Surface(texture);
                    if (player == null) prepare();
                    else {
                        try {
                            player.setSurface(surface);
                            fitVideo(); updatePlaybackState();
                        } catch (IllegalStateException error) { finish("ERROR\nA superficie do video foi interrompida."); }
                    }
                }
                @Override public void onSurfaceTextureSizeChanged(SurfaceTexture texture, int width, int height) { fitVideo(); }
                @Override public void onSurfaceTextureUpdated(SurfaceTexture texture) { }
                @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture texture) {
                    if (player != null) {
                        try {
                            if (prepared && player.isPlaying()) player.pause();
                            player.setSurface(null);
                        } catch (IllegalStateException ignored) { }
                    }
                    if (surface != null) surface.release();
                    surface = null; resetHold();
                    return true;
                }
            });
            dialog.show();
            // Hide navigation/status bars while retaining Android's edge gesture.
            dialog.getWindow().getDecorView().setSystemUiVisibility(0x1706);
        } catch (Exception error) { finish(null); throw error; }
    }

    @SuppressWarnings("deprecation")
    private void prepare() {
        try {
            final MediaPlayer current = new MediaPlayer();
            player = current;
            // Do not request audio focus: honor the port's Spotify/mixing option.
            current.setAudioStreamType(AudioManager.STREAM_MUSIC);
            current.setVolume(0, 0);
            current.setSurface(surface);
            current.setDataSource(request.file.getAbsolutePath());
            current.setOnPreparedListener(media -> {
                if (player != media) return;
                prepared = true;
                fitVideo();
                loading.setVisibility(View.GONE);
                updatePlaybackState();
            });
            current.setOnVideoSizeChangedListener((media, width, height) -> { if (player == media) fitVideo(); });
            current.setOnCompletionListener(media -> { if (player == media) finish("OK\ncompleted"); });
            current.setOnErrorListener((media, what, extra) -> {
                if (player == media) finish("ERROR\nO Android nao conseguiu abrir este MP4 (" + what + "/" + extra + "). Use video H.264 e audio AAC.");
                return true;
            });
            current.prepareAsync();
        } catch (Exception error) { finish("ERROR\nNao foi possivel abrir o video no Android."); }
    }

    private void fitVideo() {
        if (player == null || !prepared || video == null) return;
        int vw = video.getWidth(), vh = video.getHeight(), mw = player.getVideoWidth(), mh = player.getVideoHeight();
        if (vw <= 0 || vh <= 0 || mw <= 0 || mh <= 0) return;
        float scale = Math.min((float) vw / mw, (float) vh / mh);
        Matrix transform = new Matrix();
        transform.setScale(mw * scale / vw, mh * scale / vh, vw / 2f, vh / 2f);
        video.setTransform(transform);
    }
    private void resetHold() { heldAt = 0; heldKey = 0; touchHeld = false; lastSample = SystemClock.uptimeMillis(); }
    private void updatePlaybackState() {
        resetHold();
        lastProgressAt = SystemClock.uptimeMillis();
        if (!prepared) openedAt = SystemClock.uptimeMillis();
        if (player == null || !prepared) return;
        try {
            if (canPlay()) { updatePlayer(); if (player != null && !player.isPlaying()) player.start(); }
            else if (player.isPlaying()) player.pause();
        } catch (IllegalStateException error) { finish("ERROR\nO player de video foi interrompido."); }
    }
    private void updatePlayer() {
        long now = SystemClock.uptimeMillis();
        if (!prepared) {
            if (dialog != null && resumed && now - openedAt > 30000) finish("ERROR\nO video demorou demais para abrir.");
            return;
        }
        if (player == null) return;
        try {
            if (!canPlay()) { resetHold(); lastProgressAt = now; return; }
            if (now - lastSample > 500) resetHold();
            lastSample = now;
            double progress = (touchHeld || heldKey != 0) ? Math.min(1, (now - heldAt) / (request.holdSeconds * 1000)) : 0;
            if (request.skippable) {
                hint.setVisibility(now < hintUntil || progress > 0 ? View.VISIBLE : View.INVISIBLE);
                hint.setText(progress > 0 ? "Segure para pular  " + (int)(progress * 100) + "%" : "Segure para pular");
                if (progress >= 1) { finish("OK\nskipped"); return; }
            }
            int position = player.getCurrentPosition();
            if (position != lastPosition) { lastPosition = position; lastProgressAt = now; }
            else if (player.isPlaying() && now - lastProgressAt > 15000) {
                finish("ERROR\nO video parou de avancar. Tente novamente."); return;
            }
            double seconds = position / 1000.0;
            double duration = request.duration > 0 ? request.duration : player.getDuration() / 1000.0;
            double entrance = duration > 0 ? Math.min(request.entrance, duration / 2) : request.entrance;
            double exit = duration > 0 ? Math.min(request.exit, duration / 2) : request.exit;
            double alpha = entrance > 0 ? Math.min(1, seconds / entrance) : 1;
            if (duration > 0 && exit > 0) alpha = Math.min(alpha, Math.max(0, (duration - seconds) / exit));
            video.setAlpha((float) alpha);
            float gain = muted ? 0 : (float)(request.volume / 100.0 * alpha);
            player.setVolume(gain, gain);
        } catch (IllegalStateException error) { finish("ERROR\nA reproducao do video foi interrompida."); }
    }
    private int dp(int value) { return Math.round(value * activity.getResources().getDisplayMetrics().density); }
    private void finish(String result) {
        MovieMailbox.Completion done = completion;
        completion = null;
        MediaPlayer old = player;
        player = null; prepared = false;
        if (old != null) { old.setOnCompletionListener(null); old.setOnErrorListener(null); old.release(); }
        Dialog oldDialog = dialog;
        dialog = null;
        if (oldDialog != null) oldDialog.dismiss();
        if (surface != null) surface.release();
        surface = null; video = null; hint = loading = null; request = null;
        resetHold();
        if (done != null && result != null) done.finish(result);
    }
    @Override public void close() {
        if (closed) return;
        closed = true;
        handler.removeCallbacks(pump);
        mailbox.close();
    }
}
