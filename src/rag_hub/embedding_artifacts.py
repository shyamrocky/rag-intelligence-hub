"""Versioned M4 vector inventory, not an index, retrieval or evidence authority."""

import copy
import json

from rag_hub.embedding_inputs import embedding_id, embedding_input
from rag_hub.local_embeddings import validate_vectors
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import encode, sha


class EmbeddingArtifacts:
    def __init__(self, root, catalog, *, selector):
        import numpy as np

        self.catalog = catalog
        self.bound = BoundFiles(root)
        path = self.bound.path(selector)
        selection = json.loads(self.bound.bind(selector, sha(path.read_bytes())))
        self.manifest = json.loads(self.bound.bind(
            selection["manifest_path"], selection["manifest_sha256"]))
        m = self.manifest
        if (selection["schema"] != "embedding-selection-1.0"
                or m["schema"] != "embedding-manifest-1.0"
                or m["authority"] != "DERIVED_VECTORS_NOT_EVIDENCE_AUTHORIZATION"
                or m["dimension"] != 384 or m["dtype"] != "float32"):
            raise ValueError("unsupported_embedding_artifact_schema")
        for path, digest in m["files"].items():
            self.bound.bind(path, digest)
        config = json.loads(self.bound.bind(m["model_configuration"]["path"],
                                           m["model_configuration"]["sha256"]))
        for path, digest in config["bound_files"].items():
            self.bound.bind(path, digest)
        self.bound.bind(m["catalog_selector"]["path"], m["catalog_selector"]["sha256"])
        selected = self.bound.json(m["catalog_selector"]["path"])
        if (selected["manifest_sha256"] != m["catalog_manifest_sha256"]
                or sha(encode(catalog.manifest)) != sha(encode(json.loads(
                    self.bound.bind(selected["manifest_path"], selected["manifest_sha256"]))))):
            raise ValueError("embedding_wrong_chunk_catalog")
        rows = catalog.list_chunks(limit=1000)["items"]
        records = [json.loads(line) for line in self.bound.path(m["records_path"]).read_text().splitlines()]
        inputs = [json.loads(line) for line in self.bound.path(m["inputs_path"]).read_text().splitlines()]
        if (len(records) != len(rows) or len(inputs) != len(rows)
                or m["chunks"] != len(rows) or m["units"] != len({r["unit_id"] for r in rows})):
            raise ValueError("embedding_incomplete_catalog")
        self.records = {}
        for i, (record, source, row) in enumerate(zip(records, inputs, rows, strict=True)):
            cid = record["chunk_id"]
            text_hash = sha(source["text"].encode())
            if (cid in self.records or cid != row["chunk_id"] or source["chunk_id"] != cid
                    or record["row_index"] != i or record["unit_id"] != row["unit_id"]
                    or record["chunk_sha256"] != sha(encode(row))
                    or record["input_text_sha256"] != text_hash
                    or record["embedding_id"] != embedding_id(
                        m["model_configuration"]["sha256"], cid, text_hash)
                    or not record["complete_parent_rehydration_required"]
                    or record["mandatory_evidence_refs"] != row["mandatory_evidence_refs"]
                    or record["parent_binding"] != row["parent_binding"]
                    or record["tokens_including_specials"] != row["token_count"]):
                raise ValueError("embedding_row_binding_or_order_changed")
            self.records[cid] = record
        self.vectors = np.load(self.bound.path(m["vectors_path"]), allow_pickle=False)
        validate_vectors(self.vectors, len(records), m["dimension"])
        for record in records:
            if record["vector_sha256"] != sha(self.vectors[record["row_index"]].tobytes()):
                raise ValueError("embedding_vector_row_hash_changed")
        self.check()

    def check(self):
        self.bound.check()
        self.catalog.check()

    def get_vector(self, chunk_id):
        """Vector + identity only; this grants no source-content/evidence access."""
        self.check()
        if chunk_id not in self.records:
            raise ValueError("unknown_embedding_chunk_id")
        row = self.records[chunk_id]
        return self.vectors[row["row_index"]].copy(), copy.deepcopy(row)

    def open_bound_chunk(self, chunk_id):
        """Resolve the complete parent using M3, never a detached artifact payload."""
        _, stored = self.get_vector(chunk_id)
        view = self.catalog.open_chunk(chunk_id)
        _, binding = embedding_input(view)
        if any(stored.get(k) != v for k, v in binding.items()):
            raise ValueError("embedding_live_parent_or_input_changed")
        self.check()
        return view
