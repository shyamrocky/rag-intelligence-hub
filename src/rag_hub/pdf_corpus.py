"""Opt-in durable PDF views. No parser/default/QA policy changes or admission authority.

Existing ParsedBlock, Section, source-span and parent conformance contracts apply.
Corrections are source-bound overlays; original observations are never rewritten.
"""

import copy
import json
import re
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.schemas import ParsedBlock, Section
from rag_hub.shared.contracts import read_source
from rag_hub.shared.structure import assess, parent

VERSION = "pdf-corpus-cleanup-1.0"
SCHEMA = "persistent-pdf-corpus-1.0"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def is_folio(block, page_size):
    """Screen only: matching page value, centered lower margin; review still required."""
    box = block.locator.bbox
    width, height = page_size
    return bool(
        box
        and block.content.isascii()
        and block.content.isdecimal()
        and block.content == str(block.locator.page)
        and box[1] > 0.9 * height
        and abs((box[0] + box[2]) / 2 - width / 2) < 0.12 * width
    )


def cleanup(source, blocks, parents, audit, corrections):
    """Apply frozen, machine source-reviewed corrections with a complete inverse.

    Each target binds full original identity, block hash/locator and page geometry.
    No strings are substituted, no spans deleted and no independent review implied.
    """
    assess(parents, blocks, audit)
    lookup = {b.block_id: b for b in blocks}
    result, inventory = copy.deepcopy(parents), []
    seen = set()
    for spec in corrections:
        ident = spec["block_id"]
        if ident in seen:
            raise ValueError("duplicate_correction_target")
        seen.add(ident)
        block = lookup[ident]
        if (
            spec["raw_sha256"] != source.raw_sha256
            or spec["snapshot_id"] != source.snapshot_id
            or spec["block_sha256"] != block.content_sha256
            or spec["locator"] != block.locator.model_dump(mode="json")
            or spec["review_status"] != "machine_source_reviewed_not_owner_approved"
        ):
            raise ValueError("stale_or_unreviewed_correction")
        owners = [p for p in result if any(m["block_id"] == ident for m in p["members"])]
        if len(owners) != 1:
            raise ValueError("correction_requires_single_full_owner")
        before = owners[0]
        matches = [m for m in before["members"] if m["block_id"] == ident]
        if len(matches) != 1 or (matches[0]["start"], matches[0]["end"]) != (
            0,
            len(block.content),
        ):
            raise ValueError("partial_correction_not_supported")
        after = []
        if spec["operation"] == "separate_folio":
            if not is_folio(block, spec["page_size"]):
                raise ValueError("substantive_number_is_not_folio")
            # Split this known wrong parent only. Do not merge across intervening
            # footnotes, mathematical elements or furniture and violate flat order.
            for member in before["members"]:
                furniture = member["block_id"] == ident
                kind = "page_furniture_observation" if furniture else "paragraph_fragment"
                after.append(
                    parent(
                        VERSION + ":" + before["id"] + ":" + member["block_id"],
                        kind,
                        [copy.deepcopy(member)],
                        source,
                        lookup,
                        None if furniture else before.get("heading_block_id"),
                    )
                    | {
                        "derived_from_parent_id": before["id"],
                        "source_review_case": spec["evidence_case"],
                        "structure_status": "machine_source_reviewed_HOLD",
                        "context_dependencies": [] if furniture else ["needs_parent_context"],
                        "exclusion_reasons": ["page_furniture"]
                        if furniture
                        else ["incomplete_cross_page_context"],
                    }
                )
        elif spec["operation"] == "classify_figure_caption":
            if len(before["members"]) != 1 or not re.match(r"^Figure \d+:\s", block.content):
                raise ValueError("not_explicit_single_block_figure_caption")
            caption = copy.deepcopy(before)
            caption.update(
                id=VERSION + ":" + before["id"],
                kind="figure_caption_observation",
                derived_from_parent_id=before["id"],
                source_review_case=spec["evidence_case"],
                structure_status="machine_source_reviewed_HOLD",
                caption_attachment={"type": "caption_of", "target": None, "status": "HOLD"},
                exclusion_reasons=["unverified_caption_ownership_and_visual_content"],
            )
            after = [caption]
        else:
            raise ValueError("unsupported_cleanup_operation")
        position = result.index(before)
        result[position : position + 1] = after
        inventory.append(
            {
                "correction_id": digest(encoded(spec)),
                "version": VERSION,
                "spec": spec,
                "before": before,
                "before_sha256": digest(encoded(before)),
                "after": after,
                "after_sha256": [digest(encoded(p)) for p in after],
                "text_transformation": "none; exact original spans and joiners retained",
                "eligibility": "HOLD",
            }
        )
    conformance = assess(result, blocks, audit)
    if restore(result, inventory) != parents:
        raise ValueError("correction_inverse_failed")
    return result, inventory, conformance


