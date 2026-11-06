"""Discloud entry point: package this file as main.py beside relay.py."""
import os
import sys
from pathlib import Path

import relay


def main():
    root = Path(__file__).resolve().parent
    database = root / "data" / "relay.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    existed = database.is_file()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    print("Nordeluna Online: iniciando API. Health check: /health", flush=True)
    print("Banco local existente: " + ("sim" if existed else "nao; primeira inicializacao"), flush=True)
    # The ZIP never contains data/: application updates must preserve this
    # directory. Confirm the hosting's storage policy before real trades.
    sys.argv = ["relay.py", "--host", host, "--port", str(port), "--db", str(database)]
    relay.main()


if __name__ == "__main__":
    main()
