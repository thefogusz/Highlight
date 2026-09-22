"""Provider-reported usage only; no inference of account quota or billing tier."""
from datetime import datetime, timezone
from html import escape
import os
import tempfile


def record_usage(job, metadata, model):
    usage = dict(job.get('usage', {}))
    fields = {'input_tokens': 'prompt_token_count', 'output_tokens': 'candidates_token_count',
              'thinking_tokens': 'thoughts_token_count', 'total_tokens': 'total_token_count'}
    total = getattr(metadata, 'total_token_count', None)
    if type(total) is not int or total < 0:
        return usage
    for label, field in fields.items():
        value = getattr(metadata, field, None)
        previous = usage.get(label, 0 if not usage.get('reported_calls') else None)
        # Once a response omits a component, its cumulative total is unknown.
        # Keeping the old subtotal would make an incomplete breakdown look exact.
        usage[label] = (previous + value
                        if type(value) is int and value >= 0 and previous is not None
                        else None)
    usage['reported_calls'] = usage.get('reported_calls', 0) + 1
    usage['last_model'] = model
    usage['updated_at'] = datetime.now(timezone.utc).isoformat()
    return usage


def summarize(job):
    usage = job.get('usage') or {}
    calls = job.get('provider_calls', 0)
    reported = usage.get('reported_calls', 0)
    return {**{k: usage.get(k) for k in ('input_tokens', 'output_tokens', 'thinking_tokens', 'total_tokens')},
            'attempted_calls': calls, 'reported_calls': reported,
            'unreported_calls': max(0, calls - reported), 'local_call_limit': 30,
            'google_remaining': None, 'cost_usd': None,
            'last_model': usage.get('last_model'), 'updated_at': usage.get('updated_at')}


