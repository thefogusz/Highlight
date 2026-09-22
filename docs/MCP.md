# MCP interface contract

Status: specified, not implemented. `contracts/tools.json` is a proposed tools/list payload. JSON Schema defaults describe server behavior; validators do not insert defaults, so runtime must resolve them explicitly.

## Agent-facing flow

1. On explicit Highlight intent + URL, call highlight_create with only url when details are absent. Do not ask for category/count/API key in chat. The server applies defaults and preflight.
2. Save job_id; use highlight_status after poll_after_seconds (default 15, back off to 60). Do not hold tools/call open for an entire video. No promise of a later notification unless the host supports it; user can return and request results.
3. Terminal completed/partial -> highlight_results. Show verified clips with source links, titles, paths, warnings and expirations. Empty output is possible. partial must not be described as complete success.
4. Optional follow-up -> highlight_revise with source-time start/end and expected_revision. This queues a separate operation job and returns job_id. Preserve previous revision; stale revision returns REVISION_CONFLICT.
5. Credentials missing -> explain one-time setup from SETUP.md, never ask user to paste a secret into tool/chat.

## Eight tools

| Tool | Input | Behavior |
|---|---|---|
| highlight_create | url required; intent/categories/count/durations/aspect/focus optional | Queue and automatically analyze+render. Return resolved_options and reused flag. |
| highlight_status | job_id | Read state/stage, progress if known, warnings, next_action and polling hint. |
| highlight_results | job_id, cursor, limit | Paginated verified clips. Ready subset available while running; include job_state. |
| highlight_revise | job_id, clip_id, expected_revision, start_seconds, end_seconds | New immutable revision; validate source retention, bounds and length before queueing. |
| highlight_cancel | job_id | Idempotent cancellation request; does not delete files or undo completed provider costs. |
| highlight_retry | job_id | Resume failed/partial/cancelled/interrupted/waiting work; completed jobs are immutable. Explicit retry of an uncertain provider attempt may be billed again. |
| highlight_settings | no arguments | Read-only sanitized readiness + source of key + model/config version. No secret-setting tool. |
| highlight_jobs | cursor, limit | Find previous jobs after a chat ends, newest first. |

Mutation annotations: readOnlyHint=false. Cancellation destructiveHint=true because it stops requested work; no file deletion implied. Create/revise/retry/cancel idempotentHint=true is an implementation obligation via fingerprints and state transitions, not a guarantee provided by MCP itself. Open-world tools flag potential provider/network interaction. Read tools do not run implicit preflight network tests.

## Resource and prompt design

Resources: `highlight://jobs/<job_id>/manifest`, `highlight://clips/<clip_id>/r<N>/thumbnail`, `highlight://clips/<clip_id>/r<N>/video`. Access checked against local user/session scope. Missing/expired artifact gives an explicit error.

Optional `clip_youtube` prompt accepts url + intent and asks the Agent to call highlight_create. It is convenience only; direct tool use is complete. A named plugin can improve discovery where supported, but no cross-host guarantee of @ mention. This package does not register a plugin or modify a host's settings.

## Request semantics

Canonical source validation occurs beyond JSON Schema: URL parser, exact host allowlist, a single valid video ID, no credentials/ports/playlists. focus_ranges are non-empty source-second intervals, sorted/merged after duration is known. start < end <= source duration. All times finite, half-open [start,end). max_duration_seconds >= min_duration_seconds. Requests beyond system bounds return LIMIT_EXCEEDED rather than silently dropping work.

request intent is optional bounded editorial text. It can refine category matching but cannot override server budgets, access rules or tool permissions. If it conflicts with structured fields, fields win and warnings explain the conflict. Default target_clips is a total across selected categories.

## Results and evidence

Tool success uses `structuredContent` matching outputSchema plus text JSON fallback of the same object. Keep text concise; use resource_link/image content for artifacts. Every success has schema_version=1.0, warnings, next_action. A standard error uses `isError=true` and structuredContent with ok=false and error={code,message,retryable,action}; no stack trace/provider body/secret returned. Unknown tools or protocol syntax errors use MCP JSON-RPC errors; ordinary business failures use tool errors.

retryable means an automatic retry may be appropriate without changing inputs/configuration. CONFIG_REQUIRED has retryable=false until the user changes settings. highlight_retry is an explicit recovery action, not permission for infinite automatic retries. For partial jobs retry only failed clips; preserve verified outputs. For cancelled jobs an explicit retry revokes the cancellation and resumes safe checkpoints.

Clip metadata: absolute source times, revision, categories, reason_th, evidence list, nullable normalized replay score, AI confidence label (not calibrated probability), verified status, artifacts. excerpt-relative model times are never exposed as original-source times until converted. A source link with timestamp points back to original YouTube video, not the output clip.

## Error behavior

| Code | Action |
|---|---|
| CONFIG_REQUIRED | Set GEMINI_API_KEY via host environment or local settings wizard, then retry. |
| MODEL_UNAVAILABLE | Choose a validated video/audio-capable model in settings; do not silently swap. |
| INVALID_SOURCE / INVALID_RANGE | Correct source/range; no charged work starts. |
| SOURCE_UNAVAILABLE | Tell user download/access failed; do not bypass restrictions. |
| HEATMAP_UNAVAILABLE | Only fatal for require; prefer returns warning and continues. |
| LIMIT_EXCEEDED / BUDGET_EXCEEDED | Explain configured limit; no automatic limit increase. |
| PROVIDER_RATE_LIMIT | Bounded backoff honoring retry-after; then resumable failure. |
| PROVIDER_OUTCOME_UNKNOWN | Stop chargeable retry; explain possible duplicate charge on explicit retry. |
| MODEL_OUTPUT_INVALID | Reject invalid evidence/range; bounded repair within budget, never fabricate. |
| IDEMPOTENCY_CONFLICT / REVISION_CONFLICT | Re-read current request/revision; do not overwrite. |
| SOURCE_EXPIRED / ARTIFACT_EXPIRED | Explain retention; a new explicitly requested job can fetch again. |
| DISK_FULL / RENDER_FAILED | Preserve checkpoints/ready outputs, fix local issue then retry. |

## Example interaction (synthetic)

See [examples/calls.json](../examples/calls.json). All times, scores and clip names there are invented fixtures; no real video has been analyzed. Tools required to execute that interaction are not yet implemented.
