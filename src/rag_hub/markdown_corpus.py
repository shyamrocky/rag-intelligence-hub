"""Durable C04 view of existing MDX records and historical QA; no new decisions.

The canonical parser and Section identities are reused unchanged. Supplemental
syntax/offset evidence is for offline structural consumers, not MDX execution.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from markdown_it import MarkdownIt

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode, immutable
from rag_hub.parse_markdown import TITLE, WRAPPER, parse_markdown
from rag_hub.schemas import ParsedBlock, Section, SourceManifest
from rag_hub.source_fidelity import check_markdown

MANIFEST = "data/manifests/markdown/corpus-manifest.json"
QA_RUN = "bf9ec63f85912861a86677647d2056a6e23a7e0758315682cec29d78c0fe4580"


def structure(raw, blocks):
    """Retain whole source spans, list/quote/inline syntax and MDX boundaries."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    char_offsets, byte_offsets = [0], [0]
    for line in lines:
        char_offsets.append(char_offsets[-1] + len(line))
        byte_offsets.append(byte_offsets[-1] + len(line.encode("utf-8")))

    def span(start, end):
        fragment = "".join(lines[start:end])
        return {
            "lines_1based_inclusive": [start + 1, end],
            "chars_0based_end_exclusive": [char_offsets[start], char_offsets[end]],
            "bytes_0based_end_exclusive": [byte_offsets[start], byte_offsets[end]],
            "raw_fragment_sha256": digest(fragment.encode("utf-8")),
        }

    covered, blocked, records, containers, stack = set(), set(), [], [], []
    for block in blocks:
        start, end = block.locator.line_start - 1, block.locator.line_end
        covered.update(range(start, end))
        records.append({"block": block.model_dump(mode="json"), "source_span": span(start, end)})
        if block.block_type in ("code", "metadata"):
            blocked.update(range(start, end))
        if block.block_type != "metadata":
            continue
        match = WRAPPER.fullmatch(lines[start].rstrip("\r\n"))
        if not match:
            raise ValueError("unrecognized_existing_mdx_boundary")
        closing, tag, attrs = match.groups()
        if closing:
            if not stack or stack[-1]["tag"] != tag:
                raise ValueError("unbalanced_existing_mdx_boundary")
            container = stack.pop()
            container["closing_block_id"] = block.block_id
            container["source_span"] = span(container.pop("start"), end)
        else:
            title = TITLE.search(attrs or "")
            container = {
                "tag": tag,
                "label": title[1] if title else None,
                "opening_block_id": block.block_id,
                "parent_opening_block_id": stack[-1]["opening_block_id"] if stack else None,
                "start": start,
            }
            containers.append(container)
            stack.append(container)
    if stack:
        raise ValueError("unclosed_existing_mdx_boundary")
    missing = [n + 1 for n, line in enumerate(lines) if line.strip() and n not in covered]
    if missing:
        raise ValueError("unaccounted_nonblank_source_lines: " + str(missing))

    def token_record(token, start):
        result = {
            "type": token.type,
            "tag": token.tag,
            "nesting": token.nesting,
            "level": token.level,
            "content": token.content,
            "markup": token.markup,
            "attrs": token.attrs,
            "children": [token_record(t, start) for t in token.children or []],
        }
        if token.map is not None:
            a, b = token.map
            result["source_span"] = span(start + a, start + b)
        return result

    syntax = []
    md = MarkdownIt("commonmark", {"html": False})
    start = 0
    while start < len(lines):
        if start in blocked:
            start += 1
            continue
        end = start + 1
        while end < len(lines) and end not in blocked:
            end += 1
        syntax.extend(token_record(t, start) for t in md.parse("".join(lines[start:end])))
        start = end
    return {
        "records": records,
        "mdx_containers": containers,
        "markdown_syntax": syntax,
        "source_lines": len(lines),
        "unaccounted_nonblank_source_lines": missing,
        "offset_convention": "UTF-8 bytes and Unicode chars: zero-based, end-exclusive; lines one-based inclusive",
        "unsupported_regions": [r["block"]["block_id"] for r in records if r["block"]["issues"]],
    }


def checked_json(root, path, bindings):
    data = local_path(root, path).read_bytes()
    bindings[path] = digest(data)
    return json.loads(data)


