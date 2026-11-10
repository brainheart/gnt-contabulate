# Greek New Testament Contabulate

Independent static instance. Run `python3 build.py`, `python3 -m unittest discover -v`, and `npm test`. Source snapshots are pinned and checked by SHA-256. Generated files in `docs/data`, `docs/lines`, and `docs/commentary` must be rebuilt, not edited. Preserve canonical verse IDs and the explicit commentary crosswalk. `docs/data/glossary.json` (English glosses and lemmas) is a display-only reading aid built by `scripts/glossary.py`; the page must work without it, and `docs/js/glossary.js` is shared verbatim with the other non-English instances.
