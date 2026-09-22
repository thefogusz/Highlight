# Highlight Codex plugin

This package adds the existing local MCP server as a plugin and installs a companion personal skill named Highlight. The separate skill avoids the host's `Plugin: Skill` prefix, giving the composer a single Highlight label, a short Thai description and an icon.

Install the Python runtime from the main README first. Use Codex's plugin-creator scaffold to register `highlight` in the personal marketplace, then run from this repository:

```powershell
.venv\Scripts\python.exe scripts/prepare_codex_plugin.py --destination "$env:USERPROFILE\plugins\highlight"
codex plugin add highlight@personal
codex plugin list --marketplace personal --json
```

The preparation script requires an already scaffolded personal plugin. It writes the current venv interpreter into the local `.mcp.json`; the checked-in `.mcp.json` uses `python` as a portable template. It does not edit marketplace files or copy any API key. Model and key remain in the existing Highlight settings and OS credential store.

Start a new task after installation to pick up the skill and tools. Search for `Highlight` in the composer mention picker. Select the Highlight action with the purple play icon, not the repository folder. Provide a YouTube link and requested highlights. The preparation script installs the personal skill into `~/.codex/skills/highlight` and preserves older bundled skills in a backup outside the plugin.

For updates, run the plugin-creator cachebuster helper after preparing the local source and reinstall `highlight@personal`. The host loads its cached installed copy, not this source directory.

Reference: [official plugin packaging](https://developers.openai.com/plugins/build/plugins).
