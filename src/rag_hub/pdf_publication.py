"""POC read-only expiration policy for the unchanged, already-approved cohort.

This cannot authorize QA execution or new publications. Execution uses the strict
scoped_evidence_proofs entrypoint. Reader compatibility is pinned separately from
the immutable historical QA implementation and publication hashes.
"""

import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.pdf_prose_review import COMBINED_RELEASE_COMPONENTS, _evidence_proofs

HISTORICAL_RELEASE_PATH = "config/combined-qa-successor.json"
HISTORICAL_RELEASE_SHA256 = "3bf5e69bc3ec1b152b7a03307ba305f6ad8adeff15aef3d3d36b167ea655d5ec"
READER_CONFIG = "config/pdf-publication-reader.json"
SUCCESSOR_READER_CONFIG = "config/pdf-publication-reader-html-v1.json"
CONTEXT_READER_CONFIG = "config/pdf-publication-reader-html-context-v1.json"
TEXT_READER_CONFIG = "config/pdf-publication-reader-html-text-v1.json"
C10_READER_CONFIG = "config/pdf-publication-reader-c10-v1.json"
PDF_TEXT_READER_CONFIG = "config/pdf-publication-reader-text-recovery-v1.json"
PDF_TEXT_V11_READER_CONFIG = "config/pdf-publication-reader-text-recovery-v1-1.json"
PDF_RESIDUAL_READER_CONFIG = "config/pdf-publication-reader-residual-v1.json"
MARKDOWN_READER_CONFIG = "config/pdf-publication-reader-markdown-v1-1.json"
CHANGED_READER_FILES = {
    "src/rag_hub/pdf_prose_review.py",
    "src/rag_hub/pdf_prose_handoff.py",
}
READER_FILES = set(COMBINED_RELEASE_COMPONENTS) | {
    "src/rag_hub/pdf_publication.py",
    "src/rag_hub/ui.py",
}


def utc_now():
    return datetime.now(UTC)


