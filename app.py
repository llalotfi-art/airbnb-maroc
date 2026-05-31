"""Dashboard — Carte des prix Airbnb au Maroc (multi-villes, saisonnalité).

Lancer :  streamlit run app.py
Données   :  data/clean.csv  +  data/{slug}_quartiers.geojson
Auth      :  optionnelle via st.secrets["app_password"] (pour le déploiement).

Villes sans découpage en quartiers (petites villes sans arrondissements) :
la carte bascule automatiquement en points colorés par prix.
"""

import json
import sys
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.features import GeoJson, GeoJsonTooltip
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scrape"))
from cities import CITIES, quartiers_path  # noqa: E402

# Préférer la version compressée (8 Mo vs 33 Mo) si elle existe — Streamlit Cloud
CLEAN = next((ROOT / "data" / f for f in ("clean.csv.gz", "clean.csv")
              if (ROOT / "data" / f).exists()), ROOT / "data" / "clean.csv")

st.set_page_config(page_title="Prix Airbnb · Maroc", layout="wide")

METRICS = {
    "Prix médian / nuit": ("price_per_night_mad", "median"),
    "Prix moyen / nuit": ("price_per_night_mad", "mean"),
    "Prix médian / personne": ("price_per_person_mad", "median"),
}


# ----------------------------------------------------------------------- auth
def get_password():
    try:
        return st.secrets["app_password"]
    except Exception:
        return None  # pas de secret -> accès libre (dev local)


def check_password():
    pw_expected = get_password()
    if pw_expected is None or st.session_state.get("auth_ok"):
        return True
    pw = st.text_input("🔒 Mot de passe", type="password")
    if pw:
        if pw == pw_expected:
            st.session_state["auth_ok"] = True
            return True
        st.error("Mot de passe incorrect.")
    return False


# ----------------------------------------------------------------- chargement
@st.cache_data
def load_data():
    return pd.read_csv(CLEAN)


@st.cache_data
def load_geojson(slug):
    p = quartiers_path(ROOT, slug)
    return json.loads(p.read_text()) if p.exists() else None


def agg(df, col, how, by="quartier"):
    return getattr(df.groupby(by)[col], how)()


def add_price_points(fmap, d, colored=True):
    pts = d.dropna(subset=["lat", "lng", "price_per_night_mad"])
    scale = None
    if colored and len(pts):
        scale = cm.linear.YlOrRd_09.scale(pts["price_per_night_mad"].quantile(.05),
                                          pts["price_per_night_mad"].quantile(.95))
        scale.caption = "Prix/nuit (MAD)"
        scale.add_to(fmap)
    for _, r in pts.iterrows():
        color = scale(r["price_per_night_mad"]) if scale is not None else "#3186cc"
        folium.CircleMarker([r["lat"], r["lng"]], radius=3, weight=0, fill=True,
                            fill_opacity=0.6, color=color,
                            popup=f"{r['price_per_night_mad']:.0f} MAD/nuit").add_to(fmap)


