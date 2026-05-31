# Méthodologie

## Objectif
Cartographier les prix Airbnb dans les principales villes du Maroc et leur
évolution mensuelle (saisonnalité), par quartier quand le découpage existe.

## Source & collecte
- **Source** : annonces publiques d'Airbnb, via la librairie `pyairbnb`
  (endpoint interne `StaysSearch`). Pas d'API officielle.
- **Découverte + prix en une étape** : pour chaque mois cible, on relance une
  recherche sur une **grille de bounding boxes** couvrant la ville. La recherche
  renvoie les annonces *et* leur prix pour les dates demandées. Déduplication
  par `room_id`.
- **Le calendrier d'Airbnb n'expose pas les prix** (disponibilité seulement) :
  d'où le passage par la recherche datée.

## Paramètres figés (comparabilité)
| Paramètre | Valeur |
|---|---|
| Devise | MAD |
| Voyageurs | 2 adultes |
| Durée du séjour | 3 nuits |
| Créneau | mardi → vendredi, ~mi-mois |
| Horizon | 12 mois à venir |

**Prix/nuit** = total du séjour ÷ 3.
**Prix/personne** = prix/nuit ÷ capacité estimée.
La **capacité** est estimée (lits, sinon 2 × chambres, sinon 2) — proxy, à
interpréter avec prudence.

## Découpage géographique
- Grille de tuiles par ville (`scrape/cities.py`). La recherche Airbnb
  **plafonne à ~300 annonces/zone** : en zone dense, on obtient donc un
  **échantillon** (affiner `rows`/`cols` pour plus de couverture).
- **Quartiers** : polygones OpenStreetMap `admin_level=10` (arrondissements),
  rattachement par *point-dans-polygone*. La géolocalisation Airbnb est floutée
  (~150 m), ce qui reste suffisant au niveau arrondissement.
- Villes **sans arrondissements** (petites villes touristiques) : pas de
  polygones → la carte bascule en **points colorés par prix**.

## Saisonnalité : prospective, pas historique
On capture la courbe des **12 mois à venir** (prix affichés aujourd'hui pour des
séjours futurs) → révèle la saisonnalité. Ce **n'est pas** un historique des
prix passés (non récupérable a posteriori ; nécessiterait des captures
récurrentes dans le temps).

## Nettoyage
- Note à 0 sans avis → considérée manquante.
- **Valeurs aberrantes** : flag par (ville, mois) via IQR (> Q3 + 3·(Q3−Q1)).
  Masquables dans le dashboard ; non supprimées.

## Limites
- **Échantillon** (plafond de recherche) — pas l'exhaustivité du marché.
- **Capacité estimée** → prix/personne indicatif.
- **Prospectif** — sensible aux dates choisies et à la disponibilité du moment.
- **Composition variable** : les annonces disponibles changent selon le mois.
- **Légal** : le scraping est contraire aux CGU d'Airbnb. Usage **privé /
  analytique**. Ne pas rediffuser les données d'hôtes en l'état (RGPD).

## Reproductibilité
```bash
python scrape/collect.py --city <Ville>           # collecte 12 mois
python scrape/fetch_neighborhoods.py --city <Ville>
python scrape/build_quartiers.py --city <Ville>
python scrape/geocode_clean.py                    # -> data/clean.csv
python scrape/selftest.py                         # contrôles qualité
streamlit run app.py
```
