# Supervision Réseau — Cartographie des Réclamations (Tunisie)

Prototype d'une cartographie réalisé dans le cadre d'un stage 1ère année ingénieurie. Affiche une carte de
la Tunisie (par gouvernorat ou par délégation) colorée selon l'état simulé du
réseau :

- 🟢 **vert** — réseau opérationnel
- 🟠 **orange** — service dégradé (intermittent)
- 🔴 **rouge** — réseau coupé

Chaque zone rouge/orange déclenche des réclamations simulées (type de panne,
canal de contact, secteur, statut ouvert/résolu), visibles dans le panneau de
détail au clic sur la carte, dans la liste, ou via le menu déroulant.

Chaque réclamation est désormais **géolocalisée** par des coordonnées GPS réelles
(Latitude, Longitude), et sa délégation/gouvernorat est **déduite géométriquement**
par un test point-in-polygon (Shapely), et non plus assignée directement.

## Structure du projet

```
carto_streamlit/
├── app.py                # application Streamlit (page principale)
├── simulate.py            # génération du jeu de données simulé + coordonnées GPS
├── client_data.py        # géolocalisation : random_point_in_polygon, find_delegation_for_point, generate_clients
├── generate_dataset.py   # export CSV pour Orange Data Mining (CLI)
├── test_geo.py           # test de cohérence géographique (lat/lon → délégation)
├── geo_utils.py          # chargement des GeoJSON + construction de la carte Folium
├── data/
│   ├── gouvernorats.geojson   # 24 gouvernorats — découpage administratif réel
│   └── delegations.geojson    # 264 délégations — découpage administratif réel
├── requirements.txt
└── README.md
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`.

## Flux de géolocalisation (lat/lon → délégation)

Le pipeline de génération suit ce flux :

1. Pour chaque client/réclamation, une **délégation source** est choisie (pondérée pour garder une répartition réaliste)
2. Un **point GPS aléatoire** (Latitude, Longitude) est généré **à l'intérieur** du polygone de cette délégation via `random_point_in_polygon()` (rejection sampling dans la bounding box)
3. La **délégation et le gouvernorat sont déduits** géométriquement en appelant `find_delegation_for_point()` sur ce point — un vrai test point-in-polygon Shapely, réutilisable sur de vraies coordonnées GPS

Ce pipeline garantit que `(lat, lon) → délégation` est un calcul géométrique,
indépendant de l'assignation directe, et peut être réutilisé pour ingérer de
vraies données GPS.

## Export CSV pour Orange Data Mining

```bash
# 8 colonnes de base (compatible Orange Data Mining)
python generate_dataset.py --rows 1000

# + coordonnées GPS
python generate_dataset.py --with-coords --rows 2000

# + informations géographiques (délégation, gouvernorat)
python generate_dataset.py --with-geo

# Toutes les colonnes
python generate_dataset.py --with-coords --with-geo --rows 5000 --output complet.csv
```

Options :
- `--rows N` : nombre de clients (défaut : 1000)
- `--seed N` : graine de génération (même seed = mêmes résultats)
- `--output FICHIER.csv` : chemin de sortie (défaut : `clients_tunisie.csv`)
- `--with-coords` : ajoute `Latitude`, `Longitude`
- `--with-geo` : ajoute `Delegation_ID`, `Delegation`, `Gouvernorat_ID`, `Gouvernorat`

## Test de cohérence géographique

Vérifie que chaque point (lat, lon) tombe bien dans le polygone de la délégation enregistrée :

```bash
python test_geo.py                    # 200 clients, seed=0
python test_geo.py --clients 500 --seed 42
```

## Brancher de vraies données

Toute la simulation est isolée dans `simulate.py`, fonction
`generate_network_data(delegation_features, governorate_features, seed)`.
Elle retourne un objet `NetworkDataset` avec trois `DataFrame` :

- `gov_df`  : un gouvernorat par ligne (`id`, `name`, `score`, `status`, `complaint_count`, `delegation_count`)
- `del_df`  : une délégation par ligne (mêmes colonnes + `gouv_id`, `gouv_name`)
- `reclamations_df` : une réclamation par ligne (`delegation_id`, `gouv_id`, `date`, `type`, `canal`, `secteur`, `statut`, `Latitude`, `Longitude`)

Pour brancher la vraie base de réclamations, il suffit de remplacer le corps
de cette fonction (ex. requête SQL / API) en conservant ces mêmes colonnes en
sortie — le reste de l'application (`app.py`) n'a rien à changer.

Pour déduire la délégation à partir de vraies coordonnées GPS, utiliser
`find_delegation_for_point(lat, lon, del_features)` depuis `client_data.py`.

## Notes

- Les géométries (gouvernorats / délégations) sont un découpage administratif
  réel de la Tunisie (source ouverte), pas une simulation.
- Le bouton **« Régénérer les données »** tire un nouveau jeu de données
  simulé (utile pour la démonstration).
- Le menu déroulant « Sélectionner une zone » sert de recherche/sélection de
  secours en plus du clic sur la carte.
- La case **« Afficher les points de réclamation »** dans la sidebar superpose
  les points GPS individuels sur la carte (rouge = En cours, vert = Résolu),
  regroupés via MarkerCluster pour la lisibilité.
- La génération est **déterministe** : même seed = mêmes résultats (coordonnées
  GPS incluses).
