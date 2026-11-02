"""Explicit local operational preflight; inspection only, never an admission authority."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PROFILE = "config/operations-durable-m0-m5-v1.json"
PROFILE_SHA256 = "c9c28c7d5b35b965c7044d3817e3063b1fe4b0d8705fcb73344527e1d004e4a4"


def bound(root, name, digest):
    path = root / name
    if (not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts
            or not path.resolve().is_relative_to(root.resolve())
            or any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root))):
        raise ValueError("unsafe_operational_path:" + str(name))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("missing_or_unreadable_component:" + name) from exc
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("component_hash_mismatch:" + name)
    return raw


def load_profile(root, path, digest):
    if path != PROFILE or digest != PROFILE_SHA256:
        raise ValueError("unsupported_operational_profile_no_fallback")
    return json.loads(bound(root, path, digest))


def check_bindings(root, profile):
    """Check configured witnesses; native readers still validate semantics/authorization."""
    selections = {}
    files = {}
    for name, digest in profile["selection"].items():
        files[name] = digest
        value = json.loads(bound(root, name, digest))
        selections[name] = value
        for path_key, hash_key in (("manifest_path", "manifest_sha256"),
                                   ("descriptor_path", "descriptor_sha256"),
                                   ("build_path", "build_sha256")):
            if path_key in value:
                actual_key = ("expected_manifest_sha256" if name ==
                              "config/pdf-durable-admission-publication-v1.json"
                              and path_key == "manifest_path" else hash_key)
                files[value[path_key]] = value[actual_key]
        if name == "config/pdf-durable-admission-publication-v1.json":
            files[value["release_path"]] = value["expected_release_sha256"]
    files.update(profile["verification_components"])
    for project in profile["projects"]:
        base = Path(project["project"])
        files[str(base / "pyproject.toml")] = project["manifest_sha256"]
        files[str(base / "uv.lock")] = project["lock_sha256"]
    m5 = selections["config/vector-index-m5-v1-1.json"]
    manifest = json.loads(bound(root, m5["manifest_path"], m5["manifest_sha256"]))
    # The accepted manifest binds the payload; verify it before using its dependency map.
    payload = json.loads(bound(root, manifest["payload_path"],
                               manifest["spec"]["payload_sha256"]))
    files.update(payload["bindings"])
    files.update(manifest["spec"]["components"])
    if any(p.startswith("workspace/") for p in files):
        raise ValueError("workspace_dependency_forbidden")
    for name, digest in files.items():
        bound(root, name, digest)
    return {"status": "PASS_BINDINGS_ONLY_NOT_AUTHORIZATION", "files": len(files),
            "workspace_dependencies": 0}


def environment():
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "RAG_TEST_QA_RELEASE",
                "PYTEST_PLUGINS"):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               ANONYMIZED_TELEMETRY="false", OTEL_SDK_DISABLED="true", UV_OFFLINE="1")
    return env


def command(root, args, *, timeout=240):
    result = subprocess.run(args, cwd=root, env=environment(), capture_output=True,
                            text=True, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError("operational_check_failed:" + str(args[-1]) + ":" +
                         (result.stdout + result.stderr)[-2500:])
    return result.stdout


def native_checks(root, profile):
    """Fixed native APIs; no profile-provided executable/import, inference, or writes."""
    result = {}
    command(root, [str(root / ".venv/bin/python"), "-c",
                   ("from pathlib import Path; "
                    "from tools.ingestion.run import load_selection, WORKER_SHA; "
                    "from tools.operations.check_selection import bound; "
                    "load_selection(Path.cwd(), 'config/ingestion-strict-v1.json'); "
                    "bound(Path.cwd(), 'tools/ingestion/strict_worker.py', WORKER_SHA)")])
    result["strict_selection"] = "PASS_NO_INGESTION_EXECUTED"
    output = command(root, [str(root / "tools/embeddings/.venv/bin/python"),
                           "tools/hardening/verify_successor.py", "--root", str(root),
                           "--depth", "sample"])
    result["durable"] = json.loads(output.splitlines()[-1])
    selector = "config/vector-index-m5-v1-1.json"
    output = command(root, [str(root / "tools/indexing/.venv/bin/python"),
                           "tools/indexing/m5_index.py", "inspect", "--root", str(root),
                           "--selector", selector, "--selector-sha256",
                           profile["selection"][selector]])
    result["m5"] = json.loads(output)
    if (result["durable"]["status"] != "PASS" or result["m5"]["status"] != "PASS"
            or result["m5"]["records"] != profile["expected"]["indexed_records"]):
        raise ValueError("native_operational_verification_failed")
    return result


def run(root, path, digest):
    from installation_manifest import verify_installation

    root = root.resolve(strict=True)
    profile = load_profile(root, path, digest)
    bindings = check_bindings(root, profile)
    installation = verify_installation(root, profile)
    native = native_checks(root, profile)
    # No success if witnesses changed while the more expensive native checks ran.
    check_bindings(root, profile)
    return {"status": "PASS_OPERATIONAL_PREFLIGHT", "authority": "INSPECTION_ONLY",
            "profile": path, "profile_sha256": digest, "bindings": bindings,
            "installation": installation, "native": native,
            "limitations": ["Not a QA decision, durable authorization lease or M6 approval",
                            "Clean-root recovery and other-platform inference unqualified",
                            "Historical APIs unchanged; use only explicitly selected forward paths"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.root, args.profile, args.profile_sha256), sort_keys=True))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "fallback": False}))
        sys.exit(1)


if __name__ == "__main__":
    main()
