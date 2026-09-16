import rasterio
from pyproj import CRS


def get_raster_info(path):
    """Return a dictionary of key metadata for a raster file."""
    with rasterio.open(path) as src:
        info = {
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "crs": CRS(src.crs),
            "bounds": src.bounds,
            "transform": src.transform,
        }
    print(
        f"{path}: {info['width']}x{info['height']}, {info['count']} band(s), CRS {info['crs'].to_epsg()}"
    )
    return info


def check_crs_match(path1, path2):
    """Compare the CRS of two raster files and report whether they match."""
    with rasterio.open(path1) as src1:
        crs1 = CRS(src1.crs)
    with rasterio.open(path2) as src2:
        crs2 = CRS(src2.crs)

    match = crs1 == crs2
    status = "match" if match else "DO NOT match"
    print(f"{path1} and {path2} {status} ({crs1.to_epsg()} vs {crs2.to_epsg()})")
    return match


def save_raster(array, profile, path):
    """Write a NumPy array to disk as a raster, using a given rasterio profile."""
    updated_profile = profile.copy()
    updated_profile.update(
        {
            "height": array.shape[0],
            "width": array.shape[1],
        }
    )

    with rasterio.open(path, "w", **updated_profile) as dst:
        dst.write(array, 1)

    print(f"Saved raster to {path}")
