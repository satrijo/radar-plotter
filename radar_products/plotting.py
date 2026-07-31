import os
import textwrap
from io import BytesIO
from urllib.request import HTTPError, Request, URLError, urlopen

from radar_products.config import MPLCONFIG_DIR

os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR.resolve()))

import matplotlib

matplotlib.use("Agg")
import cartopy  # noqa: E402
import cartopy.crs as ccrs  # noqa: E402
import cartopy.io.img_tiles as cimgt  # noqa: E402
import cartopy.io.shapereader as shpreader  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as path_effects  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from netCDF4 import Dataset  # noqa: E402
from PIL import Image  # noqa: E402
from pyproj import Transformer  # noqa: E402

from radar_products.config import (
    FOOTER_COLOR,
    FOOTER_FONT_SIZE,
    FOOTER_TEXT,
    FOOTER_X,
    FOOTER_Y,
    CMAX_IMAGE_DPI,
    CMAX_MAX_HEIGHT_KM,
    CMAX_MIN_HEIGHT_KM,
    CMAX_RANGE_X_KM,
    CMAX_RANGE_Y_KM,
    DATA_FILE,
    DISPLAY_MIN_DBZ,
    DISPLAY_SMOOTH_SIGMA,
    ELEVATION_GIF_DPI,
    ELEVATION_GIF_FRAME_MS,
    FIGURE_GRID_WIDTH_RATIOS,
    FIGURE_GRID_WSPACE,
    FIGURE_SIZE,
    FIGURE_SUBPLOTS_ADJUST,
    GRIDLINE_ALPHA,
    GRIDLINE_COLOR,
    GRIDLINE_LABEL_FONT_SIZE,
    GRIDLINE_LINEWIDTH,
    GRIDLINE_STYLE,
    KECAMATAN_BOUNDARY_ALPHA,
    KECAMATAN_BOUNDARY_COLOR,
    KECAMATAN_BOUNDARY_LINEWIDTH,
    KECAMATAN_BOUNDARY_ZORDER,
    KECAMATAN_LABEL_ALPHA,
    KECAMATAN_LABEL_COLOR,
    KECAMATAN_LABEL_COLLISION_PADDING_PX,
    KECAMATAN_LABEL_FONT_SIZE,
    KECAMATAN_LABEL_GRID_CELL_PX,
    KECAMATAN_LABEL_MAX_COUNT,
    KECAMATAN_LABEL_MAX_PER_GRID_CELL,
    KECAMATAN_LABEL_MIN_DISTANCE_PX,
    KECAMATAN_LABEL_OUTLINE_COLOR,
    KECAMATAN_LABEL_OUTLINE_WIDTH,
    KECAMATAN_LABEL_ZORDER,
    KECAMATAN_NAME_FIELD,
    KECAMATAN_SHP_FILES,
    LEGEND_BORDER_LINEWIDTH,
    LEGEND_LABEL_FONT_SIZE,
    LEGEND_LABEL_GAP,
    LEGEND_TICK_LENGTH,
    MAP_FACE_COLOR,
    MPLCONFIG_DIR,
    BASEMAP_ATTRIBUTION_BOX_ALPHA,
    BASEMAP_ATTRIBUTION_BOX_PAD,
    BASEMAP_ATTRIBUTION_FONT_SIZE,
    BASEMAP_ATTRIBUTION_TEXT,
    BASEMAP_ATTRIBUTION_X,
    BASEMAP_ATTRIBUTION_Y,
    BASEMAP_ATTRIBUTION_ZORDER,
    BASEMAP_TILE_CACHE_DIR,
    BASEMAP_TILE_INTERPOLATION,
    BASEMAP_TILE_PROVIDER,
    BASEMAP_TILE_URL,
    BASEMAP_TILE_USER_AGENT,
    BASEMAP_TILE_ZOOM,
    BASEMAP_TILE_ZORDER,
    PLOT_RANGE_X_KM,
    PLOT_RANGE_Y_KM,
    RADAR_OVERLAY_ALPHA,
    RADAR_IMAGE_ZORDER,
    RADAR_MARKER_EDGE_COLOR,
    RADAR_MARKER_EDGE_WIDTH,
    RADAR_MARKER_FACE_COLOR,
    RADAR_MARKER_SIZE,
    RADAR_MARKER_ZORDER,
    REFLECTIVITY_BOUNDS,
    REFLECTIVITY_COLORS,
    REFLECTIVITY_LABELS,
    REFLECTIVITY_OVER_COLOR,
    RAIN_RATE_BOUNDS,
    RAIN_RATE_COLORS,
    RAIN_RATE_LABELS,
    RAIN_RATE_OVER_COLOR,
    RANGE_UNIT_TO_METER,
    SIDE_PANEL_LEGEND_HEIGHT,
    SIDE_PANEL_LEGEND_WIDTH,
    SIDE_PANEL_LEGEND_X,
    SIDE_PANEL_LEGEND_Y,
    SIDE_PANEL_HEADER_SUBTITLE_TEXT,
    SIDE_PANEL_HEADER_SUBTITLE_GAP,
    SIDE_PANEL_HEADER_SUBTITLE_WRAP_WIDTH,
    SIDE_PANEL_HEADER_TITLE_TEXT,
    SIDE_PANEL_HEADER_TITLE_WRAP_WIDTH,
    SIDE_PANEL_HEADER_LINE_STEP,
    SIDE_PANEL_KEY_X,
    SIDE_PANEL_LOGO_HEIGHT,
    SIDE_PANEL_LOGO_INTERPOLATION,
    SIDE_PANEL_LOGO_PATH,
    SIDE_PANEL_LOGO_RESAMPLE,
    SIDE_PANEL_LOGO_WIDTH,
    SIDE_PANEL_LOGO_X,
    SIDE_PANEL_LOGO_Y,
    SIDE_PANEL_LOGO_ZORDER,
    SIDE_PANEL_ROW_BASE_STEP,
    SIDE_PANEL_ROW_FONT_SIZE,
    SIDE_PANEL_ROW_LINE_STEP,
    SIDE_PANEL_TEXT_Y,
    SIDE_PANEL_TIME_FONT_SIZE,
    SIDE_PANEL_TIME_X,
    SIDE_PANEL_TIME_Y,
    SIDE_PANEL_TITLE_FONT_SIZE,
    SIDE_PANEL_TITLE_X,
    SIDE_PANEL_TITLE_Y,
    SIDE_PANEL_VALUE_X,
    SIDE_PANEL_VALUE_WRAP_WIDTH,
    SHOW_KECAMATAN_BOUNDARIES,
    SHOW_KECAMATAN_LABELS,
    TITLE_FONT_SIZE,
    TRANSPARENT_COLOR,
    USE_BASEMAP_TILES,
)
from radar_products.processing import smooth_masked_field
from radar_products.map_layers import add_basemap_tiles, add_kecamatan_overlay, add_map_guides, add_osm_attribution
from radar_products.annotations import (
    add_side_panel,
    draw_product_legend,
)
from radar_products.products.ppi import build_ppi


