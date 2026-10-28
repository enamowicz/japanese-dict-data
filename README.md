# japanese-dict-data

Builds the offline Japanese–English dictionary used by a Japanese reading app, and publishes it as
a GitHub Release every month.

## What's in a release

| File | What |
|---|---|
| `dict.sqlite.gz` | The dictionary as a gzip-compressed SQLite database |
| `manifest.json` | Version, schema, size and SHA-256 of the download and of the unpacked database, source versions |
| `DATA-LICENSE.md` | Licence and attribution (CC BY-SA 4.0) |

The app reads `https://github.com/enamowicz/japanese-dict-data/releases/latest/download/manifest.json`.

## Tables (schema 1)

- `entry`: one row per JMdict entry. `id` is the JMdict sequence number (stable across releases),
  plus `common`, `jlpt` (5 = N5 … 1 = N1) and `zipf` (wordfreq frequency × 100).
- `kanji_form`, `kana_form`: written forms and readings, indexed by `text` for lookups.
- `sense`: meanings, with parts of speech and English glosses as JSON arrays.
- `kanji`: KANJIDIC2 characters (strokes, grade, frequency, readings, meanings).
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

The build script is MIT (`LICENSE`). The built dictionary is CC BY-SA 4.0; see `DATA-LICENSE.md` for
the sources and required attribution.
