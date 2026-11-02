"""Read-only M8 assembly through accepted live M4/M3/Unified parent gateways."""

import copy
import json
import os
import subprocess
import threading
from pathlib import Path

from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from tools.evidence.contract import (
    POLICY,
    SCHEMA,
    budget_limit,
    load_configuration,
    validate_candidates,
)
from tools.indexing.m5_index import encoded, sha
from tools.retrieval.contract import check_files


class EvidenceIntegrityError(ValueError):
    """Invalid input or current binding: never an ordinary no-results outcome."""


class EvidenceService:
    """Trusted local Python service. Packages are ephemeral, not bearer authorizations."""

    def __init__(self, root, *, selector, selector_sha256):
        self.root = Path(root).resolve(strict=True)
        if Path(__file__).resolve() != self.root / "tools/evidence/service.py":
            raise EvidenceIntegrityError("m8_loaded_implementation_origin_changed")
        self.selector, self.selector_sha256 = selector, selector_sha256
        self._lock = threading.RLock()
        self.manifest, self.m7, self.files, self.inventory = load_configuration(
            self.root, selector, selector_sha256)
        selected = self.m7["spec"]["selections"]
        self.corpus = load_durable_corpus(self.root, selector=selected["unified"]["path"])
        self.catalog = QualifiedChunkCatalog(self.root, self.corpus, selector=selected["m3"]["path"])
        self.artifacts = EmbeddingArtifacts(self.root, self.catalog, selector=selected["m4"]["path"])
        self.check()

    def check(self):
        check_files(self.root, self.files)
        self.artifacts.check()

    def _count(self, texts):
        """Exact pinned tokenizer, existing isolated runtime; no network/inference."""
        env = dict(os.environ)
        for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP"):
            env.pop(key, None)
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
        run = subprocess.run([str(self.root / "tools/chunking/.venv/bin/python"),
            "-m", "tools.evidence.token_worker"], cwd=self.root, env=env,
            input=json.dumps({"root": str(self.root), "texts": texts}, ensure_ascii=False),
            text=True, capture_output=True, timeout=120, check=False)
        if run.returncode:
            # Never echo worker input/source payload or full stderr into public logs.
            raise EvidenceIntegrityError("m8_pinned_counting_runtime_failed")
        result = json.loads(run.stdout)
        if (result.get("schema") != "m8-token-counts-1.0"
                or result["tokenizer"]["spec_sha256"] != POLICY["tokenizer_spec_sha256"]
                or result["tokenizer"]["truncation"] is not False
                or len(result["counts"]) != len(texts)):
            raise EvidenceIntegrityError("m8_invalid_token_count_contract")
        counts = []
        for text, row in zip(texts, result["counts"], strict=True):
            if (row["sha256"] != sha(text.encode()) or type(row["tokens"]) is not int
                    or row["tokens"] < 2):
                raise EvidenceIntegrityError("m8_counting_text_binding_failed")
            counts.append(row["tokens"])
        return counts

    def assemble(self, result, *, token_budget):
        """Invalid/integrity failures raise; ordinary empty/budget outcomes return status."""
        with self._lock:
            try:
                return self._assemble(copy.deepcopy(result), budget_limit(token_budget))
            except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
                raise EvidenceIntegrityError("m8_verification_failed:" + str(exc)) from exc

    def _assemble(self, result, limit):
        self.check()
        hits = validate_candidates(result, self.m7, self.inventory)
        parents, order, deduplicated = {}, [], []
        # Every exact candidate reopens its live native parent; detached text is never accepted.
        for hit in hits:
            cid = hit["chunk_id"]
            view = self.artifacts.open_bound_chunk(cid)
            row, parent = view["chunk"], view["verified_parent"]
            uid = row["unit_id"]
            self.corpus.evidence.validate(parent)
            if (parent["unit_id"] != uid or parent["admission_status"] != "ADMITTED"
                    or parent["document_id"] != hit["document_id"]
                    or parent["reference_classification"] != hit["reference_classification"]
                    or parent["format"] != hit["format"]):
                raise EvidenceIntegrityError("m8_live_parent_identity_mismatch")
            relationships = self.corpus.catalog.get_unit_sections(uid)
            if relationships != parent["memberships"]:
                raise EvidenceIntegrityError("m8_parent_memberships_changed")
            if uid not in parents:
                order.append(uid)
                parents[uid] = {"unit_id": uid, "document_id": parent["document_id"],
                    "format": parent["format"], "reference_classification": parent["reference_classification"],
                    "complete_parent_required": True,
                    "verified_parent": parent,
                    "citation_precision": {"parent": "NATIVE_LOCATORS_UNCHANGED_NO_PRECISION_UPGRADE",
                                           "contributing_chunks": []},
                    "contributing_candidates": []}
            else:
                if encoded(parents[uid]["verified_parent"]) != encoded(parent):
                    raise EvidenceIntegrityError("m8_parent_changed_during_assembly")
                deduplicated.append({"unit_id": uid, "chunk_id": cid, "rank": hit["rank"],
                                     "action": "PARENT_ALREADY_PRESENT_LINEAGE_RETAINED"})
            parents[uid]["contributing_candidates"].append(hit)
            parents[uid]["citation_precision"]["contributing_chunks"].append({
                "chunk_id": cid, "source_span_precision": row["lineage"]["precision"],
                "source_span": row["source"], "lineage": row["lineage"],
                "restriction": "Cite complete authorized parent; search slice is not independent evidence."})
        blocks = [parents[uid] for uid in order]
        texts = [encoded(block).decode() + "\n" for block in blocks]
        # Per-block special-token overhead is conservatively reserved. Combined input is
        # also counted exactly; nothing is removed from a parent to make it fit.
        counts = self._count(texts) if texts else []
        selected, omitted, reserved = [], [], 0
        for block, text, count in zip(blocks, texts, counts, strict=True):
            if reserved + count <= limit:
                selected.append({"block": block, "text": text, "token_count": count})
                reserved += count
            else:
                omitted.append({"unit_id": block["unit_id"], "token_count": count,
                    "contributing_chunk_ids": [h["chunk_id"] for h in block["contributing_candidates"]],
                    "reason": "PARENT_EXCEEDS_TOTAL_BUDGET" if count > limit else "BUDGET_EXHAUSTED",
                    "remaining_tokens": limit - reserved, "partial_parent_returned": False})
        llm_text = "".join(p["text"] for p in selected)
        exact = self._count([llm_text])[0] if selected else 0
        if exact > limit:
            raise EvidenceIntegrityError("m8_combined_count_exceeds_budget_no_truncation")
        self.check()
        status = "VERIFIED_EVIDENCE" if selected else (
            "INSUFFICIENT_EVIDENCE_FOR_BUDGET" if hits else "NO_RETRIEVAL_CANDIDATES")
        # Everything needed for authorized consumption is inside each counted block.
        # Package metadata and diagnostics are audit/control fields, not extra LLM source text.
        return {"schema": SCHEMA, "authority": "EPHEMERAL_VERIFIED_COMPOSITION_NOT_ADMISSION",
            "status": status, "verification": "LIVE_NATIVE_PARENT_BINDINGS_VERIFIED",
            "release_identity": self.manifest["identity"],
            "selection": {"path": self.selector, "sha256": self.selector_sha256},
            "retrieval": {"release_identity": result["release_identity"],
                "query_sha256": result["query_sha256"], "mode": result["retrieval_mode"],
                "candidate_result_sha256": sha(encoded(result)),
                "rank_provenance": "VALIDATED_M7_CONTRACT_NOT_SIGNED_RETRIEVAL_ATTESTATION"},
            "budget": {"policy": POLICY, "limit": limit, "reserved_block_tokens": reserved,
                "exact_llm_evidence_tokens": exact, "budget_exhausted": bool(omitted),
                "truncation": False, "scope": "llm_evidence; audit diagnostics excluded"},
            "counts": {"candidates": len(hits), "distinct_parents": len(blocks),
                "selected_parents": len(selected), "omitted_parents": len(omitted)},
            "parents": [{"evidence": p["block"], "token_count": p["token_count"]} for p in selected],
            "llm_evidence": llm_text,
            "diagnostics": {"deduplicated": deduplicated, "omitted": omitted,
                "rejected_candidates": [], "invalid_candidate_policy": "REJECT_ENTIRE_REQUEST",
                "sufficiency": "BUDGET_AVAILABILITY_ONLY_NOT_RELEVANCE_OR_ANSWER_SUPPORT",
                "reuse": "Revalidate through this service before use; not a detached authorization."}}

    def validate(self, package, result):
        """Reject edits, stale evidence and stripped obligations before downstream use."""
        try:
            expected = self.assemble(result, token_budget=package["budget"]["limit"])
            if encoded(package) != encoded(expected):
                raise EvidenceIntegrityError("m8_altered_stale_or_obligation_stripped_package")
        except (KeyError, TypeError) as exc:
            raise EvidenceIntegrityError("m8_invalid_package") from exc
        return True

    def serialize(self, package, result):
        self.validate(package, result)
        return encoded(package)
