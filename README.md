# Supervision Réseau — Cartographie des Réclamations (Tunisie)

Prototype Streamlit réalisé dans le cadre d'un stage PFE. Affiche une carte de
la Tunisie (par gouvernorat ou par délégation) colorée selon l'état simulé du
réseau :

- 🟢 **vert** — réseau opérationnel
- 🟠 **orange** — service dégradé (intermittent)
- 🔴 **rouge** — réseau coupé

Chaque zone rouge/orange déclenche des réclamations simulées (type de panne,
canal de contact, secteur, statut ouvert/résolu), visibles dans le panneau de
détail au clic sur la carte, dans la liste, ou via le menu déroulant.

## Structure du projet

```
carto_streamlit/
├── app.py            # application Streamlit (page principale)
├── simulate.py        # génération du jeu de données simulé (à remplacer par la vraie source)
├── geo_utils.py        # chargement des GeoJSON + construction de la carte Folium
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

## Brancher de vraies données

Toute la simulation est isolée dans `simulate.py`, fonction
`generate_network_data(delegation_features, governorate_features, seed)`.
Elle retourne un objet `NetworkDataset` avec trois `DataFrame` :

- `gov_df`  : un gouvernorat par ligne (`id`, `name`, `score`, `status`, `complaint_count`, `delegation_count`)
- `del_df`  : une délégation par ligne (mêmes colonnes + `gouv_id`, `gouv_name`)
- `reclamations_df` : une réclamation par ligne (`delegation_id`, `gouv_id`, `date`, `type`, `canal`, `secteur`, `statut`)

Pour brancher la vraie base de réclamations, il suffit de remplacer le corps
de cette fonction (ex. requête SQL / API) en conservant ces mêmes colonnes en
sortie — le reste de l'application (`app.py`) n'a rien à changer.

## Notes

- Les géométries (gouvernorats / délégations) sont un découpage administratif
  réel de la Tunisie (source ouverte), pas une simulation.
- Le bouton **« Régénérer les données »** tire un nouveau jeu de données
  simulé (utile pour la démonstration).
- Le menu déroulant « Sélectionner une zone » sert de recherche/sélection de
  secours en plus du clic sur la carte.
