# Local ingestion: G0–G2

**Forward status — October 25, 2026:** New supported ingestion uses the accepted explicitly selected strict runtime; the current-root historical HOME path remains unchanged. See [current ingestion execution and admission](current-operations.md#ingestion-execution-and-admission). The three-source milestone below is historical and does not represent the accepted 16-document QA publications.

Milestone 2 implements local source validation/acquisition, PDF/MDX parsing, structural records, provenance, transformation audit and explicit HOLD/review. It does not implement chunking or any downstream RAG stage.

## Commands and private artifacts

```sh
uv run --locked rag-hub verify-sources
uv run --locked rag-hub ingest --local-use-basis "User-authorized private local processing; redistribution not cleared"
```

The registry `config/sources.json` contains public metadata and exact historical expected hashes/bytes, not source text. Inputs reside in gitignored `data/raw/`. Verification rejects missing or changed inputs. It also rejects traversal, symlinks, repaired/encrypted PDFs and unexpected PDF page counts. An explicit local-use basis is required before snapshotting; it is the operator's authorization record, not an automatic legal determination. No source is downloaded and no URL or embedded code is executed.

Original capture timestamps are unknown and remain null; source dates or file modification times are not fabricated as acquisition timestamps. Local snapshots are copied to `data/snapshots/<full-sha256>/`; reruns reject modified existing snapshots. Collection identity derives from source IDs and full hashes.

Each versioned run under `data/ingestion/<run-id>/` contains:

| File | Purpose |
|---|---|
| manifest.json | Source hashes, immutable paths, original/canonical URLs, versions and local-use basis |
| blocks.jsonl | Ordered typed content, original source locators, content hashes, code/tab and parser metadata |
| sections.jsonl | Atomic block-level sections with heading ancestry, source lineage, normalized hashes and review status |
| audit.jsonl | Before/after or removed content and reasons, linked to original blocks |
| sidecars.jsonl | Unverified table/math/image/PDF regions with visual references and nearby context pointers; unknown structured cells/settings remain null/empty |
| holds.jsonl | All sections not specifically approved |
| reviews.json | Exact-section review receipts used for this run |
| report.json | Counts, implementation/dependency fingerprints and limitations |

The run identity includes source registry, implementation and dependency versions, local-use basis and review receipts. Identical runs reproduce the same artifact bytes and refuse changed existing output. This is application-level immutability, not filesystem write protection. All data outputs are gitignored.

## Parsing and normalization

PyMuPDF extracts native PDF blocks with page/bounding-box locators and possible heading/table/math classifications. Embedded images receive visual-review placeholders. Native reading order is retained and explicitly unreviewed; coordinate sorting alone is not claimed to solve multi-column layout. Single-letter/symbol/control-glyph fragments remain held. No OCR, equation reconstruction or automatic numerical-table reconstruction is provided.

Markdown processing combines markdown-it-py for standard Markdown with an explicit state machine for fenced code and `Tabs`/`Tab`/`CodeGroup`. It preserves code indentation relative to its source container, language, provider labels and alternative labels. Code comments cannot become headings; MDX markup inside fences remains data. Unsupported MDX/HTML and unparsed nonblank lines are preserved and held. This is a bounded grammar for these snapshots, not a complete MDX/JavaScript parser. Links remain in original Markdown; relative targets resolve against the manifest URL when a future consumer renders them.

Normalization emits one atomic parsed block per section while retaining heading/page ancestry. This avoids silently joining math, table rows, code alternatives or adjacent unreviewed prose. It is not the later structure-aware chunker. Code receives canonical fences with code bodies unchanged except removal of MDX container indentation. Exact known C06 print-margin headers/footers and MDX container markup are removed with an audit; remaining ambiguous material stays present and held. The source-specific rules deliberately avoid generic deduplication of valid experimental variants.

Nearby table/context pointers are aids for source review, not proof that every column, setting and row is associated correctly. In this milestone all tables/equations remain HOLD; structured reconstruction needs a later reviewed extraction change. The three historically checked C06 rows were visually inspected again but are not approved by this parser. No row values are guessed into sidecar cells.

## Review boundary

All normalized sections start unapproved. Optional private review receipts authorize only exact section/source hashes:

```sh
uv run --locked rag-hub ingest --local-use-basis "User-authorized private local processing; redistribution not cleared" --reviews workspace/milestone2-review/reviews.json
```

A receipt records `section_id`, `normalized_sha256`, `raw_sha256`, `reviewer`, and `evidence_note`. Missing/stale/duplicate receipts fail closed. Review application accepts only prose/code/headings without unresolved extraction issues (PDF reading-order warning may be cleared by explicit visual comparison). Unsafe tables/equations, corrupted glyphs, unknown MDX and incomplete fences cannot be approved by this path. Review receipts are local operator attestations, not cryptographically signed credentials. Future indexing must revalidate them and source integrity; an approval field alone is insufficient.

The current private report has 9 narrowly approved samples. The rest remain HOLD, including neighboring formulas/tables and unreviewed text. This is partial source QA, not approval of three entire documents or a corpus ready for indexing.

## Dependency basis

The engineering specification proposed PyMuPDF; this milestone uses its standard extraction/rendering API and markdown-it-py. Official references: [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html), [markdown-it-py token API](https://markdown-it-py.readthedocs.io/en/latest/using.html), and [PyMuPDF AGPL/commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright). No project release license or public deployment is selected here; release licensing remains a separate decision.
