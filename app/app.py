# app.py
# Session 10: the final integration. This file contains almost no real
# analysis logic of its own, on purpose. Every calculation it needs,
# loading data, calculating indices and terrain, buffering roads and
# power lines, reprojecting and aligning, normalizing and weighting,
# building the map, already exists in modules/, one file per session.
# app.py's only job is to wire those pieces together into something
# interactive, and to rerun the cheap parts, the weighted overlay, live,
# every time someone moves a slider.

import io
import sys
from pathlib import Path

import altair as alt
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import streamlit as st
from folium.plugins import Fullscreen, MarkerCluster, MeasureControl, MiniMap
from rasterio.warp import Resampling, calculate_default_transform, reproject
from streamlit_folium import st_folium

sys.path.append(str(Path(__file__).parent / "modules"))

from data_loader import load_boundary  # Session 01
from indices import load_and_calculate_indices  # Session 04
from interactive_map import (add_legend, add_reset_view_button,  # Session 09
                             add_vector_layer, array_to_rgba)
from raster_utils import save_raster  # Session 03
from reprojector import (check_alignment, clip_array_to_boundary,  # Session 07
                         reproject_raster, resample_to_reference)
from solar_suitability import apply_water_mask  # Session 08
from solar_suitability import (calculate_final_score, classify_multi,
                               classify_suitability, normalize_aspect,
                               normalize_ndvi, normalize_slope)
from spatial_analysis import buffer_and_union  # Session 06
from spatial_analysis import rasterize_to_reference
from terrain_analysis import load_and_calculate_terrain  # Session 05

# ---------------------------------------------------------------------------
# Paths and constants, matching every earlier session exactly.
# ---------------------------------------------------------------------------

DATA_DIR = Path("data")
OUT_DIR = DATA_DIR / "outputs"
ALIGNED_DIR = OUT_DIR / "aligned"

DEM_PATH = DATA_DIR / "dem.tif"
SENTINEL_PATH = DATA_DIR / "sentinel.tif"
BOUNDARY_PATH = DATA_DIR / "Desierto_de_Tabernas.gpkg"
ROAD_PATH = DATA_DIR / "road.gpkg"
POWER_PATH = DATA_DIR / "power.gpkg"

TARGET_CRS = "EPSG:32629"  # Session 07's shared, projected reference CRS
RED_BAND, GREEN_BAND, NIR_BAND = 3, 2, 4  # Session 04's confirmed band mapping
BUFFER_DISTANCE_M = 1000  # Session 06's access buffer distance
INITIAL_ZOOM = 12

DEFAULT_WEIGHTS = {"slope": 0.30, "aspect": 0.20, "ndvi": 0.30, "access": 0.20}

# Two selectable color/label schemes, so the map, the legend, and the bar
# chart all agree no matter whether the viewer picks 3 or 5 classes.
CLASS_SCHEMES = {
    3: {
        "labels": {0: "Unsuitable", 1: "Moderate", 2: "Suitable"},
        "colors_hex": {0: "#b2182b", 1: "#f7e876", 2: "#1a9850"},
        "colors_rgb": {0: (178, 24, 43), 1: (247, 232, 118), 2: (26, 152, 80)},
    },
    5: {
        "labels": {
            0: "Very unsuitable",
            1: "Unsuitable",
            2: "Moderate",
            3: "Suitable",
            4: "Very suitable",
        },
        "colors_hex": {
            0: "#d7191c",
            1: "#fdae61",
            2: "#ffffbf",
            3: "#a6d96a",
            4: "#1a9641",
        },
        "colors_rgb": {
            0: (215, 25, 28),
            1: (253, 174, 97),
            2: (255, 255, 191),
            3: (166, 217, 106),
            4: (26, 150, 65),
        },
    },
}


