"""Optional, locally installed PO provider; no account-cookie access."""
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from .core import Failure


def fallback_args(settings, base):
    home = settings.config.get('youtube_po_provider_home')
    if not home or not settings.binary('node'):
        return None
    home = Path(home).resolve()
    if not (home / 'build' / 'generate_once.js').is_file():
        return None
    try:
        if version('bgutil-ytdlp-pot-provider') != '2.0.0':
            return None
    except PackageNotFoundError:
        return None
    return [*base, '--extractor-args', 'youtube:player_client=mweb',
            '--extractor-args', 'youtubepot-bgutilscript:server_home=' + str(home)]


def fetch_with_fallback(fetch, primary, fallback, record):
    try:
        return fetch(primary), primary
    except Failure as exc:
        eligible = exc.code == 'RENDER_FAILED' and any(x in str(exc) for x in ('sign-in verification', 'HTTP 403'))
        if not eligible or fallback is None:
            raise
        record('default_failed_trying_mweb_po')
        try:
            result = fetch(fallback)
        except Failure:
            record('mweb_po_failed')
            raise
        record('mweb_po_succeeded')
        return result, fallback
