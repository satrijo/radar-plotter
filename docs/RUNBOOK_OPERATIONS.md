# Radar Pipeline Operations Runbook

## Scope

Pipeline:

```text
radar-file-mover → NFS latest.json → watchdog → Redis Stream → radar-plotter → output/latest.json + PNG
```

Input NFS is read-only for consumers. Redis stores queue metadata, never radar files.

## Normal health checks

Run on the WSL host:

```bash
cd /home/twl/apps/radar-plotter
docker compose ps
docker exec radar-redis redis-cli PING
docker exec radar-redis redis-cli XINFO GROUPS radar:jobs
docker exec radar-redis redis-cli XLEN radar:jobs:dead
cat /home/twl/apps/radar-plotter/output/latest.json
systemctl --user status radar-plotter-scaler.timer radar-plotter-retention.timer
```

Healthy baseline:

- plotter container is `healthy`;
- Redis responds `PONG`;
- consumer-group lag is normally near zero;
- heartbeat is fresh;
- `latest.json` has `latest.status=completed` after successful plots;
- dead-letter does not grow unexpectedly.

## Queue lag or worker backlog

Inspect:

```bash
docker exec radar-redis redis-cli XINFO GROUPS radar:jobs
docker compose logs --tail=200 radar-plotter
```

The autoscaler adjusts replicas every two minutes:

```text
lag >= 100 → 3 replicas
lag 50–99  → 2 replicas
lag <= 20  → 1 replica
```

Manual temporary scale:

```bash
docker compose up -d --scale radar-plotter=3 radar-plotter
```

Do not delete pending Redis entries during a backlog incident. Let `XAUTOCLAIM` reclaim abandoned jobs.

## Unhealthy worker

Inspect health and heartbeat:

```bash
docker compose ps
docker compose logs --tail=300 radar-plotter
docker exec radar-redis redis-cli --scan --pattern 'radar:worker:*'
```

Restart only the plotter first:

```bash
docker compose up -d --force-recreate radar-plotter
```

Then verify:

```bash
docker compose ps
docker exec radar-redis redis-cli XINFO GROUPS radar:jobs
```

Redis pending jobs should be reclaimed by the restarted worker. Do not remove the Redis stream as a recovery shortcut.

## Redis unavailable

Check the service and logs:

```bash
docker compose ps redis
docker compose logs --tail=200 redis
docker exec radar-redis redis-cli PING
```

Restart Redis only after confirming the persistent Redis volume is present:

```bash
docker compose up -d redis
```

Then verify `PONG`, the stream, the consumer group, and worker health. Do not run `docker compose down -v`; that can destroy queue state.

## Dead-letter review

Inspect recent entries:

```bash
docker exec radar-redis redis-cli XRANGE radar:jobs:dead - + COUNT 20
```

Classify before replaying:

- obsolete `.jpg`/`.jpeg`: leave for retention cleanup;
- malformed job: fix publisher/schema first;
- real `.vol`/`.nc4` failure: inspect plotter logs and source readability.

Never replay all dead-letter entries blindly. Replay only a verified job after fixing its cause, preserving the original message ID in the audit record.

## NFS or watchdog issue

Verify the mount and manifest:

```bash
findmnt /mnt/qnap_radar
mountpoint /mnt/qnap_radar
python3 - <<'PY'
import json
p='/mnt/qnap_radar/Radar/latest.json'
d=json.load(open(p))
print(d.get('updated_at'), len(d.get('organized', [])), len(d.get('pending', [])))
PY
```

Check watchdog:

```bash
docker compose -f /home/twl/apps/watchdog/docker-compose.yml ps
docker compose -f /home/twl/apps/watchdog/docker-compose.yml logs --tail=200 watchdog
```

Do not make the watchdog scan/rename files if the file mover owns organization. Restore the upstream mover or NFS path first.

## Output and metadata

Output layout:

```text
output/YYYY/MM/DD/HHMM/<product>/
```

Plotter metadata:

```text
output/latest.json
```

The manifest is written atomically after successful rendering. Verify source format, scan time, sweep count, and output paths before distributing a plot.

Retention:

- PNG output: 7 days;
- dead-letter stream: 30 days;
- manifest history: 100 entries;
- cleanup timer: daily at 03:30 WIB.

Dry-run retention:

```bash
python3 /home/twl/apps/radar-plotter/scripts/retention_cleanup.py --dry-run
```

## Change and deployment gate

Before production changes:

```bash
git diff --check
git status --short
python3 -m compileall -q .
docker compose config >/dev/null
docker compose build radar-plotter
docker run --rm radar-plotter:local python -m pytest -q tests
```

After deployment, verify the live surface: container health, heartbeat, Redis group lag/pending, dead-letter count, output manifest, and one real output artifact.

Never print or commit runtime credentials. Keep `.env` mode `600`.

## Alerting

A host-side check runs every five minutes and sends only state changes to the operator channel. It checks worker health/heartbeat, Redis lag/pending, and dead-letter growth. The check is intentionally silent while healthy.

The local scheduler job is named `radar-pipeline-alerts`; its remote implementation is `scripts/monitor_alert.py`.

## Output mirror to D drive

Canonical output remains on the Linux filesystem:

```text
/home/twl/apps/radar-plotter/output
```

A systemd oneshot service mirrors it to:

```text
/mnt/d/Radar
```

The timer runs every two minutes:

```bash
systemctl --user status radar-output-mirror.timer
systemctl --user start radar-output-mirror.service
journalctl --user -u radar-output-mirror.service -n 50 --no-pager
```

The mirror copies PNG/output artifacts first and `latest.json` last using atomic per-file replacement. It excludes lock files and cache directories. The plotter does not depend on the mirror; a D-drive failure must not stop Redis ACK or plotting.
