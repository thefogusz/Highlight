# Evidence and source register

Checked 2026-09-22. Capabilities below come from documentation/source inspection, not our runtime test. Model names, prices, SDK versions and platform behavior can change; recheck at implementation.

| Source | What it supports | What it does not prove |
|---|---|---|
| [MCP server guide](https://modelcontextprotocol.io/docs/develop/build-server) | SDK-based server and stdio logging rules | That Highlight exists or connects |
| [MCP tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) | input/output schemas, structured results and annotations | Exactly-once execution or job persistence |
| [MCP transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) | stdio and Streamable HTTP | Universal @ mention or inline video player |
| [Codex MCP configuration](https://developers.openai.com/codex/mcp/) | command/args/env/env_vars configuration | Current user host already configured |
| [Gemini video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) | Audio/video input, timestamp queries, sampling controls | Thai humor accuracy or frame-accurate editing |
| [Gemini key setup](https://ai.google.dev/gemini-api/docs/api-key) | Provider key configuration | Free/available quota for the user |
| [yt-dlp YouTube extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py) | Heatmap start/end/normalized intensity extraction | All videos expose a heatmap or raw viewer counts |
| [OpenShorts MCP source](https://github.com/mutonby/openshorts/blob/main/mcp_server.py) | Source exposes process/status/results/recut tools | Production reliability or Thai evaluation |
| [OpenShorts README](https://github.com/mutonby/openshorts) | Transcript-based moment picker and optional framing | Complete visual-humor understanding |
| [OpenShorts license](https://github.com/mutonby/openshorts/blob/main/LICENSE) | MIT license file at checked revision | Compatibility of every transitive dependency |
| [Clips Kitty](https://github.com/ColinGPT9/clips-studio) | Transcript/signal workflow reference, AGPL-3.0 | Permission to copy without license obligations |
| [Paxa STT](https://paxalabs.com/th/speech-to-text) | Research status at inspection | Available production transcription endpoint |

## Decision record

- Build a thin independent Highlight service: OpenShorts provides useful reference, but a whole fork adds unrelated publishing/UGC/billing complexity.
- Gemini first because one provider accepts audio/video; ASR and deterministic editing remain separate. No claim it wins Thai benchmarks.
- Local stdio first for one owner; persistence independent of chat transport. Remote mode deferred until authentication/tenant isolation exists.
- Separate replay evidence from editorial scores. Heatmap is an accelerator, not the only candidate source.
- Secrets via environment/keyring, not Agent-visible configuration tools. Host @ experience is integration-specific.
