"""Build an immutable opt-in assembly configuration, never an admission publication."""

import json
from pathlib import Path

from tools.evidence.contract import COMPONENTS, M7_SELECTOR, M7_SHA, POLICY
from tools.indexing.m5_index import encoded, local, sha
from tools.retrieval.contract import load_release

SELECTOR = "config/evidence-reconstruction-m8-v1.json"


def build(root):
    root = Path(root).resolve(strict=True)
    m7, _, _ = load_release(root, M7_SELECTOR, M7_SHA)
    spec = {"authority": "ASSEMBLY_ONLY_NOT_ADMISSION", "budget_policy": POLICY,
        "m7": {"path": M7_SELECTOR, "sha256": M7_SHA},
        "m7_manifest_sha256": sha(encoded(m7)),
        "components": {p: sha(local(root, p).read_bytes()) for p in COMPONENTS}}
    identity = sha(encoded(spec))
    manifest = {"schema": "m8-composition-1.0", "identity": identity, "spec": spec}
    path = "data/evidence/m8-v1/" + identity + "/manifest.json"
    target = local(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != encoded(manifest):
        raise ValueError("m8_immutable_manifest_conflict")
    if not target.exists():
        target.write_bytes(encoded(manifest))
    selection = {"schema": "m8-selection-1.0", "manifest_path": path,
                 "manifest_sha256": sha(encoded(manifest))}
    local(root, SELECTOR).write_bytes(encoded(selection))
    return {"selector": SELECTOR, "selector_sha256": sha(encoded(selection)),
            "identity": identity, **selection}


if __name__ == "__main__":
    print(json.dumps(build(Path.cwd()), sort_keys=True))
