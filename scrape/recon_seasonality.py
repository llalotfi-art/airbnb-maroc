"""Phase 0bis — Valider que la recherche capte la saisonnalité.

On relance la MÊME recherche (mini-zone) pour 3 séjours à des mois différents
et on compare le prix/nuit des annonces communes. Si les prix diffèrent par
mois, l'approche "search par mois" est validée pour la courbe annuelle.
"""

import datetime as dt
import re

import pyairbnb

CURRENCY, LANGUAGE, ADULTS = "MAD", "en", 2
# Mini-zone (Gauthier) pour aller vite
NE_LAT, NE_LNG = 33.592, -7.625
SW_LAT, SW_LNG = 33.580, -7.640
ZOOM = 16

# 3 séjours de 3 nuits, même créneau mardi->vendredi, mois différents
STAYS = {
    "juin":     (dt.date(2026, 6, 16),  dt.date(2026, 6, 19)),
    "aout":     (dt.date(2026, 8, 18),  dt.date(2026, 8, 21)),
    "decembre": (dt.date(2026, 12, 15), dt.date(2026, 12, 18)),
}
NIGHTS = 3


def per_night(listing):
    """Extrait le prix/nuit (MAD) depuis le champ price d'une annonce."""
    price = listing.get("price", {})
    amt = price.get("unit", {}).get("amount")  # total du séjour
    if isinstance(amt, (int, float)) and amt > 0:
        return round(amt / NIGHTS, 1)
    # fallback : parser le break_down "3 nights x MAD746.66"
    for bd in price.get("break_down", []):
        m = re.search(r"x\s*MAD([\d.,]+)", bd.get("description", ""))
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def main():
    by_month = {}
    for label, (ci, co) in STAYS.items():
        res = pyairbnb.search_all(
            check_in=ci.isoformat(), check_out=co.isoformat(),
            ne_lat=NE_LAT, ne_long=NE_LNG, sw_lat=SW_LAT, sw_long=SW_LNG,
            zoom_value=ZOOM, price_min=0, price_max=0, adults=ADULTS,
            currency=CURRENCY, language=LANGUAGE,
        )
        prices = {str(l["room_id"]): per_night(l) for l in res if per_night(l)}
        by_month[label] = prices
        vals = [v for v in prices.values()]
        med = sorted(vals)[len(vals)//2] if vals else None
        print(f"{label:9s}: {len(res):3d} annonces, {len(prices):3d} avec prix, médiane/nuit ≈ {med} MAD")

    # Annonces présentes dans les 3 mois -> comparer
    common = set.intersection(*[set(d) for d in by_month.values()]) if by_month else set()
    print(f"\nAnnonces communes aux 3 mois : {len(common)}")
    print(f"{'room_id':>20} | {'juin':>8} {'aout':>8} {'decembre':>8}  (MAD/nuit)")
    for rid in list(common)[:12]:
        row = "  ".join(f"{by_month[m][rid]:>8}" for m in STAYS)
        print(f"{rid:>20} | {row}")


if __name__ == "__main__":
    main()
