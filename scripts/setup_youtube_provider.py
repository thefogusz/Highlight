"""Install a pinned local PO helper. Run with the Highlight virtualenv Python."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from highlight_mcp.core import Settings


def main():
    settings = Settings()
    git, npm, node = shutil.which('git'), shutil.which('npm.cmd') or shutil.which('npm'), settings.binary('node')
    if not all((git, npm, node)):
        raise SystemExit('Install Git and Node.js >=22 (including npm), then run this installer again.')
    home = settings.root / 'tools' / 'bgutil-2.0.0'
    home.parent.mkdir(parents=True, exist_ok=True)
    if not home.exists():
        subprocess.run([git, 'clone', '--depth', '1', '--branch', '2.0.0', 'https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git', str(home)], check=True)
    sha = subprocess.check_output([git, '-C', str(home), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != '37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8':
        raise SystemExit('Unexpected provider revision; installation stopped.')
    server = home / 'server'
    subprocess.run([npm, 'ci'], cwd=server, check=True)
    subprocess.run([node, str(server / 'node_modules/typescript/bin/tsc')], cwd=server, check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'bgutil-ytdlp-pot-provider==2.0.0'], check=True)
    settings.config['youtube_po_provider_home'] = str(server)
    temp = settings.config_file.with_suffix('.tmp')
    temp.write_text(json.dumps(settings.config, indent=2), encoding='utf-8')
    temp.replace(settings.config_file)
    print('Local PO helper configured. No browser cookies used. YouTube access is not guaranteed.')


if __name__ == '__main__':
    main()
