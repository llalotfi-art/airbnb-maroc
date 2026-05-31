"""Orchestrateur — met le lot prioritaire en file derrière la collecte en cours.

1. Attend que Marrakech/Agadir/Tanger soient entièrement traitées (poll).
2. Régénère clean.csv (4 villes).
3. Collecte le lot prioritaire (collect + quartiers OSM par ville).
4. Régénère clean.csv final (toutes villes).

Lancé en arrière-plan. Log : data/run_batch.log
"""

import subprocess
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")
SCRAPE = ROOT / "scrape"

WAIT_FOR = {"marrakech": 300, "agadir": 192, "tanger": 192}  # tuiles attendues
PRIORITY = ["Rabat", "Fès", "Essaouira", "Chefchaouen", "Ouarzazate"]
MAX_WAIT_S = 4 * 3600


def attempted(slug):
    p = ROOT / "data" / f"airbnb_{slug}.db"
    if not p.exists():
        return 0
    c = sqlite3.connect(p)
    try:
        return c.execute("SELECT COUNT(*) FROM scrape_log").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        c.close()


def run(*cmd):
    print(f">> {' '.join(cmd)}", flush=True)
    subprocess.run([PY, *cmd], cwd=str(ROOT))


def main():
    # 1) attendre la fin de la collecte en cours
    print("== Attente de la collecte en cours (Marrakech/Agadir/Tanger) ==", flush=True)
    start = time.time()
    while time.time() - start < MAX_WAIT_S:
        state = {s: attempted(s) for s in WAIT_FOR}
        if all(state[s] >= t for s, t in WAIT_FOR.items()):
            print(f"Terminée : {state}", flush=True)
            break
        print(f"  ... {state}", flush=True)
        time.sleep(90)
    time.sleep(15)  # laisser le process courant se fermer proprement

    # 2) clean intermédiaire (4 villes)
    run(str(SCRAPE / "geocode_clean.py"))

    # 3) lot prioritaire
    for city in PRIORITY:
        print(f"\n========== {city} ==========", flush=True)
        run(str(SCRAPE / "collect.py"), "--city", city, "--reset")
        run(str(SCRAPE / "fetch_neighborhoods.py"), "--city", city)
        run(str(SCRAPE / "build_quartiers.py"), "--city", city)

    # 4) clean final
    run(str(SCRAPE / "geocode_clean.py"))
    print("\n=== BATCH PRIORITAIRE TERMINÉ ===", flush=True)


if __name__ == "__main__":
    main()
