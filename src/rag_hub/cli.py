"""Offline project verification and local G0–G2 ingestion commands."""

import argparse
import importlib
import json
from pathlib import Path

from rag_hub.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("smoke")
    for name in ("verify-sources", "ingest"):
        sub = commands.add_parser(name)
        sub.add_argument("--root", type=Path, default=Path.cwd())
        sub.add_argument("--registry", default="config/sources.json")
        if name == "ingest":
            sub.add_argument("--local-use-basis", required=True)
            sub.add_argument("--reviews", help="Private hash-bound section review receipts JSON")
            sub.add_argument(
                "--source-manifest", help="Existing private local source for shared stage execution"
            )
            sub.add_argument("--release", help="Private successor foundation fingerprint directory")
            sub.add_argument(
                "--pdf-constraints", help="Trusted private owner-bound paragraph-split evidence"
            )
            sub.add_argument("--output", help="Private immutable shared execution output")
            sub.add_argument(
                "--pdf-classification-evidence",
                help="Trusted private hashed PDF type evidence bundle",
            )
    validation = commands.add_parser("validate-content")
    validation.add_argument("--root", type=Path, default=Path.cwd())
    validation.add_argument("--policy", default="config/validation-policy.json")
    validation.add_argument("--reviews")
    validation.add_argument("--exclude-samples")
    validation.add_argument("--expand-cohort", action="append", default=[])
    validation.add_argument("--role", choices=["acceptance", "calibration"], default="acceptance")
    args = parser.parse_args()
    try:
        if args.command == "smoke":
            for module in (
                "schemas",
                "ingestion",
                "normalization",
                "chunking",
                "embedding",
                "retrieval",
                "generation",
                "evaluation",
                "ui",
                "pipeline",
                "validation_pipeline",
            ):
                importlib.import_module(f"rag_hub.{module}")
            settings = Settings()
            result = {
                "status": "scaffold_ok",
                "milestone": "2.5",
                "content_validation_implemented": True,
                "pipeline_implemented": False,
                "ingestion_implemented": True,
                "top_k": settings.top_k,
            }
        elif args.command == "validate-content":
            from rag_hub.validation_pipeline import validate_content

            result = validate_content(
                args.root,
                policy_path=args.policy,
                reviews_path=args.reviews,
                exclusions_path=args.exclude_samples,
                expansion_cohorts=args.expand_cohort,
                role=args.role,
            )
        else:
            from rag_hub.pipeline import ingest, verify_inputs

            if args.command == "verify-sources":
                result = {"status": "verified", "sources": verify_inputs(args.root, args.registry)}
            else:
                result = ingest(
                    args.root,
                    registry_path=args.registry,
                    use_basis=args.local_use_basis,
                    reviews_path=args.reviews,
                    source_manifest=args.source_manifest,
                    release=args.release,
                    pdf_constraints=args.pdf_constraints,
                    pdf_classification_evidence=args.pdf_classification_evidence,
                    output=args.output,
                )
        print(json.dumps(result))
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
