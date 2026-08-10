"""geo_utils.py — chargement des fonds de carte et construction de la carte Folium."""

from __future__ import annotations

import json
from pathlib import Path

import folium

from simulate import STATUS_COLORS, STATUS_LABELS

DATA_DIR = Path(__file__).parent / "data"


def load_geojson(filename: str) -> dict:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def build_map(
    features: list[dict],
    id_field: str,
    name_field: str,
    status_by_id: dict[str, dict],
    selected_id: str | None = None,
    outline_features: list[dict] | None = None,
    zoom_start: int = 6,
    center: tuple[float, float] = (34.2, 9.4),
) -> folium.Map:
    """Construit une carte Folium colorée par statut réseau.

    status_by_id: dict {id: {"status": "vert"|"orange"|"rouge", "count": int, "score": int}}
    """
    m = folium.Map(
        location=list(center),
        zoom_start=zoom_start,
        tiles="CartoDB dark_matter",
        zoom_control=True,
        control_scale=False,
    )

    # Contours des gouvernorats en fond (utile en vue "délégations")
    if outline_features:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": outline_features},
            style_function=lambda x: {"fillOpacity": 0, "color": "#3A4252", "weight": 1.2},
            interactive=False,
        ).add_to(m)

    bounds = []
    for feat in features:
        props = feat["properties"]
        fid = props[id_field]
        info = status_by_id.get(fid)
        if not info:
            continue
        color = STATUS_COLORS[info["status"]]
        is_selected = fid == selected_id
        tooltip_html = (
            f"<b>{props[name_field]}</b><br>"
            f"{STATUS_LABELS[info['status']]}<br>"
            f"{info['count']} réclamation(s) · indice {info['score']}%"
        )

        def _style(_, color=color, is_selected=is_selected):
            return {
                "fillColor": color,
                "fillOpacity": 1.0 if is_selected else 0.82,
                "color": "#FFFFFF" if is_selected else "#0A0D12",
                "weight": 2.4 if is_selected else 0.7,
            }

        gj = folium.GeoJson(
            feat,
            style_function=_style,
            highlight_function=lambda _: {"weight": 2, "fillOpacity": 1},
            tooltip=folium.Tooltip(tooltip_html),
        )
        gj.add_to(m)

    return m
