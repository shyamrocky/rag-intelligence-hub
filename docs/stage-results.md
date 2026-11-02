# Ingestion stage-result contract

Approved direction: D018. Phase 1A exercises a private, versioned reporting envelope, reusing existing immutable evidence and source-manifest models. This is an experimental contract for review, not a production schema migration or dashboard implementation.

An execution record contains an attempt ID, workstream/checkpoint and contract versions, exact input and implementation fingerprints, UTC start/end times, and one record for each source/stage pair. Stage order is acquisition, parsing, normalization, quality_assurance, ingestion_readiness_gate. Each record names its sole publisher, contributing components, source manifest or explicit missing-identity issue, artifacts with hashes, checks, issues and provenance. Outcomes are success, failure, partial, blocked or not_executed. A completed program can publish partial QA; program execution success is not source quality success.

Checks retain independent fidelity and structure dimensions. Required pending/failed evidence prevents stage success. Duplicate publishers are rejected. Successful downstream stages require successful upstream stages in a full execution. In this isolated checkpoint, upstream stages and the gate are explicitly not_executed, with references to historical inputs; QA publishes only a partial checkpoint assessment. The gate publishes no readiness decision here, and no module publishes new content eligibility.

Issues identify a stable code, severity, evidence dimension, source/unit/block spans, explanation and supporting artifact references. Original text, offsets and hashes remain immutable; whitespace and terminal punctuation are not silently discarded. An unaccounted interval is unresolved evidence, not permission to repair it. Completeness of claimed spans does not establish source fidelity, paragraph correctness or whole-document coverage.

The future dashboard renders authoritative records and links their evidence. It must show failed/blocked/not-executed records and unknown metrics, distinguish historical from current outcomes, and never compute stage statuses, readiness or content eligibility. Readiness and eligibility continue to have distinct owners under D018.

## Phase 1B experimental reporting

Phase 1B reuses the same immutable StageResult, Check, Issue and source-manifest models. Its version1.1 execution envelope records one experimental parsing owner and one QA owner per source/attempt; both publish partial outcomes while required fidelity/independent evidence remains pending or structural targets fail. Acquisition, production normalization and the readiness gate are explicitly not executed. Reversible display transformations are inspectable proposal evidence, not a production normalization run. No eligibility/readiness decision is made. The Phase1A-only execution wrapper and all historical records remain unchanged. This private experiment is not a production orchestration or dashboard integration.

## EXT-01 experimental reporting

The isolated EXT-01 candidate reuses Check, Issue and the stage-row safety rules. Its source field admits legacy0.1 and explicitly versioned0.2 manifests. The typed `stage-result-experimental-2.0` execution envelope lifts the Phase1A-only restriction, retaining per-source/attempt uniqueness, stage order, timestamps and upstream-success invariants. The old1.0 wrapper,1.1 dictionary envelopes and their original rows remain unchanged/readable; none is retroactively upgraded.

One owner per stage publishes the same five-stage sequence. Local synthetic demonstrations record acquisition verification, parsing and mechanical normalization as successful; QA is partial while qualification is pending; the readiness gate is not executed. Mechanical failures publish failure/blocked evidence with immutable run/attempt artifacts. Required pending or missing fidelity checks cannot produce QA success. Program completion can coexist with QA failure; consumers must read stage outcomes.

Artifacts bind actual source/component/configuration/lock hashes. A deterministic processing identity is separate from unique attempt IDs, timings and process resource diagnostics. A latest-processing pointer is only an artifact navigation aid, never an eligibility/readiness declaration. The dashboard remains unimplemented and must consume these authoritative records without recomputing their decisions. Full arbitrary historical artifact-reader dispatch and safe UI drill-down remain a later approved implementation.
