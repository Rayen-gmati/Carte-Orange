#!/usr/bin/env python3
"""
test_geo.py
-----------
Test de cohérence géographique : vérifie que chaque point (lat, lon) généré
tombe bien dans le polygone de la délégation enregistrée.

Usage :
    python test_geo.py
    python test_geo.py --clients 500 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.prepared import prep

from client_data import generate_clients, prepare_delegation_geometries

DATA_DIR = Path(__file__).parent / "data"


def run_test(n_clients: int = 200, seed: int = 0) -> bool:
    """Test complet de cohérence géographique.

    Returns True si tous les points passent, False sinon.
    """
    print(f"Chargement des GeoJSON...")
    with open(DATA_DIR / "gouvernorats.geojson", encoding="utf-8") as f:
        gov_geo = json.load(f)
    with open(DATA_DIR / "delegations.geojson", encoding="utf-8") as f:
        del_geo = json.load(f)

    print(f"  → {len(gov_geo['features'])} gouvernorats, {len(del_geo['features'])} délégations chargés")

    # Préparer les géométries pour vérification
    prepared_geoms = prepare_delegation_geometries(del_geo["features"])

    # Générer les clients
    print(f"Génération de {n_clients} clients (seed={seed})...")
    df = generate_clients(del_geo["features"], gov_geo["features"], n_clients=n_clients, seed=seed)
    print(f"  → {len(df)} clients générés")

    # Vérifier chaque point
    print(f"\nVérification de {len(df)} points...")
    passed = 0
    failed = 0
    errors = []

    for idx, row in df.iterrows():
        lat, lon = row["Latitude"], row["Longitude"]
        expected_id = row["Delegation_ID"]

        point = Point(lon, lat)

        if expected_id in prepared_geoms:
            prep_geom, _ = prepared_geoms[expected_id]
            if prep_geom.contains(point):
                passed += 1
            else:
                failed += 1
                errors.append(
                    f"  FAIL client {row['ID_Client']}: ({lat:.6f}, {lon:.6f}) "
                    f"→ déclaré {expected_id} ({row['Delegation']}), mais hors du polygone"
                )
        else:
            failed += 1
            errors.append(
                f"  FAIL client {row['ID_Client']}: délégation {expected_id} introuvable dans les géométries"
            )

    # Rapport
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  RÉSULTAT : {passed}/{total} points passent ({passed/total*100:.1f}%)")
    print(f"{'='*60}")

    if errors:
        print(f"\n{len(errors)} erreur(s) détectée(s) :")
        for err in errors[:20]:
            print(err)
        if len(errors) > 20:
            print(f"  ... et {len(errors) - 20} autre(s)")
        return False
    else:
        print("\n✅ Tous les points sont cohérents avec leur délégation enregistrée.")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Test de cohérence géographique (lat/lon → délégation)")
    parser.add_argument("--clients", type=int, default=200, help="Nombre de clients à tester (défaut : 200)")
    parser.add_argument("--seed", type=int, default=0, help="Graine de génération (défaut : 0)")
    args = parser.parse_args()

    success = run_test(n_clients=args.clients, seed=args.seed)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
