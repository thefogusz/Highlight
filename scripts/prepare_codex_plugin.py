"""Populate an already scaffolded personal Highlight plugin; never edits marketplace/config."""
import argparse
import json
import shutil
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
destination = args.destination.resolve()
if destination.name != 'highlight' or not (destination / '.codex-plugin/plugin.json').is_file():
    raise SystemExit('Scaffold the personal highlight plugin first.')
shutil.copytree(repo / 'integrations/codex/highlight', destination, dirs_exist_ok=True)
assets = destination / 'assets'
assets.mkdir(exist_ok=True)
shutil.copy2(repo / 'src/highlight_mcp/assets/highlight.svg', assets / 'highlight.svg')
config = {'mcpServers': {'highlight': {'command': sys.executable, 'args': ['-m', 'highlight_mcp', 'serve']}}}
(destination / '.mcp.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
print('Prepared local plugin:', destination)
