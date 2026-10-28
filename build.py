"""Builds dict.sqlite for the Japanese reading app from public dictionary data.

Sources (see DATA-LICENSE.md for licences):
  JMdict (English) and KANJIDIC2 via jmdict-simplified, JLPT vocabulary lists from
  open-anki-jlpt-decks, word frequencies from wordfreq. The release also carries the
  SudachiDict system dictionary for the app's tokenizer, unchanged.

Usage:
  python build.py [--out dist]

Writes <out>/dict.sqlite, <out>/dict.sqlite.gz, <out>/sudachi-<edition>.dic.gz and
<out>/manifest.json.
"""

import argparse
import csv
import datetime
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
import re
import shutil
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

import wordfreq

# Bump when the table layout changes in a way the app has to know about. The app only installs a
# dictionary whose schema it understands.
SCHEMA = 1

JMDICT_RELEASE = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
SUDACHI_RELEASE = "https://api.github.com/repos/WorksApplications/SudachiDict/releases/latest"
# "core" keeps compound words whole (人間関係, 一生懸命); "small" only has short units.
SUDACHI_EDITION = "core"
JLPT_CSV = "https://raw.githubusercontent.com/jamsinclair/open-anki-jlpt-decks/main/src/n{level}.csv"
CACHE = Path(__file__).parent / "cache"


def fetch(url: str, name: str) -> bytes:
    """Downloads `url` once into cache/<name> and returns its bytes."""
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"downloading {url}", file=sys.stderr)
        request = urllib.request.Request(url, headers={"User-Agent": "japanese-dict-data"})
        with urllib.request.urlopen(request) as response:
            path.write_bytes(response.read())
    return path.read_bytes()


def jmdict_simplified() -> tuple[str, dict, dict]:
    """Returns (release tag, JMdict JSON, KANJIDIC2 JSON) from the latest jmdict-simplified release."""
    release = json.loads(urllib.request.urlopen(JMDICT_RELEASE).read())
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}

    def load(prefix: str) -> dict:
        name = next(n for n in assets if n.startswith(prefix) and n.endswith(".json.zip"))
        with zipfile.ZipFile(io.BytesIO(fetch(assets[name], name))) as archive:
            return json.loads(archive.read(archive.namelist()[0]))

    return release["tag_name"], load("jmdict-eng-3"), load("kanjidic2-en-3")


SCHEMA_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- One row per JMdict entry. id is the JMdict sequence number, which stays the same across releases,
-- so user data can refer to it. jlpt is 5 (N5, easiest) to 1 (N1); zipf is wordfreq's Zipf
-- frequency x 100 (about 100 = rare, 700 = very common), 0 if unknown.
CREATE TABLE entry (
  id INTEGER PRIMARY KEY,
  common INTEGER NOT NULL,
  jlpt INTEGER,
  zipf INTEGER NOT NULL
);

-- Written forms with kanji (JMdict k_ele) and readings (r_ele), in dictionary order.
-- tags: JSON array of JMdict tags (e.g. ["rK"] rarely used kanji form) or NULL.
CREATE TABLE kanji_form (
  entry_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  text TEXT NOT NULL,
  common INTEGER NOT NULL,
  tags TEXT,
  PRIMARY KEY (entry_id, ord)
) WITHOUT ROWID;

-- applies_to: JSON array of the kanji forms this reading belongs to, NULL for all of them.
CREATE TABLE kana_form (
  entry_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  text TEXT NOT NULL,
  common INTEGER NOT NULL,
  tags TEXT,
  applies_to TEXT,
  PRIMARY KEY (entry_id, ord)
) WITHOUT ROWID;

-- Meanings. pos, misc, field, info and glosses are JSON arrays (NULL when empty). applies_to_kanji /
-- applies_to_kana restrict the sense to some forms (NULL = all).
CREATE TABLE sense (
  entry_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  pos TEXT,
  misc TEXT,
  field TEXT,
  info TEXT,
  applies_to_kanji TEXT,
  applies_to_kana TEXT,
  glosses TEXT NOT NULL,
  PRIMARY KEY (entry_id, ord)
) WITHOUT ROWID;

