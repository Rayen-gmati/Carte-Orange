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
    .main { background-color: #0A0D12; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }

    .orange-badge {
        background:#FF7900; color:#101317; font-weight:800; font-size:13px;
        padding:5px 10px; border-radius:6px; display:inline-block;
    }
    .app-title { font-weight:700; font-size:20px; color:#E7EAEF; margin:0; }
    .app-subtitle { font-size:12.5px; color:#8B93A3; margin:0; }

    div[data-testid="stMetric"] {
        background:#12161D; border:1px solid #232A36; border-radius:10px; padding:12px 14px;
    }
    div[data-testid="stMetricValue"] { font-family:'IBM Plex Mono', monospace; }

    .zone-card {
        background:#12161D; border:1px solid #232A36; border-radius:12px; padding:16px 18px;
    }
    .status-pill {
        display:inline-flex; align-items:center; gap:6px; font-weight:700; font-size:12px;
        padding:4px 10px; border-radius:999px; border:1px solid currentColor;
    }
    .record-card {
        background:#171C24; border:1px solid #232A36; border-radius:8px; padding:8px 10px; margin-bottom:6px;
    }
    .record-top { display:flex; justify-content:space-between; font-size:12.5px; font-weight:600; }
    .record-meta { font-size:10.5px; color:#8B93A3; margin-top:2px; }
    .tag-ok { color:#22C55E; font-size:10px; font-weight:700; }
    .tag-open { color:#EF4444; font-size:10px; font-weight:700; }
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
defaults = {"seed": 0, "view": "Par gouvernorat", "focus_gov": None, "selected_id": None}
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

    st.divider()
    if st.button("🔄 Régénérer les données", use_container_width=True):
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

k1, k2, k3, k4, k5 = st.columns(5)
counts = del_df["status"].value_counts()
k1.metric("Zones vertes", int(counts.get("vert", 0)), f"{round(counts.get('vert', 0) / len(del_df) * 100)}%")
k2.metric("Zones orange", int(counts.get("orange", 0)), f"{round(counts.get('orange', 0) / len(del_df) * 100)}%")
k3.metric("Zones rouges", int(counts.get("rouge", 0)), f"{round(counts.get('rouge', 0) / len(del_df) * 100)}%")
k4.metric("Réclamations (30j)", int(del_df["complaint_count"].sum()))
k5.metric("Indice qualité moyen", f"{round(del_df['score'].mean())}%")

st.write("")

tab_map, tab_stats = st.tabs(["🗺️ Carte interactive", "📊 Statistiques"])

# ---------------------------------------------------------------------------
# Onglet Carte
# ---------------------------------------------------------------------------
with tab_map:
    col_map, col_detail = st.columns([1.5, 1])
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
        fmap = build_map(
            features,
            id_field,
            name_field,
            status_by_id,
            selected_id=st.session_state.selected_id,
            outline_features=outline_features,
            zoom_start=zoom_start,
            center=center,
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

    st.subheader(f"Liste des zones ({len(df_filtered)})")
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
            st.markdown(
                '<div class="zone-card" style="text-align:center; color:#4B5568; padding:40px 16px;">'
                "📍 Sélectionnez une zone sur la carte, dans la liste ou via le menu déroulant pour afficher le détail des réclamations."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            r = row.iloc[0]
            color = STATUS_COLORS[r["status"]]
            st.markdown(
                f"""
                <div class="zone-card">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                      <div style="font-size:10.5px; color:#8B93A3; text-transform:uppercase; letter-spacing:0.5px; font-weight:600;">
                        {"Gouvernorat" if is_gov_view else "Délégation · " + r["gouv_name"]}
                      </div>
                      <div style="font-size:19px; font-weight:700; margin-top:2px;">{r['name']}</div>
                    </div>
                    <span class="status-pill" style="color:{color};">{STATUS_EMOJI[r['status']]} {STATUS_LABELS[r['status']]}</span>
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

            st.progress(int(r["score"]))

            trend = last_n_days_counts(zone_reclam, 7)
            st.caption("Réclamations · 7 derniers jours")
            st.bar_chart(trend, height=140, color="#FF7900")

            if is_gov_view and int(r["delegation_count"]) > 0:
                if st.button(f"Voir les {int(r['delegation_count'])} délégations →", use_container_width=True):
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
                    st.markdown(
                        f"""
                        <div class="record-card">
                          <div class="record-top">
                            <span>{rec['type']}</span>
                            <span class="{tag_class}">{rec['statut']}</span>
                          </div>
                          <div class="record-meta">{rec['date'].strftime('%d %b · %H:%M')} · {rec['secteur']} · {rec['canal']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

# ---------------------------------------------------------------------------
# Onglet Statistiques
# ---------------------------------------------------------------------------
with tab_stats:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Répartition des statuts (délégations)")
        pie_df = del_df["status"].value_counts().reset_index()
        pie_df.columns = ["status", "count"]
        pie_df["label"] = pie_df["status"].map(STATUS_LABELS)
        fig_pie = px.pie(
            pie_df, names="label", values="count",
            color="status", color_discrete_map={"vert": "#22C55E", "orange": "#FF7900", "rouge": "#EF4444"},
            hole=0.55,
        )
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#E7EAEF", legend_title="")
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("Top 10 gouvernorats les plus impactés")
        top10 = gov_df.sort_values("complaint_count", ascending=False).head(10)
        fig_bar = px.bar(
            top10, x="complaint_count", y="name", orientation="h",
            color="status", color_discrete_map={"vert": "#22C55E", "orange": "#FF7900", "rouge": "#EF4444"},
            labels={"complaint_count": "Réclamations", "name": ""},
        )
        fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E7EAEF", yaxis={"categoryorder": "total ascending"}, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Évolution des réclamations — 30 derniers jours")
    daily = reclamations_df.copy()
    daily["day"] = daily["date"].dt.date
    daily_counts = daily.groupby("day").size().reset_index(name="count")
    fig_line = px.area(daily_counts, x="day", y="count", labels={"day": "", "count": "Réclamations"})
    fig_line.update_traces(line_color="#FF7900", fillcolor="rgba(255,121,0,0.15)")
    fig_line.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E7EAEF")
    st.plotly_chart(fig_line, use_container_width=True)
