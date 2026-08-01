import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap


REFLECTIVITY_COLORS = [
    "#d9d9d9", "#9ff7f1", "#63cfea", "#2f9df4", "#2362f1",
    "#a8ff00", "#7ed800", "#55a600", "#2f7600", "#004800",
    "#ffff00", "#ffbf2e", "#ff8a16", "#ff4b00", "#b80000", "#ff00e8",
]
VELOCITY_COLORS = ["#173f9e", "#2864c7", "#58a6d9", "#a9d7e8", "#f4f4f4", "#f4b1b1", "#e66a6a", "#c52e45", "#8b102d"]
SEQUENTIAL_COLORS = ["#f7fbff", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"]
QUALITY_COLORS = ["#d9d9d9", "#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
PHASE_COLORS = ["#440154", "#414487", "#2a788e", "#22a884", "#7ad151", "#bddf26", "#fde725", "#fca636"]
RAIN_RATE_LABELS = np.asarray([0.1, 0.5, 1, 2, 5, 10, 20, 30, 50, 75, 100], dtype=float)
RAIN_RATE_COLORS = ["#d9d9d9", "#9ff7f1", "#63cfea", "#2f9df4", "#2362f1", "#a8ff00", "#55a600", "#ffff00", "#ffbf2e", "#ff4b00", "#b80000"]


def _spec(units, display_min, display_max, labels, colors, value_name=None, definition=None, kind="continuous"):
    return {
        "units": units,
        "display_min": display_min,
        "display_max": display_max,
        "labels": np.asarray(labels, dtype=float),
        "colors": list(colors),
        "value_name": value_name or units,
        "definition": definition or "radar field",
        "legend_kind": kind,
    }


FIELD_SPECS = {
    "dbz": _spec("dBZ", -10, 64, [-10, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64], REFLECTIVITY_COLORS, "Reflectivity", "Equivalent reflectivity factor"),
    "dbzv": _spec("dBZ", -10, 64, [-10, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64], REFLECTIVITY_COLORS, "Reflectivity (vertical)", "Vertical-polarized reflectivity"),
    "dbuz": _spec("dBZ", -10, 70, [-10, 0, 10, 20, 30, 40, 50, 60, 70], REFLECTIVITY_COLORS[:9], "Unattenuated reflectivity", "Unattenuated equivalent reflectivity factor"),
    "dbuzv": _spec("dBZ", -10, 70, [-10, 0, 10, 20, 30, 40, 50, 60, 70], REFLECTIVITY_COLORS[:9], "Unattenuated reflectivity (vertical)", "Vertical-polarized unattenuated reflectivity"),
    "v": _spec("m/s", -40, 40, [-40, -30, -20, -10, 0, 10, 20, 30, 40], VELOCITY_COLORS, "Radial velocity", "Radial Doppler velocity"),
    "w": _spec("m/s", 0, 8, [0, 1, 2, 3, 4, 5, 6, 7, 8], SEQUENTIAL_COLORS + ["#031b4e"], "Spectrum width", "Doppler spectrum width"),
    "zdr": _spec("dB", -8, 8, [-8, -6, -4, -2, 0, 2, 4, 6, 8], VELOCITY_COLORS, "Differential reflectivity", "Horizontal/vertical reflectivity difference"),
    "rhohv": _spec("", 0, 1, [0, .2, .4, .6, .8, 1], QUALITY_COLORS, "Correlation coefficient", "copolar correlation coefficient", "quality"),
    "ccor": _spec("", 0, 1, [0, .2, .4, .6, .8, 1], QUALITY_COLORS, "Correlation coefficient", "Correlation coefficient", "quality"),
    "sqi": _spec("", 0, 1, [0, .2, .4, .6, .8, 1], QUALITY_COLORS, "Signal quality index", "Signal quality index", "quality"),
    "mdqi": _spec("", 0, 1, [0, .2, .4, .6, .8, 1], QUALITY_COLORS, "Data quality index", "Meteorological data quality index", "quality"),
    "phidp": _spec("°", 0, 360, [0, 45, 90, 135, 180, 225, 270, 315, 360], PHASE_COLORS + ["#fee825"], "Differential phase", "Differential propagation phase", "phase"),
    "uphidp": _spec("°", 0, 360, [0, 45, 90, 135, 180, 225, 270, 315, 360], PHASE_COLORS + ["#fee825"], "Unwrapped differential phase", "Unwrapped differential propagation phase", "phase"),
    "kdp": _spec("°/km", -2, 8, [-2, -1, 0, 1, 2, 4, 6, 8], VELOCITY_COLORS[:8], "Specific differential phase", "Specific differential phase", "continuous"),
    "et": _spec("km", 0, 20, [0, 2, 4, 6, 8, 10, 12, 16, 20], SEQUENTIAL_COLORS + ["#031b4e"], "Echo top", "Echo-top height", "continuous"),
}


def normalize_field_name(field_name):
    return str(field_name or "unknown").strip().lower().replace(" ", "")


def field_spec(field_name):
    key = normalize_field_name(field_name)
    if key in FIELD_SPECS:
        return FIELD_SPECS[key], key
    return _spec("native", None, None, [], SEQUENTIAL_COLORS, str(field_name or "Field"), "Unclassified radar field", "unknown"), key


def apply_field_spec(product_data):
    existing_kind = product_data.get("legend_kind")
    if existing_kind == "rain_rate":
        product_data["value_units"] = "mm/h"
        product_data["value_name"] = "Rain rate"
        product_data["display_min"] = 0.1
        product_data["display_max"] = 100.0
        product_data["legend_labels"] = RAIN_RATE_LABELS
        product_data["legend_colors"] = RAIN_RATE_COLORS
        product_data["product_definition"] = "Z-R derived rain-rate estimate"
        product_data["peak_value"] = product_data.get("peak_value", product_data.get("peak_dbz"))
        return product_data

    spec, key = field_spec(product_data.get("field_name"))
    product_data["field_spec_key"] = key
    product_data["value_units"] = spec["units"]
    product_data["value_name"] = spec["value_name"]
    product_data["display_min"] = spec["display_min"]
    product_data["display_max"] = spec["display_max"]
    product_data["legend_labels"] = spec["labels"]
    product_data["legend_colors"] = spec["colors"]
    product_data["legend_kind"] = spec["legend_kind"]
    product_data["product_definition"] = product_data.get("product_definition") or spec["definition"]
    product_data["peak_value"] = product_data.get("peak_value", product_data.get("peak_dbz"))
    return product_data


def make_field_colormap(product_data):
    labels = np.asarray(product_data.get("legend_labels", []), dtype=float)
    colors = product_data.get("legend_colors", [])
    if labels.size < 2 or not colors:
        labels = np.linspace(0, 1, 8)
        colors = SEQUENTIAL_COLORS
    cmap = ListedColormap(colors, name=f"field_{product_data.get('field_spec_key', 'native')}")
    cmap.set_under((1.0, 1.0, 1.0, 0.0))
    cmap.set_over("#ff00e8")
    norm = BoundaryNorm(labels, cmap.N, extend="max")
    return cmap, norm
