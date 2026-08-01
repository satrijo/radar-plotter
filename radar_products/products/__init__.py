from radar_products.config import (
    CAPPI_HEIGHT_KM,
    GRID_RESOLUTION_KM,
    PCAPPI_HEIGHT_KM,
    PPI_ELEVATION_DEG,
    SRI_ELEVATION_DEG,
)
from radar_products.field_specs import apply_field_spec
from radar_products.products.cappi import build_cappi
from radar_products.products.cmax import build_cmax
from radar_products.products.pcappi import build_pcappi
from radar_products.products.ppi import build_ppi, select_nearest_elevation
from radar_products.products.sri import build_sri

SUPPORTED_PRODUCTS = ("cmax", "ppi", "cappi", "pcappi", "sri")


def finalize_product(product_data, product_type):
    product_data["product_type"] = product_type
    field_name = str(product_data.get("field_name", "Field"))
    field_key = field_name.lower().replace(" ", "")
    if product_type == "cmax":
        reflectivity = field_key in {"dbz", "dbzv", "dbuz", "dbuzv"}
        product_data["product_label"] = "CMAX" if reflectivity else f"MAX {field_name}"
        product_data["product_definition"] = (
            "maximum reflectivity across elevations" if reflectivity
            else f"maximum {field_name} across elevations"
        )
    elif product_type == "ppi":
        product_data["product_definition"] = "plan position indicator at nearest configured elevation"
    elif product_type == "cappi":
        product_data["product_definition"] = "constant-altitude plan position indicator with vertical interpolation"
    elif product_type == "pcappi":
        product_data["product_definition"] = "pseudo-CAPPI using nearest available beam"
    elif product_type == "sri":
        product_data["product_definition"] = "Z-R derived rain-rate estimate"
    return apply_field_spec(product_data)


def build_product(product_type, radar_data):
    product_type = product_type.lower()
    slice_data_list = radar_data["slice_data_list"]
    if product_type == "cmax":
        if radar_data["prebuilt_cmax"] is not None:
            product_data = radar_data["prebuilt_cmax"]
        else:
            product_data = build_cmax(
                slice_data_list,
                GRID_RESOLUTION_KM,
                radar_data["time_label"],
                radar_data["radar_site"],
            )
        product_data["metadata"] = radar_data["metadata"]
        return finalize_product(product_data, product_type)

    if product_type == "ppi":
        slice_data = select_nearest_elevation(slice_data_list, PPI_ELEVATION_DEG)
        return finalize_product(build_ppi(slice_data), product_type)

    if product_type == "cappi":
        return finalize_product(build_cappi(
            slice_data_list, GRID_RESOLUTION_KM, radar_data["time_label"],
            radar_data["radar_site"], CAPPI_HEIGHT_KM, pseudo=False,
        ), product_type)

    if product_type == "pcappi":
        return finalize_product(build_pcappi(
            slice_data_list, GRID_RESOLUTION_KM, radar_data["time_label"],
            radar_data["radar_site"], PCAPPI_HEIGHT_KM,
        ), product_type)

    if product_type == "sri":
        slice_data = select_nearest_elevation(slice_data_list, SRI_ELEVATION_DEG)
        return finalize_product(build_sri(slice_data), product_type)

    supported = ", ".join(SUPPORTED_PRODUCTS)
    raise ValueError(f"Unsupported PRODUCT_TYPE {product_type!r}. Supported: {supported}")
