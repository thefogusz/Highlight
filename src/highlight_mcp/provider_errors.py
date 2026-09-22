"""Allowlisted diagnostics: never persist provider messages or request contents."""
import json
import httpx
from google.genai.errors import APIError
from .core import Failure


def provider_failure(exc):
    if isinstance(exc, APIError):
        status = exc.code
        kind, message = {
            400: ('PROVIDER_REQUEST_INVALID', 'Provider rejected the request; check model capabilities and parameters.'),
            401: ('PROVIDER_AUTH_FAILED', 'Check the API key in Highlight Settings.'),
            403: ('PROVIDER_AUTH_FAILED', 'Access denied; check key restrictions and project permissions.'),
            404: ('PROVIDER_MODEL_UNAVAILABLE', 'Model or resource unavailable; refresh model selection in Highlight Settings.'),
            429: ('PROVIDER_RATE_LIMITED', 'Rate limit or quota reached; check provider quota before retrying. This does not prove free credits are exhausted.'),
        }.get(status, ('PROVIDER_UNAVAILABLE', 'Provider service failed.') if isinstance(status, int) and status >= 500 else ('PROVIDER_OUTCOME_UNKNOWN', 'Provider outcome is unknown.'))
        # Only a numeric HTTP status is safe to expose.
        label = str(status) if type(status) is int else 'unknown'
        return Failure(kind, f'HTTP {label}: {message} No automatic retry was made.')
    if isinstance(exc, json.JSONDecodeError):
        return Failure('MODEL_OUTPUT_INVALID', 'Provider returned invalid JSON. Usage may have been charged; no automatic retry was made.')
    if isinstance(exc, httpx.TimeoutException):
        return Failure('PROVIDER_OUTCOME_UNKNOWN', 'Provider request timed out. Billing outcome is unknown; no automatic retry was made.')
    if isinstance(exc, httpx.TransportError):
        return Failure('PROVIDER_OUTCOME_UNKNOWN', 'Network connection failed. Billing outcome is unknown; no automatic retry was made.')
    return Failure('PROVIDER_OUTCOME_UNKNOWN', 'Provider outcome is unknown. No automatic retry was made; credentials and response contents are not logged.')
