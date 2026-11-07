package com.mkxpz.launcher;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.*;

/** Bounded HTTP outside the Ruby VM. Mailboxes contain data, never executable code. */
public final class OnlineBridge implements AutoCloseable {
    private static final int MAX_REQUEST = 262144, MAX_RESPONSE = 524288;
    private static final long DEADLINE_MS = 10000;
    private final File directory, log;
    private final Object markerLock = new Object();
    private final String session = UUID.randomUUID().toString();
    private final ScheduledExecutorService scanner = Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private volatile boolean resumed, closed;
    private volatile Job active;
    private long heartbeat, lastCleanup;

    private static final class Job {
        final String id;
        final long started = System.nanoTime();
        volatile HttpURLConnection connection;
        volatile boolean cancelled;
        Job(String id) { this.id = id; }
    }

    public OnlineBridge(File game) throws IOException {
        directory = new File(game, ".nordeluna-online-bridge");
        if (!directory.getCanonicalFile().getParentFile().equals(game.getCanonicalFile()))
            throw new IOException("Invalid bridge directory");
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Bridge directory unavailable");
        log = new File(game, "nordeluna-online-transport.log");
        File[] old = directory.listFiles();
        if (old != null) for (File file : old) if (owned(file)) file.delete();
        write(new File(directory, "session"), session);
        scanner.scheduleWithFixedDelay(this::tick, 0, 50, TimeUnit.MILLISECONDS);
    }

    private boolean owned(File file) {
        return file.isFile() && (file.getName().matches("[0-9a-f]{32}\\.(request|response|cancel|writing)") ||
            file.getName().equals("session") || file.getName().equals("status"));
    }

    public void setResumed(boolean value) {
        resumed = value;
        heartbeat = 0;
        Job job = active;
        if (!value && job != null) job.cancelled = true;
    }

    private void cancel(Job job) {
        if (job == null) return;
        job.cancelled = true;
        HttpURLConnection connection = job.connection;
        if (connection != null) connection.disconnect();
    }

    private void tick() {
        if (closed) return;
        try {
            long now = System.currentTimeMillis();
            if (now - heartbeat >= 1000) {
                synchronized (markerLock) {
                    if (closed) return;
                    write(new File(directory, "status"), resumed ? "1" : "0");
                }
                heartbeat = now;
            }
            Job job = active;
            if (job != null) {
                if (job.cancelled || !resumed || new File(directory, job.id + ".cancel").exists() ||
                        TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - job.started) >= DEADLINE_MS) cancel(job);
                return;
            }
            File[] files = directory.listFiles();
            if (files == null) return;
            if (now - lastCleanup > 30000) {
                for (File file : files) if (owned(file) && file.getName().matches("[0-9a-f]{32}\\..+") && now - file.lastModified() > 30000) file.delete();
                lastCleanup = now;
            }
            // Exactly one job may enter the executor. No unbounded request queue.
            for (File file : files) {
                if (!file.getName().matches("[0-9a-f]{32}\\.request")) continue;
                Job next = new Job(file.getName().substring(0, 32));
                active = next;
                network.execute(() -> execute(next, file));
                break;
            }
        } catch (Exception error) {
            diagnostic("bridge-error " + error.getClass().getSimpleName());
        }
    }

    private void execute(Job job, File file) {
        String result;
        try {
            if (!resumed || job.cancelled || new File(directory, job.id + ".cancel").exists())
                throw new IOException("App pausado ou pedido cancelado.");
            String request = new String(readLimited(new FileInputStream(file), MAX_REQUEST + 1024), StandardCharsets.UTF_8);
            int first = request.indexOf('\n'), second = request.indexOf('\n', first + 1);
            if (first < 0 || second < 0 || !request.substring(0, first).equals(session))
                throw new IOException("Sessao do aplicativo mudou. Reabra o online.");
            URI uri = new URI(request.substring(first + 1, second));
            if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme())) || uri.getHost() == null ||
                    uri.getUserInfo() != null || uri.getFragment() != null || uri.getQuery() != null ||
                    !uri.getPath().endsWith("/api")) throw new IOException("Endereco de servidor invalido.");
            byte[] body = request.substring(second + 1).getBytes(StandardCharsets.UTF_8);
            if (body.length > MAX_REQUEST) throw new IOException("Pedido muito grande.");
            HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
            job.connection = connection;
            connection.setConnectTimeout(4000);
            connection.setReadTimeout(5000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("User-Agent", "Nordeluna-Android/OnlineBridge-1");
            connection.setFixedLengthStreamingMode(body.length);
            if (job.cancelled) throw new IOException("Pedido cancelado.");
            try (OutputStream out = connection.getOutputStream()) { out.write(body); }
            int status = connection.getResponseCode();
            InputStream input = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            byte[] response = input == null ? new byte[0] : readLimited(input, MAX_RESPONSE);
            if (job.cancelled || !resumed) throw new IOException("Conexao interrompida ao pausar o aplicativo.");
            result = status + "\n" + new String(response, StandardCharsets.UTF_8);
            diagnostic("http=" + status + " ms=" + TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - job.started));
        } catch (Exception error) {
            // Never log URL, body, room token or Pokemon data.
            diagnostic("network-error " + error.getClass().getSimpleName());
            result = "ERROR\nConexao interrompida ou servidor sem resposta. Verifique a internet e tente novamente.";
        } finally {
            if (job.connection != null) job.connection.disconnect();
            file.delete();
        }
        try {
            if (!closed) {
                File temporary = new File(directory, job.id + ".writing");
                write(temporary, result);
                if (!temporary.renameTo(new File(directory, job.id + ".response"))) temporary.delete();
            }
        } catch (IOException error) { diagnostic("response-write-error"); }
        finally {
            new File(directory, job.id + ".cancel").delete();
            active = null;
        }
    }

    private static byte[] readLimited(InputStream input, int limit) throws IOException {
        try (InputStream stream = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = stream.read(buffer)) != -1) {
                if (output.size() + count > limit) throw new IOException("Response limit");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private static void write(File file, String value) throws IOException {
        try (FileOutputStream output = new FileOutputStream(file)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
        }
    }

    private synchronized void diagnostic(String value) {
        try {
            if (log.length() > 128 * 1024) try (FileOutputStream clear = new FileOutputStream(log)) { }
            try (FileOutputStream output = new FileOutputStream(log, true)) {
                output.write((System.currentTimeMillis() + " " + value + "\n").getBytes(StandardCharsets.UTF_8));
            }
        } catch (IOException ignored) { }
    }

    @Override public void close() {
        closed = true;
        resumed = false;
        cancel(active);
        scanner.shutdownNow();
        network.shutdownNow();
        synchronized (markerLock) {
            new File(directory, "status").delete();
            new File(directory, "session").delete();
        }
    }
}
