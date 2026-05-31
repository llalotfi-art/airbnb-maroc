"""Phase 0 — Recon technique.

But : valider l'accès aux endpoints Airbnb sur une zone test de Casablanca,
inspecter la structure des données (annonces + calendrier de prix), et écrire
quelques fichiers JSON bruts dans data/ pour analyse.

Aucune écriture en base ici : c'est juste une validation.
"""

import datetime as dt
import json
from pathlib import Path

import pyairbnb

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)

# --- Paramètres figés (comparabilité) ---
CURRENCY = "MAD"
LANGUAGE = "en"
ADULTS = 2

# Séjour test : 3 nuits, ~4 semaines à partir d'aujourd'hui (mardi -> vendredi)
CHECK_IN = dt.date(2026, 6, 23)
CHECK_OUT = dt.date(2026, 6, 26)

# Zone test : centre de Casablanca (Gauthier / Maarif / Anfa)
NE_LAT, NE_LNG = 33.605, -7.585
SW_LAT, SW_LNG = 33.560, -7.660
ZOOM = 15


def dump(name, obj):
    path = DATA / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    print(f"  -> écrit {path} ({path.stat().st_size/1024:.1f} Ko)")


def main():
    # NB: search_first_page est buggé en v2.2.1 (passe le mauvais objet au
    # parser). search_all est correct et reste borné par la petite zone test.
    print("== 1) Recherche annonces (search_all sur zone test) ==")
    results = pyairbnb.search_all(
        check_in=CHECK_IN.isoformat(),
        check_out=CHECK_OUT.isoformat(),
        ne_lat=NE_LAT, ne_long=NE_LNG, sw_lat=SW_LAT, sw_long=SW_LNG,
        zoom_value=ZOOM,
        price_min=0, price_max=0,
        adults=ADULTS,
        currency=CURRENCY, language=LANGUAGE,
    )
    print(f"  Annonces trouvées : {len(results)}")
    if not results:
        print("  !! Aucune annonce — endpoint ou zone à revoir.")
        return
    dump("recon_search.json", results)

    first = results[0]
    print("\n== 2) Structure d'une annonce (clés de 1er niveau) ==")
    print("  ", sorted(first.keys()))
    print("\n  Aperçu annonce #0 :")
    print(json.dumps(first, ensure_ascii=False, indent=2, default=str)[:1500])

    room_id = str(first.get("room_id") or first.get("listing_id") or first.get("id") or "")
    print(f"\n  room_id retenu : {room_id}")

    print("\n== 3) Clé API + calendrier de prix ==")
    api_key = pyairbnb.get_api_key("")
    print(f"  api_key : {api_key[:8]}... (len={len(api_key)})")

    try:
        cal = pyairbnb.get_calendar(api_key=api_key, room_id=room_id)
        dump("recon_calendar.json", cal)
        if isinstance(cal, list):
            print(f"  calendrier : liste de {len(cal)} éléments ; exemple : {json.dumps(cal[0], default=str)[:400]}")
        elif isinstance(cal, dict):
            print(f"  calendrier (dict) clés : {list(cal.keys())[:20]}")
    except Exception as e:
        print(f"  !! get_calendar a échoué : {e!r}")

    print("\n== 4) Prix d'un séjour précis (get_price) ==")
    try:
        price = pyairbnb.get_price(
            room_id=room_id, check_in=CHECK_IN, check_out=CHECK_OUT,
            adults=ADULTS, currency=CURRENCY, language=LANGUAGE, api_key=api_key,
        )
        dump("recon_price.json", price)
        print("  prix keys :", list(price.keys()) if isinstance(price, dict) else type(price))
    except Exception as e:
        print(f"  !! get_price a échoué : {e!r}")

    print("\nOK — recon terminée.")


if __name__ == "__main__":
    main()
