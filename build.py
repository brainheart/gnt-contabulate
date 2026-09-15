import datetime
import json
import math
import re
from pathlib import Path

import hashlib
import unicodedata
from scripts.map_commentary import map_commentary

TOKEN_RE = re.compile(r"[^\W\d_]+(?:[\u0300-\u036f]+[^\W\d_]*)*", re.UNICODE)
SENT_RE = re.compile(r"[.!?;;]+")
APOSTROPHES = str.maketrans({c: "'" for c in "’ʼ᾽"})
# Remove apparatus pointers, while retaining editorial square/double brackets.
APPARATUS_RE = re.compile(r"[⸀⸁⸂⸃⸄⸅][0-9]*")
BOOK_METADATA = {'Matt': ('Matthew', 'Matt', 'New Testament'),
 'Mark': ('Mark', 'Mark', 'New Testament'),
 'Luke': ('Luke', 'Luke', 'New Testament'),
 'John': ('John', 'John', 'New Testament'),
 'Acts': ('Acts', 'Acts', 'New Testament'),
 'Rom': ('Romans', 'Rom', 'New Testament'),
 '1Cor': ('1 Corinthians', '1Cor', 'New Testament'),
 '2Cor': ('2 Corinthians', '2Cor', 'New Testament'),
 'Gal': ('Galatians', 'Gal', 'New Testament'),
 'Eph': ('Ephesians', 'Eph', 'New Testament'),
 'Phil': ('Philippians', 'Phil', 'New Testament'),
 'Col': ('Colossians', 'Col', 'New Testament'),
 '1Thess': ('1 Thessalonians', '1Thess', 'New Testament'),
 '2Thess': ('2 Thessalonians', '2Thess', 'New Testament'),
 '1Tim': ('1 Timothy', '1Tim', 'New Testament'),
 '2Tim': ('2 Timothy', '2Tim', 'New Testament'),
 'Titus': ('Titus', 'Titus', 'New Testament'),
 'Phlm': ('Philemon', 'Phlm', 'New Testament'),
 'Heb': ('Hebrews', 'Heb', 'New Testament'),
 'Jas': ('James', 'Jas', 'New Testament'),
 '1Pet': ('1 Peter', '1Pet', 'New Testament'),
 '2Pet': ('2 Peter', '2Pet', 'New Testament'),
 '1John': ('1 John', '1John', 'New Testament'),
 '2John': ('2 John', '2John', 'New Testament'),
 '3John': ('3 John', '3John', 'New Testament'),
 'Jude': ('Jude', 'Jude', 'New Testament'),
 'Rev': ('Revelation', 'Rev', 'New Testament')}
BOOK_ORDER = list(BOOK_METADATA)


def verify_source_files(directory):
    provenance = json.loads((directory / "provenance.json").read_text())
    for name, info in provenance["files"].items():
        expected = info["sha256"] if isinstance(info, dict) else info
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source checksum mismatch: {directory / name}")
    return provenance


def read_corpus(source_dir):
    verify_source_files(source_dir)
    books = []
    seen = set()
    for book in BOOK_ORDER:
        verses = []
        previous = (0, 0)
        for number, line in enumerate((source_dir / f"{book}.txt").read_text(encoding="utf-8-sig").splitlines(), 1):
            if number == 1:  # Greek book heading; never a corpus token.
                continue
            if not line.strip():
                continue
            match = re.fullmatch(r"(\w+) (\d+):(\d+)\t(.+)", line)
            if not match or match[1] != book:
                raise ValueError(f"Unexpected source row: {book}:{number}")
            chapter, verse = int(match[2]), int(match[3])
            canonical_id = f"{book}.{chapter}.{verse}"
            if canonical_id in seen or (chapter, verse) <= previous:
                raise ValueError(f"Duplicate or unordered verse: {canonical_id}")
            seen.add(canonical_id)
            previous = (chapter, verse)
            text = unicodedata.normalize("NFC", normalize_ws(APPARATUS_RE.sub("", match[4])))
            if not tokenize(text):
                raise ValueError(f"Empty source verse: {canonical_id}")
            verses.append({"osis_id": canonical_id, "chapter": chapter, "verse": verse, "text": text})
        books.append((book, verses))
    return books


def normalize_ws(text):
    return " ".join((text or "").split())


def tokenize(text):
    return TOKEN_RE.findall(unicodedata.normalize("NFC", (text or "").translate(APOSTROPHES).lower()))


def count_sentences(text):
    return len(SENT_RE.findall(text or ""))


def mattr(tokens, window=50):
    """Moving-average type-token ratio: lexical diversity comparable across lengths."""
    if not tokens:
        return 0.0
    if len(tokens) < window:
        return len(set(tokens)) / len(tokens)
    ratios = [
        len(set(tokens[i:i + window])) / window
        for i in range(len(tokens) - window + 1)
    ]
    return sum(ratios) / len(ratios)


def clean_dir_json_files(path):
    path.mkdir(parents=True, exist_ok=True)
    for json_path in path.glob("*.json"):
        json_path.unlink()


