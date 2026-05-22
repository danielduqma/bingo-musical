#!/usr/bin/env python3

import argparse
import csv
import random
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

FILLER_SYMBOLS = ["♪", "★", "♫", "🎵", "🎶", "🎸", "🎤"]
CARD_ROWS = 2
CARD_COLS = 5
MIN_SONGS_PER_ROW = 3
MAX_SONGS_PER_ROW = 4


def load_songs(csv_path: Path) -> list[dict]:
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            artist = row.get("Grupo/artista", "").strip()
            title = row.get("Canción", "").strip()
            if artist and title:
                songs.append({"artist": artist, "title": title, "index": i})
    if len(songs) < CARD_ROWS * MAX_SONGS_PER_ROW:
        print(
            f"Error: se necesitan al menos {CARD_ROWS * MAX_SONGS_PER_ROW} canciones en el CSV.",
            file=sys.stderr,
        )
        sys.exit(1)
    return songs


def build_card(songs: list[dict], rng: random.Random) -> list[list[dict]]:
    rows = []
    used: set[int] = set()
    for _ in range(CARD_ROWS):
        n_songs = rng.randint(MIN_SONGS_PER_ROW, MAX_SONGS_PER_ROW)
        available = [s for s in songs if s["index"] not in used]
        chosen = rng.sample(available, n_songs)
        used.update(s["index"] for s in chosen)
        n_fillers = CARD_COLS - n_songs
        cells = [{"type": "song", **s} for s in chosen]
        cells += [{"type": "filler"} for _ in range(n_fillers)]
        rng.shuffle(cells)
        rows.append(cells)
    return rows


def generate_pdf(
    songs: list[dict],
    template_path: Path,
    output_path: Path,
    count: int,
    seed: int | None,
) -> None:
    rng = random.Random(seed)

    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)

    pages = []
    for _ in range(count):
        card_top = build_card(songs, rng)
        card_bottom = build_card(songs, rng)
        pages.append({"top": card_top, "bottom": card_bottom})

    html_content = template.render(pages=pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content, base_url=str(template_path.parent)).write_pdf(
        str(output_path)
    )
    print(f"PDF generado: {output_path} ({count} página(s), {count * 2} cartones)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de cartones de bingo musical")
    parser.add_argument("csv", type=Path, help="Ruta al CSV de canciones")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).parent / "template.html",
        help="Plantilla HTML (por defecto: template.html)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "output" / "bingo.pdf",
        help="Ruta del PDF de salida",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Número de páginas A4 a generar (2 cartones por página)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla aleatoria para reproducibilidad",
    )
    args = parser.parse_args()

    songs = load_songs(args.csv)
    generate_pdf(songs, args.template, args.output, args.count, args.seed)


if __name__ == "__main__":
    main()
