# Data licences

Each release contains two independent data files with different licences.

## dict.sqlite (CC BY-SA 4.0)

`dict.sqlite` (and `dict.sqlite.gz`) in the releases of this repository is an adaptation of the
sources below and is published under the
[Creative Commons Attribution-ShareAlike 4.0 International licence (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

### Sources

- **JMdict**, **KANJIDIC2** and **KRADFILE**: these files are the property of the
  [Electronic Dictionary Research and Development Group](https://www.edrdg.org/) (EDRDG), and are used in
  conformance with the Group's [licence](https://www.edrdg.org/edrdg/licence.html) (CC BY-SA 4.0).
  Converted to JSON by [jmdict-simplified](https://github.com/scriptin/jmdict-simplified). KANJIDIC2's
  SKIP codes, which carry a separate licence, are not included.
- **Stroke order**: [KanjiVG](https://kanjivg.tagaini.net), Copyright (C) 2009-2026 Ulrich Apel, licensed
  under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), which allows adaptations under
  later versions of the licence. The stroke paths are used unchanged; their lengths and stroke-number
  positions are added.
- **JLPT levels**: vocabulary from [open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks)
  (MIT) and kanji from [kanji-data](https://github.com/davidluzgouveia/kanji-data) by David Luz Gouveia
  (MIT; only its JLPT levels are used), both based on Jonathan Waller's JLPT lists (tanos.co.uk). There
  are no official JLPT lists since 2010; these levels are an approximation.
- **Word frequencies**: [wordfreq](https://github.com/rspeer/wordfreq) by Robyn Speer, data under
  CC BY-SA 4.0. wordfreq includes data from Google Books Ngrams, SUBTLEX, OpenSubtitles, Wikipedia,
  and other sources listed in its README.

## sudachi-core.dic (Apache License 2.0)

`sudachi-core.dic.gz` is the `system_core.dic` file of [SudachiDict](https://github.com/WorksApplications/SudachiDict)
by Works Applications Co., Ltd., unchanged apart from gzip compression, licensed under the
[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0). It contains parts of UniDic
(BSD licence, © The UniDic Consortium) and NEologd (© Toshinori Sato); their full notices are in
`SudachiDict-LEGAL.txt`, attached to every release.
