# M4 local embedding baseline

**Owner acceptance — October 25, 2026:** M4 is OWNER_ACCEPTED / CLOSED for the durable engineering baseline: 553 units, 992 chunks and 992 × 384 vectors, with verified numerical reuse. The current selector is `config/embedding-artifacts-m4-durable-v1.json`; manifest SHA-256 `9b304b4b8be9eb4aa3af22ea3d5fd2625a9b097951564077369943ee239c6ac6`. Use [current operations](current-operations.md) for the supported durable reader. BGE remains provisional; retrieval evaluation is deferred to M9. M5 remains unauthorized. The implementation-time input and acceptance status below are historical, not forward selectors.

The owner authorized **M4 only**, selecting `BAAI/bge-small-en-v1.5` as a
**provisional baseline**, not a proven retrieval-quality winner. M3 remains
owner accepted. M4 implementation requires separate owner acceptance after its
engineering verification. Recall@K/MRR and comparative model selection belong
to M9. M5 storage, lexical indexes, retrieval and generation are not implemented.

## Input and authority

The only input is the accepted explicit catalog
`config/retrieval-chunks-m3-c14-scope-v2.json`, manifest
`f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c`:
992 chunks, 553 verified units, 16 documents. Load it using
`load_c14_verified_corpus` and `QualifiedChunkCatalog`, as documented in the
[accepted handoff](M3_TO_M4_HANDOFF.md). Original Chunk IDs remain unchanged.

`embedding_inputs.embedding_input` projects each **live reader view** into the
exact accepted source-heading prefix and source slice, or its approved
search-only representation. It never flattens a verified parent envelope.
QA observations, warnings, qualifications, context-only body material and audit
records are not embedded as publisher knowledge. Literal approved headings
remain context prefixes exactly as accepted in M3.

The projection helper is not an authorization boundary for arbitrary
dictionaries. The generator gets its input from the original live reader and
checks it against the M3 closure input hashes. Full parent rehydration,
qualifications, citation and publication verification remain mandatory before
evidence use. Neither a vector nor its saved input text grants evidence access.
No raw-normalized fallback or new QA engine exists.

## Model-selection criteria

The baseline favors local CPU execution, an English corpus, modest artifact size,
compatibility with the already accepted BGE tokenizer/chunk budgets and an
explicit pinned license/runtime. Keeping that tokenizer avoids changing two
variables at once. Those criteria justify an engineering starting point; they do
not establish domain Recall@K, MRR, robustness to specialized notation or an
optimal embedding model. No alternative model was installed or scored. M9 owns
comparative retrieval evaluation against independently reviewed relevance labels.

## Pinned model and runtime

The model revision remains the M2 tokenizer revision:
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
`config/m4-embedding-baseline-v1.json` binds local safetensors weights, all
tokenizer/configuration assets, implementation files and the isolated lockfile.
Weights SHA-256:
`3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad`.
Acquisition checks the official revision's Git blob or LFS object hash and size.
The snapshot is private under `data/models/bge-small-en-v1.5/<revision>/`.

The isolated `tools/embeddings/pyproject.toml` and `uv.lock` pin Sentence
Transformers **5.1.2**, Transformers **4.57.1**, torch **2.8.0**, NumPy **2.2.6**,
safetensors **0.6.2**, tokenizers **0.22.2** and the accepted LangChain splitter
runtime. Root, dashboard and chunking dependencies are unchanged. Heavy packages
are imported only by optional embedding operations.

Encoding behavior is explicit:

- CPU float32, evaluation mode, deterministic algorithms, seed 0, one torch
  compute thread, eager attention, batches of 16.
- CLS pooling, 384 output dimensions and L2 normalization. The pinned model
  includes a Normalize module; encoding also requests normalization explicitly.
  A direct normalized first-token calculation checks this configuration.
- Empty document prompt; no query encoding is implemented. The loaded runtime's
  empty query/document prompt entries do not prepend content.
- 384 total input tokens normally; the four accepted selective 512-token
  exceptions remain 385/474/485/507 actual tokens. Budgets include headings,
  delimiters, CLS and SEP. Any over-budget input fails before inference.
