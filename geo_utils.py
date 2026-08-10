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


# ---------------------------------------------------------------------------
# Bounds de la Tunisie (découpage administratif réel des 24 gouvernorats)
# ---------------------------------------------------------------------------
# Étendue calculée depuis gouvernorats.geojson : on restreint la carte
# exactement à ce cadre pour que les pays/territoires voisins (Algérie,
# Libye, Italie, Malte, Sicile) ne soient ni visibles ni grisés en fond.
TUNISIA_BOUNDS = [[30.25, 7.50], [37.40, 11.62]]

# Cadre un peu élargi : la carte ne peut être déplacée / dézoomée au-delà,
# le regard reste donc centré sur les 24 gouvernorats.
MAX_BOUNDS = [[29.0, 6.4], [38.5, 12.7]]

# Style injecté dans la carte : fond épuré assorti au thème sombre de l'app
# (aucune tuile -> Leaflet peint le conteneur en gris clair par défaut, il faut
# donc le repeindre ici, dans l'iframe, car le CSS de la page parent n'y entre pas).
MAP_BG_CSS = """
<style>
    .leaflet-container {
        background:
            radial-gradient(circle at 50% 42%, #131A26 0%, #0C1016 62%, #090B0F 100%);
    }
    .leaflet-interactive {
        transition:
            fill 250ms ease,
            fill-opacity 250ms ease,
            stroke 250ms ease,
            stroke-width 250ms ease;
    }
</style>
"""


def tunisia_fit_bounds(m: folium.Map) -> None:
    """Cadre la vue sur la Tunisie avec une marge, et verrouille le déplacement.

    L'animation de zoom/pan est gérée nativement par Leaflet (~300-400 ms,
    easing par défaut) : comme st_folium ne reconstruit la carte qu'au clic,
    la transition reste fluide à l'ouverture comme lors des manipulations.
    """
    m.fit_bounds(TUNISIA_BOUNDS, padding=(24, 24))
    m.options["maxBounds"] = MAX_BOUNDS
    m.options["minZoom"] = 5


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

    Fond de carte épuré (aucune tuile cartographique) : l'attention se porte
    à 100 % sur les gouvernorats tunisiens. Le survol éclaire légèrement la
    zone (highlight + transition CSS) et affiche une infobulle native Leaflet.
    """
    m = folium.Map(
        location=list(center),
        zoom_start=zoom_start,
        tiles=None,  # fond vide : pas de mappemonde grisée derrière la Tunisie
        zoom_control=True,
        control_scale=False,
    )
    m.get_root().html.add_child(folium.Element(MAP_BG_CSS))

    # Contours des gouvernorats en fond (utile en vue "délégations")
    if outline_features:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": outline_features},
            style_function=lambda x: {"fillOpacity": 0, "color": "#3A4252", "weight": 1.2},
            interactive=False,
        ).add_to(m)

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
                "fillOpacity": 0.9 if is_selected else 0.78,
                "color": "#FFFFFF" if is_selected else "#0A0D12",
                "weight": 2.6 if is_selected else 0.8,
            }

        gj = folium.GeoJson(
            feat,
            style_function=_style,
            highlight_function=lambda _: {"weight": 2.2, "fillOpacity": 1},
            tooltip=folium.Tooltip(tooltip_html),
        )
        gj.add_to(m)

    tunisia_fit_bounds(m)
    return m
