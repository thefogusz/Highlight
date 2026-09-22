"""Import a host-agent acquired full source into an existing failed job."""
import json
import math
from pathlib import Path

from .core import Failure, canonical_url
from .pipeline import command, probe, validate_source_duration


def import_source(settings, job, acquisition):
    if job['state'] != 'failed' or job['stage'] != 'ingest':
        raise Failure('INVALID_STATE', 'Source recovery requires a failed ingest job.')
    if canonical_url(acquisition['source_url']) != job['request']['url']:
        raise Failure('INVALID_SOURCE', 'Acquired source URL differs from this job.')
    source = Path(acquisition['path'])
    if not source.is_absolute() or not source.is_file():
        raise Failure('INVALID_SOURCE', 'Provide an existing absolute local media path.')
    info = probe(settings, source, lambda: None)
    duration = float(info.get('format', {}).get('duration', 0))
    if not math.isfinite(duration):
        raise Failure('INVALID_SOURCE', 'Invalid media duration.')
    validate_source_duration(duration, False)
    if abs(duration - acquisition['expected_duration_seconds']) > max(2, duration * .001):
        raise Failure('INVALID_SOURCE', 'Source must contain the full video with the original timeline.')
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    if min(video.get('width', 0), video.get('height', 0)) < 720 or not any(s.get('codec_type') == 'audio' for s in streams):
        raise Failure('INVALID_SOURCE', 'Source requires at least 720p and an audio track.')
    root = settings.root / job['id']
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / 'importing.mp4'
    try:
        command([settings.binary('ffmpeg'), '-v', 'error', '-y', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', str(temporary)], lambda: None)
        command([settings.binary('ffmpeg'), '-v', 'error', '-xerror', '-i', str(temporary), '-f', 'null', '-'], lambda: None)
        temporary.replace(root / 'source.mp4')
    finally:
        temporary.unlink(missing_ok=True)
    metadata_path = root / 'metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    metadata.update(duration=duration, is_live=False)
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
    return {'source_url': acquisition['source_url'], 'method': acquisition['method'],
            'duration': duration, 'quality_height': min(video['width'], video['height']),
            'identity_verification': 'host_agent_attested_url_and_duration'}
