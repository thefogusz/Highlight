# Product specification — v0.1 design

## Objective

ผู้ใช้ที่ดูรายการไทยยาว 30–120 นาที ให้ Agent ค้นและตัดคลิปจากลิงก์เดียว โดยไม่ต้องกำหนด timestamp เอง ผลลัพธ์ทุกคลิปต้องตรวจย้อนกลับถึงต้นฉบับได้

Design assumptions: local single-user, Windows-first, stdio MCP, Gemini video analysis, faster-whisper Thai transcription, FFmpeg rendering, SQLite persistence. นี่เป็นข้อเสนอการออกแบบ ไม่ใช่ผล benchmark ภาษาไทย

## Scope

v1 รับ public YouTube video หนึ่งรายการต่อ job รวมลิงก์ watch, youtu.be, shorts และ live ที่จบและพร้อมเป็น VOD แล้ว; ไม่รับ playlist หรือ live ที่ยังออกอากาศ ดาวน์โหลดไม่ได้ให้คืนข้อผิดพลาดที่แก้ได้ ไม่ขอให้ Agent หาวิธีข้ามข้อจำกัด

Source URL parser ใช้ exact hostname allowlist ไม่ใช้ substring; canonicalize ด้วย video ID หลัง validation, ตัด tracking/query ที่ไม่เกี่ยวข้อง, ไม่ตีความ t= เป็นคำสั่งตัดเฉพาะช่วง ต้องใช้ focus_ranges เมื่ออยากจำกัดช่วง

ผลลัพธ์เป็น MP4, JPEG thumbnail, transcript excerpt, source timestamps, selection reasons, evidence and limitations. ผลรวมและคลิปต่อรายการแสดงใน local gallery ได้ ไม่มี auto-publish

Deferred: cloud/multi-user deployment, arbitrary file/URL intake, social publishing, dubbing, learned personal preferences, sophisticated face-tracked vertical reframing, cross-video search. ไม่สร้าง SaaS account/billing ในรุ่นแรก

## Default behavior

| Setting | Default / bound |
|---|---|
| language | th; เก็บคำพูดไทย ไม่แปลไปอังกฤษก่อนคัด |
| categories | highlight, important, funny, most_replayed |
| target_clips | 0 = automatic (default); 1–20 = explicit user maximum, never a quota |
| clip length | 30–60 s; configurable 5–60 s; separate clips, never concatenate |
| aspect | 16:9 original composition; 9:16 uses fit/pad initially |
| captions | off; optional SRT avoids double captions on TV footage |
| render | automatic, after analysis and boundary validation |
| heatmap | prefer; missing data triggers transcript/audio-visual fallback |
| context | initially -45/+30 s around candidate; expandable within source bounds |
| worker | one active job per data directory; queue other jobs |
| limit | source <= 120 min and <= 5 GB downloaded; disk preflight required |
| analysis budget | inspect <= 20 min of unique candidate video by default; explicit bounded expansion |
| retention | source/intermediate 7 days after terminal job; final outputs 30 days |

Budget is a workload cap, not a currency guarantee. Keep call/usage totals and provider model ID. Optional monetary ceiling requires a current versioned pricing table; otherwise cost_usd=null with an explanation. Never invent cost. Future provider models are configured, not hard-coded as “latest”.

“คนดูเยอะ” maps to most_replayed with a user-facing explanation: public heatmap is normalized replay intensity, not viewer counts. Missing heatmap is unknown, never zero. Scores from different videos are not globally comparable.

## Stories and acceptance IDs

- UX01: URL-only request queues an automatic job; defaults are returned so the Agent can explain what it will do.
- UX02: Thai free text refines a request; ambiguous secondary details use defaults rather than a questionnaire.
- UX03: cancel/status/results work without paying for another analysis.
- UX04: revise a clip by adjusting absolute source times; retain original and create new revision.
- UX05: key setup takes place in host settings or local wizard, never an MCP argument.
- UX06: no heatmap still yields candidates; result announces fallback.
- UX07: source/worker restart resumes safe checkpoints; duplicate calls do not create duplicate renders.
- UX08: when no defensible clips are found, return completed with empty results and reason; never fabricate success.
- UX09: playable files and verified boundaries are required before a clip is marked ready.

## Output quality

Clip structure: context/question → key statement/event → answer/reaction. Preserve corrections, denials and qualifications when omission changes meaning. Funny is an editorial label, not a fact; show observed cues and confidence. Do not infer inner feelings from faces. Do not present a guest's allegation as established fact in a title. First version cuts contiguous source ranges only.

A clip can have multiple labels but counts once toward target_clips. Per-category quotas are deferred; to request “5 funny + 3 important” Agent creates two explicitly requested jobs with shared cached assets, then reports overlaps. Do not silently interpret 8 total as 8 per label.

## Commands, structure and style

Today: run `python scripts/check_design.py` after installing requirements-design.txt. Future runtime layout and commands are in IMPLEMENTATION.md and clearly marked planned.

Current tree: docs/ specifications, contracts/ JSON Schemas, examples/ synthetic calls and templates, scripts/ design validator. Python checker uses pathlib, explicit validation errors and offline JSON Schema resolution. Future runtime uses typed models; no arbitrary shell commands or model-generated FFmpeg flags.

## Boundaries

Always validate source, ranges, provider JSON and filesystem paths; bound work and retries; report evidence level. Never commit secrets, automatically publish clips, or treat untrusted transcript/video text as instructions. Additional remote deployment/publishing requires a separate requested scope. Standard local processing proceeds under the user's request and configured spending limits.
