# C04 Markdown/MDX persistence

C04 reuses the existing canonical `mdx-v1` extraction and normalization. Its
original 34,709-byte source, snapshot ID, 215 block IDs and 158 Section IDs remain
unchanged. No parser, shared contract or QA policy was changed. Supplemental
Markdown syntax and MDX boundaries preserve structure for offline consumers.

The private canonical store is:

- `data/parsed/markdown/C04.json`: original SourceManifest and blocks, byte/character
  offsets, line ranges, Markdown token hierarchy and MDX container relationships.
- `data/normalized/markdown/C04.json`: unchanged original Sections, audited
  transformations and exact existing historical QA decisions.
- `data/manifests/markdown/corpus-manifest.json`: source, historical evidence,
  implementation and artifact hashes.
- `data/validation/markdown/v1/C04.json`: bounded engineering consistency results.

Load from the repository root, without network access or Markdown parsing:

```python
from pathlib import Path
from rag_hub.markdown_corpus import load_corpus

corpus = load_corpus(Path.cwd())  # 40 already eligible historical code records
review = load_corpus(Path.cwd(), admitted_only=False)  # all 158 existing Sections
for row in corpus["records"]:
    section = row["section"]  # existing Section model; never rewritten
    decision = row["historical_qa_decision"]  # effective existing QA decision
    source = row["source"]
    citation = (source.canonical_url, section.heading_path, section.locators)
```

**Use `historical_qa_decision` for effective historical status.** Original Section
fields reflect the earlier ingestion snapshot (four original approvals); the
later authoritative ledger retains two and adds 38 automatic code decisions.
The loader projects that existing ledger without promoting or demoting anything.
It verifies exact source/normalized identities and saved decision equality.
This is not a new admission engine, source-readiness result or chunker.

The store preserves 75 code Sections, 66 prose Sections and 17 headings. There
are 40 historically eligible code Sections and 118 HOLD Sections. Prose/context
cohort restrictions, two unsupported footer MDX/HTML regions and the unparsed
thematic break remain unresolved. Component code and source examples are never
executed. Independent whole-document content correctness is not established.

For explicit offline verification:

```sh
uv run --locked python -m rag_hub.markdown_corpus --verify-offline
```

`python -m rag_hub.markdown_corpus` deterministically materializes the view from
the pinned existing ingestion and QA records; changed existing outputs fail
closed. Ordinary downstream loading does not run this build. All content stays
private under `data/`; original bytes and historical evidence stay in place.
