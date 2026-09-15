# HistoricalChristianFaith commentary snapshot

This instance reuses the New Testament records already curated for KJV and Luther Contabulate, rather than downloading a newer, potentially different collection. The exact KJV donor commit and SHA-256 hashes are in `provenance.json`; upstream collection metadata is in `snapshot/metadata.json`.

`python3 build.py` decompresses the snapshot, applies the explicit SBLGNT passage crosswalk in `scripts/map_commentary.py`, deduplicates merged-verse matches, computes all counts, and writes the lazy per-book details. No sibling checkout or network connection is required. Preserve the snapshot when rebuilding; any future update must deliberately update its provenance and the alignment tests.

Every record retains its stable HCF ID, commentator, approximate date, work, source URL, and HCF passage URL. The display policy is the same as KJV/Luther: historical records keep their source excerpt; records dated after 1930 have only a 24-word identifying preview with reading links. The date cutoff is a display policy, not a legal determination. The upstream compilation's public-domain dedication does not apply to its copyrighted excerpts; see `LICENSE`.

Mapping is by passage overlap. HCF uses mixed historical source material, so identical verse numbers do not guarantee identical wording. Split verses share comments, and absent passages are reported rather than reassigned. `docs/data/commentary_alignment.json` accounts for all 60 source excerpts without a target. Retained comments have the same text and IDs as the source snapshot.

The snapshots are unioned by stable record ID. Twenty-four books have identical records in KJV and Luther. KJV contributes 13 records absent from Luther in Acts/2 Corinthians; Luther contributes the additional Bede comment explicitly numbered 3 John 1:15. Accordingly, the 3John snapshot comes from Luther; the other 26 come from KJV. File-specific provenance is retained.
