"""Phases 1+2 — Collecte des annonces et prix mensuels (Casablanca).

Mécanique : pour chaque mois cible, on balaie une grille de bounding boxes
couvrant Casablanca avec `pyairbnb.search_all`. Chaque recherche renvoie à la
fois la découverte des annonces ET leur prix/nuit pour le séjour du mois.

Robustesse : écriture incrémentale en SQLite + table `scrape_log` pour la
reprise (on saute les (mois, tuile) déjà traités). Rate-limiting poli.

Usage :
    python scrape/collect.py                 # run complet (12 mois, grille 5x5)
    python scrape/collect.py --rows 2 --cols 2 --months 1   # smoke test
    python scrape/collect.py --reset         # repart de zéro (vide la base)
"""

import argparse
import datetime as dt
import json
import re
import sqlite3
import time
from pathlib import Path

import pyairbnb
from cities import get as get_city, db_path  # cities.py est dans le même dossier

# ------------------------------------------------------------------ config ---
ROOT = Path(__file__).resolve().parent.parent

CURRENCY, LANGUAGE, ADULTS, NIGHTS = "MAD", "en", 2, 3
ZOOM = 15
SLEEP_BETWEEN_TILES = 1.5  # secondes, rate-limiting poli

TITLE_RE = re.compile(r"^(.*?)\s+in\s+(.*)$", re.IGNORECASE)
NUM_RE = re.compile(r"([\d.,]+)")