def render_national(df_all):
    """Vue nationale : toutes les villes comparées sur une carte du Maroc."""
    st.title("🇲🇦 Prix Airbnb au Maroc — vue nationale")

    metric_label = st.sidebar.selectbox("Métrique", list(METRICS), key="nat_metric")
    col, how = METRICS[metric_label]
    hide_out = st.sidebar.checkbox("Masquer les aberrants", value=True, key="nat_out")
    month_opts = ["Année entière"] + sorted(df_all["month"].dropna().unique())
    month = st.sidebar.selectbox("Période", month_opts, key="nat_month")

    d = df_all[~df_all["is_outlier"]] if hide_out else df_all
    dm = d if month == "Année entière" else d[d["month"] == month]

    stats = (dm.groupby("city")
             .agg(valeur=(col, how), n=("room_id", "count"),
                  med_nuit=("price_per_night_mad", "median"),
                  note=("rating", "median"))
             .reset_index().dropna(subset=["valeur"]))

    st.caption(f"Métrique : **{metric_label}** · Période : **{month}** · "
               f"{stats['n'].sum():,} observations · {len(stats)} villes")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Carte du Maroc")
        m = folium.Map(location=[31.0, -7.5], zoom_start=6, tiles="cartodbpositron")
        if len(stats):
            scale = cm.linear.YlOrRd_09.scale(stats["valeur"].min(), stats["valeur"].max())
            scale.caption = f"{metric_label} (MAD)"
            scale.add_to(m)
            for _, r in stats.iterrows():
                center = CITIES[r["city"]]["center"]
                radius = min(8 + (r["n"] ** 0.5) / 4, 28)
                folium.CircleMarker(
                    center, radius=radius, color="white", weight=1, fill=True,
                    fill_color=scale(r["valeur"]), fill_opacity=0.85,
                    tooltip=(f"{r['city']} — {r['valeur']:.0f} MAD "
                             f"({int(r['n'])} obs)")).add_to(m)
        st_folium(m, height=520, use_container_width=True)

    with right:
        st.subheader("Classement des villes")
        bar = stats.sort_values("valeur")
        figb = px.bar(bar, x="valeur", y="city", orientation="h",
                      labels={"valeur": f"{metric_label} (MAD)", "city": ""})
        figb.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(figb, width="stretch")

    st.subheader("Saisonnalité comparée (prix/nuit médian par mois)")
    season = (d.groupby(["city", "month"])["price_per_night_mad"]
              .median().reset_index())
    figs = px.line(season, x="month", y="price_per_night_mad", color="city",
                   markers=True, labels={"month": "Mois",
                                         "price_per_night_mad": "MAD/nuit"})
    figs.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(figs, width="stretch")

    st.subheader("Tableau comparatif")
    tbl = stats.rename(columns={"city": "Ville", "valeur": metric_label,
                                "n": "Observations", "med_nuit": "Médiane/nuit",
                                "note": "Note médiane"}).sort_values(
        metric_label, ascending=False)
    st.dataframe(tbl, width="stretch", hide_index=True)


# --------------------------------------------------------------------- gardes
if not check_password():
    st.stop()

if not CLEAN.exists():
    st.title("Prix Airbnb · Maroc")
    st.warning("Données absentes. Lance la collecte puis "
               "`python scrape/geocode_clean.py` pour générer data/clean.csv.")
    st.stop()

df_all = load_data()
cities = [c for c in CITIES if c in df_all["city"].unique()]

# ------------------------------------------------------------------------ vue
st.sidebar.header("Vue")
view = st.sidebar.radio("Niveau", ["🇲🇦 Maroc (national)", "🏙️ Ville (détail)"],
                        label_visibility="collapsed")
if view.startswith("🇲🇦"):
    render_national(df_all)
    st.stop()

# --------------------------------------------------------------------- filtres
st.sidebar.header("Filtres")
city = st.sidebar.selectbox("Ville", cities)
cfg = CITIES[city]
df = df_all[df_all["city"] == city]
geojson = load_geojson(cfg["slug"])
has_quartiers = (geojson is not None) and bool(df["quartier"].notna().any())

metric_label = st.sidebar.selectbox("Métrique", list(METRICS))
col, how = METRICS[metric_label]

months = sorted(df["month"].dropna().unique())
month = st.sidebar.select_slider("Mois", options=months, value=months[0])

if has_quartiers:
    quartiers_all = sorted(df["quartier"].dropna().unique())
    quartiers = st.sidebar.multiselect("Quartiers", quartiers_all, default=quartiers_all)
else:
    quartiers = None
    st.sidebar.caption("ℹ️ Pas de découpage par quartier pour cette ville — "
                       "carte en points colorés par prix.")

types_all = sorted(df["property_type"].dropna().unique())
types = st.sidebar.multiselect("Type de bien", types_all, default=types_all)
min_rating = st.sidebar.slider("Note minimale", 0.0, 5.0, 0.0, 0.1)
only_gf = st.sidebar.checkbox("Guest Favorite uniquement")
hide_out = st.sidebar.checkbox("Masquer les valeurs aberrantes", value=True)
show_points = st.sidebar.checkbox("Afficher les annonces (points)", value=False)

group_col = "quartier" if has_quartiers else "property_type"
group_label = "quartier" if has_quartiers else "type de bien"


