"""Radar product processing and plotting helpers."""

import os

from radar_products.config import MPLCONFIG_DIR

os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR.resolve()))
