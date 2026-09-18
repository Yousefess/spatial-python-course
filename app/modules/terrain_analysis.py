# modules/terrain_analysis.py
# Built in Session 05: slope and aspect from the DEM's gradient, with
# the flat-area sentinel value (-1) handled explicitly for aspect.

import numpy as np
import rasterio


def calculate_slope(dx, dy):
    """Calculate slope in degrees from x and y gradients."""
    slope_radians = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.degrees(slope_radians)


def calculate_aspect(dx, dy, flat_threshold=0.1, slope=None):
    """Calculate aspect in degrees (0-360, 0 = north, clockwise) from x and y gradients.
    Flat pixels (slope below flat_threshold) are marked as -1."""
    aspect_radians = np.arctan2(dy, -dx)
    aspect_degrees = np.degrees(aspect_radians)
    aspect_degrees = (90 - aspect_degrees) % 360

    if slope is not None:
        aspect_degrees[slope < flat_threshold] = -1

    return aspect_degrees


def load_and_calculate_terrain(dem_path):
    """Read a DEM and return slope, aspect, and the source profile.
    Converts pixel resolution from degrees to an approximate meters value
    if the DEM's CRS is geographic."""
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype("float32")
        transform = src.transform
        crs = src.crs
        bounds = src.bounds
        profile = src.profile

    if crs.is_geographic:
        center_latitude = (bounds.top + bounds.bottom) / 2
        meters_per_degree_lat = 111320
        meters_per_degree_lon = 111320 * np.cos(np.radians(center_latitude))
        x_resolution = transform.a * meters_per_degree_lon
        y_resolution = abs(transform.e) * meters_per_degree_lat
    else:
        x_resolution = transform.a
        y_resolution = abs(transform.e)

    dy, dx = np.gradient(dem, y_resolution, x_resolution)
    slope = calculate_slope(dx, dy)
    aspect = calculate_aspect(dx, dy, slope=slope)

    return slope, aspect, profile