-- KANJIDIC2 characters. Readings and meanings are JSON arrays. jlpt_old is KANJIDIC2's pre-2010
-- four-level JLPT (4 easiest). SKIP codes are left out (separate licence).
CREATE TABLE kanji (
  literal TEXT PRIMARY KEY,
  strokes INTEGER,
  grade INTEGER,
  freq INTEGER,
  jlpt_old INTEGER,
  onyomi TEXT,
  kunyomi TEXT,
  nanori TEXT,
  meanings TEXT
) WITHOUT ROWID;
"""

INDEX_SQL = """
CREATE INDEX kanji_form_text ON kanji_form (text);
CREATE INDEX kana_form_text ON kana_form (text);
"""


def as_json(values) -> str | None:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":")) if values else None


def zipf_of(frequencies: dict[str, float], forms: list[str]) -> int:
    """Highest Zipf frequency x 100 among the forms. wordfreq splits conjugated words into stems
    (食べる -> 食べ), so this undercounts verbs and adjectives; it is a ranking signal only."""
    best = max((frequencies.get(form, 0.0) for form in forms), default=0.0)
    return round(math.log10(best * 1e9) * 100) if best > 0 else 0


def write_entries(db: sqlite3.Connection, jmdict: dict) -> dict[int, tuple[list[str], list[str], bool, set[str]]]:
    """Inserts JMdict entries; returns {id: (kanji forms, kana forms, common, gloss words)} for JLPT matching."""
    frequencies = wordfreq.get_frequency_dict("ja", "best")
    forms_by_id = {}
    for word in jmdict["words"]:
        entry_id = int(word["id"])
        kanji = [k["text"] for k in word["kanji"]]
        kana = [k["text"] for k in word["kana"]]
        common = any(k["common"] for k in word["kanji"] + word["kana"])
        # Frequency of the main spelling only: rare variants are often shared with other words (本 is
        # also a spelling of もと). Words usually written in kana (uk) also count their main reading.
        usually_kana = not kanji or all("uk" in s["misc"] for s in word["sense"])
        zipf = zipf_of(frequencies, kanji[:1] + kana[:1] if usually_kana else kanji[:1])
        db.execute("INSERT INTO entry VALUES (?, ?, NULL, ?)", (entry_id, int(common), zipf))
        for i, k in enumerate(word["kanji"]):
            db.execute("INSERT INTO kanji_form VALUES (?, ?, ?, ?, ?)", (entry_id, i, k["text"], int(k["common"]), as_json(k["tags"])))
        for i, k in enumerate(word["kana"]):
            applies = None if k["appliesToKanji"] == ["*"] else k["appliesToKanji"]
            db.execute(
                "INSERT INTO kana_form VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, i, k["text"], int(k["common"]), as_json(k["tags"]), as_json(applies) if applies is not None else None),
            )
        for i, s in enumerate(word["sense"]):
            restrict_kanji = None if s["appliesToKanji"] == ["*"] else s["appliesToKanji"]
            restrict_kana = None if s["appliesToKana"] == ["*"] else s["appliesToKana"]
            db.execute(
                "INSERT INTO sense VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    i,
                    as_json(s["partOfSpeech"]),
                    as_json(s["misc"]),
                    as_json(s["field"]),
                    as_json(s["info"]),
                    json.dumps(restrict_kanji, ensure_ascii=False) if restrict_kanji is not None else None,
                    json.dumps(restrict_kana, ensure_ascii=False) if restrict_kana is not None else None,
                    as_json([g["text"] for g in s["gloss"] if g["lang"] == "eng"]) or "[]",
                ),
            )
        glosses = " ".join(g["text"] for s in word["sense"] for g in s["gloss"] if g["lang"] == "eng")
        forms_by_id[entry_id] = (kanji, kana, common, meaning_words(glosses))
    return forms_by_id


# Words too common in English glosses to tell entries apart.
STOPWORDS = {"to", "the", "a", "an", "of", "be", "in", "on", "for", "or", "and", "one", "s", "e", "g", "etc", "with", "at", "as", "by", "is", "it"}


def meaning_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower())) - STOPWORDS


def to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def write_jlpt(db: sqlite3.Connection, forms_by_id: dict) -> dict:
    """Sets entry.jlpt from the JLPT lists. Each listed spelling goes to the best matching JMdict entry:
    that form with one of the listed readings, then the entry whose English glosses share the most words
    with the list's meaning (いる "to be, to exist" is 居る, not 要る "to need"; いくら "how much" is 幾ら,
    not "salmon roe"), then common entries, then the lowest sequence number. A word in several lists
    keeps the easiest level."""
    by_form: dict[str, list[int]] = {}
    for entry_id, (kanji, kana, _, _) in forms_by_id.items():
        for form in set(kanji + kana):
            by_form.setdefault(form, []).append(entry_id)

    def alternatives(field: str) -> list[str]:
        # The lists write variants as "足; 脚", affixes with a "～" placeholder ("～円") and notes in
        # brackets ("下品(な)", "はい (かん)" for interjections).
        field = re.sub(r"[(（][^)）]*[)）]", "", field).replace("；", ";").replace("、", ";")
        return [a for a in (part.strip().strip("～〜").strip() for part in field.split(";")) if a]

    def candidates(expression: str, readings: set[str]) -> list[int]:
        ids = by_form.get(expression, [])
        for suffix in ("する", "な", "と"):  # "コピーする", "惨めな", "ゆっくりと" are JMdict's コピー, 惨め, ゆっくり
            if not ids and expression.endswith(suffix) and len(expression) > len(suffix):
                ids = by_form.get(expression[: -len(suffix)], [])
                readings = {r[: -len(suffix)] if r.endswith(suffix) else r for r in readings}
        return [i for i in ids if readings & {to_hiragana(k) for k in forms_by_id[i][1]}] or ids

    levels: dict[int, int] = {}
    stats = {"rows": 0, "matched": 0, "unmatched": []}
    for level in (5, 4, 3, 2, 1):
        text = fetch(JLPT_CSV.format(level=level), f"jlpt-n{level}.csv").decode("utf-8")
        for row in csv.DictReader(io.StringIO(text)):
            stats["rows"] += 1
            readings = {to_hiragana(r) for r in alternatives(row["reading"])}
            found = [c for expression in alternatives(row["expression"]) for c in candidates(expression, readings)]
            if not found:
                stats["unmatched"].append(f"N{level} {row['expression']} ({row['reading']})")
                continue
            stats["matched"] += 1
            # One entry per listed spelling (足; 脚 are separate JMdict entries), common entries first.
            meaning = meaning_words(row["meaning"])
            for expression in alternatives(row["expression"]):
                ids = candidates(expression, readings)
                if ids:
                    best = min(ids, key=lambda i: (-len(meaning & forms_by_id[i][3]), not forms_by_id[i][2], i))
                    levels[best] = max(levels.get(best, 0), level)
    db.executemany("UPDATE entry SET jlpt = ? WHERE id = ?", [(level, i) for i, level in levels.items()])
    stats["entries"] = len(levels)
    return stats


def write_kanji(db: sqlite3.Connection, kanjidic: dict) -> None:
    for c in kanjidic["characters"]:
        misc = c["misc"]
        readings = [r for group in (c["readingMeaning"] or {}).get("groups", []) for r in group["readings"]]
        meanings = [m["value"] for group in (c["readingMeaning"] or {}).get("groups", []) for m in group["meanings"] if m["lang"] == "en"]
        db.execute(
            "INSERT INTO kanji VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                c["literal"],
                misc["strokeCounts"][0] if misc["strokeCounts"] else None,
                misc["grade"],
                misc["frequency"],
                misc["jlptLevel"],
                as_json([r["value"] for r in readings if r["type"] == "ja_on"]),
                as_json([r["value"] for r in readings if r["type"] == "ja_kun"]),
                as_json((c["readingMeaning"] or {}).get("nanori", [])),
                as_json(meanings),
            ),
        )


def sudachi_dictionary(out: Path) -> dict:
    """Copies the latest SudachiDict system dictionary into the release as <out>/sudachi-<edition>.dic.gz
    and returns its manifest entry. The .dic is used as published (binary format V1, which needs
    Sudachi 0.8.2+ / SudachiPy 0.7+)."""
    release = json.loads(urllib.request.urlopen(SUDACHI_RELEASE).read())
    version = release["tag_name"].lstrip("v")
    name = f"sudachi-dictionary-{version}-{SUDACHI_EDITION}.zip"
    url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == name)
    dic_path = out / f"sudachi-{SUDACHI_EDITION}.dic"
    with zipfile.ZipFile(io.BytesIO(fetch(url, name))) as archive:
        member = next(n for n in archive.namelist() if n.endswith(f"system_{SUDACHI_EDITION}.dic"))
        with archive.open(member) as src, dic_path.open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
    gz_path = gzip_file(dic_path)
    return {
        "version": version,
        "edition": SUDACHI_EDITION,
        "file": gz_path.name,
        "size": gz_path.stat().st_size,
        "sha256": sha256(gz_path),
        "uncompressedSize": dic_path.stat().st_size,
    }


def gzip_file(path: Path) -> Path:
    gz_path = path.with_name(path.name + ".gz")
    with path.open("rb") as src, gzip.GzipFile(gz_path, "wb", compresslevel=9, mtime=0) as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    return gz_path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="dist", type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True)

    tag, jmdict, kanjidic = jmdict_simplified()
    # UTC build time, so a second build on the same day is still a new version.
    version = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d-%H%M")
    db_path = args.out / "dict.sqlite"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA page_size = 4096;")
    db.executescript(SCHEMA_SQL)

    forms_by_id = write_entries(db, jmdict)
    jlpt = write_jlpt(db, forms_by_id)
    write_kanji(db, kanjidic)
    db.executescript(INDEX_SQL)

    meta = {
        "schema": str(SCHEMA),
        "version": version,
        "jmdict_simplified": tag,
        "jmdict_date": jmdict["dictDate"],
        "kanjidic2_date": kanjidic["dictDate"],
        "wordfreq": importlib.metadata.version("wordfreq"),
    }
    db.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    db.commit()
    db.execute("VACUUM")
    db.execute("ANALYZE")
    db.commit()
    db.close()

    gz_path = gzip_file(db_path)
    tokenizer = sudachi_dictionary(args.out)

    # The top-level fields describe dict.sqlite (schema 1 apps read only those); "tokenizer" was added
    # for the app's Sudachi tokenizer and is installed only when its version changes.
    manifest = {
        "schema": SCHEMA,
        "version": version,
        "file": gz_path.name,
        "size": gz_path.stat().st_size,
        "sha256": sha256(gz_path),
        "uncompressedSize": db_path.stat().st_size,
        "uncompressedSha256": sha256(db_path),
        "sources": meta,
        "tokenizer": tokenizer,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "jlpt-unmatched.txt").write_text("\n".join(jlpt["unmatched"]) + "\n", encoding="utf-8")

    print(f"entries {len(forms_by_id)}, kanji {len(kanjidic['characters'])}")
    print(f"JLPT rows {jlpt['rows']}, matched {jlpt['matched']}, entries with a level {jlpt['entries']}, unmatched {len(jlpt['unmatched'])}")
    print(f"dict.sqlite {db_path.stat().st_size / 1e6:.1f} MB, dict.sqlite.gz {gz_path.stat().st_size / 1e6:.1f} MB")
    print(f"sudachi {tokenizer['version']} {tokenizer['edition']}: {tokenizer['uncompressedSize'] / 1e6:.1f} MB, gzip {tokenizer['size'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