def apply_filters(d, with_month=True):
    m = d["property_type"].isin(types)
    if quartiers is not None:
        m &= d["quartier"].isin(quartiers)
    if with_month:
        m &= d["month"] == month
    if min_rating > 0:
        m &= d["rating"].fillna(0) >= min_rating
    if only_gf:
        m &= d["guest_favorite"] == True  # noqa: E712
    if hide_out:
        m &= ~d["is_outlier"]
    return d[m]


fmonth = apply_filters(df, with_month=True)
fall = apply_filters(df, with_month=False)

# ----------------------------------------------------------------------- entête
st.title(f"🏠 Prix Airbnb — {city}")
st.caption(f"Métrique : **{metric_label}** · Mois : **{month}** · "
           f"{len(fmonth)} annonces filtrées")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Annonces", f"{len(fmonth)}")
c2.metric("Prix médian/nuit", f"{fmonth['price_per_night_mad'].median():.0f} MAD"
          if len(fmonth) else "—")
c3.metric("Prix moyen/nuit", f"{fmonth['price_per_night_mad'].mean():.0f} MAD"
          if len(fmonth) else "—")
c4.metric("Note médiane", f"{fmonth['rating'].median():.2f}"
          if fmonth['rating'].notna().any() else "—")

# ------------------------------------------------------------------------- carte
left, right = st.columns([3, 2])

with left:
    st.subheader(f"Carte — {metric_label} ({month})")
    m = folium.Map(location=cfg["center"], zoom_start=cfg["zoom"],
                   tiles="cartodbpositron")
    if has_quartiers:
        by_q = agg(fmonth, col, how).dropna()
        if len(by_q):
            scale = cm.linear.YlOrRd_09.scale(by_q.min(), by_q.max())
            scale.caption = f"{metric_label} (MAD)"

            def style_fn(feat):
                v = by_q.get(feat["properties"]["nom"])
                return {"fillColor": scale(v) if v == v and v is not None else "#dddddd",
                        "color": "white", "weight": 1, "fillOpacity": 0.75}

            for feat in geojson["features"]:
                v = by_q.get(feat["properties"]["nom"])
                feat["properties"]["valeur"] = f"{v:.0f} MAD" if v == v and v is not None else "n/d"
            GeoJson(geojson, style_function=style_fn,
                    tooltip=GeoJsonTooltip(fields=["nom", "valeur"],
                                           aliases=["Quartier", metric_label])).add_to(m)
            scale.add_to(m)
        if show_points:
            add_price_points(m, fmonth, colored=False)
    else:
        add_price_points(m, fmonth, colored=True)
    st_folium(m, height=520, use_container_width=True)

with right:
    st.subheader("Saisonnalité")
    season = (fall.groupby("month")[col].agg(how).reset_index()
              .rename(columns={col: "valeur"}))
    fig = px.line(season, x="month", y="valeur", markers=True,
                  labels={"month": "Mois", "valeur": f"{metric_label} (MAD)"})
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.subheader(f"Par {group_label} (ce mois)")
    bar = agg(fmonth, col, how, by=group_col).dropna().sort_values().reset_index()
    bar.columns = [group_col, "valeur"]
    figb = px.bar(bar, x="valeur", y=group_col, orientation="h",
                  labels={"valeur": f"{metric_label} (MAD)", group_col: ""})
    figb.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(figb, width="stretch")

# ------------------------------------------------------------------ distributions
st.subheader(f"Distribution des prix/nuit par {group_label} (ce mois)")
figd = px.box(fmonth.dropna(subset=["price_per_night_mad"]),
              x=group_col, y="price_per_night_mad", points=False,
              labels={group_col: "", "price_per_night_mad": "MAD/nuit"})
figd.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(figd, width="stretch")

with st.expander("Voir les annonces filtrées (table)"):
    st.dataframe(
        fmonth[["name", "quartier", "property_type", "bedrooms", "beds",
                "rating", "review_count", "price_per_night_mad",
                "price_per_person_mad", "guest_favorite"]]
        .sort_values("price_per_night_mad", ascending=False),
        width="stretch", height=400)
