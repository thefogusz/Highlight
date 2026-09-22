"""Reviewed video/audio + JSON models, intersected with API access.
Sources: https://ai.google.dev/gemini-api/docs/models/<model-id>, 2026-09-22.
Never infer modality support from generateContent alone.
"""
# Product baseline; a newer model must not displace it merely by version number.
FLASH = ('gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-2.5-flash')
PRO = ('gemini-2.5-pro',)


def available_models(models):
    return {m.name.removeprefix('models/') for m in models
            if m.name and 'generateContent' in (m.supported_actions or [])}


def suitable_models(models):
    available = available_models(models)
    # Keep every reviewed, API-visible fallback in preference order.  Selecting
    # only the first Flash model made a temporarily unavailable preferred model
    # hide viable Flash alternatives from the setup UI.
    return [model for family in (FLASH, PRO) for model in family if model in available]


def select_model(models, preferred=None):
    models = list(models)
    options = suitable_models(models)
    if preferred:
        if preferred not in FLASH + PRO or preferred not in available_models(models):
            raise ValueError('โมเดลที่กำหนดไว้ไม่อยู่ในรุ่นที่รองรับหรือ key นี้มองไม่เห็นโมเดลนั้น')
        if preferred not in options:
            options.append(preferred)
        return preferred, options
    if not options:
        raise ValueError('ไม่พบโมเดลที่รองรับ Highlight สำหรับ key นี้ กรุณาตรวจสิทธิ์ API หรืออัปเดต Highlight')
    return options[0], options


def discover_models(token, preferred=None):
    from google import genai
    from google.genai import types
    try:
        with genai.Client(api_key=token, http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
            models = list(client.models.list())
    except Exception:
        raise ValueError('เชื่อมต่อไม่ได้ กรุณาตรวจ API key และอินเทอร์เน็ต แล้วลองอีกครั้ง') from None
    return select_model(models, preferred)
