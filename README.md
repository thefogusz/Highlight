# Highlight MCP

ออกแบบระบบให้ Agent รับลิงก์ YouTube แล้วคัดไฮไลต์ ประเด็นสำคัญ ช่วงตลก และช่วงดูซ้ำสูง ออกมาเป็นวิดีโอพร้อมเวลาต้นฉบับ

> **สถานะ: Local alpha 0.1 — มี MCP server, worker, หน้าตั้งค่า และ pipeline แล้ว**
> ผ่านการทดสอบ MCP stdio และตัดวิดีโอจำลองจริง การเรียก Gemini และดาวน์โหลด YouTube จริงยังต้องทดสอบด้วย key/คลิปของผู้ใช้ ยังไม่รับรองความแม่นยำมุกไทย อ่านข้อจำกัดใน [Runtime](docs/RUNTIME.md)

## ประสบการณ์ที่ต้องการ

หลังติดตั้ง runtime และตั้งค่า key ครั้งเดียว ผู้ใช้พิมพ์:

> ใช้ Highlight กับ https://www.youtube.com/watch?v=VIDEO_ID เอาช่วงตลกและประเด็นสำคัญ ตัดให้เลย

Agent เรียก `highlight_create` → ได้ `job_id` → ใช้ `highlight_status` → `highlight_results` → ได้ path ไฟล์ MP4 ผู้ใช้สั่งต่อว่า “คลิป 2 เพิ่มก่อนหน้า 10 วินาที” ผ่าน `highlight_revise` ได้ รุ่นนี้ยังไม่มี gallery/ภาพตัวอย่าง

การติดตั้ง MCP อย่างเดียวอาจไม่ขึ้นในเมนู `@` ของ Codex หากต้องการเลือก `@Highlight` ให้ติดตั้ง [Codex plugin](integrations/codex/README.md) ซึ่งรวมชื่อ ไอคอน และ MCP ไว้ด้วยกัน การเล่นวิดีโอและการแจ้งเมื่อเสร็จขึ้นอยู่กับ host

## อ่านตามลำดับ

| เอกสาร | เนื้อหา |
|---|---|
| [Product specification](docs/SPEC.md) | ขอบเขต ค่าเริ่มต้น ความสำเร็จที่ตรวจวัดได้ |
| [Architecture](docs/ARCHITECTURE.md) | การคัดช่วง งานเบื้องหลัง การกู้คืน และการจัดเก็บ |
| [MCP contract](docs/MCP.md) | เครื่องมือ การเรียก ข้อผิดพลาด และข้อมูลผลลัพธ์ |
| [Settings and agent setup](docs/SETUP.md) | API key, Codex/host config และแบบหน้าตั้งค่า |
| [Implementation plan](docs/IMPLEMENTATION.md) | ลำดับพัฒนาและเกณฑ์ตรวจแต่ละขั้น |
| [Acceptance and evaluation](docs/ACCEPTANCE.md) | ทดสอบไฟล์จริงและประเมินภาษาไทย |
| [Sources and reuse](docs/SOURCES.md) | แหล่งอ้างอิงและการตัดสินใจเรื่อง repo |
| [Design review](docs/REVIEW.md) | ผลตรวจ ข้อจำกัด และสิ่งที่ยังไม่พิสูจน์ |
| [Tool schemas](contracts/tools.json) | input/output schema สำหรับ tools/list |

## การตั้งค่า API

### ดูสถานะและการใช้ API

สั่ง agent ว่า **“เปิดแผงสถานะ Highlight ของงานนี้”** โดย `highlight_status` คืน `dashboard_path` เป็น HTML ให้ host เปิดใน preview พร้อมข้อมูล `usage` สำหรับแสดงสรุปในแชต หน้าจอแสดงขั้นตอนงาน จำนวนคลิป จำนวนครั้งเรียก AI และโทเคนจริงที่ provider รายงาน รวม thinking tokens ข้อมูลอัปเดตเมื่อ worker บันทึกสถานะ และหน้า HTML โหลดไฟล์ใหม่ทุก 5 วินาที (การรีเฟรชใน preview ขึ้นอยู่กับ host)

