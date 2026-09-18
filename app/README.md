# Solar Site Suitability - Desierto de Tabernas

Final project for the Spatial Python course. Identifies the most suitable
locations for solar panel installation, combining slope, aspect, land cover
(NDVI), and access to roads/power lines into one weighted suitability score,
with an interactive Streamlit front end.

## Folder structure

```
solar_suitability_project/
├── data/
│   ├── dem.tif                        <- put your own data here
│   ├── sentinel.tif
│   ├── Desierto_de_Tabernas.gpkg
│   ├── road.gpkg
│   ├── power.gpkg
│   └── outputs/
│       └── aligned/                   <- generated automatically on first run
├── modules/
│   ├── data_loader.py                 (Session 01)
│   ├── raster_utils.py                (Session 03)
│   ├── indices.py                      (Session 04)
│   ├── terrain_analysis.py             (Session 05)
│   ├── spatial_analysis.py             (Session 06)
│   ├── reprojector.py                  (Session 07)
│   ├── solar_suitability.py            (Session 08)
│   └── interactive_map.py              (Session 09)
├── app.py                              (Session 10)
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Place your own `dem.tif`, `sentinel.tif`, `Desierto_de_Tabernas.gpkg`,
`road.gpkg`, and `power.gpkg` inside `data/`. `power.gpkg` must contain a
`power_point` layer and a `power_line` layer, exactly as built in Session 02.

## Running the app

```bash
streamlit run app.py
```

The first run builds `data/outputs/aligned/*_aligned.tif` from scratch by
calling the Session 04-07 modules in sequence (this can take a little while,
depending on raster size). Every run after that loads those files directly
and only recomputes the weighted overlay, which is instant, so the sidebar
sliders for slope/aspect/NDVI/access weights and the classification
thresholds update the map live.

If you ever change the raw data in `data/` and want the pipeline to rerun,
delete the contents of `data/outputs/aligned/` first.

## What app.py actually does

`app.py` intentionally contains almost no analysis logic. It imports the
modules built in Sessions 01, 03-09, runs the one-time alignment pipeline if
`data/outputs/aligned/` is empty, then on every rerun:

1. normalizes slope, aspect, and NDVI, and passes access through unchanged
   (`modules/solar_suitability.py`)
2. combines them with the sidebar's weights into one 0-100 score
3. applies the NDWI water exclusion mask and classifies into three classes
4. reprojects the classified array to EPSG:4326 in memory and colors it
   (`modules/interactive_map.py`)
5. renders it on a Folium map alongside roads and power infrastructure,
   with a legend, layer control, and optional plugins (fullscreen, minimap,
   measure tool, marker clustering)
6. offers the current classified GeoTIFF and the map's HTML as downloads

See the "How this app is put together" expander at the bottom of the app
for the exact module-to-feature mapping.
