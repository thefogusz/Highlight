"""Fake provider, real media: proves orchestration, not Thai/model quality."""
import json
import subprocess
import pytest
from types import SimpleNamespace
from google import genai
from highlight_mcp.core import Settings, Service
from highlight_mcp.pipeline import run
from highlight_mcp.core import Failure


@pytest.mark.parametrize('reply,expected', [('not JSON', 'MODEL_OUTPUT_INVALID'), (None, 'MODEL_OUTPUT_INVALID'), ('[]', 'MODEL_OUTPUT_INVALID'), ('{}', 'MODEL_OUTPUT_INVALID'), (429, 'PROVIDER_RATE_LIMITED'), (503, 'PROVIDER_UNAVAILABLE')])
def test_provider_failure_stops_after_one_call(tmp_path, monkeypatch, reply, expected):
    from google.genai.errors import ClientError
    from highlight_mcp import pipeline
    from highlight_mcp import provider_errors
    from functools import partial
    monkeypatch.setattr(provider_errors, 'generate_with_retry', partial(provider_errors.generate_with_retry, sleep=lambda _: None))
    monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('HIGHLIGHT_MODEL', 'synthetic-model')
    service = Service(Settings(tmp_path), launch=False)
    created = service.call('highlight_create', {'url': 'https://youtu.be/abcdefghijk?t=30', 'heatmap': 'ignore'})
    job = service.store.get(created['job_id'])
    root = tmp_path / job['id']
    root.mkdir()
    (root / 'metadata.json').write_text(json.dumps({'duration': 120, 'is_live': False}))
    (root / 'transcript.json').write_text(json.dumps([{'start': 0, 'end': 20, 'text': 'before timestamp'}, {'start': 30, 'end': 120, 'text': 'in scope'}]))
    (root / 'source.mp4').touch()
    monkeypatch.setattr(pipeline, 'probe', lambda *args: {'format': {'duration': 120}})
    calls, closed = [], []
    class FakeClient:
        def __init__(self, **kwargs):
            self.models = SimpleNamespace(generate_content=self.generate)
        def generate(self, **kwargs):
            calls.append(kwargs)
            assert 'before timestamp' not in kwargs['contents'][0]
            if reply in (429, 503):
                raise ClientError(reply, {'error': {'message': 'synthetic-key'}})
            return SimpleNamespace(text=reply, usage_metadata=None)
        def close(self):
            closed.append(True)
    monkeypatch.setattr(genai, 'Client', FakeClient)
    with pytest.raises(Failure) as caught:
        run(service.settings, service.store, job, lambda: None)
    assert caught.value.code == expected
    assert 'synthetic-key' not in str(caught.value)
    expected_calls = 3 if reply == 503 else 1
    assert len(calls) == expected_calls and closed == [True]
    assert service.store.get(job['id'])['provider_calls'] == expected_calls


def test_cached_ingest_to_verified_clip_with_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    monkeypatch.setenv("HIGHLIGHT_MODEL", "synthetic-model")
    service = Service(Settings(tmp_path), launch=False)
    result = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk", "target_clips": 1, "min_duration_seconds": 5, "max_duration_seconds": 8, "captions": "srt", "heatmap": "ignore"})
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
            self.models = SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text=json.dumps(next(replies)), usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30, total_token_count=150)))
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
    status = service.call('highlight_status', {'job_id': job['id']})
    assert status['ok'] and status['usage']['total_tokens'] == 300
    assert status['usage']['reported_calls'] == 2
    assert status['dashboard_path'].endswith('dashboard.html')
