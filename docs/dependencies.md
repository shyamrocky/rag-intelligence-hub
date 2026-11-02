# Dependencies and configuration

**Forward status — October 25, 2026:** The current implementation uses four isolated locked environments (root, dashboard, chunking and embeddings). See [current environment and offline prerequisites](current-operations.md#environment-and-private-prerequisites). Earlier dependency-planning sections below are historical; do not infer that already implemented capabilities remain uninstalled.

Milestone 1 installs Pydantic for contracts, pytest for offline tests, Ruff for lint, and Hatchling for packaging. `uv.lock` pins resolutions; `.python-version` selects Python 3.12. Python 3.15 is the machine default and is intentionally not used. `pypdf` was used as a temporary review tool for the Academy PDF, not selected as the production parser.

Defer runtime integrations until their milestone so the scaffold does not download models or install a large inference stack. Before adding each, verify official package APIs, Python/platform compatibility, licenses and pin a resolved lock:

| Later capability | Candidate dependencies |
|---|---|
| PDF | PyMuPDF primary (review its license), pdfplumber comparison; parser choice remains proposed |
| Markdown/MDX | markdown-it-py plus explicit MDX tab handling; generic Markdown parsing alone is insufficient |
| HTML/acquisition | beautifulsoup4, httpx; allowlisted acquisition and source rights policy first |
| Chunking/framework | langchain, langchain-text-splitters; LangGraph only if needed |
| Local embeddings | sentence-transformers, langchain-huggingface; pin model revision/tokenizer |
| Persistent index | chromadb, langchain-chroma |
| Generation | langchain-openai or OpenAI SDK adapter; exact model and credits unresolved |
| Lexical baseline | scikit-learn TF-IDF |
| UI | streamlit |

`.env.example` contains empty secret/model placeholders and provisional local defaults. Current settings use explicit constructor arguments; environment loading is future work. Never log keys, private corpus or sensitive question text by default. No external telemetry integration is enabled.


Milestone 2 adds locked PyMuPDF 1.28.2 and markdown-it-py 4.2.0 (mdurl 0.1.2). These implement only local parsing; no model/provider/vector/UI libraries were added. PyMuPDF is the engineering spec's proposed parser and uses AGPL/commercial licensing; review release licensing before public distribution/deployment. Official API/license references are in docs/ingestion.md. Full project release licensing remains unresolved; local source-use authorization does not grant redistribution rights to corpus files.


M4 adds an isolated locked environment under `tools/embeddings/`, preserving root and chunking locks. It pins Sentence Transformers 5.1.2, Transformers 4.57.1, torch 2.8.0, NumPy 2.2.6, safetensors 0.6.2 and existing tokenizer 0.22.2. Only the authorized revision of BAAI/bge-small-en-v1.5 is acquired (MIT model-card declaration), using safetensors without remote code. See [M4 dependencies and behavior](LOCAL_EMBEDDINGS.md). No ChromaDB, BM25 or retrieval dependencies are introduced.
