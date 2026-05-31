"""Tests d'interface du dashboard via streamlit AppTest (sans navigateur).

Couvre : vue nationale (métriques/période), vue ville (ville/mois/filtres),
et l'authentification par mot de passe.

Usage : python scrape/test_app.py     (exit != 0 si un test échoue)
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
CLEAN = ROOT / "data" / "clean.csv"

from streamlit.testing.v1 import AppTest  # noqa: E402

PASS = FAIL = 0
METRICS = ["Prix médian / nuit", "Prix moyen / nuit", "Prix médian / personne"]


def run(fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  ✅ {fn.__name__}")
        PASS += 1
    except Exception:
        print(f"  ❌ {fn.__name__}")
        traceback.print_exc()
        FAIL += 1


def W(at, coll, label):
    for w in getattr(at, coll):
        if w.label == label:
            return w
    raise AssertionError(f"{coll} '{label}' introuvable")


def fresh(run_=True):
    at = AppTest.from_file(APP, default_timeout=120)
    if run_:
        at.run()
    return at


def to_city_view(at):
    W(at, "radio", "Niveau").set_value("🏙️ Ville (détail)").run()
    return at


# ----------------------------------------------------------------- national
def test_national_default():
    at = fresh()
    assert not at.exception
    assert at.title[0].value.startswith("🇲🇦")


def test_national_all_metrics():
    for m in METRICS:
        at = fresh()
        W(at, "selectbox", "Métrique").set_value(m).run()
        assert not at.exception, f"métrique {m}"


def test_national_specific_month():
    at = fresh()
    W(at, "selectbox", "Période").set_value("2026-06").run()
    assert not at.exception


# --------------------------------------------------------------------- ville
def test_city_view():
    at = to_city_view(fresh())
    assert not at.exception
    assert at.title[0].value.startswith("🏠")


def test_city_switch_city():
    at = to_city_view(fresh())
    villes = W(at, "selectbox", "Ville").options
    for v in villes:
        W(at, "selectbox", "Ville").set_value(v).run()
        assert not at.exception, f"ville {v}"


def test_city_change_month_and_metric():
    at = to_city_view(fresh())
    ss = W(at, "select_slider", "Mois")
    ss.set_value(ss.options[-1]).run()          # dernier mois
    assert not at.exception
    for m in METRICS:
        W(at, "selectbox", "Métrique").set_value(m).run()
        assert not at.exception, m


def test_city_filters_toggles():
    at = to_city_view(fresh())
    for label in ["Guest Favorite uniquement", "Afficher les annonces (points)"]:
        W(at, "checkbox", label).set_value(True).run()
        assert not at.exception, label
    W(at, "checkbox", "Masquer les valeurs aberrantes").set_value(False).run()
    assert not at.exception


def test_city_empty_quartiers():
    at = to_city_view(fresh())
    W(at, "multiselect", "Quartiers").set_value([]).run()   # aucun quartier
    assert not at.exception
    # KPI "Annonces" doit valoir 0 sans planter
    assert any(m.value == "0" for m in at.metric)


# ----------------------------------------------------------------------- auth
def test_auth_gate():
    at = fresh(run_=False)
    at.secrets["app_password"] = "motdepasse"
    at.run()
    assert len(at.title) == 0 and len(at.text_input) >= 1   # bloqué

    at.text_input[0].set_value("faux").run()
    assert len(at.title) == 0                                # toujours bloqué
    assert any("incorrect" in e.value.lower() for e in at.error)

    at.text_input[0].set_value("motdepasse").run()
    assert len(at.title) >= 1                                # débloqué


def main():
    if not CLEAN.exists():
        sys.exit("clean.csv absent — lance la collecte + geocode_clean d'abord.")
    print("=== TESTS DASHBOARD (AppTest) ===")
    for t in [test_national_default, test_national_all_metrics,
              test_national_specific_month, test_city_view,
              test_city_switch_city, test_city_change_month_and_metric,
              test_city_filters_toggles, test_city_empty_quartiers,
              test_auth_gate]:
        run(t)
    print(f"\n{PASS} réussis, {FAIL} échoués")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