def authorization_interval(value):
    try:
        start = datetime.fromisoformat(value["valid_from"])
        end = datetime.fromisoformat(value["expires_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid_publication_authorization_interval") from exc
    if not start.tzinfo or not end.tzinfo or start >= end:
        raise ValueError("invalid_publication_authorization_interval")
    if utc_now() < start:
        raise ValueError("publication_authorization_not_yet_valid")
    return start, end


def publication_metadata(authorization):
    _, end = authorization_interval(authorization)
    return _status_metadata(authorization["expires_at"], utc_now() >= end)


def display_metadata(metadata):
    """An answer may finish after expiry even if its passages were read earlier."""
    end = datetime.fromisoformat(metadata["expires_at"])
    if not end.tzinfo:
        raise ValueError("invalid_publication_expiration")
    return _status_metadata(
        metadata["expires_at"], metadata["status"] == "EXPIRED" or utc_now() >= end
    )


def _status_metadata(expires_at, expired):
    end = datetime.fromisoformat(expires_at)
    return {
        "status": "EXPIRED" if expired else "VALID",
        "expires_at": expires_at,
        "warning": (
            "Publication authorization expired on "
            + end.astimezone(UTC).isoformat()
            + ". This answer uses previously approved PDF content; its source integrity "
            "and complete-paragraph approval were verified."
        )
        if expired
        else None,
        "warning_code": "PDF_PUBLICATION_EXPIRED" if expired else None,
        "display_to_user_when_used": expired,
        "retrieval_allowed": True,
    }


def verify_reader(root, release_path, expected_release_sha256):
    """Verify actual reader bytes without relabeling the historical QA release."""
    root = Path(root).resolve()
    if (
        str(release_path) != HISTORICAL_RELEASE_PATH
        or expected_release_sha256 != HISTORICAL_RELEASE_SHA256
    ):
        raise ValueError("publication_reader_not_authorized_for_this_QA_release")
    original = local_path(root, release_path).read_bytes()
    if digest(original) != expected_release_sha256:
        raise ValueError("historical_QA_manifest_hash_mismatch")
    historical = json.loads(original)
    predecessor_bytes = local_path(root, READER_CONFIG).read_bytes()
    config = json.loads(predecessor_bytes)
    # An explicitly installed, fingerprinted compatibility successor preserves
    # the exact historical publication allowlist. It grants no new PDF admission.
    successor_path = local_path(root, PDF_RESIDUAL_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, PDF_TEXT_V11_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, PDF_TEXT_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, C10_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, MARKDOWN_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, TEXT_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, CONTEXT_READER_CONFIG)
    if not successor_path.exists():
        successor_path = local_path(root, SUCCESSOR_READER_CONFIG)
    successor = json.loads(successor_path.read_bytes()) if successor_path.exists() else None
    if successor is not None:
        if successor_path in {
            local_path(root, PDF_TEXT_READER_CONFIG),
            local_path(root, PDF_TEXT_V11_READER_CONFIG),
            local_path(root, PDF_RESIDUAL_READER_CONFIG),
        }:
            from rag_hub.pdf_text_recovery import verify_release as verify_successor
        elif successor_path in {
            local_path(root, MARKDOWN_READER_CONFIG),
            local_path(root, C10_READER_CONFIG),
        }:
            from rag_hub.markdown_qualification import verify_release as verify_successor
        else:
            from rag_hub.html_qualification import verify_release as verify_successor

        release = verify_successor(
            root, successor["qa_release_path"], successor["qa_release_sha256"]
        )
        if (
            successor.get("predecessor_reader_sha256") != digest(predecessor_bytes)
            or successor.get("approved_publications") != config.get("approved_publications")
            or successor.get("historical_release_sha256") != expected_release_sha256
            or successor.get("schema") != "pdf-publication-reader-1.1"
            or set(successor.get("files", {})) != READER_FILES
            or any(successor["files"][p] != release["files"][p] for p in READER_FILES)
        ):
            raise ValueError("invalid_HTML_successor_PDF_reader_compatibility")
        config = dict(successor, schema="pdf-publication-reader-1.0")
    if (
        config.get("schema") != "pdf-publication-reader-1.0"
        or config.get("historical_release_sha256") != expected_release_sha256
        or set(config.get("files", {})) != READER_FILES
        or set(historical.get("files", {})) != set(COMBINED_RELEASE_COMPONENTS)
        or Path(__file__).resolve() != root / "src/rag_hub/pdf_publication.py"
    ):
        raise ValueError("invalid_publication_reader_fingerprint_contract")
    for name in COMBINED_RELEASE_COMPONENTS:
        allowed = CHANGED_READER_FILES | (
            {"src/rag_hub/shared/qa.py", "src/rag_hub/validation_reviews.py"}
            if successor is not None
            else set()
        )
        if name not in allowed and config["files"][name] != historical["files"][name]:
            raise ValueError("publication_reader_changed_QA_or_HTML_components")
    for name, sha in config["files"].items():
        if digest(local_path(root, name).read_bytes()) != sha:
            raise ValueError("publication_reader_component_changed: " + name)
    if historical["dependencies"] != {
        name: importlib.metadata.version(name) for name in historical["dependencies"]
    }:
        raise ValueError("publication_reader_dependency_changed")
    # The installed, trusted reader configuration pins the four original
    # publications. Source text and publication payloads cannot add an exception.
    if len(config.get("approved_publications", {})) != 4:
        raise ValueError("invalid_frozen_publication_allowlist")
    return config


def published_evidence_proofs(root, source, sections, results, **arguments):
    """Reuse every receipt/span/policy check; expiration alone is informational."""
    return _evidence_proofs(
        root,
        source,
        sections,
        results,
        **arguments,
        release_check=verify_reader,
        authorization_check=authorization_interval,
    )
