"""Outil ponctuel — géocode une liste de villes (Nominatim) et génère les
entrées prêtes à coller dans cities.py (bbox urbaine = centre ± fenêtre/taille).

Usage : python scrape/geocode_cities.py
"""

import time
import unicodedata

import requests

# (nom, tier) — tier pilote la taille de la fenêtre urbaine + la grille
TIERS = {
    # tier      half_lat half_lng rows cols zoom
    "grande":  (0.060, 0.075, 5, 5, 12),
    "moyenne": (0.045, 0.055, 4, 4, 12),
    "petite":  (0.025, 0.032, 3, 3, 13),
}

CITIES = [
    ("Rabat", "grande"), ("Fès", "grande"), ("Salé", "moyenne"),
    ("Meknès", "moyenne"), ("Tétouan", "moyenne"), ("Oujda", "moyenne"),
    ("Kénitra", "moyenne"), ("Mohammedia", "moyenne"), ("El Jadida", "moyenne"),
    ("Nador", "moyenne"), ("Essaouira", "petite"), ("Chefchaouen", "petite"),
    ("Ouarzazate", "petite"), ("Ifrane", "petite"), ("Dakhla", "petite"),
    ("Asilah", "petite"),
]

HEADERS = {"User-Agent": "airbnb-maroc-map/1.0 (projet privé)"}


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "-").replace("'", "")


def geocode(name):
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": f"{name}, Maroc", "format": "json", "limit": 1},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def main():
    print("    # --- villes ajoutées (centres via Nominatim) ---")
    for name, tier in CITIES:
        try:
            res = geocode(name)
        except Exception as e:
            print(f"    # {name}: ERREUR {e!r}")
            continue
        if not res:
            print(f"    # {name}: introuvable")
            continue
        lat, lng = res
        hlat, hlng, rows, cols, zoom = TIERS[tier]
        slug = slugify(name)
        print(f'    "{name}": dict(')
        print(f'        slug="{slug}",')
        print(f'        bbox=dict(sw_lat={lat-hlat:.4f}, sw_lng={lng-hlng:.4f}, '
              f'ne_lat={lat+hlat:.4f}, ne_lng={lng+hlng:.4f}),')
        print(f'        rows={rows}, cols={cols}, admin_level=10,  # {tier} — à confirmer')
        print(f'        center=[{lat:.4f}, {lng:.4f}], zoom={zoom}),')
        time.sleep(1.1)  # politesse Nominatim


if __name__ == "__main__":
    main()
