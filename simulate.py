"""
simulate.py
------------
Simule l'état du réseau et les réclamations clients par délégation / gouvernorat.

Ce module ne dépend d'aucune source réelle : il sert de bouchon ("mock") en
attendant le branchement sur la vraie base de réclamations Orange. La seule
chose à remplacer plus tard est `generate_network_data()` : garder les mêmes
colonnes en sortie (`gov_df`, `del_df`, `reclamations_df`) suffit pour que le
reste de l'application (app.py) continue de fonctionner sans changement.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from shapely.geometry import shape

from client_data import random_point_in_polygon

# ---------------------------------------------------------------------------
# Constantes du domaine
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    "vert": "Réseau opérationnel",
    "orange": "Service dégradé",
    "rouge": "Réseau coupé",
}

STATUS_COLORS = {
    "vert": "#22C55E",
    "orange": "#FF7900",  # couleur de marque Orange, réutilisée pour l'état "moyen"
    "rouge": "#EF4444",
}

PANNE_TYPES = [
    ("Coupure totale du réseau", 2),
    ("Panne antenne relais", 2),
    ("Zone blanche persistante", 2),
    ("Débit internet très faible", 1),
    ("Perte intermittente du signal", 1),
    ("Aucune couverture en intérieur", 1),
    ("Latence / lenteur data", 1),
    ("Dégradation suite à maintenance", 0),
]

CANAUX = [
    "Centre d'appel 1298",
    "App Orange & Moi",
    "Boutique Orange",
    "Réseaux sociaux",
    "Agence agréée",
]


def status_from_score(score: float) -> str:
    if score >= 70:
        return "vert"
    if score >= 40:
        return "orange"
    return "rouge"


def _seed_for(*parts: str) -> int:
    """Seed déterministe (0..2**32-1) dérivée d'une chaîne, pour un RNG stable
    entre deux exécutions tant que la 'seed' globale ne change pas."""
    digest = hashlib.md5("_".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


@dataclass
class NetworkDataset:
    gov_df: pd.DataFrame
    del_df: pd.DataFrame
    reclamations_df: pd.DataFrame


def generate_network_data(delegation_features: list[dict], governorate_features: list[dict], seed: int = 0) -> NetworkDataset:
    """Génère un jeu de données simulé complet.

    Parameters
    ----------
    delegation_features : liste des features GeoJSON des délégations
        (chaque `properties` doit contenir id, del_fr, del_ar, gouv_id, gouv_fr)
    governorate_features : liste des features GeoJSON des gouvernorats
        (chaque `properties` doit contenir gouv_id, gouv_fr, gouv_ar)
    seed : graine globale -> change tout le jeu de données simulé
        (utilisée par le bouton "Régénérer" de l'application)
    """
    del_rows = []
    reclamation_rows = []
    now = datetime.now()

    for feat in delegation_features:
        props = feat["properties"]
        del_id = props["id"]
        rng = np.random.default_rng(_seed_for(del_id, str(seed)))

        r = rng.random()
        if r < 0.58:
            score = 68 + rng.random() * 32
        elif r < 0.85:
            score = 38 + rng.random() * 30
        else:
            score = rng.random() * 38
        score = int(round(min(100, max(0, score))))
        status = status_from_score(score)

        base_count = round((100 - score) * (0.22 + rng.random() * 0.5))
        if status == "rouge":
            count = max(base_count, 6)
        elif status == "vert":
            count = round(rng.random() * 3)
        else:
            count = base_count

        del_rows.append(
            {
                "id": del_id,
                "name": props["del_fr"],
                "name_ar": props.get("del_ar", ""),
                "gouv_id": props["gouv_id"],
                "gouv_name": props["gouv_fr"],
                "score": score,
                "status": status,
                "complaint_count": int(count),
            }
        )

        # Préparer la géométrie Shapely pour générer des points GPS
        del_geom = shape(feat["geometry"])

        pool = PANNE_TYPES if status == "vert" else [p for p in PANNE_TYPES if p[1] > 0]
        n_records = min(int(count), 22)
        for i in range(n_records):
            days_ago = rng.random() * 30
            date = now - timedelta(days=days_ago, hours=rng.random() * 24)
            panne_label, severity = pool[rng.integers(0, len(pool))]
            canal = CANAUX[rng.integers(0, len(CANAUX))]
            secteur = f"Secteur {rng.integers(1, 6)}"
            resolve_chance = {"vert": 0.95, "orange": 0.6, "rouge": 0.28}[status]
            statut = "Résolue" if rng.random() < resolve_chance else "En cours"

            # Générer un point GPS aléatoire DANS le polygone de la délégation
            lat, lon = random_point_in_polygon(del_geom, rng=rng)

            reclamation_rows.append(
                {
                    "id": f"{del_id}-{i}",
                    "delegation_id": del_id,
                    "gouv_id": props["gouv_id"],
                    "date": date,
                    "type": panne_label,
                    "severity": severity,
                    "canal": canal,
                    "secteur": secteur,
                    "statut": statut,
                    "Latitude": round(lat, 6),
                    "Longitude": round(lon, 6),
                }
            )

    del_df = pd.DataFrame(del_rows)
    reclamations_df = pd.DataFrame(reclamation_rows)
    if not reclamations_df.empty:
        reclamations_df["date"] = pd.to_datetime(reclamations_df["date"])
        reclamations_df.sort_values("date", ascending=False, inplace=True)

    gov_agg = (
        del_df.groupby("gouv_id")
        .agg(score=("score", "mean"), complaint_count=("complaint_count", "sum"), delegation_count=("id", "count"))
        .reset_index()
    )
    gov_agg["score"] = gov_agg["score"].round().astype(int)
    gov_agg["status"] = gov_agg["score"].apply(status_from_score)

    gov_rows = []
    for feat in governorate_features:
        props = feat["properties"]
        gid = props["gouv_id"]
        match = gov_agg[gov_agg["gouv_id"] == gid]
        if not match.empty:
            row = match.iloc[0]
            score, status, count, del_count = (
                int(row["score"]),
                row["status"],
                int(row["complaint_count"]),
                int(row["delegation_count"]),
            )
        else:
            score, status, count, del_count = 50, "orange", 0, 0
        gov_rows.append(
            {
                "id": gid,
                "name": props["gouv_fr"],
                "name_ar": props.get("gouv_ar", ""),
                "score": score,
                "status": status,
                "complaint_count": count,
                "delegation_count": del_count,
            }
        )

    gov_df = pd.DataFrame(gov_rows)

    return NetworkDataset(gov_df=gov_df, del_df=del_df, reclamations_df=reclamations_df)


def last_n_days_counts(reclamations_df: pd.DataFrame, n: int = 7) -> pd.Series:
    """Retourne le nombre de réclamations par jour sur les n derniers jours
    (index 0 = il y a n-1 jours ... index n-1 = aujourd'hui)."""
    today = pd.Timestamp.now().normalize()
    days = pd.date_range(today - pd.Timedelta(days=n - 1), today, freq="D")
    if reclamations_df.empty:
        return pd.Series([0] * n, index=days.strftime("%d/%m"))
    counts = reclamations_df.copy()
    counts["day"] = counts["date"].dt.normalize()
    grouped = counts.groupby("day").size()
    values = [int(grouped.get(d, 0)) for d in days]
    return pd.Series(values, index=days.strftime("%d/%m"))
