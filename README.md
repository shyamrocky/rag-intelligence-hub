# RAG Intelligence Hub

A local-first RAG application for learning how answers are built from traceable
research and technical documentation. It combines a single-question RAG Bot with
an engineering workspace for inspecting sources, retrieval, evidence delivery,
generation diagnostics, cost, latency and human review.

**Repository scope:** private code/documentation review. The original corpus,
indexes, model assets, evaluation records and execution trust artifacts are not
included. **A clean clone is not a self-contained runnable demo.** See
[private review and setup boundaries](docs/PRIVATE_GITHUB_REVIEW.md).

## Application

| Workspace | What it shows |
|---|---|
| RAG Bot | One question → verified evidence → answer, partial answer or clear stop reason |
| Knowledge Preparation | Sources → parsing → normalization → QA/evidence → chunks → embeddings and indexes → publication checks |
| Knowledge Retrieval | BM25/vector candidates, RRF ranking and complete-parent context assembly |
| Offline Retrieval Evaluation | Historical experiments, human-approved evidence requirements and discovery/delivery measurements |
| Pre-Generation | Request assembly, source bindings, model tokens, context fit and cost qualification |
| Generation | Returned output, contract acceptance, usage, estimated cost, latency and failures |
| Post-Generation Evaluation | Structure/citation/fidelity findings and unresolved answer-quality assessments |
| Human Review | Source-bound review, explicit owner decisions and protected diagnostic inspection |

The pipeline uses structure-aware chunks with parent–child lineage, local
`BAAI/bge-small-en-v1.5` embeddings, Chroma and BM25. Experimental retrieval uses
BM25 Top-50 + vector Top-50, exact Chunk-ID deduplication, RRF(k=60) and final
Top-30. Context assembly admits complete authorized parent Evidence Units within
128,000 BGE tokens; that is not the generator's model-token allowance.
Current experimental generation uses prompt v2.2 and response schema 2.0 through
the native GenerationService and trust/authorization controls.

## Launch the provisioned owner application

From the project root, **after the authorized private inputs and environments are
present**, run:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/knowledge_preparation/app.py --server.address 127.0.0.1 --server.port 8516 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8516>. The historical Master Dashboard is preserved on 8514;
see [historical launch instructions](docs/CANONICAL_MASTER_DASHBOARD.md). Starting
or refreshing a page does not submit a question. **Pressing Send in normal Chat
can transmit authorized evidence and incur model charges.** The owner's existing
Bot policy enforces $0.03 per question and a persistent $1.00 total cap, including
conservative reservations, with no automatic retries or fallback. This repository
does not transfer that owner's consent, credentials or execution authority.

## Environment setup

Python **3.12.15** is required by the current retrieval worker. `uv` manages seven
separate locked environments. The following are dependency setup commands, not
source/model acquisition, trust preparation or generation commands:

```sh
uv sync --locked --python 3.12.15
uv sync --locked --python 3.12.15 --project apps/ingestion_dashboard
uv sync --locked --python 3.12.15 --project tools/chunking
uv sync --locked --python 3.12.15 --project tools/embeddings
uv sync --locked --python 3.12.15 --project tools/indexing
uv sync --locked --python 3.12.15 --project tools/lexical
uv sync --locked --python 3.12.15 --project tools/generation
```

These commands have not been executed as part of release preparation. Installation
may download packages; it does not provide the excluded corpus/model/publication
artifacts. Full fresh-clone and cross-platform reproduction remain unverified.
POSIX-specific runtime code means Windows support must not be assumed.

Provider operations require the operator's own `OPENAI_API_KEY` in the process
environment, explicit applicable source-transfer/execution permission, and fresh
model/token/context/pricing/cost checks. `.env.example` contains placeholders;
it is not an automatic dotenv loader. Never commit real credentials or include
them in diagnostic output. Model access and current pricing are not guaranteed
by historical successful runs.

## Reproduction and verification limits

The original accepted stack depends on exact private source/QA publications,
553 Evidence Units, 992 chunks/vectors, index releases and native trust records.
Replacing those inputs with arbitrary documents does not constitute a verified
rebuild. Even the Bot's synthetic path currently requires private trust bindings.
No independently distributable sample-corpus bootstrap has been implemented.

Tests are a mixture of synthetic controls and private integration/historical
replay checks. See [regression verification](docs/REGRESSION_VERIFICATION.md).
Earlier verification identified root pytest collection and Ruff findings; a full
green clean-clone suite is not claimed. `rag-hub smoke` checks the historical
scaffold, not end-to-end retrieval quality. Release documentation checks do not
substitute for functional execution tests.

## Measured results and answer quality

The reconciled benchmark has 34 questions: 31 answerable and three unsupported
controls, with 40 human-approved evidence groups. Historical measurements recorded
39/40 group discovery, 36/40 delivery and complete delivery for 27/31 answerable
questions. All 34 questions were attempted; 29 latest responses were accepted as
structured responses. These are different measurements, not an achieved answer
faithfulness score.

[ADR D052](docs/adr/D052-semantic-grounding-validation-v2.md) separates strict
citation/source integrity, presentation-tolerant quotation fidelity, semantic
grounding, completeness and material qualifications/conflicts. Mechanical checks,
model declarations, Local POC owner approval and independent semantic acceptance
remain distinct. Historical failures and later assessments are preserved separately.

See the [Week 2 submission draft](docs/submission/WEEK2_RAG_INTELLIGENCE_HUB_SUBMISSION.md)
for the architecture, experiments, measured outcomes and limitations. Its private
evidence links are traceability references, not attachments provided by this repo.

## Layout and privacy

```text
src/rag_hub/                  ingestion, evidence, chunking and artifact readers
tools/                       retrieval, indexes, generation, validation and review
apps/knowledge_preparation/  current 8516 Bot and Knowledge Workspace
apps/master_dashboard/       preserved 8514 historical Master Dashboard
tests/ and component tests   synthetic and integration verification
config/                      versioned metadata and selectors, not corpus payloads
docs/                        architecture, decisions, operating guides and submission
data/ and workspace/         private local artifacts; excluded from the review upload
```

Private visibility is not permission to redistribute publisher material. Credentials,
signing keys, raw responses, source-bearing prompts, reviews/authorizations, models,
databases, backups and recovery archives must stay outside Git. A project license
has not yet been selected; sharing and dependency licensing need owner review.
No API call, generation, source transfer or automatic owner approval is authorized
by reading this repository or running dependency setup.
