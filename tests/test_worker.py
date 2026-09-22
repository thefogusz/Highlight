import json
import subprocess
from highlight_mcp.core import Settings, Service
from highlight_mcp.worker import worker


def test_worker_renders_revision_without_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HIGHLIGHT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HIGHLIGHT_DISABLE_KEYRING", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = Settings()
    service = Service(settings, launch=False)
    created = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    parent_id = created["job_id"]
    folder = tmp_path / parent_id
    folder.mkdir()
    source = folder / "source.mp4"
    subprocess.run([settings.binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "9", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    clip = {"clip_id": "clip_1", "revision": 1, "title_th": "ทดสอบ", "start_seconds": 0, "end_seconds": 5, "categories": ["highlight"], "reason_th": "test", "confidence": "low"}
    service.store.update(parent_id, state="completed", duration=9, clips=[clip])
    revised = service.call("highlight_revise", {"job_id": parent_id, "clip_id": "clip_1", "expected_revision": 1, "start_seconds": 1, "end_seconds": 7})
    assert revised["ok"], revised
    worker()
    result = service.call("highlight_results", {"job_id": revised["job_id"]})
    assert result["ok"], result
    assert result["job_state"] == "completed", service.store.get(revised["job_id"])
    assert result["clips"][0]["revision"] == 2
    assert result["clips"][0]["artifacts"][0]["size_bytes"] > 0


def test_crashed_worker_requires_explicit_retry(tmp_path):
    service = Service(Settings(tmp_path), launch=False)
    job = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    service.store.update(job["job_id"], state="running")
    status = service.call("highlight_status", {"job_id": job["job_id"]})
    assert status["state"] == "interrupted"