# ---------------------------------------------------------------------------
# Step 1 (only runs once, ever): build the four aligned factor layers from
# raw data, exactly following Sessions 04 through 07. If data/outputs/aligned
# already has them, this whole function is skipped, which is why it is safe
# to leave inside a Streamlit app that reruns constantly.
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def build_aligned_layers_if_needed():
    aligned_paths = {
        "slope": ALIGNED_DIR / "slope_aligned.tif",
        "aspect": ALIGNED_DIR / "aspect_aligned.tif",
        "ndvi": ALIGNED_DIR / "ndvi_aligned.tif",
        "access": ALIGNED_DIR / "access_aligned.tif",
    }

    if all(path.exists() for path in aligned_paths.values()):
        return aligned_paths

    ALIGNED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    progress = st.progress(0, text="🛰️ Running the full pipeline for the first time...")

    # Session 04: NDVI (NDWI is recomputed later, only for the water mask)
    progress.progress(10, text="Calculating NDVI (Session 04)...")
    ndvi, _, sentinel_profile = load_and_calculate_indices(
        str(SENTINEL_PATH), RED_BAND, GREEN_BAND, NIR_BAND
    )
    ndvi_profile = sentinel_profile.copy()
    ndvi_profile.update({"dtype": "float32", "count": 1, "nodata": None})
    save_raster(ndvi.astype("float32"), ndvi_profile, str(OUT_DIR / "ndvi.tif"))

    # Session 05: slope and aspect
    progress.progress(30, text="Calculating slope and aspect (Session 05)...")
    slope, aspect, dem_profile = load_and_calculate_terrain(str(DEM_PATH))
    terrain_profile = dem_profile.copy()
    terrain_profile.update({"dtype": "float32", "count": 1})
    save_raster(slope.astype("float32"), terrain_profile, str(OUT_DIR / "slope.tif"))
    save_raster(aspect.astype("float32"), terrain_profile, str(OUT_DIR / "aspect.tif"))

    # Session 06: road/power buffer, unioned and rasterized onto the DEM grid
    progress.progress(50, text="Buffering roads and power lines (Session 06)...")
    roads = gpd.read_file(str(ROAD_PATH))
    power_lines = gpd.read_file(str(POWER_PATH), layer="power_line")
    access_zone = buffer_and_union([roads, power_lines], BUFFER_DISTANCE_M, TARGET_CRS)

    with rasterio.open(str(DEM_PATH)) as src:
        dem_shape = (src.height, src.width)
        dem_transform = src.transform
        dem_crs = src.crs
        access_profile = src.profile.copy()

    access_raster = rasterize_to_reference(
        access_zone, TARGET_CRS, dem_shape, dem_transform, dem_crs
    )
    access_profile.update({"dtype": "uint8", "count": 1, "nodata": None})
    save_raster(access_raster, access_profile, str(OUT_DIR / "access.tif"))

    # Session 07: reproject all four to EPSG:32629, resample onto one shared
    # grid (slope's own reprojected grid, exactly as Session 07 chose), clip
    # to the study boundary, and save the final aligned versions.
    progress.progress(75, text="Reprojecting and aligning every layer (Session 07)...")
    resampling_choice = {
        "ndvi": Resampling.bilinear,
        "slope": Resampling.bilinear,
        "aspect": Resampling.nearest,
        "access": Resampling.nearest,
    }
    source_paths = {
        "ndvi": OUT_DIR / "ndvi.tif",
        "slope": OUT_DIR / "slope.tif",
        "aspect": OUT_DIR / "aspect.tif",
        "access": OUT_DIR / "access.tif",
    }

    reprojected = {}
    for name, path in source_paths.items():
        out_path = ALIGNED_DIR / f"{name}_utm.tif"
        reproject_raster(str(path), str(out_path), TARGET_CRS, resampling_choice[name])
        reprojected[name] = out_path

    with rasterio.open(str(reprojected["slope"])) as ref:
        reference_shape = (ref.height, ref.width)
        reference_transform = ref.transform
        reference_crs = ref.crs
        reference_profile = ref.profile

    boundary = gpd.read_file(str(BOUNDARY_PATH)).to_crs(reference_crs)

    for name in source_paths:
        array = resample_to_reference(
            str(reprojected[name]),
            reference_shape,
            reference_transform,
            reference_crs,
            resampling_choice[name],
        )
        clipped_array, clipped_transform = clip_array_to_boundary(
            array, reference_profile, boundary
        )

        final_profile = reference_profile.copy()
        final_profile.update(
            {
                "height": clipped_array.shape[0],
                "width": clipped_array.shape[1],
                "transform": clipped_transform,
            }
        )
        save_raster(
            clipped_array.astype(final_profile["dtype"]),
            final_profile,
            str(aligned_paths[name]),
        )

    progress.progress(100, text="Done.")
    progress.empty()

    return aligned_paths


