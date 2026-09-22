# Highlight MCP

ออกแบบระบบให้ Agent รับลิงก์ YouTube แล้วคัดไฮไลต์ ประเด็นสำคัญ ช่วงตลก และช่วงดูซ้ำสูง ออกมาเป็นวิดีโอพร้อมเวลาต้นฉบับ

> **สถานะ: Design package — ยังไม่มี MCP server หรือ video pipeline ที่รันได้**
> ชุดนี้มีสเปก สัญญาเครื่องมือ ตัวอย่างตั้งค่า และตัวตรวจสัญญาแบบ offline การผ่านตัวตรวจไม่ใช่ผลทดสอบการตัดคลิปหรือความแม่นยำภาษาไทย

## ประสบการณ์ที่ต้องการ

หลังติดตั้ง runtime ในอนาคตและตั้งค่า key ครั้งเดียว ผู้ใช้พิมพ์:

> ใช้ Highlight กับ https://www.youtube.com/watch?v=VIDEO_ID เอาช่วงตลกและประเด็นสำคัญ ตัดให้เลย

Agent เรียก `highlight_create` → ได้ `job_id` → ใช้ `highlight_status` → `highlight_results` → ส่ง MP4 และภาพตัวอย่างกลับมา ผู้ใช้สั่งต่อว่า “คลิป 2 เพิ่มก่อนหน้า 10 วินาที” ผ่าน `highlight_revise` ได้

`@Highlight` เป็น UX ของแอป Agent ไม่ใช่ความสามารถที่ MCP รับประกัน ทุก host ใช้การเรียก tool ได้ แต่การแสดง @, การเล่นวิดีโอ และการแจ้งเมื่อเสร็จต้องทดสอบกับ host จริง ไม่ต้องใช้ @ ก็สั่งว่า “ใช้ Highlight” ได้

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

- รุ่นแรกใช้ `GEMINI_API_KEY` ฝั่งเครื่องที่รัน worker
- key ตั้งผ่าน environment ของ MCP host ได้ หรือผ่าน local settings wizard ที่จะพัฒนา
- wizard เก็บ key ใน OS credential store; MCP ส่งกลับเพียง configured/valid/invalid/unknown ไม่คืนค่า key
- yt-dlp, faster-whisper, FFmpeg ไม่ต้องมี API key
- API วิเคราะห์จะได้รับช่วงวิดีโอและข้อความที่เลือก; การรันบนเครื่องไม่ได้หมายความว่าไม่มีข้อมูลออกไปยัง provider
- ตัวอย่างใน [examples](examples) เป็น **template หลังพัฒนา runtime** ไม่ใช่คำสั่งติดตั้งที่ใช้งานได้วันนี้

## ตรวจชุดออกแบบตอนนี้

ต้องมี Python 3.11+; คำสั่ง PowerShell จากโฟลเดอร์ repo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-design.txt
.venv\Scripts\python.exe scripts/check_design.py
git diff --check
```

ไม่มีคำสั่ง build/start runtime ในรุ่นนี้ ไม่ดาวน์โหลดวิดีโอ ไม่เรียก Gemini และไม่ใช้ key ระหว่างตรวจชุดออกแบบ
