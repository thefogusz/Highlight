from workflow_support import OFFLINE_RESEARCH
import os
import time
from pathlib import Path
import pytest
from highlight_mcp.core import Service, Settings
from highlight_mcp import browser_setup as setup


def test_packaged_extension_matches_source():
    root = Path(__file__).resolve().parents[1]
    for name in setup.FILES:
        assert (root / 'integrations/chrome' / name).read_bytes() == (root / 'src/highlight_mcp/chrome' / name).read_bytes()


@pytest.mark.skipif(os.name != 'nt', reason='Windows connector')
def test_status_does_not_install_and_stale_connection_is_not_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, 'registered', lambda _: False)
    service = Service(Settings(tmp_path), launch=False)
    result = service.call('highlight_browser_setup', {})
    assert result['ok'] and result['connection_state'] == 'setup_required'
    assert result['extension_path'] is None
    assert not (tmp_path / 'browser-bridge').exists()
    heartbeat = tmp_path / 'browser-connected'
    heartbeat.touch()
    assert service.call('highlight_browser_setup', {})['connection_state'] == 'connected'
    os.utime(heartbeat, (time.time()-60, time.time()-60))
    assert service.call('highlight_browser_setup', {})['connection_state'] == 'setup_required'


@pytest.mark.skipif(os.name != 'nt', reason='Windows connector')
def test_prepared_guide_and_job_preserved(tmp_path, monkeypatch):
    def fake_prepare(settings):
        folder = settings.root / 'browser-bridge/extension'
        folder.mkdir(parents=True)
        for name in setup.FILES:
            (folder / name).write_text('fixture')
    monkeypatch.setattr(setup, 'prepare', fake_prepare)
    monkeypatch.setattr(setup, 'registered', lambda _: True)
    service = Service(Settings(tmp_path), launch=False)
    job_id = service.call('highlight_create', {'background_research': OFFLINE_RESEARCH, **{'url':'https://youtu.be/abcdefghijk'}})['job_id']
    before = service.store.get(job_id)
    result = service.call('highlight_browser_setup', {'action':'prepare', 'job_id':job_id})
    assert result['ok'] and result['connection_state'] == 'not_connected'
    assert Path(result['extension_path']).is_absolute()
    assert any('Load unpacked' in step for step in result['steps'])
    (tmp_path / 'browser-connected').touch()
    result = service.call('highlight_browser_setup', {'job_id':job_id})
    assert job_id in result['next_action']
    assert 'cancelled' in result['next_action']
    assert service.store.get(job_id) == before


@pytest.mark.parametrize('offset,expected', [(0.5,True),(3600,False),(-60,False)])
def test_connection_clock_skew(tmp_path,offset,expected):
    from highlight_mcp.browser_bridge import connection_recent
    settings=Settings(tmp_path)
    heartbeat=tmp_path/'browser-connected'
    heartbeat.touch()
    stamp=time.time()+offset
    os.utime(heartbeat,(stamp,stamp))
    assert connection_recent(settings) == expected
