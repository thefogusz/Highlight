"""One-time local connector setup and honest readiness reporting."""
import json
import os
from pathlib import Path
import shutil
import sys

FILES = ('manifest.json', 'background.js', 'popup.html', 'popup.js')


def registered(manifest):
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\NativeMessagingHosts\com.highlight.youtube') as key:
            if Path(winreg.QueryValueEx(key, '')[0]) != manifest or not manifest.is_file():
                return False
        host = json.loads(manifest.read_text(encoding='utf-8'))
        return host.get('name') == 'com.highlight.youtube' and Path(host.get('path', '')).is_file()
    except (OSError, ValueError, TypeError):
        return False


def prepare(settings):
    from .browser_bridge import IDENTITY
    import winreg
    directory = settings.root / 'browser-bridge'
    folder = directory / 'extension'
    launcher = directory / 'host.cmd'
    # CMD expands percent signs even inside quotes. Reject unusual unsafe paths.
    if any(c in str(settings.root) + sys.executable for c in '%\r\n"'):
        raise ValueError('Unsupported launcher path')
    folder.mkdir(parents=True, exist_ok=True)
    bundled = Path(__file__).parent / 'chrome'
    for name in FILES:
        shutil.copyfile(bundled / name, folder / name)
    launcher.write_text(f'@echo off\nset "HIGHLIGHT_DATA_DIR={settings.root}"\n"{sys.executable}" -m highlight_mcp.browser_bridge %*\n', encoding='utf-8')
    manifest = directory / 'host.json'
    manifest.write_text(json.dumps({'name': 'com.highlight.youtube', 'description': 'Highlight YouTube connection',
        'path': str(launcher), 'type': 'stdio', 'allowed_origins': [f'chrome-extension://{IDENTITY}/']}, indent=2), encoding='utf-8')
    for browser in ('Google\\Chrome', 'Microsoft\\Edge'):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f'Software\\{browser}\\NativeMessagingHosts\\com.highlight.youtube') as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))


def setup(settings, action='status', job=None):
    directory = settings.root / 'browser-bridge'
    folder = directory / 'extension'
    if os.name != 'nt':
        return {'connection_state': 'unsupported', 'extension_path': None, 'steps': [],
                'next_action': 'This connector currently supports Windows only. Continue supported source acquisition; do not instruct Windows setup here.'}
    if action == 'prepare':
        prepare(settings)
    from .browser_bridge import connection_recent
    connected = connection_recent(settings)
    ready = registered(directory / 'host.json') and all((folder / name).is_file() for name in FILES)
    state = 'connected' if connected else 'not_connected' if ready else 'setup_required'
    steps = [] if connected else [
        'ถ้ามี Highlight อยู่แล้ว ให้เปิดใช้งานและกดเชื่อมต่อก่อน ไม่ต้องติดตั้งซ้ำ; ขั้นตอนถัดไปใช้เมื่อยังไม่มีส่วนขยาย',
        'เปิด Chrome ไปที่ chrome://extensions แล้วเปิด Developer mode',
        'กด Load unpacked (โหลดส่วนขยายที่แตกไฟล์แล้ว) ไม่ใช่ Pack extension',
        f'เลือกโฟลเดอร์ {folder} ซึ่งมี manifest.json อยู่ด้านใน',
        'เปิดส่วนขยาย Highlight แล้วกด อนุญาตและเชื่อมต่อ และเปิด Chrome ค้างไว้',
        'ถ้าติดตั้งไว้แล้ว ให้เปิดใช้งานส่วนขยายเดิมก่อน ไม่ต้องติดตั้งซ้ำหรือเข้าสู่ระบบใหม่',
    ]
    if state == 'setup_required':
        steps = ['ให้ Agent เรียก highlight_browser_setup action=prepare เพื่อเตรียมไฟล์ก่อน']
    next_action = ('Connection heartbeat received; this does not prove video access. ' +
        (f"Resume highlight_retry job_id={job['id']} once only if it is failed at ingest and retry remains authorized. Preserve options and research. Never restart cancelled or completed jobs automatically." if job else 'Continue the requested job; do not create duplicate jobs.')) if connected else (
        'Call highlight_browser_setup action=prepare, then show returned steps and absolute extension_path.' if state == 'setup_required' else
        'Show these steps. Missing heartbeat cannot distinguish an absent extension from closed Chrome or disabled connection. After the user connects, call highlight_browser_setup status with the same job_id; do not retry ingestion until connected.')
    return {'connection_state': state, 'extension_path': str(folder) if ready else None,
            'steps': steps, 'next_action': next_action}
