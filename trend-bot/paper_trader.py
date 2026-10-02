"""Paper trading quotidien : lit les données du jour, met à jour les stops,
passe des ordres FICTIFS et sauvegarde l'état du portefeuille en JSON.

À lancer une fois par jour, après la clôture des marchés américains.
Le script est idempotent : le relancer le même jour ne fait rien de plus.
"""
import json
import sys
from datetime import datetime, timedelta

import pandas as pd

import journal
from backtest import Portefeuille, barres_du_jour
from config import charger_config, chemin
from data import DataError, charger_univers
from strategy import preparer_univers


def charger_etat(cfg):
    """Relit l'état JSON, ou crée un portefeuille neuf au premier lancement."""
    f = chemin(cfg["sortie"]["etat_portefeuille"])
    if f.exists():
        try:
            with open(f, encoding="utf-8") as fh:
                return Portefeuille.depuis_dict(cfg, json.load(fh))
        except (json.JSONDecodeError, KeyError) as e:
            # on ne repart pas de zéro en silence : l'état serait perdu
            raise RuntimeError(f"État du portefeuille corrompu ({f}) : {e}. "
                               "Corrigez ou supprimez ce fichier.") from e
    return Portefeuille(cfg)


def sauver_etat(cfg, pf):
    """Écriture atomique (fichier temporaire puis renommage)."""
    f = chemin(cfg["sortie"]["etat_portefeuille"])
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(pf.vers_dict(), fh, ensure_ascii=False, indent=2)
    tmp.replace(f)


def executer_jour(cfg, brut=None):
    """Traite tous les jours de bourse non encore traités. Renvoie le portefeuille.

    `brut` permet d'injecter des données (tests) au lieu de télécharger.
    """
    if brut is None:
        # ~400 jours calendaires suffisent pour la SMA 200 ; on force le rafraîchissement
        debut = (datetime.today() - timedelta(days=500)).strftime("%Y-%m-%d")
        brut = charger_univers(cfg, debut=debut, forcer=True)
    donnees = preparer_univers(brut, cfg)
    dates = sorted(set().union(*[df.index for df in donnees.values()]))

    pf = charger_etat(cfg)
    if pf.derniere_date is None:
        # Premier lancement : on démarre aujourd'hui, sans rejouer le passé
        a_traiter = dates[-1:]
    else:
        a_traiter = [d for d in dates if d > pd.Timestamp(pf.derniere_date)]
    if not a_traiter:
        print(f"Rien à faire : le portefeuille est déjà à jour ({pf.derniere_date}).")
        return pf

    for d in a_traiter:
        clotures, ordres = pf.traiter_jour(d, barres_du_jour(donnees, d))
        print(f"--- {d.date()} ---")
        for o in ordres:
            print("  " + o)
        if not ordres:
            print("  Aucun ordre.")
        journal.enregistrer(chemin(cfg["sortie"]["journal_paper"]), clotures)
    sauver_etat(cfg, pf)

    print(f"\nCapital : {pf.valeur():,.2f} USD (cash {pf.cash:,.2f}) | "
          f"{len(pf.positions)} position(s) ouverte(s)")
    for s, p in pf.positions.items():
        print(f"  {s}: {p['quantite']} @ {p['prix_entree']:.2f} | "
              f"dernier {p['dernier_prix']:.2f} | stop {p['stop']:.2f} ({p['type_stop']})")
    return pf


def main():
    cfg = charger_config()
    try:
        executer_jour(cfg)
    except DataError as e:
        # État intact : on n'écrit rien si les données manquent
        print(f"ERREUR DONNÉES : {e}\nAucun ordre passé, état inchangé.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(2)
    import dashboard
    dashboard.generer(cfg)
    print(f"Tableau de bord mis à jour : {cfg['sortie']['dashboard']}")


if __name__ == "__main__":
    main()
