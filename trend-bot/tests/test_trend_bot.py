"""Tests des règles de la stratégie et du paper trading (données fictives)."""
import copy

import pandas as pd
import pytest

import journal
from backtest import Portefeuille, barres_du_jour, calculer_metriques
from config import charger_config
from data import donnees_synthetiques
from paper_trader import executer_jour
from strategy import atr_wilder, preparer_univers, taille_position


@pytest.fixture
def cfg(tmp_path):
    c = charger_config()
    c["sortie"] = {"dossier": str(tmp_path), "etat_portefeuille": str(tmp_path / "etat.json"),
                   "journal_paper": str(tmp_path / "j.csv"),
                   "resultats_backtest": str(tmp_path / "r.json"),
                   "dashboard": str(tmp_path / "d.html")}
    return c


def barre(close, atr=2.0, high=None, signal=False, mom=0.1):
    return pd.Series({"Close": close, "High": high or close, "atr": atr,
                      "signal": signal, "momentum": mom})


def test_taille_position_formule(cfg):
    # risque 1 % de 100 000 = 1 000 ; 2 x ATR(5) = 10 -> 100 unités (plafond 25 % non atteint)
    assert taille_position(100_000, 5, 50, 100_000, cfg) == 100


def test_taille_position_plafond_25pct(cfg):
    # ATR minuscule -> formule donnerait 50 000 unités ; plafond 25 000 $ / 100 $ = 250
    assert taille_position(100_000, 0.01, 100, 100_000, cfg) == 250


def test_taille_position_arrondi_inferieur(cfg):
    assert taille_position(100_000, 3, 10, 100_000, cfg) == 166  # 1000/6 = 166,67


def test_entree_frais_slippage_et_stop_initial(cfg):
    pf = Portefeuille(cfg)
    pf.traiter_jour("2024-01-02", {"AAA": barre(100, atr=5, signal=True)})
    pos = pf.positions["AAA"]
    prix = 100 * 1.0005
    assert pos["prix_entree"] == pytest.approx(prix)
    assert pos["quantite"] == 100
    assert pos["stop_initial"] == pytest.approx(prix - 10)
    assert pf.cash == pytest.approx(100_000 - 100 * prix * 1.001)


def test_stop_suiveur_ne_peut_que_monter_et_sortie(cfg):
    pf = Portefeuille(cfg)
    pf.traiter_jour("2024-01-02", {"AAA": barre(100, atr=5, signal=True)})
    # hausse : le plus haut monte à 150, stop suiveur = 150 - 3x5 = 135
    pf.traiter_jour("2024-01-03", {"AAA": barre(148, atr=5, high=150)})
    assert pf.positions["AAA"]["stop"] == pytest.approx(135)
    assert pf.positions["AAA"]["type_stop"] == "stop_suiveur"
    # repli sans casser le stop : le stop ne baisse pas même si l'ATR grossit
    pf.traiter_jour("2024-01-04", {"AAA": barre(140, atr=9, high=145)})
    assert pf.positions["AAA"]["stop"] == pytest.approx(135)
    # clôture sous le stop -> vente
    clot, _ = pf.traiter_jour("2024-01-05", {"AAA": barre(130, atr=5)})
    assert len(clot) == 1 and clot[0]["raison_sortie"] == "stop_suiveur"
    assert "AAA" not in pf.positions
    assert clot[0]["gain_perte"] > 0


def test_sortie_stop_initial_perte(cfg):
    pf = Portefeuille(cfg)
    pf.traiter_jour("2024-01-02", {"AAA": barre(100, atr=5, signal=True)})
    clot, _ = pf.traiter_jour("2024-01-03", {"AAA": barre(85, atr=5)})
    assert clot[0]["raison_sortie"] == "stop_initial"
    assert clot[0]["gain_perte"] < -1000  # perte ~ risque + frais/slippage


def test_priorite_momentum_et_max_positions(cfg):
    pf = Portefeuille(cfg)
    barres = {f"S{i}": barre(100, atr=5, signal=True, mom=i / 100) for i in range(8)}
    pf.traiter_jour("2024-01-02", barres)
    assert len(pf.positions) == 5
    assert set(pf.positions) == {"S7", "S6", "S5", "S4", "S3"}


def test_pas_de_double_position(cfg):
    pf = Portefeuille(cfg)
    pf.traiter_jour("2024-01-02", {"AAA": barre(100, atr=5, signal=True)})
    q = pf.positions["AAA"]["quantite"]
    pf.traiter_jour("2024-01-03", {"AAA": barre(101, atr=5, signal=True)})
    assert pf.positions["AAA"]["quantite"] == q


def test_pas_de_lookahead_indicateurs(cfg):
    """Modifier le futur ne doit pas changer les indicateurs/signaux passés."""
    brut = donnees_synthetiques(["AAA"], "2018-01-01", "2020-12-31")
    a = preparer_univers(brut, cfg)["AAA"]
    brut2 = copy.deepcopy(brut)
    brut2["AAA"].iloc[-50:, :4] *= 3
    b = preparer_univers(brut2, cfg)["AAA"]
    pd.testing.assert_frame_equal(a.iloc[:-50], b.iloc[:-50])


def test_atr_constant():
    df = pd.DataFrame({"High": [11.0] * 30, "Low": [9.0] * 30, "Close": [10.0] * 30})
    assert atr_wilder(df, 14).iloc[-1] == pytest.approx(2.0)


def test_metriques():
    courbe = [["2024-01-02", 110_000], ["2024-01-03", 88_000], ["2025-01-02", 121_000]]
    m = calculer_metriques(courbe, [{"gain_perte": 300}, {"gain_perte": -100}], 100_000)
    assert m["drawdown_max"] == pytest.approx(-0.2)
    assert m["rendement_total"] == pytest.approx(0.21)
    assert m["taux_reussite"] == 0.5 and m["ratio_gain_perte"] == 3


def test_paper_trader_idempotent_et_reprise(cfg):
    brut = donnees_synthetiques(cfg["univers"], "2022-01-01", "2024-06-28")
    pf = executer_jour(cfg, brut)          # 1er lancement : démarre au dernier jour
    assert len(pf.courbe) == 1
    # lendemain : de nouvelles données arrivent, l'état JSON est relu
    brut2 = donnees_synthetiques(cfg["univers"], "2022-01-01", "2024-07-05")
    pf2 = executer_jour(cfg, brut2)        # rattrape les 5 jours manquants
    assert len(pf2.courbe) == 6
    pf3 = executer_jour(cfg, brut2)        # 2e lancement identique : rien ne change
    assert len(pf3.courbe) == 6


def test_journal_csv(tmp_path):
    f = tmp_path / "j.csv"
    t = {"date_entree": "a", "date_sortie": "b", "actif": "SPY", "prix_entree": 1,
         "prix_sortie": 2, "quantite": 3, "raison_sortie": "stop_initial",
         "frais": 0.1, "gain_perte": 2.9}
    journal.enregistrer(f, [t])
    journal.enregistrer(f, [t])
    assert len(journal.lire(f)) == 2
