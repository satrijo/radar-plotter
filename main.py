import argparse
from pathlib import Path

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


def output_dir_for_time(time_label, output_root, data_file):
    parts = time_label.replace(" UTC", "").split()
    if len(parts) < 2:
        return output_root / data_file.stem
    date = parts[0].replace("-", "")
    start_clock = parts[1].split("-", 1)[0].replace(":", "")
    return output_root / date / start_clock[:4]


def print_scan_summary(data_file, time_label, radar_site, output_dir, slices):
    print(f"File: {data_file}")
    print(f"Time: {time_label}")
    print(f"Radar: {radar_site['name']} ({radar_site['lat']}, {radar_site['lon']})")
    print(f"Output dir: {output_dir}")
    print("Available elevations:")
    for item in slices:
        print(f"  {item['name']}: {item['elevation']:g} deg, {item['field']}, rays={item['rays']}, bins={item['bins']}")


def output_name_for_product(output_name, product_type):
    if product_type.lower() == "cmax":
        return output_name
    return output_name.replace("cmax", product_type.lower()).replace("CMAX", product_type.upper())


def run_once(data_file, output_root, product_type):
    data_file = Path(data_file)
    output_root = Path(output_root)
    radar_data = load_radar_file(data_file)
    time_label = radar_data["time_label"]
    run_output_dir = output_dir_for_time(time_label, output_root, data_file)
    print_scan_summary(data_file, time_label, radar_data["radar_site"], run_output_dir, radar_data["slices"])
    product_data = build_product(product_type, radar_data)
    product_data["source_file"] = str(data_file)
    output_stem = data_file.name
    source_suffixes = (
        (".vol.nc4", "_vol_nc4"),
        (".vol.nc", "_vol_nc"),
        (".nc4", "_nc4"),
        (".nc", "_nc"),
        (".vol", "_vol"),
        (".cmax", "_cmax"),
        (".cappi", "_cappi"),
        (".ppi", "_ppi"),
    )
    for suffix, source_label in source_suffixes:
        if output_stem.lower().endswith(suffix):
            output_stem = output_stem[:-len(suffix)] + source_label
            break
    image_name = output_name_for_product(OUTPUT_CMAX_IMAGE_NAME, product_type)
    image_file = run_output_dir / f"{Path(image_name).stem}_{output_stem}{Path(image_name).suffix}"
    netcdf_name = output_name_for_product(OUTPUT_CMAX_NETCDF_NAME, product_type)
    netcdf_file = run_output_dir / f"{Path(netcdf_name).stem}_{output_stem}{Path(netcdf_name).suffix}"
    gif_file = run_output_dir / f"elevations_{output_stem}.gif"
    if WRITE_CMAX_IMAGE:
        plot_product(product_data, image_file)
        print(f"Saved {product_type.upper()} image to {image_file}")
    if WRITE_CMAX_NETCDF:
        save_product_netcdf(product_data, netcdf_file)
        print(f"Saved {product_type.upper()} data to {netcdf_file}")
    if WRITE_ELEVATION_GIF and radar_data["slice_data_list"]:
        save_elevation_gif(radar_data["slice_data_list"], gif_file)
        print(f"Saved elevation GIF to {gif_file}")
    return image_file


def parse_args():
    parser = argparse.ArgumentParser(description="Generate radar products from a radar volume/product file")
    parser.add_argument("--input", type=Path, default=DATA_FILE, help="Radar input file")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Root output directory")
    parser.add_argument("--product", default=PRODUCT_TYPE, choices=("cmax", "ppi", "cappi", "pcappi", "sri"))
    return parser.parse_args()


def main():
    args = parse_args()
    run_once(args.input, args.output_dir, args.product)


if __name__ == "__main__":
    main()
