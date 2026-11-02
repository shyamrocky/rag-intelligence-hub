"""Non-executing Markdown parser with a bounded, explicit MDX container grammar."""

import re

from markdown_it import MarkdownIt

from rag_hub.acquire import digest
from rag_hub.schemas import Locator, ParsedBlock, SourceManifest

PARSER_VERSION = "mdx-v1"
FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
WRAPPER = re.compile(r"^\s*<(\/?)(Tabs|Tab|CodeGroup)(?:\s+([^>]*))?>\s*$")
TITLE = re.compile(r'title\s*=\s*["\']([^"\']+)["\']')


def parse_markdown(data: bytes, source: SourceManifest) -> list[ParsedBlock]:
    lines = data.decode("utf-8").splitlines(keepends=True)
    blocks = []
    covered: set[int] = set()
    headings: list[tuple[int, str]] = []
    containers: list[tuple[str, str | None]] = []
    md = MarkdownIt("commonmark", {"html": False})
    i = 0

    def emit(kind, content, start, end, *, language=None, info=None, issues=()):
        covered.update(range(start, end))
        seq = len(blocks)
        heading = tuple(text for _, text in headings)
        tab = next((label for tag, label in reversed(containers) if tag == "Tab"), None)
        group = "CodeGroup" if any(t == "CodeGroup" for t, _ in containers) else None
        blocks.append(
            ParsedBlock(
                block_id=f"{source.doc_id}:b{seq:05d}",
                doc_id=source.doc_id,
                snapshot_id=source.snapshot_id,
                sequence=seq,
                block_type=kind,
                content=content,
                heading_path=heading,
                locator=Locator(
                    url=source.canonical_url,
                    line_start=start + 1,
                    line_end=end,
                    anchor=re.sub(r"[^a-z0-9]+", "-", heading[-1].lower()).strip("-")
                    if heading
                    else None,
                ),
                language=language,
                provider_tab=tab,
                code_group=group,
                fence_info=info,
                issues=issues,
                raw_sha256=source.raw_sha256,
                content_sha256=digest(content.encode()),
                parser_version=PARSER_VERSION,
                verification_status="hold" if issues else "unreviewed",
            )
        )

    while i < len(lines):
        match = FENCE.match(lines[i].rstrip("\r\n"))
        if match:
            indent, marker, info = match.groups()
            start = i
            i += 1
            body = []
            closed = False
            while i < len(lines):
                close = re.fullmatch(
                    r"\s*" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*",
                    lines[i].rstrip("\r\n"),
                )
                if close:
                    closed = True
                    i += 1
                    break
                line = lines[i]
                # Container indentation belongs to MDX, not the code body.
                body.append(line[len(indent) :] if indent and line.startswith(indent) else line)
                i += 1
            language = info.strip().split()[0] if info.strip() else None
            emit(
                "code",
                "".join(body),
                start,
                i,
                language=language,
                info=info.strip(),
                issues=() if closed else ("unclosed_code_fence",),
            )
            continue
        wrapper = WRAPPER.match(lines[i].rstrip("\r\n"))
        if wrapper:
            closing, tag, attrs = wrapper.groups()
            label = TITLE.search(attrs or "")
            emit("metadata", lines[i], i, i + 1)
            if closing:
                if not containers or containers[-1][0] != tag:
                    raise ValueError(f"unbalanced MDX container at line {i + 1}")
                containers.pop()
            else:
                if tag == "Tab" and not label:
                    raise ValueError("provider Tab requires a title")
                containers.append((tag, label.group(1) if label else None))
            i += 1
            continue
        start = i
        # Parse ordinary Markdown in stretches bounded by MDX containers and fences.
        while i < len(lines) and not FENCE.match(lines[i]) and not WRAPPER.match(lines[i]):
            i += 1
        segment = "".join(lines[start:i])
        tokens = md.parse(segment)
        level = None
        for token in tokens:
            if token.type == "heading_open":
                level = int(token.tag[1:])
            if token.type not in ("inline", "code_block") or token.map is None:
                continue
            a, b = token.map
            if level:
                headings[:] = [(depth, text) for depth, text in headings if depth < level]
                headings.append((level, token.content))
                kind = "heading"
                level = None
            else:
                kind = "code" if token.type == "code_block" else "prose"
            content = "".join(lines[start + a : start + b]) if kind != "code" else token.content
            issues = ("unsupported_mdx_or_html",) if re.search(r"<[/A-Za-z]", content) else ()
            if "|" in content and re.search(r"\|\s*:?-+", content):
                kind = "table"
                issues += ("unverified_table",)
            emit(kind, content, start + a, start + b, issues=issues)
    if containers:
        raise ValueError("unclosed MDX container")
    # Preserve reference definitions, thematic breaks and other unhandled nonblank
    # lines rather than silently dropping source data not represented by leaf tokens.
    for line_index, line in enumerate(lines):
        if line_index not in covered and line.strip():
            emit(
                "prose",
                line,
                line_index,
                line_index + 1,
                issues=("markdown_unparsed_line_requires_review",),
            )
    ordered = sorted(blocks, key=lambda b: b.locator.line_start)
    return [
        ParsedBlock.model_validate(
            b.model_dump() | {"sequence": seq, "block_id": f"{source.doc_id}:b{seq:05d}"}
        )
        for seq, b in enumerate(ordered)
    ]
