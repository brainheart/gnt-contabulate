# Greek New Testament Contabulate

A static explorer of the **SBL Greek New Testament v1.2**, with the same HistoricalChristianFaith commentary collection used by the KJV and Luther Contabulate instances.

**27 books · 260 chapters · 7,939 verses · 137,741 words · 58,620 commentary excerpts from 242 commentators.**

## Build and preview

Python 3.10+ is sufficient for the offline build; all source snapshots are included and verified by SHA-256.

```sh
python3 build.py
python3 -m http.server --bind 0.0.0.0 8776 -d docs
```

Open [the local preview](http://localhost:8776/). The canonical URL is [gnt.contabulate.org](https://gnt.contabulate.org/).

```sh
python3 -m unittest discover -v
npm ci
npx playwright install chromium
npm test
```

Playwright starts its own server on port 8775. `python3 scripts/verify_sources.py` regenerates the independent source comparison.

## Text and edition

- **Primary source:** [Faithlife/SBLGNT](https://github.com/Faithlife/SBLGNT), publisher's v1.2 text, commit `c4d241a9c1c479a55b989ba35a4976c1d0b8052c`.
- **Editor:** Michael W. Holmes. Copyright © 2010 Society of Biblical Literature and Logos Bible Software. Licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); full license and upstream notices are in `source_text/`.
- **Independent verification:** [MorphGNT SBLGNT 6.12](https://github.com/morphgnt/sblgnt/tree/6.12), edited by James K. Tauber, DOI `10.5281/zenodo.376200`. The included parsing/lemma snapshot retains its CC BY-SA 3.0 terms and is used only for comparison. It agrees on token sequences in 7,910 verses; 17 differ, and it predates the 12 added verses of John 7:53–8:11. The publisher's reading wins consistently; see `source_text/comparison.json`.
- Source headings and apparatus pointers (`⸀`, `⸂`, etc., including their numbered suffixes) are excluded. Greek spelling, accents, breathings, punctuation, and editorial square/double brackets remain; whitespace and Unicode representation are normalized.
- The corpus includes the publisher's bracketed John 7:53–8:11, the shorter ending appended to Mark 16:8, and Mark 16:9–20. Counts include that text. SBLGNT omits certain KJV verses, including Romans 16:25–27; omitted verse numbers are never invented or renumbered.

SBLGNT is a modern critical edition with a clear redistribution license, suited to a reproducible public explorer. It is one edition, not a synthesis of manuscripts or a reproduction of NA28's apparatus.

## Search and metrics

The hierarchy is Testament → Book → Chapter → Verse, with word/bigram/trigram vocabulary views. Canonical IDs are `Matt.1.1` through `Rev.22.21`; sortable locations run from `01.Matt.001.001` to `27.Rev.022.021`.

Search ignores capitalization and elision marks and preserves accents and breathings. NFC and decomposed Unicode queries agree. Vocabulary counts are **written forms, not lemmas**; grave/acute forms remain distinct. Phrase indexes stop at verse boundaries, and percentage denominators sum available phrase positions within verses. Greek question marks count as sentence endings; middle dots do not. The word-length metric counts Unicode code points of normalized tokens. Proper-name filtering is disabled until a reviewed name list is available.

## Commentary mapping

The pinned snapshot takes the union of KJV and Luther HCF records. This preserves 13 records found only in KJV and a Bede comment on 3 John 1:15 found only in Luther. Only its New Testament material is included. Author names, record IDs, dates, work titles, source links, and the existing historical-text/modern-preview display policy are preserved. The mapped corpus has 242 commentators with coverage; the OT-only commentators are not exposed as empty columns.

Most references map directly. These exceptions use explicit passage overlap:

| SBLGNT verse | KJV/HCF reference(s) |
|---|---|
| Acts 19:40 | Acts 19:40–41 |
| 2 Corinthians 13:12 | 2 Corinthians 13:12–13 |
| 2 Corinthians 13:13 | 2 Corinthians 13:14 |
| 3 John 1:14 | 3 John 1:14 |
| 3 John 1:15 | 3 John 1:14, plus HCF records explicitly numbered 1:15 |
| Revelation 12:18 and 13:1 | Revelation 13:1 |

A comment covering multiple merged source verses is counted once per target verse. Split verses share passage-level comments; this does not claim clause-level alignment or that every commentator used this Greek edition. Commentary modal passage labels and outbound links retain HCF numbering.

Sixty source excerpts have no target passage in this edition. Their IDs are recorded in `docs/data/commentary_alignment.json`; their records remain in the compressed source snapshot. All retained records are accounted for by the tests. Table totals count verse–comment overlaps; the instance's comment total counts individual excerpts, so it is smaller than the sum across verses.

See [commentary/README.md](commentary/README.md) for snapshot provenance and rights handling and [the reader-facing source notes](docs/sources.html).

## Project layout

- `build.py`: authoritative corpus/index/metrics/metadata builder.
- `scripts/map_commentary.py`: checked, deduplicated commentary crosswalk.
- `source_text/`: pinned publisher files, notices, independent MorphGNT snapshot, and comparison.
- `commentary/snapshot/`: compressed NT source records; `provenance.json` pins their origin and hashes.
- `docs/data`, `docs/lines`, `docs/commentary`, `docs/instance.json`: generated, committed static output.
- `instance-meta.json`: curated identity and verified sample links.
- `tests/`: corpus, Unicode, crosswalk, and browser regression checks.

The shell is adapted from Luther Contabulate commit `63c1d27`, matching the current shared table features in Tanakh. Application code is MIT licensed; source text and commentary retain their respective terms.

## Publication

GitHub repository: [brainheart/gnt-contabulate](https://github.com/brainheart/gnt-contabulate).
GitHub Pages publishes `main:/docs` at [gnt.contabulate.org](https://gnt.contabulate.org/).
Cloudflare DNS points the subdomain to `brainheart.github.io`. Push rebuilt and tested output to `main` to publish updates. The hub registration is maintained in the separate [Contabulate repository](https://github.com/brainheart/contabulate); verify the live `/instance.json` endpoint after each release.
