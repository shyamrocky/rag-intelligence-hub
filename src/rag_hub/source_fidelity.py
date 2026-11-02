"""Independent raw Markdown-span verification; never invokes ingestion parsers."""

import ast
import builtins
import re

from rag_hub.acquire import digest
from rag_hub.schemas import ParsedBlock, Section

OPEN_FENCE = re.compile(r"^( *)(`{3,}|~{3,})([^\r\n]*)\r?\n?$")
TAG = re.compile(r"^\s*<(/?)(Tabs|Tab|CodeGroup)(?:\s+([^>]*))?>\s*$")
LABEL = re.compile(r"""title\s*=\s*["']([^"']+)["']""")


def raw_context(lines: list[str], stop: int):
    """Independent metadata walk, excluding all fenced bodies from heading/tab state."""
    heading, containers = [], []
    fence = None
    for line in lines[:stop]:
        if fence:
            if re.fullmatch(r" *" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
            continue
        opened = OPEN_FENCE.fullmatch(line)
        if opened:
            fence = (opened[2][0], len(opened[2]))
            continue
        m = TAG.fullmatch(line)
        if m:
            closing, tag, attrs = m.groups()
            if closing:
                if not containers or containers[-1][0] != tag:
                    raise ValueError("unbalanced source containers")
                containers.pop()
            else:
                title = LABEL.search(attrs or "")
                containers.append((tag, title[1] if title else None))
            continue
        h = re.fullmatch(r" {0,3}(#{1,6})\s+(.+?)\s*#*\s*", re.sub(r"^> ?", "", line))
        if h:
            level = len(h[1])
            heading = [(d, t) for d, t in heading if d < level] + [(level, h[2])]
    provider = next((label for tag, label in reversed(containers) if tag == "Tab"), None)
    group = "CodeGroup" if any(tag == "CodeGroup" for tag, _ in containers) else None
    return tuple(t for _, t in heading), provider, group


def check_markdown(section: Section, block: ParsedBlock, data: bytes) -> list[str]:
    reasons = []
    lines = data.decode("utf-8").splitlines(keepends=True)
    loc = block.locator
    if (
        loc.line_start is None
        or loc.line_end is None
        or not 1 <= loc.line_start <= loc.line_end <= len(lines)
    ):
        return ["invalid_source_lines"]
    span = lines[loc.line_start - 1 : loc.line_end]
    expected = "".join(span)
    if block.block_type == "code":
        opener = OPEN_FENCE.fullmatch(span[0])
        if not opener or len(span) < 2:
            return ["unsupported_code_span"]
        indent, marker, info = opener.groups()
        if not re.fullmatch(
            r" *" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*", span[-1]
        ):
            return ["unclosed_source_fence"]
        expected = "".join(
            l[len(indent) :] if indent and l.startswith(indent) else l for l in span[1:-1]
        )
        language = info.strip().split()[0] if info.strip() else None
        if block.language != language or block.fence_info != info.strip():
            reasons.append("fence_metadata_mismatch")
        marker = "~~~~" if "```" in expected else "```"
        normalized = marker + (language or "") + "\n" + expected
        if not expected.endswith("\n"):
            normalized += "\n"
        normalized += marker
        expected_transforms = ["wrap_code_body_in_canonical_fence"]
        if block.fence_info:
            expected_transforms.append("strip_nonsemantic_fence_attributes")
        if section.transformations != tuple(expected_transforms):
            reasons.append("unexpected_code_transformation")
        if section.code_label != (info.split("theme=", 1)[0].strip() or None):
            reasons.append("code_label_mismatch")
    else:
        normalized = expected
        if section.transformations:
            reasons.append("unexplained_text_transformation")
    if expected != block.content or digest(expected.encode()) != block.content_sha256:
        reasons.append("raw_source_body_mismatch")
    if normalized != section.text:
        reasons.append("normalized_source_mismatch")
    context = raw_context(lines, loc.line_start - 1)
    if block.block_type == "heading":
        h = re.fullmatch(r" {0,3}(#{1,6})\s+(.+?)\s*#*\s*", span[0])
        if not h:
            reasons.append("unsupported_heading_span")
        else:
            preceding = []
            # Use explicit source heading levels to preserve skipped levels.
            for n, line in enumerate(lines[: loc.line_start]):
                if re.fullmatch(r" {0,3}#{1,6}\s+.*", line.rstrip("\r\n")):
                    # The source state walker handles headings inside code correctly.
                    preceding = list(raw_context(lines, n + 1)[0])
            context = (tuple(preceding), context[1], context[2])
    if section.heading_path != context[0] or block.heading_path != context[0]:
        reasons.append("heading_ancestry_mismatch")
    if section.provider_tab != context[1] or block.provider_tab != context[1]:
        reasons.append("provider_mismatch")
    if section.code_group != context[2] or block.code_group != context[2]:
        reasons.append("code_group_mismatch")
    return sorted(set(reasons))


def contextual_reasons(section: Section, block: ParsedBlock) -> list[str]:
    text = block.content.strip()
    reasons = []
    if not text:
        reasons.append("empty_content")
    if section.block_type == "heading":
        reasons.append("heading_only_requires_body_context")
    elif section.block_type == "prose":
        if not re.search(r"[.!?][\"'`)]*$", text) or re.match(r"^(?:[-*>]|\d+[.)])\s", text):
            reasons.append("incomplete_or_list_context")
        if re.search(
            r"\b(this|these|those|above|below|following|previous|it|its|them|they)\b",
            text,
            re.IGNORECASE,
        ):
            reasons.append("unresolved_context_reference")
        if text[:1].islower():
            reasons.append("sentence_fragment")
    elif section.block_type == "code":
        if block.language == "python":
            try:
                tree = ast.parse(block.content)
            except SyntaxError:
                return ["incomplete_python_syntax"]
            bound = {
                n.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            }
            bound |= {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
            bound |= {
                n.name
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            for n in ast.walk(tree):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    bound |= {a.asname or a.name.split(".")[0] for a in n.names}
            used = {
                n.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            }
            if used - bound - set(dir(builtins)):
                reasons.append("code_requires_external_bindings")
            # A name assigned later is not evidence that its earlier use is defined.
            available = set(dir(builtins))
            for statement in tree.body:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    available |= {a.asname or a.name.split(".")[0] for a in statement.names}
                    continue
                loaded = {
                    n.id
                    for n in ast.walk(statement)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                }
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    local = {
                        n.id
                        for n in ast.walk(statement)
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                    }
                    local |= {n.arg for n in ast.walk(statement) if isinstance(n, ast.arg)}
                    local.add(statement.name)
                    loaded -= local
                if loaded - available:
                    reasons.append("code_requires_external_bindings")
                if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    available |= {
                        n.id
                        for n in ast.walk(statement)
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                    }
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    available.add(statement.name)
            if re.search(r"\b(TODO|YOUR_[A-Z_]+|\.\.\.)\b", block.content):
                reasons.append("code_placeholder_requires_context")
        elif block.language in ("shell", "bash"):
            if any(
                not re.fullmatch(
                    r"(?:pip install |uv add |conda install )[A-Za-z0-9_. /\[\],>=<-]+",
                    line.strip(),
                )
                for line in block.content.splitlines()
                if line.strip()
            ):
                reasons.append("shell_example_requires_context")
        else:
            reasons.append("code_output_or_unsupported_language")
    return sorted(set(reasons))
