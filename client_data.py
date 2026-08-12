"""
client_data.py
--------------
Géolocalisation des clients/réclamations par coordonnées GPS réelles.

Pipeline : (lat, lon) → délégation déduite par point-in-polygon (Shapely).

Ce module fournit :
- `random_point_in_polygon()`  : génère un point aléatoire DANS un polygone
- `find_delegation_for_point()` : retrouve la délégation à partir de (lat, lon)
- `generate_clients()`         : génère un DataFrame clients géolocalisés
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.prepared import prep

DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# Constantes domaine client (Orange Tunisie)
# ---------------------------------------------------------------------------

CONTRAT_TYPES = ["Mobile prépayé", "Mobile postpayé", "Fibre optique", "ADSL", "4G Box"]

MOTIFS = [
    "Coupure totale du réseau",
    "Panne antenne relais",
    "Zone blanche persistante",
    "Débit internet très faible",
    "Perte intermittente du signal",
    "Aucune couverture en intérieur",
    "Latence / lenteur data",
    "Dégradation suite à maintenance",
]

STATUT_TICKET = ["En cours", "Résolu"]


def _seed_for(*parts: str) -> int:
    """Seed déterministe (0..2**32-1) dérivée d'une chaîne."""
    digest = hashlib.md5("_".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


# ---------------------------------------------------------------------------
# Géométrie — génération de points aléatoires dans un polygone
# ---------------------------------------------------------------------------


def random_point_in_polygon(
    geometry: Polygon | MultiPolygon,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Génère un point (latitude, longitude) uniformément dans un polygone.

    Utilise le *rejection sampling* : tire des points dans la bounding box
    jusqu'à ce qu'un tombe à l'intérieur du polygone.

    Parameters
    ----------
    geometry : Polygon ou MultiPolygon Shapely
    rng : numpy Generator (optionnel, pour reproductibilité)

    Returns
    -------
    (latitude, longitude) en degrés décimaux
    """
    if rng is None:
        rng = np.random.default_rng()

    min_lon, min_lat, max_lon, max_lat = geometry.bounds

    # rejection sampling — boucle jusqu'à tomber dans le polygone
    max_attempts = 10_000
    for _ in range(max_attempts):
        lon = rng.uniform(min_lon, max_lon)
        lat = rng.uniform(min_lat, max_lat)
        if geometry.contains(Point(lon, lat)):
            return float(lat), float(lon)

    # Fallback : centroïde (ne devrait arriver que pour des polygones dégénérés)
    centroid = geometry.centroid
    return float(centroid.y), float(centroid.x)


# ---------------------------------------------------------------------------
# Géométrie — lookup délégation à partir d'un point (lat, lon)
# ---------------------------------------------------------------------------


def find_delegation_for_point(
    lat: float,
    lon: float,
    del_features: Sequence[dict],
    prepared_geoms: dict | None = None,
) -> tuple[str | None, str | None]:
    """Retrouve la délégation contenant le point (lat, lon).

    Parameters
    ----------
    lat, lon : coordonnées GPS du point
    del_features : liste des features GeoJSON des délégations
    prepared_geoms : dict {del_id: prepared_geometry} pré-calculé
        (accélère considérablement les appels répétés)

    Returns
    -------
    (delegation_id, gouv_id) ou (None, None) si hors de toute délégation
    """
    point = Point(lon, lat)

    if prepared_geoms is not None:
        for del_id, (prep_geom, props) in prepared_geoms.items():
            if prep_geom.contains(point):
                return del_id, props["gouv_id"]
        return None, None

    # Version sans géométries préparées (plus lente, pour usage ponctuel)
    for feat in del_features:
        geom = shape(feat["geometry"])
        if geom.contains(point):
            props = feat["properties"]
            return props["id"], props["gouv_id"]
    return None, None


def prepare_delegation_geometries(del_features: Sequence[dict]) -> dict:
    """Pré-calcule les géométries préparées pour accélérer find_delegation_for_point.

    Returns
    -------
    dict {delegation_id: (prepared_geometry, properties)}
    """
    prepared = {}
    for feat in del_features:
        del_id = feat["properties"]["id"]
        geom = shape(feat["geometry"])
        prepared[del_id] = (prep(geom), feat["properties"])
    return prepared


# ---------------------------------------------------------------------------
# Génération de clients géolocalisés
# ---------------------------------------------------------------------------


def generate_clients(
    del_features: Sequence[dict],
    gov_features: Sequence[dict],
    n_clients: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    """Génère un DataFrame de clients géolocalisés.

    Pour chaque client :
    1. Choisit une délégation "source" (uniformément parmi toutes les délégations)
    2. Génère un point (lat, lon) aléatoire DANS le polygone de cette délégation
    3. Déduit Delegation_ID / Gouvernorat_ID via find_delegation_for_point()
       (le pipeline géométrique, réutilisable sur de vraies coordonnées GPS)

    Parameters
    ----------
    del_features : features GeoJSON des délégations
    gov_features : features GeoJSON des gouvernorats
    n_clients : nombre de clients à générer
    seed : graine pour reproductibilité

    Returns
    -------
    DataFrame avec colonnes :
        ID_Client, Type_Contrat, Anciennete_Mois, Conso_Data_Go,
        Nbr_Reclamations, Motif_Principal, Statut_Ticket, Churn,
        Latitude, Longitude,
        Delegation_ID, Delegation, Gouvernorat_ID, Gouvernorat
    """
    rng = np.random.default_rng(seed)

    # Préparer les géométries pour accélérer les lookups
    prepared_geoms = prepare_delegation_geometries(del_features)

    # Mapping del_id -> (del_name, gouv_id, gouv_name)
    del_info = {}
    for feat in del_features:
        props = feat["properties"]
        del_info[props["id"]] = (props["del_fr"], props["gouv_id"], props["gouv_fr"])

    # Mapping gouv_id -> gouv_name
    gov_info = {}
    for feat in gov_features:
        props = feat["properties"]
        gov_info[props["gouv_id"]] = props["gouv_fr"]

    # Shapely geometries pour le tirage aléatoire
    del_geometries = []
    for feat in del_features:
        del_id = feat["properties"]["id"]
        geom = shape(feat["geometry"])
        del_geometries.append((del_id, geom))

    rows = []
    for i in range(n_clients):
        client_rng = np.random.default_rng(_seed_for(f"client_{i}", str(seed)))

        # 1. Choisir une délégation source (uniformément)
        source_idx = rng.integers(0, len(del_geometries))
        source_id, source_geom = del_geometries[source_idx]

        # 2. Générer un point aléatoire DANS le polygone source
        lat, lon = random_point_in_polygon(source_geom, rng=client_rng)

        # 3. Déduire délégation/gouvernorat via point-in-polygon
        deduced_del_id, deduced_gouv_id = find_delegation_for_point(
            lat, lon, del_features, prepared_geoms=prepared_geoms
        )

        # Si le point tombe hors de toute délégation (bordure, mer...), utiliser la source
        if deduced_del_id is None:
            deduced_del_id = source_id
            deduced_gouv_id = del_info[source_id][1]

        # Attributs client
        contrat = CONTRAT_TYPES[rng.integers(0, len(CONTRAT_TYPES))]
        anciennete = int(rng.integers(1, 120))  # mois
        conso_data = round(float(rng.exponential(8.0)), 2)
        nbr_reclam = int(rng.poisson(1.5))
        motif = MOTIFS[rng.integers(0, len(MOTIFS))]

        # Statut ticket : ~60% résolu
        ticket_resolved = rng.random() < 0.6
        statut = "Résolu" if ticket_resolved else "En cours"

        # Churn : corrélation avec nombre de réclamations + conso faible
        churn_prob = min(0.5, 0.05 + nbr_reclam * 0.08 + (0.02 if conso_data < 2.0 else 0))
        churn = int(rng.random() < churn_prob)

        # Noms lisibles
        del_name = del_info.get(deduced_del_id, ("", "", ""))[0]
        gouv_name = gov_info.get(deduced_gouv_id, "")

        rows.append({
            "ID_Client": f"C{seed:02d}{i:05d}",
            "Type_Contrat": contrat,
            "Anciennete_Mois": anciennete,
            "Conso_Data_Go": conso_data,
            "Nbr_Reclamations": nbr_reclam,
            "Motif_Principal": motif,
            "Statut_Ticket": statut,
            "Churn": churn,
            "Latitude": round(lat, 6),
            "Longitude": round(lon, 6),
            "Delegation_ID": deduced_del_id,
            "Delegation": del_name,
            "Gouvernorat_ID": deduced_gouv_id,
            "Gouvernorat": gouv_name,
        })

    df = pd.DataFrame(rows)

    # --- Test de cohérence : vérifier que (lat, lon) tombe dans la délégation enregistrée
    _verify_geocoherence(df, del_features, prepared_geoms, sample_size=50)

    return df


def _verify_geocoherence(
    df: pd.DataFrame,
    del_features: Sequence[dict],
    prepared_geoms: dict,
    sample_size: int = 50,
) -> None:
    """Vérifie qu'un échantillon de points (lat, lon) tombe bien dans le polygone
    de la délégation enregistrée. Lève AssertionError sinon."""
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)

    mismatches = []
    for idx, row in sample.iterrows():
        point = Point(row["Longitude"], row["Latitude"])
        expected_id = row["Delegation_ID"]

        # Vérifier que le point est dans le polygone attendu
        if expected_id in prepared_geoms:
            prep_geom, _ = prepared_geoms[expected_id]
            if not prep_geom.contains(point):
                mismatches.append(
                    f"  Client {row['ID_Client']}: ({row['Latitude']:.5f}, {row['Longitude']:.5f}) "
                    f"→ attendu {expected_id}, mais hors du polygone"
                )

    if mismatches:
        msg = (
            f"Test de cohérence géo ÉCHOUÉ ({len(mismatches)}/{sample_size} erreurs) :\n"
            + "\n".join(mismatches[:10])
        )
        raise AssertionError(msg)