def build(root):
    root = Path(root).resolve()
    bindings = {}
    policy = checked_json(root, "config/validation-policy.json", bindings)
    run = "data/ingestion/" + policy["input_run_id"]
    old = {}
    for name, expected in policy["artifact_sha256"].items():
        path = run + "/" + name
        data = local_path(root, path).read_bytes()
        if digest(data) != expected:
            raise ValueError("historical_ingestion_binding_mismatch: " + name)
        bindings[path] = expected
        old[name] = (
            json.loads(data)
            if name.endswith(".json")
            else [json.loads(l) for l in data.splitlines()]
        )
    source = SourceManifest.model_validate(
        next(s for s in old["manifest.json"] if s["doc_id"] == "C04")
    )
    for path in (source.raw_path, source.snapshot_path):
        data = local_path(root, path).read_bytes()
        if len(data) != source.byte_size or digest(data) != source.raw_sha256:
            raise ValueError("C04_raw_snapshot_mismatch")
        bindings[str(path)] = source.raw_sha256
    raw = local_path(root, source.raw_path).read_bytes()
    blocks = [ParsedBlock.model_validate(b) for b in old["blocks.jsonl"] if b["doc_id"] == "C04"]
    sections = [Section.model_validate(s) for s in old["sections.jsonl"] if s["doc_id"] == "C04"]
    if parse_markdown(raw, source) != blocks:
        raise ValueError("existing_C04_parser_no_longer_reproduces")
    block_map = {b.block_id: b for b in blocks}
    for section in sections:
        failures = check_markdown(section, block_map[section.block_ids[0]], raw)
        if failures:
            raise ValueError("C04_source_check_failed: " + str(failures))
    qa_dir = "data/validation/" + QA_RUN
    qa = {}
    for path in sorted(local_path(root, qa_dir).glob("*.json*")):
        relative = str(path.relative_to(root))
        data = path.read_bytes()
        bindings[relative] = digest(data)
        qa[path.name] = (
            json.loads(data)
            if path.suffix == ".json"
            else [json.loads(l) for l in data.splitlines()]
        )
    approved = qa["approved_manifest.json"]
    if (
        approved["input_run_id"] != policy["input_run_id"]
        or len(approved["approved"]) != 40
        or len(qa["holds.jsonl"]) != 1634
    ):
        raise ValueError("historical_QA_baseline_mismatch")
    decisions = {d["section_id"]: d for d in qa["decisions.jsonl"] if d["doc_id"] == "C04"}
    approved_ids = {d["section_id"] for d in approved["approved"]}
    if {s.section_id for s in sections} != set(decisions):
        raise ValueError("C04_historical_decision_coverage_mismatch")
    for section in sections:
        d = decisions[section.section_id]
        if (d["raw_sha256"], d["normalized_sha256"]) != (
            source.raw_sha256,
            section.normalized_sha256,
        ):
            raise ValueError("C04_decision_identity_mismatch")
        if (d["status"] == "approved_for_index") != (section.section_id in approved_ids):
            raise ValueError("C04_decision_manifest_disagreement")
    parsed = {"source": source.model_dump(mode="json"), **structure(raw, blocks)}
    span_map = {r["block"]["block_id"]: r["source_span"] for r in parsed["records"]}
    normalized = {
        "source": source.model_dump(mode="json"),
        "records": [
            {
                "section": s.model_dump(mode="json"),
                "source_span": span_map[s.block_ids[0]],
                "historical_qa_decision": decisions[s.section_id],
            }
            for s in sections
        ],
        "audit": [a for a in old["audit.jsonl"] if a["block_id"].startswith("C04:")],
        "status_note": "Section fields preserve the original ingestion snapshot; effective historical eligibility is only historical_qa_decision. No new approvals or demotions.",
    }
    report = {
        "engineering": "complete_existing_canonical_records_reused",
        "source_sha256": source.raw_sha256,
        "byte_size": len(raw),
        "blocks": len(blocks),
        "sections": len(sections),
        "block_counts": dict(Counter(b.block_type for b in blocks)),
        "section_counts": dict(Counter(s.block_type for s in sections)),
        "effective_historical_qa": dict(Counter(d["status"] for d in decisions.values())),
        "historical_approval_bases": dict(Counter(d["basis"] for d in approved["approved"])),
        "source_checks_pass": len(sections),
        "nonblank_line_accounting": "pass",
        "mdx_containers": len(parsed["mdx_containers"]),
        "unsupported_regions": parsed["unsupported_regions"],
        "independent_content_qualification": "no_new_review; existing approvals only",
        "source_readiness": "not_executed",
    }
    for path, payload in [
        ("data/parsed/markdown/C04.json", parsed),
        ("data/normalized/markdown/C04.json", normalized),
        ("data/validation/markdown/v1/C04.json", report),
    ]:
        immutable(local_path(root, path), encode(payload))
        bindings[path] = digest(encode(payload))
    implementation = {
        f"src/rag_hub/{name}.py": digest(local_path(root, f"src/rag_hub/{name}.py").read_bytes())
        for name in (
            "markdown_corpus",
            "parse_markdown",
            "normalize",
            "schemas",
            "source_fidelity",
            "acquire",
            "html_acquire",
        )
    }
    manifest = {
        "schema": "markdown-corpus-1.0",
        "documents": ["C04"],
        "source": source.model_dump(mode="json"),
        "historical_qa_run": QA_RUN,
        "artifacts": bindings,
        "implementation": implementation,
        "report": report,
        "source_readiness": "not_executed",
    }
    manifest["identity_sha256"] = digest(encode(manifest))
    immutable(local_path(root, MANIFEST), encode(manifest))
    return manifest


