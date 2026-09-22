from highlight_mcp.recovery import recovery_plan, recovery_action

def test_auth_recovery_preserves_state_and_stops_duplicate_fallback():
    plan = recovery_plan({'state':'failed','stage':'ingest','error':'YouTube requires sign-in verification','youtube_access':'mweb_po_failed'})
    assert plan['cause']=='youtube_authentication'
    text=recovery_action(plan)
    assert 'already failed' in text and 'authorization' in text and 'Continue independent' in text


def test_rate_limit_is_not_immediate_retry():
    plan=recovery_plan({'state':'failed','stage':'ingest','error':'rate-limited'})
    assert plan['cause']=='rate_limited' and 'Do not retry immediately' in recovery_action(plan)


def test_render_failure_and_cancel_are_not_download_recovery():
    assert recovery_plan({'state':'failed','stage':'render'}) is None
    assert recovery_plan({'state':'cancelled','stage':'ingest'}) is None


def test_real_status_and_results_return_recovery(tmp_path,monkeypatch):
    from highlight_mcp.core import Service,Settings
    monkeypatch.setenv('HIGHLIGHT_DATA_DIR',str(tmp_path))
    service=Service(Settings(),launch=False)
    created=service.call('highlight_create',{'url':'https://youtu.be/abcdefghijk'})
    job=created['job_id']
    service.store.update(job,state='failed',stage='ingest',error='YouTube requires sign-in verification')
    for tool in ('highlight_status','highlight_results'):
        response=service.call(tool,{'job_id':job})
        assert response['ok'],response
        assert 'INGEST RECOVERY' in response['next_action']
    assert service.store.get(job)['recovery_plan']['cause']=='youtube_authentication'
