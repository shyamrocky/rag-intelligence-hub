"""Opt-in, source-bound PDF text qualification evidence for the sole shared QA owner.

No model inference, canonical mutation, default scope expansion or publisher audit.
Native replay proves original characters/positions, not mathematical or visual truth.
"""

import importlib
import json
import re
from collections import defaultdict
from importlib.metadata import version as installed_version
from itertools import pairwise
from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import model_validator

from rag_hub.acquire import digest, local_path
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_layout import native_layout
from rag_hub.schemas import ParsedBlock
from rag_hub.shared.contracts import read_source
from rag_hub.validation_models import QualityDecision
from rag_hub.validation_sampling import fingerprint

VERSION = "pdf-source-text-qualification-1.0"
RELEASE = "combined-pdf-text-qa-1.0"
HOME = "data/validation/pdf/text-recovery-v1"
POLICY = "config/pdf-text-qualification-policy.json"
RELEASE_PATH = "config/pdf-text-qa-successor.json"
RESIDUAL_RELEASE_PATH = "config/pdf-residual-qa-successor-v1.json"
SOURCE_IDS = {"C01", "C02", "C06", "C14"}
BAD = re.compile(r"[\x00-\x08\ufffd]")
CAPTION = re.compile(r"^(?:Figure|Fig\.|Table|TABLE)\s*[\dIVX]+(?:[.:\s])")
NUMERIC = re.compile(r"^[−+\-]?\d[\d.,%±*\s−+\-]*$")


class PdfTextDecision(QualityDecision):
    schema_version: Literal["pdf-text-scoped-decision-1.0"] = "pdf-text-scoped-decision-1.0"
    basis: Literal["scoped_pdf_source_qualification"] = "scoped_pdf_source_qualification"
    scope: dict
    resolved_restrictions: dict[str, str]

    @model_validator(mode="after")
    def bounded(self):
        if (
            self.status != "approved_for_index"
            or self.reasons
            or self.section_id not in self.scope.get("required_section_ids", [])
            or self.scope.get("consumption") != "verified_complete_unit_only"
            or self.scope.get("whole_source_ready") is not False
            or not self.scope.get("memberships")
            or self.doc_id not in SOURCE_IDS
        ):
            raise ValueError("invalid_pdf_text_scope")
        return self


def verify_release(root, path, expected):
    raw = local_path(root, path).read_bytes()
    release = json.loads(raw)
    if (
        not expected
        or digest(raw) != expected
        or release.get("version")
        not in {RELEASE, "combined-pdf-text-qa-1.1", "combined-pdf-residual-qa-1.0"}
    ):
        raise ValueError("invalid_pdf_text_release_selection")
    required = {
        "src/rag_hub/pdf_text_recovery.py",
        "src/rag_hub/pdf_text_handoff.py",
        "src/rag_hub/shared/qa.py",
        "src/rag_hub/validation_reviews.py",
        release.get("qualification_policy_path", POLICY),
    }
    if release.get("version") == "combined-pdf-residual-qa-1.0":
        required.add("src/rag_hub/pdf_residual_recovery.py")
    if not required <= release.get("files", {}).keys():
        raise ValueError("incomplete_pdf_text_release")
    changed = {
        name
        for name, sha in release["files"].items()
        if digest(local_path(root, name).read_bytes()) != sha
    }
    if changed:
        successor_path = (
            RESIDUAL_RELEASE_PATH
            if local_path(root, RESIDUAL_RELEASE_PATH).exists()
            else "config/pdf-text-qa-successor-v1-1.json"
        )
        if str(path) == successor_path or not changed <= {
            "src/rag_hub/pdf_text_recovery.py",
            "src/rag_hub/pdf_text_handoff.py",
            "src/rag_hub/html_handoff.py",
            "src/rag_hub/markdown_qualification.py",
            "src/rag_hub/pdf_publication.py",
        }:
            raise ValueError("pdf_text_component_changed: " + ", ".join(sorted(changed)))
        successor = verify_release(
            root, successor_path, digest(local_path(root, successor_path).read_bytes())
        )
        if successor.get("compatible_pdf_text_releases", {}).get(str(path)) != expected:
            raise ValueError("unapproved_pdf_text_predecessor")
    actual = successor["files"] if changed else release["files"]
    for name, sha in actual.items():
        if digest(local_path(root, name).read_bytes()) != sha:
            raise ValueError("pdf_text_component_changed: " + name)
        if name.startswith("src/rag_hub/") and name.endswith(".py"):
            module = importlib.import_module(name[4:-3].replace("/", "."))
            if Path(module.__file__).resolve() != Path(root).resolve() / name:
                raise ValueError("pdf_text_imported_component_mismatch")
    if release["dependencies"] != {n: installed_version(n) for n in release["dependencies"]}:
        raise ValueError("pdf_text_dependency_changed")
    return release


def fragment(block, start=0, end=None):
    if digest(block["content"].encode()) != block["content_sha256"]:
        raise ValueError("pdf_block_content_hash_mismatch")
    end = len(block["content"]) if end is None else end
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(block["content"])
    ):
        raise ValueError("invalid_pdf_source_span")
    return {
        "block_id": block["block_id"],
        "start": start,
        "end": end,
        "block_sha256": block["content_sha256"],
        "span_sha256": digest(block["content"][start:end].encode()),
        "locator": block["locator"],
        "offset_unit": "Unicode codepoints; end exclusive",
    }


