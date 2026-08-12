"""
app.py — Supervision Réseau : cartographie des réclamations (Tunisie)
=====================================================================

Prototype Streamlit pour stage PFE (Orange). Affiche une carte de la
Tunisie par gouvernorat ou par délégation, colorée selon l'état simulé
du réseau (vert / orange / rouge), avec un historique de réclamations
simulées par zone.

Lancer avec :  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from geo_utils import build_map, load_geojson
from simulate import STATUS_COLORS, STATUS_LABELS, generate_network_data, last_n_days_counts

# ---------------------------------------------------------------------------
# Configuration de page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Supervision Réseau — Orange Tunisie", page_icon="📶", layout="wide")

STATUS_EMOJI = {"vert": "🟢", "orange": "🟠", "rouge": "🔴"}

CUSTOM_CSS = """
<style>
/* ==========================================================================
   Supervision Réseau — thème « Orange Opérationnel Télécom »
   Fond noir/anthracite · accent #FF7900 · glassmorphism léger
   ========================================================================== */

:root {
  --orange: #FF7900;
  --orange-strong: #E86E00;
  --orange-glow: rgba(255, 121, 0, 0.16);
  --bg: #0A0C10;
  --bg-2: #0F131B;
  --card: rgba(19, 24, 32, 0.78);
  --card-solid: #141A23;
  --border: #242C3A;
  --border-soft: #1B222E;
  --text: #E9EDF3;
  --muted: #8B93A3;
  --green: #22C55E;
  --red: #EF4444;
  --radius: 14px;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
}

html, body, [class*="css"] {
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}

.stApp, .main { background: var(--bg); }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }

/* --- Scrollbar -------------------------------------------------------- */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2A3342; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #3A4556; }

/* ==========================================================================
   En-tête
   ========================================================================== */
.orange-badge {
  background: linear-gradient(135deg, var(--orange), var(--orange-strong));
  color: #101317; font-weight: 800; font-size: 12px;
  padding: 4px 11px; border-radius: 999px; display: inline-block;
  letter-spacing: 0.4px; box-shadow: 0 0 18px var(--orange-glow);
}
.app-title { font-weight: 800; font-size: 21px; color: var(--text); margin: 0; letter-spacing: -0.2px; }
.app-subtitle { font-size: 12.5px; color: var(--muted); margin: 0; }

/* ==========================================================================
   KPI / métriques (glassmorphism)
   ========================================================================== */
div[data-testid="stMetric"] {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius);
  padding: 14px 16px;
  backdrop-filter: blur(8px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.25);
  transition: transform 220ms var(--ease), border-color 220ms ease, box-shadow 220ms ease;
  animation: cardIn 500ms var(--ease) both;
}
div[data-testid="stMetric"]:hover {
  transform: translateY(-3px);
  border-color: var(--border);
  box-shadow: 0 10px 26px rgba(0,0,0,0.35);
}
div[data-testid="stMetricLabel"] { color: var(--muted); font-size: 12px; font-weight: 600; }
div[data-testid="stMetricValue"] {
  font-weight: 800; font-size: 26px; color: var(--text); letter-spacing: -0.5px;
}
div[data-testid="stMetricDelta"] { color: var(--muted); font-weight: 600; }
.kpi-row div[data-testid="stMetric"]:nth-child(2) { animation-delay: 60ms; }
.kpi-row div[data-testid="stMetric"]:nth-child(3) { animation-delay: 120ms; }
.kpi-row div[data-testid="stMetric"]:nth-child(4) { animation-delay: 180ms; }
.kpi-row div[data-testid="stMetric"]:nth-child(5) { animation-delay: 240ms; }

/* ==========================================================================
   Onglets personnalisés (pills)
   ========================================================================== */
[data-testid="stBaseButton"] {
  transition: transform 180ms var(--ease), box-shadow 180ms ease,
              border-color 180ms ease, background 180ms ease, color 180ms ease;
  border-radius: 999px !important;
  font-weight: 700;
  letter-spacing: 0.2px;
}
[data-testid="stBaseButton"]:hover { transform: translateY(-1px); }
[data-testid="stBaseButton"]:active { transform: translateY(0) scale(0.98); }
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, var(--orange), var(--orange-strong)) !important;
  border: 1px solid var(--orange) !important;
  color: #101317 !important;
  box-shadow: 0 4px 16px var(--orange-glow);
}
[data-testid="stBaseButton-secondary"] {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--orange) !important;
  color: #FFB066 !important;
  box-shadow: 0 0 0 3px var(--orange-glow);
}

