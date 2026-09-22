"""Two-minute ASR checkpoints, with original timestamps and bounded audio input."""
import json
import math
from .core import digest, now


def transcribe_chunks(settings, store, job_id, source, duration, check, command, model_factory=None):
    if model_factory is None:
        from faster_whisper import WhisperModel
        model_factory = WhisperModel
    model_name = settings.config.get('whisper_model', 'small')
    stamp = source.stat()
    identity = digest({'size': stamp.st_size, 'mtime': stamp.st_mtime_ns,
                       'duration': duration, 'model': model_name, 'version': 1})[:16]
    folder = source.parent / ('asr_' + identity)
    folder.mkdir(exist_ok=True)
    count = math.ceil(duration / 120)
    result, model = [], None

    def report(completed, chunks, observed=None):
        store.update(job_id, transcription={'completed_seconds': completed,
                     'observed_seconds': completed if observed is None else observed,
                     'total_seconds': duration, 'completed_chunks': chunks,
                     'total_chunks': count, 'updated_at': now()})

    report(0, 0)
    for index in range(count):
        check()
        start, end = index * 120, min(duration, (index + 1) * 120)
        cache = folder / f'{index:04}.json'
        if cache.exists():
            rows = json.loads(cache.read_text(encoding='utf-8'))
        else:
            if model is None:
                model = model_factory(model_name, device='cpu', compute_type='int8')
            check()
            left, right = max(0, start - 2), min(duration, end + 2)
            audio = folder / 'current.wav'
            command([settings.binary('ffmpeg'), '-v', 'error', '-y', '-ss', left,
                     '-i', source, '-t', right-left, '-vn', '-ac', '1', '-ar', '16000', audio], check, 120)
            try:
                segments, _ = model.transcribe(str(audio), language='th', vad_filter=True)
                rows = []
                last_report = start
                for segment in segments:
                    check()
                    a, b = max(0, left + segment.start), min(duration, left + segment.end)
                    # Overlap gives boundary context. Assign each segment to one core window.
                    if start <= (a + b) / 2 < end and a < b:
                        rows.append({'start': a, 'end': b, 'text': segment.text})
                    observed = min(end, max(start, b))
                    if observed - last_report >= 10:
                        report(start, index, observed)
                        last_report = observed
                check()
                temporary = cache.with_suffix('.tmp')
                temporary.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
                temporary.replace(cache)
            finally:
                audio.unlink(missing_ok=True)
        result.extend(rows)
        report(end, index + 1)
    return sorted(result, key=lambda row: row['start'])