def source_text(members, blocks):
    out = []
    for m in members:
        b = blocks[m["block_id"]]
        if fragment(b, m["start"], m["end"]) != m:
            raise ValueError("changed_pdf_source_span_or_locator")
        out.append(b["content"][m["start"] : m["end"]])
    return "\n".join(out)


def line_rows(block, layout):
    return [
        {
            "text": block["content"][l["start"] : l["end"]],
            "bbox": l["bbox"],
            "member": fragment(block, l["start"], l["end"]),
        }
        for l in layout[block["block_id"]]["lines"]
        if l["end"] > l["start"]
    ]


def simple_grid(header, body, layout):
    """Qualify only rectangular native baseline grids; reject ambiguous/missing cells.

    Each printed cell is an exact original line span; no numeric interpolation,
    merged-cell inference or generic table-library confidence promotion.
    """
    hs = line_rows(header, layout)
    if not 3 <= len(hs) <= 12 or max(h["bbox"][1] for h in hs) - min(h["bbox"][1] for h in hs) > 2:
        return None
    hs.sort(key=lambda x: x["bbox"][0])
    ls = line_rows(body, layout)
    if len(ls) < len(hs) * 2 or len(ls) % len(hs):
        return None
    rows = []
    for a in range(0, len(ls), len(hs)):
        row = ls[a : a + len(hs)]
        if max(x["bbox"][1] for x in row) - min(x["bbox"][1] for x in row) > 2:
            return None
        row.sort(key=lambda x: x["bbox"][0])
        if abs(row[0]["bbox"][0] - hs[0]["bbox"][0]) > 8:
            return None
        if not all(NUMERIC.fullmatch(x["text"].strip()) for x in row[1:]):
            return None
        if any(abs(x["bbox"][2] - h["bbox"][2]) > 14 for x, h in zip(row[1:], hs[1:], strict=True)):
            return None
        if any(x["bbox"][2] >= y["bbox"][0] for x, y in pairwise(row)):
            return None
        rows.append(row)
    return {
        "headers": hs,
        "rows": rows,
        "association_evidence": "native_same_baseline_and_column_alignment",
        "merged_cells_supported": False,
    }


def ruled_grids(document, data, layout):
    """Use existing PyMuPDF ruling geometry, validating every selected source line.

    Reject merged/missing/crossing cells and clipped rows. Empty outer columns
    created by browser page borders are removed only when they contain no text.
    Source strings come exclusively from original observation spans.
    """
    bypage = defaultdict(list)
    for b in document["blocks"]:
        if b["content"]:
            bypage[b["locator"]["page"]].extend(line_rows(b, layout))
    output = []
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for n, page in enumerate(pdf, 1):
            # Browser tables have real cell rulings. Academic papers often have
            # horizontal rules only; those are handled by simple_grid instead.
            if document["source"]["doc_id"] != "C06":
                continue
            for table in page.find_tables(strategy="lines").tables:
                if table.row_count < 3 or table.col_count < 3:
                    continue
                rows = []
                bad_rows = set()
                for ri, row in enumerate(table.rows):
                    cells = []
                    for box in row.cells:
                        if box is None:
                            cells.append(None)
                            continue
                        rect = pymupdf.Rect(box)
                        found = []
                        for line in bypage[n]:
                            lb = pymupdf.Rect(line["bbox"])
                            if rect.contains(lb.tl) and rect.contains(lb.br):
                                found.append(line)
                            elif (
                                rect.intersects(lb)
                                and lb.get_area()
                                and (rect & lb).get_area() / lb.get_area() > 0.15
                            ):
                                bad_rows.add(ri)
                        found.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
                        cells.append(
                            {
                                "text": "\n".join(l["text"] for l in found),
                                "members": [l["member"] for l in found],
                                "bbox": list(box),
                            }
                        )
                    rows.append(cells)
                active = [
                    i
                    for i in range(table.col_count)
                    if any(r[i] and r[i]["text"].strip() for r in rows)
                ]
                if 0 in bad_rows or len(active) < 3:
                    continue
                rows = [[r[i] for i in active] for r in rows]
                invalid = {
                    ri
                    for ri, r in enumerate(rows)
                    if any(c is None or not c["text"].strip() for c in r)
                }
                if 0 in invalid:
                    continue
                rows = [r for ri, r in enumerate(rows) if ri not in bad_rows | invalid]
                if len(rows) < 3:
                    continue
                header = rows[0]
                if sum(bool(re.search(r"[A-Za-z]{2,}", c["text"])) for c in header) < 3:
                    continue
                members = [m for r in rows for c in r for m in c["members"]]
                keys = [(m["block_id"], m["start"], m["end"]) for m in members]
                if len(keys) != len(set(keys)):
                    continue
                output.append(
                    {
                        "page": n,
                        "headers": header,
                        "rows": rows[1:],
                        "association_evidence": "native_ruled_cell_rectangles_and_contained_original_line_spans",
                        "merged_cells_supported": False,
                        "unqualified_native_rows": sorted(bad_rows | invalid),
                    }
                )
    return output


