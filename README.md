# Carte de prix Airbnb — Maroc

Dashboard interactif de l'évolution mensuelle des prix Airbnb dans plusieurs
villes du Maroc, par quartier. Données collectées par scraping (usage **privé**).

Villes : **Casablanca, Marrakech, Agadir, Tanger** (extensible via `scrape/cities.py`).

## Pipeline

```
scrape/cities.py             Config des villes (bbox, grille, niveau OSM, carte)
scrape/recon*.py             Phase 0 — validation technique (référence)
scrape/collect.py            Collecte annonces + prix mensuels -> SQLite (--city)
scrape/fetch_neighborhoods.py Frontières OSM d'une ville (--city)
scrape/build_quartiers.py    Extrait les quartiers d'une ville (--city)
scrape/geocode_clean.py      GPS->quartier + nettoyage, multi-villes -> clean.csv
scrape/make_preview.py       Aperçu PNG statique
app.py                       Dashboard Streamlit (sélecteur de ville)
```

## Installation

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt -r requirements-scrape.txt
```

## Ajouter / rafraîchir une ville

```bash
CITY=Marrakech
./.venv/bin/python scrape/collect.py --city $CITY            # 1. collecte 12 mois
./.venv/bin/python scrape/fetch_neighborhoods.py --city $CITY # 2. frontières OSM
./.venv/bin/python scrape/build_quartiers.py --city $CITY     #    (vérifier admin_level)
./.venv/bin/python scrape/geocode_clean.py                    # 3. (re)génère clean.csv (toutes villes)
```
Pour une **nouvelle** ville : ajouter son entrée (bbox/grille) dans `scrape/cities.py`.

## Lancer le dashboard

```bash
./.venv/bin/streamlit run app.py
```

## Déploiement (Streamlit Community Cloud)

Le dashboard ne lit que `data/clean.csv` + `data/*_quartiers.geojson` (légers) ;
les bases SQLite et fichiers bruts sont exclus par `.gitignore`.

1. **Mot de passe** : copie `.streamlit/secrets.toml.example` en
   `.streamlit/secrets.toml` et choisis `app_password` (pour tester en local).
   *Sans* ce secret, le dashboard est en accès libre.
2. **Repo GitHub** : `git init && git add . && git commit -m "dashboard"` puis
   pousse vers un dépôt (privé de préférence).
3. **Streamlit Cloud** : sur https://share.streamlit.io → *New app* → choisis le
   repo, fichier principal `app.py`.
4. **Secret** : dans *Settings > Secrets*, colle `app_password = "..."`.
   L'app demandera ce mot de passe à l'ouverture.

> ⚠️ Données scrapées = ne pas rendre le repo public en l'état (CGU Airbnb /
> RGPD). Repo privé + mot de passe = usage restreint.

## Tests & qualité

```bash
python scrape/test_pipeline.py     # 26 tests unitaires (parsing, DB, géocodage, dates, Overpass mocké…)
python scrape/test_app.py          # 9 tests d'interface du dashboard (AppTest)
python scrape/selftest.py          # contrôles config + GeoJSON + clean.csv + dashboard
python scrape/quality_report.py    # audit qualité des données (anomalies, taux de nuls)
```

## Méthodologie & limites

- **Prix** : séjour figé 3 nuits, 2 voyageurs, mardi→vendredi, ~mi-mois, en MAD.
  Prix/nuit = total ÷ 3. *Prospectif* (mois à venir = saisonnalité), pas un
  historique du passé.
- **Échantillon** : la recherche Airbnb plafonne ~300 annonces/zone ; en zone
  dense on échantillonne (affiner la grille dans `cities.py` pour plus).
- **Prix/personne** : capacité **estimée** (lits, sinon 2×chambres).
- **Quartier** : rattachement GPS par polygone OSM (admin_level 10).
- **Légal** : scraping contraire aux CGU Airbnb. Usage privé/analytique.
```
