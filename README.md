# 🗺️ Spatial Python Course

A hands-on, project-based course teaching Python for spatial analysis, combining **vector data** (roads, power lines, boundaries) and **raster data** (DEM, Sentinel-2 imagery).

By the end of the course, students build a complete **Solar Site Suitability** application: given a DEM, a Sentinel image, and OSM infrastructure layers, the app identifies and maps the best areas for solar panel installation.

🔗 **Live site:** https://yousefess.github.io/spatial-python-course/

---

## 📚 Course Structure


| Session | Topic                                            | Module File                    |
| --------- | -------------------------------------------------- | -------------------------------- |
| 0       | Python Refresher for Spatial Analysis            | `unit_converter.py` (practice) |
| 1       | Intro to spatial data, loading rasters & vectors | `data_loader.py`               |
| 2       | Working with vector data (GeoPandas)             | `vector_utils.py`              |
| 3       | Raster data & metadata, CRS alignment            | `raster_utils.py`              |
| 4       | NDVI calculation (remote sensing)                | `indices.py`                   |
| 5       | Slope & aspect from DEM                          | `terrain_analysis.py`          |
| 6       | Buffers & distance analysis                      | `spatial_analysis.py`          |
| 7       | Reprojection & resampling                        | `reprojector.py`               |
| 8       | Weighted suitability modeling                    | `solar_suitability.py`         |
| 9       | Interactive maps with Folium                     | `interactive_map.py`           |
| 10      | Final Streamlit app                              | `app.py`                       |

Each session builds one piece of the final project — by Session 10, everything comes together in a working Streamlit application.

---

## 🗂️ Repository Structure

```
spatial-python-course/
├── .github/
│   └── workflows/
│       └── publish.yml          # GitHub Action: render & deploy site
├── _quarto.yml                  # Quarto site configuration
├── index.qmd                    # Homepage
├── sessions/                    # One .qmd notebook per session
│   ├── session-00-python-review.qmd
│   ├── session-01-....qmd
│   └── ...
├── data/                        # Sample datasets used throughout the course
│   ├── sentinel.tif
│   ├── dem.tif
│   ├── boundary.shp
│   ├── roads.shp
│   ├── power_lines.shp
│   └── outputs/                 # Generated rasters (ndvi.tif, slope.tif, ...)
├── modules/                     # .py files built session by session
├── images/                      # Diagrams and illustrations used in notebooks
├── main.py                      # Command-line script running the full pipeline
├── app.py                       # Final Streamlit application (Session 10)
├── requirements.txt             # Python dependencies
└── README.md
```

---

## 🚀 Running Locally

```bash
# Clone the repo
git clone https://github.com/YOUR-USERNAME/spatial-python-course.git
cd spatial-python-course

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Preview the course website locally
quarto preview
```

---

## 🧩 Requirements

- Python 3.10+
- [Quarto](https://quarto.org) (for building/previewing the course website)
- Core libraries: `rasterio`, `geopandas`, `numpy`, `matplotlib`, `shapely`, `folium`, `streamlit`

See `requirements.txt` for the full pinned list.

---

## 📦 Data

Sample datasets for the study area used throughout the course live in `data/`. These are intentionally kept small (cropped to a limited extent) so the repository stays lightweight and processing stays fast during class (under ~30 seconds per operation).

**Note:** these files are tracked directly in this repository (not excluded via `.gitignore`), since they're small enough to version normally and are central to following along with each session.

---

## 🤝 Contributing / Notes for Instructors

- Each session's notebook lives in `sessions/` as a `.qmd` file — edit these to update course content.
- Add new sessions to the `navbar` section of `_quarto.yml` so they appear on the site.
- Pushing to `main` automatically rebuilds and republishes the site via GitHub Actions.