def unit(
    document,
    members,
    kind,
    classification,
    headings=(),
    limitations=(),
    *,
    structure=None,
    presentation=None,
    related=(),
):
    bs = {b["block_id"]: b for b in document["blocks"]}
    text = source_text(members, bs)
    member_ids = {m["block_id"] for m in members}
    required_ids = member_ids | set(headings)
    ids = [s["section_id"] for s in document["sections"] if required_ids & set(s["block_ids"])]
    context = []
    for h in headings:
        if h not in member_ids:
            match = re.fullmatch(r"([IVX]+\. [A-Z ]+)\n([A-Z])", bs[h]["content"])
            hm = fragment(bs[h], 0, len(match[1])) if match else fragment(bs[h])
            context.append(
                {
                    "kind": "SOURCE_CONTENT",
                    "role": "source_heading",
                    "text": bs[h]["content"][hm["start"] : hm["end"]],
                    "source_span": hm,
                }
            )
    display = text
    transforms = []
    for a, b in pairwise(members):
        original = bs[a["block_id"]]["content"]
        match = re.fullmatch(r"([IVX]+\. [A-Z ]+)\n([A-Z])", original)
        if match and a["start"] == len(match[1]) + 1 and a["end"] == len(original):
            left = original[a["start"] : a["end"]]
            right = bs[b["block_id"]]["content"][b["start"] : b["end"]]
            if right[:1].isupper():
                before = left + "\n" + right
                after = left + right
                if display.count(before) != 1:
                    raise ValueError("ambiguous_dropcap_projection")
                display = display.replace(before, after)
                transforms.append(
                    {
                        "operation": "remove_synthetic_joiner_after_source_drop_cap",
                        "source_members": [a, b],
                        "before": before,
                        "after": after,
                        "reversible": True,
                    }
                )
    src = document["source"]
    if presentation is not None and "consumable_lines" in presentation:
        display = "\n".join(l["text"] for l in presentation["consumable_lines"])
        transforms.append(
            {
                "operation": "separate_source_backed_printed_line_numbers",
                "original_text": text,
                "display_text": display,
                "metadata": presentation["printed_line_numbers"],
                "source_lines": presentation["original_lines"],
                "reversible": True,
            }
        )
    u = {
        "schema": "pdf-source-text-unit-1.0",
        "doc_id": src["doc_id"],
        "source": src,
        "content_type": kind,
        "text": text,
        "text_sha256": digest(text.encode()),
        "source_members": members,
        "display_text": display,
        "display_transformations": transforms,
        "required_section_ids": ids,
        "required_context": context,
        "structure": structure,
        "reference_classification": classification,
        "known_limitations": list(limitations),
        "qa_observations": [
            {
                "kind": "QA_OBSERVATION",
                "issue_id": "PDF-TEXT-" + digest(x.encode())[:12],
                "severity": "WARNING",
                "origin": "ingestion_QA_not_publisher",
                "explanation": x,
            }
            for x in limitations
        ],
        "allowed_usage": [
            "Attributed source-grounded explanation within the admitted source spans."
        ]
        + (
            ["Quoted illustration with all qualifications and required context."]
            if classification == "ILLUSTRATIVE"
            else []
        ),
        "forbidden_usage": [
            "Treating excluded neighboring material as approved.",
            "Claiming independent publisher or experimental certification.",
        ]
        + (
            ["Executable-code or complete-mathematical correctness certification."]
            if kind in {"code_example", "mathematical_reference"}
            else []
        ),
        "related_evidence": list(related),
        "presentation": presentation,
        "citation_locators": [
            {
                "doc_id": src["doc_id"],
                "url": src["canonical_url"],
                "page": m["locator"]["page"],
                "bbox": m["locator"]["bbox"],
                "coordinate_precision": "original block bbox; span offsets are exact",
                "block_id": m["block_id"],
                "start": m["start"],
                "end": m["end"],
                "raw_sha256": src["raw_sha256"],
            }
            for m in members
        ],
        "evidence_origin": "deterministic_source_replay; not independent human certification",
    }
    u["id"] = "pdf-text-unit:" + src["doc_id"] + ":" + digest(encoded(u))[:24]
    u["unit_sha256"] = digest(encoded(u))
    return u