# ---------------------------------------------------------------------------
# Step 2: load the aligned layers and everything that does not depend on
# the slider weights, cached so moving a slider never re-touches disk.
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading aligned layers...")
def load_layers(_aligned_paths):
    layers, profile = {}, None
    for name, path in _aligned_paths.items():
        with rasterio.open(str(path)) as src:
            layers[name] = src.read(1).astype("float32")
            if profile is None:
                profile = src.profile
    check_alignment(layers)
    return layers, profile


@st.cache_data(show_spinner="Normalizing factor layers...")
def compute_normalized_scores(layers):
    return {
        "slope": normalize_slope(layers["slope"]),
        "aspect": normalize_aspect(layers["aspect"]),
        "ndvi": normalize_ndvi(layers["ndvi"]),
        "access": layers["access"],
    }


@st.cache_data(show_spinner="Building the water exclusion mask...")
def compute_aligned_water_mask(_reference_profile):
    with rasterio.open(str(SENTINEL_PATH)) as src:
        green = src.read(GREEN_BAND).astype("float32")
        nir = src.read(NIR_BAND).astype("float32")
        src_transform, src_crs = src.transform, src.crs

    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = np.where((green + nir) != 0, (green - nir) / (green + nir), 0)
    water_mask = (ndwi > 0).astype("uint8")

    aligned_mask = np.zeros(
        (_reference_profile["height"], _reference_profile["width"]), dtype="uint8"
    )
    reproject(
        source=water_mask,
        destination=aligned_mask,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=_reference_profile["transform"],
        dst_crs=_reference_profile["crs"],
        resampling=Resampling.nearest,
    )
    return aligned_mask


@st.cache_data(show_spinner="Loading roads and power infrastructure...")
def load_vector_layers():
    boundary = load_boundary(str(BOUNDARY_PATH))
    roads = gpd.read_file(str(ROAD_PATH))
    power_lines = gpd.read_file(str(POWER_PATH), layer="power_line")
    power_points = gpd.read_file(str(POWER_PATH), layer="power_point")
    return boundary, roads, power_lines, power_points


def reproject_array_to_4326(array, src_transform, src_crs):
    """Reproject a single in-memory band to EPSG:4326 for the web map,
    without ever writing an intermediate file to disk (Session 09's
    ImageOverlay pattern, made fast enough to run on every slider move)."""
    height, width = array.shape
    new_transform, new_width, new_height = calculate_default_transform(
        src_crs,
        "EPSG:4326",
        width,
        height,
        *rasterio.transform.array_bounds(height, width, src_transform),
    )
    destination = np.zeros((new_height, new_width), dtype=array.dtype)
    reproject(
        source=array,
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=new_transform,
        dst_crs="EPSG:4326",
        resampling=Resampling.nearest,
    )
    bounds = rasterio.transform.array_bounds(new_height, new_width, new_transform)
    west, south, east, north = bounds
    return destination, (south, west, north, east)


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Solar Site Suitability | Desierto de Tabernas",
    layout="wide",
    page_icon="🌞",
)

st.title("🌞 Solar Site Suitability")
st.caption(
    "🏜️ Desierto de Tabernas, Almeria. Every layer on this page was produced by "
    "modules/ built across Sessions 01-09 of this course; this page only "
    "combines and displays them live."
)

if not DEM_PATH.exists() or not SENTINEL_PATH.exists() or not BOUNDARY_PATH.exists():
    st.error(
        "🚫 Expected data files were not found under `data/`. This app needs "
        "`dem.tif`, `sentinel.tif`, `Desierto_de_Tabernas.gpkg`, `road.gpkg`, "
        "and `power.gpkg` in the project's `data/` folder before it can run."
    )
    st.stop()

aligned_paths = build_aligned_layers_if_needed()
layers, reference_profile = load_layers(aligned_paths)
scores = compute_normalized_scores(layers)
water_mask = compute_aligned_water_mask(reference_profile)
boundary, roads, power_lines, power_points = load_vector_layers()

pixel_area_m2 = abs(reference_profile["transform"].a * reference_profile["transform"].e)

# --- Sidebar: weights, class count, thresholds, and plugins --------------

st.sidebar.header("⚙️ Suitability weights")
st.sidebar.caption("How much each factor counts. Automatically rescaled to sum to 1.")

