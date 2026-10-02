"""Simulation complète : portefeuille, frais, slippage, gestion du capital.

La classe Portefeuille est partagée avec paper_trader.py : le backtest et le
paper trading appliquent donc exactement les mêmes règles.

Hypothèse d'exécution : le signal est calculé avec la clôture du jour et
l'ordre est exécuté à cette clôture, corrigée du slippage (ordre "à la clôture").
Aucun look-ahead : on n'utilise que des données connues à la clôture.
"""
import argparse
import json
import sys
from datetime import datetime

import pandas as pd

import journal
from config import charger_config, chemin
from data import DataError, charger_univers, donnees_synthetiques
from strategy import preparer_univers, taille_position


class Portefeuille:
    """Cash + positions ouvertes, avec mise à jour des stops et passage d'ordres."""

    def __init__(self, cfg, capital=None):
        self.cfg = cfg
        self.cash = float(capital if capital is not None else cfg["capital_initial"])
        self.capital_initial = self.cash
        self.positions = {}        # symbole -> dict de la position
        self.courbe = []           # liste de [date, valeur_totale]
        self.derniere_date = None

    # ---------- sérialisation (état JSON du paper trading) ----------
    def vers_dict(self):
        return {"capital_initial": self.capital_initial, "cash": self.cash,
                "positions": self.positions, "courbe": self.courbe,
                "derniere_date": self.derniere_date}

    @classmethod
    def depuis_dict(cls, cfg, d):
        p = cls(cfg, d["capital_initial"])
        p.cash, p.positions = d["cash"], d["positions"]
        p.courbe, p.derniere_date = d["courbe"], d["derniere_date"]
        return p

    # ---------- valorisation ----------
    def valeur(self):
        """Capital actuel = cash + valeur de marché des positions."""
        return self.cash + sum(p["quantite"] * p["dernier_prix"]
                               for p in self.positions.values())

    # ---------- une journée de simulation ----------
    def traiter_jour(self, date, barres):
        """Traite une journée. `barres` = {symbole: ligne d'indicateurs du jour}.

        Ordre des opérations : 1) sorties sur stops, 2) mise à jour des stops,
        3) nouvelles entrées. Renvoie (trades_clotures, ordres_passes).
        """
        c = self.cfg
        p = c["strategie"]
        frais, slip = c["frais_ordre"], c["slippage"]
        date_s = pd.Timestamp(date).strftime("%Y-%m-%d")
        clotures, ordres, sortis_aujourdhui = [], [], set()

        # 1) Sorties : clôture sous le stop actif connu la veille
        for s in list(self.positions):
            b = barres.get(s)
            pos = self.positions[s]
            if b is None:
                continue
            pos["dernier_prix"] = float(b["Close"])
            if b["Close"] < pos["stop"]:
                prix = b["Close"] * (1 - slip)            # vente : prix dégradé
                frais_sortie = pos["quantite"] * prix * frais
                self.cash += pos["quantite"] * prix - frais_sortie
                total_frais = pos["frais_entree"] + frais_sortie
                gain = (prix - pos["prix_entree"]) * pos["quantite"] - total_frais
                trade = {"date_entree": pos["date_entree"], "date_sortie": date_s,
                         "actif": s, "prix_entree": round(pos["prix_entree"], 4),
                         "prix_sortie": round(prix, 4), "quantite": pos["quantite"],
                         "raison_sortie": pos["type_stop"],
                         "frais": round(total_frais, 2), "gain_perte": round(gain, 2)}
                clotures.append(trade)
                ordres.append(f"VENTE  {pos['quantite']} {s} @ {prix:.2f} ({pos['type_stop']})")
                sortis_aujourdhui.add(s)
                del self.positions[s]
            else:
                # 2) Mise à jour du stop suiveur : il ne peut que monter
                pos["plus_haut"] = max(pos["plus_haut"], float(b["High"]))
                suiveur = pos["plus_haut"] - p["stop_suiveur_atr"] * float(b["atr"])
                pos["stop_suiveur"] = max(pos["stop_suiveur"], suiveur)
                # Stop actif = le plus élevé des deux
                if pos["stop_suiveur"] > pos["stop_initial"]:
                    pos["stop"], pos["type_stop"] = pos["stop_suiveur"], "stop_suiveur"
                else:
                    pos["stop"], pos["type_stop"] = pos["stop_initial"], "stop_initial"

        # 3) Entrées : signaux du jour, priorité à la plus forte hausse sur 3 mois
        capital = self.valeur()
        places = c["max_positions"] - len(self.positions)
        candidats = [(float(b["momentum"]), s) for s, b in barres.items()
                     if b["signal"] and s not in self.positions
                     and s not in sortis_aujourdhui]
        candidats.sort(reverse=True)
        for _, s in candidats:
            if places <= 0:
                break
            b = barres[s]
            prix = float(b["Close"]) * (1 + slip)         # achat : prix dégradé
            atr = float(b["atr"])
            qte = taille_position(capital, atr, prix, self.cash, c)
            if qte < 1:
                continue
            frais_entree = qte * prix * frais
            self.cash -= qte * prix + frais_entree
            initial = prix - p["stop_initial_atr"] * atr
            plus_haut = float(b["High"])
            suiveur = plus_haut - p["stop_suiveur_atr"] * atr
            actif = max(initial, suiveur)
            self.positions[s] = {
                "date_entree": date_s, "prix_entree": prix, "quantite": qte,
                "frais_entree": frais_entree, "stop_initial": initial,
                "stop_suiveur": suiveur, "plus_haut": plus_haut, "stop": actif,
                "type_stop": "stop_suiveur" if suiveur > initial else "stop_initial",
                "dernier_prix": float(b["Close"]),
            }
            ordres.append(f"ACHAT  {qte} {s} @ {prix:.2f} (stop {actif:.2f})")
            places -= 1

        self.courbe.append([date_s, round(self.valeur(), 2)])
        self.derniere_date = date_s
        return clotures, ordres


