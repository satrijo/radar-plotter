import numpy as np

from radar_products.config import (
    AZIMUTH_FULL_CIRCLE_DEG,
    MISSING_VALUE_THRESHOLD,
    RANGE_UNIT_TO_METER,
)


def list_slices(nc):
    scan = nc.groups["scan"]
    slices = []

    for name, group in scan.groups.items():
        if not name.startswith("slice_"):
            continue

        raw_group = group.groups["slicedata"].groups["rawdata"]
        slices.append(
            {
                "name": name,
                "index": int(name.split("_", 1)[1]),
                "elevation": float(group.getncattr("posangle")),
                "field": raw_group.getncattr("type"),
                "rays": int(raw_group.getncattr("rays")),
                "bins": int(raw_group.getncattr("bins")),
            }
        )

    return sorted(slices, key=lambda item: item["index"])


def read_slice(nc, slice_name):
    scan = nc.groups["scan"]
    pargroup = scan.groups["pargroup"]
    slice_group = scan.groups[slice_name]
    slicedata = slice_group.groups["slicedata"]
    raw_group = slicedata.groups["rawdata"]

    field = np.ma.array(raw_group.variables["rawdata"][:], dtype=float)
    field = np.ma.masked_invalid(field)
    field = np.ma.masked_less(field, MISSING_VALUE_THRESHOLD)

    ray_start = slicedata.groups["rayinfo_0"].variables["rayinfo"][:].astype(float)
    ray_stop = slicedata.groups["rayinfo_1"].variables["rayinfo"][:].astype(float)
    azimuth_centers = circular_midpoint(ray_start, ray_stop)
    azimuth_edges = np.concatenate([ray_start, [ray_stop[-1]]])

    start_range_km = get_float_attr(slice_group, "start_range", pargroup, default=0.0)
    range_step_km = get_float_attr(slice_group, "rangestep", pargroup, default=0.5)
    stop_range_km = get_float_attr(slice_group, "stoprange", pargroup, default=250.0)
    range_edges_km = start_range_km + np.arange(field.shape[1] + 1) * range_step_km

    return {
        "name": slice_name,
        "elevation": float(slice_group.getncattr("posangle")),
        "field_name": raw_group.getncattr("type"),
        "field": field,
        "azimuth_centers": azimuth_centers,
        "azimuth_edges": azimuth_edges,
        "range_edges_km": range_edges_km,
        "stop_range_km": stop_range_km,
    }


def get_radar_site(nc):
    sensor = nc.groups["sensorinfo"]
    return {
        "name": get_attr(sensor, "name", "Radar"),
        "lat": float(get_attr(sensor, "lat", "0")),
        "lon": float(get_attr(sensor, "lon", "0")),
        "alt_km": float(get_attr(sensor, "alt", "0")) / RANGE_UNIT_TO_METER,
    }


def get_time_label(nc):
    scan = nc.groups.get("scan")
    timezone = " UTC" if get_attr(nc, "datetime", "").endswith("Z") else ""
    if scan is None:
        return get_attr(nc, "datetime", "unknown time").replace("T", " ")

    start_time = get_attr(scan, "starttime", "")
    end_time = get_attr(scan, "endtime", "")
    if start_time and end_time:
        date = start_time.split("T", 1)[0]
        start_clock = start_time.split("T", 1)[1]
        end_clock = end_time.split("T", 1)[1] if "T" in end_time else end_time
        return f"{date} {start_clock}-{end_clock}{timezone}"

    date = get_attr(scan, "date", "")
    clock = get_attr(scan, "time", "")
    if date and clock:
        return f"{date} {clock}{timezone}"

    return get_attr(nc, "datetime", "unknown time").replace("T", " ")


def circular_midpoint(start_degrees, stop_degrees):
    return (
        start_degrees
        + ((stop_degrees - start_degrees) % AZIMUTH_FULL_CIRCLE_DEG) / 2.0
    ) % AZIMUTH_FULL_CIRCLE_DEG


def get_float_attr(primary_group, attr_name, fallback_group, default):
    if attr_name in primary_group.ncattrs():
        return float(primary_group.getncattr(attr_name))

    if attr_name in fallback_group.ncattrs():
        return float(fallback_group.getncattr(attr_name))

    return default


def get_attr(group, attr_name, default):
    if attr_name in group.ncattrs():
        return str(group.getncattr(attr_name))
    return default
