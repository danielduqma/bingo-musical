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
SONGS_PER_CARD = 7  # siempre 7: distribución 3+4 o 4+3 aleatoria


def load_songs(csv_path: Path) -> tuple[list[dict], list[dict]]:
    """Load songs from CSV. Returns (all_songs, ordered_songs).

    If the CSV contains an 'Orden' column, songs with a value form the ordered
    play sequence (sorted by that value). The sequence must be a contiguous
    range 1..N with no duplicates.
    """
    songs: list[dict] = []
    ordered: list[dict] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        has_orden = "Orden" in (reader.fieldnames or [])
        for i, row in enumerate(reader, start=1):
            artist = row.get("Grupo/artista", "").strip()
            title = row.get("Canción", "").strip()
            if not artist or not title:
                continue
            song: dict = {"artist": artist, "title": title, "index": i}
            if has_orden:
                orden_str = row.get("Orden", "").strip()
                if orden_str:
                    try:
                        song["orden"] = int(orden_str)
                        ordered.append(song)
                    except ValueError:
                        print(
                            f"Error: valor de Orden inválido en fila {i}: '{orden_str}'.",
                            file=sys.stderr,
                        )
                        sys.exit(1)
            songs.append(song)

    if len(songs) < CARD_ROWS * MAX_SONGS_PER_ROW:
        print(
            f"Error: se necesitan al menos {CARD_ROWS * MAX_SONGS_PER_ROW} canciones en el CSV.",
            file=sys.stderr,
        )
        sys.exit(1)

    if ordered:
        ordered.sort(key=lambda s: s["orden"])
        orden_values = [s["orden"] for s in ordered]
        if orden_values != list(range(1, len(ordered) + 1)):
            print(
                "Error: los valores de Orden deben ser una secuencia contigua sin huecos ni "
                f"duplicados (1..{len(ordered)}). Valores encontrados: {orden_values}.",
                file=sys.stderr,
            )
            sys.exit(1)

    return songs, ordered


def _row_distribution(total: int, rng: random.Random) -> list[int]:
    """Distribute `total` songs across CARD_ROWS rows, each between MIN and MAX songs per row."""
    counts = [MIN_SONGS_PER_ROW] * CARD_ROWS
    remaining = total - sum(counts)
    indices = list(range(CARD_ROWS))
    rng.shuffle(indices)
    for i in indices:
        if remaining == 0:
            break
        if counts[i] < MAX_SONGS_PER_ROW:
            counts[i] += 1
            remaining -= 1
    return counts


def _build_row(songs: list[dict], row_size: int, rng: random.Random) -> list[dict]:
    cells = [{"type": "song", **s} for s in songs]
    cells += [{"type": "filler"} for _ in range(CARD_COLS - row_size)]
    rng.shuffle(cells)
    return cells


def build_card(
    songs: list[dict],
    rng: random.Random,
    seen_cards: set[frozenset[int]],
    songs_per_card: int,
) -> list[list[dict]]:
    for _ in range(1000):
        row_counts = _row_distribution(songs_per_card, rng)
        rows = []
        used: set[int] = set()
        row_song_sets: list[frozenset[int]] = []
        for n_songs in row_counts:
            available = [s for s in songs if s["index"] not in used]
            chosen = rng.sample(available, n_songs)
            row_set = frozenset(s["index"] for s in chosen)
            if row_set in row_song_sets:
                break
            row_song_sets.append(row_set)
            used.update(row_set)
            rows.append(_build_row(chosen, n_songs, rng))
        else:
            card_key = frozenset(used)
            if card_key not in seen_cards:
                seen_cards.add(card_key)
                return rows
    raise RuntimeError(
        "No se pudieron generar suficientes cartones únicos con las canciones disponibles."
    )


