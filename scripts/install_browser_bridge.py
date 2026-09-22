"""Register the bundled native host, never install browser extensions silently."""
import json
import os
from pathlib import Path
import sys


def main():
    if os.name != 'nt':
        raise SystemExit('This installer supports Windows.')
    import winreg
    from highlight_mcp.core import Settings
    from highlight_mcp.browser_bridge import IDENTITY
    settings = Settings()
    directory = settings.root / 'browser-bridge'
    directory.mkdir(exist_ok=True)
    launcher = directory / 'host.cmd'
    launcher.write_text(f'@echo off\nset "HIGHLIGHT_DATA_DIR={settings.root}"\n"{sys.executable}" -m highlight_mcp.browser_bridge %*\n', encoding='utf-8')
    manifest = directory / 'host.json'
    manifest.write_text(json.dumps({'name':'com.highlight.youtube','description':'Highlight YouTube connection',
        'path':str(launcher),'type':'stdio','allowed_origins':[f'chrome-extension://{IDENTITY}/']},indent=2))
    for browser in ('Google\\Chrome', 'Microsoft\\Edge'):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f'Software\\{browser}\\NativeMessagingHosts\\com.highlight.youtube') as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
    print('Native host installed:', manifest)
    print('Extension folder:', Path(__file__).resolve().parents[1] / 'integrations' / 'chrome')
    print('Browser installation and session permission still require user action. No Web Store release exists yet.')


if __name__ == '__main__':
    main()
