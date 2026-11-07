import json
import os
from pathlib import Path
import socketserver
import http.server
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"


@unittest.skipUnless(os.name == "nt" and CSC.is_file(), "Windows .NET Framework required")
class WindowsBridgeTests(unittest.TestCase):
    def test_real_http_six_pokemon_unicode_cancellation_and_parent_exit(self):
        received = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps(dict(ok=True, species="NOCTGEIST", nick="Lúna"), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        with tempfile.TemporaryDirectory(prefix="nordeluna-win-http-") as temporary:
            directory = Path(temporary)
            exe = directory / "WindowsHttpBridge.exe"
            subprocess.run([str(CSC), "/nologo", "/target:winexe", "/optimize+", "/out:" + str(exe),
                            str(ROOT / "game-plugins/Nordeluna Online/bridge/WindowsHttpBridge.cs")], check=True, timeout=20)
            # Explicitly ensure a GUI-subsystem helper: no console window for players.
            import struct
            image = exe.read_bytes()
            pe = struct.unpack_from("<I", image, 0x3c)[0]
            self.assertEqual(struct.unpack_from("<H", image, pe + 24 + 68)[0], 2)
            server = Server(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"], creationflags=subprocess.CREATE_NO_WINDOW)
            helper = subprocess.Popen([str(exe), str(directory), str(parent.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
            mailbox = directory / (".nordeluna-online-bridge-windows-v2-" + str(parent.pid))
            def wait_file(path):
                deadline = time.monotonic() + 8
                while not path.is_file():
                    if helper.poll() is not None or time.monotonic() > deadline:
                        self.fail("Windows broker failed: " + str(helper.poll()))
                    time.sleep(0.02)
                return path.read_text(encoding="utf-8")
            try:
                session = wait_file(mailbox / "session")
                self.assertEqual(wait_file(mailbox / "status"), "1")
                status_stamp = (mailbox / "status").stat().st_mtime_ns
                url = f"http://127.0.0.1:{server.server_port}/api"
                def request(number, ticket_session=session, cancel=False):
                    name = format(number, "032x")
                    data = dict(action="create", profile=dict(name="Lúna"), payload=[dict(species="NOCTGEIST")] * 6)
                    if cancel: (mailbox / (name + ".cancel")).write_text("1")
                    staged = mailbox / (name + ".writing")
                    staged.write_bytes((ticket_session + "\n" + url + "\n" + json.dumps(data, ensure_ascii=False)).encode("utf-8"))
                    staged.rename(mailbox / (name + ".request"))
                    result = wait_file(mailbox / (name + ".response"))
                    (mailbox / (name + ".response")).unlink()
                    return result
                for number in range(1, 16):
                    result = request(number)
                    self.assertTrue(result.startswith("200\n"), result + "\n" + (directory / "nordeluna-online-transport.log").read_text())
                self.assertEqual(len(received), 15)
                self.assertEqual((mailbox / "status").stat().st_mtime_ns, status_stamp,
                                 "broker rewrote its status while Ruby may be reading it")
                self.assertTrue(all(len(row["payload"]) == 6 and row["profile"]["name"] == "Lúna" for row in received))
                self.assertTrue(request(20, ticket_session="old").startswith("ERROR\n"))
                self.assertTrue(request(21, cancel=True).startswith("ERROR\n"))
                self.assertEqual(len(received), 15)
                parent.terminate()
                parent.wait(timeout=5)
                helper.wait(timeout=6)
                self.assertFalse((mailbox / "session").exists())
                self.assertIn("game-exit-code=", (directory / "nordeluna-online-transport.log").read_text())
            finally:
                if parent.poll() is None: parent.terminate()
                parent.wait(timeout=5)
                if helper.poll() is None: helper.terminate()
                helper.wait(timeout=5)
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