/* ==========================================================================
   Cartes de détail & listes (glassmorphism)
   ========================================================================== */
.zone-card {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius);
  padding: 18px 20px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.30);
  animation: cardIn 420ms var(--ease) both;
}
.zone-card .sk-line { animation: shimmer 1.4s ease infinite; }
.status-pill {
  display: inline-flex; align-items: center; gap: 8px;
  font-weight: 700; font-size: 12px;
  padding: 6px 12px; border-radius: 999px;
  border: 1px solid currentColor;
  background: rgba(255,255,255,0.02);
  white-space: nowrap;
}
.status-dot {
  width: 9px; height: 9px; border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 8px currentColor;
}
.record-card {
  background: var(--card-solid);
  border: 1px solid var(--border-soft);
  border-radius: 11px;
  padding: 9px 12px; margin-bottom: 7px;
  transition: transform 180ms var(--ease), border-color 180ms ease, background 180ms ease;
  animation: cardIn 380ms var(--ease) both;
}
.record-card:hover { transform: translateX(4px); border-color: var(--border); }
.record-top { display: flex; justify-content: space-between; font-size: 12.5px; font-weight: 600; }
.record-meta { font-size: 10.5px; color: var(--muted); margin-top: 2px; }
.tag-ok { color: var(--green); font-size: 10px; font-weight: 700; }
.tag-open { color: var(--red); font-size: 10px; font-weight: 700; }

/* --- Barre de progression (indice qualité) ------------------------------ */
[data-testid="stProgress"] > div { background: var(--border-soft) !important; }
[data-testid="stProgress"] [role="progressbar"] {
  background: linear-gradient(90deg, var(--orange-strong), var(--orange)) !important;
  box-shadow: 0 0 10px var(--orange-glow);
}
/* --- mini barre métier (indice) ---------------------------------------- */
.quality-bar {
  height: 8px; border-radius: 999px; background: var(--border-soft);
  overflow: hidden; position: relative;
}
.quality-bar > span {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--orange-strong), var(--orange));
  box-shadow: 0 0 12px var(--orange-glow);
  animation: growBar 800ms var(--ease) both;
}

/* ==========================================================================
   Skeleton loader (shimmer)
   ========================================================================== */
