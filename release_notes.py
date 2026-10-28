"""Prints the GitHub release notes for a manifest.json (used by the release workflow)."""

import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
sources, tokenizer = manifest["sources"], manifest["tokenizer"]
print(
    f"dict.sqlite: JMdict {sources['jmdict_date']}, KANJIDIC2 {sources['kanjidic2_date']}, "
    f"wordfreq {sources['wordfreq']} (CC BY-SA 4.0).\n"
    f"sudachi-{tokenizer['edition']}.dic: SudachiDict {tokenizer['version']} (Apache-2.0; UniDic and NEologd "
    "notices in SudachiDict-LEGAL.txt).\nSee DATA-LICENSE.md."
)