def save_elevation_gif(slice_data_list, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frames = [render_elevation_frame(slice_data) for slice_data in slice_data_list]
    if not frames:
        return

    frames[0].save(
        output_file,
        save_all=True,
        append_images=frames[1:],
        duration=ELEVATION_GIF_FRAME_MS,
        loop=0,
        optimize=True,
    )


def render_elevation_frame(slice_data):
    elevation_data = build_ppi(slice_data)
    display_field = np.ma.masked_less(elevation_data["field"], DISPLAY_MIN_DBZ)
    cmap, norm = make_reflectivity_colormap()
    cmap.set_bad(TRANSPARENT_COLOR)

    radar_site = elevation_data["radar_site"]
    radar_lon = radar_site["lon"]
    radar_lat = radar_site["lat"]
    map_crs = ccrs.Mercator.GOOGLE

    fig, ax, panel_ax = create_map_figure(map_crs)
    set_centered_extent(
        ax,
        map_crs,
        radar_lon,
        radar_lat,
        PLOT_RANGE_X_KM * RANGE_UNIT_TO_METER,
        PLOT_RANGE_Y_KM * RANGE_UNIT_TO_METER,
    )

    draw_map_base(ax)
    add_kecamatan_overlay(ax)
    ax.imshow(
        display_field,
        origin="lower",
        extent=radar_km_to_mercator_extent(
            radar_lon, radar_lat, elevation_data["extent"]
        ),
        transform=map_crs,
        cmap=cmap,
        norm=norm,
        alpha=RADAR_OVERLAY_ALPHA,
        zorder=RADAR_IMAGE_ZORDER,
        interpolation="nearest",
    )

    ax.set_title(
        f"{slice_data['field_name']} {slice_data['name']} {elevation_data['time_label']}\n"
        f"{radar_site['name']} - elevation {slice_data['elevation']:g} deg",
        fontsize=TITLE_FONT_SIZE,
        loc="left",
    )
    add_map_guides(ax, radar_lon, radar_lat)
    add_osm_attribution(ax)
    add_side_panel(panel_ax, elevation_data)
    add_footer(fig)

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=ELEVATION_GIF_DPI)
    plt.close(fig)
    buffer.seek(0)
    return Image.open(buffer).convert("P", palette=Image.Palette.ADAPTIVE)


