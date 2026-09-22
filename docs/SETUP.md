# Settings and host integration design

**Original target design. Local alpha now implements stdio, a Tkinter settings form and OS keyring. Follow [README](../README.md) and [runtime implementation/limits](RUNTIME.md) for executable instructions. Sections below describe the fuller target, not a claim that every feature has shipped.**

## One-time setup target

Future installer flow: select data folder → check FFmpeg/yt-dlp/runtime → choose ASR CPU/GPU → enter Gemini key in a masked local form → choose available video/audio model → test connection → export host config. Downloading ASR weights is explicit in the setup progress. Local readiness is distinct from a provider test, which may incur a small charge and reports its usage.

The Gemini key is for video analysis, not YouTube heatmap. No YouTube Data API key, Paxa key, OpenAI key or hosted storage account is required for v1. Provider receives selected media/transcripts. Separate a user's Agent subscription from provider API billing.

## Secret storage

Supported planned modes, precedence:

1. `GEMINI_API_KEY` inherited from the MCP host/worker environment.
2. Local OS keyring entry `Highlight/gemini` (Windows Credential Manager; other OS equivalent when supported).

If both exist, environment wins and sanitized settings say key_source=environment. No hidden .env discovery. No key in settings.json, manifest, SQLite, logs, URLs, process arguments or tool responses. No `set_api_key` MCP tool. Replacing an environment key requires restarting the worker; jobs retain non-secret config version only. Invalid credential returns a sanitized error, never provider request headers.

The settings UI can show “configured”, “validated at <time>”, or “not tested”. Reopen never reveals existing key. Save/replace/clear via the local form; explicit clear does not delete job outputs. If secure keyring is unavailable, require environment configuration instead of silently storing plaintext.

Local wizard/gallery backend binds loopback, uses a per-session capability token, strict Origin checks and CSRF protection for writes. Never store secrets in localStorage. Do not expose the settings service to LAN. A clipboard-pasted key is entered by the user locally, not by the Agent.

## Non-secret settings

provider=gemini, model ID (validated during setup), language=th, data_dir, ASR model/device, retention, max source duration/bytes, max inspection seconds/calls, worker concurrency=1, output aspect=16:9. Model ID is explicitly selected and pinned in runtime configuration; there is no unverified alias in templates. API version/SDK and provider availability are revalidated at implementation time.

## Codex template

See [examples/codex.config.toml](../examples/codex.config.toml). It uses env_vars to pass an existing GEMINI_API_KEY from the host. If a user instead uses `[mcp_servers.highlight.env]` with an inline key, that config file contains a plaintext secret; never commit it. Keyring setup is preferable when the desktop host does not inherit the expected shell environment.

`command` must be an absolute path to the installed environment's Python; args use `-m highlight_mcp serve` (planned CLI). Avoid unpinned `npx`/`uvx` auto-downloads in a production host. No need to change host approval preferences in a template.

Host controls @ discovery. Acceptance requires listing Highlight tools in the actual host, executing a synthetic/local smoke job, then a real authorized clip job. The checked config's syntax is not proof of host connection.

## Generic MCP host template

See [examples/mcp.config.json](../examples/mcp.config.json). MCP clients differ in configuration formats and environment interpolation. The JSON template intentionally contains no `${ENV}` syntax or key; configure inherited environment or use the server keyring. Do not assume a JSON client supports Codex TOML or vice versa.

## Remote later

If processing moves to another machine, use Streamable HTTP with authentication; Gemini key stays on that server. Local stdio config cannot be pasted into a remote-only client. Remote gallery/artifact URLs need authenticated, expiring access. Multi-user key separation, quotas and authorization are release blockers for remote mode.
