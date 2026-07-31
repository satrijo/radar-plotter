from netCDF4 import Dataset

from radar_products.metadata import get_product_metadata
from radar_products.netcdf_reader import get_radar_site, get_time_label, list_slices, read_slice
from radar_products.rainbow_reader import read_rainbow_cmax, read_rainbow_volume

RAINBOW_VOLUME_SUFFIXES = {".vol", ".azi"}
RAINBOW_PRODUCT_SUFFIXES = {".cmax", ".cappi", ".ppi"}
NETCDF_SUFFIXES = {".nc", ".nc4", ".cdf", ".netcdf"}


def load_radar_file(path):
    suffix = normalized_suffix(path)
    if suffix in NETCDF_SUFFIXES:
        return load_netcdf_volume(path)
    if suffix in RAINBOW_VOLUME_SUFFIXES:
        return read_rainbow_volume(path)
    if suffix in RAINBOW_PRODUCT_SUFFIXES:
        return read_rainbow_cmax(path)
    raise ValueError(
        f"Unsupported radar file extension {suffix!r}. "
        f"Supported: {sorted(NETCDF_SUFFIXES | RAINBOW_VOLUME_SUFFIXES | RAINBOW_PRODUCT_SUFFIXES)}"
    )


def load_netcdf_volume(path):
    with Dataset(path) as nc:
        slices = list_slices(nc)
        time_label = get_time_label(nc)
        radar_site = get_radar_site(nc)
        product_metadata = get_product_metadata(nc, path.name)
        slice_data_list = [read_slice(nc, item["name"]) for item in slices]

    for slice_data in slice_data_list:
        slice_data["time_label"] = time_label
        slice_data["radar_site"] = radar_site
        slice_data["metadata"] = product_metadata

    return {
        "file_type": "netcdf-volume",
        "time_label": time_label,
        "radar_site": radar_site,
        "metadata": product_metadata,
        "slices": slices,
        "slice_data_list": slice_data_list,
        "prebuilt_cmax": None,
    }


def normalized_suffix(path):
    name = path.name.lower()
    for suffix in (".vol.nc4", ".vol.nc", ".nc4", ".nc"):
        if name.endswith(suffix):
            return suffix.rsplit(".vol", 1)[-1]
    return path.suffix.lower()