- Sentence Transformers' actual tokenization, including its whitespace/case
  preprocessing and batch padding, must match the accepted M2 unpadded token
  IDs for every input. Its internal length limit is not permission to truncate.
- No remote code, pickle weights, automatic device selection, extra model or
  network inference. Offline flags and a blocked socket enforce the run boundary.

The official [pinned model card](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/README.md)
and [Sentence Transformers API](https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html)
support the selected local inference path. This model's MIT declaration is
recorded with the acquisition; other dependency and corpus licenses remain
separate. No model or source files are published to Git.

## Artifact contract and later comparisons

An explicit `config/embedding-artifacts-m4-v1.json` selects the generated
`embedding-manifest-1.0` release under `data/embeddings/`. It is not a default
switch or an index. The manifest binds:

- Exact M3 selector/manifest and model-configuration hash.
- `vectors.npy`: row-ordered float32 vectors; loaded with `allow_pickle=False`.
- `records.jsonl`: unchanged Chunk/Unit IDs, input-text and token-ID hashes,
  vector-row hashes, source spans, lineage precision, configuration/budget,
  classification and mandatory parent/qualification/publication references.
- `inputs.jsonl`: exact derived input text for numeric replay, explicitly marked
  as not evidence authorization.
- `runtime.json`: actual Python/platform, installed versions and hashes of loaded
  Sentence Transformers, pooling, normalization and BERT implementation classes.

Embedding IDs hash the **model configuration + original Chunk ID + input hash**.
The M3 IDs are not rewritten. Later alternatives can use a separate adapter,
configuration and artifact selector over the same upstream evidence. Different
weights, runtimes, pooling, prompts or normalization produce a distinct identity;
incompatible vectors must never be mixed. Only BGE is loaded in M4. The present adapter/reader qualify 384-dimensional
BGE vectors; another dimension or backend needs its own tested embedding
adapter/schema version, not changes to M0–M3. Alternative tokenizers must verify
these exact unchanged input strings and fail explicitly if their own limits are
exceeded; model comparison cannot silently rechunk or truncate them. Adapter
extensions and comparative inference require future authorization; M9 must use
the same frozen relevance labels and report Recall@K/MRR, not infer a winner from
vector dimensions, engineering tests or publisher benchmark scores.

`EmbeddingArtifacts(root, catalog, selector=...)` checks selected file hashes,
row order, complete catalog membership, identity bindings, finite values, shape,
dtype, normalization and per-vector hashes. `get_vector(chunk_id)` returns only
a copied vector and identity metadata, not evidence. `open_bound_chunk(chunk_id)`
uses the original M3 reader to rehydrate the full parent and checks its current
input and qualification bindings. Supported access retains the live filesystem
leases. Arbitrary trusted Python/filesystem callers can bypass application APIs;
this is not an untrusted-code sandbox.

## Execution and verification

From the repository root, install only the isolated locked environment:

```sh
uv sync --project tools/embeddings --locked
```

Read the model configuration hash from
`workspace/rag-implementation/v1/m4-embeddings-v1/MODEL_CONFIGURATION_BINDING.json`.
The implemented generator is `tools/embeddings/run_m4.py --model-sha256 2444f602babc045234dba3258e89fa4a7ea26572fa748576c6df0509dc24e3de`
in that environment, with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`HF_HUB_DISABLE_TELEMETRY=1`, `TOKENIZERS_PARALLELISM=false` and
`LANGSMITH_TRACING=false`. It writes immutable payloads, rejecting changed
existing files. Verification uses `tools/embeddings/verify_m4.py` in a fresh
process: full-catalog numerical replay plus isolated negative-control files.
These scripts do not create a database or execute similarity search.

Focused controls:

```sh
uv run --project tools/embeddings --locked pytest tools/embeddings/tests tests/test_embedding_inputs.py
uv run --locked pytest
uv run --locked ruff check .
uv run --locked rag-hub smoke
```

The private release report records actual vectors, hashes, resource observations,
replay and test results. CPU/platform-specific bitwise reproduction, if measured,
is not a guarantee across different BLAS implementations, hardware or runtimes.
M4 supplies engineering evidence only; no retrieval or answer-quality score is
claimed. Stop for owner acceptance before M5.
