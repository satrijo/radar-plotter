import os
import textwrap
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from PIL import Image

from radar_products.config import *  # noqa: F403


def add_side_panel(panel_ax, product_data):
    radar_site = product_data["radar_site"]
    metadata = product_data["metadata"]
    draw_product_legend(panel_ax, product_data)
    add_side_panel_header(panel_ax, product_data, radar_site)
    value_units = product_data.get("value_units", "dBZ")

    panel_rows = [
        ("Source", metadata["source_file"]),
        ("Scan", metadata["scan_name"]),
        ("Strategy", metadata["scan_strategy"]),
        ("Clutter", metadata["clutter_filter"]),
        ("Time samp.", metadata["time_sampling"]),
        ("PRF", metadata["prf"]),
        ("Range", metadata["source_range"]),
        ("Range step", metadata["range_step"]),
        ("Data", metadata["data_types"]),
        ("Elev.", metadata["elevation_range"]),
        ("Peak", f"{product_data['peak_dbz']:.1f} {value_units}"),
        ("Radar", f"{radar_site['lon']:.3f}, {radar_site['lat']:.3f}"),
    ]

    y = SIDE_PANEL_TEXT_Y
    for key, value in panel_rows:
        wrapped_value = wrap_text(value, SIDE_PANEL_VALUE_WRAP_WIDTH)
        line_count = wrapped_value.count("\n") + 1
        panel_ax.text(
            SIDE_PANEL_KEY_X,
            y,
            f"{key}:",
            transform=panel_ax.transAxes,
            ha="left",
            va="top",
            fontsize=SIDE_PANEL_ROW_FONT_SIZE,
        )
        panel_ax.text(
            SIDE_PANEL_VALUE_X,
            y,
            wrapped_value,
            transform=panel_ax.transAxes,
            ha="left",
            va="top",
            fontsize=SIDE_PANEL_ROW_FONT_SIZE,
            linespacing=0.9,
        )
        y -= SIDE_PANEL_ROW_BASE_STEP + SIDE_PANEL_ROW_LINE_STEP * line_count


def add_side_panel_header(panel_ax, cmax_data, radar_site):
    add_side_panel_logo(panel_ax)
    title = SIDE_PANEL_HEADER_TITLE_TEXT or (
        f"{cmax_data.get('product_label', 'CMAX')} ({cmax_data['field_name']})"
    )
    subtitle = SIDE_PANEL_HEADER_SUBTITLE_TEXT or (
        f"{cmax_data['scan_time_label']}\n{radar_site['name']}"
    )
    title = wrap_text(title, SIDE_PANEL_HEADER_TITLE_WRAP_WIDTH)
    subtitle = wrap_text(subtitle, SIDE_PANEL_HEADER_SUBTITLE_WRAP_WIDTH)
    title_lines = title.count("\n") + 1
    subtitle_y = (
        SIDE_PANEL_TITLE_Y
        - SIDE_PANEL_HEADER_LINE_STEP * title_lines
        - SIDE_PANEL_HEADER_SUBTITLE_GAP
    )

    panel_ax.text(
        SIDE_PANEL_TITLE_X,
        SIDE_PANEL_TITLE_Y,
        title,
        transform=panel_ax.transAxes,
        ha="center",
        va="top",
        fontsize=SIDE_PANEL_TITLE_FONT_SIZE,
        fontweight="bold",
    )
    panel_ax.text(
        SIDE_PANEL_TIME_X,
        subtitle_y,
        subtitle,
        transform=panel_ax.transAxes,
        ha="center",
        va="top",
        fontsize=SIDE_PANEL_TIME_FONT_SIZE,
        fontweight="bold",
    )


def add_side_panel_logo(panel_ax):
    if not SIDE_PANEL_LOGO_PATH:
        return

    logo_path = os.fspath(SIDE_PANEL_LOGO_PATH)
    if not os.path.exists(logo_path):
        return

    image = Image.open(logo_path).convert("RGBA")
    width, height = side_panel_logo_size(panel_ax, image)
    image = resize_logo_for_output(panel_ax, image, width, height)
    x0 = SIDE_PANEL_LOGO_X - width / 2
    x1 = SIDE_PANEL_LOGO_X + width / 2
    y0 = SIDE_PANEL_LOGO_Y - height
    y1 = SIDE_PANEL_LOGO_Y
    panel_ax.imshow(
        image,
        extent=(x0, x1, y0, y1),
        transform=panel_ax.transAxes,
        zorder=SIDE_PANEL_LOGO_ZORDER,
        interpolation=SIDE_PANEL_LOGO_INTERPOLATION,
    )


