"""Additive residual source projections; evidence only, never an admission authority.

Prior units are copied byte-for-byte. Geometry annotations and literal excerpts
are machine-reviewed source evidence, not independent human certification.
"""

import copy
import re
from collections import defaultdict
from itertools import pairwise

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded
from rag_hub.pdf_text_recovery import BAD, fragment, line_rows, unit

VERSION = "pdf-residual-source-qualification-1.0"


def complete_sentences(block, layout):
    """Withhold expression-bearing sentences; retain exact offsets, never fill gaps."""
    text = block["content"]
    accepted = []
    for match in re.finditer(r".*?(?:[.!?][’”\"\']*(?=\s+[A-Z]|\s*$)|:\s*$)", text, re.DOTALL):
        a, z = match.span()
        a += len(text[a:z]) - len(text[a:z].lstrip())
        z = a + len(text[a:z].rstrip())
        value = text[a:z]
        if len(re.findall(r"\b[A-Za-z]{2,}\b", value)) < 5 or BAD.search(value):
            continue
        # Only plain baseline scalar variables are allowed in these explanatory
        # excerpts. Any scripts, operators, expressions or attachment ambiguity
        # cause abstention for the whole sentence, not a guessed transcription.
        math = [m for m in layout["math_spans"] if a < m["end"] and m["start"] < z]
        if any(
            not re.fullmatch(r"[ pxyzYk()|,]*", text[m["start"] : m["end"]])
            or abs((m["bbox"][3] - m["bbox"][1]) - layout["font_size"]) > 4
            for m in math
        ):
            continue
        accepted.append(fragment(block, a, z))
    return accepted


def baseline_grid(headers, bodies, *, annotated_multiline_header=False):
    """Exact native baseline cells, with explicit absent row-label header.

    No inferred merged cells, rowspans, value splitting or missing-value repair.
    """
    headers = sorted(headers, key=lambda x: x["bbox"][0])
    if not headers or (
        not annotated_multiline_header
        and max(h["bbox"][1] for h in headers) - min(h["bbox"][1] for h in headers) > 2
    ):
        return None
    rows = []
    for line in sorted(bodies, key=lambda x: (x["bbox"][1], x["bbox"][0])):
        if rows and abs(rows[-1][0]["bbox"][1] - line["bbox"][1]) <= 2:
            rows[-1].append(line)
        else:
            rows.append([line])
    if not rows:
        return None
    rows = [sorted(row, key=lambda x: x["bbox"][0]) for row in rows]
    absent = len(rows[0]) == len(headers) + 1
    if absent:
        if rows[0][0]["bbox"][2] >= headers[0]["bbox"][0] - 2:
            return None
        hs = [{"text": "", "printed_header_absent": True, "role": "row_label"}] + headers
    else:
        hs = headers
    for row in rows:
        if len(row) != len(hs):
            return None
        if any(a["bbox"][2] >= b["bbox"][0] for a, b in pairwise(row)):
            return None
        for cell, header in zip(row[1:], headers if absent else headers[1:]):
            cx = (cell["bbox"][0] + cell["bbox"][2]) / 2
            hx = (header["bbox"][0] + header["bbox"][2]) / 2
            if abs(cx - hx) > max(13, (header["bbox"][2] - header["bbox"][0]) / 2):
                return None
    return {
        "headers": hs,
        "rows": rows,
        "merged_cells_supported": False,
        "association_evidence": "exact native baselines and aligned column centers",
    }


