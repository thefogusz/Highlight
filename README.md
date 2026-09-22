# Highlight MCP 0.3 — ไม่ต้องมี API key

วางลิงก์ YouTube ให้ Codex, Claude หรือ agent ที่รองรับ MCP แล้วได้ MP4 แยกคลิปละไม่เกิน 60 วินาทีโดยค่าเริ่มต้น (ปรับได้ตามผู้ใช้) MCP เตรียมข้อมูลและตัดไฟล์ ส่วนโมเดลในแชทวิเคราะห์ ไม่มีการเรียก Gemini ใน worker

## ติดตั้ง

ต้องมี Python 3.11+, FFmpeg/ffprobe และ Node.js สำหรับ YouTube บางคลิป Whisper ทำงานในเครื่องและอาจดาวน์โหลดโมเดลครั้งแรก ไม่ต้องมีคีย์

```powershell
git clone https://github.com/thefogusz/Highlight.git
cd Highlight
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m highlight_mcp doctor
```

ตั้ง MCP host ให้เรียก Python ใน venv ด้วย arguments `-m highlight_mcp serve` ดู [JSON](examples/mcp.config.json) และ [Codex](examples/codex.config.toml) เปลี่ยน path ให้ตรงเครื่อง ไม่ต้องมี API environment variables หลังอัปเดตต้อง reconnect MCP หรือปิดเปิดแอปเพื่อโหลด tools ใหม่

คีย์เก่าใน credential store จะไม่ถูกอ่านหรือใช้งาน และไม่ถูกลบอัตโนมัติ คำสั่ง `setup` แสดง readiness เช่นเดียวกับ `doctor` ไม่มีหน้ากรอก key

## ใช้งาน

`@Highlight https://www.youtube.com/watch?v=...`

ค่าเริ่มต้นเลือกจำนวนตามคุณภาพ ไม่บังคับครบ 8 คลิป 5–60 วินาที 16:9 เปลี่ยนเป็นแนวตั้งหรือขอ SRT ได้ ลิงก์ `t=574s` เลือกตั้งแต่ 9:34 จนจบ ส่ง `start_seconds: 0` เพื่อเลือกทั้งคลิป

1. `highlight_create` เตรียมวิดีโอ ดึงซับไทยคนทำก่อน แล้วซับไทยอัตโนมัติ หากใช้ไม่ได้จึงเรียก Whisper
2. `highlight_status` รอจน `awaiting_selection` จากนั้นหยุด poll
3. `highlight_transcript` อ่านทีละหน้าให้ครบ เก็บบันทึกเรื่องราวก่อน ยังไม่เลือกไฮไลต์ แล้วบันทึก `highlight_story` ให้ครบก่อนเลือกช่วง
4. Agent บันทึกช่วงเด่นเรียงอันดับ อ่านบริบทรอบจุดตัด และตรวจภาพ/เสียงจาก `highlight_preview` ก่อนส่ง `highlight_render`
5. รอ **render job ที่คืนมา** แล้วอ่าน `highlight_results` เพื่อแสดง MP4/SRT

การส่ง selection เดิมซ้ำไม่สร้างงานตัดซ้ำ ใช้ `highlight_revise` แก้คลิปที่ตัดแล้ว

## โมเดลและโทเคน

อ่าน [แผนงานประหยัดโทเคน](docs/AGENT_WORKFLOW.md) MCP เปลี่ยนโมเดล host เองไม่ได้และอ่านโควตาคงเหลือไม่ได้ การใช้ agent ยังคงนับโควตาของ Codex/Claude งานดาวน์โหลด/ถอดเสียง/ตัดไฟล์ไม่ต้องเรียก chat model

## ข้อจำกัด

- วิดีโอต้องจบแล้ว ไม่เกิน 6 ชั่วโมง และยังเข้าถึงได้ มีข้อจำกัดพื้นที่/ขนาดไฟล์
- Heatmap อาจไม่มี ไม่ใช่จำนวนผู้ชมจริง
- เลือกจากซับไม่เท่ากับตรวจภาพและเสียง ต้องใช้เครื่องมือ media ของ host ตรวจจริง
- `verification: verified` หมายถึง FFmpeg ตรวจการ decode และ duration ไม่ใช่รับรองความตลก หลักฐานจะระบุ transcript อย่างตรงไปตรงมา
- งานที่เตรียมพร้อมต้องมี agent เลือก ไม่ได้วิเคราะห์เองเมื่อ host ปิดอยู่
- งานเก่าอ่านผลได้; retry จะใช้ local preparation/agent selection ไม่เรียก Gemini

## ทดสอบ

```powershell
python -m pip install pytest
python -m pytest -q
python scripts/check_design.py
```

Tests ครอบคลุม MCP stdio, keyless preparation, pagination, validation, idempotency, MP4/SRT และ revision จริง คุณภาพมุกไทยยังต้องตรวจเนื้อหาจริง เอกสารรุ่น 0.1 ที่เหลือเป็นประวัติ ให้ยึด README และ AGENT_WORKFLOW รุ่น 0.2


## Context-first boundaries

