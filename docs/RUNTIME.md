# Local alpha 0.1

## Implemented

- Eight schema-validated MCP tools over stdio with structured results and sanitized errors.
- SQLite durable jobs, request deduplication, detached single worker, cooperative cancellation, interrupted-job detection and explicit retries.
- Strict public HTTPS YouTube URL input. yt-dlp metadata/download, optional unofficial replay heatmap, no YouTube API key.
- Local faster-whisper small, CPU/int8, Thai transcription. Weights download automatically on the first real job.
- Transcript discovery over overlapping 10-minute windows; heatmap peaks join candidates. Global text ranking when the pool exceeds the requested count. Candidate audio/video uploaded to the configured Gemini model for inspection.
- FFmpeg H.264/AAC MP4 rendering, source aspect fitted into landscape or portrait with padding, optional sidecar SRT, decode and duration verification.
- Local masked key form with Windows Credential Manager. Environment key overrides keyring. Model listing checks access; it does not certify video compatibility. No key-setting MCP tool.
- Revisions render from retained original media without a new provider call. Expanded context is not reanalyzed; evidence explicitly says this.
- Artifact URIs resolve to metadata through resources/read; MP4 bytes remain at absolute local paths. Host preview/playback is host-dependent.

## Limits and explicit gaps

This is an installable alpha, not completion of every requirement in SPEC/ARCHITECTURE/ACCEPTANCE.

- No real Gemini/YouTube end-to-end run or Thai editorial evaluation has been performed without a user key. A working server and synthetic media tests do not establish humor accuracy.
- Key status remains `unknown` in MCP until a future persisted provider-validation feature; model-list UI success is transient. No default model is invented.
- Transcript-first discovery can miss silent visual jokes. Not every second of video is inspected. Candidates rejected during inspection are not automatically backfilled; fewer clips produce `partial`.
- Heatmap depends on YouTube/yt-dlp availability, is normalized within the video and is not a viewer count. Resolution follows returned bins. Missing heatmap yields null scores.
- Two-hour source cap, yt-dlp 5 GB per-file download cap, 8 GB job folder cap checked periodically, 2 GB free-space guard, 30 generated-content calls per job. These are resource bounds, **not a currency spending cap**. File upload/processing and model usage may cost money. Exact billing estimation/token ledger is not implemented.
- Provider automatic generation retries are disabled. Explicit retry may repeat a charged request whose outcome was unknown. JSON checkpoints reuse completed stages. Budget exhaustion requires a new implementation/configuration decision; blind retries do not reset the call counter.
- Retention cleanup is not automatic. `expires_at` is an advisory 30-day retention date; files persist until manually removed. Delete completed job folders only when no longer needed. Jobs database stores local paths.
- A worker interruption requires explicit retry. Cancellation waits for an in-flight synchronous provider/ASR operation to yield; it cannot retract an already billed request.
- No authenticated gallery, thumbnails, smart face tracking, burned-in captions, GPU setup, hosted multi-user mode or auto-updater.
- YouTube extraction may require a supported JavaScript runtime or encounter platform access restrictions. The server does not automatically use browser cookies or account credentials; such failures need separate diagnosis.
- MCP does not guarantee an @ mention. Agent should call create once, poll at the suggested interval, and return existing paths. Do not repeatedly create/retry failed jobs automatically.

## Verification performed

28 tests pass: input validation, secret non-echo, deduplication, schema outputs, MCP subprocess handshake/list/calls, real synthetic FFmpeg render/decode, real worker revision without a provider, crash state, and fake-provider discovery/inspection with real media and SRT output. 108 design-contract/link checks pass separately.

Not verified: live YouTube extraction, real Gemini video responses, Whisper accuracy on Thai talk shows, Codex inline video UI, human judgment of highlights.

## Local operations

`python -m highlight_mcp serve` runs MCP stdio. Keep stdout reserved for protocol messages.

`python -m highlight_mcp setup` opens the local key/model form.

`python -m highlight_mcp doctor` prints only sanitized readiness.

Default data directory: `%LOCALAPPDATA%\Highlight`; override with `HIGHLIGHT_DATA_DIR`. Nonsecret settings live in `settings.json`. API credentials are read from `GEMINI_API_KEY` or OS keyring service `Highlight`, account `gemini`. They are never written into repository or job payloads.

Windows installer dependencies: Python 3.11, FFmpeg + ffprobe; package dependencies pinned in pyproject.toml. Install the checkout into its own venv. When relocating an installation, recreate the venv instead of moving it.
