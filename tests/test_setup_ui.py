import json
import time
import tkinter as tk
from types import SimpleNamespace
import pytest
from highlight_mcp import setup_ui


@pytest.fixture(scope='module')
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def form(tmp_path, monkeypatch, tk_root):
    monkeypatch.setenv('HIGHLIGHT_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('HIGHLIGHT_DISABLE_KEYRING', '1')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('HIGHLIGHT_MODEL', raising=False)
    window = tk.Toplevel(tk_root)
    window.withdraw()
    instance = setup_ui.SetupForm(window)
    yield instance
    window.after_cancel(instance.poll_id)
    window.destroy()


def wait(form):
    deadline = time.monotonic() + 5
    while form.busy and time.monotonic() < deadline:
        form.window.update()
        time.sleep(.01)
    assert not form.busy


def test_one_click_saves_auto_model_without_secret_in_config(form, monkeypatch):
    stored = []
    monkeypatch.setattr(setup_ui, 'discover_models', lambda token, preferred: ('gemini-3.8-flash', ['gemini-3.8-flash']))
    monkeypatch.setattr(setup_ui.keyring, 'set_password', lambda *args: stored.append(args))
    form.key.set('synthetic-secret')
    form.request(True)
    wait(form)
    config = form.settings.config_file.read_text()
    assert json.loads(config)['model'] == 'gemini-3.8-flash'
    assert 'synthetic-secret' not in config
    assert len(stored) == 1 and form.key.get() == ''
    assert form.choice.winfo_manager() == ''


def test_multiple_models_preselect_recommended_then_preserve_choice(form, monkeypatch):
    options = ['gemini-3.8-flash', 'gemini-2.5-pro']
    monkeypatch.setattr(setup_ui, 'discover_models', lambda token, preferred: (preferred or options[0], options))
    monkeypatch.setattr(setup_ui.keyring, 'set_password', lambda *args: None)
    form.key.set('synthetic-secret')
    form.request(False)
    wait(form)
    assert form.combo.current() == 0 and form.choice.winfo_manager() == 'pack'
    assert not form.settings.config_file.exists()
    form.combo.current(1)
    form.request(True)
    wait(form)
    assert form.settings.model == 'gemini-2.5-pro'


def test_failed_lookup_never_writes_key_or_settings(form, monkeypatch):
    def failed(*args):
        raise ValueError('Lookup failed')
    monkeypatch.setattr(setup_ui, 'discover_models', failed)
    monkeypatch.setattr(setup_ui.keyring, 'set_password', lambda *args: pytest.fail('Must not save failed key'))
    form.key.set('synthetic-secret')
    form.request(True)
    wait(form)
    assert not form.settings.config_file.exists()
    assert form.status.get() == 'Lookup failed'
    assert str(form.save_button['state']) == 'normal'


def test_editing_key_invalidates_old_model_choices(form, monkeypatch):
    monkeypatch.setattr(setup_ui, 'discover_models', lambda *args: ('gemini-3.8-flash', ['gemini-3.8-flash']))
    form.key.set('first')
    form.request(False)
    wait(form)
    form.key.set('second')
    assert not form.options and form.checked_token is None


@pytest.mark.parametrize('symbol', ['v', 'V', 'Thai_oang'])
def test_control_v_uses_physical_key_on_windows(form, monkeypatch, symbol):
    events = []
    monkeypatch.setattr(setup_ui.os, 'name', 'nt')
    monkeypatch.setattr(form.entry, 'event_generate', lambda event: events.append(event))
    assert form.control_key(SimpleNamespace(keycode=86, keysym=symbol)) == 'break'
    assert events == ['<<Paste>>']


def test_other_control_keys_keep_native_behavior(form, monkeypatch):
    monkeypatch.setattr(form.entry, 'event_generate', lambda event: pytest.fail('Unexpected paste'))
    assert form.control_key(SimpleNamespace(keycode=65, keysym='a')) is None


def test_control_v_does_not_paste_while_disabled(form, monkeypatch):
    form.entry.configure(state='disabled')
    monkeypatch.setattr(form.entry, 'event_generate', lambda event: pytest.fail('Unexpected paste'))
    assert form.control_key(SimpleNamespace(keycode=86, keysym='v')) == 'break'
