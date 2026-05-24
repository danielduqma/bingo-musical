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
) -> tuple[list[list[dict]], int, int]:
    """Build the winner card with controlled línea and bingo timing.

    All 7 songs come from the ordered sequence — no pool songs on this card:
    - Línea row: songs from positions 1..K, triggering a línea at song K ≈ N/2.
    - Bingo row: remaining songs from the sequence, last being song N (full bingo).

    Normal cards have ≥1 pool song per row and can never línea or bingo during
    the sequence, so this is the only card that can score.

    Returns (rows, K, N) where K is the línea position and N is the bingo position.
    """
    N = len(ordered_songs)
    if N < SONGS_PER_CARD:
        print(
            f"Error: se necesitan al menos {SONGS_PER_CARD} canciones con Orden "
            "para garantizar un bingo completo en el cartón ganador.",
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

    # K: 1-indexed position in the sequence where the línea triggers (≈ N/2)
    K = (N + 1) // 2

    # Determine feasible (línea_size, bingo_size) pairs.
    # Línea row needs linea_size - 1 songs from positions 1..K-1 (before the trigger).
    feasible = [
        (ls, SONGS_PER_CARD - ls)
        for ls in [MIN_SONGS_PER_ROW, MAX_SONGS_PER_ROW]
        if K >= ls  # positions 1..K-1 must have at least linea_size - 1 songs
    ]
    linea_size, bingo_size = rng.choice(feasible)

    # Línea row: trigger is song K; others are sampled from songs at positions < K.
    linea_trigger = ordered_songs[K - 1]
    linea_others = rng.sample(ordered_songs[:K - 1], linea_size - 1)
    linea_songs = linea_others + [linea_trigger]

    # Bingo row: trigger is song N (last_song); others from the remaining sequence.
    last_song = ordered_songs[-1]
    used = {s["index"] for s in linea_songs} | {last_song["index"]}
    remaining = [s for s in ordered_songs if s["index"] not in used]
    bingo_others = rng.sample(remaining, bingo_size - 1)
    bingo_songs = bingo_others + [last_song]

    linea_row = _build_row(linea_songs, linea_size, rng)
    bingo_row = _build_row(bingo_songs, bingo_size, rng)
    rows = [linea_row, bingo_row] if rng.random() < 0.5 else [bingo_row, linea_row]

    card_key = frozenset(s["index"] for s in linea_songs + bingo_songs)
    seen_cards.add(card_key)
    return rows, K, N


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
    linea_pos: int = 0
    bingo_pos: int = 0

    def _next_card() -> list[list[dict]]:
        nonlocal winner_placed, linea_pos, bingo_pos
        if duration_mode and not winner_placed:
            winner_placed = True
            rows, linea_pos, bingo_pos = build_duration_card(
                ordered_songs, pool_songs, rng, seen_cards
            )
            return rows
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
        linea_song = ordered_songs[linea_pos - 1]
        bingo_song = ordered_songs[bingo_pos - 1]
        print(
            f"Modo duración activo:\n"
            f"  · Línea en canción #{linea_pos}: "
            f'"{linea_song["title"]}" – {linea_song["artist"]}\n'
            f"  · Bingo en canción #{bingo_pos}: "
            f'"{bingo_song["title"]}" – {bingo_song["artist"]}\n'
            "  · La carta ganadora está en la parte superior de la primera página."
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
