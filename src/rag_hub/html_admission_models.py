"""Scope-bound HTML automatic decisions; legacy consumers reject the new basis."""

from typing import Literal

from pydantic import model_validator

from rag_hub.validation_models import QualityDecision


class ScopedHtmlDecision(QualityDecision):
    schema_version: Literal["html-scoped-decision-1.0"] = "html-scoped-decision-1.0"
    basis: Literal["scoped_html_automatic"] = "scoped_html_automatic"
    scope: dict
    resolved_restrictions: dict[str, str]

    @model_validator(mode="after")
    def bounded(self):
        scope = self.scope
        ids = scope.get("required_section_ids", [])
        if (
            self.status != "approved_for_index"
            or self.reasons
            or self.section_id not in ids
            or not ids
            or len(ids) != len(set(ids))
            or scope.get("consumption") != "complete_unit_only"
            or scope.get("source_format") != "html"
            or scope.get("whole_source_ready") is not False
            or not all(
                scope.get(k)
                for k in (
                    "unit_id",
                    "unit_sha256",
                    "qualification_policy_sha256",
                    "authorization_sha256",
                    "qa_release_sha256",
                    "role",
                )
            )
        ):
            raise ValueError("invalid_scoped_HTML_decision")
        return self
