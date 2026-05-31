"""Phase 3b — Extraire les quartiers d'une ville à un admin_level donné + nettoyer.

Usage : python scrape/build_quartiers.py --city Marrakech [--level 10]

Entrée : data/{slug}_admin_raw.geojson
Sortie : data/{slug}_quartiers.geojson (propriété `nom`)
"""

import argparse
import json
import re
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

from cities import get as get_city

DATA = Path(__file__).resolve().parent.parent / "data"

# garde la partie latine (français) avant tout caractère arabe/tifinagh
LATIN_ONLY = re.compile(r"[^؀-ۿⴰ-⵿]+")
PREFIX = re.compile(
    r"^(?:Arrondissement|Pachalik|Commune|Caïdat|Cercle)\s+"
    r"(?:de\s+|d['’]\s*|des\s+|du\s+)?", re.IGNORECASE)


def clean_name(tags: dict) -> str:
    name = tags.get("name:fr") or tags.get("name") or ""
    latin = "".join(LATIN_ONLY.findall(name)).strip()
    latin = PREFIX.sub("", latin).strip()
    return latin or name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--level", type=int, default=None)
    args = ap.parse_args()
    cfg = get_city(args.city)
    level = str(args.level or cfg["admin_level"])
    raw = DATA / f"{cfg['slug']}_admin_raw.geojson"
    out = DATA / f"{cfg['slug']}_quartiers.geojson"

    gj = json.loads(raw.read_text())
    feats = []
    for f in gj["features"]:
        tags = f["properties"].get("tags", {})
        if str(tags.get("admin_level")) != level:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"nom": clean_name(tags),
                           "osm_id": f["properties"].get("id")},
            "geometry": f["geometry"],
        })
    json_out = {"type": "FeatureCollection", "features": feats}
    out.write_text(json.dumps(json_out, ensure_ascii=False))
    print(f"{cfg['slug']} : {len(feats)} quartiers (admin_level {level}) -> {out}")
    for f in feats:
        print("  -", f["properties"]["nom"])

    # garde-fou : les polygones couvrent-ils vraiment la ville ?
    if feats:
        union = unary_union([shape(f["geometry"]) for f in feats])
        b = cfg["bbox"]
        bbox_area = (b["ne_lat"] - b["sw_lat"]) * (b["ne_lng"] - b["sw_lng"])
        cover = (union.area / bbox_area * 100) if bbox_area else 0
        if cover < 15:
            print(f"  ⚠️ Couverture {cover:.0f}% de la bbox seulement — admin_level "
                  f"{level} probablement incomplet pour cette ville. Envisager le "
                  f"mode points (supprimer {out.name}).")


if __name__ == "__main__":
    main()
