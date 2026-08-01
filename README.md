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

## Tests

Unit tests run without external radar data:

```bash
docker run --rm radar-plotter:local python -m pytest -q tests
```

Run the real rendering smoke test with an accessible `.nc4` sample:

```bash
RADAR_SAMPLE_FILE=/mnt/qnap_radar/Radar/2026/07/31/12/2026073112200100dBZ.vol.nc4 docker compose run --rm -e RADAR_SAMPLE_FILE radar-plotter python -m pytest -q tests/test_rendering.py
```

The Docker base image is pinned by digest and the primary radar runtime dependencies are version-pinned in `environment.yml`.

## Autoscaling

Each plotter replica uses its container hostname as the Redis consumer identity. Scale manually or run the lag controller:

```bash
./scripts/scale_plotter.sh
```

Default policy:

- lag `>= 100`: 3 replicas
- lag `50..99`: 2 replicas
- lag `<= 20`: 1 replica

Override `MIN_REPLICAS`, `MAX_REPLICAS`, `SCALE_UP_LAG`, `SCALE_MAX_LAG`, or `SCALE_DOWN_LAG` when needed. All replicas share the read-only NFS input and host output/cache mounts.

The rendering smoke test also checks the golden output contract: 3900x2400 pixels, RGB/RGBA output, non-empty visual content, and a real `.nc4` render.

## Partial volume policy

The plotter inspects volume metadata before plotting. No fixed elevation-angle list is required. Configure the behavior in `.env`:

```env
PARTIAL_VOLUME_POLICY=skip
MIN_VOLUME_SWEEPS=3
```

`skip` ACKs a volume with fewer than the configured sweep count and records `status=skipped_partial`; `process` keeps the existing behavior and plots it. `.cmax` inputs are not treated as raw elevation volumes. Recreate the plotter after changing the setting.

## Plotter output metadata

The plotter publishes an atomic manifest at:

```text
output/latest.json
```

It contains `schema_version`, `updated_at`, the latest completed output, and a bounded `history` list. Each latest record includes the source path/name/format, scan time, sweep count, elevations, product, status, and output paths. The manifest is safe for concurrent replicas and is written with a file lock plus atomic replace.