def plot_product(product_data, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    display_min = product_data.get("display_min", DISPLAY_MIN_DBZ)
    display_field = np.ma.masked_less(product_data["field"], display_min)
    display_field = smooth_masked_field(display_field, DISPLAY_SMOOTH_SIGMA)
    display_field = np.ma.masked_less(display_field, display_min)
    cmap, norm = make_product_colormap(product_data)
    cmap.set_bad(TRANSPARENT_COLOR)

    radar_site = product_data["radar_site"]
    radar_lon = radar_site["lon"]
    radar_lat = radar_site["lat"]
    map_crs = ccrs.Mercator.GOOGLE

    fig, ax, panel_ax = create_map_figure(map_crs)
    set_centered_extent(
        ax,
        map_crs,
        radar_lon,
        radar_lat,
        PLOT_RANGE_X_KM * RANGE_UNIT_TO_METER,
        PLOT_RANGE_Y_KM * RANGE_UNIT_TO_METER,
    )

    draw_map_base(ax)
    add_kecamatan_overlay(ax)
    ax.imshow(
        display_field,
        origin="lower",
        extent=radar_km_to_mercator_extent(radar_lon, radar_lat, product_data["extent"]),
        transform=map_crs,
        cmap=cmap,
        norm=norm,
        alpha=RADAR_OVERLAY_ALPHA,
        zorder=RADAR_IMAGE_ZORDER,
        interpolation="nearest",
    )

    elevations = product_data["elevations"]
    min_height, max_height = product_data.get("height_range_km", (np.nan, np.nan))
    if np.isfinite(min_height) and np.isfinite(max_height) and np.isclose(min_height, max_height):
        elevation_text = f"height {min_height:g} km"
    elif len(elevations) == 1:
        elevation_text = f"elevation {elevations[0]:g} deg"
    elif elevations:
        elevation_text = (
            f"{len(elevations)} elevations, "
            f"{CMAX_MIN_HEIGHT_KM:g}-{CMAX_MAX_HEIGHT_KM:g} km, up to {max(elevations):g} deg"
        )
    else:
        elevation_text = product_data.get("product_label", "CMAX")
    ax.set_title(
        f"{product_data.get('product_label', 'PRODUCT')} {product_data['field_name']} {product_data['time_label']}\n"
        f"{radar_site['name']} - {elevation_text}",
        fontsize=TITLE_FONT_SIZE,
        loc="left",
    )
    add_map_guides(ax, radar_lon, radar_lat)
    add_osm_attribution(ax)
    add_side_panel(panel_ax, product_data)
    add_footer(fig)
    fig.savefig(output_file, dpi=CMAX_IMAGE_DPI)
    plt.close(fig)


def plot_cmax(cmax_data, output_file):
    plot_product(cmax_data, output_file)


def create_map_figure(map_crs):
    fig = plt.figure(figsize=FIGURE_SIZE, constrained_layout=False)
    grid = GridSpec(
        1,
        2,
        figure=fig,
        width_ratios=FIGURE_GRID_WIDTH_RATIOS,
        wspace=FIGURE_GRID_WSPACE,
    )
    ax = fig.add_subplot(grid[0, 0], projection=map_crs)
    panel_ax = fig.add_subplot(grid[0, 1])
    ax.set_anchor("C")
    panel_ax.set_anchor("C")
    panel_ax.axis("off")
    fig.subplots_adjust(**FIGURE_SUBPLOTS_ADJUST)
    return fig, ax, panel_ax


def draw_map_base(ax):
    ax.set_facecolor(MAP_FACE_COLOR)
    if USE_BASEMAP_TILES:
        add_basemap_tiles(ax)


def set_centered_extent(ax, map_crs, radar_lon, radar_lat, range_x_m, range_y_m):
    center_x, center_y = map_crs.transform_point(
        radar_lon, radar_lat, ccrs.PlateCarree()
    )
    set_map_extent(ax, map_crs, center_x, center_y, range_x_m, range_y_m)


def set_map_extent(ax, map_crs, center_x, center_y, range_x_m, range_y_m):
    set_extent = getattr(ax, "set_extent")
    set_extent(
        [
            center_x - range_x_m,
            center_x + range_x_m,
            center_y - range_y_m,
            center_y + range_y_m,
        ],
        crs=map_crs,
    )


def radar_km_to_mercator_extent(radar_lon, radar_lat, extent_km):
    ae_proj = (
        f"+proj=aeqd +lat_0={radar_lat} +lon_0={radar_lon} +R=6371000 +units=m +no_defs"
    )
    ae_to_merc = Transformer.from_proj(ae_proj, "epsg:3857", always_xy=True)
    x_min_km, x_max_km, y_min_km, y_max_km = extent_km
    corners = [
        (x_min_km, y_min_km),
        (x_max_km, y_min_km),
        (x_max_km, y_max_km),
        (x_min_km, y_max_km),
    ]
    xs = []
    ys = []
    for x_km, y_km in corners:
        x, y = ae_to_merc.transform(x_km * RANGE_UNIT_TO_METER, y_km * RANGE_UNIT_TO_METER)
        xs.append(x)
        ys.append(y)
    return (min(xs), max(xs), min(ys), max(ys))


def make_reflectivity_colormap():
    cmap = ListedColormap(REFLECTIVITY_COLORS, name="bmkg_reflectivity")
    cmap.set_under(TRANSPARENT_COLOR)
    cmap.set_over(REFLECTIVITY_OVER_COLOR)
    norm = BoundaryNorm(REFLECTIVITY_BOUNDS, cmap.N, extend="max")
    return cmap, norm


def make_product_colormap(product_data):
    if product_data.get("legend_kind") == "rain_rate":
        cmap = ListedColormap(RAIN_RATE_COLORS, name="bmkg_rain_rate")
        cmap.set_under(TRANSPARENT_COLOR)
        cmap.set_over(RAIN_RATE_OVER_COLOR)
        norm = BoundaryNorm(RAIN_RATE_BOUNDS, cmap.N, extend="max")
        return cmap, norm

    return make_reflectivity_colormap()

    return f"{value_text} {unit_label}"




def add_footer(fig):
    fig.text(
        FOOTER_X,
        FOOTER_Y,
        FOOTER_TEXT,
        ha="left",
        va="bottom",
        fontsize=FOOTER_FONT_SIZE,
        color=FOOTER_COLOR,
    )


def save_product_netcdf(product_data, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    variable_name = product_data.get("product_label", "PRODUCT").upper().replace(" ", "_")

    with Dataset(output_file, "w") as nc:
        nc.createDimension("y", product_data["field"].shape[0])
        nc.createDimension("x", product_data["field"].shape[1])

        x_var = nc.createVariable("x", "f4", ("x",))
        y_var = nc.createVariable("y", "f4", ("y",))
        product_var = nc.createVariable(
            variable_name,
            "f4",
            ("y", "x"),
            fill_value=-9999.0,
            zlib=True,
        )

        x_var[:] = product_data["x_km"]
        y_var[:] = product_data["y_km"]
        product_var[:] = product_data["field"].filled(-9999.0)

        x_var.units = "km"
        y_var.units = "km"
        product_var.units = product_data.get("value_units", "dBZ")
        product_var.long_name = product_data.get("product_label", variable_name)

        nc.source_file = product_data.get("source_file", str(DATA_FILE))
        nc.product_type = product_data.get("product_label", variable_name)
        nc.grid_resolution_km = product_data["grid_resolution_km"]
        nc.elevations_degrees = ",".join(
            f"{value:g}" for value in product_data["elevations"]
        )
        nc.time = product_data["time_label"]
        nc.method = product_data.get("method", "bilinear Cartesian-to-polar sampling")
        nc.range_x_km = CMAX_RANGE_X_KM
        nc.range_y_km = CMAX_RANGE_Y_KM
        nc.min_height_km = product_data["height_range_km"][0]
        nc.max_height_km = product_data["height_range_km"][1]
        nc.radar_name = product_data["radar_site"]["name"]
        nc.radar_latitude = product_data["radar_site"]["lat"]
        nc.radar_longitude = product_data["radar_site"]["lon"]


def save_cmax_netcdf(cmax_data, output_file):
    save_product_netcdf(cmax_data, output_file)
