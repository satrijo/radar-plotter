import concurrent.futures
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import redis

from radar_products.volume_policy import should_skip_partial

STREAM = os.getenv("REDIS_STREAM", "radar:jobs")
GROUP = os.getenv("REDIS_GROUP", "radar-plotter")
CONSUMER = os.getenv("REDIS_CONSUMER", socket.gethostname())
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MAX_ATTEMPTS = int(os.getenv("REDIS_MAX_ATTEMPTS", "3"))
CLAIM_IDLE_MS = int(os.getenv("REDIS_CLAIM_IDLE_MS", "60000"))
DEAD_LETTER_STREAM = os.getenv("REDIS_DEAD_LETTER_STREAM", "radar:jobs:dead")
CONCURRENCY = max(1, int(os.getenv("PLOTTER_CONCURRENCY", "2")))
HEARTBEAT_TTL = int(os.getenv("PLOTTER_HEARTBEAT_TTL", "30"))
HEARTBEAT_INTERVAL = max(1, int(os.getenv("PLOTTER_HEARTBEAT_INTERVAL", "5")))
WORKER_KEY = f"radar:worker:{CONSUMER}"

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("radar-plotter")


def ensure_group(client):
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def decode_fields(fields):
    return {
        key.decode() if isinstance(key, bytes) else key:
        value.decode() if isinstance(value, bytes) else value
        for key, value in fields.items()
    }


def required_job_fields(job):
    return ("job_id", "path", "product")


def is_automatic_dzb_source(path):
    name = Path(path).name.lower()
    return name.endswith("dbz.vol") or name.endswith("dbz.vol.nc4")


def validate_job(job):
    missing = [field for field in required_job_fields(job) if not job.get(field)]
    if missing:
        raise ValueError(f"missing required job fields: {', '.join(missing)}")
    if not Path(job["path"]).is_absolute():
        raise ValueError("job path must be absolute")
    if job["product"].lower() not in {"cmax", "ppi", "cappi", "pcappi", "sri"}:
        raise ValueError(f"unsupported product: {job['product']}")


def update_metrics(client, **values):
    mapping = {key: str(value) for key, value in values.items()}
    if mapping:
        client.hset(WORKER_KEY, mapping=mapping)


def dead_letter(client, message_id, job, attempts, error):
    client.hset(
        f"radar:job:{job.get('job_id', message_id)}",
        mapping={"status": "dead_letter", "attempts": attempts, "error": str(error)},
    )
    client.xadd(
        DEAD_LETTER_STREAM,
        {**job, "original_message_id": message_id, "error": str(error), "attempts": attempts},
    )
    client.xack(STREAM, GROUP, message_id)
    client.hincrby(WORKER_KEY, "dead_letter_total", 1)


