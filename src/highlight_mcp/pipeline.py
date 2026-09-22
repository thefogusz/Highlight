"""Bounded local pipeline. Provider results are data, never executable commands."""
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import Failure, valid_range, MAX_SOURCE_SECONDS


def refresh_missing_heatmap(metadata, fetch):
    try:
        fresh = fetch()
        heatmap = fresh.get('heatmap')
        if heatmap is not None and not isinstance(heatmap, list):
            return metadata, 'fetch_failed'
        return {**metadata, 'heatmap': heatmap}, 'available' if heatmap else 'not_returned'
    except Failure as exc:
        if exc.code != 'RENDER_FAILED':
            raise
        return metadata, 'fetch_failed'
    except (ValueError, TypeError, AttributeError):
        return metadata, 'fetch_failed'


def validate_source_duration(duration, is_live):
    if is_live or not valid_range(0, duration, MAX_SOURCE_SECONDS):
        raise Failure("LIMIT_EXCEEDED", "Use a completed video no longer than six hours.")


def discovery_windows(duration, target_clips):
    # Reserve one ranking call and one video inspection per requested clip.
    available = max(1, 30 - target_clips - 1)
    width = max(600, math.ceil(duration / available))
    return [(start, min(duration, start + width + 60))
            for start in range(0, math.ceil(duration), width)]


def selection_ranges(opts, duration):
    start = opts.get('start_seconds', 0)
    if not valid_range(start, duration, duration):
        raise Failure('INVALID_RANGE', 'Start time must be before the end of the video.')
    ranges = opts['focus_ranges'] or [{'start_seconds': start, 'end_seconds': duration}]
    # Only trim a sub-quarter-second end rounding difference; never expand clips.
    ranges = [{**r, 'end_seconds': duration if duration < r['end_seconds'] <= duration + .25 else r['end_seconds']} for r in ranges]
    if any(not valid_range(r['start_seconds'], r['end_seconds'], duration) for r in ranges):
        raise Failure('INVALID_RANGE', 'Focus range exceeds video duration.')
    ranges = [{**r, 'start_seconds': max(start, r['start_seconds'])} for r in ranges if r['end_seconds'] > start]
    if not ranges:
        raise Failure('INVALID_RANGE', 'Focus ranges end before the requested start time.')
    return ranges


def youtube_failure(stderr):
    """Return safe categories, never raw stderr containing URLs or credentials."""
    text = stderr.lower()
    if 'sign in to confirm' in text or 'not a bot' in text:
        return 'YouTube requires sign-in verification for this request. Do not retry unchanged or request an MP4 by default. Explain the sign-in requirement; authenticated downloader access needs explicit user authorization.', False
    if any(x in text for x in ('private video', 'members-only', 'not available in your country', 'video unavailable', 'removed by')):
        return 'YouTube source is restricted or unavailable. Check video access; do not promise that uploading an MP4 will immediately produce clips.', False
    if 'http error 403' in text:
        return 'YouTube returned HTTP 403 for this media request. Check client and PO Token support.', False
    if any(x in text for x in ('429', 'too many requests')):
        return 'YouTube rate-limited this request. Stop repeated requests and retry later; do not ask for an MP4 by default.', False
    if any(x in text for x in ('timed out', 'temporary failure', 'connection reset', 'http error 503', 'http error 502')):
        return 'Temporary YouTube connection failure. One automatic retry was attempted; preserve the existing job and user options.', True
    return 'YouTube download failed for an unclassified reason. Inspect the downloader installation and source access before asking the user for a file.', False


