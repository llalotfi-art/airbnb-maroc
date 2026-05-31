"""Aperçu national PNG : carte du Maroc + classement + saisonnalité comparée.

Sortie : docs/apercu_maroc.png
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrape"))
from cities import CITIES  # noqa: E402

df = pd.read_csv(ROOT / "data" / "clean.csv")
df = df[~df["is_outlier"]]
OUT = ROOT / "docs" / "apercu_maroc.png"
OUT.parent.mkdir(exist_ok=True)

stats = (df.groupby("city")
         .agg(median=("price_per_night_mad", "median"),
              n=("room_id", "nunique"))
         .reset_index())
stats["lat"] = stats["city"].map(lambda c: CITIES[c]["center"][0])
stats["lng"] = stats["city"].map(lambda c: CITIES[c]["center"][1])

fig = plt.figure(figsize=(16, 9))
gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 1], height_ratios=[1, 1])
axm = fig.add_subplot(gs[:, 0])
axb = fig.add_subplot(gs[0, 1])
axs = fig.add_subplot(gs[1, 1])

# --- carte (scatter) ---
norm = mcolors.Normalize(stats["median"].min(), stats["median"].max())
cmap = mcm.get_cmap("YlOrRd")
sizes = 120 + (stats["n"] / stats["n"].max()) * 1400
axm.scatter(stats["lng"], stats["lat"], s=sizes, c=stats["median"],
            cmap=cmap, norm=norm, edgecolor="black", linewidth=0.6, zorder=3)
for _, r in stats.iterrows():
    axm.annotate(f"{r['city']}\n{r['median']:.0f} MAD", (r["lng"], r["lat"]),
                 textcoords="offset points", xytext=(8, 6), fontsize=8, weight="bold")
axm.set_xlim(-11, -4); axm.set_ylim(29, 36.5)
axm.set_xlabel("Longitude"); axm.set_ylabel("Latitude")
axm.set_title("Prix médian / nuit par ville (taille = nb d'annonces)", weight="bold")
axm.grid(alpha=0.25)
fig.colorbar(mcm.ScalarMappable(norm=norm, cmap=cmap), ax=axm,
             fraction=0.04, pad=0.02, label="MAD / nuit")

# --- classement ---
bar = stats.sort_values("median")
axb.barh(bar["city"], bar["median"], color=cmap(norm(bar["median"])))
axb.set_title("Classement (prix médian/nuit)", weight="bold")
axb.set_xlabel("MAD / nuit")
for i, v in enumerate(bar["median"]):
    axb.text(v + 5, i, f"{v:.0f}", va="center", fontsize=8)

# --- saisonnalité ---
season = df.groupby(["city", "month"])["price_per_night_mad"].median().reset_index()
for city in stats.sort_values("median", ascending=False)["city"]:
    s = season[season.city == city]
    axs.plot(s["month"], s["price_per_night_mad"], marker="o", ms=3, label=city)
axs.set_title("Saisonnalité comparée", weight="bold")
axs.set_ylabel("MAD / nuit"); axs.tick_params(axis="x", rotation=90, labelsize=7)
axs.grid(alpha=0.25); axs.legend(fontsize=6, ncol=2)

n_list = stats["n"].sum()
fig.suptitle(f"Prix Airbnb au Maroc — {len(stats)} villes · {n_list:,} annonces · "
             f"saisonnalité 12 mois", fontsize=15, weight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(OUT, dpi=130, bbox_inches="tight")
print(f"-> {OUT}")
