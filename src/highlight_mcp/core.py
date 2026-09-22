from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator, ValidationError

TOOLS = json.loads(Path(__file__).with_name("tools.json").read_text(encoding="utf-8"))["tools"]
CATALOG = {t["name"]: t for t in TOOLS}
TERMINAL = {"completed", "partial", "failed", "cancelled"}
MAX_SOURCE_SECONDS = 6 * 60 * 60


class Failure(Exception):
    def __init__(self, code, message, action="Correct the request and retry."):
        super().__init__(message)
        self.code, self.action = code, action


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def valid_range(start, end, duration):
    return all(type(x) in (int, float) and math.isfinite(x) for x in (start, end, duration)) and 0 <= start < end <= duration


def canonical_url(url):
    try:
        u = urlsplit(url)
        if u.scheme != "https" or u.username or u.password or u.port:
            raise ValueError()
        if u.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            raise ValueError()
        query = parse_qs(u.query)
        if "list" in query:
            raise ValueError()
        if u.hostname == "youtu.be":
            video = u.path.strip("/")
        elif u.path == "/watch" and len(query.get("v", [])) == 1:
            video = query["v"][0]
        elif re.fullmatch(r"/(shorts|live)/[\w-]{11}/?", u.path):
            video = u.path.split("/")[2]
        else:
            raise ValueError()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", video):
            raise ValueError()
        return f"https://www.youtube.com/watch?v={video}"
    except (ValueError, TypeError):
        raise Failure("INVALID_SOURCE", "Use one public HTTPS YouTube video link, without a playlist.") from None


class Settings:
    def __init__(self, root=None):
        default = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local"))) / "Highlight"
        self.root = Path(root or os.getenv("HIGHLIGHT_DATA_DIR", default)).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_file = self.root / "settings.json"
        self.config = json.loads(self.config_file.read_text(encoding="utf-8")) if self.config_file.exists() else {}

    @property
    def model(self):
        return os.getenv("HIGHLIGHT_MODEL") or self.config.get("model")

    def key(self):
        if os.getenv("GEMINI_API_KEY"):
            return os.environ["GEMINI_API_KEY"], "environment"
        if not os.getenv("HIGHLIGHT_DISABLE_KEYRING"):
            try:
                import keyring
                value = keyring.get_password("Highlight", "gemini")
                if value:
                    return value, "keyring"
            except Exception:
                pass
        return None, "none"

    def binary(self, name):
        explicit = self.config.get(name)
        if explicit and Path(explicit).is_file():
            return str(Path(explicit).resolve())
        found = shutil.which(name)
        if found:
            return found
        if os.name == "nt":
            base = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
            matches = sorted(base.glob(f"Gyan.FFmpeg*/**/{name}.exe"))
            if matches:
                return str(matches[-1])
        return None

    def public(self):
        key, source = self.key()
        missing = [name for name, valid in [("GEMINI_API_KEY", bool(key)), ("model", bool(self.model)), ("ffmpeg", bool(self.binary("ffmpeg"))), ("ffprobe", bool(self.binary("ffprobe")))] if not valid]
        return {"provider": "gemini", "model": self.model, "key_configured": bool(key), "key_source": source, "key_status": "unknown", "config_version": digest(self.config)[:16], "ready": not missing, "missing": missing}


