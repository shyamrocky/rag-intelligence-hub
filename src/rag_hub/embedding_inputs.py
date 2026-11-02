"""Source-only M4 projections of live M3 reader views, never QA authorization.

Callers must obtain views from open_chunk; this pure projection does not confer
trust on caller-supplied dictionaries. No parent envelope is flattened into text.
"""

from rag_hub.unified_models import encode, sha


def embedding_input(view):
    row = view["chunk"]
    parent = view["verified_parent"]
    qualification = parent["consumer"]["llm_context"]["qualification"]
    if (parent["admission_status"] != "ADMITTED" or parent["unit_id"] != row["unit_id"]
            or not qualification["mandatory"] or not qualification["complete_unit_only"]
            or row["mandatory_evidence_refs"]["scope"] != "complete_verified_unit_only"
            or row["parent_binding"]["publication_sha256"] != sha(encode(
                parent["publication_identity"]))
            or row["parent_binding"]["memberships_sha256"] != sha(encode(parent["memberships"]))):
        raise ValueError("embedding_parent_or_qualification_mismatch")
    source_ids = {e["section_id"] for e in parent["memberships"]
                  if e["role"] in {"content", "projection"}}
    if not set(row["lineage"]["section_ids"]) <= source_ids:
        raise ValueError("embedding_context_only_as_source")
    source = view["source_slice"]
    if not source or sha(source.encode()) != row["source"]["text_sha256"]:
        raise ValueError("embedding_source_slice_changed")
    heading = "\n".join(h["text"] for h in view["heading_context"])
    text = (heading + "\n\n" if heading else "") + source
    search = view.get("search_representation")
    if search is not None and (search["text"] != text or not search["complete_parent_required"]
            or search["role"] != "SEARCH_ONLY_NOT_INDEPENDENT_EVIDENCE"):
        raise ValueError("embedding_qualified_search_scope_changed")
    binding = {
        "schema": "embedding-input-binding-1.0",
        "authority": "DERIVED_SEARCH_INPUT_NOT_EVIDENCE_AUTHORIZATION",
        "chunk_id": row["chunk_id"], "unit_id": row["unit_id"],
        "document_id": row["document_id"], "format": row["format"],
        "input_text_sha256": sha(text.encode()), "chunk_sha256": sha(encode(row)),
        "tokens_including_specials": row["token_count"],
        "configuration_id": row["configuration_id"], "parent_binding": row["parent_binding"],
        "source": row["source"], "lineage": row["lineage"],
        "heading_context_sha256": row["heading_context_sha256"],
        "reference_classification": row["reference_classification"],
        "mandatory_evidence_refs": row["mandatory_evidence_refs"],
        "qualification_sha256": sha(encode(qualification)),
        "publication_identity": parent["publication_identity"],
        "complete_parent_rehydration_required": True,
    }
    return text, binding


def embedding_id(model_configuration_sha256, chunk_id, input_text_sha256):
    """New models/configurations get new IDs without editing M3 IDs or evidence."""
    return "emb:1.0:" + sha(encode({"model_configuration_sha256": model_configuration_sha256,
                                 "chunk_id": chunk_id, "input_text_sha256": input_text_sha256}))
