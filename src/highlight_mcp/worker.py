from filelock import FileLock, Timeout
import shutil
import time
from .core import Settings, Store, Failure
from .pipeline import run


class Cancelled(Exception):
    pass


def worker():
    settings = Settings()
    store = Store(settings.root)
    try:
        with FileLock(str(settings.root / "worker.lock"), timeout=60):
            for job in store.all():
                if job["state"] == "running":
                    store.update(job["id"], state="interrupted", error="Previous worker stopped. Explicit retry is required.")
            while True:
                jobs = [j for j in reversed(store.all()) if j["state"] == "queued"]
                if not jobs:
                    return
                for job in jobs:
                    if store.get(job["id"])["cancel_requested"]:
                        store.update(job["id"], state="cancelled")
                        continue
                    if not job["request"].get("revision") and not settings.public()["ready"]:
                        store.update(job["id"], state="waiting_for_configuration")
                        continue
                    store.update(job["id"], state="running", stage="preflight")
                    last_disk_check = [0.0]
                    def check():
                        if store.get(job["id"])["cancel_requested"]:
                            raise Cancelled()
                        if time.monotonic() - last_disk_check[0] > 5:
                            last_disk_check[0] = time.monotonic()
                            if shutil.disk_usage(settings.root).free < 2 * 1024**3:
                                raise Failure("DISK_FULL", "Keep at least 2 GB free for media processing.")
                            folder = settings.root / job["id"]
                            if sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) > 8 * 1024**3:
                                raise Failure("LIMIT_EXCEEDED", "Job media reached the 8 GB local storage limit.")
                    try:
                        run(settings, store, job, check)
                    except Cancelled:
                        store.update(job["id"], state="cancelled")
                    except Failure as exc:
                        store.update(job["id"], state="partial" if store.get(job["id"])["clips"] else "failed", error=f"{exc.code}: {exc}")
                    except Exception:
                        store.update(job["id"], state="partial" if store.get(job["id"])["clips"] else "failed", error="Local pipeline failed. Check installed dependencies and source availability; credentials are not logged.")
                    finally:
                        for name in ('browser-session.bin', 'browser-request.json'):
                            (settings.root / job['id'] / name).unlink(missing_ok=True)
    except Timeout:
        return
