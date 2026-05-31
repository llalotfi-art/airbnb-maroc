"""Phase 3c — Géocodage (GPS -> quartier) + nettoyage, multi-villes.

Parcourt chaque ville de cities.py qui possède une base data/airbnb_{slug}.db,
rattache ses annonces à ses quartiers, nettoie, et concatène tout dans
data/clean.csv (avec une colonne `city`).

Usage : python scrape/geocode_clean.py
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
from shapely.geometry import shape, Point

from cities import CITIES, db_path, quartiers_path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "clean.csv"


def load_quartiers(path):
    if not path.exists():
        return []
    gj = json.loads(path.read_text())
    return [(f["properties"]["nom"], shape(f["geometry"])) for f in gj["features"]]


def assign_quartier(lat, lng, quartiers):
    if lat is None or lng is None or pd.isna(lat) or pd.isna(lng):
        return None
    pt = Point(lng, lat)
    for nom, geom in quartiers:
        if geom.contains(pt):
            return nom
    return None


def estimate_capacity(beds, bedrooms):
    """Capacité estimée : lits, sinon 2×chambres, sinon 2 (min 1)."""
    cap = beds.fillna(0)
    cap = cap.where(cap > 0, bedrooms.fillna(0) * 2)
    cap = cap.where(cap > 0, 2)
    return cap.clip(lower=1)


def flag_outliers(df):
    """Marque is_outlier par (ville, mois) via IQR (> Q3 + 3·IQR)."""
    df = df.copy()
    df["is_outlier"] = False
    for _, grp in df.groupby(["city", "month"]):
        q1, q3 = grp["price_per_night_mad"].quantile([.25, .75])
        hi = q3 + 3 * (q3 - q1)
        df.loc[grp.index[grp["price_per_night_mad"] > hi], "is_outlier"] = True
    return df


def process_city(name, cfg):
    dbp = db_path(ROOT, cfg["slug"])
    if not dbp.exists():
        return None
    conn = sqlite3.connect(dbp)
    listings = pd.read_sql("SELECT * FROM listings", conn)
    prices = pd.read_sql("SELECT * FROM prices", conn)
    conn.close()
    if listings.empty:
        return None

    # Qualité minimale : note > 4 et au moins 15 avis
    before = len(listings)
    listings = listings[(listings["rating"] > 4) & (listings["review_count"] > 15)]
    print(f"  filtre qualité : {before} → {len(listings)} annonces "
          f"(rating>4 & reviews>15)")
    if listings.empty:
        return None

    quartiers = load_quartiers(quartiers_path(ROOT, cfg["slug"]))
    listings["quartier"] = [assign_quartier(la, lo, quartiers)
                            for la, lo in zip(listings["lat"], listings["lng"])]
    hors = listings["quartier"].isna().sum()
    print(f"{name:12s}: {len(listings):5d} annonces | rattachées "
          f"{len(listings)-hors:5d} | hors zone {hors:4d} | quartiers {len(quartiers)}")

    # nettoyage
    listings.loc[(listings["rating"] == 0) & (listings["review_count"].fillna(0) == 0),
                 "rating"] = pd.NA
    listings["capacity_est"] = estimate_capacity(listings["beds"], listings["bedrooms"])
    listings["guest_favorite"] = listings["badges"].fillna("[]").str.contains("GUEST_FAVORITE")

    df = prices.merge(
        listings[["room_id", "name", "quartier", "property_type", "lat", "lng",
                  "bedrooms", "beds", "baths", "rating", "review_count",
                  "capacity_est", "guest_favorite"]],
        on="room_id", how="left")
    df["city"] = name
    df["price_per_person_mad"] = (df["price_per_night_mad"] / df["capacity_est"]).round(2)
    return df


def main():
    frames = []
    for name, cfg in CITIES.items():
        d = process_city(name, cfg)
        if d is not None:
            frames.append(d)
    if not frames:
        raise SystemExit("Aucune base trouvée. Lance d'abord collect.py.")
    df = pd.concat(frames, ignore_index=True)
    df = flag_outliers(df)
    df.to_csv(OUT, index=False)
    print(f"\n-> {OUT} ({len(df)} lignes, {df['city'].nunique()} villes)")
    print("\nPrix/nuit médian par ville (hors outliers) :")
    print(df[~df.is_outlier].groupby("city")["price_per_night_mad"].median().round(0))


if __name__ == "__main__":
    main()
