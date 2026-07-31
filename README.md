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

Input NFS is mounted read-only. Generated products are persisted in the `radar-output` volume.

Basemap tiles are disabled by default for worker reliability. If required, configure `USE_BASEMAP_TILES=true` and inject `MAPTILER_TILE_URL` at runtime; no API key belongs in Git.
