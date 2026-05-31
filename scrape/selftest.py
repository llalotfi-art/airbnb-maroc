"""Selftest — contrôles qualité du pipeline et du dashboard.

Vérifie : config des villes, schéma de clean.csv, GeoJSON des quartiers, et que
le dashboard s'exécute (vues nationale + ville) sans erreur.

Usage : python scrape/selftest.py    (exit != 0 si un test échoue)
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrape"))
from cities import CITIES, quartiers_path  # noqa: E402

# bornes géographiques du Maroc (large, inclut le Sahara / Dakhla)
MA_LAT = (20.5, 36.2)
MA_LNG = (-17.5, -0.9)

ok = True


def check(label, cond, detail=""):
    global ok
    status = "✅" if cond else "❌"
    if not cond:
        ok = False
    print(f"  {status} {label}" + (f" — {detail}" if detail and not cond else ""))


def test_cities():
    print("\n[cities.py]")
    slugs = set()
    for name, c in CITIES.items():
        b = c["bbox"]
        check(f"{name}: bbox cohérente",
              b["sw_lat"] < b["ne_lat"] and b["sw_lng"] < b["ne_lng"], str(b))
        check(f"{name}: dans le Maroc",
              MA_LAT[0] <= b["sw_lat"] and b["ne_lat"] <= MA_LAT[1]
              and MA_LNG[0] <= b["sw_lng"] and b["ne_lng"] <= MA_LNG[1])
        clat, clng = c["center"]
        check(f"{name}: centre dans la bbox",
              b["sw_lat"] <= clat <= b["ne_lat"] and b["sw_lng"] <= clng <= b["ne_lng"])
        check(f"{name}: slug unique", c["slug"] not in slugs, c["slug"])
        slugs.add(c["slug"])


def test_geojson():
    print("\n[GeoJSON quartiers]")
    found = 0
    for name, c in CITIES.items():
        p = quartiers_path(ROOT, c["slug"])
        if not p.exists():
            continue
        found += 1
        gj = json.loads(p.read_text())
        feats = gj.get("features", [])
        check(f"{name}: features non vides", len(feats) > 0, str(len(feats)))
        if feats:
            check(f"{name}: 'nom' + géométrie présents",
                  all("nom" in f["properties"] and f.get("geometry") for f in feats))
    print(f"  ({found} fichiers quartiers trouvés)")


def test_clean():
    print("\n[clean.csv]")
    p = ROOT / "data" / "clean.csv"
    if not p.exists():
        print("  (absent — collecte pas encore faite, ignoré)")
        return
    df = pd.read_csv(p)
    needed = {"room_id", "month", "city", "price_per_night_mad",
              "price_per_person_mad", "quartier", "property_type",
              "lat", "lng", "is_outlier"}
    check("colonnes attendues présentes", needed <= set(df.columns),
          str(needed - set(df.columns)))
    check("villes ∈ cities.py", set(df["city"].dropna()) <= set(CITIES))
    check("prix/nuit > 0", bool((df["price_per_night_mad"] > 0).all()))
    check("pas de doublon (room_id, mois)",
          not df.duplicated(["room_id", "month"]).any())
    print(f"  ({len(df)} lignes, {df['city'].nunique()} villes, "
          f"{df['month'].nunique()} mois)")


def test_app():
    print("\n[dashboard]")
    if not (ROOT / "data" / "clean.csv").exists():
        print("  (clean.csv absent, ignoré)")
        return
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    check("vue nationale sans erreur", not at.exception, str(at.exception))
    if at.radio:
        at.radio[0].set_value("🏙️ Ville (détail)").run()
        check("vue ville sans erreur", not at.exception, str(at.exception))


def main():
    print("=== SELFTEST — Carte prix Airbnb Maroc ===")
    test_cities()
    test_geojson()
    test_clean()
    test_app()
    print("\n" + ("✅ TOUS LES TESTS PASSENT" if ok else "❌ ÉCHECS DÉTECTÉS"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
