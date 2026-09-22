"""Local review media and host-reported editorial evidence, separate from decoding."""
import json
import shutil
import time
from .core import Failure, digest
from .pipeline import command, probe


def identity(settings, job, review, clip):
    source = settings.root / job['id'] / 'source.mp4'
    stat = source.stat()
    return digest({'story_id': review['story_id'], 'source_size': stat.st_size,
                   'source_mtime_ns': stat.st_mtime_ns,
                   'candidate_index': clip['candidate_index'],
                   'start': clip['start_seconds'], 'end': clip['end_seconds']})


def preview(service, job, review, args):
    settings = service.settings
    key = identity(settings, job, review, args)
    folder = settings.root / job['id'] / 'previews' / key
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / 'receipt.json'
    video, context, audio = (folder / name for name in ('clip.mp4', 'context.mp4', 'audio.wav'))
    if receipt.is_file() and all(p.is_file() for p in (video, context, audio)):
        return json.loads(receipt.read_text(encoding='utf-8'))
    last_disk_check = [0.0]
    def check():
        if time.monotonic() - last_disk_check[0] > 5:
            last_disk_check[0] = time.monotonic()
            if shutil.disk_usage(settings.root).free < 2 * 1024**3:
                raise Failure("DISK_FULL", "Keep at least 2 GB free for previews.")
            if sum(p.stat().st_size for p in (settings.root / job["id"]).rglob("*") if p.is_file()) > 8 * 1024**3:
                raise Failure("LIMIT_EXCEEDED", "Job media reached the 8 GB limit.")
        current = service.store.get(job['id'])
        if current['cancel_requested'] or current['state'] == 'cancelled':
            raise Failure('INVALID_STATE', 'Job cancelled; stop preview.')
    check()
    source = settings.root / job['id'] / 'source.mp4'
    a, b = args['start_seconds'], args['end_seconds']
    left, right = max(0, a-15), min(job['duration'], b+15)
    for output, start, end in ((video, a, b), (context, left, right)):
        command([settings.binary('ffmpeg'), '-v', 'error', '-y', '-ss', start, '-i', source,
                 '-t', end-start, '-map', '0:v:0', '-map', '0:a:0',
                 '-vf', 'scale=-2:480', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '26',
                 '-c:a', 'aac', '-movflags', '+faststart', output], check)
        actual = float(probe(settings, output, check)['format']['duration'])
        if abs(actual-(end-start)) > .3:
            raise Failure('RENDER_FAILED', 'Preview duration does not match selected range.')
    command([settings.binary('ffmpeg'), '-v', 'error', '-y', '-i', video,
             '-vn', '-ac', '1', '-ar', '16000', audio], check)
    result = {'job_id': job['id'], 'preview_id': key, 'video_path': str(video),
              'context_path': str(context), 'audio_path': str(audio),
              'clip_offset_in_context_seconds': a-left,
              'next_action': 'Inspect the actual clip video/audio and surrounding context with host media tools. Submit preview_id and editorial_review describing observed opening, ending and audio/visual cues only after inspection. If unavailable or incomplete, keep this preview as a draft and report the limitation; do not fabricate approval or call highlight_render. A preview receipt proves media preparation only.'}
    receipt.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


def require_editorial(settings, job, review, clip):
    key = identity(settings, job, review, clip)
    folder = settings.root / job['id'] / 'previews' / key
    if clip.get('preview_id') != key or not all((folder / name).is_file() for name in ('receipt.json', 'clip.mp4', 'context.mp4', 'audio.wav')):
        raise Failure('INVALID_STATE', 'Prepare and inspect highlight_preview for these exact boundaries and current story before rendering. Changed boundaries require fresh review.')
    evidence = clip.get('editorial_review', {})
    if evidence.get('status') != 'approved' or evidence.get('basis') != 'audiovisual':
        raise Failure('INVALID_STATE', 'Final clips require host-reported audiovisual approval. Retain previews as drafts when media tools are unavailable or the ending is unresolved.')
