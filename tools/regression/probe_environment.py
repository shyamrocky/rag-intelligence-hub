"""Inspect the actual locked interpreter and editable source origin without model inference."""

import argparse
import importlib.metadata
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path


def verify(root, project):
    root = Path(root).resolve()
    project = root / project
    expected = project / '.venv'
    if Path(sys.prefix).resolve() != expected.resolve() or sys.version_info[:2] != (3, 12):
        raise ValueError('wrong_python_environment')
    spec = importlib.util.find_spec('rag_hub')
    if not spec or Path(spec.origin).resolve() != root / 'src/rag_hub/__init__.py':
        raise ValueError('wrong_editable_source_origin')
    definition = tomllib.loads((project / 'pyproject.toml').read_text())
    locked = tomllib.loads((project / 'uv.lock').read_text())
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    versions = {}
    for package in locked['package']:
        versions.setdefault(normalize(package['name']), set()).add(package['version'])
    requirements = definition['project'].get('dependencies', []) + definition.get(
        'dependency-groups', {}).get('dev', [])
    names = {normalize(re.split(r'[<=>!~;\[ @]', req)[0]) for req in requirements
             if isinstance(req, str)}
    if definition.get('tool', {}).get('uv', {}).get('package', True):
        names.add(normalize(definition['project']['name']))
    checked = {}
    for name in sorted(names):
        actual = importlib.metadata.version(name)
        if actual not in versions.get(name, set()):
            raise ValueError('installed_dependency_not_locked:' + name)
        checked[name] = actual
    return {'status': 'PASS', 'project': str(project.relative_to(root)),
            'prefix': sys.prefix, 'python': sys.version, 'source_origin': spec.origin,
            'installed_direct_dependencies': checked, 'model_inference': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.project), indent=2))


if __name__ == '__main__':
    main()
