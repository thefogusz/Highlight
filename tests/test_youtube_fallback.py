import pytest
from highlight_mcp.core import Failure
from highlight_mcp.youtube import fetch_with_fallback


def test_recovered_client_used_for_subsequent_download():
    attempts, states = [], []
    def fetch(args):
        attempts.append(args)
        if args == ['default']:
            raise Failure('RENDER_FAILED', 'YouTube requires sign-in verification')
        return b'metadata'
    result, client = fetch_with_fallback(fetch, ['default'], ['mweb'], states.append)
    assert result == b'metadata' and client == ['mweb']
    assert len(attempts) == 2 and states[-1] == 'mweb_po_succeeded'


def test_fallback_does_not_loop():
    attempts, states = [], []
    def fetch(args):
        attempts.append(args)
        raise Failure('RENDER_FAILED', 'YouTube requires sign-in verification')
    with pytest.raises(Failure):
        fetch_with_fallback(fetch, ['default'], ['mweb'], states.append)
    assert len(attempts) == 2 and states[-1] == 'mweb_po_failed'


@pytest.mark.parametrize('message', ['restricted or unavailable', 'rate-limited', 'Temporary connection failure'])
def test_unrelated_errors_do_not_switch_clients(message):
    attempts=[]
    def fetch(args):
        attempts.append(args)
        raise Failure('RENDER_FAILED',message)
    with pytest.raises(Failure):
        fetch_with_fallback(fetch, ['default'], ['mweb'], lambda _: None)
    assert len(attempts)==1
