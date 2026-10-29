# japanese-dict-data

Builds the offline Japanese–English dictionary used by a Japanese reading app, and publishes it as
a GitHub Release every month.

## What's in a release

| File | What |
|---|---|
| `dict.sqlite.gz` | The dictionary as a gzip-compressed SQLite database |
| `sudachi-core.dic.gz` | SudachiDict's core system dictionary for the app's tokenizer (Sudachi 0.8.2+, format V1) |
| `manifest.json` | Version, schema, size and SHA-256 of each download, source versions (`tokenizer` describes the Sudachi file) |
| `DATA-LICENSE.md`, `SudachiDict-LEGAL.txt` | Licences and attribution |

The app reads `https://github.com/enamowicz/japanese-dict-data/releases/latest/download/manifest.json`.

## Tables (schema 1)

- `entry`: one row per JMdict entry. `id` is the JMdict sequence number (stable across releases),
  plus `common`, `jlpt` (5 = N5 … 1 = N1) and `zipf` (wordfreq frequency × 100).
- `kanji_form`, `kana_form`: written forms and readings, indexed by `text` for lookups.
- `sense`: meanings, with parts of speech and English glosses as JSON arrays.
- `kanji`: KANJIDIC2 characters (strokes, grade, frequency, readings, meanings), with the JLPT N-level
  (kanji-data) and components (KRADFILE).
- `kanji_strokes`: KanjiVG stroke order: SVG paths in drawing order, with lengths and stroke-number positions.
- `kanji_word`: up to 12 common words written with each kanji.
- `meta`: version and source dates.

See `build.py` for the exact layout.

## Build locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows; use .venv/bin on macOS/Linux
.venv/Scripts/python build.py
```

The output goes to `dist/`. Source downloads are cached in `cache/`.

## Licences

The build script is MIT (`LICENSE`). The built dictionary is CC BY-SA 4.0 and the Sudachi dictionary is
Apache-2.0; see `DATA-LICENSE.md` for the sources and required attribution.
