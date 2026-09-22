# Highlight Codex plugin

This package adds the existing local MCP server as a plugin with a single Highlight label, a short Thai description and an icon. Workflow instructions come from MCP initialization. Reference skill material is kept outside the installed plugin so it does not create a second composer entry.

Install the Python runtime from the main README first. Use Codex's plugin-creator scaffold to register `highlight` in the personal marketplace, then run from this repository:

```powershell
.venv\Scripts\python.exe scripts/prepare_codex_plugin.py --destination "$env:USERPROFILE\plugins\highlight"
codex plugin add highlight@personal
codex plugin list --marketplace personal --json
```

The preparation script requires an already scaffolded personal plugin. It writes the current venv interpreter into the local `.mcp.json`; the checked-in `.mcp.json` uses `python` as a portable template. It does not edit marketplace files or copy any API key. Version 0.2 does not read or use any model API key. Old credentials are left untouched. The host agent selects highlights using transcript/render tools.

Start a new task after installation to pick up the tools. Search for `Highlight` in the composer mention picker. Select the Highlight action with the purple play icon, not the repository folder. Provide a YouTube link and requested highlights. The preparation script preserves older bundled skills and its own former personal skill in backups outside discovery paths, avoiding duplicate entries.

For updates, run the plugin-creator cachebuster helper after preparing the local source and reinstall `highlight@personal`. The host loads its cached installed copy, not this source directory.

Reference: [official plugin packaging](https://developers.openai.com/plugins/build/plugins).
