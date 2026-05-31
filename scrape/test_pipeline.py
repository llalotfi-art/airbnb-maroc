"""Tests unitaires des fonctions pures du pipeline (sans réseau réel).

Usage : python scrape/test_pipeline.py     (exit != 0 si un test échoue)
"""

import datetime as dt
import sqlite3
import sys
import traceback
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from shapely.geometry import box, MultiPolygon  # noqa: E402

import collect  # noqa: E402
import cities  # noqa: E402
import fetch_neighborhoods as fn  # noqa: E402
from geocode_clean import (assign_quartier, estimate_capacity,  # noqa: E402
                           flag_outliers)
from build_quartiers import clean_name  # noqa: E402
from geocode_cities import slugify  # noqa: E402

PASS = FAIL = 0


def run(fn_):
    global PASS, FAIL
    try:
        fn_()
        print(f"  ✅ {fn_.__name__}")
        PASS += 1
    except Exception:
        print(f"  ❌ {fn_.__name__}")
        traceback.print_exc()
        FAIL += 1


# ========================================================= collect : num()
def test_num():
    assert collect.num(None) is None
    assert collect.num("4.9") == 4.9
    assert collect.num(255) == 255.0          # int en entrée
    assert collect.num("1,234") == 1234.0
    assert collect.num("3 beds") == 3.0
    assert collect.num("MAD746.66") == 746.66
    assert collect.num("studio") is None


# ============================================= collect : target_months()
def test_target_months_basic():
    ms = collect.target_months(12, dt.date(2026, 5, 30))
    assert len(ms) == 12
    assert ms[0][0] == "2026-06" and ms[-1][0] == "2027-05"
    labels = [m[0] for m in ms]
    assert labels == sorted(labels) and len(set(labels)) == 12
    for _, ci, co in ms:
        assert ci.weekday() == 1 and (co - ci).days == 3 and ci.day >= 15


def test_target_months_year_wrap():
    ms = collect.target_months(3, dt.date(2026, 12, 10))
    assert [m[0] for m in ms] == ["2027-01", "2027-02", "2027-03"]


def test_target_months_one_and_long():
    assert len(collect.target_months(1, dt.date(2026, 1, 1))) == 1
    ms = collect.target_months(24, dt.date(2026, 5, 1))
    assert len(ms) == 24 and len({m[0] for m in ms}) == 24


# =================================================== collect : make_grid()
def test_make_grid():
    bbox = dict(sw_lat=0.0, sw_lng=0.0, ne_lat=10.0, ne_lng=10.0)
    tiles = collect.make_grid(bbox, 2, 5)
    assert len(tiles) == 10
    assert sorted(t["idx"] for t in tiles) == list(range(10))
    for t in tiles:
        assert t["sw_lat"] < t["ne_lat"] and t["sw_lng"] < t["ne_lng"]
    assert min(t["sw_lat"] for t in tiles) == 0.0
    assert max(t["ne_lng"] for t in tiles) == 10.0


def test_make_grid_1x1():
    bbox = dict(sw_lat=1.0, sw_lng=2.0, ne_lat=3.0, ne_lng=4.0)
    t = collect.make_grid(bbox, 1, 1)
    assert len(t) == 1
    assert (t[0]["sw_lat"], t[0]["sw_lng"], t[0]["ne_lat"], t[0]["ne_lng"]) == (1.0, 2.0, 3.0, 4.0)


# =============================================== collect : parse_listing()
def _listing(**over):
    base = dict(
        room_id=123, name="Joli appart", title="Apartment in Gauthier",
        coordinates={"latitude": 33.59, "longitud": -7.63},
        structuredContent={"mapPrimaryLine": [
            {"body": "2 bedrooms"}, {"body": "3 beds"}, {"body": "1 bath"}]},
        price={"unit": {"amount": 2400.0, "qualifier": "total"},
               "break_down": [{"description": "3 nights x MAD800"}]},
        rating={"value": 4.8, "reviewCount": "120"},
        badges=["GUEST_FAVORITE"])
    base.update(over)
    return base


