"""Create a server-only Discloud upload; never include live database/game files."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package(subdomain, output, areas=None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,18}[a-z0-9]", subdomain):
        raise ValueError("Subdominio: 2 a 20 letras minusculas/numeros/hifens, sem dominio ou https://.")
    relay_source = (ROOT / "server/relay.py").read_text(encoding="utf-8")
    if areas is not None:
        if not isinstance(areas, dict) or set(areas) != {"plaza", "coliseum", "market"}:
            raise ValueError("Areas precisam das chaves plaza, coliseum e market.")
        values = [value for value in areas.values() if value is not None]
        if type(areas["plaza"]) is not int or any(type(value) is not int or value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError("IDs de areas precisam ser inteiros positivos e distintos; plaza e obrigatoria.")
        relay_source, count = re.subn(r"(?m)^DEFAULT_AREAS = [^\r\n]+", "DEFAULT_AREAS = " + repr(areas), relay_source)
        if count != 1:
            raise ValueError("Nao foi encontrada uma configuracao unica de areas no relay.")
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
        archive.writestr("relay.py", relay_source.encode("utf-8"))
        archive.write(ROOT / "server/gifts.py", "gifts.py")
        archive.write(ROOT / "server/economy.py", "economy.py")
        archive.write(ROOT / "server/content.py", "content.py")
        archive.write(ROOT / "server/updates.py", "updates.py")
        archive.write(ROOT / "server/moderation.py", "moderation.py")
        archive.write(ROOT / "server/content-key.json", "content-key.json")
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
    parser.add_argument("--areas-json", type=json.loads, help='Configuracao preparada, por exemplo {"plaza":39,"coliseum":40,"market":41}; nao faz deploy')
    args = parser.parse_args()
    output = args.output or ROOT / "build/discloud" / args.subdomain / "Nordeluna-Online-Discloud.zip"
    print(package(args.subdomain, output, args.areas_json))