The requested maximum (default 60 seconds) is a ceiling, never a target. Do not fill the time or force every clip near one minute. Select a complete meaningful moment first: setup then punchline, question then answer, claim then response/consequence. Read 15–30 seconds of surrounding context for shortlisted boundaries. End before the next unfinished topic begins. A deliberate cliffhanger must be understandable and meaningful, not a dangling fragment. Supply opening_reason and ending_reason to highlight_render. The default 5-second minimum is technical, not an editorial target. If a complete exchange cannot fit, choose another moment. Transcript-based timing remains approximate; verify speech/reaction with actual media tools when available.

ผู้ใช้ขอ “คลิปละไม่เกิน 5 นาที” ให้ agent ส่ง `max_duration_seconds: 300` โดยไม่เปลี่ยนค่าเริ่มต้นของงานอื่น `highlight_revise` รับค่า override นี้ได้เช่นกัน หากไม่ส่งจะใช้เพดานของงานเดิม ทุกช่วงยังต้องอยู่ภายในวิดีโอต้นฉบับและจบใจความ ไม่ใช่เติมให้ครบเวลาที่ตั้งไว้


## Whole-story gate (current)

Output start/focus ranges restrict clips, not understanding: full-video transcript delivery is mandatory. Sequential page receipts are persisted against the transcript hash. Before selection, save `highlight_story` with people, a narrative summary, topic setup, resolution (or explicitly unresolved), importance, real supporting quotes, and uncertainty. Each clip references current `story_id` and `topic_id`. After saving, read at least 15 seconds around both clip boundaries through context queries; complete every context page. Changing the transcript invalidates reading/story receipts; changing the map invalidates boundary receipts. All revisions, including historical clips, require current story_id/topic_id from the source preparation job and context reads around the new boundaries. Re-prepare a legacy source if its transcript is missing. Receipts prove data delivery and procedural compliance, NOT comprehension or correct audio timing. Rolling caption endpoints are not speech endpoints. Use local word timing/media evidence near selected boundaries; choose another complete exchange if closure is uncertain.


### Background research

Before preparation, the host agent researches the exact video topic using its existing web tools and passes a compact, sourced `background_research` brief to `highlight_create`. Facts, reporting and opinion stay separate; missing browsing or matching sources must be recorded explicitly. No extra API key is needed. Older jobs may attach the brief when saving `highlight_story`. Story saving and rendering require this record, but the MCP cannot independently verify that the host actually browsed or understood the sources. Full-video transcript review and boundary checks remain required.


### YouTube fallback and comment research

An optional local bgutil 2.0.0 helper can be configured with `youtube_po_provider_home` pointing to its server directory. `scripts/setup_youtube_provider.py` provides a pinned installer requiring Git, Node >=22 and npm. An eligible metadata failure gets at most one alternate mweb attempt. The successful client is retained for download and subtitles. This does not guarantee access: the real DOM9gelySKc probe still returned sign-in verification with mweb and web_safari. No account cookies are read.

Research may store up to 12 observed timestamped comments with text, source links and visible likes (null when unknown). These guide inspection only after full-video reading. Missing comments do not block selection.


### Agent download recovery
If built-in ingestion fails, the host agent can acquire the full source with an available supported tool and return it to the same job through `highlight_retry.acquired_source`. This preserves options and research; the server checks duration, minimum 720p, audio and full decoding before resuming. Video identity is verified by the host agent. This handoff does not guarantee that another downloader can access a blocked YouTube video.


### Optional Chrome connection (Windows preview)
The local companion extension can hand off the existing YouTube session without reading Chrome cookie databases. Setup and limits: [Browser connection](docs/BROWSER_CONNECTION.md). It requires one-time browser installation and consent; it has been tested on the previously failing video DOM9gelySKc (1080p with audio), but is not published to the Chrome Web Store.


## Enforced workflow in 0.4

The user still supplies only the link. The host agent researches the exact video: new `highlight_create` calls require `background_research`. Record unavailable browsing honestly with a reason. Legacy ingestion accepts the brief through `highlight_retry` without recreating the job.

Read the full transcript and save the whole story with an initial empty `candidate_moments` list. Then save ranked worthwhile moments. Zero is valid; no fixed quota. Each render/revision references a zero-based `candidate_index` and stays within that saved candidate. Updating the story or ledger invalidates boundary reads and previews; read boundary context again.

Call `highlight_preview` for the exact cut, surrounding context video and WAV audio. Inspect with host media tools, then supply `preview_id` and `editorial_review` observations of opening, ending, audiovisual cues and limitations. Only approved audiovisual review may render final clips. If media inspection is unavailable, keep a draft preview and explain the limitation; do not invent approval or add a paid model. Revised timestamps require fresh review. Receipts prove preparation, not that an agent watched. Editorial approval is host-reported, never a guarantee of comprehension or humor. `verification` remains a technical file check.

Thai subtitles precede Whisper. A gap over 30 seconds or under 60% merged time coverage makes a track suspect: try the next Thai track, then Whisper. This conservative talk-show heuristic may reject real silent passages and increase local transcription work; it does not prove every spoken word is covered.

For browser setup use `highlight_browser_setup` status/prepare, show its exact folder/steps, recheck after user consent and resume the same failed job. Do not restart cancelled jobs automatically.
