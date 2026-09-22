# Implementation plan

Design complete does not mean implementation complete. All runtime milestones below remain pending. No model training or whole OpenShorts fork is required to begin.

## Proposed project structure

```text
src/highlight_mcp/
  server.py          # SDK adapter; tools/resources, no long processing
  contracts.py       # typed validation matching contracts/tools.json
  settings.py        # keyring/environment + sanitized readiness
  jobs.py            # SQLite states, fingerprints, leases, events
  worker.py          # background stage runner, checkpoint recovery
  pipeline/
    intake.py        # yt-dlp, heatmap normalization, source validation
    transcribe.py    # ASR interface + faster-whisper
    discover.py      # heatmap/transcript/signal candidate union
    inspect.py       # provider proposals + timestamp grounding
    render.py        # FFmpeg and ffprobe, immutable revisions
  providers/gemini.py
  gallery.py         # local review + settings, optional to Agent workflow
tests/               # unit + integration
tests/e2e/           # real media and SDK client handshake
```

Use Python 3.11+; official MCP SDK; Google Gen AI SDK; yt-dlp; faster-whisper; FFmpeg/ffprobe as external binaries; SQLite from stdlib. Pin tested versions in a lockfile during implementation. Named dependencies are proposed, not installed by this design package. No Redis/Postgres/cloud storage requirement for one local worker.

## Milestones

| Step | Deliverable | Exit check |
|---|---|---|
| 1 | Typed contracts, local MCP server, mock worker, settings readiness | Official SDK client initialize/list/call; stdout only protocol; missing key redacted |
| 2 | Durable SQLite jobs and worker lifecycle | Duplicate submission, cancel, restart, lease contention tests; no double renders |
| 3 | Source intake, heatmap, ASR | Fixture and one authorized real source; actual bin widths; missing graph fallback |
| 4 | Candidate union and Gemini inspection | Bounded provider calls, invalid JSON/time rejection, Thai evidence reviewed |
| 5 | Rendering and artifacts | Synthetic and real clips decode; source boundaries/audio/SRT verified |
| 6 | Revisions, job history, settings wizard, review gallery | Source-expired handling, stale revision conflict, no secrets in responses |
| 7 | Agent UX and packaging | Actual host link-only request -> MP4; documented install/config; release evaluation |

Each step should be a reviewable commit/PR. Update acceptance results per step. Implement contract tests before logic; use media fixtures rather than mocking FFmpeg in all tests. Budget controls need failure tests, not just happy-path demos.

## Proposed runtime CLI (not available yet)

```text
python -m highlight_mcp setup        # local masked-key wizard
python -m highlight_mcp doctor       # offline readiness by default
python -m highlight_mcp doctor --provider-test
python -m highlight_mcp serve        # stdio adapter; ensure local worker
python -m highlight_mcp worker       # process supervisor entry point
```

Future runtime test commands: `python -m pytest tests/`; `python -m pytest tests/e2e/ -m real_media`. They must not be represented as executable commands for this design-only repository. Current verification command is in README.

## Reuse decision

OpenShorts is a reference and possible source for bounded MIT-licensed components, not a mandatory platform dependency. Its broad product includes many unrelated features. Audit a pinned commit, tests, dependencies and attribution before copying any code. Keep Highlight contracts independent so its discovery pipeline can be replaced. Clips Kitty is architectural reference only in this design; do not silently copy AGPL code into a differently licensed runtime. No third-party source is copied in this package.
