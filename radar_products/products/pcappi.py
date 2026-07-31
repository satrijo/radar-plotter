from radar_products.products.cappi import build_cappi


def build_pcappi(
    slice_data_list,
    grid_resolution_km,
    time_label,
    radar_site,
    target_height_km,
):
    return build_cappi(
        slice_data_list,
        grid_resolution_km,
        time_label,
        radar_site,
        target_height_km,
        pseudo=True,
    )
