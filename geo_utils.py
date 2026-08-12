"""geo_utils.py — chargement des fonds de carte et construction de la carte Folium."""

from __future__ import annotations

import json
from pathlib import Path

import folium
import folium.plugins

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


# CSS pour le marqueur pulsant (localisation d'une réclamation)
LOCATE_MARKER_CSS = """
<style>
    .locate-pulse {
        border-radius: 50%;
        animation: locatePulse 1.5s ease-out infinite;
    }
    @keyframes locatePulse {
        0%   { box-shadow: 0 0 0 0 rgba(255,121,0,0.7); }
        70%  { box-shadow: 0 0 0 20px rgba(255,121,0,0); }
        100% { box-shadow: 0 0 0 0 rgba(255,121,0,0); }
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
    complaint_points: list[dict] | None = None,
    show_points: bool = False,
    locate_point: dict | None = None,
) -> folium.Map:
    """Construit une carte Folium colorée par statut réseau.

    status_by_id: dict {id: {"status": "vert"|"orange"|"rouge", "count": int, "score": int}}
    complaint_points: liste de dicts {"Latitude", "Longitude", "statut", "type", ...}
    show_points: si True, superpose les points GPS des réclamations sur la carte
    locate_point: dict {"Latitude", "Longitude", "type", "statut", ...} pour centrer
                  et zoomer sur une réclamation précise avec un marqueur pulsant

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

    if not locate_point:
        tunisia_fit_bounds(m)

    # -- Localisation d'une réclamation spécifique (marqueur pulsant) ------
    if locate_point:
        lat, lon = locate_point["Latitude"], locate_point["Longitude"]
        # Injecter le CSS de pulsation
        m.get_root().html.add_child(folium.Element(LOCATE_MARKER_CSS))
        # Centrer et zoomer sur le point (avant les GeoJSON pour éviter le conflit fit_bounds)
        m.location = [lat, lon]
        m.options["zoom"] = 14
        # Cercle extérieur pulsant (animation)
        folium.CircleMarker(
            location=[lat, lon],
            radius=18,
            color="#FF7900",
            fillColor="#FF7900",
            fillOpacity=0.18,
            weight=2,
            className="locate-pulse",
        ).add_to(m)
        # Marqueur central
        folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            color="#FFFFFF",
            fillColor="#FF7900",
            fillOpacity=1.0,
            weight=2.5,
            tooltip=folium.Tooltip(
                f"<b>📍 {locate_point.get('type', 'Réclamation')}</b><br>"
                f"Statut : {locate_point.get('statut', '?')}<br>"
                f"GPS : {lat:.5f}, {lon:.5f}"
            ),
        ).add_to(m)

    # -- Superposition des points GPS de réclamations (optionnel) ----------
    if show_points and complaint_points:
        # Couleurs selon le statut du ticket
        POINT_COLORS = {"En cours": "#EF4444", "Résolu": "#22C55E"}

        cluster = folium.plugins.MarkerCluster(name="Réclamations").add_to(m)
        for pt in complaint_points:
            color = POINT_COLORS.get(pt.get("statut", ""), "#8B93A3")
            tooltip = (
                f"<b>{pt.get('type', 'Réclamation')}</b><br>"
                f"Statut : {pt.get('statut', '?')}<br>"
                f"Délégation : {pt.get('delegation_name', '?')}<br>"
                f"GPS : {pt['Latitude']:.5f}, {pt['Longitude']:.5f}"
            )
            folium.CircleMarker(
                location=[pt["Latitude"], pt["Longitude"]],
                radius=4,
                color=color,
                fillColor=color,
                fillOpacity=0.85,
                weight=1.2,
                tooltip=folium.Tooltip(tooltip),
            ).add_to(cluster)

    return m