def recover(document, data, *, math_references=()):
    """Census/recovery evidence only; assess/make_decisions own admission.

    Larger source-defined heading scopes retain paragraph/block boundaries. They
    are structural source units, never token-sized retrieval chunks.
    """
    src = read_source(document["source"])
    blocks = {b["block_id"]: b for b in document["blocks"]}
    objects = [ParsedBlock.model_validate(b) for b in blocks.values()]
    layout, _ = native_layout(data, src, objects)
    coverage = {r["block_id"]: r for r in document["pdf_classification"]["coverage"]}
    roles = document["pdf_classification"]["layout_roles"]
    units = []
    consumed = set()
    excluded = {}
    holds = {}
    table_failures = []
    heading = None
    headings = {}
    ref_start = None
    ordered = list(blocks.values())
    paragraph_peers = defaultdict(set)
    for parent in document["parents"]:
        if parent["kind"] == "paragraph" and not parent.get("hazards"):
            ids = {m["block_id"] for m in parent["members"]}
            for bid in ids:
                paragraph_peers[bid].update(ids - {bid})
    for b in ordered:
        bid = b["block_id"]
        t = b["content"].strip()
        role = roles.get(bid, {})
        if t.upper() in {"REFERENCES", "BIBLIOGRAPHY"}:
            ref_start = b["sequence"]
        kind = coverage[bid]["content_type"]
        drop = re.fullmatch(r"([IVX]+\. [A-Z ]+)\n([A-Z])", t)
        if drop or (
            kind == "heading"
            and len(t) > 3
            and not t.startswith(("20 Total", "10 Total", "30 Total"))
            and (
                role.get("role") == "document_heading_candidate"
                or t.upper() in {"REFERENCES", "BIBLIOGRAPHY", "ABSTRACT", "ACKNOWLEDGMENTS"}
                or re.match(r"^(?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)?)\s*\n[A-Z]", t)
            )
        ):
            heading = bid
        headings[bid] = heading
        if not t:
            if coverage[bid]["native_type"] != "image":
                raise ValueError("empty_substantive_pdf_text")
            excluded[bid] = "EXCLUDED_NON_TEXT: native image; visual information unavailable"
        elif (
            kind == "page_furniture"
            or re.fullmatch(r"\d{1,2}", t)
            and (b["locator"]["bbox"][1] > 0.9 * layout[bid]["page_size"][1])
        ):
            excluded[bid] = "EXCLUDED_NON_KNOWLEDGE: source-backed page furniture"
    front = []
    for b in ordered:
        if b["locator"]["page"] != 1 or re.match(r"^Abstract\b", b["content"], re.IGNORECASE):
            break
        if b["content"] and b["block_id"] not in excluded:
            front.append(fragment(b))
    if front:
        units.append(
            unit(
                document,
                front,
                "document_citation",
                "ILLUSTRATIVE",
                limitations=[
                    "Document front-matter attribution only; original names and affiliation markers retained without inferring unverified marker relationships."
                ],
            )
        )
        consumed.update(m["block_id"] for m in front)
    # Every table stays source-bound; font alone cannot turn a table into code.
    table_blocks = set()
    for grid in ruled_grids(document, data, layout):
        ms = [
            m for row in [grid["headers"]] + grid["rows"] for cell in row for m in cell["members"]
        ]
        if any(m["block_id"] in consumed for m in ms):
            continue
        h = headings[ms[0]["block_id"]]
        units.append(
            unit(
                document,
                ms,
                "table",
                "ILLUSTRATIVE",
                [h] if h else [],
                [
                    "Exact printed page table segment only. Repeated headers are retained; no cross-page missing row or merged-cell association is inferred.",
                    "Reported means, deviations and benchmark comparisons belong to the frozen Chroma report and are not independently reproduced.",
                ],
                structure=grid,
            )
        )
        consumed.update(m["block_id"] for m in ms)
        table_blocks.update(m["block_id"] for m in ms)
    # Explicit simple column/header association, not flattened table text.
    for i, b in enumerate(ordered[1:], 1):
        if b["block_id"] in excluded:
            continue
        prev = ordered[i - 1]
        if (
            b["locator"]["page"] != prev["locator"]["page"]
            or not b["content"]
            or not prev["content"]
        ):
            continue
        if coverage[b["block_id"]]["content_type"] != "table":
            continue
        grid = simple_grid(prev, b, layout)
        if grid:
            ms = [x["member"] for row in [grid["headers"]] + grid["rows"] for x in row]
            caption = next(
                (
                    x
                    for x in ordered[max(0, i - 2) : i + 3]
                    if x["locator"]["page"] == b["locator"]["page"]
                    and CAPTION.match(x["content"].strip())
                ),
                None,
            )
            if not caption:
                continue
            ms.append(fragment(caption))
            u = unit(
                document,
                ms,
                "table",
                "ILLUSTRATIVE",
                [headings[b["block_id"]]] if headings[b["block_id"]] else [],
                [
                    "Printed table values and source header associations only; reported results were not independently reproduced."
                ],
                structure=grid,
            )
            units.append(u)
            consumed.update(m["block_id"] for m in ms)
    # Source-verified mathematical transcriptions, never a model prediction.
    for ref in math_references:
        bind = ref["source_binding"]
        if bind["document_id"] != src.doc_id or ref["reference_type"] not in {"inline", "display"}:
            continue
        if (
            ref["decision"] != "PASS"
            or bind["pdf_sha256"] != src.raw_sha256
            or bind["snapshot_id"] != src.snapshot_id
        ):
            raise ValueError("unverified_math_reference")
        ms = [fragment(blocks[m["block_id"]], m["start"], m["end"]) for m in bind["source_spans"]]
        if any(blocks[k]["content_sha256"] != v for k, v in bind["source_block_hashes"].items()):
            raise ValueError("math_reference_source_changed")
        u = unit(
            document,
            ms,
            "mathematical_reference",
            "ILLUSTRATIVE",
            limitations=[
                "Owner-verified transcription of this exact printed expression only; no model or generalized formula-recognition qualification.",
                "Use only the explicit transcribed expression and its source attachment; neighboring raw notation remains unqualified.",
            ],
            structure={
                "reference_latex": ref["reference_latex"],
                "critical_relationships": ref["critical_reference_notes"],
                "reference_case_id": ref["case_id"],
                "original_source_binding": bind,
            },
            related=[
                {"type": "source_prose_attachment", "description": ref["critical_reference_notes"]}
            ],
        )
        units.append(u)
    # Remaining prose is grouped by actual heading scope, with retained paragraph
    # boundaries and explicit omitted-specialized-element records.
    groups = defaultdict(list)
    specialized = defaultdict(list)
    for b in ordered:
        bid = b["block_id"]
        t = b["content"].strip()
        kind = coverage[bid]["content_type"]
        if bid in excluded or bid in consumed:
            continue
        role = roles.get(bid, {}).get("role", "")
        drop = re.fullmatch(r"([IVX]+\. [A-Z ]+)\n([A-Z])", b["content"])
        if drop:
            groups[(bid, "section_text")].append(fragment(b, 0, len(drop[1])))
            groups[(bid, "section_text")].append(fragment(b, len(drop[1]) + 1, len(b["content"])))
            continue
        if BAD.search(t):
            holds[bid] = "source glyph/decoder corruption; no unsupported symbolic repair"
            continue
        if role == "chart_text_HOLD":
            holds[bid] = (
                "chart label/value/series relationship is not recoverable as standalone text"
            )
            continue
        if kind == "heading" and bid == headings[bid]:
            groups[(headings[bid], "section_text")].append(fragment(b))
            continue
        if kind in {"figure_caption", "table_caption"} or CAPTION.match(t):
            # A prose reference beginning 'Figure 5 shows...' is not a caption.
            cap = bool(
                re.match(r"^(?:Figure|Fig\.|Table)\s+\d+\s*[:.]", t)
                or re.match(r"^TABLE\s+[IVX]+\s*\n", t)
            )
            if cap or kind in {"figure_caption", "table_caption"}:
                units.append(
                    unit(
                        document,
                        [fragment(b)],
                        "caption",
                        "ILLUSTRATIVE",
                        [headings[bid]] if headings[bid] else [],
                        [
                            "Caption text only. Associated visual/table contents and caption ownership are not independently certified; do not infer unseen values or trends."
                        ],
                    )
                )
                consumed.add(bid)
                continue
        # Bibliography is supporting attribution, not a research claim. Preserve
        # native entries at page-column scope, including fragments spanning blocks.
        if (
            ref_start is not None
            and b["sequence"] > ref_start
            and (
                "reference" in blocks[headings[bid]]["content"].lower() if headings[bid] else False
            )
        ):
            groups[(headings[bid], "bibliography")].append(fragment(b))
            continue
        native_lines = layout[bid]["lines"]
        internal_grid = any(
            sum(abs(a["bbox"][1] - x["bbox"][1]) < 2 for x in native_lines) >= 3
            for a in native_lines
        )
        if internal_grid:
            holds[bid] = (
                "native multi-cell table/diagram geometry; associations are not safely represented by flattened prose"
            )
            specialized[headings[bid]].append(bid)
            continue
        if kind == "code" or role == "monospaced_payload_HOLD":
            # Keep source-page runs and printed formatting observations; never
            # label line numbers as executable source or promise missing code.
            page = b["locator"]["page"]
            page_mono = [
                x
                for x in ordered
                if x["locator"]["page"] == page
                and (
                    coverage[x["block_id"]]["content_type"] == "code"
                    or roles.get(x["block_id"], {}).get("role") == "monospaced_payload_HOLD"
                )
                and x["block_id"] not in consumed
            ]
            page_text = "\n".join(x["content"] for x in page_mono)
            actual_code = bool(
                re.search(
                    r"@techreport\{|\bdef \w+\(|\bimport \w+|\bclass \w+|JSON data:|Write a high-quality answer|Extract the value|<[^>]+>",
                    page_text,
                )
            )
            if src.doc_id == "C06" and not actual_code:
                # Source prompt/algorithm continuations need not repeat 'def' on
                # every printed page. Three or more aligned cells on a baseline
                # signal a table, regardless of monospace typography.
                ls = [l for x in page_mono for l in line_rows(x, layout)]
                cell_grid = any(
                    sum(abs(a["bbox"][1] - b["bbox"][1]) < 2 for b in ls) >= 3 for a in ls
                )
                context_text = blocks[headings[bid]]["content"] if headings[bid] else ""
                actual_code = not cell_grid and bool(
                    re.search(r"prompt|algorithm|chunking", context_text, re.IGNORECASE)
                )
            if actual_code:
                groups[(headings[bid], "code_example")].append(fragment(b))
            else:
                holds[bid] = (
                    "monospaced source is not established code; unresolved table/diagram association"
                )
            continue
        words = re.findall(r"[^\W\d_]{2,}", t)
        readable = len(words) >= 5 and sum(c.isalpha() for c in t) / max(len(t), 1) > 0.50
        math = [
            m
            for m in layout[bid]["math_spans"]
            if b["content"][m["start"] : m["end"]].strip() not in {"•", "†", "‡", "⋆", "∗"}
        ]
        if (
            kind == "prose"
            and not math
            and not BAD.search(t)
            and paragraph_peers[bid]
            and not re.search(r"\S \n[.,;)]|\(\s*\n?\)|\b(?:Precision|query)\s+[,.;]", b["content"])
        ):
            supported_peer = any(
                len(re.findall(r"\b[A-Za-z]{2,}\b", blocks[p]["content"])) >= 5
                and coverage[p]["content_type"] == "prose"
                and p not in holds
                for p in paragraph_peers[bid]
            )
            if supported_peer and not internal_grid:
                groups[(headings[bid], "section_text")].append(fragment(b))
                continue
        detached = ("\n" in t and len(words) < 5) or kind == "inline_math"
        if kind == "table":
            holds[bid] = (
                "table header/cell/merged or clipped associations not sufficiently established; flattened numeric text withheld"
            )
            specialized[headings[bid]].append(bid)
            continue
        if detached or kind == "equation" or (not readable and any(c in t for c in "=∑∏∩Ωηθ")):
            holds[bid] = (
                "unresolved mathematical ordering/script/operator or prose attachment; no inferred repairs"
            )
            specialized[headings[bid]].append(bid)
            continue
        if readable and not math and kind in {"prose", "list", "unknown", "footnote"}:
            # A blank inside otherwise readable source often indicates a detached
            # symbol, notably browser-printed math. Do not qualify it as complete.
            if re.search(r"\S \n[.,;)]|\(\s*\n?\)|\b(?:Precision|query)\s+[,.;]", b["content"]):
                holds[bid] = "visible inline-symbol gap requires explicit source-backed attachment"
                continue
            groups[(headings[bid], "section_text")].append(fragment(b))
            continue
        if readable and math:
            # Recover complete non-mathematical sentences from mixed observations.
            # No placeholders within a supposedly complete equation or sentence.
            text = b["content"]
            for match in re.finditer(r"[^.!?]+[.!?](?:\s+|$)", text):
                a, z = match.span()
                if not any(a < s["end"] and s["start"] < z for s in math):
                    frag = text[a:z].strip()
                    if len(re.findall(r"\b[A-Za-z]{2,}\b", frag)) >= 7:
                        a += len(text[a:z]) - len(text[a:z].lstrip())
                        z = a + len(frag)
                        groups[(headings[bid], "prose_projection")].append(fragment(b, a, z))
            holds[bid] = (
                "inline mathematical glyph/script fidelity unresolved outside admitted non-mathematical sentences"
            )
            specialized[headings[bid]].append(bid)
            continue
        if kind == "presentation":
            excluded[bid] = (
                "EXCLUDED_NON_KNOWLEDGE: printed presentation label; retained as code provenance"
            )
            continue
        if not readable:
            holds[bid] = (
                "short fragment or specialized source relationship requires context; no bounded faithful interpretation established"
            )
        else:
            holds[bid] = "unresolved specialized source structure"
    for key, members in groups.items():
        h, kind, *_ = key

        # Preserve source reading order per physical column, not native emission
        # sequence when blocks are emitted in alternating columns.
        def position(m):
            b = blocks[m["block_id"]]
            x0, y0, _x1, _ = b["locator"]["bbox"]
            width = layout[m["block_id"]]["page_size"][0]
            col = 0 if x0 < width * 0.50 else 1
            return (b["locator"]["page"], col, y0, x0, m["start"])

        members.sort(key=position)
        body = [m for m in members if m["block_id"] != h]
        if not body:
            continue  # Heading-only evidence is context, not independent knowledge.
        limits = []
        if kind == "bibliography":
            limits = [
                "Bibliographic attribution only; citation text is not evidence for the cited publication's unacquired contents."
            ]
        elif kind == "code_example":
            limits = [
                "Printed source example/excerpt only; page boundaries, visible payload and source indentation evidence retained. Not verified runnable code; no missing lines inferred."
            ]
        elif kind == "prose_projection":
            limits = [
                "Complete non-mathematical source sentences only; omitted mathematical sentences and relationships remain unavailable."
            ]
        if specialized[h] and kind == "section_text":
            limits.append(
                "Explanatory source text only; specialized dependent material listed separately remains withheld. Do not infer its missing numerical or symbolic contents."
            )
        if kind == "section_text" and any(
            re.search(
                r"\d\s*%|\d[.\d]*\s*±|\boutperform\w*\b",
                blocks[m["block_id"]]["content"],
                re.IGNORECASE,
            )
            for m in body
        ):
            limits.append(
                "Reported comparisons/results are attributed to the frozen paper; no independent experimental reproduction is claimed."
            )
        illustrative = (
            bool(limits)
            or src.doc_id == "C06"
            and any(
                re.search(
                    r"\b(?:results?|scores?|benchmark|precision|recall|performance)\b",
                    blocks[m["block_id"]]["content"],
                    re.IGNORECASE,
                )
                for m in body
            )
        )
        if src.doc_id == "C06" and illustrative:
            limits.append(
                "Attribute observations and reported results to this frozen Chroma report, not universal benchmark facts."
            )
        presentation = None
        if kind == "code_example":
            ls = [x for m in members for x in line_rows(blocks[m["block_id"]], layout)]
            # A printed gutter number must be horizontally separated from a
            # source line on the same baseline. Literal numeric source lines
            # and numerical signs have no such evidence and remain payload.
            candidates = []
            for l in ls:
                if l["text"].strip().isdigit() and any(
                    x["member"]["locator"]["page"] == l["member"]["locator"]["page"]
                    and abs(x["bbox"][1] - l["bbox"][1]) < 2
                    and x["bbox"][0] > l["bbox"][2] + 5
                    for x in ls
                ):
                    candidates.append(l)
            numbers = [int(x["text"].strip()) for x in candidates]
            verified = bool(
                len(numbers) >= 3 and numbers == list(range(numbers[0], numbers[0] + len(numbers)))
            )
            presentation = {
                "original_lines": ls,
                "printed_line_numbers": candidates if verified else [],
                "consumable_lines": [l for l in ls if not verified or l not in candidates],
                "indentation": "literal extracted spaces retained; native x/y kept for audit; no invented indentation",
            }
        u = unit(
            document,
            members,
            kind,
            "ILLUSTRATIVE" if illustrative else "STANDARD",
            [h] if h else [],
            limits,
            structure={
                "type": "source_heading_scope_with_explicit_block_boundaries",
                "paragraphs": [
                    {
                        "source_member": m,
                        "boundary": "original block boundary; no claim of independent paragraph certification",
                    }
                    for m in members
                ],
                "reading_order": "page, physical column, source y/x; original block IDs retained",
                "unavailable_related_blocks": specialized[h],
            },
            presentation=presentation,
        )
        units.append(u)
        consumed.update(m["block_id"] for m in members)
    # Canonical accounting is distinct from observational image/furniture sidecars.
    memberships = defaultdict(list)
    for u in units:
        for sid in u["required_section_ids"]:
            memberships[sid].append(u["id"])
    dispositions = []
    covered = defaultdict(set)
    for u in units:
        for m in u["source_members"]:
            covered[m["block_id"]].update(range(m["start"], m["end"]))
    residuals = {}
    for bid, b in blocks.items():
        missing = [
            i for i, c in enumerate(b["content"]) if not c.isspace() and i not in covered[bid]
        ]
        intervals = []
        for n in missing:
            if intervals and intervals[-1][1] == n:
                intervals[-1][1] = n + 1
            else:
                intervals.append([n, n + 1])
        if intervals:
            residuals[bid] = intervals
    by_unit = {u["id"]: u for u in units}
    for s in document["sections"]:
        ids = s["block_ids"]
        us = memberships[s["section_id"]]
        reasons = sorted({holds[b] for b in ids if b in holds})
        if us:
            standard = any(by_unit[u]["reference_classification"] == "STANDARD" for u in us)
            status = "STANDARD" if standard else "ILLUSTRATIVE"
            reason = "qualified only through complete source-bound units and mandatory projections"
        elif all(b in excluded for b in ids):
            status = "EXCLUDED"
            reason = "; ".join(sorted({excluded[b] for b in ids}))
        else:
            status = "HOLD"
            reason = (
                "; ".join(reasons)
                or "heading/context fragment has no qualified complete-unit membership"
            )
        dispositions.append(
            {
                "section_id": s["section_id"],
                "doc_id": src.doc_id,
                "disposition": status,
                "reason": reason,
                "unit_ids": us,
                "original_section_sha256": s["normalized_sha256"],
                "original_block_ids": ids,
                "source_locators": s["locators"],
                "remaining_unqualified_aspects": reasons,
                "unqualified_intervals": {b: residuals[b] for b in ids if b in residuals},
                "scope_limited_projection": bool(us and any(b in residuals for b in ids)),
            }
        )
    return {
        "schema": "pdf-text-recovery-evidence-1.0",
        "version": VERSION,
        "source": document["source"],
        "units": units,
        "section_accounting": dispositions,
        "noncanonical_observations": excluded,
        "unqualified_block_reasons": holds,
        "table_diagnostics": table_failures,
        "unqualified_source_intervals": residuals,
        "native_text_geometry_replayed": len(layout),
        "independent_whole_source_verification": False,
    }


