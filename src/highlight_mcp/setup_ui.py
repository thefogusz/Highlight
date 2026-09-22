"""A local form; credentials never travel through an agent tool call."""
import json
import threading
import tkinter as tk
from tkinter import ttk
import keyring
from .core import Settings


def setup():
    settings = Settings()
    window = tk.Tk()
    window.title("Highlight — API Settings")
    window.geometry("660x390")
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Highlight MCP · Gemini", font=("Segoe UI", 18)).pack(anchor="w")
    ttk.Label(frame, text="API key: saved in Windows Credential Manager, never in the repository.").pack(anchor="w", pady=(15, 4))
    key = tk.StringVar()
    ttk.Entry(frame, textvariable=key, show="●", width=75).pack(fill="x")
    ttk.Label(frame, text="Leave blank to keep the saved key. Environment GEMINI_API_KEY takes priority.").pack(anchor="w")
    ttk.Label(frame, text="Gemini model ID (load models, then select a video-capable model):").pack(anchor="w", pady=(16, 4))
    model = tk.StringVar(value=settings.model or "")
    models = ttk.Combobox(frame, textvariable=model, width=70)
    models.pack(fill="x")
    status = tk.StringVar(value="API key is not configured." if not settings.key()[0] else "A key is configured. Model/video access still needs verification.")
    ttk.Label(frame, textvariable=status, wraplength=600).pack(anchor="w", pady=16)
    def load_models():
        token = key.get().strip() or settings.key()[0]
        if not token:
            status.set("Enter an API key first.")
            return
        status.set("Checking model access…")
        def work():
            try:
                from google import genai
                from google.genai import types
                with genai.Client(api_key=token, http_options=types.HttpOptions(timeout=30000)) as client:
                    names = [m.name.removeprefix("models/") for m in client.models.list() if "generateContent" in (m.supported_actions or [])]
                def done():
                    models["values"] = names
                    status.set("Key accepted. Select a Gemini video-capable model; listing alone does not test video analysis.")
                window.after(0, done)
            except Exception:
                window.after(0, lambda: status.set("Could not list models. Check the API key and network. No key details are logged."))
        threading.Thread(target=work, daemon=True).start()
    def save():
        try:
            if key.get().strip():
                keyring.set_password("Highlight", "gemini", key.get().strip())
                key.set("")
            config = {**settings.config, "model": model.get().strip() or None}
            settings.config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
            status.set("Saved. Ask the agent to call highlight_settings, then retry your job.")
        except Exception:
            status.set("Could not save settings. Check Windows Credential Manager and directory permissions.")
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="w")
    ttk.Button(buttons, text="Load available models", command=load_models).pack(side="left", padx=(0, 10))
    ttk.Button(buttons, text="Save settings", command=save).pack(side="left")
    window.mainloop()
