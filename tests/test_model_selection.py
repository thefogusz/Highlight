from types import SimpleNamespace
import pytest
from highlight_mcp.model_selection import suitable_models, select_model


def model(name, actions=None):
    return SimpleNamespace(name='models/' + name, supported_actions=['generateContent'] if actions is None else actions)


def test_filters_unsupported_and_prefers_current_flash():
    rows = [model(n) for n in ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-3.8-flash-preview', 'gemini-live', 'imagen-4', 'gemini-3.1-flash-image', 'unknown-future-model']]
    assert suitable_models(rows) == ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-pro']


def test_keeps_reviewed_flash_fallbacks_in_preference_order():
    rows = [model(n) for n in ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-2.5-flash']]
    assert suitable_models(rows) == ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-2.5-flash']
    assert select_model(rows)[0] == 'gemini-3.6-flash'
    assert select_model(rows, 'gemini-3.8-flash')[0] == 'gemini-3.8-flash'


def test_single_model_selected_automatically():
    assert select_model([model('gemini-2.5-flash')]) == ('gemini-2.5-flash', ['gemini-2.5-flash'])


def test_requires_generate_content():
    assert suitable_models([model('gemini-3.8-flash', ['embedContent'])]) == []


def test_no_supported_model_fails_without_inventing_default():
    with pytest.raises(ValueError):
        select_model([model('imagen-4')])


def test_explicit_choice_is_respected_and_validated():
    rows = [model('gemini-3.8-flash'), model('gemini-2.5-pro')]
    assert select_model(rows, 'gemini-2.5-pro')[0] == 'gemini-2.5-pro'
    with pytest.raises(ValueError):
        select_model(rows, 'imagen-4')


def test_pinned_older_compatible_model_remains_available():
    selected, options = select_model([model('gemini-3.8-flash'), model('gemini-2.5-flash')], 'gemini-2.5-flash')
    assert selected == 'gemini-2.5-flash' and selected in options
