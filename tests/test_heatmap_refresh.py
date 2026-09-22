import pytest
from highlight_mcp.core import Failure
from highlight_mcp.pipeline import refresh_missing_heatmap


def test_refresh_preserves_source_metadata():
    old = {'duration': 8292, 'is_live': False, 'heatmap': None}
    fresh, state = refresh_missing_heatmap(old, lambda: {'heatmap': [{'start_time': 0, 'end_time': 10, 'value': .5}]})
    assert fresh['duration'] == 8292 and fresh['heatmap']
    assert state == 'available'


def test_missing_and_fetch_failure_are_distinct():
    old = {'heatmap': None}
    assert refresh_missing_heatmap(old, lambda: {'heatmap': None})[1] == 'not_returned'
    def failed():
        raise Failure('RENDER_FAILED', 'sensitive upstream detail')
    assert refresh_missing_heatmap(old, failed) == (old, 'fetch_failed')


def test_cancellation_is_not_swallowed():
    class Cancelled(Exception):
        pass
    def cancel():
        raise Cancelled()
    with pytest.raises(Cancelled):
        refresh_missing_heatmap({}, cancel)


def test_disk_guard_is_not_swallowed():
    def full():
        raise Failure('DISK_FULL', 'No space')
    with pytest.raises(Failure, match='No space'):
        refresh_missing_heatmap({}, full)
