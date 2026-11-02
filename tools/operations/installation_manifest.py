"""Inspect five existing locked environments; never install, sync, or relocate them."""

import importlib.metadata
import importlib.util
import json
import platform
import re
import sys
from pathlib import Path

from check_selection import bound, command


def normalize(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def inspect_runtime(root, project):
    # Reuse the accepted environment/source-origin validator in its actual interpreter.
    sys.path.insert(0, str(root / "tools/regression"))
    from probe_environment import verify

    if project == "tools/indexing":
        # The fifth environment deliberately has no editable rag_hub dependency.
        # It stores numbers/metadata only and cannot authorize source evidence.
        if (Path(sys.prefix).resolve() != (root / project / ".venv").resolve()
                or importlib.util.find_spec("rag_hub") is not None):
            raise ValueError("indexing_environment_isolation_changed")
        details = {"status": "PASS", "project": project, "prefix": sys.prefix,
                   "source_origin": "NOT_INSTALLED_BY_DESIGN_NUMERICAL_STORE_ONLY"}
    else:
        details = verify(root, project)
    details.update(python_exact=platform.python_version(), machine=platform.machine(),
                   system=platform.system(),
                   base_executable=str(Path(sys.executable).resolve()),
                   distributions={normalize(d.metadata["Name"]): d.version
                                  for d in importlib.metadata.distributions()})
    return details


def validate_runtime(details, project, profile):
    if (details["python_exact"] != profile["python"]
            or details["system"] != profile["platform"]["system"]
            or details["machine"] != profile["platform"]["machine"]):
        raise ValueError("incompatible_python_or_platform:" + project["project"])
    if details["distributions"] != project["distributions"]:
        raise ValueError("installed_runtime_differs_from_accepted_inventory:" + project["project"])


def verify_installation(root, profile):
    if command(root, ["uv", "--version"]).split()[1] != profile["uv"]:
        raise ValueError("incompatible_uv_version")
    reports = []
    for project in profile["projects"]:
        base = Path(project["project"])
        bound(root, str(base / "uv.lock"), project["lock_sha256"])
        bound(root, str(base / "pyproject.toml"), project["manifest_sha256"])
        interpreter = root / base / ".venv/bin/python"
        if not interpreter.is_file():
            raise ValueError("missing_locked_interpreter:" + str(base))
        # Inspect, do not call uv run (which may sync an environment).
        details = json.loads(command(root, [str(interpreter),
            "tools/operations/installation_manifest.py", "--root", str(root),
            "--project", project["project"]]))
        validate_runtime(details, project, profile)
        command(root, ["uv", "lock", "--check", "--offline", "--project", str(base)])
        reports.append(details)
    return {"status": "PASS_EXISTING_INSTALLATION_ONLY", "projects": reports,
            "clean_offline_reconstruction_verified": False}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    print(json.dumps(inspect_runtime(args.root.resolve(), args.project), sort_keys=True))