def preserve_historical(evidence, document, passages, *, expires_at):
    """Add the eight exact old parents; retain original receipts/scopes separately.

    These do not supply approval for any new neighboring passage. The new source
    qualification is applied independently; the old publication remains intact.
    """
    bs = {b["block_id"]: b for b in document["blocks"]}
    for old in passages:
        if old["source"]["doc_id"] != document["source"]["doc_id"]:
            continue
        ms = [fragment(bs[m["block_id"]], m["start"], m["end"]) for m in old["source_members"]]
        u = unit(document, ms, "historical_reviewed_paragraph", "STANDARD")
        if u["text"] != old["text"]:
            raise ValueError("historical_parent_text_changed")
        u["historical_passage"] = old
        u["historical_publication_interval"] = {"status": "VALID", "expires_at": expires_at}
        u["required_context"] = [
            {
                "kind": "SOURCE_CONTENT",
                "role": "reviewed_heading_context",
                "text": bs[m["block_id"]]["content"][m["start"] : m["end"]],
                "source_span": fragment(bs[m["block_id"]], m["start"], m["end"]),
            }
            for m in old["retrieval_context"]["source_spans"]
        ]
        u["id"] = "pdf-preserved:" + old["candidate_id"]
        u["unit_sha256"] = digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"}))
        evidence["units"].append(u)
        for row in evidence["section_accounting"]:
            if row["section_id"] in old["required_section_ids"]:
                row["disposition"] = "STANDARD"
                row["unit_ids"].append(u["id"])
                row["historical_approval_preserved"] = True
    for u in evidence["units"]:
        related = [
            p for p in passages if set(p["required_section_ids"]) & set(u["required_section_ids"])
        ]
        if related:
            u["historical_publication_interval"] = {"status": "VALID", "expires_at": expires_at}
            u["historical_approval_references"] = [
                {
                    "parent_id": p["parent_id"],
                    "parent_sha256": p["parent_sha256"],
                    "authoritative_publication": p["authoritative_publication"],
                    "required_section_ids": p["required_section_ids"],
                }
                for p in related
            ]
            u["unit_sha256"] = digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"}))
    return evidence


