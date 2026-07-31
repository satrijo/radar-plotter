from radar_products.config import (
    DATA_FILE,
    OUTPUT_CMAX_IMAGE_NAME,
    OUTPUT_CMAX_NETCDF_NAME,
    OUTPUT_DIR,
    OUTPUT_ELEVATION_GIF_NAME,
    PRODUCT_TYPE,
    WRITE_CMAX_IMAGE,
    WRITE_CMAX_NETCDF,
    WRITE_ELEVATION_GIF,
)
from radar_products.plotting import plot_product, save_elevation_gif, save_product_netcdf
from radar_products.products import build_product
from radar_products.source import load_radar_file


def output_dir_for_time(time_label):
    parts = time_label.replace(" UTC", "").split()
    if len(parts) < 2:
        return OUTPUT_DIR / DATA_FILE.stem

    date = parts[0].replace("-", "")
    start_clock = parts[1].split("-", 1)[0].replace(":", "")
    hour_minute = start_clock[:4]
    return OUTPUT_DIR / date / hour_minute


def print_scan_summary(data_file, time_label, radar_site, output_dir, slices):
    print(f"File: {data_file}")
    print(f"Time: {time_label}")
    print(f"Radar: {radar_site['name']} ({radar_site['lat']}, {radar_site['lon']})")
    print(f"Output dir: {output_dir}")
    print("Available elevations:")
    for item in slices:
        print(
            f"  {item['name']}: {item['elevation']:g} deg, "
            f"{item['field']}, rays={item['rays']}, bins={item['bins']}"
        )


def main():
    radar_data = load_radar_file(DATA_FILE)
    time_label = radar_data["time_label"]
    radar_site = radar_data["radar_site"]
    slices = radar_data["slices"]
    slice_data_list = radar_data["slice_data_list"]
    run_output_dir = output_dir_for_time(time_label)

    print_scan_summary(DATA_FILE, time_label, radar_site, run_output_dir, slices)

    product_data = build_product(PRODUCT_TYPE, radar_data)

    product_image_file = run_output_dir / output_name_for_product(OUTPUT_CMAX_IMAGE_NAME)
    product_netcdf_file = run_output_dir / output_name_for_product(OUTPUT_CMAX_NETCDF_NAME)
    elevation_gif_file = run_output_dir / OUTPUT_ELEVATION_GIF_NAME

    if WRITE_CMAX_IMAGE:
        plot_product(product_data, product_image_file)
        print(f"Saved {PRODUCT_TYPE.upper()} image to {product_image_file}")
    if WRITE_CMAX_NETCDF:
        save_product_netcdf(product_data, product_netcdf_file)
        print(f"Saved {PRODUCT_TYPE.upper()} data to {product_netcdf_file}")
    if WRITE_ELEVATION_GIF and slice_data_list:
        save_elevation_gif(slice_data_list, elevation_gif_file)
        print(f"Saved elevation GIF to {elevation_gif_file}")


def output_name_for_product(output_name):
    if PRODUCT_TYPE.lower() == "cmax":
        return output_name

    return output_name.replace("cmax", PRODUCT_TYPE.lower()).replace("CMAX", PRODUCT_TYPE.upper())


if __name__ == "__main__":
    main()
