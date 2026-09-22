import json
import subprocess
import pytest
from highlight_mcp.core import Service, Settings
from highlight_mcp.worker import worker


def test_render_requires_whole_story_review(prepared):
    service, job = prepared
    clip = {'start_seconds':0,'end_seconds':6,'title_th':'test','reason_th':'test','categories':['highlight'],'topic_id':'topic1','opening_reason':'The question establishes context.','ending_reason':'The answer completes the exchange.'}
    result=service.call('highlight_render',{'job_id':job,'clips':[clip]})
    assert not result['ok']
    story=service.call('highlight_story',{'job_id':job})
    assert story['ok'] and not story['coverage_complete']


def test_full_read_includes_context_before_requested_start(prepared):
    service,job=prepared
    request=service.store.get(job)['request']
    request['options']['start_seconds']=6
    service.store.update(job,request=request)
    page=service.call('highlight_transcript',{'job_id':job})
    assert page['ok'] and page['segments'][0]['start']==0


def test_cannot_skip_pages_or_save_story_early(prepared):
    service,job=prepared
    assert not service.call('highlight_transcript',{'job_id':job,'cursor':'1'})['ok']
    service.call('highlight_transcript',{'job_id':job,'limit':1})
    status=service.call('highlight_story',{'job_id':job})
    assert status['delivered_segments']==1 and not status['coverage_complete']
    story={'summary':'The whole episode concerns a question followed by a complete answer.','participants':['two speakers'],'topics':[{'topic_id':'one','start_seconds':0,'end_seconds':12,'setup':'A question opens the scene.','resolution':'An answer closes the scene.','significance':'The answer explains the dispute.','evidence_quote':'first'}],'uncertainties':[]}
    assert not service.call('highlight_story',{'job_id':job,'story':story})['ok']


def test_story_and_context_are_invalidated_by_changes(prepared):
    service,job=prepared
    story_id=save_review(service,job)
    story=service.call('highlight_story',{'job_id':job})['story']
    story['topics'][0]['evidence_quote']='invented quote'
    assert not service.call('highlight_story',{'job_id':job,'story':story})['ok']
    story['topics'][0]['evidence_quote']='first'
    story['summary']+=' Additional context changes the interpretation.'
    saved=service.call('highlight_story',{'job_id':job,'story':story})
    assert saved['ok'] and saved['story_id']!=story_id
    clip={'topic_id':'topic1','start_seconds':0,'end_seconds':6,'title_th':'test','reason_th':'test','categories':['highlight'],'opening_reason':'The question gives context.','ending_reason':'The answer resolves the exchange.'}
    for identifier in (story_id,saved['story_id']):
        result=service.call('highlight_render',{'job_id':job,'story_id':identifier,'clips':[clip]})
        assert not result['ok']
    path=service.settings.root/job/'transcript.json'
    path.write_text(json.dumps([{'start':0,'end':12,'text':'changed transcript'}]))
    status=service.call('highlight_story',{'job_id':job})
    assert not status['coverage_complete'] and status['story_id'] is None


def save_review(service, job):
    args={'job_id':job}
    while True:
        page=service.call('highlight_transcript',args)
        assert page['ok'],page
        if page['next_cursor'] is None:break
        args['cursor']=page['next_cursor']
    duration=service.store.get(job)['duration']
    story={'summary':'A participant asks about the dispute and the other person gives a complete response.', 'participants':['Participant one and participant two'], 'topics':[{'topic_id':'topic1','start_seconds':0,'end_seconds':duration,'setup':'The first speaker asks the question.','resolution':'The second speaker gives the answer.','significance':'This exchange resolves the central dispute.','evidence_quote':'first'}], 'uncertainties':[]}
    result=service.call('highlight_story',{'job_id':job,'story':story})
    assert result['ok'],result
    for boundary in (0,6,7,180,200,301):
        if boundary>duration:continue
        a,b=max(0,boundary-15),min(duration,boundary+15)
        context=service.call('highlight_transcript',{'job_id':job,'context_start_seconds':a,'context_end_seconds':b})
        assert context['ok'],context
    return result['story_id']


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
    request={'job_id':job,'story_id':save_review(service,job),'clips':[{'start_seconds':0,'end_seconds':6,'title_th':'test','reason_th':'dialogue','categories':['highlight'],'topic_id':'topic1','opening_reason':'The question establishes context.','ending_reason':'The answer completes the exchange.'}]}
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
    revised = service.call('highlight_revise', {'job_id':render['job_id'], 'clip_id':clip['clip_id'], 'expected_revision':1,'story_id':service.store.get(job)['story_review']['story_id'],'topic_id':'topic1', 'start_seconds':1, 'end_seconds':7})
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


def test_context_query_and_required_editorial_reasons(prepared):
    service,job=prepared
    page=service.call('highlight_transcript',{'job_id':job,'context_start_seconds':6,'context_end_seconds':12})
    assert page['ok'] and [r['text'] for r in page['segments']]==['second']
    assert not service.call('highlight_transcript',{'job_id':job,'context_start_seconds':6})['ok']
    missing=service.call('highlight_render',{'job_id':job,'clips':[{'start_seconds':0,'end_seconds':6,'title_th':'test','reason_th':'test','categories':['highlight']}]})
    assert not missing['ok']


def test_user_ceiling_applies_to_selection_and_revision(prepared):
    service,job=prepared
    request=service.store.get(job)['request']
    request['options']['max_duration_seconds']=300
    service.store.update(job,request=request,duration=400)
    clip={'start_seconds':0,'end_seconds':180,'title_th':'complete exchange','reason_th':'complete topic','categories':['highlight'],'topic_id':'topic1','opening_reason':'The question establishes the topic.','ending_reason':'The response completes the topic.'}
    result=service.call('highlight_render',{'job_id':job,'story_id':save_review(service,job),'clips':[clip]})
    assert result['ok'],result
    rendered=service.store.get(result['job_id'])
    assert rendered['request']['options']['max_duration_seconds']==300
    service.store.update(result['job_id'],state='completed',duration=400,source_job=job,clips=[{**clip,'clip_id':'clip_1','revision':1}])
    revision=service.call('highlight_revise',{'job_id':result['job_id'],'clip_id':'clip_1','expected_revision':1,'story_id':service.store.get(job)['story_review']['story_id'],'topic_id':'topic1','start_seconds':0,'end_seconds':200})
    assert revision['ok'],revision
    invalid=service.call('highlight_revise',{'job_id':result['job_id'],'clip_id':'clip_1','expected_revision':1,'story_id':service.store.get(job)['story_review']['story_id'],'topic_id':'topic1','start_seconds':0,'end_seconds':301})
    assert not invalid['ok']
    override=service.call('highlight_revise',{'job_id':result['job_id'],'clip_id':'clip_1','expected_revision':1,'story_id':service.store.get(job)['story_review']['story_id'],'topic_id':'topic1','start_seconds':0,'end_seconds':301,'max_duration_seconds':360})
    assert override['ok'],override


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
    result=service.call('highlight_render',{'job_id':job,'clips':[{'start_seconds':a,'end_seconds':b,'title_th':'test','reason_th':'test','categories':[category],'opening_reason':'The question establishes context.','ending_reason':'The answer completes the exchange.'}]})
    assert not result['ok']
    assert len(service.store.all())==1