def test_parse_listing_full():
    r = collect.parse_listing(_listing())
    assert r["room_id"] == "123"
    assert r["lat"] == 33.59 and r["lng"] == -7.63
    assert r["property_type"] == "Apartment" and r["neighborhood_title"] == "Gauthier"
    assert r["bedrooms"] == 2.0 and r["beds"] == 3.0 and r["baths"] == 1.0
    assert r["price_total"] == 2400.0 and r["price_per_night"] == 800.0
    assert r["rating"] == 4.8 and r["review_count"] == 120.0
    assert "GUEST_FAVORITE" in r["badges"]


def test_parse_listing_breakdown_fallback():
    r = collect.parse_listing(_listing(price={
        "unit": {}, "break_down": [{"description": "3 nights x MAD500"}]}))
    assert r["price_total"] == 1500.0 and r["price_per_night"] == 500.0


def test_parse_listing_longitude_correct_spelling():
    r = collect.parse_listing(_listing(coordinates={"latitude": 33.5, "longitude": -7.6}))
    assert r["lng"] == -7.6


def test_parse_listing_villa():
    r = collect.parse_listing(_listing(title="Villa in Palmeraie"))
    assert r["property_type"] == "Villa" and r["neighborhood_title"] == "Palmeraie"


def test_parse_listing_no_title_match():
    r = collect.parse_listing(_listing(title="Room"))
    assert r["property_type"] is None and r["neighborhood_title"] is None


def test_parse_listing_studio_no_bedrooms():
    r = collect.parse_listing(_listing(structuredContent={
        "mapPrimaryLine": [{"body": "Studio"}, {"body": "1 bed"}, {"body": "1 bath"}]}))
    assert r["bedrooms"] is None and r["beds"] == 1.0 and r["baths"] == 1.0


def test_parse_listing_no_price():
    r = collect.parse_listing(_listing(price={}))
    assert r["price_total"] is None and r["price_per_night"] is None


def test_parse_listing_robuste_si_vide():
    r = collect.parse_listing({"room_id": 1})
    assert r["room_id"] == "1" and r["lat"] is None and r["price_per_night"] is None


# ================================================= collect : couche SQLite
def test_db_upsert_and_resume():
    conn = sqlite3.connect(":memory:")
    collect.init_db(conn)
    rec = collect.parse_listing(_listing())

    collect.upsert_listing(conn, rec, "t1")
    collect.upsert_listing(conn, {**rec, "name": "Renommé"}, "t2")  # conflit -> update
    rows = conn.execute("SELECT COUNT(*), MAX(name), MAX(last_seen) FROM listings").fetchone()
    assert rows[0] == 1 and rows[1] == "Renommé" and rows[2] == "t2"

    collect.upsert_price(conn, rec["room_id"], "2026-06", "a", "b", rec, "t1")
    collect.upsert_price(conn, rec["room_id"], "2026-06",
                         "a", "b", {**rec, "price_per_night": None}, "t1")  # ignoré
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 1

    assert not collect.already_done(conn, "2026-06", 0)
    conn.execute("INSERT INTO scrape_log VALUES ('2026-06',0,5,'ok','t1')")
    assert collect.already_done(conn, "2026-06", 0)
    assert not collect.already_done(conn, "2026-07", 0)


# ============================================ geocode_clean : helpers purs
def test_estimate_capacity():
    beds = pd.Series([4, None, 0, None])
    bedrooms = pd.Series([None, 2, None, None])
    cap = estimate_capacity(beds, bedrooms)
    assert list(cap) == [4.0, 4.0, 2.0, 2.0]   # lits / 2×chambres / défaut


def test_flag_outliers():
    df = pd.DataFrame({
        "city": ["X"] * 6,
        "month": ["2026-06"] * 6,
        "price_per_night_mad": [100, 110, 120, 130, 140, 100000],
    })
    out = flag_outliers(df)
    assert out["is_outlier"].tolist() == [False] * 5 + [True]


def test_assign_quartier():
    poly = box(-7.65, 33.55, -7.60, 33.60)
    qs = [("Zone", poly)]
    assert assign_quartier(33.57, -7.62, qs) == "Zone"
    assert assign_quartier(34.0, -7.62, qs) is None
    assert assign_quartier(None, None, qs) is None
    assert assign_quartier(33.57, -7.62, []) is None


def test_assign_quartier_multipolygon_and_order():
    a = box(0, 0, 1, 1)
    b = box(10, 10, 11, 11)
    qs = [("A", a), ("B", MultiPolygon([b]))]
    assert assign_quartier(10.5, 10.5, qs) == "B"   # 2e quartier, multipolygone
    assert assign_quartier(0.5, 0.5, qs) == "A"


