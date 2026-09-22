# Design review — 2026-09-22

Scope: design package only. Review covers correctness, clarity, architecture, credential handling, resource bounds and implementability. No independent reviewer or live video evaluation is claimed.

## Findings resolved in the design

- @ discovery is host-specific; direct tools remain usable. Templates are labeled non-runnable until runtime exists.
- A stdio connection alone cannot own durable work; separate hidden worker + SQLite leases/checkpoints specified.
- Missing heatmap is unknown; fallback and require-mode failure explicitly differ.
- API timeouts can have uncertain billing; no claim of exactly-once provider charges or blind retries.
- Secrets configured outside model-visible tools; sanitized settings, environment precedence and worker restart defined.
- Per-category labels do not multiply target count; category quota behavior explicit.
- Revisions retain source-time coordinates and previous output; source expiration/stale version are errors.
- Rendering success requires media verification; partial/empty/failure outcomes have distinct semantics.
- Whole OpenShorts fork is not required; reuse awaits pinned-code/license audit. No third-party code copied.

## Offline checks

See `scripts/check_design.py` and the repository verification command. The checker verifies schema and example consistency, negative request fixtures, a temporal acceptance oracle, state transitions, configuration syntax and local links. The oracle specifies required runtime behavior; it does not prove a runtime implements it.

Observed on 2026-09-22: Python 3.11, jsonschema 4.26.0; `python scripts/check_design.py` passed **105 checks**. Added a required video artifact to the output schema, source URL/duration to results, and clarified explicit retry after partial/cancelled jobs during review. Dependency versions used for this check are pinned in requirements-design.txt. `git diff --cached --check` passed before the final commit.

## Open release gates

All runtime milestones in IMPLEMENTATION.md remain pending. Need an actual Gemini key/model-access check, real source episode, installed media dependencies, actual MCP host handshake, generated playable clips and Thai editorial evaluation before describing this system as usable. No cost, speed or humor-accuracy result is claimed.

Verdict: design is ready to guide implementation after offline validation. This verdict does not approve a runtime release.
