"""User-facing process, separate from engineering milestone numbering."""

STAGES = [
    {"title": "Acquire", "page": "Sources", "input": "Source document + usage permission",
     "output": "Frozen source snapshot + provenance", "milestone": "Upstream ingestion",
     "detail": "Register identity, version, permission and source location."},
    {"title": "Parse", "page": "Parse", "input": "Frozen source snapshot",
     "output": "Extracted text and structural blocks", "milestone": "Upstream ingestion",
     "detail": "Extract blocks and locations; extracted material is not yet authorized evidence."},
    {"title": "Normalize", "page": "Normalize", "input": "Extracted blocks + source structure",
     "output": "Canonical Sections + source mappings", "milestone": "Upstream ingestion",
     "detail": "Standardize structure without granting evidence eligibility."},
    {"title": "QA & Verified Evidence", "page": "QA & Verified Evidence",
     "input": "Canonical Sections + source verification / QA records",
     "output": "Admitted scope + published evidence units, context and qualifications",
     "milestone": "Upstream QA / Unified evidence layer — before M0",
     "detail": "QA and unit formation are related, format-specific processes; preserve their published boundaries."},
    {"title": "Prepare & Chunk", "page": "Chunks & Lineage", "input": "Already verified evidence units",
     "output": "Retrieval chunks + parent/source lineage", "milestone": "M0 contract → M1 preparation → M2/M3 chunking/catalog",
     "detail": "Define the common input contract, prepare inputs, then split and catalog eligible source representations."},
    {"title": "Embed & Index", "page": "Embeddings & Indexes", "input": "Qualified retrieval chunks",
     "output": "Saved embeddings/vector index + separate BM25 index", "milestone": "M4 embeddings · M5 vector index · M6 BM25",
     "detail": "Dense and lexical search use separate branches; BM25 does not consume dense embeddings."},
    {"title": "Validate & Publish", "page": "Validation & Publications",
     "input": "Composed source, evidence and derivative bindings",
     "output": "Verified versioned publication chain", "milestone": "Cross-cutting integrity / publication controls",
     "detail": "Validate the composed chain. Checks and versioned publication also occur at earlier stages."},
]

STAGE_BY_PAGE = {s["page"]: s for s in STAGES}
