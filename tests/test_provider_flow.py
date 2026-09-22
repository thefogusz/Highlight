"""Fake provider, real media: proves orchestration, not Thai/model quality."""
import json
import subprocess
from types import SimpleNamespace
from google import genai
from highlight_mcp.core import Settings, Service
from highlight_mcp.pipeline import run


def test_cached_ingest_to_verified_clip_with_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    monkeypatch.setenv("HIGHLIGHT_MODEL", "synthetic-model")
    service = Service(Settings(tmp_path), launch=False)
    result = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk", "target_clips": 1, "min_duration_seconds": 5, "max_duration_seconds": 8, "captions": "srt"})
    job = service.store.get(result["job_id"])
    folder = tmp_path / job["id"]
    folder.mkdir()
    (folder / "metadata.json").write_text(json.dumps({"duration": 9, "heatmap": [], "is_live": False}))
    (folder / "transcript.json").write_text(json.dumps([{"start": 0, "end": 9, "text": "test"}]))
    subprocess.run([service.settings.binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-t", "9", "-c:v", "libx264", str(folder / "source.mp4")], check=True)
    deleted = []
    replies = iter([{"clips": [{"start_seconds": 1, "end_seconds": 7, "categories": ["funny"], "title_th": "test", "reason_th": "test"}]}, {"keep": True, "title_th": "test", "reason_th": "test", "confidence": "medium", "categories": ["funny"]}])
    class FakeClient:
        def __init__(self, **kwargs):
            self.models = SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text=json.dumps(next(replies))))
            self.files = SimpleNamespace(upload=lambda **kwargs: SimpleNamespace(name="fake", state=SimpleNamespace(name="ACTIVE")), delete=lambda **kwargs: deleted.append(kwargs["name"]))
        def close(self):
            pass
    monkeypatch.setattr(genai, "Client", FakeClient)
    run(service.settings, service.store, job, lambda: None)
    output = service.call("highlight_results", {"job_id": job["id"]})
    assert output["ok"], output
    assert output["job_state"] == "completed"
    assert output["clips"][0]["replay_score"] is None
    assert len(output["clips"][0]["artifacts"]) == 2
    assert deleted == ["fake"]
