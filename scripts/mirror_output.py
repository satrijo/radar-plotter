from pathlib import Path
import os
import shutil
import tempfile

SOURCE = Path(os.getenv("OUTPUT_SOURCE", "/home/twl/apps/radar-plotter/output"))
DEST = Path(os.getenv("OUTPUT_MIRROR", "/mnt/d/Radar"))
EXCLUDED = {".latest.json.lock", ".matplotlib-cache"}


def is_excluded(path):
    return any(part in EXCLUDED or part.startswith(".") and part != "." for part in path.relative_to(SOURCE).parts)


def copy_atomic(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        s = source.stat()
        d = destination.stat()
        if s.st_size == d.st_size and s.st_mtime_ns == d.st_mtime_ns:
            return False
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as target, source.open("rb") as source_stream:
            shutil.copyfileobj(source_stream, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        shutil.copystat(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    if not SOURCE.is_dir():
        raise SystemExit(f"source missing: {SOURCE}")
    DEST.mkdir(parents=True, exist_ok=True)
    expected = set()
    changed = 0
    # Copy all output artifacts except the manifest; it is copied last.
    for source in sorted(SOURCE.rglob("*")):
        if not source.is_file() or source.name == "latest.json" or is_excluded(source):
            continue
        relative = source.relative_to(SOURCE)
        destination = DEST / relative
        expected.add(relative)
        changed += int(copy_atomic(source, destination))
    manifest = SOURCE / "latest.json"
    if manifest.exists():
        expected.add(Path("latest.json"))
        changed += int(copy_atomic(manifest, DEST / "latest.json"))
    # Mirror is dedicated to plotter output; remove only files no longer in source.
    removed = 0
    for destination in sorted(DEST.rglob("*"), reverse=True):
        if destination.is_file() and destination.relative_to(DEST) not in expected:
            destination.unlink()
            removed += 1
        elif destination.is_dir() and not any(destination.iterdir()):
            destination.rmdir()
    print(f"source={SOURCE} mirror={DEST} changed={changed} removed={removed} files={len(expected)}")


if __name__ == "__main__":
    main()
