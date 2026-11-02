"""Disposable immutable-source, publication, vector and native-index mutation controls."""

import json
import shutil
from pathlib import Path

import pytest

from tools.evidence.contract import load_configuration
from tools.indexing.m5_index import sha

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = "config/evidence-reconstruction-m8-v1.json"
SHA = sha((ROOT / SELECTOR).read_bytes())


@pytest.fixture(scope="module")
def copied(tmp_path_factory):
    _, _, files, _ = load_configuration(ROOT, SELECTOR, SHA)
    target = tmp_path_factory.mktemp("m8-source-binding-controls")
    for name in files:
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, p)
    return target, files


@pytest.mark.parametrize("kind", ["source_pdf", "qa_publication", "vectors", "chroma"])
def test_bound_payload_mutations_fail_closed(copied, kind):
    root, files = copied
    if kind == "source_pdf":
        name = next(p for p in files if p.endswith('.pdf'))
    elif kind == "vectors":
        name = next(p for p in files if p.endswith('vectors.npy'))
    elif kind == "chroma":
        name = next(p for p in files if p.endswith('chroma.sqlite3'))
    else:
        selected = json.loads((root / 'config/pdf-durable-admission-publication-v1.json').read_bytes())
        manifest = json.loads((root / selected['manifest_path']).read_bytes())
        name = manifest['publications'][0]['path']
    p = root / name
    original = p.read_bytes()
    try:
        p.write_bytes(original + b'CORRUPTED_DISPOSABLE_CONTROL')
        with pytest.raises(ValueError):
            load_configuration(root, SELECTOR, SHA)
    finally:
        p.write_bytes(original)
    load_configuration(root, SELECTOR, SHA)
