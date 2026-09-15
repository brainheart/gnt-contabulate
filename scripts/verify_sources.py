"""Compare the publisher's verse tokens to the independent MorphGNT 6.12 snapshot."""
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def compare():
    directory = ROOT / 'source_text/morphgnt'
    provenance = build.verify_source_files(directory)
    primary = {v['osis_id']: build.tokenize(v['text'])
               for _, verses in build.read_corpus(ROOT / 'source_text') for v in verses}
    secondary = defaultdict(list)
    for path in sorted(directory.glob('*.txt')):
        for line in path.read_text().splitlines():
            ref, pos, parsing, text, word, normalized, lemma = line.split()
            canonical = f'{build.BOOK_ORDER[int(ref[:2]) - 1]}.{int(ref[2:4])}.{int(ref[4:])}'
            secondary[canonical].extend(build.tokenize(word))
    differences = {ref: {'publisher': primary[ref], 'morphgnt': secondary[ref]}
                   for ref in sorted(primary.keys() & secondary.keys()) if primary[ref] != secondary[ref]}
    return {
        'comparison_source': provenance['source'], 'comparison_commit': provenance['commit'],
        'matching_verses': sum(primary[ref] == secondary[ref] for ref in primary.keys() & secondary.keys()),
        'publisher_only_verses': sorted(primary.keys() - secondary.keys()),
        'morphgnt_only_verses': sorted(secondary.keys() - primary.keys()),
        'different_verses': differences,
        'policy': 'Publisher v1.2 is authoritative. MorphGNT is a cross-check, not a source of replacement readings.',
    }


if __name__ == '__main__':
    result = compare()
    (ROOT / 'source_text/comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"Source cross-check: {result['matching_verses']} identical verses; "
          f"{len(result['different_verses'])} differences; {len(result['publisher_only_verses'])} added verses.")