def build_duration_card(
    ordered_songs: list[dict],
    pool_songs: list[dict],
    rng: random.Random,
    seen_cards: set[frozenset[int]],
) -> list[list[dict]]:
    """Build the winner card that bingos exactly when the last ordered song is announced.

    Winning row: contains last_song + (win_size - 1) earlier ordered songs.
      → Completes only when last_song is announced (song #N).
    Losing row: contains at least 1 pool song (never announced).
      → Can never complete during the N-song sequence.
    """
    if len(ordered_songs) < MIN_SONGS_PER_ROW:
        print(
            f"Error: se necesitan al menos {MIN_SONGS_PER_ROW} canciones con Orden "
            "para generar la carta ganadora.",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(pool_songs) < CARD_ROWS:
        print(
            f"Error: se necesitan al menos {CARD_ROWS} canciones sin Orden (canciones de "
            "reserva) para garantizar que solo un cartón gane.",
            file=sys.stderr,
        )
        sys.exit(1)

    last_song = ordered_songs[-1]
    earlier_songs = ordered_songs[:-1]

    # Determine win/lose row sizes from what's feasible (3+4 or 4+3)
    feasible = [
        (win, SONGS_PER_CARD - win)
        for win in [MIN_SONGS_PER_ROW, MAX_SONGS_PER_ROW]
        if len(earlier_songs) >= win - 1
    ]
    if not feasible:
        print(
            "Error: no hay suficientes canciones con Orden para construir la fila ganadora.",
            file=sys.stderr,
        )
        sys.exit(1)

    win_size, lose_size = rng.choice(feasible)
    win_other = rng.sample(earlier_songs, win_size - 1)
    win_songs = win_other + [last_song]
    rng.shuffle(win_songs)

    # Losing row: 1 mandatory pool song + (lose_size - 1) others (not used in winning row)
    used = {s["index"] for s in win_songs}
    available_pool = [s for s in pool_songs if s["index"] not in used]
    if not available_pool:
        print(
            "Error: no hay canciones de reserva disponibles para la fila perdedora.",
            file=sys.stderr,
        )
        sys.exit(1)
    pool_pick = rng.choice(available_pool)
    used.add(pool_pick["index"])

    rest_available = [
        s for s in (ordered_songs + pool_songs) if s["index"] not in used
    ]
    if len(rest_available) < lose_size - 1:
        print(
            "Error: no hay suficientes canciones para rellenar la fila perdedora.",
            file=sys.stderr,
        )
        sys.exit(1)
    lose_songs = [pool_pick] + rng.sample(rest_available, lose_size - 1)
    rng.shuffle(lose_songs)

    win_row = _build_row(win_songs, win_size, rng)
    lose_row = _build_row(lose_songs, lose_size, rng)
    rows = [win_row, lose_row] if rng.random() < 0.5 else [lose_row, win_row]

    card_key = frozenset(s["index"] for s in win_songs + lose_songs)
    seen_cards.add(card_key)
    return rows


def build_constrained_card(
    songs: list[dict],
    pool_songs: list[dict],
    rng: random.Random,
    seen_cards: set[frozenset[int]],
) -> list[list[dict]]:
    """Build a normal card where every row includes at least 1 pool song.

    Used in duration mode so normal cards can never accidentally bingo during
    the ordered play sequence.
    """
    for _ in range(1000):
        row_counts = _row_distribution(SONGS_PER_CARD, rng)
        rows = []
        used: set[int] = set()
        row_song_sets: list[frozenset[int]] = []
        ok = True
        for n_songs in row_counts:
            available_pool = [s for s in pool_songs if s["index"] not in used]
            if not available_pool:
                ok = False
                break
            pool_pick = rng.choice(available_pool)
            used.add(pool_pick["index"])
            available_rest = [s for s in songs if s["index"] not in used]
            if len(available_rest) < n_songs - 1:
                ok = False
                break
            others = rng.sample(available_rest, n_songs - 1)
            chosen = [pool_pick] + others
            row_set = frozenset(s["index"] for s in chosen)
            if row_set in row_song_sets:
                ok = False
                break
            row_song_sets.append(row_set)
            used.update(row_set)
            rng.shuffle(chosen)
            rows.append(_build_row(chosen, n_songs, rng))
        if not ok:
            continue
        card_key = frozenset(used)
        if card_key not in seen_cards:
            seen_cards.add(card_key)
            return rows
    raise RuntimeError(
        "No se pudieron generar suficientes cartones únicos con las canciones disponibles."
    )


def generate_pdf(
    songs: list[dict],
    ordered_songs: list[dict],
    template_path: Path,
    output_path: Path,
    count: int,
    seed: int | None,
) -> None:
    rng = random.Random(seed)
    pool_songs = [s for s in songs if "orden" not in s]
    duration_mode = bool(ordered_songs)

    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)

    seen_cards: set[frozenset[int]] = set()
    winner_placed = False

    def _next_card() -> list[list[dict]]:
        nonlocal winner_placed
        if duration_mode and not winner_placed:
            winner_placed = True
            return build_duration_card(ordered_songs, pool_songs, rng, seen_cards)
        if duration_mode:
            return build_constrained_card(songs, pool_songs, rng, seen_cards)
        return build_card(songs, rng, seen_cards, SONGS_PER_CARD)

    cards = [_next_card() for _ in range(count)]

    pages = []
    for i in range(0, len(cards), 2):
        pages.append({
            "top": cards[i],
            "bottom": cards[i + 1] if i + 1 < len(cards) else None,
        })

    html_content = template.render(pages=pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content, base_url=str(template_path.parent)).write_pdf(
        str(output_path)
    )

    n_pages = len(pages)
    if duration_mode:
        last = ordered_songs[-1]
        n = len(ordered_songs)
        print(
            f'Modo duración activo: bingo garantizado en la canción #{n} '
            f'("{last["title"]}" – {last["artist"]}). '
            "La carta ganadora está en la parte superior de la primera página."
        )
    print(f"PDF generado: {output_path} ({n_pages} página(s), {count} cartones)")


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
        help="Número de cartones a generar (2 cartones por página A4)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla aleatoria para reproducibilidad",
    )
    args = parser.parse_args()

    songs, ordered_songs = load_songs(args.csv)
    generate_pdf(songs, ordered_songs, args.template, args.output, args.count, args.seed)


if __name__ == "__main__":
    main()
