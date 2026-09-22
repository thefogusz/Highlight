import json
from pathlib import Path
from highlight_mcp.subtitles import parse_json3, youtube_subtitles
from highlight_mcp.core import Failure


DATA = {'events': [{'tStartMs': 1000, 'dDurationMs': 2000, 'segs': [{'utf8': 'สวัสดีครับ'}]}]}


def test_timestamp_and_invalid_rows():
    rows = parse_json3(DATA, 2)
    assert rows == [{'start': 1, 'end': 2, 'text': 'สวัสดีครับ'}]
    assert parse_json3({'events': [{'tStartMs': 'bad'}]}, 60) == []


def test_manual_preferred(tmp_path):
    calls=[]
    def command(args, *rest):
        calls.append(args)
        Path(args[args.index('-o')+1].replace('%(ext)s','th.json3')).write_text(json.dumps(DATA),encoding='utf-8')
    rows, source = youtube_subtitles([], 'url', tmp_path, 3, lambda:None, command)
    assert rows and source == 'youtube_manual_th' and len(calls)==1


def test_auto_fallback(tmp_path):
    def command(args, *rest):
        if '--write-auto-subs' in args:
            Path(args[args.index('-o')+1].replace('%(ext)s','th-orig.json3')).write_text(json.dumps(DATA),encoding='utf-8')
    assert youtube_subtitles([], 'url', tmp_path, 3, lambda:None, command)[1]=='youtube_auto_th'


def test_truncated_caption_track_cannot_replace_full_episode(tmp_path):
    def command(args, *rest):
        Path(args[args.index('-o')+1].replace('%(ext)s','th.json3')).write_text(json.dumps(DATA),encoding='utf-8')
    assert youtube_subtitles([], 'url', tmp_path, 8292, lambda:None, command)==([], 'fetch_failed_or_unusable')


def test_fetch_failure_allows_whisper(tmp_path):
    def command(*args): raise Failure('RENDER_FAILED','no captions')
    assert youtube_subtitles([], 'url', tmp_path, 60, lambda:None, command)==([], 'fetch_failed_or_unusable')
