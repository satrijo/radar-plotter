#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATE_DIR = re.compile(r"^\d{4}$")
MONTH_DIR = re.compile(r"^\d{2}$")
DAY_DIR = re.compile(r"^\d{2}$")


def cutoff(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).date()


def collect_output_dirs(root, before):
    for year in root.iterdir():
        if not year.is_dir() or not DATE_DIR.match(year.name):
            continue
        for month in year.iterdir():
            if not month.is_dir() or not MONTH_DIR.match(month.name):
                continue
            for day in month.iterdir():
                if not day.is_dir() or not DAY_DIR.match(day.name):
                    continue
                try:
                    value = datetime.strptime(f"{year.name}-{month.name}-{day.name}", "%Y-%m-%d").date()
                except ValueError:
                    continue
                if value < before:
                    yield day


def trim_dead_letter(container, stream, days, dry_run):
    min_id = str(int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)) + "-0"
    if dry_run:
        return f"dry-run XTRIM {stream} MINID {min_id}"
    result = subprocess.run(["docker", "exec", container, "redis-cli", "XTRIM", stream, "MINID", min_id], check=True, capture_output=True, text=True)
    return f"trimmed {stream}: {result.stdout.strip()}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(os.getenv("OUTPUT_ROOT", "/home/twl/apps/radar-plotter/output"))
    output_days = int(os.getenv("OUTPUT_RETENTION_DAYS", "7"))
    dead_days = int(os.getenv("DEAD_LETTER_RETENTION_DAYS", "30"))
    before = cutoff(output_days)
    removed = []
    if root.exists():
        for path in collect_output_dirs(root, before):
            if args.dry_run:
                removed.append(str(path))
            else:
                shutil.rmtree(path)
                removed.append(str(path))
    print(f"output_retention_days={output_days} cutoff={before} dry_run={args.dry_run} candidates={len(removed)}")
    for path in removed[:20]: print(path)
    print(trim_dead_letter(os.getenv("REDIS_CONTAINER", "radar-redis"), "radar:jobs:dead", dead_days, args.dry_run))


if __name__ == "__main__":
    main()
