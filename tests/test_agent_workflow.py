import json
import subprocess
import pytest
from highlight_mcp.core import Service, Settings
from highlight_mcp.worker import worker


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setenv('HIGHLIGHT_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    service = Service(Settings(tmp_path), launch=False)
    created = service.call('highlight_create', {'url': 'https://youtu.be/abcdefghijk', 'min_duration_seconds': 5, 'target_clips': 2, 'heatmap': 'ignore', 'captions': 'srt'})
    assert created['ok'] and created['state'] == 'queued'
    folder = tmp_path / created['job_id']
    folder.mkdir()
    subprocess.run([service.settings.binary('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10', '-t', '12', '-c:v', 'libx264', str(folder/'source.mp4')], check=True)
    (folder/'metadata.json').write_text(json.dumps({'duration':12, 'is_live':False,'heatmap':[]}))
    (folder/'transcript.json').write_text(json.dumps([{'start':0,'end':6,'text':'first'}, {'start':6,'end':12,'text':'second'}]))
    worker()
    assert service.store.get(created['job_id'])['state'] == 'awaiting_selection'
    return service, created['job_id']


def test_keyless_prepare_select_render_and_idempotency(prepared):
    service, job = prepared
    assert service.call('highlight_settings', {})['provider'] == 'agent'
    status = service.call('highlight_status', {'job_id':job})
    assert status['ok'] and status['poll_after_seconds'] == 0
    first = service.call('highlight_transcript', {'job_id':job,'limit':1})
    assert first['ok'] and first['next_cursor'] == '1'
    second = service.call('highlight_transcript', {'job_id':job,'cursor':'1'})
    assert second['segments'][0]['text'] == 'second' and second['next_cursor'] is None
    request={'job_id':job,'clips':[{'start_seconds':0,'end_seconds':6,'title_th':'test','reason_th':'dialogue','categories':['highlight']}]}
    render=service.call('highlight_render',request)
    assert render['ok'],render
    assert service.call('highlight_render',request)['job_id']==render['job_id']
    worker()
    result=service.call('highlight_results',{'job_id':render['job_id']})
    assert result['ok'] and result['job_state']=='completed',result
    clip=result['clips'][0]
    assert clip['end_seconds']-clip['start_seconds']==6
    assert clip['evidence'][0]['source']=='transcript'
    assert len(clip['artifacts'])==2
    assert service.store.get(render['job_id']).get('provider_calls',0)==0
    revised = service.call('highlight_revise', {'job_id':render['job_id'], 'clip_id':clip['clip_id'], 'expected_revision':1, 'start_seconds':1, 'end_seconds':7})
    assert revised['ok'], revised
    worker()
    revision = service.call('highlight_results', {'job_id':revised['job_id']})
    assert revision['ok'] and revision['clips'][0]['start_seconds']==1
    assert revision['clips'][0]['end_seconds']==7


def test_prepared_retry_does_not_restart_and_cancel_blocks_selection(prepared):
    service, job=prepared
    retry=service.call('highlight_retry',{'job_id':job})
    assert retry['ok'] and retry['state']=='awaiting_selection'
    service.call('highlight_cancel',{'job_id':job})
    assert not service.call('highlight_transcript',{'job_id':job})['ok']


def test_pagination_preserves_rows_with_soft_character_cap(prepared):
    service, job=prepared
    path=service.settings.root/job/'transcript.json'
    rows=[{'start':i,'end':i+1,'text':str(i)+'x'*4000} for i in range(10)]
    path.write_text(json.dumps(rows),encoding='utf-8')
    collected=[]
    args={'job_id':job,'limit':100}
    while True:
        page=service.call('highlight_transcript',args)
        assert page['ok'],page
        assert len(page['segments'])<=2
        collected.extend(page['segments'])
        if page['next_cursor'] is None: break
        args['cursor']=page['next_cursor']
    assert collected==rows


@pytest.mark.parametrize('a,b,category', [(0,61,'highlight'),(10,20,'highlight'),(0,6,'most_replayed')])
def test_invalid_agent_selections_never_queue(prepared,a,b,category):
    service,job=prepared
    result=service.call('highlight_render',{'job_id':job,'clips':[{'start_seconds':a,'end_seconds':b,'title_th':'test','reason_th':'test','categories':[category]}]})
    assert not result['ok']
    assert len(service.store.all())==1
