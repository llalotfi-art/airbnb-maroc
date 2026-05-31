"""Audit qualité des données — profile data/clean.csv et signale les anomalies.

Usage : python scrape/quality_report.py
"""

import sys
from pathlib import Path

import pandas as pd

from cities import CITIES, quartiers_path

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean.csv"

warnings = []


def warn(msg):
    warnings.append(msg)
    print(f"  ⚠️  {msg}")


def main():
    if not CLEAN.exists():
        sys.exit("clean.csv absent.")
    df = pd.read_csv(CLEAN)
    print(f"=== AUDIT QUALITÉ — {len(df):,} lignes, {df['city'].nunique()} villes ===\n")

    # 1) Par ville
    print("[1] Profil par ville")
    print(f"{'Ville':12s} {'annonces':>8} {'obs':>7} {'mois':>5} "
          f"{'%géocod':>8} {'%note':>6} {'médiane':>8} {'min':>6} {'max':>7} {'%aberr':>7}")
    for city, g in df.groupby("city"):
        n_list = g["room_id"].nunique()
        geocoded = g["quartier"].notna().mean() * 100
        rated = g["rating"].notna().mean() * 100
        med = g["price_per_night_mad"].median()
        lo, hi = g["price_per_night_mad"].min(), g["price_per_night_mad"].max()
        out = g["is_outlier"].mean() * 100
        nmonths = g["month"].nunique()
        # ville en "mode points" si pas de polygones de quartiers
        slug = CITIES.get(city, {}).get("slug", "")
        has_q = bool(slug) and quartiers_path(ROOT, slug).exists()
        tag = "" if has_q else "  (mode points)"
        print(f"{city:12s} {n_list:>8} {len(g):>7} {nmonths:>5} {geocoded:>7.0f}% "
              f"{rated:>5.0f}% {med:>8.0f} {lo:>6.0f} {hi:>7.0f} {out:>6.1f}%{tag}")
        if nmonths < 12:
            warn(f"{city}: seulement {nmonths}/12 mois")
        if has_q and geocoded < 85:
            warn(f"{city}: {geocoded:.0f}% géocodés seulement (annonces hors arrondissements)")

    # 2) Intégrité
    print("\n[2] Intégrité")
    dup = int(df.duplicated(["room_id", "month"]).sum())
    print(f"  doublons (room_id, mois) : {dup}")
    if dup:
        warn(f"{dup} doublons (room_id, mois)")
    # room_id présents dans >1 ville (chevauchement de bbox)
    cross = (df.groupby("room_id")["city"].nunique() > 1).sum()
    print(f"  room_id dans >1 ville     : {int(cross)}")
    if cross:
        warn(f"{int(cross)} annonces apparaissent dans 2 villes (bbox qui se chevauchent)")

    # 3) Cohérence des prix
    print("\n[3] Cohérence des prix")
    diff = (df["price_total_mad"] - df["price_per_night_mad"] * df["nights"]).abs()
    incoh = int((diff > 1).sum())
    print(f"  total ≈ prix/nuit × nuits : {len(df)-incoh}/{len(df)} cohérents")
    if incoh:
        warn(f"{incoh} lignes incohérentes total vs prix/nuit")
    low = int((df["price_per_night_mad"] < 100).sum())
    high = int((df["price_per_night_mad"] > 15000).sum())
    print(f"  prix/nuit < 100 MAD : {low}  |  > 15 000 MAD : {high}")
    if low:
        warn(f"{low} prix < 100 MAD/nuit (suspects)")

    # 4) Complétude (taux de nuls)
    print("\n[4] Taux de valeurs manquantes")
    for c in ["quartier", "property_type", "rating", "beds", "bedrooms",
              "lat", "lng", "price_per_night_mad", "capacity_est"]:
        if c in df:
            na = df[c].isna().mean() * 100
            print(f"  {c:20s}: {na:5.1f}%")
            if c in ("lat", "lng", "price_per_night_mad") and na > 0:
                warn(f"{c} a {na:.1f}% de manquants (devrait être 0)")

    print("\n" + ("✅ AUCUNE ANOMALIE BLOQUANTE"
                  if not warnings else f"⚠️ {len(warnings)} POINT(S) D'ATTENTION"))


if __name__ == "__main__":
    main()
