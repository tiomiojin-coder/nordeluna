using System;
using System.IO;
using System.Net;
using System.Text;
using System.Diagnostics;
using System.Threading;
using System.Text.RegularExpressions;

// Built as a Windows GUI executable: no console and no Ruby/native HTTP calls.
internal static class WindowsHttpBridge {
    static string folder, session, log;
    static Process parent;
    static volatile bool running = true;
    static volatile HttpWebRequest active;
    static string activeId;
    static long started;
    static readonly object gate = new object();
    static readonly Stopwatch uptime = Stopwatch.StartNew();
    static readonly Encoding utf8 = new UTF8Encoding(false);
    static bool ParentAlive() { try { return !parent.HasExited; } catch { return false; } }
    static void Marker(string name, string value) {
        string temporary = Path.Combine(folder, name + ".writing"), target = Path.Combine(folder, name);
        File.WriteAllText(temporary, value, utf8);
        if (File.Exists(target)) File.Replace(temporary, target, null);
        else File.Move(temporary, target);
    }
    static void Diagnostic(string value) {
        try {
            if (File.Exists(log) && new FileInfo(log).Length > 131072) File.WriteAllText(log, "", utf8);
            File.AppendAllText(log, DateTime.UtcNow.ToString("o") + " " + value + "\n", utf8);
        } catch { }
    }
    static void Watch(object ignored) {
        try {
            if (!ParentAlive()) running = false;
            lock (gate) {
                if (!running) { if (active != null) active.Abort(); return; }
                Marker("status", "1");
                if (active != null && (uptime.ElapsedMilliseconds - started > 10000 ||
                        File.Exists(Path.Combine(folder, activeId + ".cancel")))) active.Abort();
            }
        } catch { }
    }
    static byte[] ReadLimited(Stream stream, int limit) {
        using (stream) using (MemoryStream result = new MemoryStream()) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = stream.Read(buffer, 0, buffer.Length)) > 0) {
                if (result.Length + count > limit) throw new IOException("Response limit");
                result.Write(buffer, 0, count);
            }
            return result.ToArray();
        }
    }
    static void Execute(string file) {
        string id = Path.GetFileNameWithoutExtension(file), response, stage = "read-request";
        try {
            if (new FileInfo(file).Length > 263168 || File.Exists(Path.Combine(folder, id + ".cancel"))) throw new IOException("Cancelled/large request");
            string request = File.ReadAllText(file, utf8);
            stage = "validate-session";
            int a = request.IndexOf('\n'), b = request.IndexOf('\n', a + 1);
            if (a < 0 || b < 0 || request.Substring(0, a) != session) throw new IOException("Stale session");
            Uri uri = new Uri(request.Substring(a + 1, b - a - 1));
            stage = "validate-url";
            if ((uri.Scheme != "https" && uri.Scheme != "http") || uri.UserInfo.Length != 0 ||
                    uri.Fragment.Length != 0 || uri.Query.Length != 0 || !uri.AbsolutePath.EndsWith("/api")) throw new IOException("Invalid URL");
            byte[] body = utf8.GetBytes(request.Substring(b + 1));
            if (body.Length > 262144) throw new IOException("Request limit");
            HttpWebRequest http = (HttpWebRequest)WebRequest.Create(uri);
            stage = "send";
            http.Method = "POST"; http.AllowAutoRedirect = false; http.Timeout = 5000; http.ReadWriteTimeout = 5000;
            http.ContentType = "application/json; charset=utf-8"; http.Accept = "application/json";
            http.UserAgent = "Nordeluna-Windows/OnlineBridge-1"; http.ContentLength = body.Length;
            lock (gate) { active = http; activeId = id; started = uptime.ElapsedMilliseconds; }
            using (Stream output = http.GetRequestStream()) output.Write(body, 0, body.Length);
            stage = "receive";
            HttpWebResponse result;
            try { result = (HttpWebResponse)http.GetResponse(); }
            catch (WebException error) { result = error.Response as HttpWebResponse; if (result == null) throw; }
            using (result) {
                string text = utf8.GetString(ReadLimited(result.GetResponseStream(), 524288));
                response = ((int)result.StatusCode) + "\n" + text;
                Diagnostic("http=" + ((int)result.StatusCode) + " ms=" + (uptime.ElapsedMilliseconds - started));
            }
        } catch (Exception error) {
            Diagnostic("network-error " + error.GetType().Name + " stage=" + stage + " code=" + error.HResult);
            response = "ERROR\nConexao interrompida ou servidor sem resposta. Verifique a internet e tente novamente.";
        } finally {
            lock (gate) { if (active != null) active.Abort(); active = null; }
            try { File.Delete(file); } catch { }
        }
        try {
            if (running) { File.WriteAllText(Path.Combine(folder, id + ".writing"), response, utf8); File.Move(Path.Combine(folder, id + ".writing"), Path.Combine(folder, id + ".response")); }
            File.Delete(Path.Combine(folder, id + ".cancel"));
        } catch { }
    }
    [STAThread] static void Main(string[] args) {
        if (args.Length != 2) return;
        try {
            string game = Path.GetFullPath(args[0]);
            parent = Process.GetProcessById(Int32.Parse(args[1]));
            if (parent.Handle == IntPtr.Zero) return;
            folder = Path.Combine(game, ".nordeluna-online-bridge-windows-" + args[1]);
            Directory.CreateDirectory(folder);
            log = Path.Combine(game, "nordeluna-online-transport.log");
            foreach (string old in Directory.GetFiles(folder)) {
                if (Regex.IsMatch(Path.GetFileName(old), @"^(?:[0-9a-f]{32}\.(?:request|response|cancel|writing)|session|status)(?:\.writing)?$")) File.Delete(old);
            }
            session = Guid.NewGuid().ToString();
            Marker("session", session); Marker("status", "1");
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            using (Timer watch = new Timer(Watch, null, 0, 200)) {
                while (running && ParentAlive()) {
                    foreach (string file in Directory.GetFiles(folder, "*.request")) {
                        if (Regex.IsMatch(Path.GetFileName(file), @"^[0-9a-f]{32}\.request$")) Execute(file);
                        if (!running) break;
                    }
                    foreach (string old in Directory.GetFiles(folder)) {
                        if (Regex.IsMatch(Path.GetFileName(old), @"^[0-9a-f]{32}\.(request|response|cancel|writing)$") &&
                                DateTime.UtcNow - File.GetLastWriteTimeUtc(old) > TimeSpan.FromSeconds(30)) File.Delete(old);
                    }
                    Thread.Sleep(50);
                }
            }
        } catch (Exception error) { if (log != null) Diagnostic("broker-error " + error.GetType().Name); }
        finally {
            try { if (parent != null && parent.HasExited) Diagnostic("game-exit-code=" + parent.ExitCode); } catch { }
            try { File.Delete(Path.Combine(folder, "status")); File.Delete(Path.Combine(folder, "session")); } catch { }
        }
    }
}
