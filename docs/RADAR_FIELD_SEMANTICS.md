# Radar Field Semantics

The plotter treats the radar field independently from the geometric product.
`CMAX` is reserved for maximum reflectivity; for non-reflectivity fields the
same elevation aggregation is labeled `MAX <field>`.

| Field family | Unit | Plot semantics |
|---|---|---|
| dBZ, dBZv, dBuZ, dBuZv | dBZ | Reflectivity-family scale |
| V | m/s | Radial velocity, diverging scale around zero |
| W | m/s | Spectrum width, non-negative scale |
| ZDR | dB | Differential reflectivity, diverging scale around zero |
| RhoHV, CCOR, SQI, MDQI | unitless | Quality/correlation index, 0–1 scale |
| PhiDP, uPhiDP | degrees | Differential phase, 0–360 degrees |
| KDP | degrees/km | Specific differential phase |
| ET | km | Echo-top height |
| SRI | mm/h | Z-R derived rain-rate estimate |

Display thresholds, legend labels, colors, peak-value units, and manifest
metadata are selected from this field contract. Unknown fields are rendered
with `native` units and are not filtered using a dBZ threshold.

These automatic products remain supplementary displays. Quality-mask status
must not be inferred from a source metadata flag; the current output declares
`metadata_only` until an actual quality mask is implemented and validated.
