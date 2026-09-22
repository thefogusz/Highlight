from highlight_mcp.pipeline import youtube_failure

def test_signin_is_not_retried_or_reported_as_render_error():
    message, retry = youtube_failure("Sign in to confirm you're not a bot. secret URL")
    assert not retry and 'sign-in' in message and 'secret' not in message

def test_transient_retry_classification():
    assert youtube_failure('HTTP Error 503')[1]
    assert youtube_failure('Connection reset')[1]
    assert not youtube_failure('HTTP Error 429')[1]
    assert not youtube_failure('Private video')[1]


def test_schema_error_identifies_field_without_echoing_value(tmp_path, monkeypatch):
    from highlight_mcp.core import Service, Settings
    monkeypatch.setenv('HIGHLIGHT_DATA_DIR', str(tmp_path))
    result = Service(Settings(), launch=False).call('highlight_create', {'url':'https://youtu.be/abcdefghijk', 'target_clips':'secret'})
    assert not result['ok']
    assert 'target_clips' in result['error']['message']
    assert 'secret' not in str(result)
    assert 'Preserve' in result['next_action']


def test_command_retries_transient_once(tmp_path):
    import sys
    import pytest
    from highlight_mcp.pipeline import command
    from highlight_mcp.core import Failure
    count = tmp_path / 'attempts'
    script = "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text(p.read_text()+'x' if p.exists() else 'x'); sys.stderr.write('HTTP Error 503'); sys.exit(1)"
    with pytest.raises(Failure, match='Temporary YouTube'):
        command([sys.executable, '-c', script, str(count), 'yt_dlp'], lambda: None, 10)
    assert count.read_text() == 'xx'


def test_command_does_not_retry_signin(tmp_path):
    import sys
    import pytest
    from highlight_mcp.pipeline import command
    from highlight_mcp.core import Failure
    count = tmp_path / 'attempts'
    script = "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text(p.read_text()+'x' if p.exists() else 'x'); sys.stderr.write('Sign in to confirm'); sys.exit(1)"
    with pytest.raises(Failure, match='sign-in'):
        command([sys.executable, '-c', script, str(count), 'yt_dlp'], lambda: None, 10)
    assert count.read_text() == 'x'


def test_timestamp_comment_contract():
    from jsonschema import Draft202012Validator
    from highlight_mcp.core import CATALOG
    schema = CATALOG['highlight_create']['inputSchema']['properties']['background_research']['properties']['comment_signals']
    validator = Draft202012Validator(schema)
    signal = {'timestamp_seconds':574, 'text':'Interesting answer at 9:34', 'likes':42, 'url':'https://www.youtube.com/watch?v=abcdefghijk&lc=example'}
    assert not list(validator.iter_errors([signal]))
    assert not list(validator.iter_errors([{**signal,'likes':None}]))
    assert list(validator.iter_errors([{**signal,'likes':-1}]))
    assert list(validator.iter_errors([{**signal,'timestamp_seconds':-1}]))
