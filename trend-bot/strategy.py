"""Calcul des indicateurs et des signaux d'entrée (suivi de tendance)."""
import numpy as np
import pandas as pd


def atr_wilder(df, periode):
    """ATR de Wilder : moyenne lissée du vrai range (True Range)."""
    cloture_prec = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - cloture_prec).abs(),
        (df["Low"] - cloture_prec).abs(),
    ], axis=1).max(axis=1)
    # le premier TR n'a pas de clôture précédente : min_periods évite un biais
    return tr.ewm(alpha=1 / periode, adjust=False, min_periods=periode).mean()


def calculer_indicateurs(df, cfg):
    """Ajoute au DataFrame OHLCV : sma, haut_breakout, atr, momentum, signal."""
    p = cfg["strategie"]
    df = df.copy()
    df["sma"] = df["Close"].rolling(p["sma_filtre"]).mean()
    # Plus haut des N jours PRÉCÉDENTS (shift(1) : on exclut la journée en cours,
    # sinon la clôture ne pourrait jamais dépasser son propre plus haut)
    df["haut_breakout"] = df["High"].rolling(p["breakout"]).max().shift(1)
    df["atr"] = atr_wilder(df, p["atr_periode"])
    # Hausse sur ~3 mois, utilisée pour départager les signaux simultanés
    df["momentum"] = df["Close"] / df["Close"].shift(p["momentum_jours"]) - 1
    # Signal d'entrée : filtre de tendance ET cassure du plus haut 20 jours
    df["signal"] = ((df["Close"] > df["sma"])
                    & (df["Close"] > df["haut_breakout"])
                    & df["atr"].notna()
                    & df["momentum"].notna()).fillna(False)
    return df


def preparer_univers(donnees, cfg):
    """Applique calculer_indicateurs à chaque actif."""
    return {s: calculer_indicateurs(df, cfg) for s, df in donnees.items()}


def taille_position(capital, atr, prix, cash, cfg):
    """Taille = (capital x risque) / (2 x ATR), arrondie à l'unité inférieure,
    puis plafonnée par la limite de 25 % du capital et par le cash disponible
    (frais inclus).
    """
    p = cfg["strategie"]
    if not atr or atr <= 0 or prix <= 0:
        return 0
    risque = capital * cfg["risque_par_trade"]
    qte = risque / (p["stop_initial_atr"] * atr)
    qte = min(qte, capital * cfg["max_position_pct"] / prix)
    qte = min(qte, cash / (prix * (1 + cfg["frais_ordre"])))
    return int(np.floor(qte))
