"""Génère un aperçu statique PNG : choroplèthe + saisonnalité.

Sortie : docs/apercu.png
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data" / "clean.csv")
gj = json.loads((ROOT / "data" / "casa_quartiers.geojson").read_text())
OUT = ROOT / "docs" / "apercu.png"
OUT.parent.mkdir(exist_ok=True)

df = df[~df["is_outlier"]]
PEAK = "2026-08"  # mois affiché sur la carte

# --- valeurs par arrondissement (mois pic) ---
MIN_N = 10  # médiane peu fiable en dessous -> on grise
g = df[df.month == PEAK].groupby("quartier")["price_per_night_mad"]
med = g.median()
med = med[g.count() >= MIN_N]  # ne garder que les arrondissements assez fournis

fig, (axm, axs) = plt.subplots(1, 2, figsize=(16, 8),
                               gridspec_kw={"width_ratios": [1.15, 1]})

# ---------------------------------------------------------------- choroplèthe
vmin, vmax = med.min(), med.max()
norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
cmap = mcm.get_cmap("YlOrRd")

patches, colors = [], []
for f in gj["features"]:
    nom = f["properties"]["nom"]
    geom = shape(f["geometry"])
    val = med.get(nom)
    color = cmap(norm(val)) if pd.notna(val) else "#e8e8e8"
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for p in polys:
        patches.append(MplPolygon(list(p.exterior.coords)))
        colors.append(color)
    # étiquette au centroïde
    c = geom.centroid
    label = nom if pd.isna(val) else f"{nom}\n{val:.0f}"
    axm.annotate(label, (c.x, c.y), ha="center", va="center", fontsize=7,
                 weight="bold", color="#222")

pc = PatchCollection(patches, facecolor=colors, edgecolor="white", linewidths=0.8)
axm.add_collection(pc)
axm.autoscale_view()
axm.set_aspect("equal")
axm.set_xticks([]); axm.set_yticks([])
axm.set_title(f"Prix médian / nuit par arrondissement — {PEAK}\nCasablanca · Airbnb (MAD)",
              fontsize=12, weight="bold")
sm = mcm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
fig.colorbar(sm, ax=axm, fraction=0.04, pad=0.02, label="MAD / nuit")

# --------------------------------------------------------------- saisonnalité
season = df.groupby("month")["price_per_night_mad"].agg(["median", "mean"])
axs.plot(season.index, season["median"], "-o", label="Médiane", color="#d7301f")
axs.plot(season.index, season["mean"], "-s", label="Moyenne", color="#fc8d59")
# quelques arrondissements phares
for q in ["Anfa", "Maârif", "Sidi Belyout", "Hay Hassani"]:
    s = df[df.quartier == q].groupby("month")["price_per_night_mad"].median()
    axs.plot(s.index, s.values, "--", alpha=0.6, label=q)
axs.set_title("Saisonnalité des prix/nuit (12 mois)", fontsize=12, weight="bold")
axs.set_ylabel("MAD / nuit"); axs.tick_params(axis="x", rotation=45)
axs.grid(alpha=0.3); axs.legend(fontsize=8, ncol=2)

n_listings = df[df.city == "Casablanca"]["room_id"].nunique() if "city" in df.columns else df["room_id"].nunique()
fig.suptitle(f"Carte de prix Airbnb · Casablanca  —  {n_listings:,} annonces, 12 mois",
             fontsize=14, weight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(OUT, dpi=130, bbox_inches="tight")
print(f"-> {OUT}")
