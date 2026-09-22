# Verification and release acceptance

## Current offline design check

`scripts/check_design.py` validates JSON Schema definitions, positive and negative call fixtures, output contracts, cross-field timing rules, job state model, configuration syntax, local Markdown links and no key input fields. It is a design consistency check, not a live MCP test. External links/provider availability require separate live checks.

## Required runtime checks (not run)

| ID | Scenario | Pass condition |
|---|---|---|
| R01 | URL-only create through real MCP SDK client | defaults resolved, job_id returned promptly, no video processing blocks handshake |
| R02 | missing/invalid key | CONFIG_REQUIRED/provider error, no secret in logs/response; reads still usable |
| R03 | duplicate parallel create | same normalized request -> one active job/render; conflicting idempotency key rejected |
| R04 | no heatmap | prefer continues with explicit warning; require fails; unknown never becomes zero |
| R05 | transcript-only/quiet joke | non-heatmap discovery exercised; visual/audio coverage shown |
| R06 | malformed/out-of-bounds provider time | reject; never call FFmpeg with invalid time or model-generated command |
| R07 | kill worker during render/chargeable call | lease recovery and atomic outputs; uncertain external charge not silently retried |
| R08 | cancel and retry | subprocess tree stops, no further provider calls; safe checkpoints retained |
| R09 | partial render failure | only verified clips ready, job partial, failed artifact excluded |
| R10 | source expired or stale revision | explicit SOURCE_EXPIRED / REVISION_CONFLICT; original unchanged |
| R11 | prompt injection in captions/frame text | no new tool authority, downloads, secret access or publishing |
| R12 | URL tricks/path traversal/NaN/oversized media | fail at boundary before side effect |
| R13 | budget/rate limit/disk full | bounded work; actionable error; usage includes known and unknown attempts |
| R14 | closed Agent session | job persists; reopen highlight_jobs/results; no promise of unsolicited notification |
| R15 | local key wizard | masked entry, OS keyring, Origin/CSRF checks, no key in config/logs/browser storage |
| R16 | actual host UX | discover tools without @ dependency, paste URL, wait/read results, play output, revise |
| R17 | output timing | synthetic marked fixture cut differs <= 1 output frame; A/V sync within defined fixture tolerance |

Runtime smoke target: local create returns within 2 seconds after queue write under idle fixture conditions; cold model load happens in worker, not MCP. Timing is a target, not a measured claim.

## Thai editorial evaluation

Use 3 authorized episodes: clear turn-taking, overlapping heated conversation, quiet/dry humor. Owner marks important/funny events before seeing AI output; include 20–30 positive and negative candidate excerpts. Store episode ID, source hash, reference ranges/category and reason. Two Thai reviewers where possible; record disagreement rather than forcing a universal humor label.

Compare same sources, inspection budgets and output counts across configurations. Do not select only the best demo. Measure accepted clips/returned clips, recalled marked events, context completeness, wrong attribution, duplicate-event rate, boundary adjustments, elapsed time, provider usage and cost per accepted clip. Overlap matching threshold and one-to-one event matching must be fixed before evaluation; initial temporal IoU >= 0.3 plus reviewer semantic match, report both.

Proposed release targets to validate with owner: >=70% returned clips accepted; >=70% marked events recalled for requested categories; >=90% context-complete; zero fabricated quotes and zero critical meaning-changing cuts in the evaluation sample. These are release targets, not model performance claims. Any critical failure blocks automatic production use until corrected and retested.

## Media evidence

For each real run save source fingerprint, pipeline/model/prompt versions, request options, inspected ranges, provider usage, source/output timestamps, ffprobe JSON, decoding result and editorial decisions. Clip verification must include playback of representative outputs; duration metadata alone is not visual verification. Keep a report of failed/skipped clips.

No API key or actual episode was supplied for this design task, so no live video analysis, download, billing or Thai accuracy measurement is claimed.
