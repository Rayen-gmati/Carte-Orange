#!/usr/bin/env python3
"""
generate_dataset.py
-------------------
Export CSV de clients simulés pour Orange Data Mining.

Usage :
    python generate_dataset.py                        # 1000 clients, 8 colonnes de base
    python generate_dataset.py --rows 5000             # 5000 clients
    python generate_dataset.py --with-coords           # + Latitude, Longitude
    python generate_dataset.py --with-geo              # + Delegation_ID, Delegation, Gouvernorat_ID, Gouvernorat
    python generate_dataset.py --with-coords --with-geo  # toutes les colonnes
    python generate_dataset.py --output mon_fichier.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from client_data import generate_clients

DATA_DIR = Path(__file__).parent / "data"

# Colonnes de base (compatibles Orange Data Mining)
BASE_COLUMNS = [
    "ID_Client",
    "Type_Contrat",
    "Anciennete_Mois",
    "Conso_Data_Go",
    "Nbr_Reclamations",
    "Motif_Principal",
    "Statut_Ticket",
    "Churn",
]

GEO_COLUMNS = ["Delegation_ID", "Delegation", "Gouvernorat_ID", "Gouvernorat"]
COORD_COLUMNS = ["Latitude", "Longitude"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère un CSV de clients Orange Tunisie pour export Orange Data Mining."
    )
    parser.add_argument(
        "--rows", type=int, default=1000,
        help="Nombre de clients à générer (défaut : 1000)",
    )
    parser.add_argument(
        "--seed", type=int, default=0,
        help="Graine de génération (défaut : 0, même seed = mêmes résultats)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Chemin du fichier CSV de sortie (défaut : clients_tunisie.csv)",
    )
    parser.add_argument(
        "--with-coords", action="store_true",
        help="Ajouter les colonnes Latitude, Longitude au CSV",
    )
    parser.add_argument(
        "--with-geo", action="store_true",
        help="Ajouter Delegation_ID, Delegation, Gouvernorat_ID, Gouvernorat au CSV",
    )
    args = parser.parse_args()

    # Charger les GeoJSON
    with open(DATA_DIR / "gouvernorats.geojson", encoding="utf-8") as f:
        gov_geo = json.load(f)
    with open(DATA_DIR / "delegations.geojson", encoding="utf-8") as f:
        del_geo = json.load(f)

    print(f"Génération de {args.rows} clients (seed={args.seed})...")
    df = generate_clients(del_geo["features"], gov_geo["features"], n_clients=args.rows, seed=args.seed)

    # Sélection des colonnes à exporter
    columns = list(BASE_COLUMNS)
    if args.with_coords:
        columns.extend(COORD_COLUMNS)
    if args.with_geo:
        columns.extend(GEO_COLUMNS)

    df_export = df[columns]

    # Export
    output_path = args.output or "clients_tunisie.csv"
    df_export.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Export terminé : {output_path}")
    print(f"  → {len(df_export)} lignes, {len(columns)} colonnes : {', '.join(columns)}")


if __name__ == "__main__":
    main()
