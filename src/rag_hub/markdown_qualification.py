"""Frozen-source MDX evidence for the sole QA owner; never publishes admission.

The bounded policy qualifies documentation units, not executable programs or
publisher claims. Examples are inspected statically and are never executed.
"""

import ast
import builtins
import importlib
import importlib.metadata
import json
import re
import shlex
import symtable
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Literal

from markdown_it import MarkdownIt
from pydantic import model_validator

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.markdown_corpus import MANIFEST, load_corpus
from rag_hub.schemas import ParsedBlock
from rag_hub.source_fidelity import OPEN_FENCE, TAG, check_markdown
from rag_hub.validation_models import QualityDecision
from rag_hub.validation_sampling import fingerprint

VERSION = "markdown-complete-units-1.2"
SOURCE = "2faa8c25ba8a5a8ff5f9553243cf697ba63957b55264728998403546a9e7ffc0"
CORPUS = "12088137eb0116ab277e715df849856061fedadd43bc79441c06e08d20584887"
EVIDENCE = "data/validation/markdown/v2/assessment.json"


def sha(value):
    return digest(encode(value))


def fidelity(data, source, blocks, sections, options):
    """Reuse maintained fidelity checks with resolvable persisted evidence paths."""
    from rag_hub.shared.builtins import markdown_fidelity

    if source.doc_id != "C04" or source.raw_sha256 != SOURCE or digest(data) != SOURCE:
        raise ValueError("outside_C04_fidelity_scope")
    paths = (
        MANIFEST,
        "data/parsed/markdown/C04.json",
        "data/normalized/markdown/C04.json",
        str(source.raw_path),
        str(source.snapshot_path),
    )
    return [
        check.model_copy(update={"evidence": paths})
        for check in markdown_fidelity(data, source, blocks, sections, options)
    ]


def adapter():
    """An explicit QA contribution; maintained parser/default registration unchanged."""
    from rag_hub.shared.builtins import entries

    return replace(
        entries()[1], adapter_id="C04-source-bound-QA", version=VERSION, fidelity=fidelity
    )