def load_corpus(root, *, admitted_only=True):
    """Verify persisted bytes and expose existing decisions; no parsing or QA run.

    Rows retain original Section models plus the effective historical decision.
    This read-only projection never mints receipts or rewrites Section statuses.
    """
    root = Path(root).resolve()
    manifest = json.loads(local_path(root, MANIFEST).read_bytes())
    if manifest.get("schema") != "markdown-corpus-1.0" or manifest.get("documents") != ["C04"]:
        raise ValueError("unsupported_markdown_manifest")
    if (
        digest(encode({k: v for k, v in manifest.items() if k != "identity_sha256"}))
        != manifest["identity_sha256"]
    ):
        raise ValueError("markdown_manifest_integrity_mismatch")
    for name, expected in (manifest["artifacts"] | manifest["implementation"]).items():
        if digest(local_path(root, name).read_bytes()) != expected:
            raise ValueError("markdown_artifact_integrity_mismatch: " + name)
    normalized = json.loads(local_path(root, "data/normalized/markdown/C04.json").read_bytes())
    parsed = json.loads(local_path(root, "data/parsed/markdown/C04.json").read_bytes())
    source = SourceManifest.model_validate(manifest["source"])
    if normalized["source"] != manifest["source"] or parsed["source"] != manifest["source"]:
        raise ValueError("markdown_source_identity_mismatch")
    qa_dir = "data/validation/" + manifest["historical_qa_run"]
    approved = json.loads(local_path(root, qa_dir + "/approved_manifest.json").read_bytes())
    exact = {r["section_id"]: r for r in approved["approved"]}
    decisions = {
        r["section_id"]: r
        for r in map(
            json.loads, local_path(root, qa_dir + "/decisions.jsonl").read_bytes().splitlines()
        )
    }
    rows = []
    seen = set()
    for record in normalized["records"]:
        section = Section.model_validate(record["section"])
        decision = record["historical_qa_decision"]
        if section.section_id in seen or (
            section.doc_id,
            section.snapshot_id,
            section.raw_sha256,
        ) != (source.doc_id, source.snapshot_id, source.raw_sha256):
            raise ValueError("foreign_or_duplicate_markdown_section")
        seen.add(section.section_id)
        if (
            decision != decisions.get(section.section_id)
            or decision["normalized_sha256"] != section.normalized_sha256
            or decision["raw_sha256"] != section.raw_sha256
        ):
            raise ValueError("markdown_historical_decision_mismatch")
        eligible = decision["status"] == "approved_for_index"
        if eligible and exact.get(section.section_id) != decision:
            raise ValueError("unbound_markdown_approval")
        if not admitted_only or eligible:
            rows.append({**record, "section": section, "source": source})
    return {"manifest": manifest, "records": rows, "structure": parsed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-offline", action="store_true")
    args = parser.parse_args()
    if args.verify_offline:
        corpus = load_corpus(args.root, admitted_only=False)
        print(
            json.dumps(
                {
                    "sections": len(corpus["records"]),
                    "historically_eligible": sum(
                        r["historical_qa_decision"]["status"] == "approved_for_index"
                        for r in corpus["records"]
                    ),
                }
            )
        )
    else:
        print(json.dumps(build(args.root)["report"]))


if __name__ == "__main__":
    main()