def evidence_proofs(
    root,
    source,
    data,
    blocks,
    sections,
    audit,
    results,
    *,
    release_path,
    expected_release_sha256,
    authorization_path,
    authorization_sha256,
):
    release = verify_release(root, release_path, expected_release_sha256)
    auth_raw = local_path(root, authorization_path).read_bytes()
    if digest(auth_raw) != authorization_sha256:
        raise ValueError("pdf_text_authorization_changed")
    auth = json.loads(auth_raw)
    policy_path = release.get("qualification_policy_path", POLICY)
    policy = json.loads(local_path(root, policy_path).read_bytes())
    if (
        auth.get("release_sha256") != expected_release_sha256
        or auth.get("policy_sha256") != digest(encoded(policy))
        or auth.get("scope") != sorted(SOURCE_IDS)
    ):
        raise ValueError("unbound_pdf_text_authorization")
    corpus = load_corpus(root)
    document = corpus["documents"][source.doc_id]
    if (
        source.model_dump(mode="json") != document["source"]
        or digest(data) != source.raw_sha256
        or [b.model_dump(mode="json") for b in blocks] != document["blocks"]
        or [s.model_dump(mode="json") for s in sections] != document["sections"]
        or audit != document["audit"]
    ):
        raise ValueError("pdf_text_canonical_replay_mismatch")
    for p, h in policy["frozen_bindings"].items():
        if digest(local_path(root, p).read_bytes()) != h:
            raise ValueError("pdf_text_frozen_binding_changed")
    evidence = json.loads(local_path(root, policy["recovery_evidence"][source.doc_id]).read_bytes())
    if evidence["source"] != document["source"]:
        raise ValueError("pdf_text_evidence_source_mismatch")
    bs = {b["block_id"]: b for b in document["blocks"]}
    for u in evidence["units"]:
        if (
            source_text(u["source_members"], bs) != u["text"]
            or digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"}))
            != u["unit_sha256"]
        ):
            raise ValueError("pdf_text_unit_source_or_structure_changed")
        for context in u["required_context"]:
            if source_text([context["source_span"]], bs) != context["text"]:
                raise ValueError("pdf_text_heading_context_changed")
    proofs = {}
    evidence_sha256 = digest(encoded(evidence))
    lookup = {r.section_id: r for r in results}
    for row in evidence["section_accounting"]:
        if row["disposition"] not in {"STANDARD", "ILLUSTRATIVE"}:
            continue
        r = lookup[row["section_id"]]
        # Old policy includes expected PDF layout/math HOLD diagnostics. Resolve
        # only source-replayed complete-unit facets, never genuine integrity errors.
        fatal = {
            k
            for k, v in r.checks.items()
            if v == "fail"
            and k in {"source_hash", "section_hash", "block_hash", "provenance", "normalized_hash"}
        }
        if r.blocking_integrity or fatal or "fail" in r.checks.values():
            raise ValueError("pdf_text_integrity_failure")
        us = [u for u in evidence["units"] if u["id"] in row["unit_ids"]]
        proofs[r.section_id] = {
            "memberships": [
                {
                    "unit_id": u["id"],
                    "unit_sha256": u["unit_sha256"],
                    "required_section_ids": u["required_section_ids"],
                    "reference_classification": u["reference_classification"],
                }
                for u in us
            ],
            "resolved_restrictions": {
                reason: "Source-replayed, scope-bound text qualification; original diagnostic retained in audit."
                for reason in r.reasons
            },
            "required_section_ids": sorted({s for u in us for s in u["required_section_ids"]}),
            "qa_release_sha256": expected_release_sha256,
            "authorization_sha256": authorization_sha256,
            "qualification_policy_sha256": release["files"][policy_path],
            "evidence_sha256": evidence_sha256,
        }
    return proofs, evidence


