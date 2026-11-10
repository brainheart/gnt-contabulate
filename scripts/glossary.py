"""English reading aids for the Greek text: a lemma and gloss for every word.

Lemmas come from the MorphGNT SBLGNT snapshot already kept in this repository
for verification; glosses come from the MorphGNT morphological lexicon, whose
`gloss` field is the short gloss of Dodson's public-domain lexicon. MorphGNT
analyses the same edition this instance shows, so words line up one to one in
all but a few verses; those are matched word by word, and words MorphGNT does
not have (John 7:53-8:11) take the lemma their written form has elsewhere.
"""
import difflib
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

LEXICON_COMMIT = "0dca2af89f413cbb24f617ddbdc347e9d798ddf3"
LEXICON_URL = f"https://raw.githubusercontent.com/morphgnt/morphological-lexicon/{LEXICON_COMMIT}/lexemes.yaml"
LEXICON_SHA256 = "16e8c79e1cfd57bde6d2917e7cc9e1f173bac92d11eac2cdb06ef0dcc7dab0c8"
POS_LABELS = {
    "N-": "noun", "V-": "verb", "A-": "adjective", "D-": "adverb", "P-": "preposition",
    "C-": "conjunction", "RA": "article", "RP": "pronoun", "RR": "pronoun", "RD": "pronoun",
    "RI": "pronoun", "X-": "particle", "I-": "interjection",
}
# Words too common in glosses to say what a lemma means. They are indexed
# only for lemmas whose glosses contain nothing else.
STOP_WORDS = frozenset("""
a an the and or of to in on for with by from at as is are was were be been it its he she they them
their his her you your we our us i my me him who whom which that this those these then so but not
no will would shall should may might can could do does did have has had o if when what there than
am
""".split())


def parse_lexemes(path):
    """The lexicon is flat YAML: a lemma line, then indented `key: value` lines."""
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != LEXICON_SHA256:
        raise ValueError(f"Source checksum mismatch: {path}")
    lexemes = {}
    current = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            current = lexemes.setdefault(line.rstrip().rstrip(":").strip("'\""), {})
        elif current is not None and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key] = value.strip().strip("'\"")
    return lexemes


def load_morphgnt(directory, book_order, tokenize):
    """Words by canonical verse id: [(token, lemma, part of speech), ...]."""
    verses = defaultdict(list)
    for path in sorted(Path(directory).glob("*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            ref, pos, _parsing, _text, word, _normalized, lemma = line.split()
            canonical = f"{book_order[int(ref[:2]) - 1]}.{int(ref[2:4])}.{int(ref[4:])}"
            for token in tokenize(word):
                verses[canonical].append((token, lemma, pos))
    return verses


def annotate(lines, morphgnt, tokenize):
    """One (lemma, pos) or None per displayed word, plus statistics."""
    notes = {}
    stats = Counter()
    for row in lines:
        tokens = tokenize(row["text"])
        words = morphgnt.get(row["canonical_id"], [])
        out = [None] * len(tokens)
        if [w[0] for w in words] == tokens:
            out = [(lemma, pos) for _, lemma, pos in words]
            stats["verses_identical"] += 1
        elif words:
            stats["verses_matched_word_by_word"] += 1
            matcher = difflib.SequenceMatcher(a=[w[0] for w in words], b=tokens, autojunk=False)
            for block in matcher.get_matching_blocks():
                for offset in range(block.size):
                    _, lemma, pos = words[block.a + offset]
                    out[block.b + offset] = (lemma, pos)
        else:
            stats["verses_without_morphology"] += 1
        notes[row["canonical_id"]] = out
        stats["words"] += len(tokens)
    # Words without an analysis take the lemma their form most often has.
    by_form = defaultdict(Counter)
    for row in lines:
        for token, note in zip(tokenize(row["text"]), notes[row["canonical_id"]]):
            if note:
                by_form[token][note] += 1
    for row in lines:
        out = notes[row["canonical_id"]]
        for i, token in enumerate(tokenize(row["text"])):
            if out[i] is None:
                if by_form[token]:
                    out[i] = by_form[token].most_common(1)[0][0]
                    stats["words_lemma_by_form"] += 1
                else:
                    stats["words_without_lemma"] += 1
    return notes, stats


def gloss_words(gloss):
    """Lower-case content words of a gloss; parenthesized notes are left out
    when anything else remains."""
    plain = re.sub(r"\([^)]*\)", " ", gloss)
    words = [w for w in re.findall(r"[a-z]+(?:'[a-z]+)?", plain.lower()) if w not in STOP_WORDS]
    return words or re.findall(r"[a-z]+(?:'[a-z]+)?", gloss.lower())


def word_index(gloss, count, limit=14):
    """English words of a gloss weighted by the lemma's frequency; words of
    the first sense count in full, later senses half."""
    weights = {}
    for position, sense in enumerate(re.split(r"[,;]", gloss)):
        for word in gloss_words(sense):
            weight = max(1, count if position == 0 else count // 2)
            weights[word] = max(weights.get(word, 0), weight)
    return [[w, c] for w, c in sorted(weights.items(), key=lambda wc: (-wc[1], wc[0]))[:limit]]


def build_glossary(lines, morphgnt_dir, lexemes_path, book_order, tokenize):
    lexemes = parse_lexemes(lexemes_path)
    notes, stats = annotate(lines, load_morphgnt(morphgnt_dir, book_order, tokenize), tokenize)
    form_total = Counter()
    form_lemmas = defaultdict(Counter)
    lemma_forms = defaultdict(Counter)
    lemma_pos = defaultdict(Counter)
    for row in lines:
        for token, note in zip(tokenize(row["text"]), notes[row["canonical_id"]]):
            form_total[token] += 1
            if note:
                lemma, pos = note
                form_lemmas[token][lemma] += 1
                lemma_forms[lemma][token] += 1
                lemma_pos[lemma][pos] += 1
    ordered = sorted(lemma_forms, key=lambda k: (-sum(lemma_forms[k].values()), k))
    index = {lemma: i for i, lemma in enumerate(ordered)}
    lemmas = []
    for lemma in ordered:
        count = sum(lemma_forms[lemma].values())
        gloss = lexemes.get(lemma, {}).get("gloss", "")
        if not gloss:
            stats["lemmas_without_gloss"] += 1
        lemmas.append({
            "lemma": lemma,
            "pos": POS_LABELS.get(lemma_pos[lemma].most_common(1)[0][0], "particle"),
            "n": count,
            "def": gloss,
            "en": [],
            "w": word_index(gloss, count) if gloss else [],
            "forms": [[f, c] for f, c in sorted(lemma_forms[lemma].items(), key=lambda fc: (-fc[1], fc[0]))],
        })
    forms = {}
    for form in sorted(form_total):
        related = [index[k] for k, _ in form_lemmas[form].most_common(3)]
        glosses = [lemmas[i]["def"] for i in related[:2] if lemmas[i]["def"]]
        forms[form] = [form_total[form], glosses, related]
    stats["lemmas"] = len(lemmas)
    stats["forms"] = len(forms)
    return {"forms": forms, "lemmas": lemmas}, stats
