# Radar Plotter

Redis consumer worker for radar products. It consumes jobs published by `watchdog`, reads radar input from NFS, and writes generated products to the output volume.

## Pipeline

```text
watchdog → Redis Stream radar:jobs → consumer group radar-plotter → plotter → /app/output
```

Supported products:

```text
cmax, ppi, cappi, pcappi, sri
```

## Manual run

```bash
python main.py --input /path/file.vol.nc4 --output-dir output --product cmax
```

The input path must be readable by the runtime. Output is grouped by scan date and hour:

```text
output/YYYYMMDD/HHMM/cmax_<input-stem>.png
```

## Worker

```bash
python worker.py
```

The worker uses Redis consumer group `radar-plotter`, ACKs only after successful plotting, retries failed jobs, and publishes exhausted jobs to `radar:jobs:dead`.

## Docker

The plotter environment is Conda-based because it requires `wradlib`, `netCDF4`, `cartopy`, `pyproj`, and scientific Python dependencies.

The shared deployment network is created by the watchdog Compose project:

```bash
cd /home/twl/apps/watchdog
docker compose up -d --build redis watchdog
cd /home/twl/apps/radar-plotter
docker compose build
docker compose up -d
```

Input NFS is mounted read-only. Generated products are bind-mounted to `/home/twl/apps/radar-plotter/output`. Basemap and Matplotlib caches are bind-mounted separately to `/home/twl/apps/radar-plotter/cache`.

Basemap tiles are disabled by default for worker reliability. If required, create a local `.env` (ignored by Git) with `USE_BASEMAP_TILES=true` and `MAPTILER_TILE_URL=...`; Compose forwards it at runtime and no API key belongs in Git.

## Runtime health

The worker publishes a Redis heartbeat at `radar:worker:<consumer>`. Docker healthcheck verifies Redis connectivity and heartbeat freshness. Worker metrics are stored in the same hash, including completed, retry, and dead-letter totals.

`PLOTTER_CONCURRENCY` controls bounded parallel plotting; default is `2`.
