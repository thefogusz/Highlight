import json
from pathlib import Path
import pytest
from highlight_mcp.core import Service, Settings, Failure
from highlight_mcp.story_review import require_review
from highlight_mcp.subtitles import youtube_subtitles


def test_missing_research_never_creates_job(tmp_path):
    service = Service(Settings(tmp_path), launch=False)
    result = service.call('highlight_create', {'url': 'https://youtu.be/abcdefghijk'})
    assert not result['ok']
    assert service.store.all() == []


def test_caption_middle_gap_triggers_fallback(tmp_path):
    data = {'events': [{'tStartMs': a, 'dDurationMs': 5000, 'segs': [{'utf8': 'สวัสดีครับ'}]} for a in (0, 595000)]}
    def command(args, *rest):
        Path(args[args.index('-o')+1].replace('%(ext)s', 'th.json3')).write_text(json.dumps(data), encoding='utf-8')
    assert youtube_subtitles([], 'url', tmp_path, 600, lambda: None, command) == ([], 'fetch_failed_or_unusable')


def test_render_cannot_bypass_candidate_ledger():
    review = {'story_id': 'story', 'contexts': [[0,60]], 'story': {'background_research': {'status':'unavailable'}, 'topics': [{'topic_id':'one','start_seconds':0,'end_seconds':60}], 'candidate_moments': []}}
    with pytest.raises(Failure):
        require_review(review, 'story', [{'topic_id':'one','start_seconds':0,'end_seconds':10}], 60)


def test_preview_tool_is_exposed(tmp_path):
    from highlight_mcp.core import CATALOG
    assert 'highlight_preview' in CATALOG


@pytest.mark.parametrize('rows,expected', [
    ([{'start':0,'end':40},{'start':10,'end':50}],False),
    ([{'start':0,'end':40},{'start':50,'end':100}],True),
    ([{'start':0,'end':30},{'start':70,'end':100}],False),
])
def test_caption_coverage_uses_merged_intervals(rows, expected):
    from highlight_mcp.subtitles import usable_coverage
    assert usable_coverage(rows,100) == expected


def test_legacy_retry_requires_research_and_keeps_options(tmp_path):
    from workflow_support import OFFLINE_RESEARCH
    service = Service(Settings(tmp_path), launch=False)
    job_id = service.call('highlight_create', {'url':'https://youtu.be/abcdefghijk','background_research':OFFLINE_RESEARCH,'max_duration_seconds':300})['job_id']
    request = service.store.get(job_id)['request']
    request['background_research'] = None
    service.store.update(job_id,request=request,state='failed',stage='ingest')
    assert not service.call('highlight_retry',{'job_id':job_id})['ok']
    resumed = service.call('highlight_retry',{'job_id':job_id,'background_research':OFFLINE_RESEARCH})
    assert resumed['ok'] and resumed['job_id'] == job_id
    assert service.store.get(job_id)['request']['options']['max_duration_seconds'] == 300


@pytest.mark.parametrize('state', ['completed','running','awaiting_selection'])
def test_retry_does_not_mutate_research_in_active_or_complete_jobs(tmp_path,state):
    from workflow_support import OFFLINE_RESEARCH
    service=Service(Settings(tmp_path),launch=False)
    job_id=service.call('highlight_create',{'url':'https://youtu.be/abcdefghijk','background_research':OFFLINE_RESEARCH})['job_id']
    service.store.update(job_id,state=state)
    original=service.store.get(job_id)['request']
    from filelock import FileLock
    with FileLock(str(tmp_path / 'worker.lock')):
        service.call('highlight_retry',{'job_id':job_id,'background_research':{**OFFLINE_RESEARCH,'brief':'A different test brief should not be applied here.'}})
    assert service.store.get(job_id)['request']==original
