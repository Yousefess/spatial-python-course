# modules/spatial_analysis.py
# Built in Session 06: dissolve, spatial join, buffer + union, and
# rasterizing the resulting access zone onto a reference raster grid.

import geopandas as gpd
import rasterio.features
from pyproj import Transformer
from shapely.ops import transform as shapely_transform


def dissolve_by_type(gdf, column):
    """Merge features sharing the same value in a given column into one geometry per group."""
    return gdf.dissolve(by=column)


def join_within_boundary(gdf, boundary):
    """Return only the features of gdf that fall within boundary, after matching their CRS."""
    boundary_matched = boundary.to_crs(gdf.crs)
    joined = gpd.sjoin(gdf, boundary_matched, predicate="within", how="left")
    return joined[joined["index_right"].notna()]


def buffer_and_union(gdf_list, distance, projected_crs):
    """Buffer each GeoDataFrame in gdf_list by distance (in the units of projected_crs),
    then merge every resulting buffer into a single combined geometry."""
    all_buffers = []
    for gdf in gdf_list:
        gdf_projected = gdf.to_crs(projected_crs)
        all_buffers.extend(list(gdf_projected.buffer(distance)))

    combined = gpd.GeoSeries(all_buffers, crs=projected_crs)
    return combined.unary_union


def rasterize_to_reference(
    geometry, geometry_crs, reference_shape, reference_transform, reference_crs
):
    """Rasterize a single geometry onto a reference raster's grid, reprojecting it first if needed."""
    if geometry_crs != reference_crs:
        transformer = Transformer.from_crs(geometry_crs, reference_crs, always_xy=True)
        geometry = shapely_transform(transformer.transform, geometry)

    return rasterio.features.rasterize(
        [(geometry, 1)],
        out_shape=reference_shape,
        transform=reference_transform,
        fill=0,
        dtype="uint8",
    )
