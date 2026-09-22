import json
import pytest
from google.genai.errors import ClientError
from highlight_mcp.provider_errors import provider_failure


@pytest.mark.parametrize('status,code', [(400, 'PROVIDER_REQUEST_INVALID'), (401, 'PROVIDER_AUTH_FAILED'), (403, 'PROVIDER_AUTH_FAILED'), (404, 'PROVIDER_MODEL_UNAVAILABLE'), (429, 'PROVIDER_RATE_LIMITED'), (503, 'PROVIDER_UNAVAILABLE')])
def test_safe_provider_classification(status, code):
    error = ClientError(status, {'error': {'message': 'SECRET_KEY prompt content'}})
    failure = provider_failure(error)
    assert failure.code == code
    assert 'SECRET_KEY' not in str(failure)
    assert str(status) in str(failure)


def test_invalid_json_is_distinct_from_unknown_network_outcome():
    assert provider_failure(json.JSONDecodeError('bad', '', 0)).code == 'MODEL_OUTPUT_INVALID'
    assert provider_failure(RuntimeError('SECRET_KEY')).code == 'PROVIDER_OUTCOME_UNKNOWN'
