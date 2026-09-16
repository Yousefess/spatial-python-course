import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject
from rasterio.mask import mask


def reproject_raster(source_path, destination_path, target_crs, resampling):
    """Reproject a raster to a new CRS, writing the result to destination_path."""
    with rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )

        profile = src.profile.copy()
        profile.update(
            {
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height,
            }
        )

        with rasterio.open(destination_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=target_crs,
                resampling=resampling,
            )

    return destination_path


def resample_to_reference(
    source_path, reference_shape, reference_transform, reference_crs, resampling
):
    """Resample a raster directly onto a reference grid's shape, transform, and CRS."""
    with rasterio.open(source_path) as src:
        destination = np.zeros(reference_shape, dtype=src.dtypes[0])
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=reference_transform,
            dst_crs=reference_crs,
            resampling=resampling,
        )

    return destination


def clip_array_to_boundary(array, profile, boundary_gdf):
    """Clip an in-memory array to a boundary geometry, returning the clipped array and its new transform."""
    with rasterio.io.MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(array, 1)
            clipped, clipped_transform = mask(dataset, boundary_gdf.geometry, crop=True)

    return clipped[0], clipped_transform


def check_alignment(arrays):
    """Confirm every array in a dict shares the same shape. Raises ValueError otherwise."""
    shapes = {name: array.shape for name, array in arrays.items()}
    if len(set(shapes.values())) > 1:
        raise ValueError(f"Shape mismatch across layers: {shapes}")
    return True
