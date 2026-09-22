import json
import pytest

from highlight_mcp.core import Service, Settings, Failure, canonical_url, valid_range


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("HIGHLIGHT_DISABLE_KEYRING", "1")
    return Service(Settings(tmp_path), launch=False)


@pytest.mark.parametrize("url", ["https://youtube.com.evil.test/watch?v=abcdefghijk", "https://user@youtube.com/watch?v=abcdefghijk", "https://youtube.com:443/watch?v=abcdefghijk", "https://youtube.com/playlist?list=xx", "file:///tmp/a", "https://youtu.be/short"])
def test_reject_unsafe_sources(url):
    with pytest.raises(Failure):
        canonical_url(url)


def test_canonical_url_strips_tracking():
    assert canonical_url("https://youtu.be/abcdefghijk?t=30") == "https://www.youtube.com/watch?v=abcdefghijk"


def test_missing_key_is_actionable_and_durable(service):
    result = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    assert result["ok"] and result["state"] == "waiting_for_configuration"
    assert Service(service.settings, launch=False).call("highlight_jobs", {})["jobs"][0]["job_id"] == result["job_id"]


def test_duplicate_submission_reuses_job(service):
    a = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    b = service.call("highlight_create", {"url": "https://www.youtube.com/watch?v=abcdefghijk"})
    assert a["job_id"] == b["job_id"] and b["reused"]


def test_idempotency_conflict(service):
    service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk", "idempotency_key": "one"})
    result = service.call("highlight_create", {"url": "https://youtu.be/12345678901", "idempotency_key": "one"})
    assert result["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_invalid_duration_does_not_queue(service):
    result = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk", "min_duration_seconds": 100, "max_duration_seconds": 20})
    assert result["error"]["code"] == "INVALID_RANGE"
    assert service.call("highlight_jobs", {})["jobs"] == []


def test_cancel_is_idempotent(service):
    job = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    a = service.call("highlight_cancel", {"job_id": job["job_id"]})
    b = service.call("highlight_cancel", {"job_id": job["job_id"]})
    assert a == b and a["state"] == "cancelled"


def test_extra_secret_input_not_echoed(service):
    result = service.call("highlight_settings", {"api_key": "SECRET_TEST_VALUE"})
    assert not result["ok"]
    assert "SECRET_TEST_VALUE" not in json.dumps(result)


def test_setting_key_not_returned(service, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET_TEST_VALUE")
    result = service.call("highlight_settings", {})
    assert result["key_configured"]
    assert "SECRET_TEST_VALUE" not in json.dumps(result)


@pytest.mark.parametrize("start,end", [(0, 0), (-1, 2), (2, 1), (0, 61), (float('nan'), 2), (0, float('inf'))])
def test_temporal_guard(start, end):
    assert not valid_range(start, end, 60)


def test_boolean_model_timestamp_is_rejected():
    assert not valid_range(False, 30, 60)


def test_reused_failed_job_is_identified_as_historical(service):
    request = {'url': 'https://youtu.be/abcdefghijk'}
    created = service.call('highlight_create', request)
    service.store.update(created['job_id'], state='failed', error='old two hour limit')
    result = service.call('highlight_create', request)
    assert result['ok'] and result['reused']
    assert result['poll_after_seconds'] == 0
    assert 'highlight_retry' in result['next_action']
    assert 'earlier attempt' in result['warnings'][0]


def test_retry_restarts_stranded_queued_job(service, monkeypatch):
    job = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    service.store.update(job["job_id"], state="queued")
    launches = []
    monkeypatch.setattr(service, "start_worker", lambda: launches.append(True))
    result = service.call("highlight_retry", {"job_id": job["job_id"]})
    assert result["ok"] and result["reused"]
    assert launches == [True]


def test_status_does_not_overwrite_completion_during_lock_acquisition(service, monkeypatch):
    import filelock
    job = service.call("highlight_create", {"url": "https://youtu.be/abcdefghijk"})
    service.store.update(job["job_id"], state="running")

    class CompletingLock:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            service.store.update(job["job_id"], state="completed")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(filelock, "FileLock", CompletingLock)
    result = service.call("highlight_status", {"job_id": job["job_id"]})
    assert result["state"] == "completed"
