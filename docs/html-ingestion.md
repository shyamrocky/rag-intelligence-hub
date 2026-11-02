# Fixed HTML corpus ingestion

The HTML-only adapter owns C03, C05, C07–C13, C15 and C16 from the original
16-source inventory. C04 and the four PDFs stay in their existing workstreams.
No HTML dependency, shared schema, admission rule, application default or PDF
release was changed. This is ingestion implementation, not owner acceptance.

Run from the repository root with the locked Python 3.12 environment:

```sh
uv run --locked python -m rag_hub.html_acquire
uv run --locked python -m rag_hub.html_corpus
uv run --locked python -m rag_hub.html_corpus --verify-offline
```

Acquisition fetches only the eleven pinned URLs, accepts HTML, limits responses
to 15 MiB and redirects to the same publisher, and records failures separately.
It reuses hash-verified receipts and immutable raw files. Parsing, rebuilding and
verification need no network. A changed source or existing artifact is rejected;
a future refresh requires an explicitly versioned destination, not overwrite.

Existing `SourceManifest`, `ParsedBlock`, `Section`, normalization and source-span
consumers are reused. The HTML adapter retains specialized HTML metadata that
the MDX-specific metadata-removal rule would otherwise drop. Every Section is
HOLD. The authoritative QA validator rejects unsupported HTML; no admission or
readiness workflow is enabled here.

`data/manifests/html/corpus-manifest.json` binds each raw receipt, hash-addressed
snapshot, parsed artifact, normalized artifact and consistency report. Parsed
and normalized records retain DOM paths, decoded-source character spans (Unicode,
end exclusive), source-fragment hashes and a semantic evidence tree. Inline code,
links, nested lists, table cells/spans/headers, image references and captions stay
in that tree. Code bodies preserve whitespace; non-code HTML ASCII whitespace is
collapsed without changing spelling, punctuation or Unicode normalization.

Load persisted content offline:

```python
from pathlib import Path
from rag_hub.html_corpus import load_corpus

# Safe default: [] while no HTML content has authoritative admission receipts.
admitted = load_corpus(Path.cwd())
# Evidence review only; these records are not permission to index.
review = load_corpus(Path.cwd(), admitted_only=False, include_structure=True)
```

The structured view includes Section objects, evidence trees, source locators,
context metadata and document containers. A future chunker must respect these
structures and the authoritative QA boundary. Flattened Section text alone is
insufficient for nested lists, tables, alternative tabs or image semantics.
Tab labels and panel boundaries are preserved; label-to-panel ownership remains
unverified where the captured HTML lacks explicit ARIA bindings. No chunker is
implemented or executed by this work.

Private results, candidate passages and provisional DEV questions are under
`data/validation/html/v1/`. Independent human acceptance remains pending. Raw and
derived third-party content remains gitignored and uncleared for redistribution.

## Metadata correction and engineering closure

C13 publisher metadata is corrected to Pinecone from the pinned page's
`og:site_name = Pinecone Docs`. The existing deterministic builder reproduced all
eleven sources; all raw, snapshot, acquisition, parsed and normalized bytes stayed
identical. Only the C13 SourceManifest, config and current corpus manifest changed.
Original metadata and the original delivery receipt are archived under
`data/manifests/html/history/c13-metadata-before/`.

The current manifest remains `data/manifests/html/corpus-manifest.json`.
The consolidated closure evidence is
`data/validation/html-markdown/v1/COMPLETION_REPORT.md`.
Earlier v1 reports describe their original manifest identity and remain historical.
Engineering is complete for 11 acquired, parsed and persisted documents / 457
Sections. Content qualification is pending: all 457 stay HOLD with no retrieval
admission. C04 has its separate [Markdown store](markdown-persistence.md).