def browser_row(header, body):
    """Bound a complete native browser-table row to its printed header columns."""
    if len(header) != 8 or [x["text"] for x in header] != [
        "Chunking",
        "Size",
        "Overlap",
        "Retrieve",
        "Recall",
        "Precision",
        "Precision_Ω",
        "IoU",
    ]:
        return None
    centers = [(h["bbox"][0] + h["bbox"][2]) / 2 for h in header]
    edges = (
        [header[0]["bbox"][0] - 15]
        + [(a["bbox"][2] + b["bbox"][0]) / 2 for a, b in pairwise(header)]
        + [header[-1]["bbox"][2] + 30]
    )
    cells = [[] for _ in header]
    for line in body:
        x = (line["bbox"][0] + line["bbox"][2]) / 2
        matches = [i for i in range(8) if edges[i] <= x < edges[i + 1]]
        if len(matches) != 1:
            return None
        i = matches[0]
        if line["bbox"][0] < edges[i] - 3 or line["bbox"][2] > edges[i + 1] + 3:
            return None
        cells[i].append(line)
    if any(not cell for cell in cells):
        return None
    cells = [sorted(cell, key=lambda x: x["bbox"][1]) for cell in cells]
    texts = ["\n".join(l["text"] for l in cell) for cell in cells]
    if not re.fullmatch(r"[A-Za-z][A-Za-z -]*", texts[0]):
        return None
    if not all(re.fullmatch(r"\d+|N/A|Min", t) for t in texts[1:4]):
        return None
    number = r"[−+\-]?\d+(?:\.\d+)?"
    if not all(re.fullmatch(rf"{number}\s*±\s*{number}", t) for t in texts[4:]):
        return None
    if max(c[0]["bbox"][1] for c in cells[:4]) - min(c[0]["bbox"][1] for c in cells[:4]) > 3:
        return None
    return [
        {
            "text": t,
            "members": [l["member"] for l in cell],
            "column_index": i,
            "header_center_x": centers[i],
        }
        for i, (t, cell) in enumerate(zip(texts, cells))
    ]


