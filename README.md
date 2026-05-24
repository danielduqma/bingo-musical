# 🎵 Bingo Musical

Generador de cartones de bingo musical en PDF. Cada cartón tiene dos filas de canciones; el jugador marca las que van sonando y gana cuando completa una fila entera.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Uso básico

```bash
uv run --with weasyprint,jinja2 python3 generate_bingo.py songs.csv
```

Genera un PDF con una página (2 cartones) en `output/bingo.pdf`.

### Opciones

| Opción | Por defecto | Descripción |
|---|---|---|
| `--count N` | `1` | Número de cartones a generar (2 por página A4) |
| `--output ruta` | `output/bingo.pdf` | Ruta del PDF de salida |
| `--template ruta` | `template.html` | Plantilla HTML personalizada |
| `--seed N` | aleatorio | Semilla para resultados reproducibles |

```bash
# 5 páginas A4 con 10 cartones, resultado reproducible
uv run --with weasyprint,jinja2 python3 generate_bingo.py songs.csv --count 10 --seed 42
```

## Formato del CSV

El CSV de canciones tiene dos columnas obligatorias y una opcional:

```csv
Grupo/artista,Canción,Orden
Queen,Bohemian Rhapsody,1
The Beatles,Hey Jude,2
Radiohead,Creep,8
The Rolling Stones,Paint It Black,
ABBA,Dancing Queen,
```

- **`Grupo/artista`** y **`Canción`**: nombre del artista y título de la canción.
- **`Orden`** *(opcional)*: número entero que indica el orden de reproducción (ver [Modo duración](#modo-duración)).

Se necesitan al menos 8 canciones en el CSV.

## Estructura de un cartón

Cada cartón tiene **2 filas × 5 columnas**. En cada fila hay entre 3 y 4 canciones; el resto de celdas son relleno decorativo. Un cartón tiene 7 canciones en total (distribución 3+4 ó 4+3 aleatoria).

- **Línea**: se completa una fila entera (3 o 4 canciones).
- **Bingo**: se completan las 7 canciones del cartón (ambas filas).

---

## Modo duración

Permite controlar exactamente cuándo se produce el bingo: marca las canciones que van a sonar y en qué orden, y el generador crea un cartón especial que **garantiza el bingo en la última canción**.

### Cómo activarlo

Añade la columna `Orden` al CSV y asigna valores enteros consecutivos (1, 2, 3…) a las canciones de la secuencia de juego. Las canciones **sin** valor en `Orden` son *canciones de reserva* y no se anuncian durante la partida.

```csv
Grupo/artista,Canción,Orden
Queen,Bohemian Rhapsody,1
The Beatles,Hey Jude,2
Michael Jackson,Thriller,3
Nirvana,Smells Like Teen Spirit,4
David Bowie,Heroes,5
Led Zeppelin,Stairway to Heaven,6
Pink Floyd,Wish You Were Here,7
Radiohead,Creep,8          ← el bingo ocurre aquí
The Rolling Stones,Paint It Black,   ← canciones de reserva
Fleetwood Mac,Go Your Own Way,
ABBA,Dancing Queen,
```

Al ejecutar con este CSV, el modo duración se activa automáticamente:

```
Modo duración activo:
  · Línea en canción #4: "Smells Like Teen Spirit" – Nirvana (cartón de línea: página 1)
  · Bingo en canción #8: "Creep" – Radiohead (cartón de bingo: página 1)
  · El cartón de línea y el cartón de bingo son distintos.
```

### Cómo funciona internamente

El generador produce **tres tipos de cartones**:

**Cartón de línea** *(posición 1 de la primera página)*

- **Fila de línea**: canciones de posiciones 1..K, con la última siendo la canción K (K ≈ N/2). Se completa exactamente en la canción K → **primera línea de la partida**.
- **Otra fila**: contiene al menos una canción de reserva (nunca anunciada) → **nunca puede completarse** → este cartón no puede hacer bingo.

**Cartón de bingo** *(posición 2 de la primera página)*

Todas sus 7 canciones pertenecen a la secuencia ordenada:

- **Fila pre-bingo**: contiene al menos una canción de posiciones K+1..N-1, por lo que se completa **después de K** (no roba la línea) pero antes del bingo.
- **Fila de bingo**: contiene la canción N (última de la secuencia). Se completa en la canción N → **bingo**.

**Cartones normales** *(resto de páginas)*

Cada fila incluye obligatoriamente al menos una canción de reserva. Ningún cartón normal puede línear ni hacer bingo durante la secuencia.

El resultado: **dos ganadores distintos** — uno consigue la línea en la canción K y otro el bingo en la canción N.

### Reglas del CSV en modo duración

- Los valores de `Orden` deben ser una secuencia contigua sin huecos ni duplicados: `1, 2, 3, …, N`.
- Se necesitan al menos **7 canciones con `Orden`** (para rellenar el cartón de bingo con canciones ordenadas).
- Se necesita al menos **1 canción de reserva** (sin `Orden`) para la fila extra del cartón de línea.
- Se necesitan al menos **2 cartones** (`--count 2`): uno para línea y otro para bingo.
