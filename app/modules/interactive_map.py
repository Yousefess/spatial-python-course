# modules/interactive_map.py
# Built in Session 09: turning a classified raster into a Folium-ready
# RGBA image, plus small reusable helpers for the base map, styled
# vector layers, and a manual HTML legend. app.py (Session 10) imports
# every one of these directly instead of rebuilding the map logic.

import folium
import numpy as np
import rasterio
from branca.element import MacroElement
from jinja2 import Template


def raster_to_rgba(path, color_map):
    """Convert a single-band classified raster into an RGBA NumPy image,
    using color_map, a dict of {value: (r, g, b)}. Nodata pixels become transparent."""
    with rasterio.open(path) as src:
        band = src.read(1)
        bounds = src.bounds
        nodata = src.nodata

    rgba = np.zeros((*band.shape, 4), dtype="uint8")
    for value, color in color_map.items():
        mask = band == value
        rgba[mask, 0:3] = color
        rgba[mask, 3] = 255

    if nodata is not None:
        rgba[band == nodata, 3] = 0

    return rgba, bounds


def array_to_rgba(band, color_map, nodata=None):
    """Same as raster_to_rgba, but starting from an already-loaded array
    instead of a file path. Used by app.py so a slider change never has
    to re-read a GeoTIFF from disk just to recolor it."""
    rgba = np.zeros((*band.shape, 4), dtype="uint8")
    for value, color in color_map.items():
        mask = band == value
        rgba[mask, 0:3] = color
        rgba[mask, 3] = 255

    if nodata is not None:
        rgba[band == nodata, 3] = 0

    return rgba


def build_base_map(boundary_gdf, zoom_start=12, tiles="OpenStreetMap"):
    """Create a Folium map centered on a boundary GeoDataFrame's centroid."""
    boundary_4326 = boundary_gdf.to_crs("EPSG:4326")
    center = boundary_4326.geometry.union_all().centroid
    return folium.Map(location=[center.y, center.x], zoom_start=zoom_start, tiles=tiles)


def add_vector_layer(m, gdf, name, color, weight, tooltip_field=None):
    """Add a GeoDataFrame to a Folium map as a styled GeoJson layer."""
    tooltip = folium.GeoJsonTooltip(fields=[tooltip_field]) if tooltip_field else None
    folium.GeoJson(
        gdf.to_crs("EPSG:4326"),
        name=name,
        style_function=lambda feature: {"color": color, "weight": weight},
        tooltip=tooltip,
    ).add_to(m)


def add_legend(m, title, entries):
    """Add a simple fixed-position HTML legend. entries is a list of (label, hex_color).

    Text color is hardcoded rather than inherited, so the legend stays
    readable whether the surrounding page (or the viewer's browser) is in
    light or dark mode; without this, dark themes can end up rendering
    white-on-white or near-invisible text here."""
    rows = "".join(
        f'<span style="background:{color}; width:12px; height:12px; '
        f'display:inline-block; border-radius:2px; margin-right:6px;"></span>'
        f'<span style="color:#1f2937;">{label}</span><br>'
        for label, color in entries
    )
    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background-color: rgba(255, 255, 255, 0.95); color: #1f2937;
                padding: 10px 14px; border: 1px solid #9ca3af; border-radius: 6px;
                font-size: 13px; line-height: 1.6;
                box-shadow: 0 1px 6px rgba(0,0,0,0.25);">
      <b style="color:#111827;">{title}</b><br>{rows}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))


def add_reset_view_button(m, latitude, longitude, zoom, position="topleft"):
    """Add a small button that resets the map back to its initial center and
    zoom level. Implemented as a proper Folium/Leaflet control, the same
    mechanism folium.plugins (Fullscreen, MeasureControl, ...) use internally,
    rather than a hand-rolled <script> tag, so it is registered and timed the
    same reliable way those plugins are, and stacks neatly with them in the
    same corner instead of overlapping the (unrelated) layer control panel."""
    ResetViewControl(latitude, longitude, zoom, position=position).add_to(m)


class ResetViewControl(MacroElement):
    """A minimal Leaflet control with a single button that calls
    map.setView(...) back to a fixed center and zoom."""

    _template = Template("""
        {% macro script(this, kwargs) %}
        var {{ this.get_name() }} = L.Control.extend({
            options: {position: '{{ this.position }}'},
            onAdd: function(map) {
                var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                var button = L.DomUtil.create('a', '', container);
                button.href = '#';
                button.title = 'Reset to initial view';
                button.innerHTML = '&#127968;';
                button.style.display = 'flex';
                button.style.alignItems = 'center';
                button.style.justifyContent = 'center';
                button.style.fontSize = '16px';
                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.on(button, 'click', function(e) {
                    L.DomEvent.preventDefault(e);
                    {{ this._parent.get_name() }}.setView(
                        [{{ this.lat }}, {{ this.lon }}], {{ this.zoom }}
                    );
                });
                return container;
            }
        });
        {{ this._parent.get_name() }}.addControl(new {{ this.get_name() }}());
        {% endmacro %}
        """)

    def __init__(self, lat, lon, zoom, position="topleft"):
        super().__init__()
        self._name = "ResetViewControl"
        self.lat = lat
        self.lon = lon
        self.zoom = zoom
        self.position = position
