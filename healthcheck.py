import os
import socket
import sys
import time

import redis

def main():
    client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    client.ping()
    consumer = os.getenv("REDIS_CONSUMER", socket.gethostname())
    heartbeat = client.hget(f"radar:worker:{consumer}", "heartbeat_at")
    if heartbeat is None or time.time() - float(heartbeat) > int(os.getenv("PLOTTER_HEARTBEAT_TTL", "30")):
        raise RuntimeError("worker heartbeat is stale")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
