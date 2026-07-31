from radar_products.config import (
    CAPPI_HEIGHT_KM,
    GRID_RESOLUTION_KM,
    PCAPPI_HEIGHT_KM,
    PPI_ELEVATION_DEG,
    SRI_ELEVATION_DEG,
)
from radar_products.products.cappi import build_cappi
from radar_products.products.cmax import build_cmax
from radar_products.products.pcappi import build_pcappi
from radar_products.products.ppi import build_ppi, select_nearest_elevation
from radar_products.products.sri import build_sri


SUPPORTED_PRODUCTS = ("cmax", "ppi", "cappi", "pcappi", "sri")


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
        return product_data

    if product_type == "ppi":
        slice_data = select_nearest_elevation(slice_data_list, PPI_ELEVATION_DEG)
        return build_ppi(slice_data)

    if product_type == "cappi":
        return build_cappi(
            slice_data_list,
            GRID_RESOLUTION_KM,
            radar_data["time_label"],
            radar_data["radar_site"],
            CAPPI_HEIGHT_KM,
            pseudo=False,
        )

    if product_type == "pcappi":
        return build_pcappi(
            slice_data_list,
            GRID_RESOLUTION_KM,
            radar_data["time_label"],
            radar_data["radar_site"],
            PCAPPI_HEIGHT_KM,
        )

    if product_type == "sri":
        slice_data = select_nearest_elevation(slice_data_list, SRI_ELEVATION_DEG)
        return build_sri(slice_data)

    supported = ", ".join(SUPPORTED_PRODUCTS)
    raise ValueError(f"Unsupported PRODUCT_TYPE {product_type!r}. Supported: {supported}")