def source_index(raw):
    """Independent lexical scan of original lines, excluding fenced code bodies."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    tokens, containers, stack, fences = [], [], [], []
    md = MarkdownIt("commonmark", {"html": False})
    i = 0
    while i < len(lines):
        opened = OPEN_FENCE.fullmatch(lines[i])
        if opened:
            start, marker = i, opened[2]
            i += 1
            while i < len(lines) and not re.fullmatch(
                r" *" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*", lines[i]
            ):
                i += 1
            if i == len(lines):
                raise ValueError("unclosed_source_fence")
            fences.append([start + 1, i + 1])
            i += 1
            continue
        wrapper = TAG.fullmatch(lines[i])
        if wrapper:
            closing, tag, attrs = wrapper.groups()
            if closing:
                if not stack or stack[-1]["tag"] != tag:
                    raise ValueError("unbalanced_source_MDX")
                stack.pop()["end"] = i + 1
            else:
                title = re.search(r"""title\s*=\s*["']([^"']+)["']""", attrs or "")
                if tag == "Tab" and (not title or not stack or stack[-1]["tag"] != "Tabs"):
                    raise ValueError("invalid_source_Tab")
                c = {
                    "tag": tag,
                    "label": title[1] if title else None,
                    "start": i + 1,
                    "parent_start": stack[-1]["start"] if stack else None,
                }
                containers.append(c)
                stack.append(c)
            i += 1
            continue
        start = i
        while i < len(lines) and not OPEN_FENCE.fullmatch(lines[i]) and not TAG.fullmatch(lines[i]):
            i += 1
        for token in md.parse("".join(lines[start:i])):
            if token.map:
                tokens.append(
                    {
                        "type": token.type,
                        "tag": token.tag,
                        "start": start + token.map[0] + 1,
                        "end": start + token.map[1],
                        "content": token.content,
                        "children": [t.as_dict() for t in token.children or []],
                    }
                )
    if stack:
        raise ValueError("unclosed_source_MDX")
    return {"tokens": tokens, "containers": containers, "fences": fences}


def python_names(body):
    """Free module/global names, without importing or executing source examples."""
    tree = ast.parse(body)
    table = symtable.symtable(body, "<frozen-documentation>", "exec")
    bound = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported()}
    # Inputs/placeholders are retained on HOLD, not silently supplied by this policy.
    placeholders = any(
        isinstance(n, ast.Constant)
        and (
            n.value is Ellipsis
            or isinstance(n.value, str)
            and re.search(r"\.{3}|xxxx|YOUR_|<[A-Z_ ]+>", n.value)
        )
        for n in ast.walk(tree)
    )
    free = {
        s.get_name()
        for s in table.get_symbols()
        if s.is_referenced() and not (s.is_assigned() or s.is_imported())
    }
    # Child global references resolve against all module bindings; module
    # use-before-definition above must remain unresolved.
    global_needed = set()

    def globals_in(t):
        for child in t.get_children():
            global_needed.update(
                s.get_name() for s in child.get_symbols() if s.is_referenced() and s.is_global()
            )
            globals_in(child)

    globals_in(table)
    unresolved = (free | (global_needed - bound)) - set(dir(builtins))
    # Assignment cannot resolve an earlier use on its RHS.
    available = set(dir(builtins))
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            available.update(a.asname or a.name.split(".")[0] for a in statement.names)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            available.add(statement.name)
        else:
            locals_ = {
                x.id
                for n in ast.walk(statement)
                if isinstance(n, ast.comprehension)
                for x in ast.walk(n.target)
                if isinstance(x, ast.Name)
            }
            unresolved.update(
                n.id
                for n in ast.walk(statement)
                if isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id not in available | locals_
            )
            available.update(
                n.id
                for n in ast.walk(statement)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            )
    return bound, unresolved, placeholders


def install_command(body):
    for line in body.splitlines():
        if not line.strip():
            continue
        try:
            words = shlex.split(line)
        except ValueError:
            return False
        if words[:2] not in [["pip", "install"], ["uv", "add"], ["conda", "install"]]:
            return False
        if any(not re.fullmatch(r"[-A-Za-z0-9_.,\[\]>=]+", w) for w in words[2:]):
            return False
        if not any(not w.startswith("-") for w in words[2:]):
            return False
    return bool(body.strip())


def audit(root):
    """Source comparison of every canonical Section; no canonical parser rerun."""
    root = Path(root).resolve()
    corpus = load_corpus(root, admitted_only=False)
    if corpus["manifest"]["identity_sha256"] != CORPUS:
        raise ValueError("unaccepted_C04_corpus_identity")
    source = corpus["manifest"]["source"]
    if (source["doc_id"], source["source_format"], source["raw_sha256"]) != (
        "C04",
        "markdown_mdx",
        SOURCE,
    ):
        raise ValueError("outside_authorized_Markdown_scope")
    rows, parsed = corpus["records"], corpus["structure"]
    if len(rows) != 158 or len({r["section"].section_id for r in rows}) != 158:
        raise ValueError("C04_exact_coverage_required")
    raw = local_path(root, source["raw_path"]).read_bytes()
    index = source_index(raw)
    lines = raw.decode().splitlines(keepends=True)
    chars, byte_offsets = [0], [0]
    for line in lines:
        chars.append(chars[-1] + len(line))
        byte_offsets.append(byte_offsets[-1] + len(line.encode()))
    blocks = {r["block"]["block_id"]: r for r in parsed["records"]}
    covered, results = set(), []
    for rec in parsed["records"]:
        loc = rec["block"]["locator"]
        a, b = loc["line_start"], loc["line_end"]
        if covered & set(range(a, b + 1)):
            raise ValueError("overlapping_original_block_spans")
        covered.update(range(a, b + 1))
    if any(n not in covered and l.strip() for n, l in enumerate(lines, 1)):
        raise ValueError("missing_nonblank_source_line")
    for row in rows:
        s = row["section"]
        if len(s.block_ids) != 1:
            raise ValueError("unexpected_C04_lineage")
        rec = blocks[s.block_ids[0]]
        block = ParsedBlock.model_validate(rec["block"])
        a, b = block.locator.line_start, block.locator.line_end
        expected = {
            "lines_1based_inclusive": [a, b],
            "chars_0based_end_exclusive": [chars[a - 1], chars[b]],
            "bytes_0based_end_exclusive": [byte_offsets[a - 1], byte_offsets[b]],
            "raw_fragment_sha256": digest("".join(lines[a - 1 : b]).encode()),
        }
        failures = check_markdown(s, block, raw)
        if (
            row["source_span"] != expected
            or rec["source_span"] != expected
            or digest(s.text.encode()) != s.normalized_sha256
            or s.block_type != block.block_type
        ):
            failures.append("source_binding_or_type_mismatch")
        if failures:
            raise ValueError(s.section_id + ": " + ",".join(failures))
        containers = [c for c in index["containers"] if c["start"] < a <= b < c["end"]]
        tokens = [t for t in index["tokens"] if t["start"] <= a <= b <= t["end"]]
        role = (
            "code"
            if s.block_type == "code"
            else "heading"
            if s.block_type == "heading"
            else "list_item"
            if any(t["type"] == "list_item_open" for t in tokens)
            else "paragraph"
        )
        if s.block_type == "code" and [a, b] not in index["fences"]:
            raise ValueError("code_not_full_fenced_unit")
        if (
            role == "paragraph"
            and not s.issues
            and not any(
                t["type"] == "paragraph_open" and [t["start"], t["end"]] == [a, b] for t in tokens
            )
        ):
            raise ValueError("incomplete_source_paragraph")
        syntax = [
            t for t in index["tokens"] if t["type"] == "inline" and t["start"] <= a <= b <= t["end"]
        ]
        results.append(
            {
                "section_id": s.section_id,
                "block_id": block.block_id,
                "block_type": s.block_type,
                "source_role": role,
                "source_span": expected,
                "source_checks": "PASS",
                "heading_path": list(s.heading_path),
                "provider_tab": s.provider_tab,
                "code_label": s.code_label,
                "containers": containers,
                "inline_syntax": syntax,
                "historical_decision": row["historical_qa_decision"],
                "normalized_sha256": s.normalized_sha256,
            }
        )
    return corpus, raw, index, results


def _initial_assess(root):
    """Census plus finite, source-backed content-unit/context qualification."""
    corpus, _raw, index, checks = audit(root)
    rows = corpus["records"]
    by_id = {r["section"].section_id: r for r in rows}
    blocks = {r["block"]["block_id"]: r["block"] for r in corpus["structure"]["records"]}
    status, reasons, dependencies, code_state = {}, {}, {}, {}
    approved = {
        c["section_id"]
        for c in checks
        if c["historical_decision"]["status"] == "approved_for_index"
    }
    if len(approved) != 40:
        raise ValueError("historical_approval_count_changed")
    for c in checks:
        sid = c["section_id"]
        s, block = by_id[sid]["section"], blocks[c["block_id"]]
        status[sid], reasons[sid], dependencies[sid] = "candidate", [], []
        text = block["content"].strip()
        if s.block_type != "code":
            if text.startswith(">") or re.fullmatch(r"(?:\*\s*){3,}|(?:-\s*){3,}", text):
                status[sid], reasons[sid] = "excluded", ["non_content_discovery_or_separator"]
            elif "unsupported_mdx_or_html" in s.issues:
                status[sid], reasons[sid] = "excluded", ["publisher_footer_MDX_not_POC_content"]
            elif s.issues:
                status[sid], reasons[sid] = "hold", ["unsupported_source_syntax"]
            continue
        language, body = block["language"], block["content"]
        state = {"bound": [], "unresolved": [], "syntax": "not_applicable"}
        if language == "python":
            try:
                bound, missing, placeholders = python_names(body)
                state = {"bound": sorted(bound), "unresolved": sorted(missing), "syntax": "PASS"}
                # Reuse prior same-heading, same-tab code only; never select a provider implicitly.
                available = set()
                for previous in checks:
                    if previous is c:
                        break
                    pid = previous["section_id"]
                    if (
                        pid in code_state
                        and status[pid] in ("candidate", "historical")
                        and (previous["heading_path"], previous["provider_tab"])
                        == (c["heading_path"], c["provider_tab"])
                    ) and missing & set(code_state[pid]["bound"]):
                        dependencies[sid].append(pid)
                        available.update(code_state[pid]["bound"])
                missing -= available
                state["unresolved"] = sorted(missing)
                if placeholders:
                    status[sid], reasons[sid] = (
                        "hold",
                        ["source_example_contains_unresolved_placeholders"],
                    )
                elif missing:
                    status[sid], reasons[sid] = "hold", ["unresolved_code_or_provider_inputs"]
            except SyntaxError as e:
                state["syntax"] = {"error": e.msg, "line_in_body": e.lineno}
                status[sid], reasons[sid] = "hold", ["invalid_example_syntax_in_original_source"]
        elif language in ("bash", "shell"):
            if not install_command(body):
                status[sid], reasons[sid] = (
                    "hold",
                    ["source_example_contains_unresolved_placeholders"],
                )
        elif language == "text":
            # Complete numeric output can accompany its exact, closed source example.
            previous = next(
                (p for p in reversed(checks[: checks.index(c)]) if p["block_type"] == "code"), None
            )
            if (
                body.strip().isdigit()
                and previous
                and status[previous["section_id"]] in ("candidate", "historical")
            ):
                dependencies[sid].append(previous["section_id"])
            else:
                status[sid], reasons[sid] = (
                    "excluded",
                    ["illustrative_numeric_or_Nike_output_not_POC_knowledge"],
                )
        else:
            status[sid], reasons[sid] = "hold", ["unsupported_code_language"]
        # Printed Python-labelled Document output is publisher output, not broken extraction.
        if language == "python" and (body.startswith(("page_content=", "Score:"))):
            status[sid], reasons[sid] = "excluded", ["illustrative_Nike_output_not_POC_knowledge"]
        code_state[sid] = state
        # Existing approvals are immutable, even if a new static screen is more restrictive.
        if sid in approved:
            status[sid], reasons[sid] = "historical", []

    # A historical code block is available as evidence without replacing its decision.
    available = {sid for sid, st in status.items() if st in ("candidate", "historical")}
    lists = [t for t in index["tokens"] if t["type"] in ("bullet_list_open", "ordered_list_open")]
    groups, grouped = [], set()
    for token in lists:
        members = [
            c["section_id"]
            for c in checks
            if token["start"] <= c["source_span"]["lines_1based_inclusive"][0] <= token["end"]
        ]
        if not members:
            continue
        first = next(i for i, c in enumerate(checks) if c["section_id"] == members[0])
        if first and by_id[checks[first - 1]["section_id"]]["section"].text.rstrip().endswith(":"):
            members.insert(0, checks[first - 1]["section_id"])
        groups.append({"kind": "complete_list", "members": members})
        grouped.update(members)

    # Bind introductory fragments to complete following examples; broad pronoun
    # heuristics alone do not block full source paragraphs.
    for n, c in enumerate(checks):
        sid = c["section_id"]
        if c["block_type"] != "prose" or status[sid] != "candidate" or sid in grouped:
            continue
        s = by_id[sid]["section"]
        if s.text.rstrip().endswith(":"):
            nxt = checks[n + 1] if n + 1 < len(checks) else None
            if nxt and nxt["containers"] and nxt["heading_path"] == c["heading_path"]:
                # This paragraph introduces a choice, not an implicit first-provider default.
                outer = nxt["containers"][0]
                c["alternative_selection_context"] = {
                    "container": outer,
                    "choices": [
                        {
                            "provider_tab": p["provider_tab"],
                            "code_label": p["code_label"],
                            "source_lines": p["source_span"]["lines_1based_inclusive"],
                        }
                        for p in checks
                        if p["block_type"] == "code"
                        and any(k["start"] == outer["start"] for k in p["containers"])
                    ],
                    "selected_alternative": None,
                    "code_bodies_not_admitted_by_intro": True,
                }
            elif nxt and nxt["block_type"] == "code" and nxt["heading_path"] == c["heading_path"]:
                nid = nxt["section_id"]
                if nid in available:
                    dependencies[sid].append(nid)
                else:
                    status[sid], reasons[sid] = "hold", ["intro_requires_unqualified_example"]
            else:
                status[sid], reasons[sid] = "hold", ["incomplete_intro_without_complete_parent"]
        if "In this case, the score" in s.text:
            # The captured page does not name the selected store for this distance claim.
            status[sid], reasons[sid] = "hold", ["score_metric_provider_unspecified_in_source"]

    for c in checks:
        sid = c["section_id"]
        if c["block_type"] != "heading" and sid not in grouped and status[sid] == "candidate":
            groups.append(
                {
                    "kind": "complete_code" if c["block_type"] == "code" else "complete_paragraph",
                    "members": [sid],
                }
            )

    for n, c in enumerate(checks):
        sid = c["section_id"]
        if c["block_type"] == "code" and status[sid] in ("candidate", "historical"):
            # Bind the contiguous source introduction, including external PDF URL,
            # without crossing a heading, code example or provider boundary.
            p = n - 1
            while (
                p >= 0
                and checks[p]["block_type"] == "prose"
                and (checks[p]["heading_path"], checks[p]["provider_tab"])
                == (c["heading_path"], c["provider_tab"])
            ):
                pid = checks[p]["section_id"]
                if status[pid] == "candidate":
                    dependencies[sid].append(pid)
                p -= 1
        if c["block_type"] == "prose" and by_id[sid]["section"].text.startswith("These methods"):
            previous_list = next(
                (
                    g
                    for g in reversed(groups)
                    if g["kind"] == "complete_list"
                    and by_id[g["members"][-1]]["section"].locators[0].line_end
                    < by_id[sid]["section"].locators[0].line_start
                ),
                None,
            )
            if previous_list:
                dependencies[sid].extend(previous_list["members"])

    lookup = {c["section_id"]: c for c in checks}
    units = []
    for g in groups:
        members = set(g["members"])
        todo = list(members)
        while todo:
            for dependency in dependencies[todo.pop()]:
                if dependency not in members:
                    members.add(dependency)
                    todo.append(dependency)
        headings = [
            c["section_id"]
            for c in checks
            if c["block_type"] == "heading"
            and any(
                lookup[m]["heading_path"][: len(c["heading_path"])] == c["heading_path"]
                for m in members
            )
        ]
        if any(status[m] not in ("candidate", "historical") for m in members):
            continue
        providers = {lookup[m]["provider_tab"] for m in members} - {None}
        if len(providers) > 1:
            raise ValueError("alternative_provider_mixing")
        group_choices = {}
        for m in members:
            if lookup[m]["block_type"] == "code":
                for container in lookup[m]["containers"]:
                    if container["tag"] == "CodeGroup":
                        group_choices.setdefault(container["start"], set()).add(
                            lookup[m]["code_label"]
                        )
        if any(len(choices) > 1 for choices in group_choices.values()):
            raise ValueError("alternative_CodeGroup_mixing")
        ordered = sorted(
            members, key=lambda sid: lookup[sid]["source_span"]["lines_1based_inclusive"]
        )
        unit = {
            "kind": g["kind"],
            "required_section_ids": ordered,
            "supporting_heading_ids": headings,
            "provider_tab": next(iter(providers), None),
            "whole_unit_required": True,
            "source_spans": {m: lookup[m]["source_span"] for m in ordered + headings},
            "context": {
                m: {
                    k: lookup[m].get(k)
                    for k in (
                        "heading_path",
                        "provider_tab",
                        "code_label",
                        "containers",
                        "alternative_selection_context",
                    )
                }
                for m in ordered
            },
            "source_semantics": "frozen documentation, not executed examples or verified runtime claims",
            "example_prerequisites": "original documented runtime inputs; no inference executed",
        }
        unit["unit_id"] = "C04:unit:" + sha(unit)[:20]
        units.append(unit)
    qualified = {m for u in units for m in u["required_section_ids"] + u["supporting_heading_ids"]}
    for c in checks:
        sid = c["section_id"]
        if sid not in approved and status[sid] == "candidate" and sid not in qualified:
            status[sid], reasons[sid] = "hold", ["no_complete_qualified_content_unit"]
        c.update(
            {
                "assessment": "historical" if sid in approved else status[sid],
                "reasons": reasons[sid],
                "code_analysis": code_state.get(sid),
                "required_dependencies": dependencies[sid],
                "qualified_unit_ids": [
                    u["unit_id"]
                    for u in units
                    if sid in u["required_section_ids"] + u["supporting_heading_ids"]
                ],
                "human_review_required": status[sid] == "hold"
                and reasons[sid] == ["score_metric_provider_unspecified_in_source"],
                "primary_exception": None
                if sid in approved or sid in qualified
                else "unsupported_content"
                if status[sid] == "excluded"
                else "other_explicit_QA_restriction"
                if reasons[sid] == ["invalid_example_syntax_in_original_source"]
                else "context_or_container_dependency",
            }
        )
    binding_paths = set(corpus["manifest"]["artifacts"]) | set(corpus["manifest"]["implementation"])
    binding_paths.add(MANIFEST)
    return {
        "schema": "markdown-qualification-evidence-1.0",
        "policy": VERSION,
        "status": "STAGED_NOT_AUTHORITATIVE",
        "source": corpus["manifest"]["source"],
        "corpus_identity_sha256": corpus["manifest"]["identity_sha256"],
        "bindings": {p: digest(local_path(root, p).read_bytes()) for p in sorted(binding_paths)},
        "sections": checks,
        "units": units,
        "source_index": index,
        "canonical_sections_changed": 0,
        "confirmed_extraction_defects": 0,
        "source_example_errors_are_not_parser_defects": True,
        "counts": dict(Counter(c["assessment"] for c in checks)),
        "counts_by_type": {
            kind: dict(Counter(c["assessment"] for c in checks if c["block_type"] == kind))
            for kind in ("code", "prose", "heading")
        },
        "newly_authoritatively_admitted": 0,
        "source_readiness": "not_executed",
    }


def assess(root):
    """Reuse the frozen census and reassess only its 42 residual Sections."""
    from rag_hub.markdown_illustrative import assess_illustrative

    return assess_illustrative(root)


class MarkdownUnitDecision(QualityDecision):
    """Consumer must require the whole source-bound unit, never isolated headings."""

    schema_version: Literal["markdown-unit-decision-1.0"] = "markdown-unit-decision-1.0"
    basis: Literal["markdown_verified_content_unit"] = "markdown_verified_content_unit"
    scope: dict

    @model_validator(mode="after")
    def bounded_scope(self):
        units = self.scope.get("units", [])
        if (
            self.doc_id != "C04"
            or self.raw_sha256 != SOURCE
            or self.status != "approved_for_index"
            or self.reasons
            or self.risk != "low"
            or not self.scope.get("whole_unit_required")
            or not units
            or not any(
                self.section_id
                in u.get("required_section_ids", []) + u.get("supporting_heading_ids", [])
                for u in units
            )
            or any(
                not u.get("whole_unit_required") or not u.get("required_section_ids") for u in units
            )
            or set(self.scope.get("unit_ids", [])) != {u.get("unit_id") for u in units}
            or not all(
                self.scope.get(k)
                for k in (
                    "evidence_sha256",
                    "policy_authorization_sha256",
                    "qa_release_sha256",
                    "unit_ids",
                )
            )
        ):
            raise ValueError("invalid_Markdown_content_unit_scope")
        return self


def verify_release(root, path, expected):
    """Verify the explicitly selected integrated implementation, not eligibility."""
    raw = local_path(root, path).read_bytes()
    if not expected or digest(raw) != expected:
        raise ValueError("Markdown_policy_binding_mismatch")
    release = json.loads(raw)
    if release.get("schema") != "markdown-unit-QA-release-1.0":
        raise ValueError("invalid_Markdown_QA_release")
    files = release.get("files", {})
    required = {
        "src/rag_hub/markdown_qualification.py",
        "src/rag_hub/markdown_residual.py",
        "src/rag_hub/markdown_illustrative.py",
        "src/rag_hub/validation_reviews.py",
        "src/rag_hub/shared/qa.py",
        "src/rag_hub/markdown_handoff.py",
        "src/rag_hub/content_validation.py",
        "src/rag_hub/validation_models.py",
        "src/rag_hub/validation_sampling.py",
        "src/rag_hub/source_fidelity.py",
        "src/rag_hub/markdown_corpus.py",
        "src/rag_hub/schemas.py",
        "src/rag_hub/acquire.py",
        "src/rag_hub/html_acquire.py",
        "src/rag_hub/shared/builtins.py",
    }
    if release.get("version") == "combined-c10-html-qa-1.0":
        required |= {
            "src/rag_hub/html_c10.py",
            "src/rag_hub/consumption.py",
            "src/rag_hub/html_handoff.py",
        }
    if not required <= files.keys():
        raise ValueError("Markdown_QA_release_fingerprint_mismatch")
    changed = {p for p, h in files.items() if digest(local_path(root, p).read_bytes()) != h}
    actual_files = files
    pdf_successor_path = "config/pdf-residual-qa-successor-v1.json"
    if not local_path(root, pdf_successor_path).exists():
        pdf_successor_path = "config/pdf-text-qa-successor-v1-1.json"
    if not local_path(root, pdf_successor_path).exists():
        pdf_successor_path = "config/pdf-text-qa-successor.json"
    if changed and local_path(root, pdf_successor_path).exists():
        from rag_hub.pdf_text_recovery import verify_release as verify_pdf_text

        successor = verify_pdf_text(
            root, pdf_successor_path, digest(local_path(root, pdf_successor_path).read_bytes())
        )
        allowed = set(successor["compatibility_changed_files"])
        if (
            not changed <= allowed
            or successor["compatible_integrated_releases"].get(str(path)) != expected
        ):
            raise ValueError("unapproved_PDF_text_reader_compatibility")
        actual_files = successor["files"]
        changed = set()
    if changed:
        successor_path = "config/c10-qa-successor.json"
        allowed = {
            "src/rag_hub/html_qualification.py",
            "src/rag_hub/html_handoff.py",
            "src/rag_hub/markdown_qualification.py",
            "src/rag_hub/pdf_publication.py",
        }
        if (
            not changed <= allowed
            or str(path) == successor_path
            or not local_path(root, successor_path).exists()
        ):
            raise ValueError("Markdown_QA_release_fingerprint_mismatch")
        successor = verify_release(
            root, successor_path, digest(local_path(root, successor_path).read_bytes())
        )
        if successor.get("compatible_integrated_releases", {}).get(str(path)) != expected:
            raise ValueError("unapproved_integrated_QA_compatibility")
        actual_files = successor["files"]
    for name in required:
        module = importlib.import_module(
            name.removeprefix("src/").removesuffix(".py").replace("/", ".")
        )
        if digest(Path(module.__file__).read_bytes()) != actual_files[name]:
            raise ValueError("Markdown_imported_component_fingerprint_mismatch")
    if "dependencies" in release and release["dependencies"] != {
        name: importlib.metadata.version(name) for name in release["dependencies"]
    }:
        raise ValueError("Markdown_QA_dependency_mismatch")
    return release


def evidence_proofs(
    root,
    source,
    sections,
    results,
    *,
    evidence_path,
    expected_evidence_sha256,
    authorization_path,
    expected_authorization_sha256,
    qa_release_path,
    expected_qa_release_sha256,
):
    """Owner-configured seam only. Recompute every check; source cannot activate it.

    Integration owner must explicitly enable this policy on the exact evidence
    and fresh QA release. The current evidence has no such enabled authorization.
    """
    if (
        source.doc_id != "C04"
        or source.source_format != "markdown_mdx"
        or source.raw_sha256 != SOURCE
    ):
        raise ValueError("Markdown_policy_cannot_cross_formats")

    def read(path, expected):
        raw = local_path(root, path).read_bytes()
        if digest(raw) != expected:
            raise ValueError("Markdown_policy_binding_mismatch")
        return json.loads(raw)

    evidence = read(evidence_path, expected_evidence_sha256)
    if source.model_dump(mode="json") != evidence["source"]:
        raise ValueError("Markdown_source_identity_changed")
    authorization = read(authorization_path, expected_authorization_sha256)
    read(qa_release_path, expected_qa_release_sha256)
    if evidence != assess(root):
        raise ValueError("stale_or_forged_Markdown_evidence")
    if authorization != {
        "schema": "markdown-policy-enablement-1.0",
        "enabled": True,
        "policy": VERSION,
        "source_sha256": SOURCE,
        "evidence_sha256": expected_evidence_sha256,
        "qa_release_sha256": expected_qa_release_sha256,
        "authority": "main_RAG_shared_QA_integration_owner",
    }:
        raise ValueError("Markdown_policy_not_explicitly_enabled")
    verify_release(root, qa_release_path, expected_qa_release_sha256)
    exact_sections = {r["section_id"]: r for r in evidence["sections"]}
    if (
        len(sections) != 158
        or {s.section_id for s in sections} != set(exact_sections)
        or len(results) != 158
        or {r.section_id for r in results} != set(exact_sections)
    ):
        raise ValueError("Markdown_QA_requires_full_census")
    canonical = {
        r["section"].section_id: r["section"]
        for r in load_corpus(root, admitted_only=False)["records"]
    }
    if any(s != canonical[s.section_id] for s in sections):
        raise ValueError("Markdown_section_changed")
    # Do not trust even a re-hashed publication's claimed ValidationResults.
    # Replay the existing validator over the same persisted source and audit;
    # this is verification, never a second eligibility engine.
    from rag_hub.content_validation import ValidationInput, validate_section
    from rag_hub.validation_models import ValidationPolicy

    corpus = load_corpus(root, admitted_only=False)
    normalized = json.loads(local_path(root, "data/normalized/markdown/C04.json").read_bytes())
    grouped_audit = {}
    for row in normalized["audit"]:
        grouped_audit.setdefault(row["block_id"], []).append(row)
    context = ValidationInput(
        root=Path(root),
        run_id="C04-source-proof-verification",
        sections=sections,
        blocks={
            row["block"]["block_id"]: ParsedBlock.model_validate(row["block"])
            for row in corpus["structure"]["records"]
        },
        sources={"C04": source},
        raw={"C04": local_path(root, source.raw_path).read_bytes()},
        page_sizes={},
        audit=grouped_audit,
        original_receipts=[],
        artifact_sha256={},
    )
    policy = ValidationPolicy(input_run_id=context.run_id, artifact_sha256={})
    expected = {s.section_id: validate_section(s, context, policy) for s in sections}
    if any(r != expected[r.section_id] for r in results):
        raise ValueError("changed_Markdown_validation_results")
    proofs = {}
    for r in results:
        c = exact_sections[r.section_id]
        if (
            r.raw_sha256 != SOURCE
            or r.normalized_sha256 != c["normalized_sha256"]
            or r.doc_id != "C04"
            or r.blocking_integrity
            or set(r.checks) != {"audit", "context", "integrity", "provenance", "source_fidelity"}
            or any(
                r.checks.get(k) != "pass"
                for k in ("audit", "integrity", "provenance", "source_fidelity")
            )
        ):
            raise ValueError("Markdown_validation_identity_or_integrity_mismatch")
        if c["assessment"] == "historical":
            proofs[r.section_id] = {
                "historical_decision": c["historical_decision"],
                "validation_sha256": fingerprint(r),
            }
            continue
        if c["assessment"] != "candidate":
            continue
        allowed = {
            "heading_only_requires_body_context",
            "unresolved_context_reference",
            "incomplete_or_list_context",
            "code_requires_external_bindings",
            "shell_example_requires_context",
            "code_output_or_unsupported_language",
        }
        if "incomplete_python_syntax" in r.reasons:
            units = [u for u in evidence["units"] if u["unit_id"] in c["qualified_unit_ids"]]
            source_defect = c.get("qualification_scope") == "ILLUSTRATIVE_SOURCE_DEFECT"
            if not units or any(
                not (
                    source_defect
                    and u.get("restricted_projection", {}).get("classification")
                    == "ILLUSTRATIVE_SOURCE_DEFECT"
                    and u["restricted_projection"].get("source_defect")
                    and u["restricted_projection"].get("not_executable_guidance")
                )
                and not (
                    c["section_id"] in u.get("context_only_section_ids", [])
                    and u.get("documentation_scope", {})
                    .get("output_roles", {})
                    .get(c["section_id"])
                    == "attributed_example_output_only"
                )
                for u in units
            ):
                raise ValueError("unresolved_Markdown_syntax_hazard")
            allowed.add("incomplete_python_syntax")
        if "concealed_math_or_table" in r.reasons:
            # An assignment wholly inside an exact inline-code token is a code
            # setting, not a silently qualified mathematical expression.
            plain = " ".join(
                child["content"]
                for token in c["inline_syntax"]
                for child in token["children"]
                if child["type"] == "text"
            )
            if re.search(r"\b[A-Za-z]\w*(?:\([^)]*\))?\s*[=≈]\s*\S", plain):
                raise ValueError("unresolved_Markdown_math_hazard")
            allowed.add("concealed_math_or_table")
        if set(r.reasons) - allowed or any(v == "fail" for v in r.checks.values()):
            raise ValueError("unresolved_Markdown_QA_hazard")
        units = [u for u in evidence["units"] if u["unit_id"] in c["qualified_unit_ids"]]
        scope = {
            "whole_unit_required": True,
            "consumption_rule": "one_complete_bound_unit_with_all_supporting_headings; restricted units require their warning-bearing source projection",
            "unit_ids": c["qualified_unit_ids"],
            "units": units,
            "evidence_sha256": expected_evidence_sha256,
            "policy_authorization_sha256": expected_authorization_sha256,
            "qa_release_sha256": expected_qa_release_sha256,
        }
        proofs[r.section_id] = {
            "scope": scope,
            "reviewed_reasons": list(r.reasons),
            "validation_sha256": fingerprint(r),
            "receipt_sha256": sha(scope | {"validation_sha256": fingerprint(r)}),
        }
    return proofs


def decision_from_proof(result, policy, proof):
    """Constructor used ONLY by make_decisions in the staged integration patch."""
    if (
        result.doc_id != "C04"
        or result.blocking_integrity
        or result.raw_sha256 != SOURCE
        or fingerprint(result) != proof["validation_sha256"]
    ):
        raise ValueError("Markdown_proof_cannot_override_unresolved_or_changed_evidence")
    if "historical_decision" in proof:
        decision = QualityDecision.model_validate(proof["historical_decision"])
        if (decision.section_id, decision.raw_sha256, decision.normalized_sha256) != (
            result.section_id,
            result.raw_sha256,
            result.normalized_sha256,
        ):
            raise ValueError("changed_historical_Markdown_approval")
        return decision
    if set(result.reasons) != set(proof["reviewed_reasons"]):
        raise ValueError("changed_Markdown_reason_dispositions")
    return MarkdownUnitDecision(
        section_id=result.section_id,
        doc_id=result.doc_id,
        raw_sha256=result.raw_sha256,
        normalized_sha256=result.normalized_sha256,
        risk="low",
        status="approved_for_index",
        reasons=(),
        policy_sha256=fingerprint(policy),
        validation_sha256=fingerprint(result),
        receipt_sha256=proof["receipt_sha256"],
        scope=proof["scope"],
    )
