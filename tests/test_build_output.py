"""Corpus integrity, independent-source checks, and commentary join regression tests."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import unicodedata
import unittest

import build
from scripts.verify_sources import compare

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text())


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.books = read('docs/data/plays.json')
        cls.chunks = read('docs/data/chunks.json')
        cls.lines = read('docs/lines/all_lines.json')
        cls.tokens = read('docs/data/tokens.json')

    def test_source_checksums_and_independent_comparison(self):
        build.verify_source_files(ROOT / 'source_text')
        comparison = compare()
        self.assertEqual(comparison, read('source_text/comparison.json'))
        self.assertEqual(comparison['matching_verses'], 7910)
        self.assertEqual(len(comparison['different_verses']), 17)
        self.assertEqual(set(comparison['publisher_only_verses']),
                         {'John.7.53'} | {f'John.8.{v}' for v in range(1, 12)})
        self.assertEqual(comparison['morphgnt_only_verses'], [])

    def test_corpus_totals_and_hierarchy(self):
        self.assertEqual(len(self.books), 27)
        self.assertEqual(sum(b['num_acts'] for b in self.books), 260)
        self.assertEqual(len(self.chunks), 7939)
        self.assertEqual(sum(b['total_words'] for b in self.books), 137741)
        self.assertEqual(len(self.tokens), 18616)
        self.assertEqual({b['genre'] for b in self.books}, {'New Testament'})
        self.assertEqual(self.books[0]['location'], '01.Matt')
        self.assertEqual(self.books[-1]['location'], '27.Rev')
        self.assertEqual([r['canonical_id'] for r in self.chunks], [r['canonical_id'] for r in self.lines])
        self.assertEqual(len({r['scene_id'] for r in self.chunks}), 7939)
        self.assertEqual(len({r['canonical_id'] for r in self.chunks}), 7939)
        for chunk, line in zip(self.chunks, self.lines):
            self.assertIn(chunk['play_id'], range(1, 28))
            self.assertEqual(chunk['scene_id'], line['line_num'])
            self.assertEqual(chunk['total_words'], len(build.tokenize(line['text'])))
            self.assertEqual(chunk['verse_count'], 1)

    def test_text_boundaries_editorial_brackets_and_omissions(self):
        lines = {r['canonical_id']: r['text'] for r in self.lines}
        self.assertEqual(self.lines[0]['canonical_id'], 'Matt.1.1')
        self.assertTrue(lines['Matt.1.1'].startswith('Βίβλος γενέσεως'))
        self.assertEqual(self.lines[-1]['canonical_id'], 'Rev.22.21')
        self.assertTrue(lines['Rev.22.21'].startswith('Ἡ χάρις'))
        self.assertEqual(lines['John.1.1'], 'Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.')
        self.assertTrue(lines['John.7.53'].startswith('⟦'))
        self.assertIn('⟧', lines['John.8.11'])
        self.assertIn('⟦Πάντα', lines['Mark.16.8'])
        self.assertTrue(lines['Mark.16.9'].startswith('⟦'))
        self.assertTrue(lines['Mark.16.20'].endswith('⟧'))
        self.assertNotIn('Matt.17.21', lines)
        self.assertNotIn('Rom.16.25', lines)
        for text in lines.values():
            self.assertEqual(text, unicodedata.normalize('NFC', text))
            self.assertNotRegex(text, r'[⸀⸁⸂⸃⸄⸅0-9]')
        self.assertNotIn('ΚΑΤΑ ΜΑΘΘΑΙΟΝ', ' '.join(lines.values()))

    def test_unicode_tokens_and_greek_sentence_punctuation(self):
        self.assertEqual(build.tokenize('Ἐν ἀρχῇ λόγος διʼ αὐτοῦ'), ['ἐν', 'ἀρχῇ', 'λόγος', 'δι', 'αὐτοῦ'])
        self.assertEqual(build.tokenize('Ἐν ἀρχῇ'), build.tokenize(unicodedata.normalize('NFD', 'Ἐν ἀρχῇ')))
        self.assertEqual(build.tokenize('ᾧ ᾷ'), ['ᾧ', 'ᾷ'])
        self.assertEqual(build.count_sentences('τί; ναί. τί; λόγος·'), 3)

    def test_browser_and_python_tokenizers_agree_on_entire_corpus(self):
        code = """
        global.window = global;
        require('./docs/js/utils.js');
        const fs = require('fs'); const crypto = require('crypto');
        const lines = JSON.parse(fs.readFileSync('./docs/lines/all_lines.json'));
        const stream = lines.map(l => tokenizeLineText(l.text).join(' ')).join('\\n');
        process.stdout.write(crypto.createHash('sha256').update(stream).digest('hex'));
        """
        actual = subprocess.check_output(['node', '-e', code], cwd=ROOT, text=True)
        stream = '\n'.join(' '.join(build.tokenize(row['text'])) for row in self.lines)
        self.assertEqual(actual, hashlib.sha256(stream.encode()).hexdigest())

    def test_postings_totals_do_not_cross_verse_boundaries(self):
        by_id = {r['scene_id']: r for r in self.chunks}
        for n, filename in [(1, 'tokens'), (2, 'tokens2'), (3, 'tokens3')]:
            index = read(f'docs/data/{filename}.json')
            totals = Counter()
            for term, postings in index.items():
                self.assertEqual(len(term.split()), n)
                for scene_id, count in postings:
                    self.assertIn(scene_id, by_id)
                    self.assertGreater(count, 0)
                    totals[scene_id] += count
            for scene_id, chunk in by_id.items():
                self.assertEqual(totals[scene_id], max(0, chunk['total_words'] - n + 1))

    def test_metrics_metadata_and_disabled_capabilities(self):
        instance = read('docs/instance.json')
        self.assertEqual(instance['id'], 'gnt')
        self.assertEqual(instance['stats']['comments'], 58620)
        self.assertEqual(instance['stats']['commentaries'], 242)
        self.assertEqual(sum(c['hapax_count'] for c in self.chunks),
                         sum(sum(count for _, count in p) == 1 for p in self.tokens.values()))
        for chunk in self.chunks:
            self.assertGreater(chunk['char_count'], 0)
            self.assertGreater(chunk['rarity_sum'], 0)
        self.assertEqual(read('docs/data/characters.json'), [])
        self.assertFalse(read('docs/data/character_name_filter_config.json')['enabled'])


class CommentaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = {r['canonical_id']: r for r in read('docs/data/chunks.json')}
        cls.details = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'docs/commentary').glob('*.json')}
        cls.source = {p.name.split('.')[0]: json.loads(gzip.decompress(p.read_bytes()))
                      for p in (ROOT / 'commentary/snapshot').glob('*.gz')}

    def ids_for(self, ref, source=False):
        book = ref.split('.')[0]
        payload = (self.source if source else self.details)[book]
        return {payload['comments'][idx][2] for idx in payload['verses'].get(ref, [])}

    def test_every_count_matches_readable_records_and_metadata(self):
        author_totals = Counter()
        ids = set()
        interest = read('docs/data/commentary_interest.json')
        self.assertEqual(len(self.details), 27)
        for book, payload in self.details.items():
            source_ids = {row[2] for row in self.source[book]['comments']}
            self.assertTrue({r[2] for r in payload['comments']} <= source_ids)
            for record in payload['comments']:
                self.assertNotIn(record[2], ids)
                ids.add(record[2])
                self.assertTrue(record[10].startswith('https://historicalchristian.faith/'))
                if record[9]:
                    self.assertLessEqual(len(record[8].split()), 24)
            for ref, indexes in payload['verses'].items():
                self.assertIn(ref, self.chunks)
                self.assertEqual(len(indexes), len(set(indexes)))
                counts = Counter(payload['authors'][payload['comments'][idx][0]]['key'] for idx in indexes)
                author_totals.update(counts)
                self.assertEqual(len(indexes), self.chunks[ref]['commentary_interest'])
                for key, count in counts.items():
                    self.assertEqual(self.chunks[ref]['commentary_' + key], count)
        self.assertEqual(len(ids), 58620)
        self.assertEqual({a['key']: a['reference_count'] for a in interest['metadata']['commentators']}, author_totals)
        self.assertEqual(sum(c['commentary_interest'] for c in self.chunks.values()), interest['summary']['total_interest'])

    def test_unmodified_hotspot_uses_same_comment_ids(self):
        for ref in ['John.1.1', 'Matt.5.3', 'Rom.8.28']:
            self.assertEqual(self.ids_for(ref), self.ids_for(ref, source=True))
            self.assertTrue(self.ids_for(ref))
        self.assertGreater(self.chunks['John.1.1']['commentary_augustine'], 0)
        self.assertGreater(self.chunks['John.1.1']['commentary_theophylact_of_ohrid'], 0)

    def test_crosswalk_merges_splits_and_deduplicates(self):
        self.assertEqual(self.ids_for('Acts.19.40'), self.ids_for('Acts.19.40', True) | self.ids_for('Acts.19.41', True))
        self.assertEqual(self.ids_for('2Cor.13.12'), self.ids_for('2Cor.13.12', True) | self.ids_for('2Cor.13.13', True))
        self.assertEqual(self.ids_for('2Cor.13.13'), self.ids_for('2Cor.13.14', True))
        self.assertEqual(self.ids_for('3John.1.15'), self.ids_for('3John.1.14', True) | self.ids_for('3John.1.15', True))
        self.assertEqual(self.ids_for('Rev.12.18'), self.ids_for('Rev.13.1', True))
        self.assertEqual(self.ids_for('Rev.13.1'), self.ids_for('Rev.13.1', True))

    def test_unmapped_source_comments_are_accounted_for(self):
        audit = read('docs/data/commentary_alignment.json')
        self.assertEqual(audit['unmapped_comment_count'], 60)
        for book, original in self.source.items():
            retained = {r[2] for r in self.details[book]['comments']}
            omitted = set(audit['unmapped_comment_ids_by_book'][book])
            self.assertFalse(retained & omitted)
            self.assertEqual(retained | omitted, {r[2] for r in original['comments']})


if __name__ == '__main__':
    unittest.main()
