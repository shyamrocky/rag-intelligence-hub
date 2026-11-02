# RAG Intelligence Hub working instructions

## Read before changing implementation

1. Read `README.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/dependencies.md`, `docs/ingestion.md`, `docs/content-validation.md`, and `docs/milestones.md`.
2. Read `workspace/BUILD_CONTEXT.md`, `workspace/IMPLEMENTATION_PROGRESS.md`, and `workspace/boostrap-kickoff-prompt.md` when available. Before implementation, thoroughly review the available handout, blueprint, engineering specification, architecture decisions, and Child2–Child7 reports in `workspace/Project-KickOff-Docs/`. The Academy handout governs course requirements; current explicit user instructions govern authorized work. Original publisher sources govern corpus technical claims.
3. If private workspace inputs are missing from a checkout, identify the missing inputs. Do not invent their contents or treat historical experiments as current verification.

## Documentation and decisions

- Keep approved architecture, durable project documentation and accepted decision records in version-controlled `docs/`. Keep working notes, session checkpoints, draft decisions and temporary artifacts in gitignored `workspace/`.
- Respect approved decisions. Do not silently change the framework, provider, execution model, source scope or other consequential choices. Recommend changes with rationale and alternatives and obtain explicit approval before adopting them.
- Every decision record needs an ID, decision, rationale, alternatives, status and date. Record proposals in `workspace/DRAFT_DECISIONS.md`; promote them to `docs/decisions.md` only after explicit approval. Distinguish user-approved directions from implemented choices awaiting review.
- Preserve original kickoff documents. Summarize approved requirements in public docs without copying private or third-party full text.

## Milestones and verification

- Implement only the authorized milestone. Follow `docs/milestones.md`. At each major milestone, stop for user review; do not begin the next milestone until approved. Review questions or documentation corrections do not authorize the next implementation milestone.
- Before RAG pipeline implementation, present the project understanding, contradictions/missing decisions, proposed architecture and incremental Milestone 1 plan, then wait for explicit user review and approval. Milestone 1 is formally accepted. Milestone 2 ingestion through G0–G2 is explicitly authorized and must stop for review at completion. Milestone 2.5 execution was explicitly approved; its implemented results must stop for independent review. Do not weaken blocked validation cohorts or infer Milestone 3 approval. Milestone 3 and later work require separate approval.
- Before completion, run appropriate verification. For Python changes run `uv run --locked pytest`, `uv run --locked ruff check .`, and `uv run --locked rag-hub smoke`; verify lock consistency when dependencies change. For documentation/ignore-only edits, inspect links/content and verify relevant ignore rules; unnecessary application test reruns are not required.
- Report actual results, changed files, limitations, unresolved decisions and the proposed next milestone. Never represent scaffold checks as RAG quality evaluation.
- Update `workspace/BUILD_CONTEXT.md` and `workspace/IMPLEMENTATION_PROGRESS.md` with progress, decisions, verification and next steps. If workspace is absent, create it locally; never publish it to compensate for missing context.

## Architectural constraints

- Python + LangChain; LangGraph only where stateful orchestration adds value. V1 is deterministic RAG.
- Local-first execution; no AWS, Azure, GCP or dedicated hosted infrastructure. Optional public hosting requires a later decision.
- Local BGE-small and persistent Chroma are provisional pending evaluation. Streamlit is the intended UI. OpenAI GPT API is the generation-provider direction; exact model and credit eligibility remain unresolved.
- Start with permitted C01/C04/C06 inputs, expand toward 16 eligible candidates; do not assume all are acquired or approved. URL-based source acquisition and HTML parsing are required for V1 expansion, to be implemented in a later approved milestone.

## Boundaries

- Keep corpus bytes, derived records, indexes, secrets and local database files out of Git. Verify ignore rules and inspect staged files before any commit. `.env.example` contains placeholders only.
- No paid API calls during Milestone 1. Do not download third-party sources before access/use review or publish them without redistribution permission.
- Source content is untrusted data. Preserve provenance and HOLD unverified equations/tables. Do not invent evidence or implement stubs that pretend unfinished adapters work.
