"""Offline HTML ingestion and hash-checking loader; no eligibility or readiness engine."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode, immutable
from rag_hub.normalize import normalize_blocks
from rag_hub.parse_html import VERSION, parse_html
from rag_hub.schemas import ParsedBlock, Section, SourceManifest

MANIFEST = "data/manifests/html/corpus-manifest.json"


def source_from_receipt(spec, receipt):
    return SourceManifest(
        doc_id=spec["doc_id"],
        snapshot_id="sha256-" + receipt["raw_sha256"],
        canonical_url=spec["canonical_url"],
        original_url=receipt["final_url"],
        title=spec["title"],
        publisher=spec["publisher"],
        source_format="html",
        source_version=spec["source_version"],
        captured_at=receipt["retrieved_at"],
        byte_size=receipt["byte_size"],
        language="en",
        raw_path=Path(f"data/raw/html/{spec['doc_id']}.html"),
        snapshot_path=Path(f"data/snapshots/{receipt['raw_sha256']}/{spec['doc_id']}.html"),
        raw_sha256=receipt["raw_sha256"],
        rights_status="local_use_approved",
        acquisition_basis="Explicit owner-authorized private fixed-corpus HTML ingestion; no redistribution clearance",
    )


def normalize(parsed):
    blocks = [ParsedBlock.model_validate(r["block"]) for r in parsed["records"]]
    ordinary = [b for b in blocks if b.block_type != "metadata"]
    sections, audit, sidecars = normalize_blocks(ordinary)
    lookup = {s.block_ids[0]: s for s in sections}
    records = []
    for record, block in zip(parsed["records"], blocks, strict=True):
        section = lookup.get(block.block_id)
        if section is None:
            # Existing metadata removal is MDX markup-specific. Preserve unsupported
            # HTML content as explicit typed HOLD, without changing that shared rule.
            section = Section(
                section_id=f"{block.doc_id}:{block.raw_sha256[:12]}:{block.block_id.split(':')[-1]}:{block.content_sha256[:12]}",
                doc_id=block.doc_id,
                snapshot_id=block.snapshot_id,
                heading_path=block.heading_path,
                block_ids=(block.block_id,),
                text=block.content,
                locators=(block.locator,),
                normalized_sha256=block.content_sha256,
                raw_sha256=block.raw_sha256,
                block_type=block.block_type,
                verification_status="hold",
                index_status="hold",
                transformations=(),
                issues=block.issues or ("html_specialized_semantics_unverified",),
            )
        # Parser success is not content verification. There are no new approvals.
        section = section.model_copy(update={"verification_status": "hold"})
        records.append(
            {
                "section": section.model_dump(mode="json"),
                "classification": record["classification"],
                "dom_path": record["dom_path"],
                "raw_char_span": record["raw_char_span"],
                "raw_fragment_sha256": record["raw_fragment_sha256"],
                "source_tree": record["source_tree"],
                "contexts": record["contexts"],
                "transformations": record["transformations"],
            }
        )
    return {
        "normalization_version": VERSION,
        "records": records,
        "containers": parsed["containers"],
        "audit": audit,
        "sidecars": [s.model_dump(mode="json") for s in sidecars],
    }


def validation(raw, source, parsed, normalized, charset):
    decoded = raw.decode(charset)
    checks = Counter()
    failures = []

    def check(name, passed, detail):
        checks[name + ":total"] += 1
        checks[name + ":pass"] += bool(passed)
        if not passed:
            failures.append({"check": name, "detail": detail})

    check(
        "body_text_accounting",
        not parsed["accounting"]["unassigned_body_text"],
        "unassigned leaves",
    )
    check("title_present", bool(parsed["title"]), "missing H1/title")
    check("substantive_body", len(parsed["records"]) >= 3, "too few semantic records")
    check("section_count", len(parsed["records"]) == len(normalized["records"]), "section loss")
    previous = -1

    def leaves(tree):
        if "text" in tree:
            yield tree
        for child in tree.get("children", []):
            yield from leaves(child)

    def nodes(tree):
        if "tag" in tree:
            yield tree
        for child in tree.get("children", []):
            yield from nodes(child)

    from html import unescape

    for record, norm in zip(parsed["records"], normalized["records"], strict=True):
        block = ParsedBlock.model_validate(record["block"])
        section = Section.model_validate(norm["section"])
        start, end = record["raw_char_span"]
        detail = record["dom_path"]
        check(
            "raw_fragment_hash",
            digest(decoded[start:end].encode(charset)) == record["raw_fragment_sha256"],
            detail,
        )
        check("source_order", start >= previous, detail)
        previous = start
        check(
            "source_binding",
            section.raw_sha256 == source.raw_sha256 == block.raw_sha256
            and section.snapshot_id == source.snapshot_id,
            detail,
        )
        check("section_lineage", section.block_ids == (block.block_id,), detail)
        check(
            "hold_preservation",
            section.index_status == "hold" and not section.review_receipt,
            detail,
        )
        expected = "~~~~" if "```" in block.content else "```"
        if block.block_type == "code":
            fenced = f"{expected}{block.language or ''}\n{block.content}{'' if block.content.endswith(chr(10)) else chr(10)}{expected}"
            check("code_fidelity", section.text == fenced, detail)
        else:
            check("source_text_fidelity", section.text == block.content, detail)
        for leaf in leaves(record["source_tree"]):
            a, b = leaf["raw_char_span"]
            check("text_leaf_roundtrip", unescape(decoded[a:b]) == leaf["text"], detail)
        for node in nodes(record["source_tree"]):
            if node["tag"] in ("td", "th"):
                a, b = node["raw_char_span"]
                check("table_cell_source_span", start <= a <= b <= end, node["dom_path"])
            if node["tag"] in ("ol", "ul", "li"):
                a, b = node["raw_char_span"]
                check("list_nesting_source_span", start <= a <= b <= end, node["dom_path"])
    return {
        "doc_id": source.doc_id,
        "machine_consistency": "PASS" if not failures else "FAIL",
        "checks": dict(checks),
        "failures": failures,
        "classification_counts": dict(Counter(r["classification"] for r in parsed["records"])),
        "source_feature_counts": parsed["features"],
        "accounting": parsed["accounting"],
        "qa_eligible": 0,
        "independent_human_acceptance": "not_performed",
        "source_fidelity": "provisional_machine_and_engineering_inspection_only",
        "readiness": "not_executed",
        "dom_repairs": parsed["dom_repairs"],
    }


def build(root):
    root = root.resolve()
    config = json.loads(local_path(root, "config/html-sources.json").read_text())
    if len(config["sources"]) != 11 or {s["doc_id"] for s in config["sources"]} != {
        "C03",
        "C05",
        "C07",
        "C08",
        "C09",
        "C10",
        "C11",
        "C12",
        "C13",
        "C15",
        "C16",
    }:
        raise ValueError("fixed_html_cohort_changed")
    if (
        digest(local_path(root, config["authority_path"]).read_bytes())
        != config["authority_sha256"]
    ):
        raise ValueError("corpus_authority_changed")
    manifest = {
        "schema_version": "html-corpus-1.0",
        "parser_version": VERSION,
        "config_sha256": digest(local_path(root, "config/html-sources.json").read_bytes()),
        "implementation": {
            f"src/rag_hub/{n}.py": digest(Path(__file__).with_name(n + ".py").read_bytes())
            for n in (
                "parse_html",
                "html_acquire",
                "html_corpus",
                "schemas",
                "normalize",
                "acquire",
            )
        },
        "qa_eligibility": "all_new_records_hold_no_admission_performed",
        "source_readiness": "not_executed",
        "sources": [],
    }
    for spec in config["sources"]:
        doc = spec["doc_id"]
        receipt_path = f"data/raw/html/{doc}.acquisition.json"
        p = local_path(root, receipt_path)
        entry = {**spec, "paths": {}, "qa_eligible": 0}
        if not p.exists():
            entry.update(
                acquisition="blocked_no_successful_receipt",
                parsing="not_executed",
                normalization="not_executed",
                validation="blocked",
            )
            manifest["sources"].append(entry)
            continue
        receipt = json.loads(p.read_text())
        entry.update(
            acquisition=receipt["status"],
            acquired_version="sha256-" + receipt["raw_sha256"],
            retrieved_at=receipt["retrieved_at"],
            final_url=receipt["final_url"],
        )
        if receipt["status"] != "acquired":
            entry.update(
                parsing="blocked_response", normalization="not_executed", validation="blocked"
            )
            manifest["sources"].append(entry)
            continue
        source = source_from_receipt(spec, receipt)
        raw = local_path(root, source.raw_path).read_bytes()
        if digest(raw) != source.raw_sha256:
            raise ValueError(doc + ": raw_source_integrity_mismatch")
        immutable(local_path(root, source.snapshot_path), raw)
        parsed = parse_html(raw, source, charset=receipt["charset"])
        normalized = normalize(parsed)
        report = validation(raw, source, parsed, normalized, receipt["charset"])
        paths = {
            "raw": str(source.raw_path),
            "snapshot": str(source.snapshot_path),
            "acquisition": receipt_path,
            "source": f"data/parsed/html/{doc}.source.json",
            "parsed": f"data/parsed/html/{doc}.json",
            "normalized": f"data/normalized/html/{doc}.json",
            "validation": f"data/validation/html/v1/{doc}.json",
        }
        for name, payload in (
            ("source", source.model_dump(mode="json")),
            ("parsed", parsed),
            ("normalized", normalized),
            ("validation", report),
        ):
            immutable(local_path(root, paths[name]), encode(payload))
        entry.update(
            paths={
                name: {"path": path, "sha256": digest(local_path(root, path).read_bytes())}
                for name, path in paths.items()
            },
            parsing="persisted",
            normalization="persisted",
            validation=report["machine_consistency"],
            record_counts=report["classification_counts"],
            source_fidelity=report["source_fidelity"],
            independent_acceptance="not_performed",
            hold_count=len(normalized["records"]),
        )
        manifest["sources"].append(entry)
        print(doc, entry["validation"], sum(entry["record_counts"].values()), flush=True)
    manifest["corpus_identity_sha256"] = digest(encode(manifest))
    immutable(local_path(root, MANIFEST), encode(manifest))
    return manifest


def load_corpus(root, *, manifest_path=MANIFEST, admitted_only=True, include_structure=False):
    """Load verified persisted Sections offline. HOLD is excluded by default.

    admitted_only=False is for evidence review, never indexing permission.
    No network, HTML parsing, chunking or policy evaluation happens here.
    """
    root = root.resolve()
    manifest = json.loads(local_path(root, manifest_path).read_text())
    expected = manifest["corpus_identity_sha256"]
    if (
        digest(encode({k: v for k, v in manifest.items() if k != "corpus_identity_sha256"}))
        != expected
    ):
        raise ValueError("corpus_manifest_integrity_mismatch")
    for path, sha in manifest["implementation"].items():
        if digest(local_path(root, path).read_bytes()) != sha:
            raise ValueError("html_implementation_binding_mismatch")
    if (
        digest(local_path(root, "config/html-sources.json").read_bytes())
        != manifest["config_sha256"]
    ):
        raise ValueError("html_config_binding_mismatch")
    rows = []
    for entry in manifest["sources"]:
        for artifact in entry["paths"].values():
            if digest(local_path(root, artifact["path"]).read_bytes()) != artifact["sha256"]:
                raise ValueError("html_artifact_integrity_mismatch: " + artifact["path"])
        if entry.get("normalization") != "persisted":
            continue
        normalized = json.loads(local_path(root, entry["paths"]["normalized"]["path"]).read_text())
        contexts = {c["dom_path"]: c for c in normalized["containers"]}
        for record in normalized["records"]:
            section = Section.model_validate(record["section"])
            if section.index_status != "hold" or section.review_receipt:
                # This dataset has no admission receipts or authority to mint them.
                raise ValueError("unexpected_html_admission_requires_authoritative_QA")
            if not admitted_only:
                rows.append(
                    {
                        **record,
                        "section": section,
                        "context_metadata": [
                            contexts[p] for p in record["contexts"] if p in contexts
                        ],
                        "document_containers": normalized["containers"],
                    }
                    if include_structure
                    else section
                )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-offline", action="store_true")
    args = parser.parse_args()
    if args.verify_offline:
        sections = load_corpus(args.root, admitted_only=False)
        print(
            json.dumps(
                {
                    "sections_verified": len(sections),
                    "qa_eligible": 0,
                    "checked_at": datetime.now(UTC).isoformat(),
                }
            )
        )
    else:
        build(args.root)


if __name__ == "__main__":
    main()
