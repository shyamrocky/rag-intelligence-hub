"""Optional, offline M4 BGE adapter. Heavy dependencies stay in tools/embeddings.

CPU float32, CLS pooling, L2 normalization and untruncated tokenizer parity are
explicit. No remote code, implicit downloads, query search or vector database.
"""

import inspect
import json
from importlib.metadata import version
from pathlib import Path

from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import sha


def validate_vectors(vectors, count, dimension):
    import numpy as np

    if (vectors.shape != (count, dimension) or vectors.dtype != np.dtype("float32")
            or not np.isfinite(vectors).all()
            or not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=2e-6, rtol=0)):
        raise ValueError("invalid_embedding_shape_dtype_finiteness_or_norm")


class LocalBGE:
    def __init__(self, root, *, configuration, expected_sha256):
        import torch
        from sentence_transformers import SentenceTransformer, models

        self.bound = BoundFiles(root)
        self.config_sha256 = expected_sha256
        self.spec = json.loads(self.bound.bind(configuration, expected_sha256))
        if (self.spec["schema"] != "local-embedding-model-1.0"
                or self.spec["model_repo"] != "BAAI/bge-small-en-v1.5"
                or self.spec["revision"] != "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
                or self.spec["encoding"] != {"device": "cpu", "dtype": "float32",
                    "pooling": "CLS", "normalize_embeddings": True, "dimension": 384,
                    "max_input_tokens": 512, "document_prompt": "", "batch_size": 16,
                    "threads": 1, "seed": 0, "attention": "eager"}):
            raise ValueError("unsupported_embedding_configuration")
        for package, expected in self.spec["runtime_versions"].items():
            if version(package) != expected:
                raise ValueError(f"embedding_runtime_version_changed:{package}")
        for path, digest in self.spec["bound_files"].items():
            self.bound.bind(path, digest)
        self.tokenizer = PinnedBgeTokenizer(root)
        for name, ref in self.tokenizer.spec["files"].items():
            model_path = str(Path(self.spec["model_path"]) / name)
            if self.spec["bound_files"].get(model_path) != ref["sha256"]:
                raise ValueError("embedding_M2_tokenizer_asset_mismatch")
        torch.manual_seed(0)
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.model = SentenceTransformer(
            str(self.bound.path(self.spec["model_path"])), device="cpu", local_files_only=True,
            trust_remote_code=False, model_kwargs={"use_safetensors": True,
                "dtype": torch.float32, "attn_implementation": "eager"})
        self.model.eval()
        modules = list(self.model.children())
        if ([type(m) for m in modules] != [models.Transformer, models.Pooling, models.Normalize]
                or self.model.max_seq_length != 512
                or self.model.get_sentence_embedding_dimension() != 384
                or self.model.prompts != {"query": "", "document": ""}
                or self.model.default_prompt_name is not None):
            raise ValueError("embedding_model_pipeline_changed")
        pooling = modules[1].get_config_dict()
        if (not pooling["pooling_mode_cls_token"] or any(v for k, v in pooling.items()
                if k.startswith("pooling_mode_") and k != "pooling_mode_cls_token")):
            raise ValueError("embedding_pooling_changed")
        if (any(p.dtype != torch.float32 for p in self.model.parameters())
                or any(m.training for m in self.model.modules())):
            raise ValueError("embedding_dtype_or_eval_mode_changed")
        self.loaded_components = {}
        for cls in [SentenceTransformer, models.Transformer, models.Pooling, models.Normalize,
                    type(modules[0].auto_model), type(modules[0].tokenizer)]:
            p = Path(inspect.getfile(cls))
            self.loaded_components[cls.__module__ + "." + cls.__name__] = sha(p.read_bytes())
        self.bound.check()

    def token_ids(self, texts, limits):
        self.bound.check()
        if len(texts) != len(limits) or not texts:
            raise ValueError("embedding_empty_or_misaligned_input")
        ids = []
        for text, limit in zip(texts, limits, strict=True):
            if (not isinstance(text, str) or not text or type(limit) is not int
                    or limit not in {384, 512}):
                raise ValueError("embedding_invalid_input_or_budget")
            exact = self.tokenizer.encode(text).ids
            if len(exact) > limit:
                raise ValueError("embedding_over_budget_no_truncation")
            ids.append(exact)
        # Sentence Transformers preprocesses whitespace and pads batches. Compare
        # its actual unpadded tokens, not merely the tokenizer filename/version.
        features = self.model.tokenize(texts)
        actual = [r[m.bool()].tolist() for r, m in zip(
            features["input_ids"], features["attention_mask"], strict=True)]
        if actual != ids:
            raise ValueError("embedding_runtime_tokenization_or_truncation_mismatch")
        self.bound.check()
        return ids

    def encode(self, texts, limits):
        self.token_ids(texts, limits)
        vectors = self.model.encode(texts, batch_size=self.spec["encoding"]["batch_size"],
            show_progress_bar=False, convert_to_numpy=True, precision="float32",
            normalize_embeddings=True, prompt="", device="cpu")
        validate_vectors(vectors, len(texts), self.spec["encoding"]["dimension"])
        self.bound.check()
        return vectors

    def verify_cls_normalization(self, texts, limits):
        import numpy as np
        import torch

        self.token_ids(texts, limits)
        with torch.inference_mode():
            features = self.model.tokenize(texts)
            hidden = self.model[0](features)["token_embeddings"][:, 0, :]
            direct = torch.nn.functional.normalize(hidden, p=2, dim=1).cpu().numpy()
        vectors = self.encode(texts, limits)
        if not np.allclose(vectors, direct, atol=2e-6, rtol=2e-6):
            raise ValueError("embedding_CLS_normalization_control_failed")
        return {"samples": len(texts), "max_abs_difference": float(np.max(abs(vectors - direct))),
                "pooling": "CLS", "normalization": "L2", "status": "PASS"}
