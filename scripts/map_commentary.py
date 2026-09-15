"""Rebuild GNT commentary from the same pinned HCF snapshot used by KJV/Luther."""
from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import json

# Keys are SBLGNT references, values are the KJV/HCF passage coordinates.
# Split references intentionally indicate passage overlap, not clause alignment.
CROSSWALK = {
    'Acts.19.40': ['Acts.19.40', 'Acts.19.41'],
    '2Cor.13.12': ['2Cor.13.12', '2Cor.13.13'],
    '2Cor.13.13': ['2Cor.13.14'],
    '3John.1.14': ['3John.1.14'],
    '3John.1.15': ['3John.1.14', '3John.1.15'],
    'Rev.12.18': ['Rev.13.1'],
    'Rev.13.1': ['Rev.13.1'],
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def map_commentary(project_root, books, out_dir):
    source_dir = project_root / 'commentary/snapshot'
    provenance = json.loads((project_root / 'commentary/provenance.json').read_text())
    for name, expected in provenance['files'].items():
        if hashlib.sha256((source_dir / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Commentary checksum mismatch: {name}')
    metadata = json.loads((source_dir / 'metadata.json').read_text())
    author_counts = Counter()
    verse_counts = {}
    summary = Counter()
    unmapped = {}
    source_verses_without_target = []
    unique_ids = set()
    detail_dir = out_dir / 'commentary'
    detail_dir.mkdir(parents=True, exist_ok=True)
    for path in detail_dir.glob('*.json'):
        path.unlink()
    for book, verses in books:
        source = json.loads(gzip.decompress((source_dir / f'{book}.json.gz').read_bytes()))
        mapped = {}
        used = set()
        targeted_source_ids = set()
        for verse in verses:
            canonical_id = verse['osis_id']
            refs = CROSSWALK.get(canonical_id, [canonical_id])
            targeted_source_ids.update(refs)
            # The same excerpt can cover both halves of a merged SBL verse.
            indexes = sorted({idx for ref in refs for idx in source['verses'].get(ref, [])})
            if not indexes:
                continue
            mapped[canonical_id] = indexes
            used.update(indexes)
            counts = Counter(source['authors'][source['comments'][idx][0]]['key'] for idx in indexes)
            author_counts.update(counts)
            verse_counts[canonical_id] = {'total': len(indexes), 'by_commentator': dict(counts)}
        old_to_new = {old: new for new, old in enumerate(sorted(used))}
        records = [source['comments'][idx] for idx in sorted(used)]
        for record in records:
            if record[2] in unique_ids:
                raise ValueError(f'Duplicate HCF record ID: {record[2]}')
            unique_ids.add(record[2])
            summary['mapped_comment_count'] += 1
            summary['restricted_preview_comment_count' if record[9] else 'full_text_comment_count'] += 1
            if source['works'][record[1]][1]:
                summary['comments_with_source_url'] += 1
        unmapped[book] = [record[2] for idx, record in enumerate(source['comments']) if idx not in used]
        source_verses_without_target.extend(sorted(set(source['verses']) - targeted_source_ids))
        write_json(detail_dir / f'{book}.json', {
            'book': book, 'authors': source['authors'], 'works': source['works'],
            'comments': records,
            'verses': {key: [old_to_new[idx] for idx in indexes] for key, indexes in mapped.items()},
        })
    metadata['commentators'] = [{**author, 'reference_count': author_counts[author['key']]}
                               for author in metadata['commentators'] if author_counts[author['key']]]
    metadata['detail_books'] = [book for book, _ in books]
    metadata['detail_path_template'] = 'commentary/{book}.json'
    metadata['count_meaning'] = 'Commentary excerpts overlapping the SBLGNT verse, using an explicit KJV/HCF-to-SBLGNT passage crosswalk; merged references are deduplicated.'
    metadata['alignment_note'] = 'Source passage labels and links retain HCF numbering. Split verses share passage-level comments; this is not a clause-by-clause or edition-specific textual alignment.'
    metadata['snapshot_provenance'] = provenance['snapshot_from']
    metadata['snapshot_source_overrides'] = provenance.get('file_source_overrides', {})
    summary['verses_with_interest'] = len(verse_counts)
    summary['total_interest'] = sum(row['total'] for row in verse_counts.values())
    write_json(out_dir / 'data/commentary_alignment.json', {
        'crosswalk': CROSSWALK,
        'source_verses_without_target': source_verses_without_target,
        'unmapped_comment_ids_by_book': unmapped,
        'unmapped_comment_count': sum(map(len, unmapped.values())),
        'note': metadata['alignment_note'],
    })
    return {'metadata': metadata, 'summary': dict(summary), 'verses': verse_counts}
