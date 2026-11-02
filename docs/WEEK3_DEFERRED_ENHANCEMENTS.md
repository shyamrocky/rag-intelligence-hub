# Week 3 enhancement candidates

Recorded October 29, 2026, at the project owner's request during R03 review.
**Deferred candidates only. No implementation or pipeline change is authorized.**
The Week 2 priority remains completing the controlled evaluation baseline.

| ID | Candidate | R03 motivation | Future evaluation question |
|---|---|---|---|
| W3-E01 | Contextual BM25 versus hybrid-retrieval terminology | Reviewers disagree on the materiality of conflating a context-enriched lexical technique with a vector/keyword combination. | Can answer wording distinguish the techniques using the evidence actually supplied and cited? |
| W3-E02 | Clearer semantic-embedding explanation | Claude requested an explicit explanation of nearby representations for similar meanings; Gemini and ChatGPT judged the core answer sufficient. | Does a brief conceptual explanation improve learning without adding unsupported claims? |
| W3-E03 | Separate completeness from source grounding | Owner accepts R03 as ANSWERED for semantic completeness while source-bound extra assertions remain unresolved. | Can the presentation show accepted coverage and unresolved grounding independently without implying overall validation? |
| W3-E04 | Capture evaluator disagreement | Three general-knowledge model assessments differ on completeness and terminology severity. | How should verdicts, rationales, evidence access and owner disposition be compared without treating voting as truth? |
| W3-E05 | Improve user-facing answer presentation | Claude viewed the attribution disclaimer as evaluation metadata; other reviewers did not identify it as a completeness blocker. | Can the answer become more readable while retaining applicable mandatory disclosures and source obligations? |

The three evaluator observations were supplied by the owner. They are not new
provider measurements or independent verification of the original source grounding.
Their full rationales and disagreements are preserved in the
[R03 owner-review packet](../data/evals/generation-runner-reviews/r03-owner-completeness-v1/EVALUATOR_OBSERVATIONS.json).

No prompt, response schema, source-use rule, evaluator, dependency, agent or
retrieval algorithm changes are adopted here. Each candidate needs separate scope
and owner authorization before implementation. The existing canonical Post-M11
technical-debt register and its historical eight findings remain unchanged; these
are additional owner-requested enhancement candidates, not reclassified old findings.
