"""Run yt-dlp with a scoped browser session held only in memory."""
import http.cookiejar
import sys
from .browser_bridge import read_session
from .core import canonical_url


def main():
    import yt_dlp
    payload = read_session(sys.argv[1])
    _, _, urls, options = yt_dlp.parse_options(sys.argv[2:])
    if len(urls) != 1 or canonical_url(urls[0]) != payload['url']:
        raise ValueError('Session restricted to its requested video')
    options.pop('cookiefile', None)
    options.pop('cookiesfrombrowser', None)
    with yt_dlp.YoutubeDL(options) as downloader:
        for row in payload['cookies']:
            cookie = http.cookiejar.Cookie(0, row['name'], row['value'], None, False,
                row['domain'], True, row['domain'].startswith('.'), row['path'], True,
                bool(row['secure']), int(row['expirationDate']) if row.get('expirationDate') else None,
                not row.get('expirationDate'), None, None, {})
            downloader.cookiejar.set_cookie(cookie)
        return downloader.download(urls)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Browser-assisted download failed; session values are not logged.', file=sys.stderr)
        sys.exit(1)
