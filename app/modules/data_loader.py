# modules/data_loader.py
# Built in Session 01: the very first building block of the project.
# Keeps the "open a raster / open a boundary" pattern in one place so
# every later session (and app.py) can import it instead of repeating it.

import geopandas as gpd
import rasterio


def load_raster(path):
    """Open a raster file and return the dataset path for later use with rasterio.open()."""
    with rasterio.open(path) as src:
        print(f"Loaded raster: {path} ({src.width}x{src.height}, {src.count} band(s))")
    return path


def load_boundary(path):
    """Load a vector boundary file as a GeoDataFrame."""
    boundary = gpd.read_file(path)
    print(f"Loaded boundary: {path} ({len(boundary)} feature(s))")
    return boundary
