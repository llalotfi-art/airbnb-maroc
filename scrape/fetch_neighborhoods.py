"""Phase 3a — Récupérer les frontières administratives d'une ville (OSM/Overpass).

Usage : python scrape/fetch_neighborhoods.py --city Marrakech

Sortie : data/{slug}_admin_raw.geojson + affichage des niveaux/noms pour repérer
celui des quartiers (à renseigner dans cities.py / passer à build_quartiers).
"""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import requests
import osm2geojson

from cities import get as get_city

DATA = Path(__file__).resolve().parent.parent / "data"

# Plusieurs miroirs Overpass (l'un tombe souvent en timeout) + headers
# (sans User-Agent, overpass-api.de renvoie 406).
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {
    "User-Agent": "airbnb-maroc-map/1.0 (projet privé)",
    "Accept": "application/json",
}


def fetch_overpass(q, attempts=2):
    """Essaie chaque miroir, avec quelques tentatives et backoff."""
    last = None
    for url in ENDPOINTS:
        for k in range(attempts):
            try:
                print(f"Overpass -> {url} (essai {k+1})")
                r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=180)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last = e
                print(f"  échec : {e!r}")
                time.sleep(3 * (k + 1))
    raise SystemExit(f"Overpass injoignable sur tous les miroirs. Dernier : {last!r}")


def query(bbox):
    s, w, n, e = bbox["sw_lat"], bbox["sw_lng"], bbox["ne_lat"], bbox["ne_lng"]
    return f"""
[out:json][timeout:120];
(
  relation["boundary"="administrative"]["admin_level"~"^(8|9|10|11)$"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    args = ap.parse_args()
    cfg = get_city(args.city)
    out = DATA / f"{cfg['slug']}_admin_raw.geojson"

    data = fetch_overpass(query(cfg["bbox"]))
    gj = osm2geojson.json2geojson(data)
    feats = [f for f in gj["features"]
             if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
    gj["features"] = feats
    out.write_text(json.dumps(gj, ensure_ascii=False))
    print(f"\n{len(feats)} zones polygonales -> {out}")

    levels = Counter(str(f["properties"].get("tags", {}).get("admin_level")) for f in feats)
    print("\n=== Noms par admin_level ===")
    for lvl in sorted(levels):
        names = [f["properties"].get("tags", {}).get("name")
                 for f in feats
                 if str(f["properties"].get("tags", {}).get("admin_level")) == lvl]
        print(f"\n[admin_level {lvl}] ({len(names)}):")
        for nm in names:
            print("   -", nm)


if __name__ == "__main__":
    main()
