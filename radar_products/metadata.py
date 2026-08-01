from datetime import datetime, timedelta, timezone

from radar_products.config import DATA_FILE
from radar_products.netcdf_reader import get_attr


def get_product_metadata(nc, source_file=None):
    scan = nc.groups["scan"]
    pargroup = scan.groups["pargroup"]
    high_prf = get_attr(pargroup, "highprf", "")
    low_prf = get_attr(pargroup, "lowprf", "")
    prf = format_prf(high_prf, low_prf)
    posangles = parse_float_list(get_attr(pargroup, "posanglelist", ""))
    data_types = get_attr(
        pargroup, "datatypes", get_attr(pargroup, "masterdatatypes", "")
    )

    return {
        "source_file": source_file or DATA_FILE.name,
        "scan_name": get_attr(scan, "name", get_attr(nc, "type", "unknown")),
        "scan_strategy": get_attr(pargroup, "scanstrategy", "n/a"),
        "clutter_filter": get_clutter_filter_label(pargroup),
        "time_sampling": get_attr(pargroup, "timesamp", "n/a"),
        "prf": prf,
        "source_range": f"{to_float_text(get_attr(pargroup, 'stoprange', 'n/a'))} km",
        "range_step": f"{to_float_text(get_attr(pargroup, 'rangestep', 'n/a'))} km/bin",
        "data_types": data_types,
        "elevation_range": format_elevation_range(posangles),
    }


def get_clutter_filter_label(pargroup):
    candidates = [
        ("GIP", "cf_gip"),
        ("GIP mode", "cf_gip_mode_const"),
        ("Clutter flag", "gdrx_clutter_flag_filter"),
        ("Clutter map", "gdrx_cluttermap"),
        ("FFT filter", "fftfilter"),
    ]
    enabled = []
    fallback = []
    for label, attr_name in candidates:
        value = get_attr(pargroup, attr_name, "")
        if not value:
            continue
        fallback.append(f"{label} {value}")
        if value.lower() not in {"off", "none", "false", "0"}:
            enabled.append(f"{label} {value}")

    if enabled:
        return ", ".join(enabled)
    if fallback:
        return ", ".join(fallback)
    return "n/a"


def format_prf(high_prf, low_prf):
    high = to_float_text(high_prf)
    low = to_float_text(low_prf)
    if high != "n/a" and low != "n/a":
        return f"{high} Hz / {low} Hz"
    if high != "n/a":
        return f"{high} Hz"
    if low != "n/a":
        return f"{low} Hz"
    return "n/a"


def parse_float_list(value):
    values = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(float(item))
        except ValueError:
            pass
    return values


def format_elevation_range(values):
    if not values:
        return "n/a"
    return f"{min(values):g}-{max(values):g} deg ({len(values)})"


def to_float_text(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a" if value in {"", None} else str(value)
    return f"{number:g}"


def format_scan_time_for_panel(time_label):
    parts = time_label.replace(" UTC", "").split()
    if len(parts) < 2:
        return time_label

    date = parts[0]
    start_time = parts[1].split("-", 1)[0]
    year, month, day = date.split("-")
    utc_start = datetime.strptime(f"{date} {start_time.rstrip(chr(90))}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    local_start = utc_start.astimezone(timezone(timedelta(hours=7)))
    return f'{start_time} UTC / {local_start.strftime("%H:%M")} WIB\n{day}-{month}-{year}'