def format_location(book_id, book_abbr, chapter=None, verse=None):
    location = f"{int(book_id):02d}.{book_abbr}"
    if chapter is not None:
        location = f"{location}.{int(chapter):03d}"
    if verse is not None:
        location = f"{location}.{int(verse):03d}"
    return location


def get_commentary_columns(metadata):
    columns = []
    for item in metadata.get("commentators", []):
        key = normalize_ws(str(item.get("key", "")))
        if not key:
            continue
        columns.append(
            {
                "key": key,
                "name": normalize_ws(str(item.get("name", key))),
                "label": normalize_ws(str(item.get("label", item.get("name", key)))),
            }
        )
    return columns


def empty_commentary_fields(commentary_columns):
    return {"commentary_interest": 0}


def commentary_fields_for(canonical_id, commentary_verses, commentary_columns):
    fields = empty_commentary_fields(commentary_columns)
    item = commentary_verses.get(canonical_id) or {}
    try:
        fields["commentary_interest"] = int(item.get("total") or 0)
    except (TypeError, ValueError):
        fields["commentary_interest"] = 0
    by_commentator = item.get("by_commentator") if isinstance(item.get("by_commentator"), dict) else {}
    for column in commentary_columns:
        try:
            count = int(by_commentator.get(column["key"]) or 0)
        except (TypeError, ValueError):
            count = 0
        if count:
            fields[f"commentary_{column['key']}"] = count
    return fields