# ----------------------------------------------------------------- helpers ---
def target_months(n: int, start: dt.date | None = None):
    """n mois à venir ; pour chaque, un séjour de 3 nuits le mardi >= 15."""
    start = start or dt.date.today()
    out = []
    y, m = start.year, start.month
    # commencer au mois suivant le mois courant
    m += 1
    if m > 12:
        m, y = 1, y + 1
    for _ in range(n):
        d = dt.date(y, m, 15)
        while d.weekday() != 1:  # 1 = mardi
            d += dt.timedelta(days=1)
        out.append((f"{y:04d}-{m:02d}", d, d + dt.timedelta(days=NIGHTS)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def make_grid(bbox: dict, rows: int, cols: int):
    """Découpe une bbox en rows x cols tuiles (bounding boxes)."""
    lat0, lat1 = bbox["sw_lat"], bbox["ne_lat"]
    lng0, lng1 = bbox["sw_lng"], bbox["ne_lng"]
    dlat = (lat1 - lat0) / rows
    dlng = (lng1 - lng0) / cols
    tiles = []
    for i in range(rows):
        for j in range(cols):
            tiles.append(dict(
                idx=i * cols + j,
                sw_lat=lat0 + i * dlat, ne_lat=lat0 + (i + 1) * dlat,
                sw_lng=lng0 + j * dlng, ne_lng=lng0 + (j + 1) * dlng,
            ))
    return tiles


def num(s):
    if s is None:
        return None
    m = NUM_RE.search(str(s))
    return float(m.group(1).replace(",", "")) if m else None


def parse_listing(l: dict):
    """Extrait les champs utiles d'une annonce de recherche."""
    coords = l.get("coordinates") or {}
    lat = coords.get("latitude")
    lng = coords.get("longitud", coords.get("longitude"))  # typo 'longitud' côté lib

    title = l.get("title") or ""
    mt = TITLE_RE.match(title)
    ptype = mt.group(1).strip() if mt else None
    neigh = mt.group(2).strip() if mt else None

    # capacité depuis structuredContent.mapPrimaryLine
    beds = bedrooms = baths = None
    for seg in (l.get("structuredContent") or {}).get("mapPrimaryLine", []) or []:
        body = (seg.get("body") or "").lower()
        if "bedroom" in body:
            bedrooms = num(body)
        elif "bed" in body:
            beds = num(body)
        elif "bath" in body:
            baths = num(body)

    price = l.get("price") or {}
    total = price.get("unit", {}).get("amount")
    total = total if isinstance(total, (int, float)) and total > 0 else None
    if total is None:
        for bd in price.get("break_down", []):
            m = re.search(r"x\s*MAD([\d.,]+)", bd.get("description", ""))
            if m:
                total = float(m.group(1).replace(",", "")) * NIGHTS
                break
    per_night = round(total / NIGHTS, 2) if total else None

    rating = l.get("rating") or {}
    return dict(
        room_id=str(l.get("room_id")),
        name=l.get("name"),
        title=title,
        property_type=ptype,
        neighborhood_title=neigh,
        lat=lat, lng=lng,
        bedrooms=bedrooms, beds=beds, baths=baths,
        rating=rating.get("value"),
        review_count=num(rating.get("reviewCount")),
        badges=json.dumps(l.get("badges") or [], ensure_ascii=False),
        price_total=total, price_per_night=per_night,
    )


# ---------------------------------------------------------------------- db ---
def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS listings (
        room_id TEXT PRIMARY KEY,
        name TEXT, title TEXT, property_type TEXT, neighborhood_title TEXT,
        lat REAL, lng REAL, bedrooms REAL, beds REAL, baths REAL,
        rating REAL, review_count REAL, badges TEXT,
        first_seen TEXT, last_seen TEXT
    );
    CREATE TABLE IF NOT EXISTS prices (
        room_id TEXT, month TEXT, check_in TEXT, check_out TEXT, nights INTEGER,
        price_total_mad REAL, price_per_night_mad REAL, currency TEXT,
        scraped_at TEXT,
        PRIMARY KEY (room_id, month)
    );
    CREATE TABLE IF NOT EXISTS scrape_log (
        month TEXT, tile_idx INTEGER,
        n_results INTEGER, status TEXT, scraped_at TEXT,
        PRIMARY KEY (month, tile_idx)
    );
    """)
    conn.commit()


def already_done(conn, month, tile_idx):
    row = conn.execute(
        "SELECT 1 FROM scrape_log WHERE month=? AND tile_idx=? AND status='ok'",
        (month, tile_idx)).fetchone()
    return row is not None


def upsert_listing(conn, rec, now):
    conn.execute("""
    INSERT INTO listings (room_id,name,title,property_type,neighborhood_title,
        lat,lng,bedrooms,beds,baths,rating,review_count,badges,first_seen,last_seen)
    VALUES (:room_id,:name,:title,:property_type,:neighborhood_title,
        :lat,:lng,:bedrooms,:beds,:baths,:rating,:review_count,:badges,:now,:now)
    ON CONFLICT(room_id) DO UPDATE SET
        name=excluded.name, title=excluded.title,
        property_type=excluded.property_type,
        neighborhood_title=excluded.neighborhood_title,
        lat=excluded.lat, lng=excluded.lng,
        bedrooms=excluded.bedrooms, beds=excluded.beds, baths=excluded.baths,
        rating=excluded.rating, review_count=excluded.review_count,
        badges=excluded.badges, last_seen=excluded.last_seen
    """, {**rec, "now": now})


def upsert_price(conn, room_id, month, ci, co, rec, now):
    if rec["price_per_night"] is None:
        return
    conn.execute("""
    INSERT INTO prices (room_id,month,check_in,check_out,nights,
        price_total_mad,price_per_night_mad,currency,scraped_at)
    VALUES (?,?,?,?,?,?,?,?,?)
    ON CONFLICT(room_id,month) DO UPDATE SET
        price_total_mad=excluded.price_total_mad,
        price_per_night_mad=excluded.price_per_night_mad,
        scraped_at=excluded.scraped_at
    """, (room_id, month, ci, co, NIGHTS,
          rec["price_total"], rec["price_per_night"], CURRENCY, now))


# -------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Casablanca")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    cfg = get_city(args.city)
    rows = args.rows or cfg["rows"]
    cols = args.cols or cfg["cols"]
    DB_PATH = db_path(ROOT, cfg["slug"])

    DB_PATH.parent.mkdir(exist_ok=True)
    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    months = target_months(args.months)
    tiles = make_grid(cfg["bbox"], rows, cols)
    total_steps = len(months) * len(tiles)
    print(f"Collecte {args.city} : {len(months)} mois x {len(tiles)} tuiles "
          f"= {total_steps} recherches -> {DB_PATH.name}")
    print(f"Mois : {[m for m, _, _ in months]}")

    step = 0
    for month, ci, co in months:
        for t in tiles:
            step += 1
            if already_done(conn, month, t["idx"]):
                continue
            now = dt.datetime.now().isoformat(timespec="seconds")
            try:
                res = pyairbnb.search_all(
                    check_in=ci.isoformat(), check_out=co.isoformat(),
                    ne_lat=t["ne_lat"], ne_long=t["ne_lng"],
                    sw_lat=t["sw_lat"], sw_long=t["sw_lng"],
                    zoom_value=ZOOM, price_min=0, price_max=0, adults=ADULTS,
                    currency=CURRENCY, language=LANGUAGE,
                )
                n_priced = 0
                for l in res:
                    rec = parse_listing(l)
                    if not rec["room_id"] or rec["lat"] is None:
                        continue
                    upsert_listing(conn, rec, now)
                    upsert_price(conn, rec["room_id"], month, ci.isoformat(), co.isoformat(), rec, now)
                    if rec["price_per_night"] is not None:
                        n_priced += 1
                conn.execute(
                    "INSERT OR REPLACE INTO scrape_log VALUES (?,?,?,?,?)",
                    (month, t["idx"], len(res), "ok", now))
                conn.commit()
                print(f"[{step:3d}/{total_steps}] {month} tuile {t['idx']:2d} : "
                      f"{len(res):3d} annonces, {n_priced:3d} prix")
            except Exception as e:
                conn.execute(
                    "INSERT OR REPLACE INTO scrape_log VALUES (?,?,?,?,?)",
                    (month, t["idx"], 0, f"error: {e!r}"[:200], now))
                conn.commit()
                print(f"[{step:3d}/{total_steps}] {month} tuile {t['idx']:2d} : ERREUR {e!r}")
            time.sleep(SLEEP_BETWEEN_TILES)

    # bilan
    nl = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    npx = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    print(f"\nBilan : {nl} annonces uniques, {npx} observations de prix.")
    conn.close()


if __name__ == "__main__":
    main()
