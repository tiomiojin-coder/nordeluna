import com.mkxpz.launcher.OnlineBridge;
import com.sun.net.httpserver.HttpServer;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class OnlineBridgeTest {
    static void check(boolean value, String reason) { if (!value) throw new AssertionError(reason); }
    static String read(File file) throws Exception { return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8); }
    static void write(File file, String text) throws Exception { Files.write(file.toPath(), text.getBytes(StandardCharsets.UTF_8)); }
    static String response(File dir, String id) throws Exception {
        File file = new File(dir, id + ".response");
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(12);
        while (!file.isFile()) {
            check(System.nanoTime() < deadline, "bridge response timed out");
            Thread.sleep(10);
        }
        String text = read(file);
        file.delete();
        return text;
    }
    static void submit(File dir, String id, String session, String url, String body) throws Exception {
        File temporary = new File(dir, id + ".writing");
        write(temporary, session + "\n" + url + "\n" + body);
        check(temporary.renameTo(new File(dir, id + ".request")), "atomic request publication failed");
    }
    public static void main(String[] args) throws Exception {
        File game = new File(args[0]);
        File dir = new File(game, ".nordeluna-online-bridge");
        AtomicInteger requests = new AtomicInteger(), redirects = new AtomicInteger();
        AtomicReference<String> mode = new AtomicReference<>("ok"), received = new AtomicReference<>();
        CountDownLatch slowEntered = new CountDownLatch(1);
        ExecutorService handlers = Executors.newCachedThreadPool();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.setExecutor(handlers);
        server.createContext("/api", exchange -> {
            requests.incrementAndGet();
            received.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            String selected = mode.get();
            try {
                if (selected.equals("slow")) { slowEntered.countDown(); Thread.sleep(2500); }
                if (selected.equals("redirect")) {
                    exchange.getResponseHeaders().set("Location", "/leak");
                    exchange.sendResponseHeaders(302, -1);
                } else {
                    byte[] body = (selected.equals("large") ? "x".repeat(524289) : "{\"ok\":true,\"nick\":\"Lua\"}").getBytes(StandardCharsets.UTF_8);
                    exchange.sendResponseHeaders(200, body.length);
                    exchange.getResponseBody().write(body);
                }
            } catch (Exception ignored) { } finally { exchange.close(); }
        });
        server.createContext("/leak", exchange -> { redirects.incrementAndGet(); exchange.sendResponseHeaders(200, -1); exchange.close(); });
        server.start();
        String url = "http://127.0.0.1:" + server.getAddress().getPort() + "/api";
        try (OnlineBridge bridge = new OnlineBridge(game)) {
            bridge.setResumed(true);
            String session = read(new File(dir, "session"));
            String secretBody = "{\"token\":\"PRIVATE_TOKEN_123\",\"name\":\"Lúna\"}";
            String id = "a".repeat(32);
            submit(dir, id, session, url, secretBody);
            check(response(dir, id).startsWith("200\n{\"ok\":true"), "HTTP response not returned");
            check(received.get().equals(secretBody), "Unicode/body changed in transport");
            check(!read(new File(game, "nordeluna-online-transport.log")).contains("PRIVATE_TOKEN"), "secret leaked to logs");
            int before = requests.get();
            id = "b".repeat(32);
            submit(dir, id, "old-session", url, secretBody);
            check(response(dir, id).startsWith("ERROR\n") && requests.get() == before, "request replayed across app sessions");
            id = "c".repeat(32);
            write(new File(dir, id + ".cancel"), "1");
            submit(dir, id, session, url, secretBody);
            check(response(dir, id).startsWith("ERROR\n") && requests.get() == before, "cancelled request reached server");
            mode.set("redirect");
            id = "d".repeat(32);
            submit(dir, id, session, url, secretBody);
            check(response(dir, id).startsWith("302\n") && redirects.get() == 0, "redirect leaked POST to another route");
            mode.set("large");
            id = "e".repeat(32);
            submit(dir, id, session, url, secretBody);
            check(response(dir, id).startsWith("ERROR\n"), "oversized response accepted");
            mode.set("slow");
            id = "f".repeat(32);
            submit(dir, id, session, url, secretBody);
            check(slowEntered.await(3, TimeUnit.SECONDS), "slow request did not start");
            bridge.setResumed(false);
            check(response(dir, id).startsWith("ERROR\n"), "paused app accepted success");
            bridge.setResumed(true);
            mode.set("ok");
            id = "1".repeat(32);
            submit(dir, id, session, url, secretBody);
            check(response(dir, id).startsWith("200\n"), "transport failed after pause/reconnection");
            before = requests.get();
            id = "2".repeat(32);
            submit(dir, id, session, "file:///etc/passwd", secretBody);
            check(response(dir, id).startsWith("ERROR\n") && requests.get() == before, "invalid protocol accepted");
        } finally { server.stop(0); handlers.shutdownNow(); }
        check(!new File(dir, "session").exists() && !new File(dir, "status").exists(), "bridge remained live after close");
        System.out.println("OnlineBridge real HTTP: Unicode, session isolation, cancellation, bounded responses, redirects, pause and reconnection passed.");
    }
}
