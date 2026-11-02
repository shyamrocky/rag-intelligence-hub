# H2/H3 preparation tools

These tools inspect accepted artifacts and create private review reports. They are outside the application runtime and never establish QA eligibility, construct releases, move evidence or activate selectors.

From the repository root:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline python tools/hardening/prepare.py --root . --output workspace/hardening-review/new-plan
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline --project tools/embeddings python tools/hardening/current_probe.py --root . --output workspace/hardening-review/new-probe
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline pytest tests/test_hardening_preparation.py
```

Use a new output directory each time. Preparation deliberately pins the reviewed dependency matrix; a changed inventory requires a new reviewed version. The probe uses the actual current public reader chain and pinned tokenizer, and never constructs an embedding model. It records file-open stacks and binding hashes; it does not turn hashes into content authorization. Saved comparison records and synthetic tests are not approval receipts.

The strict pipeline patch is a review proposal, computed in memory. No apply/build/activate option exists. A separately authorized implementation must validate complete native QA scopes, every affected input/token/vector relationship and a no-workspace runtime before adoption.
