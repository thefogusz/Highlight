"""Prefer original Thai caption tracks; never request translated subtitles."""
import json
import math
from pathlib import Path
import tempfile
from .core import Failure


def parse_json3(data, duration):
    rows = []
    for event in data.get('events', []):
        if not isinstance(event, dict):
            continue
        start, length = event.get('tStartMs'), event.get('dDurationMs')
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, length)):
            continue
        a, b = max(0, start / 1000), min(duration, (start + length) / 1000)
        text = ''.join(s.get('utf8', '') for s in event.get('segs', [])
                       if isinstance(s, dict) and isinstance(s.get('utf8'), str))
        text = ' '.join(text.split())
        if a < b and text:
            if rows and rows[-1]['text'] == text and a <= rows[-1]['end']:
                rows[-1]['end'] = max(rows[-1]['end'], b)
            else:
                rows.append({'start': a, 'end': b, 'text': text})
    return sorted(rows, key=lambda r: r['start'])


def youtube_subtitles(base, url, root, duration, check, command):
    failed = False
    for automatic in (False, True):
        check()
        with tempfile.TemporaryDirectory(prefix='captions_', dir=root) as folder:
            try:
                command(base + ['--skip-download', '--retries', '0', '--extractor-args', 'youtube:skip=translated_subs', '--no-write-subs' if automatic else '--no-write-auto-subs',
                                '--write-auto-subs' if automatic else '--write-subs',
                                '--sub-langs', 'th,th-orig', '--sub-format', 'json3',
                                '-o', str(Path(folder) / 'captions.%(ext)s'), url], check, 120)
                for path in sorted(Path(folder).glob('captions.*.json3')):
                    rows = parse_json3(json.loads(path.read_text(encoding='utf-8')), duration)
                    # Conservative for talk shows: a truncated track must not replace
                    # the full transcript. This checks time span, not linguistic accuracy.
                    complete_span = rows and rows[0]['start'] <= max(60, duration * .05) and max(r['end'] for r in rows) >= duration * .9
                    if complete_span and any('\u0e00' <= c <= '\u0e7f' for row in rows for c in row['text']):
                        return rows, 'youtube_auto_th' if automatic else 'youtube_manual_th'
                    if rows:
                        failed = True
            except Failure as exc:
                if exc.code != 'RENDER_FAILED':
                    raise
                failed = True
            except (ValueError, TypeError, AttributeError, OSError):
                failed = True
    return [], 'fetch_failed_or_unusable' if failed else 'not_available'