def command(args, check, timeout=3600, _retried=False):
    import tempfile
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen([str(a) for a in args], stdout=out, stderr=err,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = time.monotonic()
        try:
            while p.poll() is None:
                check()
                if time.monotonic() - started > timeout:
                    raise Failure("LIMIT_EXCEEDED", "Local operation timed out.")
                time.sleep(.25)
            if p.returncode:
                err.seek(0)
                if 'yt_dlp' in [str(a) for a in args]:
                    message, transient = youtube_failure(err.read().decode('utf-8', errors='replace'))
                    if transient and not _retried:
                        for _ in range(8):
                            check()
                            time.sleep(.25)
                        return command(args, check, timeout, _retried=True)
                    raise Failure("RENDER_FAILED", message)
                raise Failure("RENDER_FAILED", "FFmpeg/media operation failed; inspect source integrity and installed media tools.")
            out.seek(0)
            return out.read()
        finally:
            if p.poll() is None:
                import psutil
                try:
                    for child in psutil.Process(p.pid).children(recursive=True):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                except psutil.NoSuchProcess:
                    pass
                p.kill()
                p.wait()


def probe(settings, path, check):
    return json.loads(command([settings.binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", path], check, 60))


def render_clip(settings, source, output, start, end, aspect, check, maximum=60):
    if not valid_range(start, end, end) or end - start > maximum:
        raise Failure("INVALID_RANGE", f"Each highlight must be at most {maximum} seconds. Re-select a complete moment within the requested limit.")
    info = probe(settings, source, check)
    if not valid_range(start, end, float(info["format"]["duration"])):
        raise Failure("INVALID_RANGE", "Clip lies outside the source.")
    w, h = (720, 1280) if aspect == "9:16" else (1280, 720)
    command([settings.binary("ffmpeg"), "-v", "error", "-y", "-ss", start, "-i", source, "-t", end-start,
             "-map", "0:v:0", "-map", "0:a:0?", "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
             "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-movflags", "+faststart", output], check)
    result = probe(settings, output, check)
    if float(result['format']['duration']) > maximum or abs(float(result["format"]["duration"]) - (end-start)) > .3:
        raise Failure("RENDER_FAILED", "Rendered duration failed verification.")
    command([settings.binary("ffmpeg"), "-v", "error", "-xerror", "-i", output, "-f", "null", "-"], check)


def validate_proposal(p, duration):
    if not isinstance(p, dict) or not valid_range(p.get("start_seconds"), p.get("end_seconds"), duration):
        raise Failure("MODEL_OUTPUT_INVALID", "Model returned an invalid timestamp.")


def choose_candidates(proposals, heatmap, duration, minimum, maximum, count, focus):
    selected = []
    for p in proposals:
        validate_proposal(p, duration)
        a, b = p["start_seconds"], p["end_seconds"]
        if not minimum <= b-a <= maximum:
            continue
        if focus and not any(r["start_seconds"] <= a and b <= r["end_seconds"] for r in focus):
            continue
        if any(max(0, min(b, q["end_seconds"])-max(a, q["start_seconds"])) / min(b-a, q["end_seconds"]-q["start_seconds"]) > .5 for q in selected):
            continue
        values = [h["value"] for h in heatmap if h["start_time"] < b and h["end_time"] > a]
        selected.append({**p, "replay_score": max(values) if values else None})
        if len(selected) >= count:
            break
    return selected


def artifact(path, job_id, kind, mime):
    return {"kind": kind, "mime_type": mime, "path": str(path.resolve()),
            "resource_uri": f"highlight://jobs/{job_id}/{path.name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size, "expires_at": (datetime.now(timezone.utc)+timedelta(days=30)).isoformat()}


def run(settings, store, job, check):
    root = settings.root / job["id"]
    root.mkdir(exist_ok=True)
    opts = {**job["request"]["options"]}
    opts['min_duration_seconds'] = min(opts['min_duration_seconds'], opts['max_duration_seconds'])
    def stage(name):
        check()
        store.update(job["id"], stage=name)
    def cached(name, produce):
        path = root / (name + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = produce()
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
        return data
    rev = job["request"].get("revision")
    if job['request'].get('selection') and not rev:
        selection = job['request']['selection']
        source = settings.root / selection['source_job'] / 'source.mp4'
        duration = float(probe(settings, source, check)['format']['duration'])
        selected = selection['clips']
        transcript = json.loads((source.parent / 'transcript.json').read_text(encoding='utf-8'))
        store.update(job['id'], source_job=selection['source_job'], duration=duration)
    elif rev:
        source = settings.root / rev["source_job"] / "source.mp4"
        duration = float(probe(settings, source, check)["format"]["duration"])
        selected = [{**rev["clip"], "start_seconds": rev["start_seconds"], "end_seconds": rev["end_seconds"]}]
        store.update(job["id"], source_job=rev["source_job"], duration=duration)
        transcript_path = source.parent / "transcript.json"
        transcript = json.loads(transcript_path.read_text(encoding="utf-8")) if transcript_path.exists() else []
    else:
        stage("ingest")
        base = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--socket-timeout", "30"]
        if settings.binary("node"):
            base += ["--js-runtimes", "node:" + settings.binary("node")]
        def fetch_metadata():
            nonlocal base
            from .youtube import fallback_args, fetch_with_fallback
            def fetch(arguments):
                return command(arguments + ["--dump-single-json", "--skip-download", job["request"]["url"]], check, 180)
            alternate = None if 'youtube:player_client=mweb' in base else fallback_args(settings, base)
            payload, base = fetch_with_fallback(fetch, base, alternate,
                lambda state: store.update(job['id'], youtube_access=state))
            raw = json.loads(payload)
            return {key: raw.get(key) for key in ("duration", "is_live", "heatmap")}
        had_metadata = (root / 'metadata.json').exists()
        metadata = cached("metadata", fetch_metadata)
        duration = metadata.get("duration") or 0
        validate_source_duration(duration, metadata.get("is_live"))
        # Metadata duration is often rounded. Validate focus against the media probe below.
        heatmap_state = 'available' if metadata.get('heatmap') else 'not_returned'
        # One fresh metadata request per run, never a video download or model call.
        # Preserve cached candidate decisions on retries; don't silently reanalyse paid work.
        if opts['heatmap'] != 'ignore' and had_metadata and not metadata.get('heatmap') and not (root / 'candidates.json').exists():
            metadata, heatmap_state = refresh_missing_heatmap(metadata, fetch_metadata)
            if heatmap_state != 'fetch_failed':
                temporary = root / 'metadata.tmp'
                temporary.write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
                temporary.replace(root / 'metadata.json')
        heatmap = [] if opts["heatmap"] == "ignore" else metadata.get("heatmap") or []
        warnings = ([] if heatmap else
                    ['ปิดการใช้กราฟดูซ้ำตามตัวเลือกของงาน'] if opts['heatmap'] == 'ignore' else
                    ['ลองดึงกราฟดูซ้ำใหม่ไม่สำเร็จ ยังสรุปไม่ได้ว่าคลิปไม่มีกราฟ; ใช้บทสนทนาและภาพ/เสียงแทน'] if heatmap_state == 'fetch_failed' else
                    ['ข้อมูล YouTube ที่ดึงได้ไม่ส่งกราฟดูซ้ำมา ไม่ยืนยันว่าคลิปไม่มีกราฟ; ใช้บทสนทนาและภาพ/เสียงแทน'])
        store.update(job['id'], duration=duration, warnings=warnings)
        if not heatmap and opts["heatmap"] == "require":
            raise Failure("HEATMAP_UNAVAILABLE", warnings[0])
        source = root / "source.mp4"
        if not source.exists():
            command(base + ["--max-filesize", "5G", "--ffmpeg-location", str(Path(settings.binary("ffmpeg")).parent), "-f", "bv*[height<=720]+ba/b[height<=720]", "--merge-output-format", "mp4", "--remux-video", "mp4", "-o", str(root / "download.%(ext)s"), job["request"]["url"]], check)
            downloaded = root / "download.mp4"
            if not downloaded.exists():
                raise Failure("SOURCE_UNAVAILABLE", "YouTube did not provide a downloadable video.")
            downloaded.replace(source)
        duration = float(probe(settings, source, check)["format"]["duration"])
        validate_source_duration(duration, False)
        opts['focus_ranges'] = selection_ranges(opts, duration)
        store.update(job["id"], duration=duration)
        stage("transcribe")
        def transcribe():
            from .subtitles import youtube_subtitles
            rows, origin = youtube_subtitles(base, job['request']['url'], root, duration, check, command)
            if rows:
                store.update(job['id'], transcript_source=origin,
                             warnings=store.get(job['id'])['warnings'] + ['ใช้คำบรรยายไทยจาก YouTube; ซับอาจคลาดเคลื่อน โดยเฉพาะคำพูดซ้อนและชื่อคน'])
                return rows
            store.update(job['id'], transcript_source='whisper',
                         warnings=store.get(job['id'])['warnings'] + [
                             'ดึงซับไทยไม่ได้หรือซับใช้ไม่ได้ จึงถอดเสียงด้วย Whisper' if origin == 'fetch_failed_or_unusable'
                             else 'ไม่พบซับไทยที่ดึงได้ จึงถอดเสียงด้วย Whisper'])
            from .transcription import transcribe_chunks
            return transcribe_chunks(settings, store, job['id'], source, duration, check, command)
        transcript = cached("transcript", transcribe)
        store.update(job['id'], state='awaiting_selection', stage='select', progress=None)
        return
    stage("render")
    clips = []
    for i, p in enumerate(selected):
        output = root / f"clip_{i+1}.mp4"
        render_clip(settings, source, output, p["start_seconds"], p["end_seconds"], opts["aspect"], check, maximum=opts["max_duration_seconds"])
        artifacts = [artifact(output, job["id"], "video", "video/mp4")]
        if opts["captions"] == "srt":
            def stamp(seconds):
                ms = round(seconds*1000)
                return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
            rows = [s for s in transcript if s["end"] > p["start_seconds"] and s["start"] < p["end_seconds"]]
            srt = output.with_suffix(".srt")
            srt.write_text("\n\n".join(f"{n+1}\n{stamp(max(0,s['start']-p['start_seconds']))} --> {stamp(min(p['end_seconds'],s['end'])-p['start_seconds'])}\n{s['text']}" for n,s in enumerate(rows)), encoding="utf-8")
            if rows:
                artifacts.append(artifact(srt, job["id"], "transcript", "application/x-subrip"))
        clip = {"clip_id": p.get("clip_id", f"clip_{i+1}"), "revision": p.get("revision", 0)+1, "title_th": p["title_th"], "start_seconds": p["start_seconds"], "end_seconds": p["end_seconds"], "categories": p["categories"], "reason_th": p["reason_th"], "confidence": p.get("confidence", "low"), "replay_score": None if rev else p["replay_score"], "verification": "verified", "evidence": [{"source": "transcript", "description_th": "Agent เลือกจากบทสนทนา; ตรวจไฟล์ด้วย FFmpeg แล้ว แต่ไม่ได้ยืนยันการตรวจภาพและเสียง", "start_seconds": p["start_seconds"], "end_seconds": p["end_seconds"]}], "artifacts": artifacts}
        clips.append(clip)
        store.update(job["id"], clips=clips)
    stage("verify")
    store.update(job["id"], state="completed" if len(clips) >= (1 if rev else len(selected)) else "partial", progress=1)
