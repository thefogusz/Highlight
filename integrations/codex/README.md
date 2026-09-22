# Highlight Codex plugin

This package adds composer discovery metadata, an icon, an agent workflow skill and the existing local MCP server. Standalone MCP registration alone does not provide this plugin entry.

Install the Python runtime from the main README first. Use Codex's plugin-creator scaffold to register `highlight` in the personal marketplace, then run from this repository:

```powershell
.venv\Scripts\python.exe scripts/prepare_codex_plugin.py --destination "$env:USERPROFILE\plugins\highlight"
codex plugin add highlight@personal
codex plugin list --marketplace personal --json
```

The preparation script requires an already scaffolded personal plugin. It writes the current venv interpreter into the local `.mcp.json`; the checked-in `.mcp.json` uses `python` as a portable template. It does not edit marketplace files or copy any API key. Model and key remain in the existing Highlight settings and OS credential store.

Start a new task after installation to pick up plugin skills and tools. Search for `Highlight` in the composer mention picker. Select the plugin entry with the purple play icon, not the repository folder. Provide a YouTube link and requested highlights. Plugin registration is distinct from verifying host UI discovery or running a real video analysis.

For updates, run the plugin-creator cachebuster helper after preparing the local source and reinstall `highlight@personal`. The host loads its cached installed copy, not this source directory.

Reference: [official plugin packaging](https://developers.openai.com/plugins/build/plugins).
