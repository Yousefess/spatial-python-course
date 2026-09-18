# modules/indices.py
# Built in Session 04: vectorized band math for NDVI (land cover factor)
# and NDWI (water exclusion mask), with safe division built in.

import numpy as np
import rasterio


def safe_divide(numerator, denominator):
    """Divide two arrays element-wise, returning 0 wherever the denominator is 0."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denominator != 0, numerator / denominator, 0)
    return result


def calculate_ndvi(red, nir):
    """Calculate NDVI from red and near-infrared bands."""
    return safe_divide(nir - red, nir + red)


def calculate_ndwi(green, nir):
    """Calculate NDWI from green and near-infrared bands."""
    return safe_divide(green - nir, green + nir)


def load_and_calculate_indices(sentinel_path, red_band, green_band, nir_band):
    """Read the required bands from a Sentinel file and return NDVI, NDWI, and the source profile."""
    with rasterio.open(sentinel_path) as src:
        red = src.read(red_band).astype("float32")
        green = src.read(green_band).astype("float32")
        nir = src.read(nir_band).astype("float32")
        profile = src.profile

    ndvi = calculate_ndvi(red, nir)
    ndwi = calculate_ndwi(green, nir)

    return ndvi, ndwi, profile