def barres_du_jour(donnees, date):
    """Extrait la ligne du jour de chaque actif disponible à cette date."""
    return {s: df.loc[date] for s, df in donnees.items() if date in df.index}


def calculer_metriques(courbe, trades, capital_initial):
    """Statistiques de performance à partir de la courbe de capital et des trades."""
    valeurs = pd.Series([v for _, v in courbe], index=pd.to_datetime([d for d, _ in courbe]))
    serie = pd.concat([pd.Series([capital_initial]), valeurs.reset_index(drop=True)])
    pic = serie.cummax()
    dd_max = float(((serie - pic) / pic).min())            # négatif
    final = float(valeurs.iloc[-1])
    rend_total = final / capital_initial - 1
    jours = max((valeurs.index[-1] - valeurs.index[0]).days, 1)
    annualise = (final / capital_initial) ** (365.25 / jours) - 1 if final > 0 else -1.0

    gains = [t["gain_perte"] for t in trades if t["gain_perte"] > 0]
    pertes = [t["gain_perte"] for t in trades if t["gain_perte"] <= 0]
    gain_moy = sum(gains) / len(gains) if gains else 0.0
    perte_moy = sum(pertes) / len(pertes) if pertes else 0.0
    return {
        "capital_final": round(final, 2),
        "rendement_total": rend_total,
        "rendement_annualise": annualise,
        "drawdown_max": dd_max,
        "nb_trades": len(trades),
        "taux_reussite": len(gains) / len(trades) if trades else 0.0,
        "gain_moyen": gain_moy,
        "perte_moyenne": perte_moy,
        "ratio_gain_perte": gain_moy / abs(perte_moy) if perte_moy else None,
    }


def acheter_conserver(df_bench, dates, cfg):
    """Courbe d'achat-conservation du benchmark (mêmes frais/slippage à l'achat)."""
    c = cfg
    cl = df_bench["Close"].reindex(dates).ffill()
    prix_achat = cl.iloc[0] * (1 + c["slippage"])
    qte = c["capital_initial"] / (prix_achat * (1 + c["frais_ordre"]))  # fractions permises
    return [[d.strftime("%Y-%m-%d"), round(float(qte * v), 2)] for d, v in cl.items()]


