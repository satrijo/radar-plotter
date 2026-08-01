#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path

STATE = Path("/home/twl/apps/radar-plotter/monitoring/alert_state.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

def cmd(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()

def redis(*args):
    return cmd("docker", "exec", "radar-redis", "redis-cli", "--raw", *args)

def main():
    problems=[]
    try:
        groups=redis("XINFO","GROUPS","radar:jobs").splitlines()
        values=dict(zip(groups[::2],groups[1::2]))
        lag=int(values.get("lag", "-1")); pending=int(values.get("pending", "-1"))
        if lag >= 50: problems.append(f"Redis lag tinggi: {lag}")
        if pending >= 20: problems.append(f"Redis pending tinggi: {pending}")
        dead=int(redis("XLEN","radar:jobs:dead"))
    except Exception as e:
        problems.append(f"Redis tidak dapat diperiksa: {e}"); lag=pending=dead=-1
    try:
        raw=cmd("docker","ps","--format","{{json .}}")
        containers=[json.loads(x) for x in raw.splitlines() if x]
        workers=[x for x in containers if x.get("Label","").find("com.docker.compose.service=radar-plotter") >= 0 or "radar-plotter-radar-plotter" in x.get("Names","")]
        healthy=sum("healthy" in x.get("Status","") for x in workers)
        if not workers: problems.append("Radar-plotter tidak berjalan")
        elif healthy < len(workers): problems.append(f"Radar-plotter unhealthy: {healthy}/{len(workers)} healthy")
    except Exception as e:
        problems.append(f"Worker tidak dapat diperiksa: {e}")
    try:
        worker_keys=redis("SCAN","0","MATCH","radar:worker:*","COUNT","100").splitlines()
        keys=[x for x in worker_keys if x.startswith("radar:worker:")]
        now=time.time(); fresh=0
        for key in keys:
            hb=redis("HGET",key,"heartbeat_at")
            if hb and now-float(hb) <= 120: fresh += 1
        if keys and fresh == 0: problems.append("Heartbeat worker stale")
    except Exception as e:
        problems.append(f"Heartbeat tidak dapat diperiksa: {e}")
    try:
        old=json.loads(STATE.read_text()) if STATE.exists() else {}
    except Exception: old={}
    previous_dead=old.get("dead_letter", dead)
    if dead > previous_dead: problems.append(f"Dead-letter bertambah: {previous_dead} → {dead}")
    signature="|".join(problems) if problems else "healthy"
    previous_signature=old.get("signature")
    STATE.write_text(json.dumps({"signature":signature,"dead_letter":dead,"updated_at":time.time()}))
    if signature != previous_signature:
        if signature == "healthy" and previous_signature and previous_signature != "healthy":
            print(f"✅ Radar pipeline recovered. Redis lag={lag}, pending={pending}, dead-letter={dead}.")
        elif signature != "healthy":
            print("🚨 Radar pipeline alert: " + "; ".join(problems))

if __name__ == "__main__": main()
