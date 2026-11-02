"""Pinned, offline BGE tokenizer for the M2 pilot; no embedding model runtime."""

from importlib.metadata import version

from rag_hub.unified_bindings import BoundFiles

SPEC = "config/bge-tokenizer-v1.json"
SPEC_SHA256 = "03d41df1a646ed13d41bd8b485c573864da5821109e57750135bf94f0dbde577"


class PinnedBgeTokenizer:
    def __init__(self, root):
        import json

        from tokenizers import Tokenizer

        self.bound = BoundFiles(root)
        self.spec = json.loads(self.bound.bind(SPEC, SPEC_SHA256))
        for package, expected in self.spec["runtime_versions"].items():
            if version(package) != expected:
                raise ValueError(f"m2_runtime_version_changed:{package}")
        for ref in self.spec["files"].values():
            self.bound.bind(ref["path"], ref["sha256"])
        self.config = self.bound.json(self.spec["files"]["tokenizer_config.json"]["path"])
        model = self.bound.json(self.spec["files"]["config.json"]["path"])
        sentence = self.bound.json(self.spec["files"]["sentence_bert_config.json"]["path"])
        self.max_length = min(self.config["model_max_length"], model["max_position_embeddings"],
                              sentence["max_seq_length"])
        self.tokenizer = Tokenizer.from_file(str(self.bound.path(
            self.spec["files"]["tokenizer.json"]["path"])))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.special_tokens = self.tokenizer.num_special_tokens_to_add(False)
        if (self.max_length != self.spec["input_limit"]
                or self.special_tokens != self.spec["special_tokens"]
                or self.encode("").ids != [101, 102]):
            raise ValueError("m2_unqualified_tokenizer_configuration")

    def encode(self, text, *, special=True):
        self.bound.check()
        if self.tokenizer.truncation is not None or self.tokenizer.padding is not None:
            raise ValueError("m2_truncation_or_padding_enabled")
        return self.tokenizer.encode(text, add_special_tokens=special)

    def count(self, text, *, special=True):
        return len(self.encode(text, special=special).ids)

    def reference_tokenizer(self):
        """Independent asset path: construct BERT behavior from vocab + config.

        This corroborates configuration parity, not independent model accuracy.
        """
        from tokenizers import (
            AddedToken,
            Tokenizer,
            models,
            normalizers,
            pre_tokenizers,
            processors,
        )

        reference = Tokenizer(models.WordPiece.from_file(str(self.bound.path(
            self.spec["files"]["vocab.txt"]["path"])), unk_token=self.config["unk_token"]))
        reference.normalizer = normalizers.BertNormalizer(
            clean_text=True, handle_chinese_chars=self.config["tokenize_chinese_chars"],
            strip_accents=self.config["strip_accents"], lowercase=self.config["do_lower_case"])
        reference.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
        special_map = self.bound.json(self.spec["files"]["special_tokens_map.json"]["path"])
        reference.add_special_tokens([AddedToken(t, normalized=False, special=True)
                                      for t in special_map.values()])
        reference.post_processor = processors.TemplateProcessing(
            single="[CLS] $A [SEP]", pair="[CLS] $A [SEP] $B:1 [SEP]:1",
            special_tokens=[("[CLS]", 101), ("[SEP]", 102)])
        return reference

    def metadata(self):
        self.bound.check()
        return {"repo": self.spec["repo"], "revision": self.spec["revision"],
                "spec_sha256": SPEC_SHA256, "runtime_versions": self.spec["runtime_versions"],
                "max_length": self.max_length, "special_tokens": self.special_tokens,
                "truncation": False, "padding": False, "document_instruction": "",
                "bound_files": self.bound.fingerprints()}
