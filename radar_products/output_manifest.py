import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_output_manifest(output_root, record, history_limit=100):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "latest.json"
    lock_path = root / ".latest.json.lock"
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        previous = {}
        if manifest_path.exists():
            try:
                previous = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                previous = {}
        entry = {"updated_at": _utc_now(), **record}
        history = [entry, *previous.get("history", [])][:history_limit]
        payload = {
            "schema_version": 1,
            "updated_at": entry["updated_at"],
            "latest": entry,
            "history": history,
        }
        fd, temporary = tempfile.mkstemp(prefix=".latest.", suffix=".json", dir=root)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, manifest_path)
            os.chmod(manifest_path, 0o644)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return manifest_path