def persisted_results(
    root,
    source,
    data,
    blocks,
    sections,
    audit,
    *,
    release_path,
    expected_release_sha256,
    authorization_path,
    authorization_sha256,
):
    """Reuse immutable legacy diagnostics after exact input and code verification.

    New qualification is still computed by the shared owner/decision function.
    Replaying unchanged PDF rendering diagnostics per Section adds no evidence;
    this seam does not manufacture technical PASS or alter their original HOLD.
    """
    from rag_hub.validation_models import ValidationResult

    release = verify_release(root, release_path, expected_release_sha256)
    document = load_corpus(root)["documents"][source.doc_id]
    predecessor = json.loads(local_path(root, "config/c10-qa-successor.json").read_bytes())
    stable = {
        "src/rag_hub/content_validation.py",
        "src/rag_hub/source_fidelity.py",
        "src/rag_hub/validation_models.py",
        "src/rag_hub/schemas.py",
    }
    if any(release["files"][p] != predecessor["files"][p] for p in stable):
        raise ValueError("legacy_PDF_validation_implementation_changed")
    if (
        source.model_dump(mode="json") != document["source"]
        or digest(data) != source.raw_sha256
        or [b.model_dump(mode="json") for b in blocks] != document["blocks"]
        or [s.model_dump(mode="json") for s in sections] != document["sections"]
        or audit != document["audit"]
    ):
        raise ValueError("persisted_pdf_validation_input_changed")
    if digest(local_path(root, authorization_path).read_bytes()) != authorization_sha256:
        raise ValueError("persisted_pdf_validation_authorization_changed")
    results = {
        r["section_id"]: ValidationResult.model_validate(r)
        for r in document["qa"]["validation_results"]
    }
    if set(results) != {s.section_id for s in sections}:
        raise ValueError("incomplete_legacy_pdf_diagnostics")
    return results


def decision_from_proof(result, policy, proof):
    if result.blocking_integrity or set(proof["resolved_restrictions"]) != set(result.reasons):
        raise ValueError("unresolved_pdf_text_integrity_or_diagnostics")
    return PdfTextDecision(
        section_id=result.section_id,
        doc_id=result.doc_id,
        risk=result.risk,
        status="approved_for_index",
        raw_sha256=result.raw_sha256,
        normalized_sha256=result.normalized_sha256,
        policy_sha256=fingerprint(policy),
        validation_sha256=fingerprint(result),
        receipt_sha256=digest(encoded(proof)),
        reasons=(),
        scope={
            **{k: v for k, v in proof.items() if k != "resolved_restrictions"},
            "consumption": "verified_complete_unit_only",
            "whole_source_ready": False,
        },
        resolved_restrictions=proof["resolved_restrictions"],
    )
