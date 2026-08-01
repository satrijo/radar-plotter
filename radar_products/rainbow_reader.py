import numpy as np
import wradlib as wrl

from radar_products.config import (
    AZIMUTH_FULL_CIRCLE_DEG,
    MISSING_VALUE_THRESHOLD,
    RANGE_UNIT_TO_METER,
    RAINBOW_ANGLE_SCALE,
    RAINBOW_DEFAULT_MAX_VALUE,
    RAINBOW_DEFAULT_MIN_VALUE,
)
from radar_products.metadata import format_elevation_range, format_prf, to_float_text


def read_rainbow_volume(path):
    data = wrl.io.read_rainbow(str(path))
    if "volume" not in data:
        raise ValueError(f"{path} is not a Rainbow volume file")

    volume = data["volume"]
    scan = volume["scan"]
    slices = ensure_list(scan["slice"])
    radar_site = get_radar_site(volume)
    time_label = get_time_label(volume, scan)
    metadata = get_product_metadata(path, volume, scan, radar_site, slices)

    slice_summaries = []
    slice_data_list = []
    for index, slice_group in enumerate(slices):
        slice_data = read_slice(slice_group, index, scan.get("pargroup", {}))
        slice_data["time_label"] = time_label
        slice_data["radar_site"] = radar_site
        slice_data["metadata"] = metadata
        slice_summaries.append(
            {
                "name": slice_data["name"],
                "index": index,
                "elevation": slice_data["elevation"],
                "field": slice_data["field_name"],
                "rays": slice_data["field"].shape[0],
                "bins": slice_data["field"].shape[1],
            }
        )
        slice_data_list.append(slice_data)

    return {
        "file_type": volume.get("@type", "vol"),
        "time_label": time_label,
        "radar_site": radar_site,
        "metadata": metadata,
        "slices": slice_summaries,
        "slice_data_list": slice_data_list,
        "prebuilt_cmax": None,
    }


def read_rainbow_cmax(path):
    data = wrl.io.read_rainbow(str(path))
    if "product" not in data:
        raise ValueError(f"{path} is not a Rainbow product file")

    product = data["product"]
    if product.get("@type", "").lower() not in {"cmax", "cappi", "ppi"}:
        raise ValueError(f"Unsupported Rainbow product type: {product.get('@type')}")

    product_data = product["data"]
    radar_picture = product_data["radarpicture"]
    datamap = radar_picture["datamap"]
    projection = radar_picture["projection"]
    radar_site = get_product_radar_site(product_data)
    field = decode_rainbow_raw(
        datamap["data"],
        radar_picture.get("@min", RAINBOW_DEFAULT_MIN_VALUE),
        radar_picture.get("@max", RAINBOW_DEFAULT_MAX_VALUE),
        datamap.get("@depth", "8"),
    )
    field = np.ma.masked_less(np.ma.masked_invalid(field), MISSING_VALUE_THRESHOLD)
    resolution_km = float(product_data.get("viewparams", {}).get("disphorres", "@0.2").replace("@", ""))
    size_y, size_x = field.shape
    extent = (
        -size_x * resolution_km / 2.0,
        size_x * resolution_km / 2.0,
        -size_y * resolution_km / 2.0,
        size_y * resolution_km / 2.0,
    )
    time_label = get_product_time_label(product)
    metadata = get_cmax_metadata(path, product, product_data, radar_site)

    cmax_data = {
        "field_name": product.get("@datatype", radar_picture.get("@type", "dBZ")),
        "product_label": product.get("@name", product.get("@type", "CMAX")).upper(),
        "field": field,
        "x_km": np.linspace(extent[0], extent[1], size_x, endpoint=False),
        "y_km": np.linspace(extent[2], extent[3], size_y, endpoint=False),
        "extent": extent,
        "grid_resolution_km": resolution_km,
        "elevations": [],
        "time_label": time_label,
        "scan_time_label": format_panel_time(time_label),
        "radar_site": radar_site,
        "height_range_km": (0.0, np.nan),
        "peak_dbz": float(field.max()) if field.count() else np.nan,
        "metadata": metadata,
    }
    return {
        "file_type": product.get("@type", "product"),
        "time_label": time_label,
        "radar_site": radar_site,
        "metadata": metadata,
        "slices": [],
        "slice_data_list": [],
        "prebuilt_cmax": cmax_data,
    }


