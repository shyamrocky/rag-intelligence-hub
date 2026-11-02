"""Explicit one-question dry run by default. Never prints publisher requests/answers."""

import argparse
import json
from pathlib import Path

from tools.generation.openai_adapter import OpenAIAdapter
from tools.generation.profiles import ProfileError, load_settings, resolve
from tools.generation.service import GenerationService
from tools.generation.telemetry import load_pricing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--pricing", type=Path)
    parser.add_argument("--question-id", choices=["M9-Q05"], default="M9-Q05")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--allow-paid-inference", action="store_true")
    parser.add_argument("--allow-source-transfer", action="store_true")
    parser.add_argument("--provider-preflight", action="store_true")
    args = parser.parse_args(argv)
    if args.live and not (args.allow_paid_inference and args.allow_source_transfer):
        parser.error("live mode requires explicit paid-inference and source-transfer authorization")
    try:
        settings = load_settings(args.settings, model=args.model)
        resolve(settings)
        # No generation/SDK invocation just because a valid prompt exists.
        from tools.evidence.service import EvidenceService
        from tools.pre_generation_gate.assembly import PromptAssemblyGate
        from tools.pre_generation_gate.contract import digest
        from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA

        root = Path(__file__).resolve().parents[2]
        questions = json.loads(
            (root / "data/evals/ranking/phase2-v1/QUESTIONS_ONLY.json").read_bytes()
        )
        question = questions["questions"][args.question_id]
        result = json.loads(
            (
                root / "data/evals/pre-generation-gate/experiment-v1/candidates/M9-Q05.json"
            ).read_bytes()
        )
        if result["parameters"] != {"top_k": 30, "candidate_depth": 50, "rrf_k": 60, "filters": {}}:
            raise ValueError("sealed_candidate_parameters_differ")
        # Bind sealed inputs before trusted in-memory reconstruction; no gold labels.
        seal = json.loads(
            (root / "data/evals/prompt-assembly/experiment-v1/audits/M9-Q05.json").read_bytes()
        )
        if digest(result) != seal["M7_result_sha256"]:
            raise ValueError("sealed_candidate_hash_differs")
        evidence = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
        package = evidence.assemble(result, token_budget=128000)
        if digest(package) != seal["M8_package_sha256"]:
            raise ValueError("sealed_M8_package_differs")
        gate = PromptAssemblyGate(evidence)
        prepared = gate.prepare(question, package, result)
        service = GenerationService(
            gate,
            OpenAIAdapter(timeout_seconds=settings.timeout_seconds),
            settings,
            pricing=load_pricing(args.pricing),
        )
        if args.live:
            generated = service.generate(
                prepared,
                question,
                package,
                result,
                allow_paid_inference=args.allow_paid_inference,
                allow_source_transfer=args.allow_source_transfer,
            )
        else:
            generated = service.dry_run(
                prepared,
                question,
                package,
                result,
                allow_provider_preflight=args.provider_preflight,
                allow_source_transfer=args.allow_source_transfer,
            )
        audit = generated.audit | {
            "question_id": args.question_id,
            "candidate_count": len(result["candidates"]),
            "included_parent_count": len(package["parents"]),
            "M8_BGE_evidence_tokens_not_generator_tokens": package["budget"][
                "exact_llm_evidence_tokens"
            ],
        }
        print(json.dumps(audit, indent=2, sort_keys=True))
        return 0 if generated.audit["status"] in {"READY", "GENERATED_STRUCTURE_VALID"} else 2
    except ProfileError as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_CONFIGURATION",
                    "blocking_reasons": [str(error)],
                    "generation_executed": False,
                }
            )
        )
        return 2
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        ImportError,
        RuntimeError,
        AttributeError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_CONFIGURATION_OR_INTEGRITY",
                    "blocking_reasons": ["CONFIGURATION_RUNTIME_OR_PRIVATE_BINDING_CHECK_FAILED"],
                    "error_type": type(error).__name__,
                    "generation_executed": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