def side_panel_logo_size(panel_ax, image):
    axes_bbox = panel_ax.get_window_extent()
    image_width, image_height = image.size
    image_ratio = image_height / image_width
    axes_ratio = axes_bbox.width / axes_bbox.height
    height = SIDE_PANEL_LOGO_WIDTH * image_ratio * axes_ratio
    width = SIDE_PANEL_LOGO_WIDTH

    if height > SIDE_PANEL_LOGO_HEIGHT:
        width *= SIDE_PANEL_LOGO_HEIGHT / height
        height = SIDE_PANEL_LOGO_HEIGHT

    return width, height


def resize_logo_for_output(panel_ax, image, width, height):
    axes_bbox = panel_ax.get_window_extent()
    target_size = (
        max(1, int(round(width * axes_bbox.width))),
        max(1, int(round(height * axes_bbox.height))),
    )
    if image.size == target_size:
        return image

    return image.resize(target_size, logo_resample_filter())


def logo_resample_filter():
    filters = {
        "nearest": Image.Resampling.NEAREST,
        "box": Image.Resampling.BOX,
        "bilinear": Image.Resampling.BILINEAR,
        "hamming": Image.Resampling.HAMMING,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    return filters.get(SIDE_PANEL_LOGO_RESAMPLE, Image.Resampling.LANCZOS)


def draw_product_legend(panel_ax, product_data):
    if product_data.get("legend_kind") == "rain_rate":
        draw_equal_interval_legend(
            panel_ax,
            RAIN_RATE_COLORS,
            RAIN_RATE_LABELS,
            "mm/h",
        )
        return

    draw_equal_interval_legend(
        panel_ax,
        REFLECTIVITY_COLORS,
        REFLECTIVITY_LABELS,
        "dBZ",
    )


def draw_equal_reflectivity_legend(panel_ax):
    draw_equal_interval_legend(
        panel_ax,
        REFLECTIVITY_COLORS,
        REFLECTIVITY_LABELS,
        "dBZ",
    )


def draw_equal_interval_legend(panel_ax, colors, labels, unit_label):
    x0 = SIDE_PANEL_LEGEND_X
    y0 = SIDE_PANEL_LEGEND_Y
    width = SIDE_PANEL_LEGEND_WIDTH
    height = SIDE_PANEL_LEGEND_HEIGHT
    step = height / len(colors)

    for index, color in enumerate(colors):
        y = y0 + index * step
        panel_ax.add_patch(
            Rectangle(
                (x0, y),
                width,
                step,
                transform=panel_ax.transAxes,
                facecolor=color,
                edgecolor="none",
            )
        )

    panel_ax.add_patch(
        Rectangle(
            (x0, y0),
            width,
            height,
            transform=panel_ax.transAxes,
            facecolor="none",
            edgecolor="black",
            linewidth=LEGEND_BORDER_LINEWIDTH,
        )
    )

    label_x = x0 + width + LEGEND_LABEL_GAP
    for index, value in enumerate(labels):
        y = y0 + index * step
        panel_ax.plot(
            [x0 + width, x0 + width + LEGEND_TICK_LENGTH],
            [y, y],
            transform=panel_ax.transAxes,
            color="black",
            linewidth=LEGEND_BORDER_LINEWIDTH,
        )
        panel_ax.text(
            label_x,
            y,
            format_legend_label(value, unit_label),
            transform=panel_ax.transAxes,
            ha="left",
            va="center",
            fontsize=LEGEND_LABEL_FONT_SIZE,
        )


def format_legend_label(value, unit_label):
    if float(value).is_integer():
        value_text = str(int(value))
    else:
        value_text = f"{value:g}"

def wrap_text(value, width):
    text = str(value).replace(",", ", ")
    wrapped = textwrap.wrap(
        text,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return "\n".join(wrapped)