def build(source_path: Path, out_dir: Path):
    project_root = source_path.parent
    books = read_corpus(source_path)

    data_dir = out_dir / "data"
    lines_dir = out_dir / "lines"
    clean_dir_json_files(data_dir)
    clean_dir_json_files(lines_dir)
    commentary_interest = map_commentary(project_root, books, out_dir)
    commentary_metadata = commentary_interest["metadata"]
    commentary_summary = commentary_interest["summary"]
    commentary_verses = commentary_interest["verses"]
    commentary_columns = get_commentary_columns(commentary_metadata)

    plays = []
    chunks = []
    all_lines = []
    tokens = {}
    tokens2 = {}
    tokens3 = {}

    verse_id = 0

    for book_id, (osis_id, verses) in enumerate(books, start=1):
        testament = "New Testament"
        meta = BOOK_METADATA.get(osis_id)
        book_abbr = meta[1] if meta else osis_id
        book_title = meta[0]
        chapter_numbers = sorted({v["chapter"] for v in verses if v.get("chapter") is not None})
        book_total_words = 0
        book_tokens = []  # ordered token stream for book-level MATTR
        book_commentary_fields = empty_commentary_fields(commentary_columns)

        for verse in verses:
            text = verse["text"]
            toks = tokenize(text)
            if not toks:
                continue
            verse_id += 1
            chapter_num = int(verse["chapter"] or 0)
            verse_num = int(verse["verse"] or 0)
            canonical_id = verse["osis_id"] or f"{book_abbr}.{chapter_num}.{verse_num}"
            location = format_location(book_id, book_abbr, chapter_num, verse_num)
            verse_commentary_fields = commentary_fields_for(
                canonical_id, commentary_verses, commentary_columns
            )
            for key, value in verse_commentary_fields.items():
                book_commentary_fields[key] = book_commentary_fields.get(key, 0) + value
            unique_words = len(set(toks))
            total_words = len(toks)
            book_total_words += total_words
            book_tokens.extend(toks)

            chunk_row = {
                "scene_id": verse_id,
                "canonical_id": canonical_id,
                "location": location,
                "play_id": book_id,
                "play_title": book_title,
                "play_abbr": book_abbr,
                "genre": testament,
                "act": chapter_num,
                "scene": verse_num,
                "heading": f"{book_title} {chapter_num}:{verse_num}",
                "total_words": total_words,
                "unique_words": unique_words,
                "num_speeches": 0,
                "num_lines": 1,
                "verse_count": 1,
                "characters_present_count": 0,
                "sentence_count": count_sentences(text),
            }
            chunk_row.update(verse_commentary_fields)
            chunks.append(chunk_row)
            line_row = {
                "play_id": book_id,
                "canonical_id": canonical_id,
                "location": location,
                "act": chapter_num,
                "scene": verse_num,
                "line_num": verse_id,
                "speaker": "",
                "text": text,
            }
            line_row.update(verse_commentary_fields)
            all_lines.append(line_row)

            verse_unigrams = {}
            verse_bigrams = {}
            verse_trigrams = {}
            for tok in toks:
                verse_unigrams[tok] = verse_unigrams.get(tok, 0) + 1
            for idx in range(len(toks) - 1):
                bigram = f"{toks[idx]} {toks[idx + 1]}"
                verse_bigrams[bigram] = verse_bigrams.get(bigram, 0) + 1
            for idx in range(len(toks) - 2):
                trigram = f"{toks[idx]} {toks[idx + 1]} {toks[idx + 2]}"
                verse_trigrams[trigram] = verse_trigrams.get(trigram, 0) + 1

            for term, count in verse_unigrams.items():
                tokens.setdefault(term, []).append([verse_id, count])
            for term, count in verse_bigrams.items():
                tokens2.setdefault(term, []).append([verse_id, count])
            for term, count in verse_trigrams.items():
                tokens3.setdefault(term, []).append([verse_id, count])

        book_row = {
            "play_id": book_id,
            "location": format_location(book_id, book_abbr),
            "title": book_title,
            "abbr": book_abbr,
            "genre": testament,
            "first_performance_year": None,
            "num_acts": len(chapter_numbers),
            "num_scenes": len(verses),
            "num_speeches": 0,
            "total_words": book_total_words,
            "total_lines": len(verses),
            "verse_count": len(verses),
            "mattr_50": round(mattr(book_tokens), 3),
        }
        book_row.update(book_commentary_fields)
        plays.append(book_row)

    # Additive metric fields (char_count, rarity_sum) per verse. The UI derives
    # ratio metrics (mean word length, lexical rarity) at any aggregation level
    # by summing these and dividing by total words.
    corpus_freq = {tok: sum(c for _, c in postings) for tok, postings in tokens.items()}
    corpus_total = sum(corpus_freq.values()) or 1
    tok_rarity = {tok: -math.log10(f / corpus_total) for tok, f in corpus_freq.items()}
    verse_chars = {}
    verse_rarity = {}
    verse_hapax = {}
    for tok, postings in tokens.items():
        length = len(tok)
        rarity = tok_rarity[tok]
        is_hapax = corpus_freq[tok] == 1
        for vid, count in postings:
            verse_chars[vid] = verse_chars.get(vid, 0) + length * count
            verse_rarity[vid] = verse_rarity.get(vid, 0.0) + rarity * count
            if is_hapax:
                verse_hapax[vid] = verse_hapax.get(vid, 0) + count
    for chunk_row in chunks:
        vid = chunk_row["scene_id"]
        chunk_row["char_count"] = verse_chars.get(vid, 0)
        chunk_row["rarity_sum"] = round(verse_rarity.get(vid, 0.0), 3)
        chunk_row["hapax_count"] = verse_hapax.get(vid, 0)

    instance_meta_path = Path(__file__).resolve().parent / "instance-meta.json"
    instance_meta = json.loads(instance_meta_path.read_text(encoding="utf-8")) if instance_meta_path.exists() else {}
    instance_payload = {
        "schema": 1,
        **instance_meta,
        "updated": datetime.date.today().isoformat(),
        "stats": {
            "texts": len(plays),
            "text_label": instance_meta.get("text_label", "books"),
            "segments": len(chunks),
            "segment_label": instance_meta.get("segment_label", "verses"),
            "words": sum(p.get("total_words", 0) for p in plays),
            "distinct_words": len(tokens),
            "commentaries": len(commentary_metadata.get("commentators", [])),
            "comments": int(commentary_summary.get("mapped_comment_count", 0) or 0),
        },
    }
    instance_payload.pop("text_label", None)
    instance_payload.pop("segment_label", None)
    (out_dir / "instance.json").write_text(
        json.dumps(instance_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (data_dir / "plays.json").write_text(
        json.dumps(plays, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "characters.json").write_text("[]", encoding="utf-8")
    (data_dir / "tokens.json").write_text(
        json.dumps(tokens, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "tokens2.json").write_text(
        json.dumps(tokens2, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "tokens3.json").write_text(
        json.dumps(tokens3, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "commentary_interest.json").write_text(
        json.dumps(
            {
                "metadata": commentary_metadata,
                "summary": {
                    **commentary_summary,
                    "source_file": "commentary/provenance.json",
                    "total_commentators": len(commentary_metadata.get("commentators", [])),
                    "verses_with_interest": len(commentary_verses),
                    "total_interest": sum(
                        int((item or {}).get("total") or 0)
                        for item in commentary_verses.values()
                    ),
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "tokens_char.json").write_text("{}", encoding="utf-8")
    (data_dir / "tokens_char2.json").write_text("{}", encoding="utf-8")
    (data_dir / "tokens_char3.json").write_text("{}", encoding="utf-8")
    (data_dir / "character_name_filter_config.json").write_text(
        json.dumps(
            {
                "enabled": False,
                "notes": [
                    "Disabled: this corpus does not yet have a reviewed proper-name list."
                ],
                "global_additions": [],
                "global_removals": [],
                "play_additions": {},
                "play_removals": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (lines_dir / "all_lines.json").write_text(
        json.dumps(all_lines, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "book_count": len(plays),
        "verse_count": len(chunks),
        "line_count": len(all_lines),
    }


if __name__ == "__main__":
    base = Path(__file__).parent
    source_path = base / "source_text"
    out_dir = base / "docs"
    print(f"Building from {source_path} -> {out_dir}")
    result = build(source_path, out_dir)
    print(
        "Done: "
        f"{result['book_count']} books, "
        f"{result['verse_count']} verses, "
        f"{result['line_count']} verse rows written to {out_dir}"
    )
