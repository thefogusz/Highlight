"""Populate an already scaffolded personal Highlight plugin; never edits marketplace/config."""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
destination = args.destination.resolve()
if destination.name != 'highlight' or not (destination / '.codex-plugin/plugin.json').is_file():
    raise SystemExit('Scaffold the personal highlight plugin first.')
# A standalone skill has a single display name; plugin skills gain a host prefix.
# Preserve old bundled skills outside the plugin rather than deleting them.
old_skills = destination / 'skills'
if old_skills.exists():
    if old_skills.is_symlink() or old_skills.resolve().parent != destination:
        raise SystemExit('Refusing unexpected skills path.')
    backup = destination.parent / ('highlight-skills-backup-' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
    old_skills.rename(backup)
shutil.copytree(repo / 'integrations/codex/highlight', destination, dirs_exist_ok=True)
assets = destination / 'assets'
assets.mkdir(exist_ok=True)
shutil.copy2(repo / 'src/highlight_mcp/assets/highlight.svg', assets / 'highlight.svg')
config = {'mcpServers': {'highlight': {'command': sys.executable, 'args': ['-m', 'highlight_mcp', 'serve']}}}
(destination / '.mcp.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
skill = Path.home() / '.codex' / 'skills' / 'highlight'
shutil.copytree(repo / 'integrations/codex/skills/highlight', skill, dirs_exist_ok=True)
print('Prepared local plugin:', destination)
print('Prepared composer skill:', skill)
