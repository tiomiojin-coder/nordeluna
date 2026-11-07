package com.mkxpz.launcher;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;

/** Single-flight local movie protocol. Invoked on the UI thread, never decodes media. */
public final class MovieMailbox implements AutoCloseable {
    public interface Completion { void finish(String result); }
    public interface Player {
        void start(Request request, Completion completion) throws Exception;
        void setResumed(boolean resumed);
        void cancel();
    }
    public static final class Request {
        public final File file;
        public final int volume;
        public final boolean skippable;
        public final double holdSeconds, entrance, exit, duration;

        private Request(File game, String body, String session) throws IOException {
            String[] values = body.split("\n", -1);
            if (values.length != 8 || !session.equals(values[0])) throw new IOException("Sessao de video invalida.");
            String path = values[1];
            if (path.contains("\r") || path.indexOf('\0') >= 0 || path.contains("\\") ||
                    !(path.startsWith("Movies/") || path.startsWith("Plugins/Nordeluna Video/movies/")) ||
                    !path.toLowerCase(Locale.ROOT).endsWith(".mp4")) throw new IOException("Caminho de video invalido.");
            File root = new File(game, path.startsWith("Movies/") ? "Movies" : "Plugins/Nordeluna Video/movies").getCanonicalFile();
            file = new File(game, path).getCanonicalFile();
            if (!root.getPath().startsWith(game.getPath() + File.separator) ||
                    !file.getPath().startsWith(root.getPath() + File.separator) || !file.isFile())
                throw new IOException("Video nao encontrado na pasta Movies.");
            try {
                volume = Integer.parseInt(values[2]);
                if (volume < 0 || volume > 100 || !(values[3].equals("0") || values[3].equals("1")))
                    throw new NumberFormatException();
                skippable = values[3].equals("1");
                holdSeconds = number(values[4]); entrance = number(values[5]);
                exit = number(values[6]); duration = number(values[7]);
                if (holdSeconds <= 0) throw new NumberFormatException();
            } catch (NumberFormatException error) { throw new IOException("Opcoes de video invalidas."); }
        }
        private static double number(String value) {
            double number = Double.parseDouble(value);
            if (Double.isNaN(number) || Double.isInfinite(number) || number < 0 || number > 86400) throw new NumberFormatException();
            return number;
        }
    }

    private final File game, directory;
    private final Player player;
    private final String session = UUID.randomUUID().toString();
    private String active;
    private boolean resumed, closed;
    private long sequence, lastHeartbeat;

    public MovieMailbox(File game, Player player) throws IOException {
        this.game = game.getCanonicalFile(); this.player = player;
        directory = new File(this.game, ".nordeluna-movie-bridge");
        if (!directory.getCanonicalFile().getParentFile().equals(this.game) ||
                (!directory.isDirectory() && !directory.mkdirs())) throw new IOException("Movie bridge directory unavailable");
        File[] old = directory.listFiles();
        if (old != null) for (File file : old) if (owned(file)) file.delete();
        write("session", session);
        heartbeat();
    }

    private static boolean owned(File file) {
        return file.isFile() && (file.getName().matches("[0-9a-f]{32}\\.(request|response|cancel|writing)") ||
                file.getName().equals("session") || file.getName().equals("status"));
    }
    private void write(String name, String body) throws IOException {
        File target = new File(directory, name), temporary = new File(directory, name + ".tmp");
        try (FileOutputStream output = new FileOutputStream(temporary)) { output.write(body.getBytes(StandardCharsets.UTF_8)); }
        if (!temporary.renameTo(target)) {
            // Windows test runner cannot replace an existing destination.
            if (target.exists() && !target.delete()) throw new IOException("Movie mailbox target unavailable");
            if (!temporary.renameTo(target)) throw new IOException("Movie mailbox write failed");
        }
    }
    private static String read(File file) throws IOException {
        if (file.length() > 8192) throw new IOException("Pedido de video grande demais.");
        try (InputStream input = new FileInputStream(file); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] bytes = new byte[1024]; int count;
            while ((count = input.read(bytes)) != -1) {
                if (output.size() + count > 8192) throw new IOException("Pedido de video grande demais.");
                output.write(bytes, 0, count);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        }
    }
    private void heartbeat() throws IOException {
        write("status", (resumed ? "1\n" : "0\n") + (++sequence));
        lastHeartbeat = System.nanoTime();
    }
    public void setResumed(boolean value) {
        if (closed) return;
        resumed = value;
        player.setResumed(value);
        try { heartbeat(); } catch (IOException ignored) { }
    }
    public void tick() {
        if (closed) return;
        try {
            if (System.nanoTime() - lastHeartbeat > 1000000000L) heartbeat();
            if (active != null) {
                if (new File(directory, active + ".cancel").exists()) {
                    String id = active;
                    player.cancel();
                    finish(id, "ERROR\nVideo interrompido.");
                }
                return;
            }
            if (!resumed) return;
            File[] files = directory.listFiles();
            if (files == null) return;
            for (File file : files) {
                if (owned(file) && file.getName().matches("[0-9a-f]{32}\\.(cancel|response)") &&
                        System.currentTimeMillis() - file.lastModified() > 60000) file.delete();
                if (!file.getName().matches("[0-9a-f]{32}\\.request")) continue;
                String id = file.getName().substring(0, 32);
                active = id;
                try {
                    if (new File(directory, id + ".cancel").exists()) throw new IOException("Video cancelado.");
                    Request request = new Request(game, read(file), session);
                    file.delete();
                    player.start(request, result -> finish(id, result));
                } catch (Exception error) { finish(id, "ERROR\n" + error.getMessage()); }
                return;
            }
        } catch (IOException ignored) { /* Ruby's heartbeat timeout reports a stalled bridge. */ }
    }
    private void finish(String id, String result) {
        if (!id.equals(active)) return; // Ignore a late completion from an older player.
        active = null;
        new File(directory, id + ".request").delete();
        new File(directory, id + ".cancel").delete();
        try { write(id + ".response", result); } catch (IOException ignored) { }
    }
    @Override public void close() {
        if (closed) return;
        setResumed(false);
        player.cancel();
        if (active != null) finish(active, "ERROR\nPlayer de video encerrado.");
        closed = true;
    }
}
