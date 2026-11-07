"""Normalize MP4s only inside an extracted Android build; preserve desktop originals."""
import argparse
from pathlib import Path
import subprocess


def prepare_movies(game):
    game = game.resolve()
    count = 0
    for relative in ("Movies", "Plugins/Nordeluna Video/movies"):
        folder = game / relative
        if not folder.is_dir():
            continue
        if not folder.resolve().is_relative_to(game):
            raise ValueError("Movie directory escapes the extracted game")
        for movie in sorted(folder.rglob("*")):
            if not movie.is_file() or movie.suffix.lower() != ".mp4":
                continue
            if not movie.resolve().is_relative_to(folder.resolve()):
                raise ValueError("Movie symlink escapes its directory")
            temporary = movie.with_suffix(".android-tmp.mp4")
            try:
                subprocess.run([
                    "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(movie),
                    "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn", "-map_metadata", "-1",
                    "-vf", "scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,fps=30",
                    "-c:v", "libx264", "-profile:v", "main", "-level:v", "3.1", "-pix_fmt", "yuv420p",
                    "-preset", "fast", "-crf", "22", "-maxrate", "4M", "-bufsize", "8M",
                    "-c:a", "aac", "-b:a", "128k", "-ac", "2",
                    "-ar", "48000", "-movflags", "+faststart", str(temporary)
                ], check=True)
                if temporary.stat().st_size <= 0:
                    raise RuntimeError("Empty converted movie: " + movie.name)
                temporary.replace(movie)
                count += 1
                print("Android movie:", movie.relative_to(game))
            finally:
                temporary.unlink(missing_ok=True)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    args = parser.parse_args()
    print("Prepared Android MP4s:", prepare_movies(args.game))