class Store:
    def __init__(self, root):
        self.path = root / "jobs.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL,
                  created TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS request_keys (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise Failure("NOT_FOUND", "Job was not found.")
        return json.loads(row[0])

    def update(self, job_id, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise Failure("NOT_FOUND", "Job was not found.")
            data = json.loads(row[0])
            data.update(changes)
            db.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(data, ensure_ascii=False), job_id))
        return data

    def submit(self, request, config, request_key=None):
        fingerprint = digest({"request": request, "config": config, "pipeline": "0.1.0"})
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if request_key:
                prior = db.execute("SELECT fingerprint FROM request_keys WHERE key=?", (request_key,)).fetchone()
                if prior and prior[0] != fingerprint:
                    raise Failure("IDEMPOTENCY_CONFLICT", "This idempotency key belongs to another request.")
                db.execute("INSERT OR IGNORE INTO request_keys VALUES (?,?)", (request_key, fingerprint))
            existing = db.execute("SELECT payload FROM jobs WHERE fingerprint=?", (fingerprint,)).fetchone()
            if existing:
                return json.loads(existing[0]), True
            job = {"id": "job_" + uuid.uuid4().hex, "request": request, "created": now(), "state": "queued", "stage": None, "progress": None, "cancel_requested": False, "clips": [], "warnings": [], "duration": 0, "error": None}
            db.execute("INSERT INTO jobs VALUES (?,?,?,?)", (job["id"], fingerprint, job["created"], json.dumps(job, ensure_ascii=False)))
            return job, False

    def all(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM jobs ORDER BY created DESC,id DESC").fetchall()
        return [json.loads(row[0]) for row in rows]


class Service:
    def __init__(self, settings=None, launch=True):
        self.settings = settings or Settings()
        self.store = Store(self.settings.root)
        self.launch = launch

    def start_worker(self):
        if not self.launch:
            return
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == "nt" else {"start_new_session": True}
        env = {**os.environ, "HIGHLIGHT_DATA_DIR": str(self.settings.root)}
        subprocess.Popen([sys.executable, "-m", "highlight_mcp", "worker"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, **kwargs)

    def call(self, name, arguments):
        base = {"schema_version": "1.0", "ok": True, "warnings": [], "next_action": "none"}
        try:
            if name not in CATALOG:
                raise Failure("NOT_FOUND", "Unknown Highlight tool.")
            Draft202012Validator(CATALOG[name]["inputSchema"]).validate(arguments)
            value = self.dispatch(name, copy.deepcopy(arguments))
            result = {**base, **value}
            Draft202012Validator(CATALOG[name]["outputSchema"]).validate(result)
            return result
        except ValidationError:
            failure = Failure("INVALID_RANGE", "Arguments or response did not match the Highlight contract.")
        except Failure as exc:
            failure = exc
        except Exception:
            failure = Failure("INTERNAL_ERROR", "Highlight encountered a local error. No credential details are returned.", "Check local installation and retry.")
        return {**base, "ok": False, "next_action": failure.action, "error": {"code": failure.code, "message": str(failure), "retryable": False, "action": failure.action}}

    def dispatch(self, name, args):
        if name == "highlight_settings":
            return {**self.settings.public(), "next_action": "Run Highlight Settings to configure the provider if needed."}
        if name == "highlight_create":
            url = canonical_url(args.pop("url"))
            request_key = args.pop("idempotency_key", None)
            defaults = {k: copy.deepcopy(v["default"]) for k, v in CATALOG[name]["inputSchema"]["properties"].items() if "default" in v}
            opts = {**defaults, **args}
            if opts["max_duration_seconds"] < opts["min_duration_seconds"] or any(not valid_range(r["start_seconds"], r["end_seconds"], MAX_SOURCE_SECONDS) for r in opts["focus_ranges"]):
                raise Failure("INVALID_RANGE", "Duration or focus range is invalid.")
            job, reused = self.store.submit({"url": url, "options": opts}, {"model": self.settings.model}, request_key)
            if job["state"] == "queued" and not self.settings.public()["ready"]:
                job = self.store.update(job["id"], state="waiting_for_configuration")
            if job["state"] == "queued":
                self.start_worker()
            return {"job_id": job["id"], "state": job["state"], "reused": reused, "resolved_options": opts, "poll_after_seconds": 15, "next_action": "Run Highlight Settings, then highlight_retry." if job["state"] == "waiting_for_configuration" else "Poll highlight_status after 15 seconds."}
        if name == "highlight_jobs":
            jobs = [{"job_id": j["id"], "state": j["state"], "created_at": j["created"], "source_url": j["request"]["url"]} for j in self.store.all()]
            items, cursor = self.page(jobs, args)
            return {"jobs": items, "next_cursor": cursor}
        job = self.store.get(args["job_id"])
        if job["state"] == "running":
            from filelock import FileLock, Timeout
            try:
                with FileLock(str(self.settings.root / "worker.lock"), timeout=0):
                    # The worker may have finished since the initial status read.
                    job = self.store.get(job["id"])
                    if job["state"] == "running":
                        job = self.store.update(job["id"], state="interrupted", error="Worker stopped. Explicit retry is required.")
            except Timeout:
                pass
        if name == "highlight_status":
            warnings = job["warnings"] + ([job["error"]] if job["error"] else [])
            return {"job_id": job["id"], "state": job["state"], "stage": job["stage"], "progress": job["progress"], "cancel_requested": job["cancel_requested"], "poll_after_seconds": 0 if job["state"] in TERMINAL else 15, "warnings": warnings, "next_action": "Use highlight_results for available clips." if job["state"] in TERMINAL else "Wait or resolve configuration if requested."}
        if name == "highlight_results":
            for clip in job["clips"]:
                if any(not Path(a["path"]).is_file() for a in clip["artifacts"]):
                    raise Failure("ARTIFACT_EXPIRED", "One or more retained artifacts are missing.")
            clips, cursor = self.page(job["clips"], args)
            return {"job_id": job["id"], "job_state": job["state"], "source_url": job["request"]["url"], "source_duration_seconds": job["duration"], "clips": clips, "next_cursor": cursor, "warnings": job["warnings"]}
        if name == "highlight_cancel":
            if job["state"] not in TERMINAL:
                job = self.store.update(job["id"], cancel_requested=True, **({"state": "cancelled"} if job["state"] != "running" else {}))
            return {"job_id": job["id"], "state": job["state"], "cancel_requested": job["cancel_requested"]}
        if name == "highlight_retry":
            if job["state"] == "completed":
                raise Failure("INVALID_STATE", "Completed jobs are immutable; use highlight_revise.")
            if job["state"] in {"running", "queued"}:
                if job["state"] == "queued":
                    self.start_worker()
                return {"job_id": job["id"], "state": job["state"], "reused": True}
            if not job["request"].get("revision") and not self.settings.public()["ready"]:
                raise Failure("CONFIG_REQUIRED", "Provider or media tools are not configured.", "Run Highlight Settings, then retry.")
            self.store.update(job["id"], state="queued", cancel_requested=False, error=None)
            self.start_worker()
            return {"job_id": job["id"], "state": "queued", "reused": False, "warnings": ["Explicit retry may repeat a provider request whose outcome was unknown."]}
        if name == "highlight_revise":
            clip = next((c for c in job["clips"] if c["clip_id"] == args["clip_id"]), None)
            if not clip:
                raise Failure("NOT_FOUND", "Clip was not found.")
            if args["expected_revision"] != clip["revision"]:
                raise Failure("REVISION_CONFLICT", "Re-read the latest clip revision.")
            if not valid_range(args["start_seconds"], args["end_seconds"], job["duration"]):
                raise Failure("INVALID_RANGE", "Revision must stay within original source duration.")
            if not 5 <= args["end_seconds"] - args["start_seconds"] <= 300:
                raise Failure("INVALID_RANGE", "Revised clip must be 5–300 seconds.")
            source = self.settings.root / job.get("source_job", job["id"]) / "source.mp4"
            if not source.is_file():
                raise Failure("SOURCE_EXPIRED", "Original source is no longer available.")
            request = {**job["request"], "revision": {**args, "clip": clip, "source_job": job.get("source_job", job["id"])}}
            revision, reused = self.store.submit(request, {})
            self.start_worker()
            return {"job_id": revision["id"], "parent_job_id": job["id"], "clip_id": clip["clip_id"], "state": revision["state"], "reused": reused}
        raise Failure("NOT_FOUND", "Unknown operation.")

    @staticmethod
    def page(items, args):
        try:
            offset = int(args.get("cursor") or "0")
            if offset < 0:
                raise ValueError()
        except ValueError:
            raise Failure("INVALID_RANGE", "Invalid pagination cursor.") from None
        limit = args.get("limit", 20)
        end = offset + limit
        return items[offset:end], str(end) if end < len(items) else None
