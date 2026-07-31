import os
from pathlib import Path
from urllib.request import HTTPError, Request, URLError, urlopen

import cartopy
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
import cartopy.io.shapereader as shpreader
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import numpy as np
from pyproj import Transformer

from radar_products.config import *  # noqa: F403

class ConfigurableTiles(cimgt.GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return BASEMAP_TILE_URL.format(x=x, y=y, z=z)

    def get_image(self, tile):
        cached_file = None
        if self.cache_path is not None:
            filename = "_".join([str(i) for i in tile]) + ".npy"
            cached_file = self._cache_dir / filename

        if cached_file in self.cache:
            img = np.load(cached_file, allow_pickle=False)
            if is_cartopy_error_tile(img):
                cached_file.unlink(missing_ok=True)
                self.cache.discard(cached_file)
            else:
                return img, self.tileextent(tile), "lower"

        url = self._image_url(tile)
        try:
            request = Request(url, headers={"User-Agent": self.user_agent})
            with urlopen(request, timeout=20) as response:
                img = Image.open(BytesIO(response.read()))
            img = img.convert(self.desired_tile_form)
        except (HTTPError, URLError, TimeoutError) as err:
            print(f"{BASEMAP_TILE_PROVIDER} tile unavailable: {err}")
            img = Image.fromarray(
                np.full((256, 256, 3), (250, 250, 250), dtype=np.uint8)
            ).convert(self.desired_tile_form)
            return img, self.tileextent(tile), "lower"

        if cached_file is not None:
            np.save(cached_file, img, allow_pickle=False)
            self.cache.add(cached_file)

        return img, self.tileextent(tile), "lower"


def is_cartopy_error_tile(img):
    return (
        isinstance(img, np.ndarray)
        and img.shape == (256, 256, 3)
        and img.dtype == np.uint8
        and np.array_equal(img[0, 0], [250, 250, 250])
        and np.all(img == img[0, 0])
    )


def add_basemap_tiles(ax):
    BASEMAP_TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cartopy.config["cache_dir"] = str(BASEMAP_TILE_CACHE_DIR)
    tiler = ConfigurableTiles(
        user_agent=BASEMAP_TILE_USER_AGENT,
        cache=True,
    )
    ax.add_image(
        tiler,
        BASEMAP_TILE_ZOOM,
        interpolation=BASEMAP_TILE_INTERPOLATION,
        zorder=BASEMAP_TILE_ZORDER,
    )


def add_osm_attribution(ax):
    if not USE_BASEMAP_TILES:
        return

    ax.text(
        BASEMAP_ATTRIBUTION_X,
        BASEMAP_ATTRIBUTION_Y,
        BASEMAP_ATTRIBUTION_TEXT,
        transform=ax.transAxes,
        fontsize=BASEMAP_ATTRIBUTION_FONT_SIZE,
        ha="left",
        va="bottom",
        color="black",
        bbox={
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": BASEMAP_ATTRIBUTION_BOX_ALPHA,
            "pad": BASEMAP_ATTRIBUTION_BOX_PAD,
        },
        zorder=BASEMAP_ATTRIBUTION_ZORDER,
    )


def add_kecamatan_overlay(ax):
    if not SHOW_KECAMATAN_LABELS and not SHOW_KECAMATAN_BOUNDARIES:
        return

    extent = ax.get_extent(ccrs.Mercator.GOOGLE)
    label_candidates = []
    for shp_file in kecamatan_shp_files():
        if not shp_file.exists():
            continue

        reader = shpreader.Reader(str(shp_file))
        for record in reader.records():
            geometry = record.geometry
            if geometry is None:
                continue

            transformed = transform_geometry_to_mercator(geometry)
            if not intersects_extent(transformed.bounds, extent):
                continue

            if SHOW_KECAMATAN_BOUNDARIES:
                ax.add_geometries(
                    [transformed],
                    crs=ccrs.Mercator.GOOGLE,
                    facecolor="none",
                    edgecolor=KECAMATAN_BOUNDARY_COLOR,
                    linewidth=KECAMATAN_BOUNDARY_LINEWIDTH,
                    alpha=KECAMATAN_BOUNDARY_ALPHA,
                    zorder=KECAMATAN_BOUNDARY_ZORDER,
                )

            if SHOW_KECAMATAN_LABELS:
                label = str(record.attributes.get(KECAMATAN_NAME_FIELD, "")).strip()
                if label:
                    point = transformed.representative_point()
                    label_candidates.append((transformed.area, point.x, point.y, label))

    if SHOW_KECAMATAN_LABELS:
        add_non_overlapping_kecamatan_labels(ax, label_candidates)


def kecamatan_shp_files():
    if isinstance(KECAMATAN_SHP_FILES, (str, os.PathLike)):
        return [KECAMATAN_SHP_FILES]
    return KECAMATAN_SHP_FILES


def add_non_overlapping_kecamatan_labels(ax, candidates):
    axes_bbox = ax.get_window_extent()
    placed_bboxes = []
    placed_points = []
    grid_counts = {}
    for _, x, y, label in sorted(candidates, reverse=True):
        if len(placed_bboxes) >= KECAMATAN_LABEL_MAX_COUNT:
            break

        center = ax.transData.transform((x, y))
        grid_key = label_grid_key(center, axes_bbox)
        if grid_counts.get(grid_key, 0) >= KECAMATAN_LABEL_MAX_PER_GRID_CELL:
            continue

        if any(point_distance_px(center, point) < KECAMATAN_LABEL_MIN_DISTANCE_PX for point in placed_points):
            continue

        bbox = estimate_text_bbox_px(center, label, ax.figure.dpi)
        if not bbox_inside_axes(bbox, axes_bbox):
            continue
        if any(bboxes_overlap(bbox, placed) for placed in placed_bboxes):
            continue

        placed_bboxes.append(bbox)
        placed_points.append(center)
        grid_counts[grid_key] = grid_counts.get(grid_key, 0) + 1
        text = ax.text(
            x,
            y,
            label,
            transform=ccrs.Mercator.GOOGLE,
            ha="center",
            va="center",
            fontsize=KECAMATAN_LABEL_FONT_SIZE,
            color=KECAMATAN_LABEL_COLOR,
            alpha=KECAMATAN_LABEL_ALPHA,
            zorder=KECAMATAN_LABEL_ZORDER,
        )
        text.set_path_effects(
            [
                path_effects.Stroke(
                    linewidth=KECAMATAN_LABEL_OUTLINE_WIDTH,
                    foreground=KECAMATAN_LABEL_OUTLINE_COLOR,
                ),
                path_effects.Normal(),
            ]
        )


def estimate_text_bbox_px(center, label, figure_dpi):
    center_x, center_y = center
    font_px = KECAMATAN_LABEL_FONT_SIZE * figure_dpi / 72
    width = max(1, len(label)) * font_px * 0.6
    height = font_px * 1.4
    padding = KECAMATAN_LABEL_COLLISION_PADDING_PX
    return (
        center_x - width / 2 - padding,
        center_y - height / 2 - padding,
        center_x + width / 2 + padding,
        center_y + height / 2 + padding,
    )


def bboxes_overlap(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def bbox_inside_axes(bbox, axes_bbox):
    return (
        bbox[0] >= axes_bbox.x0
        and bbox[1] >= axes_bbox.y0
        and bbox[2] <= axes_bbox.x1
        and bbox[3] <= axes_bbox.y1
    )


def label_grid_key(center, axes_bbox):
    rel_x = max(0, center[0] - axes_bbox.x0)
    rel_y = max(0, center[1] - axes_bbox.y0)
    return (
        int(rel_x // KECAMATAN_LABEL_GRID_CELL_PX),
        int(rel_y // KECAMATAN_LABEL_GRID_CELL_PX),
    )


def point_distance_px(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def transform_geometry_to_mercator(geometry):
    from shapely.ops import transform as shapely_transform

    transformer = Transformer.from_proj("epsg:4326", "epsg:3857", always_xy=True)
    return shapely_transform(transformer.transform, geometry)


def intersects_extent(bounds, extent):
    min_x, min_y, max_x, max_y = bounds
    extent_min_x, extent_max_x, extent_min_y, extent_max_y = extent
    return not (
        max_x < extent_min_x
        or min_x > extent_max_x
        or max_y < extent_min_y
        or min_y > extent_max_y
    )


def add_map_guides(ax, radar_lon, radar_lat):
    plate_carree = ccrs.PlateCarree()
    gridlines = ax.gridlines(
        crs=plate_carree,
        draw_labels=True,
        linewidth=GRIDLINE_LINEWIDTH,
        color=GRIDLINE_COLOR,
        alpha=GRIDLINE_ALPHA,
        linestyle=GRIDLINE_STYLE,
    )
    gridlines.top_labels = False
    gridlines.right_labels = False
    gridlines.xlabel_style = {"size": GRIDLINE_LABEL_FONT_SIZE}
    gridlines.ylabel_style = {"size": GRIDLINE_LABEL_FONT_SIZE}

    wgs84_to_3857 = Transformer.from_proj("epsg:4326", "epsg:3857", always_xy=True)
    radar_x, radar_y = wgs84_to_3857.transform(radar_lon, radar_lat)
    ax.plot(
        radar_x,
        radar_y,
        marker="o",
        markersize=RADAR_MARKER_SIZE,
        markerfacecolor=RADAR_MARKER_FACE_COLOR,
        markeredgecolor=RADAR_MARKER_EDGE_COLOR,
        markeredgewidth=RADAR_MARKER_EDGE_WIDTH,
        transform=ccrs.Mercator.GOOGLE,
        zorder=RADAR_MARKER_ZORDER,
    )