raw_weights = {
    "slope": st.sidebar.slider(
        "⛰️ Slope",
        0.0,
        1.0,
        DEFAULT_WEIGHTS["slope"],
        0.05,
        help="How much a gentle slope matters. Slopes under ~10° score highest; "
        "steeper than 45° scores 0.",
    ),
    "aspect": st.sidebar.slider(
        "🧭 Aspect",
        0.0,
        1.0,
        DEFAULT_WEIGHTS["aspect"],
        0.05,
        help="How much facing south matters. South-facing slopes (around 180°) "
        "score highest, north-facing slopes score lowest, flat ground scores 0.",
    ),
    "ndvi": st.sidebar.slider(
        "🌿 Land cover (NDVI)",
        0.0,
        1.0,
        DEFAULT_WEIGHTS["ndvi"],
        0.05,
        help="How much bare/scrubby land is preferred over vegetated land. "
        "Low NDVI (little vegetation) scores highest.",
    ),
    "access": st.sidebar.slider(
        "🛣️ Access (roads/power)",
        0.0,
        1.0,
        DEFAULT_WEIGHTS["access"],
        0.05,
        help="How much proximity to existing roads and power lines matters. "
        "Pixels within 1000 m of either score 1, everything else scores 0.",
    ),
}
weight_sum = sum(raw_weights.values()) or 1.0
weights = {name: value / weight_sum for name, value in raw_weights.items()}

with st.sidebar.expander(
    "ℹ️ Effective weights (after rescaling to sum to 1)", expanded=False
):
    for name, value in weights.items():
        st.write(f"{name}: {value:.2f}")

st.sidebar.divider()

st.sidebar.header("🗂️ Classification")
n_classes = st.sidebar.radio(
    "Number of classes",
    options=[3, 5],
    horizontal=True,
    help="3 classes: Unsuitable / Moderate / Suitable, with adjustable "
    "thresholds below. 5 classes: an evenly spaced Very unsuitable "
    "to Very suitable scale, useful for a finer-grained view of the map.",
)

if n_classes == 3:
    low_threshold = st.sidebar.slider(
        "Unsuitable / moderate threshold",
        0,
        100,
        40,
        help="Suitability scores below this value are classified as Unsuitable.",
    )
    high_threshold = st.sidebar.slider(
        "Moderate / suitable threshold",
        0,
        100,
        70,
        help="Suitability scores at or above this value are classified as Suitable.",
    )
    if high_threshold <= low_threshold:
        st.sidebar.warning(
            "⚠️ The suitable threshold should be higher than the unsuitable one."
        )
else:
    st.sidebar.caption("Fixed, evenly spaced thresholds: 20 / 40 / 60 / 80.")

st.sidebar.divider()

show_advanced = st.sidebar.checkbox(
    "🧰 Show map plugins",
    value=True,
    help="Adds a fullscreen button, a minimap, a measuring tool, and "
    "clusters nearby power infrastructure markers together.",
)

# --- The cheap part: recompute the weighted overlay on every rerun -------

scheme = CLASS_SCHEMES[n_classes]
class_labels = scheme["labels"]
class_colors_hex = scheme["colors_hex"]
class_colors_rgb = scheme["colors_rgb"]

suitability_score = calculate_final_score(
    scores["slope"], scores["aspect"], scores["ndvi"], scores["access"], weights
)
suitability_score = apply_water_mask(suitability_score, water_mask)

if n_classes == 3:
    suitability_class = classify_suitability(
        suitability_score, low_threshold, high_threshold
    )
else:
    suitability_class = classify_multi(suitability_score, [20, 40, 60, 80])

class_counts = {
    label: int(np.sum(suitability_class == value))
    for value, label in class_labels.items()
}
class_area_km2 = {
    label: round((count * pixel_area_m2) / 1_000_000, 2)
    for label, count in class_counts.items()
}

# --- Downloads, up top ------------------------------------------------------

class_profile = reference_profile.copy()
class_profile.update({"dtype": "uint8", "count": 1, "nodata": None})
tif_buffer = io.BytesIO()
with rasterio.io.MemoryFile() as memfile:
    with memfile.open(**class_profile) as dst:
        dst.write(suitability_class, 1)
    tif_buffer.write(memfile.read())
tif_buffer.seek(0)

download_col1, download_col2 = st.columns(2)
with download_col1:
    st.download_button(
        "⬇️ Download suitability_class.tif",
        data=tif_buffer,
        file_name="suitability_class.tif",
        mime="image/tiff",
        use_container_width=True,
    )

