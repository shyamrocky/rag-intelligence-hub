"""Deterministic, non-executing semantic HTML adapter with exact raw locators.

This bounded adapter preserves an evidence DOM alongside existing ParsedBlocks.
It makes no browser-rendering or independent content-correctness claim.
"""

import html
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

from rag_hub.acquire import digest
from rag_hub.schemas import Locator, ParsedBlock

VERSION = "fixed-html-1.0"
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
SKIP = {"script", "style", "noscript", "template", "nav", "footer", "button", "svg"}
ATOMIC = {
    "p": "paragraph",
    "pre": "code_block",
    "ul": "unordered_list",
    "ol": "ordered_list",
    "table": "table",
    "blockquote": "blockquote",
    "figure": "figure",
    "figcaption": "caption",
    "img": "image",
    "math": "equation",
    "dl": "definition_list",
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


@dataclass(eq=False)
class Text:
    value: str
    start: int
    end: int
    parent: "Node"


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict
    start: int
    end: int
    parent: "Node | None" = None
    children: list = field(default_factory=list)
    path: str = ""


class DOM(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0] + [m.end() for m in re.finditer("\n", source)]
        self.root = Node("document", {}, 0, len(source), path="/document[1]")
        self.stack = [self.root]
        self.nodes = []
        self.texts = []
        self.repairs = []
        self.feed(source)
        self.close()
        for node in self.stack[1:]:
            node.end = len(source)
            self.repairs.append({"dom_path": node.path, "reason": "unclosed_at_eof"})

    def position(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.position()
        # HTML's optional-end-tag rules needed by documentation tables/lists.
        close_set = (
            {"li"}
            if tag == "li"
            else {"td", "th"}
            if tag in ("td", "th")
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
        if close_set:
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag in close_set:
                    # A nested list item must not close its enclosing list item.
                    if tag == "li" and any(n.tag in ("ul", "ol") for n in self.stack[index + 1 :]):
                        break
                    for node in self.stack[index:]:
                        node.end = start
                    self.stack = self.stack[:index]
                    break
                if self.stack[index].tag in ("table", "ul", "ol"):
                    break
        parent = self.stack[-1]
        count = 1 + sum(isinstance(n, Node) and n.tag == tag for n in parent.children)
        node = Node(
            tag,
            dict(attrs),
            start,
            start + len(self.get_starttag_text()),
            parent,
            path=f"{parent.path}/{tag}[{count}]",
        )
        parent.children.append(node)
        self.nodes.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        end = self.source.find(">", self.position()) + 1
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                for node in self.stack[index:]:
                    node.end = end
                self.stack = self.stack[:index]
                break

    def add_text(self, value, length):
        start = self.position()
        text = Text(value, start, start + length, self.stack[-1])
        self.stack[-1].children.append(text)
        self.texts.append(text)

    def handle_data(self, data):
        self.add_text(data, len(data))

    def handle_entityref(self, name):
        raw = "&" + name
        if self.source[self.position() + len(raw) :].startswith(";"):
            raw += ";"
        self.add_text(html.unescape(raw), len(raw))

    def handle_charref(self, name):
        raw = "&#" + name
        if self.source[self.position() + len(raw) :].startswith(";"):
            raw += ";"
        self.add_text(html.unescape(raw), len(raw))


def descendants(node):
    for child in node.children:
        yield child
        if isinstance(child, Node):
            yield from descendants(child)


def ancestors(node):
    while node:
        yield node
        node = node.parent


def exclusion(node):
    if node.tag in SKIP:
        return "non_article_" + node.tag
    attrs = node.attrs
    if attrs.get("role") in ("navigation", "banner", "contentinfo"):
        return "explicit_page_furniture_role"
    classes = set((attrs.get("class") or "").split())
    if classes & {
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
    }:
        return "explicit_navigation_or_control"
    if attrs.get("id") in {
        "table-of-contents",
        "on-this-page",
        "feedback",
        "pagination",
        "in-article-cta",
    }:
        return "explicit_navigation_or_control"
    if node.tag == "a" and attrs.get("aria-label") in {
        "Navigate to header",
        "Direct link to heading",
    }:
        return "heading_link_control"
    return None


def hidden(node):
    a = node.attrs
    return (
        "hidden" in a
        or a.get("aria-hidden") == "true"
        or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style") or ""))
    )


def container_kind(node):
    role = node.attrs.get("role")
    classes = {s.lower() for s in (node.attrs.get("class") or "").split()}
    if node.tag == "details":
        return "expandable"
    if role in ("tabpanel", "tab", "tablist"):
        return role
    if (
        role in ("note", "alert")
        or node.tag == "aside"
        or classes
        & {"note", "tip", "warning", "important", "caution", "admonition", "callout", "hint"}
    ):
        return "callout"
    if role in ("doc-endnote", "doc-footnote", "doc-bibliography") or classes & {
        "footnote",
        "footnotes",
        "citation",
    }:
        return "footnote_or_citation"
    return None


def render(node, *, exact=False):
    if isinstance(node, Text):
        return node.value
    if exclusion(node):
        return ""
    if node.tag == "br":
        return "\n"
    if node.tag == "img":
        return node.attrs.get("alt") or ""
    value = "".join(render(c, exact=exact or node.tag == "pre") for c in node.children)
    if exact or node.tag == "pre":
        return value
    value = re.sub(r"[\t\r\n\f ]+", " ", value)
    return value + ("\n" if node.tag not in INLINE or node.attrs.get("data-as") == "p" else "")


def evidence_tree(node, url):
    if isinstance(node, Text):
        return {"text": node.value, "raw_char_span": [node.start, node.end]}
    if exclusion(node):
        return {"tag": node.tag, "dom_path": node.path, "excluded": exclusion(node)}
    attrs = {
        k: v
        for k, v in node.attrs.items()
        if k
        in {
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
    }
    if attrs.get("href"):
        attrs["resolved_href"] = urljoin(url, attrs["href"])
    if attrs.get("src"):
        attrs["resolved_src"] = urljoin(url, attrs["src"])
    return {
        "tag": node.tag,
        "attrs": attrs,
        "dom_path": node.path,
        "raw_char_span": [node.start, node.end],
        "children": [evidence_tree(c, url) for c in node.children],
    }


def select_body(dom):
    # Prefer publisher semantic body containers over their larger navigation shells.
    for token in ("mdx-content", "sl-markdown-content", "md-content__inner"):
        matches = [n for n in dom.nodes if token in (n.attrs.get("class") or "").split()]
        if len(matches) == 1:
            return matches[0], "class:" + token
    for attr in ("data-article-body", "data-content-ref-root"):
        matches = [n for n in dom.nodes if attr in n.attrs]
        if len(matches) == 1:
            return matches[0], "attribute:" + attr
    prose = [
        n
        for n in dom.nodes
        if "prose" in (n.attrs.get("class") or "").split() and len(render(n)) > 1000
    ]
    if len(prose) == 1:
        return prose[0], "unique_substantive_prose_container"
    content = [
        n
        for n in dom.nodes
        if (n.attrs.get("class") or "").split() == ["content"] and len(render(n)) > 1000
    ]
    if len(content) == 1:
        return content[0], "unique_substantive_content_container"
    for attr, value in (("itemprop", "articleBody"), ("role", "main")):
        matches = [n for n in dom.nodes if n.attrs.get(attr) == value]
        if len(matches) == 1:
            return matches[0], f"{attr}:{value}"
    articles = [n for n in dom.nodes if n.tag == "article" and len(render(n)) > 1000]
    if articles:
        return max(articles, key=lambda n: len(render(n))), "largest_substantive_article"
    for tag in ("main", "body"):
        matches = [n for n in dom.nodes if n.tag == tag]
        if len(matches) == 1:
            return matches[0], tag
    raise ValueError("no_article_body_requires_review")


def parse_html(raw, source, *, charset="utf-8"):
    """Return existing blocks plus lossless DOM evidence, exclusions and accounting."""
    if digest(raw) != source.raw_sha256:
        raise ValueError("raw_source_integrity_mismatch")
    text = raw.decode(charset, errors="strict")
    dom = DOM(text)
    body, method = select_body(dom)
    title_nodes = [n for n in dom.nodes if n.tag == "title"]
    h1s = [n for n in dom.nodes if n.tag == "h1" and not any(exclusion(a) for a in ancestors(n))]
    title = render(h1s[0]).strip() if h1s else render(title_nodes[0]).strip() if title_nodes else ""
    selected = set(descendants(body)) | {body}
    records, exclusions, containers = [], [], []
    headings = []
    accounted = set()

    def record(node, kind, leaves=None):
        nonlocal headings
        leaves = (
            leaves if leaves is not None else [t for t in descendants(node) if isinstance(t, Text)]
        )
        payload = render(node, exact=kind == "code_block")
        if kind != "code_block":
            payload = re.sub(r"[\t\r\n\f ]+", " ", payload).strip()
        if not payload and kind not in ("image", "figure", "equation"):
            return
        issues = []
        if re.fullmatch(r"h[1-6]", node.tag):
            level = int(node.tag[1])
            if headings and level > headings[-1][0] + 1:
                issues.append("source_heading_level_gap")
            headings = [(l, v) for l, v in headings if l < level] + [(level, payload)]
        chain = list(ancestors(node))
        if any(hidden(a) for a in chain):
            issues.append("hidden_or_alternative_content_unverified")
        if kind in ("table", "equation", "image", "figure", "unknown"):
            issues.append("specialized_or_unclassified_content_requires_review")
        if any(
            n.tag in ("math", "iframe", "canvas", "video", "svg", "img")
            and not any(exclusion(a) for a in ancestors(n.parent))
            for n in descendants(node)
            if isinstance(n, Node)
        ):
            issues.append("embedded_visual_or_dynamic_content_unverified")
        anchor = next((a.attrs["id"] for a in chain if a.attrs.get("id")), None)
        mapping = {
            "heading": "heading",
            "paragraph": "prose",
            "code_block": "code",
            "ordered_list": "list",
            "unordered_list": "list",
            "table": "table",
            "caption": "figure_caption",
            "equation": "equation",
        }
        block_type = mapping.get(kind, "prose" if kind == "blockquote" else "metadata")
        language = None
        if kind == "code_block":
            classes = " ".join(
                (n.attrs.get("class") or "")
                for n in [node, *descendants(node)]
                if isinstance(n, Node)
            )
            match = re.search(r"(?:language-|highlight-)([\w+-]+)", classes)
            language = match[1] if match else None
            if not language:
                language = next(
                    (a.attrs.get("language") for a in chain if a.attrs.get("language")), None
                )
        block = ParsedBlock(
            block_id=f"{source.doc_id}:{source.raw_sha256[:12]}:h{len(records):05d}",
            doc_id=source.doc_id,
            snapshot_id=source.snapshot_id,
            sequence=len(records),
            block_type=block_type,
            content=payload,
            heading_path=tuple(v for _, v in headings),
            locator=Locator(
                url=source.canonical_url,
                anchor=anchor,
                line_start=text.count("\n", 0, node.start) + 1,
                line_end=text.count("\n", 0, node.end) + 1,
            ),
            language=language,
            raw_sha256=source.raw_sha256,
            content_sha256=digest(payload.encode()),
            parser_version=VERSION,
            issues=tuple(issues),
            verification_status="hold",
        )
        active_leaves = [t for t in leaves if not any(exclusion(a) for a in ancestors(t.parent))]
        accounted.update(active_leaves)
        raw_span = text[node.start : node.end]
        records.append(
            {
                "block": block.model_dump(mode="json"),
                "classification": kind,
                "dom_path": node.path,
                "raw_char_span": [node.start, node.end],
                "raw_fragment_sha256": digest(raw_span.encode(charset)),
                "source_tree": evidence_tree(node, str(source.canonical_url)),
                "contexts": [a.path for a in reversed(chain) if container_kind(a)],
                "transformations": [
                    "decode_html_entities",
                    "preserve_code_whitespace"
                    if kind == "code_block"
                    else "collapse_html_ascii_whitespace",
                ],
            }
        )

    def walk(node):
        nonlocal headings
        saved_headings = (
            list(headings)
            if node.attrs.get("role") == "tabpanel" or node.tag == "details"
            else None
        )
        if container_kind(node):
            containers.append(
                {
                    "dom_path": node.path,
                    "tag": node.tag,
                    "classification": container_kind(node),
                    "source_label": render_unfiltered(node).strip()
                    if node.attrs.get("role") == "tab"
                    else node.attrs.get("aria-label"),
                    "label_to_panel_relationship": "unverified_unless_explicit_ARIA_binding_present",
                    "attrs": node.attrs,
                    "raw_char_span": [node.start, node.end],
                    "status": "source_present_interaction_unverified",
                }
            )
        reason = exclusion(node)
        if reason:
            exclusions.append(
                {
                    "dom_path": node.path,
                    "reason": reason,
                    "raw_char_span": [node.start, node.end],
                    "source_text": render_unfiltered(node),
                }
            )
            return
        kind = "heading" if re.fullmatch(r"h[1-6]", node.tag) else ATOMIC.get(node.tag)
        if node.attrs.get("data-as") == "p":
            kind = "paragraph"
        if (
            kind == "paragraph"
            and any(isinstance(n, Node) and n.tag == "img" for n in descendants(node))
            and not any(isinstance(n, Text) and n.value.strip() for n in descendants(node))
        ):
            kind = "image"
        if kind:
            record(node, kind)
            return
        # Residual inline runs become explicit unknowns, never silently dropped.
        run = []

        def flush():
            if any(
                isinstance(t, Text) and t.value.strip()
                for n in run
                for t in ([n] if isinstance(n, Text) else descendants(n))
            ):
                synthetic = Node(
                    "unknown",
                    {},
                    run[0].start,
                    run[-1].end,
                    node,
                    children=list(run),
                    path=node.path + "/inline-run[" + str(run[0].start) + "]",
                )
                record(synthetic, "unknown")
            run.clear()

        for child in node.children:
            if isinstance(child, Text) or child.tag in INLINE and child.attrs.get("data-as") != "p":
                run.append(child)
            else:
                flush()
                walk(child)
        flush()
        if saved_headings is not None:
            headings = saved_headings

    # Some documentation layouts put the source H1 above the body container.
    if h1s and h1s[0] not in selected and h1s[0].start < body.start:
        record(h1s[0], "heading")
        selected.update(descendants(h1s[0]))
        selected.add(h1s[0])
    walk(body)
    # Every meaningful decoded text leaf is either accounted or explicitly excluded.
    unassigned = []
    outside = 0
    for leaf in dom.texts:
        if not leaf.value.strip() or leaf in accounted:
            continue
        causes = [exclusion(a) for a in ancestors(leaf.parent) if exclusion(a)]
        if leaf not in selected:
            outside += len(leaf.value)
        elif not causes:
            unassigned.append({"raw_char_span": [leaf.start, leaf.end], "text": leaf.value})
    features = Counter(n.tag for n in selected if isinstance(n, Node))
    intervals = sorted(
        [(body.start, body.end)] + [(h1s[0].start, h1s[0].end)]
        if h1s and h1s[0] not in set(descendants(body))
        else [(body.start, body.end)]
    )
    outside_regions = []
    previous_end = 0
    for start, end in intervals + [(len(text), len(text))]:
        if start > previous_end:
            outside_regions.append(
                {
                    "raw_char_span": [previous_end, start],
                    "reason": "outside_selected_article_and_primary_title",
                    "raw_fragment_sha256": digest(text[previous_end:start].encode(charset)),
                }
            )
        previous_end = max(previous_end, end)
    return {
        "parser_version": VERSION,
        "title": title,
        "html_title": render(title_nodes[0]).strip() if title_nodes else None,
        "body_dom_path": body.path,
        "body_selection": method,
        "records": records,
        "containers": containers,
        "exclusions": exclusions,
        "excluded_outer_regions": outside_regions,
        "visual_and_dynamic_inventory": [
            {
                "tag": n.tag,
                "attrs": n.attrs,
                "dom_path": n.path,
                "raw_char_span": [n.start, n.end],
                "disposition": "HOLD_no_asset_fetch_or_rendering",
                "inside_control": any(exclusion(a) for a in ancestors(n.parent)),
            }
            for n in sorted(selected, key=lambda n: n.start)
            if isinstance(n, Node) and n.tag in ("img", "svg", "canvas", "iframe", "video")
        ],
        "dom_repairs": dom.repairs,
        "features": dict(features),
        "accounting": {
            "meaningful_body_text_nodes": sum(
                isinstance(n, Text) and bool(n.value.strip())
                for n in sorted(selected, key=lambda n: n.start)
            ),
            "accounted_text_nodes": sum(bool(n.value.strip()) for n in accounted),
            "outside_body_decoded_codepoints": outside,
            "unassigned_body_text": unassigned,
        },
        "source_metadata": [
            {"tag": n.tag, "attrs": n.attrs}
            for n in dom.nodes
            if n.tag in ("meta", "link")
            and (
                n.attrs.get("name") or n.attrs.get("property") or n.attrs.get("rel") == "canonical"
            )
        ],
    }


def render_unfiltered(node):
    """Evidence only: no cleaning, no source-directed execution."""
    return "".join(n.value for n in descendants(node) if isinstance(n, Text))
