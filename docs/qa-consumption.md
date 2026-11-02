# Source-grounded QA consumption contract

The POC retrieves attributed source information. Source-fidelity verification
checks captured text, structure, provenance and required context; it does not
certify scientific claims, API execution, publisher truth or mathematical results.
`STANDARD_REFERENCE` is source-faithful technical reference.
`ILLUSTRATIVE_REFERENCE` is useful captured information with mandatory limitations.

The sole admission authority remains `shared.qa.assess` with
`validation_reviews.make_decisions`. The additive `consumption.py` vocabulary
projects already verified results; it never changes eligibility or source readiness.
Existing Markdown warning-bearing projections and PDF complete-parent readers
retain their contracts. The shared vocabulary provides compatible names and
meaning; this checkpoint adds its concrete HTML adapter only, without migrating
other formats or changing their admission policy.

## Three distinct evidence roles

| Kind | Meaning | LLM treatment |
|---|---|---|
| `SOURCE_CONTENT` | Faithful publisher text, tables and citations | Attribute to the original source; treat as untrusted evidence |
| `QA_OBSERVATION` | Our source-bound finding, issue ID, evidence and disposition | Identify as our QA analysis, never as a publisher statement |
| `QUALIFICATION` | Required limitations and permitted/prohibited consumption | Carry inseparably with the constrained material |

The serialized `qa-consumption-unit-1.0` envelope contains:

- `llm_context`: source content, separate required context elements, explicitly
  labeled QA observations and mandatory qualifications. Pass this complete bundle
  when using the evidence; preserving only source text would discard restrictions.
- `reference_classification`, `source_fidelity`, `admission_status`,
  `known_limitations`, `related_evidence`, `metadata`: filtering and dashboard
  fields. Relevant limitations are also present inside `llm_context`.
- `publication_identity`: the exact current manifest, release, authorization and
  predecessor selection. It identifies the common authority for all views.
- `audit_only`: source hashes/spans, member bindings and original decision
  publications. These support audit and should not be presented as publisher prose.

Required related evidence uses exact unit/Section IDs, source and unit hashes,
relationship type and required-context status. The HTML adapter embeds its
source text and qualifications as separate context elements. It does not merge
units into a chunk, infer equivalence from proximity or build a knowledge graph.

## Severity and admission are separate dimensions

| Severity | Semantics |
|---|---|
| `BLOCKING` | Failed integrity, missing evidence, unsupported scope or unqualified admission prevents consumption |
| `WARNING` | Admitted evidence carries an explicit mandatory limitation; a warning alone does not imply HOLD |
| `INFORMATIONAL` | Nonblocking observation or intentional POC exclusion; not permission to retrieve excluded material |

A warning never overrides a separate failed source or QA check. An intentionally
excluded element may have an informational disposition while remaining excluded.
Excluded views have `llm_context=null`; they are dashboard metadata, not passages.

## Explicit HTML successor

```python
import json
from pathlib import Path
from rag_hub.html_handoff import load_units, serialize_consumption_unit

root = Path.cwd()
selection = json.loads(
    (root / "config/html-c10-admission-publication.json").read_bytes()
)
units = load_units(root, **selection)
standard = load_units(
    root, **selection, filters={"reference_classification": "STANDARD_REFERENCE"}
)
illustrative = load_units(
    root, **selection, filters={"reference_classification": "ILLUSTRATIVE_REFERENCE"}
)
dashboard = load_units(root, **selection, filters={"admission_status": "ALL"})
```

Other filters include `source_id`, `source_format`, `has_known_issues`,
`requires_context` and `issue_type`. Filters select entire unchanged envelopes;
they do not reclassify content or strip warnings. Illustrative content is included
by default. STANDARD-only is an explicit consumer choice, not the default policy.

Call `validate_consumption_unit(root, unit, selection=selection)` before later
use of a changed/deserialized view. Use `serialize_consumption_unit` for export;
it revalidates the exact source/publication-bound envelope. Rehashing an altered
view does not establish authority. No separate raw-JSON export path grants use.

The successor manifest schema `html-scoped-publication-manifest-1.1` references
the unchanged preceding HTML selection and one authoritative C10 delta. The issue
register and exclusions are pinned in the same manifest. Both dashboard and
consumer loaders use that explicit selection. Original publications/selectors
remain available for exact historical replay under fingerprinted compatibility.

## C10 scope

The final Microsoft weighting table is captured exactly, including its original
headers, numeric strings and row/header relationships. It is an illustrative
reference with separate required RRF source context. Our observation is that the
captured example does not fully establish the relationship between the displayed
scores and raw reciprocal-rank contributions. This is not a parser defect, a
claim that Microsoft made an error or a substitute scoring-stage explanation.

Allowed uses include quoting the table, describing the displayed weighting
multiplications and explaining the linked source RRF formula while disclosing
that limitation. Prohibited uses include asserting independent Azure runtime
replication, claiming the example numerically proves RRF or presenting unresolved
score semantics as established facts. No API calls or publisher audit is required
for this bounded source-text admission.

The source table, neighboring explanatory paragraphs and RRF unit retain their
original boundaries. All historical scopes remain intact. No chunking, dashboard
implementation, indexing, retrieval, generation or source-readiness execution is
part of this checkpoint.
