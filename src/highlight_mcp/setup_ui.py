"""Local masked setup. Worker threads never read or write Tk widgets."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk
import keyring
from .core import Settings
from .model_selection import discover_models


class SetupForm:
    def __init__(self, window):
        self.window = window
        self.settings = Settings()
        self.events = queue.Queue()
        self.options = []
        self.busy = False
        self.checked_token = None
        window.title('Highlight — ตั้งค่าแบบง่าย')
        window.geometry('680x510')
        window.minsize(620, 500)
        frame = ttk.Frame(window, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Highlight', font=('Segoe UI', 22)).pack(anchor='w')
        ttk.Label(frame, text='ใส่ API key แล้วให้ระบบเลือกโมเดลที่เหมาะให้').pack(anchor='w', pady=(0, 18))
        ttk.Label(frame, text='Gemini API key').pack(anchor='w')
        self.key = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.key, show='●')
        self.entry.pack(fill='x', pady=6)
        existing, source = self.settings.key()
        hint = 'มี key บันทึกอยู่แล้ว เว้นช่องว่างเพื่อใช้ key เดิม' if existing else 'เก็บ key ใน Windows Credential Manager ไม่ส่งเข้าแชต'
        if source == 'environment':
            hint = 'ใช้ key จากการตั้งค่า Codex อยู่แล้ว ไม่ต้องกรอกซ้ำ'
            self.entry.configure(state='disabled')
        ttk.Label(frame, text=hint, wraplength=610).pack(anchor='w')
        self.choice = ttk.Frame(frame)
        ttk.Label(self.choice, text='โมเดลที่เหมาะกับงานนี้ — เลือกตัวแนะนำไว้ให้แล้ว').pack(anchor='w', pady=(12, 4))
        self.combo = ttk.Combobox(self.choice, state='readonly')
        self.combo.pack(fill='x')
        self.combo.bind('<<ComboboxSelected>>', self.show_model)
        self.model_note = tk.StringVar(value='เลือกโมเดลอัตโนมัติเมื่อบันทึก')
        ttk.Label(frame, textvariable=self.model_note, wraplength=610).pack(anchor='w', pady=(16, 4))
        self.status = tk.StringVar(value='พร้อมตั้งค่า' if not existing else 'กดบันทึกได้เลย ระบบจะตรวจ key และเลือกโมเดลให้')
        ttk.Label(frame, textvariable=self.status, wraplength=610).pack(anchor='w', pady=12)
        self.buttons = ttk.Frame(frame)
        self.buttons.pack(anchor='w', pady=8)
        self.save_button = ttk.Button(self.buttons, text='บันทึกและพร้อมใช้งาน', command=lambda: self.request(True))
        self.save_button.pack(side='left', padx=(0, 12))
        self.check_button = ttk.Button(self.buttons, text='ดูตัวเลือกโมเดล', command=lambda: self.request(False))
        self.check_button.pack(side='left')
        ttk.Label(frame, text='การตั้งค่าตรวจรายชื่อโมเดลเท่านั้น การวิเคราะห์และค่า API เริ่มเมื่อสั่งตัดคลิป', wraplength=610).pack(anchor='w', pady=12)
        self.key.trace_add('write', self.invalidate)
        self.poll_id = window.after(100, self.poll)

    def invalidate(self, *_):
        self.checked_token = None
        self.options = []
        self.choice.pack_forget()
        self.model_note.set('เลือกโมเดลอัตโนมัติเมื่อบันทึก')

    def show_model(self, *_):
        index = self.combo.current()
        if 0 <= index < len(self.options):
            self.model_note.set('โมเดล: ' + self.options[index])

    def request(self, save):
        if self.busy:
            return
        env_key = os.getenv('GEMINI_API_KEY')
        entered = self.key.get().strip()
        token = env_key or entered or self.settings.key()[0]
        if not token:
            self.status.set('กรอก Gemini API key ก่อนครับ')
            return
        preferred = os.getenv('HIGHLIGHT_MODEL') or None
        if not preferred and token == self.checked_token and self.options:
            preferred = self.options[max(0, self.combo.current())]
        self.busy = True
        self.entry.configure(state='disabled')
        self.combo.configure(state='disabled')
        self.save_button.configure(state='disabled')
        self.check_button.configure(state='disabled')
        self.status.set('กำลังตรวจ key และคัดโมเดลที่รองรับวิดีโอ…')
        def work():
            try:
                selected, options = discover_models(token, preferred)
                if save:
                    if entered and not env_key:
                        keyring.set_password('Highlight', 'gemini', entered)
                    fresh = Settings()
                    config = {**fresh.config, 'model': selected}
                    temporary = fresh.config_file.with_suffix('.tmp')
                    temporary.write_text(json.dumps(config, indent=2), encoding='utf-8')
                    temporary.replace(fresh.config_file)
                self.events.put(('success', (selected, options, token, save)))
            except ValueError as exc:
                self.events.put(('error', str(exc)))
            except Exception:
                self.events.put(('error', 'บันทึกไม่สำเร็จ กรุณาตรวจ Credential Manager และสิทธิ์โฟลเดอร์'))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            kind, payload = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.entry.configure(state='disabled' if os.getenv('GEMINI_API_KEY') else 'normal')
            self.save_button.configure(state='normal')
            self.check_button.configure(state='normal')
            if kind == 'error':
                self.invalidate()
                self.status.set(payload)
            else:
                selected, options, token, saved = payload
                if saved:
                    self.key.set('')
                    self.settings = Settings()
                self.options, self.checked_token = options, token
                self.combo['values'] = [f"{'ใช้งานทั่วไป' if 'flash' in m else 'ตัวเลือก Pro'} — {m}" + (' (แนะนำ)' if i == 0 else '') for i, m in enumerate(options)]
                self.combo.current(options.index(selected))
                self.combo.configure(state='readonly' if not os.getenv('HIGHLIGHT_MODEL') else 'disabled')
                if len(options) > 1:
                    self.choice.pack(fill='x', before=self.buttons)
                else:
                    self.choice.pack_forget()
                self.model_note.set(('เลือกให้อัตโนมัติ: ' if len(options) == 1 else 'โมเดล: ') + selected)
                self.status.set('บันทึกแล้ว เปิด task ใหม่แล้วสั่ง “ใช้ Highlight” พร้อมลิงก์ YouTube ได้เลย' if saved else 'เลือกตัวแนะนำให้แล้ว กดบันทึกได้เลย')
        self.poll_id = self.window.after(100, self.poll)


def setup():
    window = tk.Tk()
    SetupForm(window)
    window.mainloop()
