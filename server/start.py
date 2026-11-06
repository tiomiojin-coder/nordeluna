"""Run the same relay locally or on a host with a persistent disk."""
import os
import socket
import sys
from pathlib import Path

import relay


def main():
    root = Path(__file__).resolve().parents[1]
    database = Path(os.environ.get("DB_PATH", str(root / ".cache/nordeluna-online-server/relay.sqlite3"))).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    print("Nordeluna Online — mantenha esta janela aberta durante as partidas.", flush=True)
    print("Banco persistente:", database, flush=True)
    if host == "0.0.0.0":
        try:
            addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
            for address in addresses:
                if not address.startswith("127."):
                    print(f"No celular, no mesmo Wi-Fi: Online > Servidor > http://{address}:{port}", flush=True)
        except OSError:
            print("Confira o IPv4 do PC com ipconfig para conectar pelo Wi-Fi.", flush=True)
    sys.argv = ["relay.py", "--host", host, "--port", str(port), "--db", str(database)]
    relay.main()


if __name__ == "__main__":
    main()