def restore(parents, inventory):
    """Exact parent-graph inverse, including previous IDs, metadata and joiners."""
    result = copy.deepcopy(parents)
    for entry in reversed(inventory):
        ids = [p["id"] for p in entry["after"]]
        positions = [i for i, p in enumerate(result) if p["id"] in ids]
        if (
            not positions
            or positions != list(range(positions[0], positions[0] + len(ids)))
            or [digest(encoded(result[i])) for i in positions] != entry["after_sha256"]
            or digest(encoded(entry["before"])) != entry["before_sha256"]
        ):
            raise ValueError("invalid_correction_inverse_binding")
        result[positions[0] : positions[-1] + 1] = [copy.deepcopy(entry["before"])]
    return result


def load_corpus(root, manifest_path="data/normalized/pdf/four-pdf-poc-v1/manifest.json"):
    """Load/check durable data only. Never opens a PDF parser or runs QA/readiness.

    This store deliberately has no approved-parent admission contract. A future
    chunker must use the authoritative QA gate, not any ad-hoc record status.
    """
    root = Path(root).resolve()
    manifest = json.loads(local_path(root, manifest_path).read_bytes())
    if manifest.get("schema") != SCHEMA or set(manifest["documents"]) != {
        "C01",
        "C02",
        "C06",
        "C14",
    }:
        raise ValueError("unsupported_corpus_manifest")
    for name, expected in manifest["artifacts"].items():
        if digest(local_path(root, name).read_bytes()) != expected:
            raise ValueError("persisted_artifact_hash_mismatch: " + name)
    documents = {}
    for doc, paths in manifest["documents"].items():
        if any(name not in manifest["artifacts"] for name in paths.values()):
            raise ValueError("unbound_persisted_artifact")
        values = {
            role: json.loads(local_path(root, name).read_bytes()) for role, name in paths.items()
        }
        source = read_source(values["source"])
        if (
            source.doc_id != doc
            or digest(local_path(root, source.snapshot_path).read_bytes()) != source.raw_sha256
        ):
            raise ValueError("persisted_source_mismatch")
        blocks = [ParsedBlock.model_validate(b) for b in values["blocks"]]
        sections = [Section.model_validate(s) for s in values["sections"]]
        if len({b.block_id for b in blocks}) != len(blocks) or any(
            (b.doc_id, b.raw_sha256, b.snapshot_id) != (doc, source.raw_sha256, source.snapshot_id)
            for b in blocks
        ):
            raise ValueError("foreign_or_duplicate_persisted_blocks")
        for section in sections:
            if (section.doc_id, section.raw_sha256, section.snapshot_id) != (
                doc,
                source.raw_sha256,
                source.snapshot_id,
            ) or section.index_status != "hold":
                raise ValueError("unsupported_or_foreign_section_admission")
        if any(p.get("experimental_eligibility") != "HOLD" for p in values["parents"]):
            raise ValueError("unsupported_parent_admission")
        if any(d["status"] != "hold" for d in values["qa"]["quality_decisions"]):
            raise ValueError("unsupported_pdf_qa_admission")
        assess(values["parents"], blocks, values["audit"])
        documents[doc] = values
    return {"manifest": manifest, "documents": documents}


def approved_parents(corpus):
    """Fail-safe empty handoff: no parent admission was granted for this version."""
    if any(
        p.get("experimental_eligibility") != "HOLD"
        for v in corpus["documents"].values()
        for p in v["parents"]
    ):
        raise ValueError("unsupported_parent_admission")
    return []


def citation_lookup(corpus, doc_id, parent_id):
    """Inspection locator, including original offsets; not permission to cite HOLD."""
    document = corpus["documents"][doc_id]
    record = next(p for p in document["parents"] if p["id"] == parent_id)
    return {
        "source": document["source"],
        "parent_id": parent_id,
        "text_sha256": record["text_sha256"],
        "members": record["members"],
        "retrieval_eligible": False,
    }
