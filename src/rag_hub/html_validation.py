"""HTML evidence contribution to the existing QA owner, never an eligibility engine.

A read-only lexical source scan verifies persisted DOM claims. It does not select
an article, regenerate parser outputs, execute a browser or establish semantics.
"""

import json
import re
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from rag_hub.acquire import digest, local_path
from rag_hub.html_corpus import MANIFEST, load_corpus
from rag_hub.schemas import ParsedBlock, SourceManifest
from rag_hub.shared.evidence import Check
from rag_hub.validation_models import ValidationResult

VERSION = "html-QA-evidence-2.0"
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
INLINE = {
    "a",
    "abbr",
    "b",
    "bdi",
    "bdo",
    "br",
    "cite",
    "code",
    "del",
    "em",
    "i",
    "kbd",
    "mark",
    "q",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "u",
    "var",
    "wbr",
}
OMIT = {"script", "style", "noscript", "template", "nav", "footer", "button", "svg"}
CONTROL_CLASSES = {
    "headerlink",
    "heading-anchor",
    "anchor",
    "copy-button",
    "toc",
    "edit-page",
    "pagination-links",
    "feedback",
    "page-footer",
    "md-source-file",
    "sr-only",
    "source-links",
}
SEMANTIC_ATTRS = {
    "id",
    "href",
    "src",
    "alt",
    "title",
    "class",
    "role",
    "hidden",
    "aria-hidden",
    "aria-label",
    "aria-labelledby",
    "aria-controls",
    "data-state",
    "open",
    "type",
    "start",
    "value",
    "rowspan",
    "colspan",
    "scope",
    "headers",
    "tabindex",
    "data-as",
    "srcset",
    "width",
    "height",
    "loading",
}


def furniture(node):
    attrs = node.get("attrs", {})
    return (
        node.get("tag") in OMIT
        or attrs.get("role") in {"navigation", "banner", "contentinfo"}
        or bool(set((attrs.get("class") or "").split()) & CONTROL_CLASSES)
        or attrs.get("id")
        in {"table-of-contents", "on-this-page", "feedback", "pagination", "in-article-cta"}
        or (
            node.get("tag") == "a"
            and attrs.get("aria-label") in {"Navigate to header", "Direct link to heading"}
        )
    )


