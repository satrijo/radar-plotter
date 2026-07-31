import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import redis

STREAM = os.getenv("REDIS_STREAM", "radar:jobs")
GROUP = os.getenv("REDIS_GROUP", "radar-plotter")
CONSUMER = os.getenv("REDIS_CONSUMER", socket.gethostname())
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MAX_ATTEMPTS = int(os.getenv("REDIS_MAX_ATTEMPTS", "3"))
CLAIM_IDLE_MS = int(os.getenv("REDIS_CLAIM_IDLE_MS", "60000"))
DEAD_LETTER_STREAM = os.getenv("REDIS_DEAD_LETTER_STREAM", "radar:jobs:dead")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("radar-plotter")


def ensure_group(client):
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def decode_fields(fields):
    return {key.decode() if isinstance(key, bytes) else key: value.decode() if isinstance(value, bytes) else value for key, value in fields.items()}


def process_job(client, message_id, fields):
    job = decode_fields(fields)
    job_id = job["job_id"]
    key = f"radar:job:{job_id}"
    attempts = int(client.hget(key, "attempts") or 0) + 1
    client.hset(key, mapping={"status": "processing", "attempts": attempts, "consumer": CONSUMER})
    command = [sys.executable, str(Path(__file__).with_name("main.py")), "--input", job["path"], "--output-dir", job.get("output_dir", "output"), "--product", job.get("product", "cmax")]
    log.info("Processing job %s: %s", job_id, job["path"])
    try:
        subprocess.run(command, check=True, timeout=int(os.getenv("PLOT_TIMEOUT", "900")))
    except Exception as exc:
        log.exception("Job %s failed: %s", job_id, exc)
        if attempts >= MAX_ATTEMPTS:
            client.hset(key, mapping={"status": "dead_letter", "error": str(exc)})
            client.xadd(DEAD_LETTER_STREAM, {**job, "error": str(exc), "attempts": attempts})
            client.xack(STREAM, GROUP, message_id)
        else:
            client.hset(key, mapping={"status": "queued", "error": str(exc)})
            client.xack(STREAM, GROUP, message_id)
            client.xadd(STREAM, job)
        return False
    client.hset(key, mapping={"status": "completed", "completed_at": str(time.time())})
    client.xack(STREAM, GROUP, message_id)
    log.info("Job %s completed", job_id)
    return True


def reclaim_pending(client):
    cursor = "0-0"
    while True:
        cursor, entries, *_ = client.xautoclaim(STREAM, GROUP, CONSUMER, CLAIM_IDLE_MS, start_id=cursor, count=10)
        for message_id, fields in entries:
            process_job(client, message_id, fields)
        if cursor == "0-0" or not entries:
            break


def main():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
    client.ping()
    ensure_group(client)
    reclaim_pending(client)
    log.info("Redis worker ready: stream=%s group=%s consumer=%s", STREAM, GROUP, CONSUMER)
    while True:
        messages = client.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=1, block=5000)
        for _, entries in messages:
            for message_id, fields in entries:
                process_job(client, message_id, fields)


if __name__ == "__main__":
    main()
