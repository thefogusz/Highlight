from types import SimpleNamespace
import pytest
from highlight_mcp.core import Settings, Store
from highlight_mcp.transcription import transcribe_chunks


def test_resume_skips_saved_chunks_and_keeps_absolute_times(tmp_path):
    settings = Settings(tmp_path)
    store = Store(tmp_path)
    job, _ = store.submit({}, {})
    folder = tmp_path / job['id']; folder.mkdir()
    source = folder / 'source.mp4'; source.write_bytes(b'fixture')
    calls = []
    class Model:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, path, **kwargs):
            calls.append(path)
            if len(calls) == 2: raise RuntimeError('interrupted')
            return iter([SimpleNamespace(start=3, end=8, text='test')]), None
    def command(*args): pass
    with pytest.raises(RuntimeError):
        transcribe_chunks(settings, store, job['id'], source, 240, lambda: None, command, Model)
    assert store.get(job['id'])['transcription']['completed_seconds'] == 120
    result = transcribe_chunks(settings, store, job['id'], source, 240, lambda: None, command, Model)
    assert len(calls) == 3
    assert [r['start'] for r in result] == [3, 121]
    assert store.get(job['id'])['transcription']['completed_seconds'] == 240


def test_cancel_does_not_save_incomplete_chunk(tmp_path):
    settings = Settings(tmp_path); store = Store(tmp_path)
    job, _ = store.submit({}, {})
    folder = tmp_path / job['id']; folder.mkdir()
    source = folder / 'source.mp4'; source.write_bytes(b'fixture')
    class Model:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs):
            def segments():
                yield SimpleNamespace(start=0,end=12,text='partial')
                raise RuntimeError('cancelled')
            return segments(), None
    with pytest.raises(RuntimeError):
        transcribe_chunks(settings,store,job['id'],source,120,lambda:None,lambda *args:None,Model)
    assert not list(folder.glob('asr_*/*.json'))