หลอด 30 ครั้งเป็นเพดานเรียกโมเดลต่อหนึ่งงานของ Highlight ไม่ใช่โควตาบัญชี Google ไม่ใช่เปอร์เซ็นต์งานเสร็จ และไม่ใช่เพดานเงิน โควตาคงเหลือและค่าใช้จ่ายยังแสดง “ยังไม่ทราบ/ยังไม่คำนวณ” ไม่มีการเดาจากจำนวนโทเคน งานเก่าหรือคำขอที่ไม่มี usage metadata จะระบุว่าข้อมูลไม่ครบ ไม่รายงานเป็นศูนย์ หน้าจอไม่แสดง API key การเปิดหน้าจอไม่เรียก Gemini

รองรับวิดีโอที่จบแล้วความยาวไม่เกิน 6 ชั่วโมง ระบบปรับขนาดช่วงบทถอดเสียงตามความยาวและจำนวนคลิปที่ต้องการ เพื่อเผื่อการจัดอันดับและตรวจวิดีโอภายในเพดาน 30 model calls ต่อหนึ่งงาน (ไม่ใช่เพดานโทเคนหรือค่าใช้จ่าย) คลิปยาวยังใช้เวลาดาวน์โหลดและถอดเสียงในเครื่องมากขึ้น และยังมีข้อจำกัดพื้นที่/ขนาดไฟล์เดิม

บนเครื่องที่ติดตั้งทางลัดแล้ว กด Windows แล้วค้นหา **Highlight Settings** เพื่อเปิดหน้ากรอก key อีกครั้ง หรือรัน `.venv\Scripts\pythonw.exe -m highlight_mcp setup` จากโฟลเดอร์ที่ติดตั้ง อ่าน [ผลตรวจและแนวทางลดขั้นตอนตั้งค่า](docs/AUDIT.md)

- รุ่นแรกใช้ `GEMINI_API_KEY` ฝั่งเครื่องที่รัน worker
- key ตั้งผ่าน environment ของ MCP host ได้ หรือผ่าน local settings form: `python -m highlight_mcp setup`
- wizard เก็บ key ใน OS credential store; MCP ส่งกลับเพียง configured/valid/invalid/unknown ไม่คืนค่า key
- yt-dlp, faster-whisper, FFmpeg ไม่ต้องมี API key
- API วิเคราะห์จะได้รับช่วงวิดีโอและข้อความที่เลือก; การรันบนเครื่องไม่ได้หมายความว่าไม่มีข้อมูลออกไปยัง provider
- ตัวอย่างใน [examples](examples) ต้องแก้ path เป็นตำแหน่งติดตั้งจริง; ดูคำสั่งด้านล่าง

## ติดตั้งบน Windows

ต้องมี Python 3.11+, Git และ FFmpeg/ffprobe จากนั้นรันใน repo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m highlight_mcp setup
.venv\Scripts\python.exe -m highlight_mcp doctor
codex mcp add highlight -- (Resolve-Path .venv\Scripts\python.exe).Path -m highlight_mcp serve
```

กรอก Gemini key → กด **บันทึกและพร้อมใช้งาน** ระบบคัดโมเดลที่รองรับและเลือกตัวแนะนำให้อัตโนมัติ หากอยากเปลี่ยน กด **ดูตัวเลือกโมเดล** เพื่อเลือกระหว่าง Flash กับ Pro ที่ key นี้มองเห็น; หากมีเพียงตัวเดียวจะไม่แสดงช่องเลือก เปิด Codex task ใหม่เพื่อโหลด MCP คำว่า `@Highlight` ขึ้นอยู่กับ host; พิมพ์ “ใช้ Highlight” ได้

การโหลดรายชื่อโมเดลทดสอบสิทธิ์ key เท่านั้น ไม่ใช่ผลทดสอบวิเคราะห์วิดีโอ งานแรกดาวน์โหลด Whisper small อัตโนมัติและประมวลผล CPU อาจใช้เวลานาน เก็บงานที่ `%LOCALAPPDATA%\Highlight` ไม่ต้องเปิด terminal ค้างไว้

## ตรวจชุดออกแบบตอนนี้

ต้องมี Python 3.11+; คำสั่ง PowerShell จากโฟลเดอร์ repo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-design.txt
.venv\Scripts\python.exe scripts/check_design.py
git diff --check
```

ตรวจ runtime: `python -m pip install pytest` แล้ว `python -m pytest -q` ต้องมี FFmpeg การทดสอบใช้วิดีโอจำลองและ provider จำลอง ไม่เรียก API แบบเสียเงิน