def render_dashboard(root, job):
    data = summarize(job)
    states = {'queued': 'รอเริ่มงาน', 'running': 'กำลังทำงาน', 'completed': 'เสร็จแล้ว',
              'partial': 'ได้คลิปบางส่วน', 'failed': 'งานหยุด — ต้องตรวจสอบ',
              'cancelled': 'ยกเลิกแล้ว', 'interrupted': 'งานสะดุด',
              'waiting_for_configuration': 'รอติดตั้งเครื่องมือ', 'waiting_for_budget': 'รอปรับงบ'}
    stages = {'ingest': 'เตรียมวิดีโอ', 'transcribe': 'ถอดเสียงในเครื่อง',
              'discover': 'หาช่วงน่าสนใจ', 'inspect': 'ตรวจภาพและเสียง',
              'render': 'ตัดคลิป', 'verify': 'ตรวจไฟล์', 'preflight': 'ตรวจความพร้อม'}
    esc = lambda value: escape(str(value or ''))
    number = lambda value: f'{value:,}' if value is not None else 'ยังไม่ทราบ'
    count = data['attempted_calls']
    transcription = job.get('transcription')
    asr = ''
    if transcription:
        done, total = transcription['completed_seconds'], transcription['total_seconds']
        asr = (f'<p>ถอดเสียงและบันทึกแล้ว <b>{done/60:.1f} / {total/60:.1f} นาที</b></p>'
               f'<progress value="{done}" max="{max(1, total)}" aria-label="ความคืบหน้าการถอดเสียง"></progress>'
               '<small>บันทึกทุก 2 นาทีของวิดีโอ หากงานหยุดจะเริ่มต่อจากช่วงที่บันทึกแล้ว</small>')
    error = job.get('error') or ''
    error_message = ('งานเดิมหยุดเพราะข้อจำกัดความยาว — อัปเดตแล้ว ให้สั่งลองงานเดิมอีกครั้ง'
                     if 'two hours' in error else 'งานหยุดก่อนเสร็จ ให้ agent ตรวจสาเหตุด้านล่าง')
    notice = (f'<p class="notice">{error_message}</p><details><summary>รายละเอียดสำหรับตรวจสอบ</summary><p>{esc(error)}</p></details>'
              if error else '<p class="muted">ถอดเสียงและตัดไฟล์ในเครื่อง ไม่เรียก API โมเดล</p>')
    updated = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')
    cards = ''.join(f'<div class="metric"><span>{title}</span><strong>{number(data[key])}</strong></div>'
                    for title, key in [('โทเคนรวมที่รายงาน', 'total_tokens'), ('ข้อมูลส่งเข้า', 'input_tokens'),
                                       ('คำตอบ', 'output_tokens'), ('การคิดของโมเดล', 'thinking_tokens')])
    html = f'''<!doctype html><html lang="th"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="5"><title>Highlight · สถานะงาน</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#12131a;color:#f4f3f8;font:16px/1.65 'Segoe UI',Tahoma,sans-serif}}
main{{max-width:780px;margin:40px auto;padding:24px}}header{{display:flex;justify-content:space-between;align-items:center;gap:16px}}
h1{{font-size:28px;margin:0}}.muted,small{{color:#b5b6c7}}.panel{{background:#1d1e29;border:1px solid #333544;border-radius:18px;padding:24px;margin-top:20px}}
h2{{font-size:20px;margin:0 0 8px}}.badge{{background:#363049;color:#ded0ff;padding:6px 12px;border-radius:20px;font-size:14px}}
.row{{display:flex;justify-content:space-between;gap:16px}}progress{{width:100%;height:16px;accent-color:#ae8bff;margin:12px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:24px}}.metric span{{display:block;color:#b5b6c7;font-size:14px}}strong{{font-size:26px}}
.notice{{border-left:3px solid #c3a35d;padding-left:14px;color:#e2d2b5}}footer{{margin-top:20px;font-size:12px;color:#9698ad;overflow-wrap:anywhere}}
@media(max-width:480px){{main{{margin:0;padding:16px}}header{{align-items:flex-start;flex-direction:column}}.panel{{padding:18px}}strong{{font-size:22px}}}}
</style><main><header><div><h1>Highlight</h1><div class="muted">การใช้ API · เฉพาะงานนี้</div></div>
<span class="badge">{esc(states.get(job.get('state'), 'ยังไม่ทราบสถานะ'))}</span></header>
<section class="panel"><h2>{esc(stages.get(job.get('stage'), 'สถานะงาน'))}</h2>
<div class="muted">ได้คลิปแล้ว {len(job.get('clips', []))} คลิป</div>
{asr}
<div class="row" style="margin-top:24px"><span>เรียก AI ไปแล้ว</span><b>{count} / 30 ครั้ง</b></div>
<progress value="{min(count, 30)}" max="30" aria-label="จำนวนครั้งที่เรียก AI จากเพดานงาน"></progress>
<small>เพดานต่อหนึ่งงานของ Highlight — ไม่ใช่โควตาฟรีหรือเปอร์เซ็นต์งานสำเร็จ</small>
<div class="grid">{cards}</div>
<p class="muted">ได้รับตัวเลขการใช้จาก API แล้ว {data['reported_calls']} จาก {count} ครั้ง</p>
<small>ครั้งที่ยังไม่มีรายงานอาจกำลังทำงาน ล้มเหลว หรือเป็นงานก่อนอัปเดต ตัวเลขรวมอาจยังไม่ครบ</small></section>
<section class="panel"><div class="row"><b>โควตา Google คงเหลือ</b><b>ยังไม่ทราบ</b></div>
<p class="muted">โควตาใช้ร่วมทั้งโปรเจกต์ รวมแอปอื่นด้วย จึงคำนวณจากงานนี้อย่างเดียวไม่ได้</p>
<a style="color:#c6aaff" href="https://aistudio.google.com/usage" target="_blank" rel="noreferrer">ดูการใช้และโควตาใน Google AI Studio ↗</a>
<p class="muted">ค่าใช้จ่าย: ยังไม่คำนวณ — ยังไม่ได้ยืนยันแพ็กเกจและอัตราของบัญชี</p></section>
{notice}
<footer>โมเดลที่รายงานล่าสุด: {esc(data['last_model'] or 'ยังไม่มีรายงาน')}<br>อัปเดตข้อมูล: {esc(updated)}<br>
{esc(job['id'])} · หน้านี้อ่านไฟล์ซ้ำทุก 5 วินาที ข้อมูลเปลี่ยนเมื่อ worker หรือ agent บันทึกสถานะ</footer></main></html>'''
    if not job.get('usage'):
        state = {'awaiting_selection': 'รอ Agent เลือกช่วง', 'queued': 'รอทำงาน', 'running': 'กำลังทำงาน', 'completed': 'เสร็จแล้ว', 'partial': 'สำเร็จบางส่วน', 'failed': 'ไม่สำเร็จ', 'cancelled': 'ยกเลิก'}.get(job.get('state'), job.get('state'))
        html = f'''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="5"><title>Highlight</title><style>body{{background:#12131a;color:#f4f3f8;font:18px/1.7 'Segoe UI',sans-serif;max-width:720px;margin:40px auto;padding:24px}}section{{background:#1d1e29;padding:24px;border-radius:16px}}small{{color:#b5b6c7}}</style><h1>Highlight</h1><section><h2>{esc(state)}</h2><p>ได้คลิปแล้ว {len(job.get('clips', []))} คลิป</p>{asr}<p>ใช้ Agent ในแชทเลือกช่วง · ไม่ต้องมี API key</p><small>โควตาและค่าใช้จ่าย Agent ดูจากแอปที่ใช้ MCP อ่านยอดคงเหลือไม่ได้</small>{notice}</section></html>'''
    folder = root / job['id']
    folder.mkdir(exist_ok=True)
    path = folder / 'dashboard.html'
    fd, temporary = tempfile.mkstemp(dir=folder, suffix='.html.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(html)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
