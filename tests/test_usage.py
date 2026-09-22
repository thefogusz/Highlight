from types import SimpleNamespace
from highlight_mcp.usage import record_usage, summarize, render_dashboard


def test_usage_includes_thinking_and_preserves_provider_total():
    job = {"provider_calls": 2}
    meta = SimpleNamespace(prompt_token_count=100, candidates_token_count=20,
                           thoughts_token_count=30, total_token_count=150)
    job['usage'] = record_usage(job, meta, 'test-model')
    result = summarize(job)
    assert result['total_tokens'] == 150
    assert result['thinking_tokens'] == 30
    assert result['reported_calls'] == 1
    assert result['unreported_calls'] == 1
    assert result['google_remaining'] is None


def test_old_jobs_do_not_claim_zero_tokens():
    assert summarize({'provider_calls': 3})['total_tokens'] is None


def test_missing_token_breakdown_never_displays_partial_sum_as_complete():
    job = {}
    job['usage'] = record_usage(job, SimpleNamespace(total_token_count=150,
        prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30), 'test')
    job['usage'] = record_usage(job, SimpleNamespace(total_token_count=200,
        prompt_token_count=120, candidates_token_count=80), 'test')
    assert job['usage']['total_tokens'] == 350
    assert job['usage']['thinking_tokens'] is None
    job['usage'] = record_usage(job, SimpleNamespace(total_token_count=150,
        prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30), 'test')
    assert job['usage']['thinking_tokens'] is None


def test_dashboard_write_failure_does_not_lose_job_update(tmp_path, monkeypatch):
    from highlight_mcp.core import Store
    from highlight_mcp import usage
    store = Store(tmp_path)
    job, _ = store.submit({'url': 'https://youtu.be/abcdefghijk'}, {})
    def denied(*args):
        raise PermissionError('File locked by preview')
    monkeypatch.setattr(usage, 'render_dashboard', denied)
    store.update(job['id'], state='completed')
    assert store.get(job['id'])['state'] == 'completed'


def test_dashboard_escapes_untrusted_values_and_labels_unknown(tmp_path):
    path = render_dashboard(tmp_path, {'id': 'job_test', 'state': 'failed',
                            'error': '<script>alert(1)</script>', 'provider_calls': 2})
    html = path.read_text(encoding='utf-8')
    assert '<script>' not in html
    assert 'MCP อ่านยอดคงเหลือไม่ได้' in html
    assert 'ไม่ต้องมี API key' in html