# --- Build the map (the HTML download button below needs it fully built) --

class_array_4326, (south, west, north, east) = reproject_array_to_4326(
    suitability_class, reference_profile["transform"], reference_profile["crs"]
)
rgba = array_to_rgba(class_array_4326, class_colors_rgb, nodata=None)

boundary_4326 = boundary.to_crs("EPSG:4326")
center = boundary_4326.geometry.union_all().centroid
initial_lat, initial_lon = center.y, center.x

m = folium.Map(
    location=[initial_lat, initial_lon], zoom_start=INITIAL_ZOOM, tiles="OpenStreetMap"
)

folium.raster_layers.ImageOverlay(
    image=rgba,
    bounds=[[south, west], [north, east]],
    opacity=0.75,
    name="Suitability",
).add_to(m)

add_vector_layer(
    m, roads, "Roads", color="dimgray", weight=1.5, tooltip_field="highway"
)
add_vector_layer(
    m, power_lines, "Power lines", color="darkorange", weight=2, tooltip_field="power"
)

if show_advanced:
    cluster = MarkerCluster(name="Power infrastructure (clustered)").add_to(m)
    for _, row in power_points.to_crs("EPSG:4326").iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4,
            color="crimson",
            fill=True,
            fill_opacity=0.9,
            tooltip=str(row.get("power", "power infrastructure")),
        ).add_to(cluster)
    Fullscreen(position="topleft").add_to(m)
    MiniMap(toggle_display=True).add_to(m)
    MeasureControl(primary_length_unit="meters").add_to(m)

add_legend(
    m, "Suitability", list(zip(class_labels.values(), class_colors_hex.values()))
)
add_reset_view_button(m, initial_lat, initial_lon, INITIAL_ZOOM)
folium.LayerControl(collapsed=False).add_to(m)

with download_col2:
    st.download_button(
        "⬇️ Download this map as solar_map.html",
        data=m.get_root().render().encode("utf-8"),
        file_name="solar_map.html",
        mime="text/html",
        use_container_width=True,
    )

# --- The map itself, full width and tall now that the chart moved below --

st.subheader("🗺️ Interactive map")
st.caption("🏠 Click the home button on the map to reset the view.")
st_folium(m, height=700, use_container_width=True, returned_objects=[])

# --- Stats and chart, now below the (bigger) map --------------------------

st.divider()
st.subheader("📊 Area by class")

metric_cols = st.columns(len(class_area_km2))
for col, (label, area) in zip(metric_cols, class_area_km2.items()):
    col.metric(label, f"{area:.1f} km²")

chart_df = pd.DataFrame(
    {
        "Class": list(class_area_km2.keys()),
        "Area (km²)": list(class_area_km2.values()),
    }
)
color_scale = alt.Scale(
    domain=list(class_labels.values()), range=list(class_colors_hex.values())
)

bar_chart = (
    alt.Chart(chart_df)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X("Class:N", sort=list(class_labels.values()), title=None),
        y=alt.Y("Area (km²):Q"),
        color=alt.Color("Class:N", scale=color_scale, legend=None),
        tooltip=["Class", "Area (km²)"],
    )
    .properties(height=320)
)
st.altair_chart(bar_chart, use_container_width=True)

st.divider()
with st.expander("🧩 How this app is put together"):
    st.markdown("""
Every session in this course ended by building one module. This app only imports them:

| Module | Session | Used here for |
|---|---|---|
| `data_loader.py` | 01 | loading the study boundary |
| `raster_utils.py` | 03 | writing intermediate GeoTIFFs during the first-run pipeline |
| `indices.py` | 04 | NDVI, on first run only |
| `terrain_analysis.py` | 05 | slope and aspect, on first run only |
| `spatial_analysis.py` | 06 | the road/power access buffer, on first run only |
| `reprojector.py` | 07 | reprojecting, aligning and clipping every layer |
| `solar_suitability.py` | 08 | normalizing, weighting, masking, classifying, live |
| `interactive_map.py` | 09 | coloring the raster, styling vector layers, the legend, and the reset-view button |

The only genuinely new code in `app.py` itself is the Streamlit layout, the
caching boundaries that keep slider moves fast, and the EPSG:32629 to
EPSG:4326 reprojection done directly on the in-memory array so the map can
update without ever touching disk again after the very first run.
        """)
