package com.mkxpz.launcher;

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Process;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Keeps diagnostics locally. Nothing is uploaded without an explicit export. */
public final class CrashDiagnostics {
    private static final AtomicBoolean INSTALLED = new AtomicBoolean();
    private static final String PREFS = "nordeluna_crash_diagnostics";
    private static final long TRACE_LIMIT = 2L * 1024 * 1024;

    private CrashDiagnostics() { }

    private static File directory(Context context) {
        File directory = new File(context.getFilesDir(), "crash-diagnostics");
        if (!directory.isDirectory()) directory.mkdirs();
        return directory;
    }

    public static void install(Context context, Runnable finished) {
        if (!INSTALLED.compareAndSet(false, true)) {
            finished.run();
            return;
        }
        Context app = context.getApplicationContext();
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, failure) -> {
            try {
                File report = new File(directory(app), "java-" + System.currentTimeMillis() + ".txt");
                try (PrintWriter writer = new PrintWriter(new FileOutputStream(report))) {
                    writer.println("Thread: " + thread.getName());
                    writer.println("Android: " + Build.VERSION.RELEASE + " / " + Build.MODEL);
                    failure.printStackTrace(writer);
                }
                app.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                    .putBoolean("unseen", true).commit();
            } catch (Throwable ignored) { }
            if (previous != null) previous.uncaughtException(thread, failure);
            else {
                Process.killProcess(Process.myPid());
                System.exit(10);
            }
        });
        new Thread(() -> {
            try {
                capturePreviousExit(app);
                prune(app);
            } catch (Exception ignored) { }
            finished.run();
        }, "Nordeluna previous-crash capture").start();
    }

    private static void capturePreviousExit(Context context) throws Exception {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;
        ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        if (manager == null) return;
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long seen = preferences.getLong("latest_exit", 0);
        long latest = seen;
        boolean found = false;
        List<ApplicationExitInfo> exits = manager.getHistoricalProcessExitReasons(null, 0, 5);
        for (ApplicationExitInfo exit : exits) {
            if (exit.getTimestamp() <= seen) continue;
            latest = Math.max(latest, exit.getTimestamp());
            int reason = exit.getReason();
            if (reason != ApplicationExitInfo.REASON_CRASH &&
                reason != ApplicationExitInfo.REASON_CRASH_NATIVE &&
                reason != ApplicationExitInfo.REASON_ANR &&
                reason != ApplicationExitInfo.REASON_LOW_MEMORY) continue;
            String name = "exit-" + exit.getTimestamp() + "-" + exit.getPid();
            String summary = "Timestamp: " + exit.getTimestamp() + "\n" +
                "PID: " + exit.getPid() + "\n" +
                "Reason: " + reason + "\n" +
                "Status/signal: " + exit.getStatus() + "\n" +
                "Description: " + exit.getDescription() + "\n" +
                "PSS KiB: " + exit.getPss() + "\nRSS KiB: " + exit.getRss() + "\n" +
                "Android: " + Build.VERSION.RELEASE + " / " + Build.MODEL + "\n";
            try (FileOutputStream output = new FileOutputStream(new File(directory(context), name + ".txt"))) {
                output.write(summary.getBytes(StandardCharsets.UTF_8));
            }
            found = true;
            try (InputStream trace = exit.getTraceInputStream()) {
                if (trace != null) {
                    // Android 12+ native traces are protobuf, not plain text.
                    String extension = reason == ApplicationExitInfo.REASON_CRASH_NATIVE ? ".pb" : "-trace.txt";
                    try (FileOutputStream output = new FileOutputStream(new File(directory(context), name + extension))) {
                        byte[] buffer = new byte[8192];
                        long count = 0;
                        int read;
                        while (count < TRACE_LIMIT && (read = trace.read(buffer, 0,
                                (int) Math.min(buffer.length, TRACE_LIMIT - count))) != -1) {
                            output.write(buffer, 0, read);
                            count += read;
                        }
                    }
                }
            } catch (Exception ignored) {
                // A summary remains useful when the OS no longer has a trace.
            }
        }
        SharedPreferences.Editor editor = preferences.edit().putLong("latest_exit", latest);
        if (found) editor.putBoolean("unseen", true);
        editor.apply();
    }

    private static void prune(Context context) {
        File[] files = directory(context).listFiles(File::isFile);
        if (files == null) return;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        // A bounded local history, never game data or saves.
        for (int i = 10; i < files.length; i++) files[i].delete();
    }

    public static boolean hasUnseenReport(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("unseen", false);
    }

    public static void acknowledge(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("unseen", false).apply();
    }

    public static void addToZip(Context context, ZipOutputStream zip) throws java.io.IOException {
        File[] files = directory(context).listFiles(File::isFile);
        if (files == null) return;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        for (int i = 0; i < Math.min(10, files.length); i++) {
            File file = files[i];
            zip.putNextEntry(new ZipEntry("crashes/" + file.getName()));
            try (InputStream input = new java.io.FileInputStream(file)) {
                byte[] buffer = new byte[8192];
                long count = 0;
                int read;
                while (count < TRACE_LIMIT && (read = input.read(buffer, 0,
                        (int) Math.min(buffer.length, TRACE_LIMIT - count))) != -1) {
                    zip.write(buffer, 0, read);
                    count += read;
                }
            }
            zip.closeEntry();
        }
    }
}
