"""Windows native messaging bridge. No HTTP listener or plaintext session files."""
import ctypes
import json
import os
import secrets
import struct
import sys
import time
from pathlib import Path

from .core import Failure, Settings, Store

IDENTITY = json.loads(Path(__file__).with_name('browser_identity.json').read_text())['extension_id']
ORIGIN = f'chrome-extension://{IDENTITY}/'


def crypt(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Windows only')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise RuntimeError('Session protection failed')
    try:
        return ctypes.string_at(output.data, output.length)
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(output.data)


def atomic(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def connection_recent(settings):
    """Allow tiny filesystem clock skew, not stale/far-future heartbeats."""
    try:
        age = time.time() - (settings.root / 'browser-connected').stat().st_mtime
        return -2 <= age < 45
    except OSError:
        return False


def request_session(settings, job, check, timeout=40):
    if not connection_recent(settings):
        return None
    root = settings.root / job['id']
    root.mkdir(exist_ok=True)
    request = root / 'browser-request.json'
    response = root / 'browser-session.bin'
    response.unlink(missing_ok=True)
    nonce = secrets.token_hex(24)
    atomic(request, json.dumps({'nonce': nonce, 'expires': time.time()+timeout}).encode())
    try:
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            check()
            if response.exists():
                payload = read_session(response)
                if payload['nonce'] == nonce and payload['url'] == job['request']['url']:
                    return response
            time.sleep(.25)
        raise Failure('SOURCE_UNAVAILABLE', 'Chrome connector did not respond. Open Chrome with the enabled Highlight extension; do not sign in again or close Chrome.')
    finally:
        request.unlink(missing_ok=True)


def read_session(path):
    payload = json.loads(crypt(Path(path).read_bytes(), decrypt=True))
    if payload['expires'] < time.time():
        raise Failure('SOURCE_UNAVAILABLE', 'Chrome session handoff expired; request a fresh handoff.')
    return payload


def pending(settings):
    result = []
    store = Store(settings.root)
    for job in store.all():
        path = settings.root / job['id'] / 'browser-request.json'
        if job['state'] != 'running' or job['stage'] != 'ingest' or not path.exists():
            continue
        request = json.loads(path.read_text())
        if request['expires'] > time.time():
            result.append({'job_id': job['id'], 'url': job['request']['url'], 'nonce': request['nonce']})
    return result


def handle(settings, message):
    if message.get('type') == 'poll':
        (settings.root / 'browser-connected').touch()
        return {'requests': pending(settings)}
    if message.get('type') == 'disconnect':
        (settings.root / 'browser-connected').unlink(missing_ok=True)
        for path in settings.root.glob('job_*/browser-session.bin'):
            path.unlink(missing_ok=True)
        return {'ok': True}
    matches = [r for r in pending(settings) if r['job_id'] == message.get('job_id') and r['nonce'] == message.get('nonce')]
    if message.get('type') != 'session' or len(matches) != 1:
        raise ValueError('No matching request')
    cookies = message.get('cookies')
    if not isinstance(cookies, list) or not 1 <= len(cookies) <= 200:
        raise ValueError('No session cookies')
    clean = []
    for row in cookies:
        domain = row.get('domain', '')
        if domain.lstrip('.') != 'youtube.com' and not domain.lstrip('.').endswith('.youtube.com'):
            raise ValueError('Unexpected cookie domain')
        if any(not isinstance(row.get(k), str) or len(row[k]) > 16000 or any(c in row[k] for c in '\r\n\x00') for k in ('name', 'value', 'path')):
            raise ValueError('Invalid cookie')
        clean.append({k: row.get(k) for k in ('domain', 'name', 'value', 'path', 'secure', 'expirationDate')})
    payload = {**matches[0], 'cookies': clean, 'expires': time.time()+3600}
    path = settings.root / matches[0]['job_id'] / 'browser-session.bin'
    atomic(path, crypt(json.dumps(payload).encode()))
    return {'ok': True}


def main():
    if len(sys.argv) < 2 or sys.argv[1] != ORIGIN:
        return 1
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    settings = Settings()
    while True:
        header = sys.stdin.buffer.read(4)
        if not header:
            return 0
        if len(header) != 4:
            return 1
        length = struct.unpack('<I', header)[0]
        if not 0 < length <= 1024*1024:
            return 1
        raw = sys.stdin.buffer.read(length)
        if len(raw) != length:
            return 1
        try:
            result = handle(settings, json.loads(raw))
        except Exception:
            result = {'ok': False, 'error': 'Connection request rejected; no session details logged.'}
        data = json.dumps(result).encode()
        sys.stdout.buffer.write(struct.pack('<I', len(data))+data)
        sys.stdout.buffer.flush()


if __name__ == '__main__':
    sys.exit(main())