.sk-line {
  height: 12px; border-radius: 6px; margin-bottom: 12px;
  background: linear-gradient(90deg, #1A212C 25%, #232C3A 37%, #1A212C 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
.sk-circle {
  width: 44px; height: 44px; border-radius: 50%; margin: 0 auto 14px;
  background: linear-gradient(90deg, #1A212C 25%, #232C3A 37%, #1A212C 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
@keyframes shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

/* ==========================================================================
   Animations
   ========================================================================== */
@keyframes cardIn {
  from { opacity: 0; transform: translateY(14px) scale(0.985); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes fadeSlide {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes growBar {
  from { width: 0; }
}

/* Apparition douce de la carte (iframe Folium) après chargement */
[data-testid="stElementContainer"] iframe {
  animation: fadeIn 600ms ease both;
}

/* Graphiques Plotly — apparition en fondu + glissement à chaque chargement */
[data-testid="stPlotlyChart"] {
  animation: fadeSlide 550ms var(--ease) both;
}

/* Tableaux de données */
.stDataFrame { border: 1px solid var(--border-soft); border-radius: 12px; overflow: hidden; }

/* ==========================================================================
   Responsive — pas de saut brutal de mise en page
   ========================================================================== */
@media (max-width: 900px) {
  .block-container { padding: 1rem 0.6rem 2rem; }
  div[data-testid="stMetricValue"] { font-size: 22px; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Données géographiques (chargées une seule fois)
# ---------------------------------------------------------------------------
gov_geo = load_geojson("gouvernorats.geojson")
del_geo = load_geojson("delegations.geojson")

# ---------------------------------------------------------------------------
# État de session
# ---------------------------------------------------------------------------
defaults = {"seed": 0, "view": "Par gouvernorat", "focus_gov": None, "selected_id": None, "tab": "Carte", "show_points": False}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ---------------------------------------------------------------------------
# Génération des données simulées (dépend uniquement de la seed)
# ---------------------------------------------------------------------------
dataset = generate_network_data(del_geo["features"], gov_geo["features"], seed=st.session_state.seed)
gov_df, del_df, reclamations_df = dataset.gov_df, dataset.del_df, dataset.reclamations_df

# ---------------------------------------------------------------------------
# Barre latérale — contrôles
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<span class="orange-badge">orange</span>', unsafe_allow_html=True)
    st.markdown("### Supervision Réseau")
    st.caption("Cartographie des réclamations · données simulées")

    st.session_state.view = st.radio("Vue", ["Par gouvernorat", "Par délégation"], index=["Par gouvernorat", "Par délégation"].index(st.session_state.view))

    if st.session_state.view == "Par délégation":
        gov_options = ["Toutes (national)"] + sorted(gov_df["name"].tolist())
        current_label = "Toutes (national)"
        if st.session_state.focus_gov:
            match = gov_df[gov_df["id"] == st.session_state.focus_gov]
            if not match.empty:
                current_label = match.iloc[0]["name"]
        chosen = st.selectbox("Gouvernorat", gov_options, index=gov_options.index(current_label))
        if chosen == "Toutes (national)":
            st.session_state.focus_gov = None
        else:
            st.session_state.focus_gov = gov_df[gov_df["name"] == chosen].iloc[0]["id"]
    else:
        st.session_state.focus_gov = None

    search = st.text_input("Rechercher une zone", "")
    status_filter = st.radio("Statut", ["Tous", "🟢 Opérationnel", "🟠 Dégradé", "🔴 Coupé"], horizontal=False)
    status_map = {"Tous": "tous", "🟢 Opérationnel": "vert", "🟠 Dégradé": "orange", "🔴 Coupé": "rouge"}
    status_filter = status_map[status_filter]
    st.session_state.show_points = st.checkbox("Afficher les points de réclamation", value=st.session_state.show_points)

    st.divider()
    if st.button("🔄 Régénérer les données", use_container_width=True, type="primary"):
        st.session_state.seed += 1
        st.session_state.selected_id = None
        st.rerun()

    st.caption(
        "Fond de carte : découpage administratif réel de la Tunisie. "
        "Statuts réseau et réclamations générés aléatoirement — à remplacer "
        "par une vraie source de données (`simulate.py`)."
    )

# ---------------------------------------------------------------------------
# En-tête + indicateurs clés
# ---------------------------------------------------------------------------
st.markdown(
    '<p class="app-title">Supervision Réseau — Cartographie des Réclamations</p>'
    f'<p class="app-subtitle">Tunisie · {len(gov_df)} gouvernorats · {len(del_df)} délégations · fenêtre glissante 30 jours</p>',
    unsafe_allow_html=True,
)
st.write("")

st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)
counts = del_df["status"].value_counts()
k1.metric("Zones vertes", int(counts.get("vert", 0)), f"{round(counts.get('vert', 0) / len(del_df) * 100)}%")
k2.metric("Zones orange", int(counts.get("orange", 0)), f"{round(counts.get('orange', 0) / len(del_df) * 100)}%")
k3.metric("Zones rouges", int(counts.get("rouge", 0)), f"{round(counts.get('rouge', 0) / len(del_df) * 100)}%")
k4.metric("Réclamations (30j)", int(del_df["complaint_count"].sum()))
k5.metric("Indice qualité moyen", f"{round(del_df['score'].mean())}%")
st.markdown('</div>', unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------------------------
# Onglets personnalisés — transition fluide via boutons pill
# ---------------------------------------------------------------------------
tab_bar_l, tab_bar_r = st.columns(2, gap="small")
with tab_bar_l:
    if st.button("🗺️ Carte interactive", type="primary" if st.session_state.tab == "Carte" else "secondary",
                 use_container_width=True, key="tab_map"):
        st.session_state.tab = "Carte"
        st.rerun()
with tab_bar_r:
    if st.button("📊 Statistiques", type="primary" if st.session_state.tab == "Statistiques" else "secondary",
                 use_container_width=True, key="tab_stats"):
        st.session_state.tab = "Statistiques"
        st.rerun()

st.write("")

# ---------------------------------------------------------------------------
# Onglet Carte interactive
# ---------------------------------------------------------------------------
if st.session_state.tab == "Carte":
    col_map, col_detail = st.columns([1.5, 1], gap="large")
    detail_slot = col_detail.empty()

    is_gov_view = st.session_state.view == "Par gouvernorat"

    if is_gov_view:
        features = gov_geo["features"]
        id_field, name_field = "gouv_id", "gouv_fr"
        status_by_id = {r["id"]: {"status": r["status"], "count": r["complaint_count"], "score": r["score"]} for _, r in gov_df.iterrows()}
        outline_features = None
        zoom_start, center = 6, (34.2, 9.4)
    else:
        if st.session_state.focus_gov:
            features = [f for f in del_geo["features"] if f["properties"]["gouv_id"] == st.session_state.focus_gov]
            outline_features = [f for f in gov_geo["features"] if f["properties"]["gouv_id"] == st.session_state.focus_gov]
            zoom_start, center = 9, (34.2, 9.4)
        else:
            features = del_geo["features"]
            outline_features = gov_geo["features"]
            zoom_start, center = 6, (34.2, 9.4)
        id_field, name_field = "id", "del_fr"
        status_by_id = {r["id"]: {"status": r["status"], "count": r["complaint_count"], "score": r["score"]} for _, r in del_df.iterrows()}

    with col_map:
        # Préparer les points GPS des réclamations pour la superposition sur la carte
        complaint_points = None
        if st.session_state.show_points and {"Latitude", "Longitude"}.issubset(reclamations_df.columns):
            points_df = reclamations_df.dropna(subset=["Latitude", "Longitude"]).copy()
            if is_gov_view:
                if st.session_state.selected_id:
                    points_df = points_df[points_df["gouv_id"] == st.session_state.selected_id]
            else:
                if st.session_state.focus_gov:
                    points_df = points_df[points_df["gouv_id"] == st.session_state.focus_gov]
                if st.session_state.selected_id:
                    points_df = points_df[points_df["delegation_id"] == st.session_state.selected_id]

            # Ajouter les noms lisibles pour les tooltips
            for col in ("delegation_name", "gouv_name", "type", "statut"):
                if col not in points_df.columns:
                    points_df[col] = ""

            complaint_points = points_df[
                ["Latitude", "Longitude", "statut", "type", "delegation_name", "gouv_name"]
            ].to_dict("records")

        fmap = build_map(
            features,
            id_field,
            name_field,
            status_by_id,
            selected_id=st.session_state.selected_id,
            outline_features=outline_features,
            zoom_start=zoom_start,
            center=center,
            complaint_points=complaint_points,
            show_points=st.session_state.show_points,
        )
        map_event = st_folium(fmap, height=620, use_container_width=True, returned_objects=["last_active_drawing"])

    if map_event and map_event.get("last_active_drawing"):
        clicked_props = map_event["last_active_drawing"].get("properties", {})
        clicked_id = clicked_props.get(id_field)
        if clicked_id and clicked_id != st.session_state.selected_id:
            st.session_state.selected_id = clicked_id
            st.rerun()

    # -- sélecteur de secours (recherche texte) -----------------------------
    st.write("")
    df_current = gov_df if is_gov_view else (del_df[del_df["gouv_id"] == st.session_state.focus_gov] if st.session_state.focus_gov else del_df)
    df_filtered = df_current.copy()
    if status_filter != "tous":
        df_filtered = df_filtered[df_filtered["status"] == status_filter]
    if search.strip():
        df_filtered = df_filtered[df_filtered["name"].str.lower().str.contains(search.strip().lower())]
    df_filtered = df_filtered.sort_values(by=["status", "complaint_count"], key=lambda s: s.map({"rouge": 0, "orange": 1, "vert": 2}) if s.name == "status" else s, ascending=[True, False])

    st.markdown('<p class="app-subtitle" style="font-size:14px; font-weight:700; color:#E9EDF3; margin-bottom:6px;">'
                f'Liste des zones ({len(df_filtered)})</p>', unsafe_allow_html=True)
    left, right = st.columns([2, 1])
    with left:
        display_df = df_filtered[["name", "status", "score", "complaint_count"]].rename(
            columns={"name": "Zone", "status": "Statut", "score": "Indice", "complaint_count": "Réclamations"}
        )
        display_df["Statut"] = display_df["Statut"].map(STATUS_EMOJI) + " " + display_df["Statut"].map(STATUS_LABELS)
        st.dataframe(display_df, hide_index=True, use_container_width=True, height=280)
    with right:
        if not df_filtered.empty:
            options = df_filtered["id"].tolist()
            labels = {row["id"]: f"{STATUS_EMOJI[row['status']]} {row['name']} ({row['complaint_count']})" for _, row in df_filtered.iterrows()}
            default_index = options.index(st.session_state.selected_id) if st.session_state.selected_id in options else 0
            picked = st.selectbox("Sélectionner une zone", options, index=default_index, format_func=lambda i: labels[i])
            if picked != st.session_state.selected_id:
                st.session_state.selected_id = picked
                st.rerun()
        else:
            st.info("Aucune zone ne correspond à la recherche.")

    # -- panneau de détail (rempli après coup, dans le slot réservé) --------
    with detail_slot.container():
        sid = st.session_state.selected_id
        source_df = gov_df if is_gov_view else del_df
        row = source_df[source_df["id"] == sid]
        if row.empty:
            # Skeleton loader — état « en attente de sélection »
            st.markdown(
                '<div class="zone-card" style="text-align:center; padding:34px 18px;">'
                '<div class="sk-circle"></div>'
                '<div class="sk-line" style="width:70%; margin:0 auto 10px;"></div>'
                '<div class="sk-line" style="width:45%; margin:0 auto;"></div>'
                '<div style="color:#4B5568; font-size:12px; margin-top:16px;">'
                "📍 Sélectionnez une zone sur la carte, dans la liste ou via le menu déroulant pour afficher le détail des réclamations."
                "</div></div>",
                unsafe_allow_html=True,
            )
        else:
            r = row.iloc[0]
            color = STATUS_COLORS[r["status"]]
            st.markdown(
                f"""
                <div class="zone-card">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
                    <div>
                      <div style="font-size:10.5px; color:#8B93A3; text-transform:uppercase; letter-spacing:0.6px; font-weight:700;">
                        {"Gouvernorat" if is_gov_view else "Délégation · " + r["gouv_name"]}
                      </div>
                      <div style="font-size:20px; font-weight:800; margin-top:3px; letter-spacing:-0.3px;">{r['name']}</div>
                    </div>
                    <span class="status-pill" style="color:{color};">
                      <span class="status-dot" style="background:{color};"></span>
                      {STATUS_LABELS[r['status']]}
                    </span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Indice qualité", f"{r['score']}%")
            m2.metric("Réclamations (30j)", int(r["complaint_count"]))
            if is_gov_view:
                zone_reclam = reclamations_df[reclamations_df["gouv_id"] == sid]
            else:
                zone_reclam = reclamations_df[reclamations_df["delegation_id"] == sid]
            open_count = int((zone_reclam["statut"] == "En cours").sum())
            m3.metric("Dossiers en cours", open_count)

            # Barre d'indice qualité stylée (orange signature)
            st.markdown(
                f'<div style="margin:6px 0 2px;"><span style="font-size:11px; color:#8B93A3; font-weight:600;">'
                f'Indice qualité — {r["score"]}%</span></div>'
                f'<div class="quality-bar"><span style="width:{r["score"]}%"></span></div>',
                unsafe_allow_html=True,
            )

            trend = last_n_days_counts(zone_reclam, 7)
            st.caption("Réclamations · 7 derniers jours")
            st.bar_chart(trend, height=140, color="#FF7900")

            if is_gov_view and int(r["delegation_count"]) > 0:
                if st.button(f"Voir les {int(r['delegation_count'])} délégations →", use_container_width=True, type="secondary"):
                    st.session_state.view = "Par délégation"
                    st.session_state.focus_gov = sid
                    st.session_state.selected_id = None
                    st.rerun()

            st.caption(f"Dernières réclamations{' (toutes délégations)' if is_gov_view else ''}")
            if zone_reclam.empty:
                st.caption("Aucune réclamation enregistrée.")
            else:
                for _, rec in zone_reclam.sort_values("date", ascending=False).head(12).iterrows():
                    tag_class = "tag-ok" if rec["statut"] == "Résolue" else "tag-open"
                    gps_txt = ""
                    if pd.notna(rec.get("Latitude")) and pd.notna(rec.get("Longitude")):
                        gps_txt = f" · GPS {float(rec['Latitude']):.5f}, {float(rec['Longitude']):.5f}"
                    st.markdown(
                        f"""
                        <div class="record-card">
                          <div class="record-top">
                            <span>{rec['type']}</span>
                            <span class="{tag_class}">{rec['statut']}</span>
                          </div>
                          <div class="record-meta">{rec['date'].strftime('%d %b · %H:%M')} · {rec['secteur']} · {rec['canal']}{gps_txt}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

# ---------------------------------------------------------------------------
# Onglet Statistiques
# ---------------------------------------------------------------------------
else:
    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown('<p class="app-subtitle" style="font-size:14px; font-weight:700; color:#E9EDF3;">Répartition des statuts (délégations)</p>',
                    unsafe_allow_html=True)
        pie_df = del_df["status"].value_counts().reset_index()
        pie_df.columns = ["status", "count"]
        pie_df["label"] = pie_df["status"].map(STATUS_LABELS)
        fig_pie = px.pie(
            pie_df, names="label", values="count",
            color="status", color_discrete_map={"vert": "#22C55E", "orange": "#FF7900", "rouge": "#EF4444"},
            hole=0.55,
        )
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#E9EDF3", legend_title="",
                              margin=dict(l=8, r=8, t=8, b=8))
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    with c2:
        st.markdown('<p class="app-subtitle" style="font-size:14px; font-weight:700; color:#E9EDF3;">Top 10 gouvernorats les plus impactés</p>',
                    unsafe_allow_html=True)
        top10 = gov_df.sort_values("complaint_count", ascending=False).head(10)
        fig_bar = px.bar(
            top10, x="complaint_count", y="name", orientation="h",
            color="status", color_discrete_map={"vert": "#22C55E", "orange": "#FF7900", "rouge": "#EF4444"},
            labels={"complaint_count": "Réclamations", "name": ""},
        )
        fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E9EDF3",
                              yaxis={"categoryorder": "total ascending"}, showlegend=False,
                              margin=dict(l=8, r=8, t=8, b=8))
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    # -- mini-tendances (sparklines) par état réseau -------------------------
    st.markdown('<p class="app-subtitle" style="font-size:14px; font-weight:700; color:#E9EDF3; margin-top:8px;">Tendance 14 jours par état réseau</p>',
                unsafe_allow_html=True)
    del_status_map = del_df.set_index("id")["status"].to_dict()
    rec_status = reclamations_df.copy()
    rec_status["status"] = rec_status["delegation_id"].map(del_status_map)

    def _daily_series(subset: pd.DataFrame, n: int = 14) -> pd.DataFrame:
        """Série quotidienne {jour, count} sur les n derniers jours."""
        today = pd.Timestamp.now().normalize()
        days = pd.date_range(today - pd.Timedelta(days=n - 1), today, freq="D")
        if subset.empty:
            vals = [0] * n
        else:
            g = subset.groupby(subset["date"].dt.normalize()).size()
            vals = [int(g.get(d, 0)) for d in days]
        return pd.DataFrame({"jour": days.strftime("%d/%m"), "count": vals})

    FILL_RGBA = {"vert": "rgba(34,197,94,0.12)", "orange": "rgba(255,121,0,0.14)", "rouge": "rgba(239,68,68,0.12)"}
    SPARK_TITLES = {"vert": "🟢 Opérationnel", "orange": "🟠 Dégradé", "rouge": "🔴 Coupé"}
    spark_cols = st.columns(3, gap="medium")
    for col, status in zip(spark_cols, ("vert", "orange", "rouge")):
        with col:
            st.markdown(f'<p style="font-size:11px; color:#8B93A3; font-weight:600; margin:0 0 4px;">{SPARK_TITLES[status]}</p>',
                        unsafe_allow_html=True)
            spark_df = _daily_series(rec_status[rec_status["status"] == status])
            fig_spark = px.area(spark_df, x="jour", y="count", labels={"jour": "", "count": ""})
            fig_spark.update_traces(
                line_color=STATUS_COLORS[status], line_width=1.8,
                fillcolor=FILL_RGBA[status],
            )
            fig_spark.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=0, b=0), height=96,
                xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            )
            st.plotly_chart(fig_spark, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<p class="app-subtitle" style="font-size:14px; font-weight:700; color:#E9EDF3; margin-top:10px;">Évolution des réclamations — 30 derniers jours</p>',
                unsafe_allow_html=True)
    daily = reclamations_df.copy()
    daily["day"] = daily["date"].dt.date
    daily_counts = daily.groupby("day").size().reset_index(name="count")
    fig_line = px.area(daily_counts, x="day", y="count", labels={"day": "", "count": "Réclamations"})
    fig_line.update_traces(line_color="#FF7900", fillcolor="rgba(255,121,0,0.15)")
    fig_line.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E9EDF3",
                           margin=dict(l=8, r=8, t=8, b=8))
    st.plotly_chart(fig_line, use_container_width=True, config={"displayModeBar": False})
