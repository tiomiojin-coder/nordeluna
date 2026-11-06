"""Create a server-only Discloud upload; never include live database/game files."""
import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package(subdomain, output):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,18}[a-z0-9]", subdomain):
        raise ValueError("Subdominio: 2 a 20 letras minusculas/numeros/hifens, sem dominio ou https://.")
    config = (
        "NAME=Nordeluna Online\n"
        "TYPE=site\n"
        f"ID={subdomain}\n"
        "MAIN=main.py\n"
        "RAM=512\n"
        "VERSION=latest\n"
        "AUTORESTART=true\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("discloud.config", config)
        archive.write(ROOT / "server/discloud_main.py", "main.py")
        archive.write(ROOT / "server/relay.py", "relay.py")
        archive.write(ROOT / "server/requirements.txt", "requirements.txt")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("ZIP corrompido")
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output.with_suffix(".zip.sha256").write_text(digest + "  " + output.name + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subdomain", required=True, help="Nome ja reservado em Dominios, sem .discloud.app/.dev")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "build/discloud" / args.subdomain / "Nordeluna-Online-Discloud.zip"
    print(package(args.subdomain, output))