def process_job(client, message_id, fields):
    started = time.monotonic()
    try:
        job = decode_fields(fields)
        job_id = job.get("job_id", message_id)
        key = f"radar:job:{job_id}"
        validate_job(job)
    except Exception as exc:
        job = locals().get("job", {})
        log.exception("Invalid job %s: %s", message_id, exc)
        dead_letter(client, message_id, job, 1, exc)
        return False

    key = f"radar:job:{job_id}"
    if os.getenv("PLOTTER_AUTOMATIC_DZB_ONLY", "true").lower() in {"1", "true", "yes", "on"} and not is_automatic_dzb_source(job["path"]):
        now = str(time.time())
        client.hset(key, mapping={
            "status": "skipped_noncanonical",
            "skipped_at": now,
            "reason": "automatic routing accepts only dBZ.vol and dBZ.vol.nc4",
        })
        client.xack(STREAM, GROUP, message_id)
        client.hincrby(WORKER_KEY, "skipped_noncanonical_total", 1)
        client.hset(WORKER_KEY, "last_skipped_noncanonical_at", now)
        log.warning("Skipped noncanonical automatic source job %s: %s", job_id, job["path"])
        return True
    try:
        volume_check = should_skip_partial(job["path"])
    except Exception as exc:
        log.warning("Volume preflight failed for job %s; continuing to plot: %s", job_id, exc)
        volume_check = None
    if volume_check and volume_check["partial"]:
        now = str(time.time())
        client.hset(key, mapping={
            "status": "skipped_partial",
            "skipped_at": now,
            "sweep_count": volume_check["sweep_count"],
            "elevations": ",".join(str(x) for x in volume_check["elevations"]),
        })
        client.xack(STREAM, GROUP, message_id)
        client.hincrby(WORKER_KEY, "skipped_partial_total", 1)
        client.hset(WORKER_KEY, "last_skipped_partial_at", now)
        log.warning("Skipped partial volume job %s: sweeps=%d minimum=%d path=%s", job_id, volume_check["sweep_count"], int(os.getenv("MIN_VOLUME_SWEEPS", "3")), job["path"])
        return True

    attempts = int(client.hget(key, "attempts") or 0) + 1
    client.hset(key, mapping={"status": "processing", "attempts": attempts, "consumer": CONSUMER})
    command = [
        sys.executable,
        str(Path(__file__).with_name("main.py")),
        "--input", job["path"],
        "--output-dir", job.get("output_dir", "output"),
        "--product", job["product"],
    ]
    log.info("Processing job %s attempt=%d: %s", job_id, attempts, job["path"])
    try:
        subprocess.run(command, check=True, timeout=int(os.getenv("PLOT_TIMEOUT", "900")))
    except Exception as exc:
        log.exception("Job %s failed: %s", job_id, exc)
        if attempts >= MAX_ATTEMPTS:
            dead_letter(client, message_id, job, attempts, exc)
        else:
            client.hset(key, mapping={"status": "queued", "error": str(exc)})
            client.xack(STREAM, GROUP, message_id)
            client.xadd(STREAM, {**job, "retry_of": message_id, "attempts": attempts})
            client.hincrby(WORKER_KEY, "retry_total", 1)
        return False

    duration = round(time.monotonic() - started, 3)
    client.hset(key, mapping={"status": "completed", "completed_at": str(time.time()), "duration_seconds": duration})
    client.xack(STREAM, GROUP, message_id)
    client.hincrby(WORKER_KEY, "completed_total", 1)
    client.hset(WORKER_KEY, "last_completed_at", str(time.time()))
    log.info("Job %s completed duration=%.3fs", job_id, duration)
    return True


def reclaim_pending(client):
    cursor = "0-0"
    reclaimed = 0
    while True:
        cursor, entries, *_ = client.xautoclaim(
            STREAM, GROUP, CONSUMER, CLAIM_IDLE_MS, start_id=cursor, count=10
        )
        for message_id, fields in entries:
            process_job(client, message_id, fields)
            reclaimed += 1
        if not entries or cursor in ("0-0", b"0-0"):
            break
    if reclaimed:
        log.info("Reclaimed %d pending jobs", reclaimed)


def heartbeat_loop(stop_event):
    client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
    while not stop_event.wait(HEARTBEAT_INTERVAL):
        try:
            now = str(time.time())
            client.hset(WORKER_KEY, mapping={
                "status": "running",
                "consumer": CONSUMER,
                "stream": STREAM,
                "group": GROUP,
                "concurrency": CONCURRENCY,
                "heartbeat_at": now,
            })
            client.expire(WORKER_KEY, HEARTBEAT_TTL)
        except Exception:
            log.exception("Heartbeat update failed")


def main():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
    client.ping()
    ensure_group(client)
    stop_event = threading.Event()
    heartbeat = threading.Thread(target=heartbeat_loop, args=(stop_event,), name="heartbeat", daemon=True)
    heartbeat.start()
    update_metrics(client, status="running", consumer=CONSUMER, concurrency=CONCURRENCY, started_at=time.time(), heartbeat_at=time.time())
    client.expire(WORKER_KEY, HEARTBEAT_TTL)
    reclaim_pending(client)
    log.info("Redis worker ready: stream=%s group=%s consumer=%s concurrency=%d", STREAM, GROUP, CONSUMER, CONCURRENCY)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            while True:
                messages = client.xreadgroup(
                    GROUP, CONSUMER, {STREAM: ">"}, count=CONCURRENCY, block=5000
                )
                futures = []
                for _, entries in messages:
                    futures.extend(pool.submit(process_job, client, message_id, fields) for message_id, fields in entries)
                for future in futures:
                    future.result()
    finally:
        stop_event.set()
        update_metrics(client, status="stopping", stopped_at=time.time())


if __name__ == "__main__":
    main()
