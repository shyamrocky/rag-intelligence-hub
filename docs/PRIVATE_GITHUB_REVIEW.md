# Private GitHub review: scope and setup boundary

This project is being prepared for a **private review repository**, with access
granted to named reviewers. This guide does not authorize an upload, make the
repository public, transfer publisher content, or grant permission to run paid
generation. No independent distributable demo corpus has been implemented.

## What reviewers receive

The proposed inventory includes the application and backend source in `src/`,
`apps/` and `tools/`, tests, configuration and prompt/schema contracts, all seven
dependency locks, and project documentation. Important current implementation
files are not yet tracked in Git; publishing only the current tracked snapshot
would omit parts of the application. Review the explicit inventory before staging;
do not use a blanket “add everything” operation.

The current root `README.md` is pinned by the native preservation baseline. A
replacement README is prepared separately for review, rather than silently
invalidating the working application. Applying it to the protected working tree
requires the established reviewed trust migration. A repository-only review copy
with that replacement must not be described as matching the original execution
baseline or as independently execution-ready.

## What stays out of Git, including a private repository

- `.env`, API credentials, Streamlit secrets, signing keys and passphrases.
- Original publisher documents and source snapshots without approved sharing rights.
- Parsed/normalized publisher text, complete evidence, prompts containing source
  passages, model assets, embeddings, local databases and index payloads.
- Raw provider responses, execution authorizations, owner/reviewer decision records
  and other private runtime/evaluation records.
- `workspace/`, backups, recovery archives, virtual environments and generated caches.

Configuration paths and hashes do not supply the referenced private content.
Privacy must be checked against the exact selected files and intended Git history;
an ignore rule does not remove content already tracked or committed. Private
visibility is not permission to redistribute third-party material. Repository
collaborators can obtain copies; private access should be limited to intended people.

## Launching the existing owner application

From an already provisioned, authorized working copy:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/knowledge_preparation/app.py --server.address 127.0.0.1 --server.port 8516 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8516>. The application provides RAG Bot, Knowledge Preparation,
Knowledge Retrieval, Offline Retrieval Evaluation, Pre-Generation, Generation,
Post-Generation Evaluation and Human Review. The historical Master Dashboard on
8514 remains preserved; see [its launch guide](CANONICAL_MASTER_DASHBOARD.md).

Navigation and refresh do not run the pipeline. **Sending a Bot question can invoke
provider preflight and paid generation** under the existing valid consent, source,
model, pricing and spending controls. Inspecting the app is different from sending
a request. Review decisions also require explicit confirmation.

## What an ordinary clone cannot reproduce by itself

The current accepted stack binds source snapshots, QA publications, complete
Evidence Units, chunk catalogs, model/tokenizer files, embeddings, Chroma/BM25
indexes, historical receipts and the reviewed native trust baseline. Its checker
and some foundation evidence reside in private `workspace/` paths. Merely installing
dependencies or supplying an API key does not replace those artifacts.

Without the authorized matching local inputs, data views or execution may report
unavailable/blocked states. Even Bot simulation currently checks the native private
trust baseline. The root scaffold smoke command is not an end-to-end RAG demo.
Do not change hashes, remove checks, insert fabricated receipts or regenerate an
unreviewed substitute to force the application to run.

Full execution on a different machine needs a separately authorized, rights-reviewed
provisioning/reproduction process. A small independently distributable demo remains
future work. Screenshots, permitted result summaries and the owner's demonstration
video can communicate existing behavior without distributing the private payloads.

## Environments and model access

The retrieval worker requires Python **3.12.15**. Seven lockfiles cover root,
dashboard, chunking, embeddings, indexing, lexical retrieval and generation. Setup
instructions belong to those environments; the root installation alone is incomplete.
See [the application/runtime guide](RAG_BOT_RUNTIME.md) and
[regression verification](REGRESSION_VERIFICATION.md) for their actual private-input
boundaries. Fresh-clone and cross-platform reproduction have not been certified.

Provider access uses the operator's own `OPENAI_API_KEY` in the process environment.
Never include the owner's key in Git or a handoff bundle. The checked-in `.env.example`
is a historical placeholder template; copying it does not automatically load an
environment file, authorize source transfer, or grant model access. Current model,
prompt, schema, pricing, token/context fit, duplicate prevention and spending limits
must pass the existing native checks. A valid old receipt is not fresh permission.

## Evidence and results

[The Week 2 report](submission/WEEK2_RAG_INTELLIGENCE_HUB_SUBMISSION.md) describes
the implementation and measured results. Its local `data/` and `workspace/` links
are audit references in the owner's working copy, not accessible review attachments.
Review any source excerpts, generated answer text and images before sharing them.
The report distinguishes 34 attempted benchmark questions, 29 accepted structured
responses, technical findings, Local POC decisions and unresolved semantic review.
Successful execution is not proof of answer quality or an achieved faithfulness target.

## Remaining release checks

1. Review the exact source inventory, including untracked application files and
   any intentional changes already present in the working tree.
2. Review candidate contents and intended branch/tag history for secrets, personal
   information and restricted content. A pattern scan is triage, not exhaustive
   clearance; no dedicated secret scanner has yet been run.
3. Decide whether to retain existing author/committer email metadata. Do not rewrite
   the private Git history as part of preparation.
4. Confirm project/dependency licensing and permitted sharing of submission excerpts;
   no project license is selected automatically.
5. Review the proposed README. Preserve the protected original and migrate trust
   bindings before changing it in the working application, if that is chosen.
6. Select the GitHub account/repository, verify **Private** visibility and intended
   reviewer access, then separately authorize the actual commit/sync operation.
7. Verify reviewer access to the repository, report and video. Do not claim a
   standalone runnable clone unless it has been provisioned and tested as such.
