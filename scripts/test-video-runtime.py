"""Test actual movie dispatch/restoration in bundled Ruby without native Windows calls."""
from plugin_tools import DEFAULT_GAME, MAINTAINED, ROOT, Ruby


def main():
    ruby = Ruby()
    ruby.load_source((ROOT / "scripts/fixtures/video-runtime.fixture").read_text(encoding="utf-8"), "video platform doubles")
    for name in ["000_Config.rb", "001_Video.rb", "006_AndroidPlayer.rb"]:
        path = MAINTAINED / "Nordeluna Video" / name
        if not path.exists():
            path = DEFAULT_GAME / "Plugins/Nordeluna Video" / name
        ruby.load_source(path.read_text(encoding="utf-8-sig"), name)
    ruby.load_source((ROOT / "scripts/fixtures/video-checks.fixture").read_text(encoding="utf-8"), "video dispatch checks")
    print(ruby.evaluate('"PASS: #{$checks} real Ruby video checks; Android routing, Windows preserved, errors, watchdog, audio and brightness restoration"'))


if __name__ == "__main__":
    main()