def read_slice(slice_group, index, pargroup=None):
    slicedata = slice_group["slicedata"]
    raw_group = slicedata["rawdata"]
    field = decode_rainbow_raw(
        raw_group["data"],
        raw_group.get("@min", RAINBOW_DEFAULT_MIN_VALUE),
        raw_group.get("@max", RAINBOW_DEFAULT_MAX_VALUE),
        raw_group.get("@depth", "8"),
    )
    field = np.ma.masked_less(np.ma.masked_invalid(field), MISSING_VALUE_THRESHOLD)

    rayinfo = ensure_list(slicedata["rayinfo"])
    ray_start = decode_angle(rayinfo[0]["data"])
    ray_stop = decode_angle(rayinfo[1]["data"])
    azimuth_centers = (
        ray_start + ((ray_stop - ray_start) % AZIMUTH_FULL_CIRCLE_DEG) / 2.0
    ) % AZIMUTH_FULL_CIRCLE_DEG
    azimuth_edges = np.concatenate([ray_start, [ray_stop[-1]]])

    pargroup = pargroup or {}
    start_range_km = float(slice_group.get("start_range", pargroup.get("start_range", 0.0)))
    range_step_km = float(slice_group.get("rangestep", pargroup.get("rangestep", 0.5)))
    stop_range_km = float(slice_group.get("stoprange", pargroup.get("stoprange", start_range_km + field.shape[1] * range_step_km)))
    range_edges_km = start_range_km + np.arange(field.shape[1] + 1) * range_step_km

    return {
        "name": f"slice_{index}",
        "elevation": float(slice_group.get("posangle", 0.0)),
        "field_name": raw_group.get("@type", "dBZ"),
        "field": field,
        "azimuth_centers": azimuth_centers,
        "azimuth_edges": azimuth_edges,
        "range_edges_km": range_edges_km,
        "stop_range_km": stop_range_km,
    }


def decode_rainbow_raw(raw, minimum, maximum, depth):
    raw = np.asarray(raw, dtype=float)
    minimum = float(minimum)
    maximum = float(maximum)
    levels = (2 ** int(depth)) - 1
    decoded = minimum + raw * (maximum - minimum) / levels
    decoded[raw <= 0] = np.nan
    return decoded


def decode_angle(raw):
    return np.asarray(raw, dtype=float) * AZIMUTH_FULL_CIRCLE_DEG / RAINBOW_ANGLE_SCALE


def get_radar_site(volume):
    sensor = volume["sensorinfo"]
    return {
        "name": str(sensor.get("@name", sensor.get("name", "Radar"))),
        "lat": float(sensor.get("lat", 0.0)),
        "lon": float(sensor.get("lon", 0.0)),
        "alt_km": float(sensor.get("alt", 0.0)) / RANGE_UNIT_TO_METER,
    }


def get_product_radar_site(product_data):
    sensor = product_data["sensorinfo"]
    return {
        "name": str(sensor.get("@name", sensor.get("name", "Radar"))),
        "lat": float(sensor.get("lat", 0.0)),
        "lon": float(sensor.get("lon", 0.0)),
        "alt_km": float(sensor.get("alt", 0.0)) / RANGE_UNIT_TO_METER,
    }


def get_time_label(volume, scan):
    start = scan.get("starttime") or f"{scan.get('@date')}T{scan.get('@time')}"
    end = scan.get("endtime", "")
    if start and end:
        date = start.split("T", 1)[0]
        start_clock = start.split("T", 1)[1]
        end_clock = end.split("T", 1)[1] if "T" in end else end
        return f"{date} {start_clock}-{end_clock} UTC"
    return str(volume.get("@datetime", "unknown time")).replace("T", " ")


def get_product_time_label(product):
    value = product.get("@datetime", "")
    if value:
        return value.replace("T", " ").replace("Z", " UTC")
    product_data = product["data"]
    date = product_data.get("@date", "")
    time = product_data.get("@time", "")
    return f"{date} {time} UTC".strip()


def format_panel_time(time_label):
    parts = time_label.replace(" UTC", "").split()
    if len(parts) < 2:
        return time_label
    date = parts[0]
    start_time = parts[1].split("-", 1)[0]
    year, month, day = date.split("-")
    return f"{start_time} / {day}-{month}-{year}"


def get_product_metadata(path, volume, scan, radar_site, slices):
    pargroup = scan.get("pargroup", {})
    posangles = [float(item.get("posangle", 0.0)) for item in slices]
    return {
        "source_file": path.name,
        "scan_name": scan.get("@name", volume.get("@type", "unknown")),
        "scan_strategy": pargroup.get("scanstrategy", "n/a"),
        "clutter_filter": pargroup.get("cf_gip", "n/a"),
        "time_sampling": pargroup.get("timesamp", "n/a"),
        "prf": format_prf(pargroup.get("highprf", ""), pargroup.get("lowprf", "")),
        "source_range": f"{to_float_text(pargroup.get('stoprange', 'n/a'))} km",
        "range_step": f"{to_float_text(pargroup.get('rangestep', 'n/a'))} km/bin",
        "data_types": pargroup.get("datatypes", "n/a"),
        "elevation_range": format_elevation_range(posangles),
    }


def get_cmax_metadata(path, product, product_data, radar_site):
    viewparams = product_data.get("viewparams", {})
    return {
        "source_file": path.name,
        "scan_name": product.get("@name", product.get("@type", "product")),
        "scan_strategy": "n/a",
        "clutter_filter": clean_value(viewparams.get("clfilter", "n/a")),
        "time_sampling": clean_value(viewparams.get("timesamp", "n/a")),
        "prf": clean_value(viewparams.get("prf", "n/a")),
        "source_range": f"{clean_value(viewparams.get('disprange', 'n/a'))} km",
        "range_step": f"{clean_value(viewparams.get('disphorres', 'n/a'))} km/pixel",
        "data_types": product.get("@datatype", "n/a"),
        "elevation_range": clean_value(viewparams.get("height", "n/a")),
    }


def clean_value(value):
    return str(value).replace("@", "")


def ensure_list(value):
    return value if isinstance(value, list) else [value]
