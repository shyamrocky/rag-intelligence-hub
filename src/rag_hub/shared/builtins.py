"""Thin wrappers only; original PDF and Markdown parsers remain untouched."""

from rag_hub.parse_markdown import parse_markdown
from rag_hub.parse_pdf import parse_pdf
from rag_hub.pdf_structure import pdf_parents
from rag_hub.source_fidelity import check_markdown

from .evidence import Check
from .registry import Adapter
from .structure import atomic_parents


class BoundParser:
    def __init__(self, data, options, function):
        self.data, self.options, self.function = data, options, function

    def parse(self, source):
        if self.function is parse_pdf:
            return self.function(self.data, source, self.options.get("expected_pages"))
        return self.function(self.data, source)


def markdown_factory(data, options):
    return BoundParser(data, options, parse_markdown)


def pdf_factory(data, options):
    return BoundParser(data, options, parse_pdf)


def markdown_fidelity(data, source, blocks, sections, options):
    lookup = {b.block_id: b for b in blocks}
    reasons = [
        reason for s in sections for reason in check_markdown(s, lookup[s.block_ids[0]], data)
    ]
    lines = data.decode().splitlines(keepends=True)
    covered = {
        n
        for b in blocks
        if b.locator.line_start is not None
        for n in range(b.locator.line_start, b.locator.line_end + 1)
    }
    missing = any(line.strip() and n not in covered for n, line in enumerate(lines, 1))
    valid = all(
        b.locator.line_start
        and b.locator.line_end
        and 1 <= b.locator.line_start <= b.locator.line_end <= len(lines)
        for b in blocks
    )
    order = [(b.locator.line_start, b.locator.line_end) for b in blocks]
    outcomes = {
        "source_text": not reasons,
        "source_locations": valid,
        "source_order": order == sorted(order),
        "source_membership": not missing,
    }
    return [
        Check(
            name=n,
            dimension="source_fidelity",
            outcome="pass" if good else "fail",
            evidence=("blocks.json", "sections.json", "source-witness.json"),
        )
        for n, good in outcomes.items()
    ]


def pdf_fidelity(data, source, blocks, sections, options):
    # Do not falsely certify native layout just because the wrapper ran.
    return [
        Check(name=n, dimension="source_fidelity", outcome="pending", evidence=("blocks.json",))
        for n in ("source_text", "source_locations", "source_order", "source_membership")
    ]


def entries():
    return (
        Adapter(
            "maintained-pymupdf",
            "pdf",
            "pdf-v1+nontext-1.0",
            pdf_factory,
            pdf_fidelity,
            pdf_parents,
            dependencies=("pymupdf",),
        ),
        Adapter(
            "baseline-markdown",
            "markdown_mdx",
            "mdx-v1",
            markdown_factory,
            markdown_fidelity,
            atomic_parents,
            dependencies=("markdown-it-py",),
        ),
    )