def supplement(document, prior, layout, plan):
    """Construct append-only candidate evidence; the existing shared QA decides."""
    if document["source"]["raw_sha256"] != plan["source_sha256"]:
        raise ValueError("residual_plan_source_changed")
    bs = {b["block_id"]: b for b in document["blocks"]}
    if any(bs[b]["content_sha256"] != h for b, h in plan["block_bindings"].items()):
        raise ValueError("residual_plan_block_changed")
    out = copy.deepcopy(prior)
    before = {u["id"]: u["unit_sha256"] for u in prior["units"]}
    new = []
    excluded = {b: entry["reason"] for entry in plan["excluded"] for b in entry["blocks"]}
    held = {
        b
        for row in prior["section_accounting"]
        if row["disposition"] == "HOLD"
        for b in row["original_block_ids"]
    }
    checks = []
    for entry in plan["prose"]:
        members = []
        for bid in entry["members"]:
            if BAD.search(bs[bid]["content"]):
                raise ValueError("residual_corrupted_text_must_remain_HOLD")
            members += (
                complete_sentences(bs[bid], layout[bid])
                if entry["mode"] == "sentences"
                else [
                    fragment(
                        bs[bid],
                        *entry.get("source_spans", {}).get(bid, [0, len(bs[bid]["content"])]),
                    )
                ]
            )
        if not members:
            checks.append({"kind": "prose", "blocks": entry["members"], "status": "ABSTAIN"})
            continue
        limits = [entry["qualification"]] if entry["qualification"] else []
        if document["source"]["doc_id"] == "C06":
            limits.append(
                "Attribute this excerpt and reported observations to the frozen Chroma report; not universal benchmark facts."
            )
        u = unit(
            document,
            members,
            "residual_prose_projection" if entry["mode"] == "sentences" else "residual_prose",
            "ILLUSTRATIVE" if limits else "STANDARD",
            ([entry["heading"]] if entry["heading"] else []) + entry["required_context_blocks"],
            limits,
            structure={
                "type": "source_reviewed_ordered_spans",
                "members": members,
                "non_contiguous_excerpts": entry["mode"] == "sentences"
                or bool(entry.get("source_spans")),
                "missing_mathematics_reconstructed": False,
            },
        )
        new.append(u)
        checks.append(
            {
                "kind": "prose",
                "blocks": entry["members"],
                "status": "SCOPED_SOURCE_MATCH",
                "unit_id": u["id"],
            }
        )
    for entry in plan.get("inline_prose", []):
        symbol = bs[entry["symbol"]]
        body = [bs[b] for b in entry["body"]]
        anchor = bs[entry["anchor_block"]]
        if (
            symbol["content"].replace("\u200b", "").strip() != "Ω"
            or anchor["content"].count(entry["anchor"]) != 1
            or symbol["locator"]["page"] != anchor["locator"]["page"]
            or abs(symbol["locator"]["bbox"][1] - anchor["locator"]["bbox"][1]) > 20
        ):
            raise ValueError("unverified_inline_symbol_attachment")
        pos = symbol["content"].index("Ω")
        ms = [fragment(b) for b in body] + [fragment(symbol, pos, pos + 1)]
        relation = {
            "type": "inline_subscript",
            "anchor_block": anchor["block_id"],
            "anchor_offset": anchor["content"].index(entry["anchor"]),
            "anchor_text": entry["anchor"],
            "symbol_span": ms[-1],
            "source_observation": entry["prior_owner_observation"],
        }
        u = unit(
            document,
            ms,
            "residual_inline_notation_prose",
            "ILLUSTRATIVE",
            [entry["heading"]],
            [
                "Only the source-supported Precision subscript Omega attachment is reconstructed; adjacent equations remain unqualified.",
                "Reported benchmark observations belong to this frozen Chroma report, not universal benchmark facts.",
            ],
            structure={"type": "source_supported_inline_attachment", "relationships": [relation]},
        )
        text = "\n".join(b["content"] for b in body)
        at = (
            sum(len(b["content"]) + 1 for b in body[: entry["body"].index(entry["anchor_block"])])
            + relation["anchor_offset"]
            + len(entry["anchor"])
        )
        u["display_text"] = text[:at] + "_Ω" + text[at:]
        u["display_transformations"] = [
            {
                "operation": "source_backed_subscript_attachment",
                "original_text": u["text"],
                "display_text": u["display_text"],
                "relationship": relation,
                "reversible": True,
                "underscore_is_not_a_new_publisher_character": True,
            }
        ]
        u.pop("unit_sha256")
        u.pop("id")
        u["id"] = (
            "pdf-residual-unit:" + document["source"]["doc_id"] + ":" + digest(encoded(u))[:24]
        )
        u["unit_sha256"] = digest(encoded(u))
        new.append(u)
    for entry in plan["heading_context"]:
        # Use only already qualified body spans. New headings supply context;
        # their presence can never independently authorize an unqualified body.
        wanted = set(entry["body"])
        members = []
        for u in prior["units"]:
            members += [m for m in u["source_members"] if m["block_id"] in wanted]
        members = list({(m["block_id"], m["start"], m["end"]): m for m in members}.values())
        members.sort(key=lambda m: (entry["body"].index(m["block_id"]), m["start"]))
        if not members:
            checks.append(
                {"kind": "heading_context", **entry, "status": "ABSTAIN_NO_QUALIFIED_BODY"}
            )
            continue
        inherited = sorted(
            {
                limit
                for u in prior["units"]
                if wanted & {m["block_id"] for m in u["source_members"]}
                for limit in u["known_limitations"]
            }
        )
        new.append(
            unit(
                document,
                members,
                "residual_context_bound",
                "ILLUSTRATIVE",
                entry["headings"],
                [
                    "Additional source-backed heading context for these exact prior-qualified spans only; inherited special-content limitations remain binding."
                ]
                + inherited,
                related=[
                    {
                        "type": "prior_qualified_unit",
                        "id": u["id"],
                        "sha256": u["unit_sha256"],
                        "mandatory_limitations": u["known_limitations"],
                    }
                    for u in prior["units"]
                    if wanted & {m["block_id"] for m in u["source_members"]}
                ],
            )
        )
    for entry in plan["tables"]:
        header = line_rows(bs[entry["header"]], layout)
        body = [l for b in entry["body"] for l in line_rows(bs[b], layout)]
        grid = baseline_grid(header, body)
        if grid is None:
            checks.append({"kind": "table", **entry, "status": "ABSTAIN_GEOMETRY"})
            continue
        if entry["group_header"]:
            groups = line_rows(bs[entry["group_header"]], layout)
            leaves = grid["headers"][1:]
            if len(groups) * entry["group_width"] != len(leaves):
                raise ValueError("unbound_table_header_hierarchy")
            grid["column_groups"] = [
                {
                    "source": g,
                    "leaf_column_indices": list(
                        range(1 + i * entry["group_width"], 1 + (i + 1) * entry["group_width"])
                    ),
                }
                for i, g in enumerate(groups)
            ]
            # Explicit source-reviewed printed two-column group headings. No
            # generic nearest-word inference of merged-cell semantics.
        members = [l["member"] for l in header + body]
        if entry["group_header"]:
            members = [fragment(bs[entry["group_header"]])] + members
        members.append(fragment(bs[entry["caption"]]))
        new.append(
            unit(
                document,
                members,
                "table",
                "ILLUSTRATIVE",
                limitations=[
                    "Printed source table projection with explicit native row/column and header-group relationships. Reported results are attributed, not independently reproduced. No unselected cells or merged associations are inferred."
                ],
                structure=grid,
            )
        )
        checks.append(
            {"kind": "table", **entry, "status": "SCOPED_SOURCE_MATCH", "rows": len(grid["rows"])}
        )
    for entry in plan.get("annotated_tables", []):
        header = []
        for group in entry["header_groups"]:
            lines = [
                line_rows(bs[f"{document['source']['doc_id']}:b{number:05}"], layout)[index]
                for number, index in group
            ]
            header.append(
                {
                    "text": "\n".join(l["text"] for l in lines),
                    "members": [l["member"] for l in lines],
                    "bbox": [
                        min(l["bbox"][0] for l in lines),
                        min(l["bbox"][1] for l in lines),
                        max(l["bbox"][2] for l in lines),
                        max(l["bbox"][3] for l in lines),
                    ],
                }
            )
        body = [l for b in entry["body"] for l in line_rows(bs[b], layout)]
        grid = baseline_grid(header, body, annotated_multiline_header=True)
        if grid is None:
            checks.append({"kind": "annotated_table", "status": "ABSTAIN_GEOMETRY", **entry})
            continue
        members = [m for h in header for m in h["members"]] + [
            l["member"] for row in grid["rows"] for l in row
        ]
        members.append(fragment(bs[entry["caption"]]))
        new.append(
            unit(
                document,
                members,
                "table",
                "ILLUSTRATIVE",
                limitations=[
                    "Source-reported RAG-method comparison only. Exact printed row and column associations with source-reviewed multiline header groups; cited implementations and claims not independently certified."
                ],
                structure=grid,
            )
        )
        checks.append(
            {
                "kind": "annotated_table",
                "status": "SCOPED_SOURCE_MATCH",
                "rows": len(grid["rows"]),
                **entry,
            }
        )
    if document["source"]["doc_id"] == "C06":
        ordered = list(bs.values())
        headers = [
            b
            for b in ordered
            if b["content"].startswith(
                "Chunking\nSize\nOverlap\nRetrieve\nRecall\nPrecision\nPrecision_Ω\nIoU"
            )
        ]
        captions = [
            b
            for b in ordered
            if re.fullmatch(
                r"(?:All corpora|\w+(?: corpus)?|Wikitext), (?:text-embedding-3-large|all-MiniLM-L6-v2)",
                b["content"],
            )
        ]
        for b in ordered:
            if b["block_id"] not in held or not re.match(
                r"^(Recursive|TokenText|Cluster|LLM)\n", b["content"]
            ):
                continue
            head = next(
                (
                    h
                    for h in reversed(headers)
                    if h["sequence"] < b["sequence"]
                    and h["locator"]["page"] == b["locator"]["page"]
                ),
                None,
            )
            caption = next((cap for cap in captions if cap["sequence"] > b["sequence"]), None)
            if not head or not caption or caption["locator"]["page"] - b["locator"]["page"] > 5:
                checks.append(
                    {"kind": "browser_row", "block": b["block_id"], "status": "ABSTAIN_CONTEXT"}
                )
                continue
            hs = line_rows(head, layout)
            row = browser_row(hs, line_rows(b, layout))
            if row is None:
                checks.append(
                    {"kind": "browser_row", "block": b["block_id"], "status": "ABSTAIN_GEOMETRY"}
                )
                continue
            members = [x["member"] for x in hs] + [m for cell in row for m in cell["members"]]
            new.append(
                unit(
                    document,
                    members,
                    "table",
                    "ILLUSTRATIVE",
                    ["C06:b00755", caption["block_id"]],
                    [
                        "Exact printed Chroma appendix row with its printed columns, corpus/embedding caption and Retrieve setting. Means/deviations are source-reported; no experiment or score semantics are independently certified. No neighboring rows or plotted values are implied."
                    ],
                    structure={
                        "headers": hs,
                        "rows": [row],
                        "merged_cells_supported": False,
                        "association_evidence": "native single-row cells aligned under same-page printed header; next source table caption",
                        "caption_span": fragment(caption),
                    },
                )
            )
            checks.append(
                {
                    "kind": "browser_row",
                    "block": b["block_id"],
                    "status": "SCOPED_SOURCE_MATCH",
                    "caption": caption["block_id"],
                }
            )
    for u in new:
        for context in u["required_context"]:
            if u["content_type"] == "table" and context["source_span"]["block_id"] != "C06:b00755":
                context["role"] = "table_corpus_embedding_caption"
            elif len(context["text"]) > 180:
                context["role"] = "required_source_context"
        u["unit_sha256"] = digest(encoded({k: v for k, v in u.items() if k != "unit_sha256"}))
    out["units"] += new
    if any(u["unit_sha256"] != before[u["id"]] for u in out["units"] if u["id"] in before):
        raise ValueError("prior_pdf_unit_changed")
    memberships = defaultdict(list)
    covered = defaultdict(set)
    for u in out["units"]:
        for sid in u["required_section_ids"]:
            memberships[sid].append(u)
        for m in u["source_members"] + [x["source_span"] for x in u["required_context"]]:
            covered[m["block_id"]].update(range(m["start"], m["end"]))
    residuals = {}
    for bid, b in bs.items():
        missing = [
            i for i, ch in enumerate(b["content"]) if not ch.isspace() and i not in covered[bid]
        ]
        intervals = []
        for i in missing:
            if intervals and intervals[-1][1] == i:
                intervals[-1][1] += 1
            else:
                intervals.append([i, i + 1])
        if intervals:
            residuals[bid] = intervals
    prior_rows = {s["section_id"]: s for s in prior["section_accounting"]}
    for row in out["section_accounting"]:
        sid = row["section_id"]
        us = memberships[sid]
        if prior_rows[sid]["disposition"] != "HOLD":
            row["unit_ids"] = [u["id"] for u in us]
            row["predecessor_scope_limited_projection"] = row["scope_limited_projection"]
            row["unqualified_intervals"] = {
                b: residuals[b] for b in row["original_block_ids"] if b in residuals
            }
            row["scope_limited_projection"] = bool(us and row["unqualified_intervals"])
            continue  # Preserve existing classifications and allowed intervals.
        row["predecessor_disposition"] = "HOLD"
        if us:
            row["disposition"] = (
                "STANDARD"
                if any(u["reference_classification"] == "STANDARD" for u in us)
                else "ILLUSTRATIVE"
            )
            row["unit_ids"] = [u["id"] for u in us]
            row["reason"] = (
                "qualified residual source spans/context only, through complete verified units"
            )
            row["unqualified_intervals"] = {
                b: residuals[b] for b in row["original_block_ids"] if b in residuals
            }
            body = any(
                set(row["original_block_ids"]) & {m["block_id"] for m in u["source_members"]}
                for u in us
            )
            row["recovery_role"] = (
                (
                    "scope_limited_projection"
                    if row["unqualified_intervals"]
                    else "fully_recovered_into_complete_unit"
                )
                if body
                else "required_context_only"
            )
            row["scope_limited_projection"] = bool(row["unqualified_intervals"])
        elif all(b in excluded for b in row["original_block_ids"]):
            row["disposition"] = "EXCLUDED"
            row["reason"] = "; ".join(sorted({excluded[b] for b in row["original_block_ids"]}))
            row["recovery_role"] = "intentional_non_knowledge_exclusion"
        else:
            row["recovery_role"] = "retained_HOLD"
    out["version"] = VERSION
    out["residual_recovery_checks"] = checks
    out["predecessor_unit_hashes"] = before
    out["unqualified_source_intervals"] = residuals
    out["source_annotation_origin"] = (
        "Codex source review and deterministic geometry; no new human attestations"
    )
    return out
