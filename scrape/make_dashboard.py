"""Génère docs/dashboard.html à partir de data/clean.csv.

Remplace le DATA object dans le template HTML par les vraies statistiques.

Usage :
    python scrape/make_dashboard.py                # ville la plus fournie
    python scrape/make_dashboard.py Casablanca
    python scrape/make_dashboard.py Marrakech
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrape"))
from cities import CITIES  # noqa: E402

CLEAN = next(
    (ROOT / "data" / f for f in ("clean.csv.gz", "clean.csv")
     if (ROOT / "data" / f).exists()),
    ROOT / "data" / "clean.csv",
)
TEMPLATE = ROOT / "docs" / "dashboard_template.html"
OUT = ROOT / "docs" / "dashboard.html"

FR_MONTHS = {
    "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr",
    "05": "Mai", "06": "Juin", "07": "Juil", "08": "Août",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc",
}

# Positions (x, y) ∈ [0, 1]² sur la carte schématique du Maroc
CITY_POS = {
    "Tanger":      (0.30, 0.10), "Chefchaouen": (0.41, 0.16),
    "Tétouan":     (0.35, 0.12), "Rabat":        (0.30, 0.30),
    "Salé":        (0.30, 0.32), "Kénitra":      (0.25, 0.28),
    "Fès":         (0.50, 0.30), "Meknès":       (0.47, 0.25),
    "Casablanca":  (0.24, 0.37), "Mohammedia":   (0.26, 0.38),
    "El Jadida":   (0.18, 0.45), "Essaouira":    (0.17, 0.55),
    "Marrakech":   (0.40, 0.58), "Ouarzazate":   (0.55, 0.66),
    "Agadir":      (0.22, 0.74), "Oujda":        (0.72, 0.20),
    "Nador":       (0.65, 0.14), "Ifrane":       (0.52, 0.26),
    "Asilah":      (0.24, 0.12), "Dakhla":       (0.28, 0.92),
}


# ─── helpers ────────────────────────────────────────────────────────────────

def fr(m: str) -> str:
    """'2026-06' → 'Juin'"""
    return FR_MONTHS.get(m[-2:], m)


def fr_label(m: str) -> str:
    """'2026-06' → 'Juin 2026'"""
    return f"{fr(m)} {m[:4]}"


def safe(v, d: int = 0) -> float:
    try:
        f = float(v)
        return round(f, d) if np.isfinite(f) else 0.0
    except Exception:
        return 0.0


def pct_str(a: float, b: float) -> str:
    if b == 0:
        return "+0,0%"
    p = (a - b) / b * 100
    return f"{p:+.1f}%".replace(".", ",")


def direction(a: float, b: float) -> str:
    return "up" if a >= b else "down"


# ─── city builder ────────────────────────────────────────────────────────────

def build_city(df: pd.DataFrame, city: str) -> dict:
    d = df[(df.city == city) & ~df.is_outlier].copy()
    if d.empty:
        return {}

    months = sorted(d.month.dropna().unique())
    latest = months[-1]
    prev   = months[-2] if len(months) > 1 else None

    dm = d[d.month == latest]
    dp = d[d.month == prev] if prev else pd.DataFrame()

    n     = len(dm)
    n_tot = len(df[(df.city == city) & (df.month == latest)])
    mp    = safe(dm.price_per_night_mad.median())
    ap    = safe(dm.price_per_night_mad.mean())
    mr    = safe(dm.rating.median(), 2)
    nr    = int(dm.review_count.notna().sum()) if "review_count" in dm.columns else n

    prev_mp = safe(dp.price_per_night_mad.median()) if not dp.empty else 0
    prev_ap = safe(dp.price_per_night_mad.mean())   if not dp.empty else 0

    d_mp = [direction(mp, prev_mp), pct_str(mp, prev_mp)] if prev_mp else None
    d_ap = [direction(ap, prev_ap), pct_str(ap, prev_ap)] if prev_ap else None

    # Saisonnalité (12 derniers mois)
    season_s = d.groupby("month").price_per_night_mad.median().dropna().sort_index().tail(12)
    season   = [[fr(m), safe(v)] for m, v in season_s.items()]

    # Barres par type de bien (ce mois)
    bars_s = (dm.groupby("property_type").price_per_night_mad.median()
                .dropna().sort_values(ascending=False).head(12))
    bars   = [[t, safe(v)] for t, v in bars_s.items()]

    # Box plot par type de bien
    boxes = []
    for pt, g in dm.groupby("property_type"):
        p = g.price_per_night_mad.dropna()
        if len(p) >= 4:
            boxes.append([pt,
                          safe(p.quantile(.05)), safe(p.quantile(.25)),
                          safe(p.median()),
                          safe(p.quantile(.75)), safe(p.quantile(.95))])

    # Table (top 7 par prix décroissant)
    top   = dm.sort_values("price_per_night_mad", ascending=False).head(7)
    table = []
    for _, r in top.iterrows():
        name  = str(r.get("name", ""))[:40] if pd.notna(r.get("name")) else "—"
        ptype = str(r.get("property_type", "—"))
        qtier = str(r.get("quartier", "—")) if pd.notna(r.get("quartier")) else "—"
        rat   = safe(r.get("rating",  4.5), 2) or 4.5
        fav   = 1 if r.get("guest_favorite") else 0
        price = int(safe(r.price_per_night_mad))
        table.append([name, ptype, qtier, rat, fav, price])

    prices  = dm.price_per_night_mad.dropna()
    map_min = safe(prices.quantile(.05))
    map_max = safe(prices.quantile(.95))

    return dict(
        flag="🏠",
        title=f"Prix Airbnb — {city}",
        chips=[
            ["Métrique", "Prix médian / nuit"],
            ["Mois", fr_label(latest)],
            ["Annonces", str(n)],
        ],
        kpis=[
            dict(label="Annonces filtrées", val=str(n), unit="", icon="list",
                 delta=None, foot=f"sur {n_tot} collectées"),
            dict(label="Prix médian / nuit", val=str(int(mp)), unit="MAD", icon="tag",
                 delta=d_mp, foot="vs mois préc."),
            dict(label="Prix moyen / nuit", val=str(int(ap)), unit="MAD", icon="avg",
                 delta=d_ap, foot="vs mois préc."),
            dict(label="Note médiane", val=f"{mr:.2f}", unit="/5", icon="star",
                 delta=None, foot=f"{nr} avis vérifiés"),
        ],
        mapMin=map_min,
        mapMax=map_max,
        markers="scatter",
        season=season,
        bars=bars,
        boxes=boxes,
        table=table,
    )


# ─── national builder ────────────────────────────────────────────────────────

def build_national(df: pd.DataFrame) -> dict:
    d     = df[~df.is_outlier]
    stats = (d.groupby("city")
              .agg(n=("room_id", "count"),
                   med=("price_per_night_mad", "median"),
                   note=("rating", "median"))
              .reset_index().dropna(subset=["med"]))

    months  = sorted(d.month.dropna().unique())
    latest  = months[-1]
    prev    = months[-2] if len(months) > 1 else None

    nat_mp  = safe(d[d.month == latest].price_per_night_mad.median())
    nat_pp  = safe(d[d.month == prev].price_per_night_mad.median()) if prev else 0
    nat_med = safe(d.price_per_night_mad.median())

    dearest  = stats.loc[stats.med.idxmax()]
    total_n  = int(d.room_id.count())
    n_cities = int(stats.city.nunique())
    n_months = len(months)

    # Positions sur la carte
    cities_list = []
    for _, r in stats.iterrows():
        pos = CITY_POS.get(r.city)
        if pos is None:
            cfg = CITIES.get(r.city, {})
            if cfg:
                lat, lng = cfg["center"]
                x = max(0.05, min(0.90, (lng + 13.0) / 12.0 * 0.65 + 0.08))
                y = max(0.05, min(0.90, (36.5 - lat) / 7.5  * 0.85 + 0.05))
                pos = (round(x, 2), round(y, 2))
            else:
                continue
        cities_list.append([r.city, pos[0], pos[1], safe(r.med)])

    # Saisonnalité nationale combinée
    season_s = d.groupby("month").price_per_night_mad.median().dropna().sort_index().tail(12)
    season   = [[fr(m), safe(v)] for m, v in season_s.items()]

    # Barres par ville
    bars = [[r.city, safe(r.med)]
            for _, r in stats.sort_values("med", ascending=False).iterrows()]

    # Box plot par ville
    boxes = []
    for city, g in d.groupby("city"):
        p = g.price_per_night_mad.dropna()
        if len(p) >= 5:
            boxes.append([city,
                          safe(p.quantile(.05)), safe(p.quantile(.25)),
                          safe(p.median()),
                          safe(p.quantile(.75)), safe(p.quantile(.95))])

    # Tableau comparatif des villes
    table = []
    for _, r in stats.sort_values("med", ascending=False).iterrows():
        cd  = d[d.city == r.city]
        cm  = sorted(cd.month.dropna().unique())
        cl  = cm[-1]
        cpm = cm[-2] if len(cm) > 1 else None
        cm_v = safe(cd[cd.month == cl].price_per_night_mad.median())
        cp_v = safe(cd[cd.month == cpm].price_per_night_mad.median()) if cpm else 0

        qtiers = ""
        if "quartier" in cd.columns:
            ql = [q for q in cd.quartier.value_counts().head(3).index
                  if pd.notna(q) and str(q) != "nan"]
            qtiers = " · ".join(ql)

        n_fmt = f"{int(r.n):,}".replace(",", " ") + " annonces"
        table.append([
            r.city,
            n_fmt,
            qtiers or "—",
            safe(r.note, 2),
            safe(r.med),
            pct_str(cm_v, cp_v),
        ])

    obs_fmt = f"{total_n:,}".replace(",", " ")
    med_all = stats.med

    return dict(
        flag="🇲🇦",
        title="Prix Airbnb au Maroc — vue nationale",
        chips=[
            ["Métrique", "Prix médian / nuit"],
            ["Période", "Année entière"],
            ["Observations", obs_fmt],
            ["Villes", str(n_cities)],
        ],
        kpis=[
            dict(label="Observations", val=obs_fmt, unit="", icon="list",
                 delta=None, foot=f"{n_cities} villes · {n_months} mois"),
            dict(label="Prix médian national", val=str(int(nat_med)), unit="MAD", icon="tag",
                 delta=[direction(nat_mp, nat_pp), pct_str(nat_mp, nat_pp)],
                 foot="vs mois préc."),
            dict(label="Ville la plus chère", val=str(int(dearest.med)), unit="MAD", icon="avg",
                 delta=["up", dearest.city], foot="prix médian / nuit"),
            dict(label="Note médiane", val=f"{safe(d.rating.median(), 2):.2f}", unit="/5",
                 icon="star", delta=None, foot="tout le pays"),
        ],
        mapMin=safe(med_all.min()),
        mapMax=safe(med_all.max()),
        markers="cities",
        cities=cities_list,
        season=season,
        bars=bars,
        boxes=boxes,
        table=table,
    )


# ─── HTML patching ───────────────────────────────────────────────────────────

def patch_html(html: str, DATA: dict, default_city: str, all_types: list) -> str:
    # 1. Remplacer le bloc const DATA={...};
    marker = "// ---------- DATA ----------"
    m_start = html.index(marker)
    m_data  = html.index("const DATA=", m_start)
    m_end   = html.index("\n};", m_data) + len("\n};")
    new_data = "const DATA=" + json.dumps(DATA, ensure_ascii=False,
                                          separators=(",", ":")) + ";"
    html = html[:m_data] + new_data + html[m_end:]

    # 2. Remplacer TYPES par les types réels du CSV
    types_js = "const TYPES=" + json.dumps(sorted(all_types), ensure_ascii=False) + ";"
    html = re.sub(r"const TYPES=\[.*?\];", types_js, html)

    # 3. Mettre à jour le label de la ville par défaut dans la sidebar
    html = html.replace(
        '<span id="cityVal">Essaouira</span>',
        f'<span id="cityVal">{default_city}</span>',
    )

    # 4. Rendre dynamique le sous-titre de la carte (supprime les valeurs figées)
    html = html.replace(
        "view==='city'?'Juin 2026 · 131 annonces géolocalisées':'Année entière · 9 villes'",
        "(view==='city'"
        "?(DATA.city.chips[1][1]+' · '+DATA.city.chips[2][1]+' annonces géolocalisées')"
        ":('Année entière · '+DATA.national.cities.length+' villes'))",
    )

    # 5. Rendre dynamique le comptage dans le filtre de prix (PF.apply)
    html = html.replace(
        "const n=full?131:Math.max(1,Math.round(131*kept/Math.max(1,total)));",
        "const nCity=+DATA.city.chips[2][1];"
        "const n=full?nCity:Math.max(1,Math.round(nCity*kept/Math.max(1,total)));",
    )
    html = html.replace(
        "sub.textContent=`Juin 2026 · ${n} annonce${n>1?'s':''} géolocalisée${n>1?'s':''}`",
        "sub.textContent=`${DATA.city.chips[1][1]} · "
        "${n} annonce${n>1?'s':''} géolocalisée${n>1?'s':''}`",
    )

    return html


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    default_city_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if not CLEAN.exists():
        print(f"Erreur : {CLEAN} introuvable. Lance d'abord geocode_clean.py.")
        sys.exit(1)
    if not TEMPLATE.exists():
        print(f"Erreur : template introuvable → {TEMPLATE}")
        sys.exit(1)

    print(f"Lecture de {CLEAN.name}…")
    df = pd.read_csv(CLEAN)

    available = [c for c in CITIES if c in df.city.unique()]
    if not available:
        print("Aucune ville CITIES dans le CSV.")
        sys.exit(1)

    if default_city_arg:
        if default_city_arg not in available:
            print(f"Ville '{default_city_arg}' inconnue. Disponibles : {available}")
            sys.exit(1)
        default_city = default_city_arg
    else:
        counts = df.groupby("city").size().reindex(available).dropna()
        default_city = str(counts.idxmax())

    print(f"Ville par défaut : {default_city}")
    print("Calcul des statistiques…")

    city_data    = build_city(df, default_city)
    national_data = build_national(df)

    if not city_data:
        print(f"Données insuffisantes pour {default_city}.")
        sys.exit(1)

    DATA      = {"city": city_data, "national": national_data}
    all_types = sorted(df.property_type.dropna().unique().tolist())

    html = TEMPLATE.read_text(encoding="utf-8")
    html = patch_html(html, DATA, default_city, all_types)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")

    print(f"\n✓ {OUT}")
    print(f"  Ville : {default_city} · "
          f"{len(city_data['bars'])} types · "
          f"{len(city_data['season'])} mois saisonnalité")
    print(f"  National : {len(national_data['cities'])} villes")
    print(f"  Types disponibles : {len(all_types)}")


if __name__ == "__main__":
    main()
