"""Configuration des villes (bounding box, grille, niveau admin OSM, carte).

bbox = (sw_lat, sw_lng, ne_lat, ne_lng) — coin sud-ouest / nord-est.
admin_level = niveau OSM des "quartiers" (à confirmer par fetch_neighborhoods).
center/zoom = centrage de la carte du dashboard.
"""

CITIES = {
    "Casablanca": dict(
        slug="casablanca",
        bbox=dict(sw_lat=33.52, sw_lng=-7.70, ne_lat=33.62, ne_lng=-7.52),
        rows=5, cols=5, admin_level=10,
        center=[33.57, -7.60], zoom=11),
    "Marrakech": dict(
        slug="marrakech",
        bbox=dict(sw_lat=31.58, sw_lng=-8.06, ne_lat=31.69, ne_lng=-7.94),
        rows=5, cols=5, admin_level=10,
        center=[31.63, -8.00], zoom=12),
    "Agadir": dict(
        slug="agadir",
        bbox=dict(sw_lat=30.37, sw_lng=-9.65, ne_lat=30.46, ne_lng=-9.52),
        rows=4, cols=4, admin_level=10,
        center=[30.42, -9.59], zoom=12),
    "Tanger": dict(
        slug="tanger",
        bbox=dict(sw_lat=35.71, sw_lng=-5.87, ne_lat=35.80, ne_lng=-5.73),
        rows=4, cols=4, admin_level=10,
        center=[35.76, -5.80], zoom=12),
    # --- villes prêtes à collecter (centres via Nominatim, bbox calibrées) ---
    # admin_level=10 = hypothèse arrondissements ; les petites villes n'en ont
    # pas -> build_quartiers renverra 0 zone et la carte basculera en points.
    "Rabat": dict(
        slug="rabat",
        bbox=dict(sw_lat=33.9618, sw_lng=-6.9159, ne_lat=34.0818, ne_lng=-6.7659),
        rows=5, cols=5, admin_level=10,
        center=[34.0218, -6.8409], zoom=12),
    "Fès": dict(
        slug="fes",
        bbox=dict(sw_lat=33.9747, sw_lng=-5.0912, ne_lat=34.0947, ne_lng=-4.9412),
        rows=5, cols=5, admin_level=10,
        center=[34.0347, -5.0162], zoom=12),
    # ⚠️ Salé chevauche Rabat (villes jumelles, Bouregreg) : la bbox de Rabat
    # couvre déjà Salé et renvoie les mêmes arrondissements. Collecter Rabat OU
    # Salé, pas les deux (sinon double comptage). Rabat = métro Rabat-Salé.
    "Salé": dict(
        slug="sale",
        bbox=dict(sw_lat=33.9999, sw_lng=-6.8690, ne_lat=34.0899, ne_lng=-6.7590),
        rows=4, cols=4, admin_level=10,
        center=[34.0449, -6.8140], zoom=12),
    "Meknès": dict(
        slug="meknes",
        bbox=dict(sw_lat=33.8534, sw_lng=-5.5872, ne_lat=33.9434, ne_lng=-5.4772),
        rows=4, cols=4, admin_level=10,
        center=[33.8984, -5.5322], zoom=12),
    "Tétouan": dict(
        slug="tetouan",
        bbox=dict(sw_lat=35.5248, sw_lng=-5.4297, ne_lat=35.6148, ne_lng=-5.3197),
        rows=4, cols=4, admin_level=10,
        center=[35.5698, -5.3747], zoom=12),
    "Oujda": dict(
        slug="oujda",
        bbox=dict(sw_lat=34.6329, sw_lng=-1.9843, ne_lat=34.7229, ne_lng=-1.8743),
        rows=4, cols=4, admin_level=10,
        center=[34.6779, -1.9293], zoom=12),
    "Kénitra": dict(
        slug="kenitra",
        bbox=dict(sw_lat=34.2196, sw_lng=-6.6252, ne_lat=34.3096, ne_lng=-6.5152),
        rows=4, cols=4, admin_level=10,
        center=[34.2646, -6.5702], zoom=12),
    "Mohammedia": dict(
        slug="mohammedia",
        bbox=dict(sw_lat=33.6508, sw_lng=-7.4443, ne_lat=33.7408, ne_lng=-7.3343),
        rows=4, cols=4, admin_level=10,
        center=[33.6958, -7.3893], zoom=12),
    "El Jadida": dict(
        slug="el-jadida",
        bbox=dict(sw_lat=33.1843, sw_lng=-8.5544, ne_lat=33.2743, ne_lng=-8.4444),
        rows=4, cols=4, admin_level=10,
        center=[33.2293, -8.4994], zoom=12),
    "Nador": dict(
        slug="nador",
        bbox=dict(sw_lat=35.1290, sw_lng=-2.9831, ne_lat=35.2190, ne_lng=-2.8731),
        rows=4, cols=4, admin_level=10,
        center=[35.1740, -2.9281], zoom=12),
    "Essaouira": dict(
        slug="essaouira",
        bbox=dict(sw_lat=31.4868, sw_lng=-9.7941, ne_lat=31.5368, ne_lng=-9.7301),
        rows=3, cols=3, admin_level=10,
        center=[31.5118, -9.7621], zoom=13),
    "Chefchaouen": dict(
        slug="chefchaouen",
        bbox=dict(sw_lat=35.1438, sw_lng=-5.3003, ne_lat=35.1938, ne_lng=-5.2363),
        rows=3, cols=3, admin_level=10,
        center=[35.1688, -5.2683], zoom=13),
    "Ouarzazate": dict(
        slug="ouarzazate",
        bbox=dict(sw_lat=30.8952, sw_lng=-6.9429, ne_lat=30.9452, ne_lng=-6.8789),
        rows=3, cols=3, admin_level=10,
        center=[30.9202, -6.9109], zoom=13),
    "Ifrane": dict(
        slug="ifrane",
        bbox=dict(sw_lat=33.5026, sw_lng=-5.1394, ne_lat=33.5526, ne_lng=-5.0754),
        rows=3, cols=3, admin_level=10,
        center=[33.5276, -5.1074], zoom=13),
    "Dakhla": dict(
        slug="dakhla",
        bbox=dict(sw_lat=23.6691, sw_lng=-15.9751, ne_lat=23.7191, ne_lng=-15.9111),
        rows=3, cols=3, admin_level=10,
        center=[23.6941, -15.9431], zoom=13),
    "Asilah": dict(
        slug="asilah",
        bbox=dict(sw_lat=35.4369, sw_lng=-6.0685, ne_lat=35.4869, ne_lng=-6.0045),
        rows=3, cols=3, admin_level=10,
        center=[35.4619, -6.0365], zoom=13),
}


def get(name: str) -> dict:
    if name not in CITIES:
        raise SystemExit(f"Ville inconnue : {name}. Choix : {list(CITIES)}")
    return CITIES[name]


def db_path(root, slug: str):
    return root / "data" / f"airbnb_{slug}.db"


def quartiers_path(root, slug: str):
    return root / "data" / f"{slug}_quartiers.geojson"
