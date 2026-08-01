# Forecaster Product Readiness

## Current status

The rendered CMAX product is suitable as a supplementary forecaster display and situational-awareness product. It is not a standalone certified warning or aviation-safety product.

## Current strengths

- 11-elevation complete volume can be rendered from `.vol`/`.nc4`.
- Legend includes dBZ units and thresholds.
- Product definition identifies CMAX as maximum reflectivity across elevations.
- Display includes UTC and WIB time, radar marker, grid, basemap, range rings, and scale bar.
- Side panel includes source format, scan strategy, clutter metadata, sweep/elevation metadata, peak value, display extent, and QC status.
- `output/latest.json` records source, scan time, sweep count, elevations, display extent, quality-control status, and output paths.

## Explicit limitations

The current QC status is intentionally reported as:

```text
metadata_only; no quality mask
```

The plot must not be interpreted as fully clutter-corrected or beam-blockage-corrected. Forecasters should cross-check with PPI 0.5 degree, velocity, spectrum width, RhoHV, ZDR, and a time loop before issuing operational conclusions.

CMAX can hide vertical structure because it takes the maximum value across elevations. Echoes over the sea or radial patterns must not automatically be treated as precipitation.

The `Range` metadata is source/radar range. `Display` is the actual map extent shown in the PNG; these are intentionally separate.

## Acceptance criteria before primary operational use

1. Add and validate quality masks for clutter, beam blockage, attenuation, and anomalous propagation where source metadata/algorithms support them.
2. Provide a temporal loop or a stable multi-frame viewer for at least 30–60 minutes.
3. Compare representative rainfall and convective cases against the trusted operational/reference radar product.
4. Define a forecaster sign-off checklist and retain the source/output metadata for each issued product.
5. Verify latency and missing-frame behavior under real continuous operations.
