"""UI interfaces and presentation helpers; no application adapter implemented."""

from typing import Protocol

from rag_hub.generation import Generator
from rag_hub.pdf_publication import display_metadata
from rag_hub.retrieval import Retriever


def format_answer_for_display(answer_text: str, used_passages) -> str:
    """Append publication warnings for evidence actually used in this answer.

    The future UI must use this presentation function rather than displaying
    generation text alone. It performs no retrieval or generation.
    """
    used_passages = tuple(used_passages)
    for passage in used_passages:
        if "authoritative_publication" not in passage:
            continue
        metadata = passage.get("publication", {})
        if (
            metadata.get("status") not in {"VALID", "EXPIRED"}
            or not metadata.get("expires_at")
            or (
                metadata["status"] == "EXPIRED"
                and (not metadata.get("warning") or not metadata.get("display_to_user_when_used"))
            )
        ):
            raise ValueError("missing_publication_display_metadata")
    current = [display_metadata(p["publication"]) for p in used_passages if "publication" in p]
    warnings = dict.fromkeys(m["warning"] for m in current if m["display_to_user_when_used"])
    return answer_text + "".join("\n\nWarning: " + text for text in warnings)


class ChatUI(Protocol):
    def run(self, retriever: Retriever, generator: Generator) -> None:
        """Display citations and use format_answer_for_display with actual used passages."""
        ...