# =================================================== build_quartiers : noms
def test_clean_name():
    assert clean_name({"name": "Arrondissement d'Anfa مقاطعة أنفا"}) == "Anfa"
    assert clean_name({"name": "arrondissement de Bni Makada بني مكادة"}) == "Bni Makada"
    assert clean_name({"name": "Arrondissement Maârif ⵜⴰⴳⵣⵣⵓⵎⵜ مقاطعة"}) == "Maârif"
    assert clean_name({"name:fr": "Guéliz", "name": "X مقاطعة"}) == "Guéliz"
    assert clean_name({"name": "Marrakech-Medina"}) == "Marrakech-Medina"
    assert clean_name({"name": "Pachalik de Souissi"}) == "Souissi"
    assert clean_name({"name": "Arrondissement de Ben M'Sick"}) == "Ben M'Sick"


# ========================================================= cities : config
def test_cities_get_and_paths():
    c = cities.get("Casablanca")
    assert c["slug"] == "casablanca"
    raised = False
    try:
        cities.get("Atlantis")
    except SystemExit:
        raised = True
    assert raised
    root = Path("/tmp/x")
    assert cities.db_path(root, "casablanca").name == "airbnb_casablanca.db"
    assert cities.quartiers_path(root, "fes").name == "fes_quartiers.geojson"


def test_cities_all_valid():
    slugs = set()
    for name, c in cities.CITIES.items():
        b = c["bbox"]
        assert b["sw_lat"] < b["ne_lat"] and b["sw_lng"] < b["ne_lng"], name
        assert c["slug"] not in slugs, c["slug"]
        slugs.add(c["slug"])
    assert len(cities.CITIES) >= 20


# ================================================ geocode_cities : slugify
def test_slugify():
    assert slugify("El Jadida") == "el-jadida"
    assert slugify("Fès") == "fes"
    assert slugify("Salé") == "sale"
    assert slugify("M'diq") == "mdiq"


# ============================================== fetch_neighborhoods : robust
def test_overpass_query():
    q = fn.query(dict(sw_lat=33.5, sw_lng=-7.7, ne_lat=33.6, ne_lng=-7.5))
    assert "33.5,-7.7,33.6,-7.5" in q
    assert "boundary" in q and "admin_level" in q and "out body" in q
    assert len(fn.ENDPOINTS) >= 2 and "User-Agent" in fn.HEADERS


def test_fetch_overpass_fallback():
    ok = mock.Mock()
    ok.raise_for_status = lambda: None
    ok.json = lambda: {"elements": [1]}
    with mock.patch.object(fn.time, "sleep", lambda *a: None), \
         mock.patch.object(fn.requests, "post",
                           side_effect=[Exception("miroir 1 KO"), ok]) as mp:
        assert fn.fetch_overpass("q") == {"elements": [1]}
        assert mp.call_count == 2  # a basculé sur le 2e essai/miroir


def test_fetch_overpass_all_fail():
    raised = False
    with mock.patch.object(fn.time, "sleep", lambda *a: None), \
         mock.patch.object(fn.requests, "post", side_effect=Exception("KO")):
        try:
            fn.fetch_overpass("q")
        except SystemExit:
            raised = True
    assert raised


def main():
    print("=== TESTS UNITAIRES — pipeline ===")
    tests = [
        test_num, test_target_months_basic, test_target_months_year_wrap,
        test_target_months_one_and_long, test_make_grid, test_make_grid_1x1,
        test_parse_listing_full, test_parse_listing_breakdown_fallback,
        test_parse_listing_longitude_correct_spelling, test_parse_listing_villa,
        test_parse_listing_no_title_match, test_parse_listing_studio_no_bedrooms,
        test_parse_listing_no_price, test_parse_listing_robuste_si_vide,
        test_db_upsert_and_resume, test_estimate_capacity, test_flag_outliers,
        test_assign_quartier, test_assign_quartier_multipolygon_and_order,
        test_clean_name, test_cities_get_and_paths, test_cities_all_valid,
        test_slugify, test_overpass_query, test_fetch_overpass_fallback,
        test_fetch_overpass_all_fail,
    ]
    for t in tests:
        run(t)
    print(f"\n{PASS} réussis, {FAIL} échoués")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
