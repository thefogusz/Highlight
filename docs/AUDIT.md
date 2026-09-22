# Local audit and configuration UX — 2026-09-22

## Verified scope

- 46 automated tests: MCP stdio handshake/tools, validation, secret redaction, durable jobs, setup form, synthetic video rendering and revisions. Provider requests are mocked.
- 110 offline design checks and dependency consistency check.
- Installed Codex plugin enabled; Windows Start Menu shortcut targets the installed `pythonw.exe -m highlight_mcp setup`.
- Fixed three reproduced defects: queued retry did not restart a missing worker; status could overwrite completion with interrupted during a race; boolean model timestamps were accepted as numbers.

Not verified: live YouTube download + Gemini inference + Thai transcription as one complete job, Thai joke quality, Claude host connection, or current visual appearance in the Codex composer. A configured key is not proof of available generation quota. This is still local alpha, not a production certification.

## Opening settings

On the installed Windows machine: press Windows, search **Highlight Settings**, then open it. From an installed checkout, run:

```powershell
.venv\Scripts\pythonw.exe -m highlight_mcp setup
```

The Start Menu shortcut is machine-specific; a plain repository clone does not create it. Keys entered in this window are stored in the OS credential store. A host-provided `GEMINI_API_KEY` takes precedence. Never paste the key into agent chat.

## What other MCP projects do

Reviewed primary sources:

- [Anthropic Desktop Extensions](https://www.anthropic.com/engineering/desktop-extensions): a bundle declares `user_config`; Claude Desktop renders the form and stores sensitive configuration in the OS keychain. This avoids writing a separate setup window.
- [MCPB manifest](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md): supports required sensitive string fields, injected through `${user_config.api_key}`.
- [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server): environment variables, VS Code password prompts, and hosted OAuth. The prompt UI belongs to the host, not the MCP protocol itself.
- [ElevenLabs MCP](https://github.com/elevenlabs/elevenlabs-mcp): documents `ELEVENLABS_API_KEY` in host configuration. A custom popup is not required.
- [Claude Code MCP](https://code.claude.com/docs/en/mcp): supports browser authentication for compatible remote OAuth servers; this is distinct from Claude Desktop bundle configuration.

Recommendation (not implemented by this audit): keep the cross-host local settings fallback, offer native sensitive configuration in a future Claude Desktop MCPB package, and use host environment settings where available. Do not assume Codex accepts Claude's MCPB manifest fields. OAuth for a hosted Highlight service would require separate service/account infrastructure; it does not automatically replace this local pipeline's Gemini credentials.

An inline chat form is not a supported secret-entry shortcut: [OpenAI MCP guidance](https://developers.openai.com/plugins/build/mcp-server) prohibits collecting secrets through elicitation forms, and the [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation) directs sensitive flows to URL mode instead. A future setup action should open a separate secure form and return readiness only. This audit does not add that action or claim a native Codex secret field exists.

Known follow-up areas: full paid-provider end-to-end validation; model/config snapshot semantics for queued jobs; streaming checksums for large artifacts; corrupted-settings recovery; and packaging validation on each supported host. No claim that all edge cases have been eliminated.
