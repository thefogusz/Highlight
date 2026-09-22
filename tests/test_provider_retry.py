import pytest
from google.genai.errors import ServerError, ClientError
from highlight_mcp.core import Failure
from highlight_mcp.provider_errors import generate_with_retry


def test_503_recovers_and_reports_waits():
    calls, waits, notices = [], [], []
    def invoke():
        calls.append(1)
        if len(calls) < 3:
            raise ServerError(503, {})
        return 'ok'
    assert generate_with_retry(invoke, lambda: None, notices.append, sleep=waits.append) == 'ok'
    assert len(calls) == 3 and len(notices) == 2
    assert 30 <= sum(waits) <= 34


def test_503_stops_after_three_attempts():
    calls = []
    def invoke():
        calls.append(1)
        raise ServerError(503, {})
    with pytest.raises(Failure, match='3 attempts'):
        generate_with_retry(invoke, lambda: None, lambda _: None, sleep=lambda _: None)
    assert len(calls) == 3


@pytest.mark.parametrize('error', [ClientError(429, {}), TimeoutError(), Failure('BUDGET_EXCEEDED', 'limit')])
def test_other_errors_are_not_retried(error):
    calls = []
    def invoke():
        calls.append(1)
        raise error
    with pytest.raises(type(error)):
        generate_with_retry(invoke, lambda: None, lambda _: None, sleep=lambda _: None)
    assert len(calls) == 1


def test_cancel_during_backoff_prevents_next_attempt():
    calls = []
    def invoke():
        calls.append(1)
        raise ServerError(503, {})
    def check():
        if calls:
            raise InterruptedError()
    with pytest.raises(InterruptedError):
        generate_with_retry(invoke, check, lambda _: None, sleep=lambda _: None)
    assert len(calls) == 1