def lancer_backtest(donnees, cfg, debut, fin=None):
    """Simule la stratégie sur [debut, fin] avec un capital initial neuf.

    `donnees` doit contenir déjà les indicateurs (preparer_univers) et un
    historique antérieur à `debut` pour chauffer la SMA 200.
    """
    toutes = sorted(set().union(*[df.index for df in donnees.values()]))
    dates = [d for d in toutes if d >= pd.Timestamp(debut)
             and (fin is None or d <= pd.Timestamp(fin))]
    if not dates:
        raise DataError(f"Aucune donnée entre {debut} et {fin}.")
    pf = Portefeuille(cfg)
    trades = []
    for d in dates:
        clot, _ = pf.traiter_jour(d, barres_du_jour(donnees, d))
        trades.extend(clot)
    bench = acheter_conserver(donnees[cfg["benchmark"]], pd.DatetimeIndex(dates), cfg)
    return {
        "debut": dates[0].strftime("%Y-%m-%d"), "fin": dates[-1].strftime("%Y-%m-%d"),
        "courbe": pf.courbe, "courbe_benchmark": bench, "trades": trades,
        "positions_ouvertes": pf.positions,
        "metriques": calculer_metriques(pf.courbe, trades, cfg["capital_initial"]),
        "metriques_benchmark": calculer_metriques(bench, [], cfg["capital_initial"]),
    }


def _pct(x):
    return f"{x * 100:+.2f} %"


def afficher(nom, r):
    m, b = r["metriques"], r["metriques_benchmark"]
    rg = m["ratio_gain_perte"]
    print(f"\n=== {nom} : {r['debut']} -> {r['fin']} ===")
    print(f"{'':28}{'Trend-bot':>14}{'SPY buy&hold':>16}")
    print(f"{'Capital final (USD)':28}{m['capital_final']:>14,.0f}{b['capital_final']:>16,.0f}")
    print(f"{'Rendement total':28}{_pct(m['rendement_total']):>14}{_pct(b['rendement_total']):>16}")
    print(f"{'Rendement annualisé':28}{_pct(m['rendement_annualise']):>14}{_pct(b['rendement_annualise']):>16}")
    print(f"{'Drawdown maximum':28}{_pct(m['drawdown_max']):>14}{_pct(b['drawdown_max']):>16}")
    print(f"Trades : {m['nb_trades']} | réussite : {m['taux_reussite'] * 100:.1f} % | "
          f"gain moyen : {m['gain_moyen']:,.0f} | perte moyenne : {m['perte_moyenne']:,.0f} | "
          f"ratio G/P : {'n/a' if rg is None else f'{rg:.2f}'}")
    print(f"Positions encore ouvertes à la fin : {len(r['positions_ouvertes'])}")


def main():
    ap = argparse.ArgumentParser(description="Backtest du trend-bot")
    ap.add_argument("--config", default=None, help="chemin d'un config.yaml alternatif")
    ap.add_argument("--synthetic", action="store_true",
                    help="données FICTIVES hors ligne (test technique uniquement)")
    ap.add_argument("--refresh", action="store_true", help="forcer le re-téléchargement")
    args = ap.parse_args()
    cfg = charger_config(args.config)

    try:
        if args.synthetic:
            print("*** DONNÉES SYNTHÉTIQUES : résultats sans valeur financière ***")
            brut = donnees_synthetiques(cfg["univers"], cfg["donnees"]["debut_historique"])
        else:
            brut = charger_univers(cfg, forcer=args.refresh)
    except DataError as e:
        print(f"\nERREUR DONNÉES : {e}", file=sys.stderr)
        sys.exit(1)

    donnees = preparer_univers(brut, cfg)
    dossier = chemin(cfg["sortie"]["dossier"])
    dossier.mkdir(parents=True, exist_ok=True)
    resultats = {"genere_le": datetime.now().isoformat(timespec="seconds"),
                 "synthetique": args.synthetic, "periodes": {}}
    for cle, nom in [("entrainement", "ENTRAÎNEMENT"), ("validation", "VALIDATION")]:
        per = cfg["periodes"][cle]
        r = lancer_backtest(donnees, cfg, per["debut"], per["fin"])
        afficher(nom, r)
        journal.ecrire_tout(dossier / f"journal_backtest_{cle}.csv", r["trades"])
        resultats["periodes"][cle] = r
    with open(chemin(cfg["sortie"]["resultats_backtest"]), "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False)
    print(f"\nRésultats enregistrés dans {cfg['sortie']['resultats_backtest']}")

    import dashboard
    dashboard.generer(cfg)
    print(f"Tableau de bord : {cfg['sortie']['dashboard']}")


if __name__ == "__main__":
    main()