class SourceIndex(HTMLParser):
    """Lexical offsets/path index only; independent of the maintained HTML parser."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.nodes = {}
        self.root = {
            "tag": "document",
            "path": "/document[1]",
            "start": 0,
            "end": len(text),
            "attrs": {},
            "children": [],
            "counts": Counter(),
            "parent": None,
        }
        self.stack = [self.root]
        self.repairs = []
        self.feed(text)
        self.close()
        for node in self.stack[1:]:
            node["end"] = len(text)
            self.repairs.append(node["path"])

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.position()
        # Optional closing tags are a lexical HTML rule, not a paragraph join.
        close = (
            {"li"}
            if tag == "li"
            else {"td", "th"}
            if tag in {"td", "th"}
            else {"td", "th", "tr"}
            if tag == "tr"
            else {"p"}
            if tag
            in {
                "p",
                "div",
                "section",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "ul",
                "ol",
                "pre",
                "table",
            }
            else set()
        )
        for i in range(len(self.stack) - 1, 0, -1):
            node = self.stack[i]
            if node["tag"] in close:
                if tag == "li" and any(n["tag"] in {"ul", "ol"} for n in self.stack[i + 1 :]):
                    break
                for n in self.stack[i:]:
                    n["end"] = start
                del self.stack[i:]
                break
            if node["tag"] in {"table", "ul", "ol"}:
                break
        parent = self.stack[-1]
        parent["counts"][tag] += 1
        path = f"{parent['path']}/{tag}[{parent['counts'][tag]}]"
        node = {
            "tag": tag,
            "path": path,
            "start": start,
            "end": start + len(self.get_starttag_text()),
            "attrs": dict(attrs),
            "children": [],
            "counts": Counter(),
            "parent": parent,
        }
        self.nodes[path] = node
        parent["children"].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                end = self.text.find(">", self.position()) + 1
                for node in self.stack[i:]:
                    node["end"] = end
                del self.stack[i:]
                return

    def add_text(self, raw):
        self.stack[-1]["children"].append(
            {"text": unescape(raw), "start": self.position(), "end": self.position() + len(raw)}
        )

    def handle_data(self, data):
        # HTMLParser does not decode entities within script/style data.
        if self.stack[-1]["tag"] in {"script", "style"}:
            return
        self.add_text(data)

    def reference(self, prefix, name):
        raw = prefix + name
        if self.text[self.position() + len(raw) :].startswith(";"):
            raw += ";"
        self.add_text(raw)

    def handle_entityref(self, name):
        self.reference("&", name)

    def handle_charref(self, name):
        self.reference("&#", name)


def nodes(node):
    yield node
    for child in node.get("children", []):
        yield from nodes(child)


def rendered(node, exact=False):
    if "text" in node:
        return node["text"]
    if furniture(node):
        return ""
    if node["tag"] == "br":
        return "\n"
    if node["tag"] == "img":
        return node["attrs"].get("alt") or ""
    exact = exact or node["tag"] == "pre"
    value = "".join(rendered(c, exact) for c in node["children"])
    if exact:
        return value
    value = re.sub(r"[\t\r\n\f ]+", " ", value)
    return value + (
        "\n" if node["tag"] not in INLINE or node["attrs"].get("data-as") == "p" else ""
    )


def canonical_text(node, code=False):
    value = rendered(node, code)
    return value if code else re.sub(r"[\t\r\n\f ]+", " ", value).strip()


def load_documents(root):
    """Verify all frozen HTML artifacts offline before accepting evidence bindings."""
    root = Path(root).resolve()
    load_corpus(root, admitted_only=False, include_structure=True)
    manifest = json.loads(local_path(root, MANIFEST).read_bytes())
    documents = {}
    for entry in manifest["sources"]:
        values = {
            name: json.loads(local_path(root, entry["paths"][name]["path"]).read_bytes())
            for name in ("source", "parsed", "normalized", "acquisition")
        }
        source = SourceManifest.model_validate(values["source"])
        raw = local_path(root, source.raw_path).read_bytes()
        snapshot = local_path(root, source.snapshot_path).read_bytes()
        if raw != snapshot or digest(raw) != source.raw_sha256 or len(raw) != source.byte_size:
            raise ValueError("html_source_snapshot_identity_mismatch")
        if values["acquisition"]["requested_url"] != str(source.canonical_url) or values[
            "acquisition"
        ]["final_url"] != str(source.original_url):
            raise ValueError("html_acquisition_URL_mismatch")
        if (
            len(values["parsed"]["records"]) != len(values["normalized"]["records"])
            or len(values["normalized"]["records"]) != entry["hold_count"]
        ):
            raise ValueError("html_persisted_record_coverage_mismatch")
        documents[source.doc_id] = {
            **values,
            "source": source,
            "raw": raw,
            "snapshot": snapshot,
            "corpus_id": manifest["corpus_identity_sha256"],
            "entry": entry,
            "manifest_sha256": digest(local_path(root, MANIFEST).read_bytes()),
            "bindings_verified": True,
        }
    return documents


def check_document(document):
    """Return per-Section applicable evidence. PASS is a technical assertion only."""
    source = document["source"]
    raw = document["raw"]
    charset = document["acquisition"].get("charset", "utf-8")
    text = raw.decode(charset, errors="strict")
    index = SourceIndex(text)
    parsed, normalized = document["parsed"], document["normalized"]
    normal = {r["section"]["block_ids"][0]: r for r in normalized["records"]}
    heading_states = {(): []}
    contexts = {c["dom_path"]: c for c in parsed["containers"]}
    positions = []
    results = {}
    intervals = [r["raw_char_span"] for r in parsed["records"]]

    def active_leaves(node):
        if furniture(node):
            return
        if "text" in node:
            if node["text"].strip():
                yield node
            return
        for child in node["children"]:
            yield from active_leaves(child)

    body = index.nodes.get(parsed["body_dom_path"])
    bases = [body] if body else []
    primary = next(
        (
            n
            for n in index.nodes.values()
            if n["tag"] == "h1" and not any(furniture(a) for a in lineage(n))
        ),
        None,
    )
    if primary and body and primary["start"] < body["start"]:
        bases.append(primary)
    missing_intervals = [
        [leaf["start"], leaf["end"]]
        for base in bases
        for leaf in active_leaves(base)
        if not any(a <= leaf["start"] and leaf["end"] <= b for a, b in intervals)
    ]

    def matches_tree(tree, actual):
        if "text" in tree:
            return tree.get("raw_char_span") == [actual.get("start"), actual.get("end")] and tree[
                "text"
            ] == actual.get("text")
        if tree.get("tag") != actual.get("tag") or tree.get("dom_path") != actual.get("path"):
            return False
        if tree.get("excluded"):
            return bool(furniture(actual))
        if tree.get("raw_char_span") != [actual["start"], actual["end"]]:
            return False
        attrs = {k: v for k, v in actual["attrs"].items() if k in SEMANTIC_ATTRS}
        for key in ("href", "src"):
            if attrs.get(key):
                attrs["resolved_" + key] = urljoin(str(source.canonical_url), attrs[key])
        if tree.get("attrs") != attrs:
            return False
        children = tree.get("children", [])
        return len(children) == len(actual["children"]) and all(
            matches_tree(t, a) for t, a in zip(children, actual["children"], strict=True)
        )

    for record in parsed["records"]:
        block = ParsedBlock.model_validate(record["block"])
        norm = normal.get(block.block_id)
        section = norm["section"] if norm else {}
        checks = {}

        def put(name, ok=None, reason="", *, applicable=True, target=checks):
            target[name] = {
                "outcome": "not_applicable"
                if not applicable
                else "HOLD"
                if ok is None
                else "PASS"
                if ok
                else "FAIL",
                "reason": reason,
            }

        put(
            "original_snapshot_identity",
            digest(raw) == source.raw_sha256
            and raw == document.get("snapshot")
            and len(raw) == source.byte_size,
            "raw bytes / immutable snapshot / SourceManifest",
        )
        put(
            "corpus_artifact_bindings",
            True if document.get("bindings_verified") is True else None,
            "manifest and every persisted artifact verified offline"
            if document.get("bindings_verified")
            else "trusted manifest verification missing",
        )
        start, end = record["raw_char_span"]
        valid_span = type(start) is int and type(end) is int and 0 <= start < end <= len(text)
        put(
            "raw_source_span",
            valid_span and digest(text[start:end].encode(charset)) == record["raw_fragment_sha256"],
            "Unicode raw interval and fragment hash",
        )
        actual = index.nodes.get(record["dom_path"])
        synthetic = (
            record["classification"] == "unknown" and record["source_tree"]["tag"] == "unknown"
        )
        if synthetic:
            parent_path = record["dom_path"].rsplit("/inline-run[", 1)[0]
            parent = index.nodes.get(parent_path)
            children = (
                [c for c in parent["children"] if start <= c["start"] and c["end"] <= end]
                if parent
                else []
            )
            actual = {
                "tag": "unknown",
                "path": record["dom_path"],
                "attrs": {},
                "start": start,
                "end": end,
                "children": children,
                "parent": parent,
            }
        traceable = (
            actual is not None and valid_span and [actual["start"], actual["end"]] == [start, end]
        )
        put(
            "DOM_locator_traceability",
            traceable and matches_tree(record["source_tree"], actual) if actual else False,
            "lexical source path, tag, attributes, complete children and offsets",
        )
        expected = (
            canonical_text(actual, record["classification"] == "code_block") if actual else None
        )
        put(
            "exact_source_text",
            expected == block.content if expected is not None else False,
            "independent lexical source text, HTML entity/whitespace contract",
        )
        put(
            "Section_lineage_and_normalization",
            bool(norm)
            and section.get("block_ids") == [block.block_id]
            and section.get("raw_sha256") == source.raw_sha256 == block.raw_sha256
            and section.get("snapshot_id") == source.snapshot_id == block.snapshot_id
            and section.get("heading_path") == list(block.heading_path)
            and section.get("locators") == [block.locator.model_dump(mode="json")]
            and section.get("normalized_sha256") == digest(section.get("text", "").encode())
            and all(
                norm.get(k) == record.get(k)
                for k in (
                    "classification",
                    "dom_path",
                    "raw_char_span",
                    "raw_fragment_sha256",
                    "source_tree",
                    "contexts",
                    "transformations",
                )
            ),
            "exact parsed-to-normalized lineage and structural evidence",
        )
        marker = "~~~~" if "```" in block.content else "```"
        expected_norm = (
            f"{marker}{block.language or ''}\n{block.content}{'' if block.content.endswith(chr(10)) else chr(10)}{marker}"
            if block.block_type == "code"
            else block.content
        )
        put(
            "normalized_text_fidelity",
            section.get("text") == expected_norm,
            "only declared canonical code fence may transform text",
        )
        put(
            "code_block_fidelity",
            expected == block.content and section.get("text") == expected_norm,
            "code whitespace/body and canonical fence",
            applicable=block.block_type == "code",
        )
        positions.append((start, end, block.block_id))
        previous = positions[-2] if len(positions) > 1 else None
        put(
            "reading_order",
            previous is None or start >= previous[1],
            "nonoverlapping original source intervals; visual/CSS order remains unverified",
        )
        kind = record["classification"]
        is_paragraph = kind == "paragraph"
        put(
            "paragraph_element_boundaries",
            bool(actual)
            and (
                actual["tag"] == "p"
                or actual["tag"] == "span"
                and actual["attrs"].get("data-as") == "p"
            ),
            "complete source paragraph element; semantic completeness is separately unverified",
            applicable=is_paragraph,
        )
        scope = tuple(
            p
            for p in record["contexts"]
            if p in contexts and contexts[p]["classification"] in {"tabpanel", "expandable"}
        )
        if scope not in heading_states:
            heading_states[scope] = list(heading_states.get(scope[:-1], heading_states[()]))
        headings = heading_states[scope]
        level = int(actual["tag"][1]) if actual and re.fullmatch(r"h[1-6]", actual["tag"]) else None
        if level:
            headings[:] = [(n, t) for n, t in headings if n < level] + [(level, expected)]
        put(
            "heading_ownership",
            tuple(t for _, t in headings) == block.heading_path,
            "source heading sequence with tab/expandable scope restoration",
        )
        put(
            "heading_hierarchy",
            None if "source_heading_level_gap" in block.issues else True,
            "source heading gap requires scoped review"
            if "source_heading_level_gap" in block.issues
            else "declared levels retained",
        )
        resolved = all(
            p in contexts
            and p in index.nodes
            and index.nodes[p]["start"] <= start
            and end <= index.nodes[p]["end"]
            for p in record["contexts"]
        )
        put(
            "context_locator_bindings",
            resolved,
            "every declared container resolves and encloses the source observation",
        )
        put(
            "context_dependencies",
            None if record["contexts"] else True,
            "callout, footnote, alternative-panel or expandable semantics require review"
            if record["contexts"]
            else "no declared container dependency; implicit semantics not certified",
        )
        current = actual
        contaminated = False
        hidden = False
        while current:
            contaminated |= bool(furniture(current))
            attrs = current.get("attrs", {})
            hidden |= (
                "hidden" in attrs
                or attrs.get("aria-hidden") == "true"
                or bool(
                    re.search(
                        r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style") or ""
                    )
                )
            )
            current = current.get("parent")
        put(
            "navigation_furniture",
            not contaminated,
            "explicit raw tag/role/control ancestors excluded; semantic relevance remains unverified",
        )
        put(
            "hidden_dynamic_visual_restrictions",
            None
            if hidden
            or block.issues
            or kind
            in {"image", "figure", "equation", "caption", "unknown", "table", "definition_list"}
            else True,
            "unresolved content stays restricted"
            if hidden or block.issues
            else "no explicit specialized hazard on this observation",
        )
        put(
            "list_structure",
            traceable and matches_tree(record["source_tree"], actual) if actual else False,
            "full nested list/item markup and source spans; no semantic certification",
            applicable=kind in {"ordered_list", "unordered_list"},
        )
        put(
            "table_structure",
            traceable and matches_tree(record["source_tree"], actual) if actual else False,
            "all raw rows/cells/header/rowspan/colspan attributes retained; numerical associations stay HOLD",
            applicable=kind == "table",
        )
        put(
            "citations_provenance",
            str(block.locator.url) == str(source.canonical_url)
            and block.doc_id == source.doc_id
            and block.locator.line_start == text.count("\n", 0, start) + 1
            and block.locator.line_end == text.count("\n", 0, end) + 1
            and (
                not block.locator.anchor
                or any(
                    n.get("attrs", {}).get("id") == block.locator.anchor for n in lineage(actual)
                )
            ),
            "source URL, line interval and source-backed anchor ancestry",
        )
        put(
            "body_text_accounting",
            body is not None
            and not missing_intervals
            and not parsed["accounting"]["unassigned_body_text"],
            "independent selected-body lexical leaf coverage; missing raw intervals="
            + str(missing_intervals)
            + "; whole-page semantic completeness unverified",
        )
        if index.repairs or parsed["dom_repairs"]:
            put("DOM_repairs", None, "ambiguous/unclosed DOM requires review")
        technical = (
            "FAIL"
            if any(c["outcome"] == "FAIL" for c in checks.values())
            else "HOLD"
            if any(c["outcome"] == "HOLD" for c in checks.values())
            else "PASS"
        )
        results[section.get("section_id", block.block_id)] = {
            "section_id": section.get("section_id"),
            "block_id": block.block_id,
            "classification": kind,
            "dom_path": record["dom_path"],
            "raw_char_span": [start, end],
            "checks": checks,
            "technical_outcome": technical,
            "independent_source_fidelity": "HOLD",
            "content_qualification": "not_established",
            "source_restriction": "pending_independent_scoped_review_no_source_wide_certification",
        }
    return results


def lineage(node):
    while node:
        yield node
        node = node.get("parent")


def enrich_result(result, section, context, policy):
    """Format evidence seam called by staged validate_section; no policy override."""
    values = result.model_dump()
    reasons = set(result.reasons) - {"unsupported_source_format"}
    document = (getattr(context, "html_evidence", None) or {}).get(section.doc_id)
    evidence = document.get("section_checks", {}).get(section.section_id) if document else None
    if evidence is None:
        values["checks"]["html_evidence"] = "manual_required"
        reasons.add("html_bound_evidence_missing")
    else:
        if (
            document["source"].raw_sha256 != section.raw_sha256
            or context.raw.get(section.doc_id) != document["raw"]
        ):
            raise ValueError("HTML_QA_context_source_mismatch")
        frozen = next(
            (
                r
                for r in document["normalized"]["records"]
                if r["section"]["section_id"] == section.section_id
            ),
            None,
        )
        original = next(
            (
                r["block"]
                for r in document["parsed"]["records"]
                if r["block"]["block_id"] in section.block_ids
            ),
            None,
        )
        current_block = (
            context.blocks.get(section.block_ids[0]) if len(section.block_ids) == 1 else None
        )
        if (
            frozen is None
            or section.model_dump(mode="json") != frozen["section"]
            or current_block is None
            or current_block.model_dump(mode="json") != original
        ):
            values["checks"]["html_current_section_binding"] = "fail"
            reasons.add("html_current_section_binding_fail")
            values["blocking_integrity"] = True
        for name, check in evidence["checks"].items():
            if check["outcome"] == "not_applicable":
                continue
            values["checks"]["html_" + name] = {
                "PASS": "pass",
                "HOLD": "manual_required",
                "FAIL": "fail",
            }[check["outcome"]]
            if check["outcome"] != "PASS":
                reasons.add("html_" + name + "_" + check["outcome"].lower())
        if any(c["outcome"] == "FAIL" for c in evidence["checks"].values()):
            values["blocking_integrity"] = True
        values["risk"] = (
            "high"
            if values["blocking_integrity"]
            or set(result.reasons) - {"unsupported_source_format"}
            or evidence["technical_outcome"] != "PASS"
            else "medium"
        )
    # These restrictions are never cleared by a technical PASS or a receipt preview.
    if values["blocking_integrity"]:
        values["checks"]["integrity"] = "fail"
    reasons.update({"html_independent_source_review_required", "html_source_qualification_pending"})
    values["checks"]["source_fidelity"] = "manual_required"
    values["eligible_automatic"] = False
    values["reasons"] = tuple(sorted(reasons))
    return ValidationResult.model_validate(values)


def fidelity(data, source, blocks, sections, options):
    """Adapter contributes required dimensions; source semantics remain pending."""
    return [
        Check(
            name=name,
            dimension="source_fidelity",
            outcome="pending",
            evidence=("HTML-bound-source-and-section-checks",),
        )
        for name in ("source_text", "source_locations", "source_order", "source_membership")
    ]
