"""Explicit offline Q05 post-validation only. No provider, credentials, retrieval or prompt build."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from .adapter import BASES, FREEZE
from .artifacts import Store, digest, sha
from .post_generation import PostGenerationValidator


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    path.chmod(0o400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--supersedes", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = (root / args.output).resolve()
    if (not output.is_relative_to(root / "data/evals/post-generation") or output.exists()
            or output.parent != root / "data/evals/post-generation"):
        raise ValueError("NEW_VERSIONED_PRIVATE_OUTPUT_REQUIRED")
    store = Store(root)
    for key in ("freeze", "phase2", "delivery", "qualification"):
        path, fingerprint = BASES[key]
        store.manifest(path, expected=fingerprint)
    generation = "data/evals/generation/live-q05-funded-v1/MANIFEST.json"
    store.manifest(generation,
                   expected="3077d9d502dfdab16791ce85f2b1ab432ef8c0e8f39e2f5874dce36c279297f8")
    candidate_name = "data/evals/pre-generation-gate/experiment-v1/candidates/M9-Q05.json"
    case = store.json("data/evals/m8-delivery/experiment-v1/cases/M9-Q05-B-128000.json")
    # Semantic gold bytes are verified, never parsed by this runtime validation.
    result = json.loads((root / candidate_name).read_bytes())
    if digest(result) != case["candidate_envelope_sha256"]:
        raise ValueError("CANDIDATE_BINDING_CHANGED")
    store.bind(candidate_name, sha(root / candidate_name))
    question = store.json("data/evals/ranking/phase2-v1/QUESTIONS_ONLY.json")["questions"]["M9-Q05"]
    response_name = "data/evals/generation/live-q05-funded-v1/GENERATED_RESPONSE.json"
    response = store.json(response_name)
    audit = store.json("data/evals/generation/live-q05-funded-v1/GENERATION_AUDIT.json")
    before = {name: sha(root / name) for name in store.verified}
    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.indexing.m5_index import no_network
    from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA

    calls = []

    def forbidden(*args, **kwargs):
        calls.append("FORBIDDEN_PROVIDER_METHOD")
        raise RuntimeError("NO_PROVIDER_AUTHORIZATION")

    no_network()
    print("Verified inputs; reopening Q05 through unchanged M8 for offline validation.", flush=True)
    with patch.object(OpenAIAdapter, "verify_model", forbidden), \
            patch.object(OpenAIAdapter, "count", forbidden), patch.object(OpenAIAdapter, "invoke", forbidden):
        service = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
        package = service.assemble(result, token_budget=128000)
        if digest(package) != audit["M8_package_sha256"]:
            raise ValueError("M8_PACKAGE_CHANGED")
        report = PostGenerationValidator(service).validate(response, package, result, question=question)
        report.update(question_id="M9-Q05", response_file_sha256=sha(root / response_name),
                      generation_experiment_manifest_sha256=store.verified[generation],
                      date=datetime.now(UTC).isoformat(),
                      ground_truth_parsed_by_runtime=False, provider_requests=0)
    if calls or any(sha(root / n) != h for n, h in before.items()):
        raise ValueError("PROVIDER_OR_PRESERVATION_VIOLATION")
    output.mkdir(mode=0o700, parents=True)
    write(output / "VALIDATION.json", report)
    write(output / "VERIFICATION.json", {"input_hashes_checked": len(before), "changed": [],
          "provider_method_attempts": calls, "credentials_read": False,
          "source_text_written": False, "full_prompt_persisted": False,
          "original_response_preserved": True, "ground_truth_parsed_by_runtime": False})
    write(output / "MANIFEST.json", {"schema": "post-generation-validation-manifest-1.0",
          "status": "COMPLETED_SEALED", "dataset_freeze_manifest_sha256": FREEZE,
          "question_id": "M9-Q05", "date": report["date"],
          "files": {p.name: sha(p) for p in output.iterdir()},
          "input_bindings": {generation: before[generation], response_name: before[response_name],
                             candidate_name: before[candidate_name],
                             BASES["freeze"][0]: FREEZE,
                             BASES["qualification"][0]: BASES["qualification"][1]},
          "supersedes_manifest_sha256": args.supersedes,
          "correction": "Native field is citation_locators, not citations" if args.supersedes else None,
          "authority": "DETERMINISTIC_CHECKS_NOT_SEMANTIC_CERTIFICATION"})
    print(json.dumps({"status": report["overall_status"], "quote_matches":
          sum(c["status"] == "VERBATIM_SOURCE_MATCH" for c in report["quote_checks"]["checks"]),
          "qualification_status": report["qualification_status"], "provider_requests": 0,
          "manifest_sha256": sha(output / "MANIFEST.json")}))


if __name__ == "__main__":
    main()
