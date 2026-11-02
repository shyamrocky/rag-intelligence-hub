"""Verify archived bytes, then replay original review assertions in a copied private root."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "workspace/pdf-remediation/phase3/nontext-compatibility-v1/before"
MODULES = (
    "validation_models", "source_fidelity", "content_validation", "validation_sampling",
    "validation_reviews", "validation_pipeline",
)
VALIDATOR = "c3509d64beca21a2d501d72ea5376a9612fc91ecb15900d923c66bb7525e8369"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_foundation_files():
    """Select only byte-identical originals; never refresh a historical fingerprint."""
    manifest = ROOT / "workspace/ext01/v1/foundation-freeze.json"
    receipt = json.loads(manifest.with_name("foundation-freeze-receipt.json").read_bytes())
    assert sha(manifest) == receipt["foundation_manifest_sha256"]
    freeze = json.loads(manifest.read_bytes())
    chosen = {}
    for rel, expected in freeze["files"].items():
        candidates = (ROOT / rel, ARCHIVE / rel)
        matches = [p for p in candidates if p.is_file() and sha(p) == expected]
        assert matches, f"historical_component_unavailable:{rel}"
        chosen[rel] = matches[0]
    return freeze, chosen


def replay_reviews():
    """No original corpus/publication writes; historical output lives in a disposable copy."""
    historical_foundation_files()
    blob = b"".join((ARCHIVE / "src/rag_hub" / (n + ".py")).read_bytes() for n in MODULES)
    assert hashlib.sha256(blob).hexdigest() == VALIDATOR
    with tempfile.TemporaryDirectory(prefix="rag-historical-reviews-") as directory:
        dest = Path(directory)
        policy = json.loads((ROOT / "config/validation-policy.json").read_bytes())
        ingest = Path("data/ingestion") / policy["input_run_id"]
        paths = [Path("config/validation-policy.json"), Path("uv.lock"),
                 Path("workspace/milestone2.5-review/reviews.json")]
        paths.extend(ingest / name for name in policy["artifact_sha256"])
        for source in json.loads((ROOT / ingest / "manifest.json").read_bytes()):
            paths.extend(Path(source[k]) for k in ("raw_path", "snapshot_path"))
        for rel in set(paths):
            assert not rel.is_absolute() and ".." not in rel.parts
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        # New process prevents archived modules contaminating current tests.
        code = '''
import importlib.util, sys
from pathlib import Path
archive, root, assertions = map(Path, sys.argv[1:])
sys.path.insert(0, str(archive / "src"))
from rag_hub.validation_sampling import validator_fingerprint
assert validator_fingerprint() == "c3509d64beca21a2d501d72ea5376a9612fc91ecb15900d923c66bb7525e8369"
spec = importlib.util.spec_from_file_location("historical_assertions", assertions)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ROOT = root
module.test_actual_1665_coverage_promotion_boundaries_and_preservation()
print("PASS: archived validator; original 195 reviews; 40/1634; deterministic disposable replay")
'''
        # Frozen original test body is retained, not rewritten or re-scored.
        assertions = Path(__file__).with_name("legacy_validation_assertions.py")
        assert sha(assertions) == "618dfa603fb18e83bb9ddf9ddd05e295e8f18d8f6668af6dedf53dba3afcf3c0"
        result = subprocess.run([sys.executable, "-c", code, str(ARCHIVE), str(dest),
                                 str(assertions)], text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        generated = list((dest / "data/validation").iterdir())
        assert len(generated) == 1
        original = ROOT / "data/validation" / generated[0].name
        assert original.is_dir(), "historical_replay_identity_differs"
        for p in generated[0].iterdir():
            assert p.read_bytes() == (original / p.name).read_bytes(), p.name
        return result.stdout
