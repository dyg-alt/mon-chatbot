"""Téléchargement des données via yfinance avec cache local (CSV).

Gestion d'erreurs : si le téléchargement échoue, on retombe sur le cache
existant (avec un avertissement). S'il n'y a pas de cache, on lève DataError.
"""
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import chemin

COLONNES = ["Open", "High", "Low", "Close", "Volume"]


class DataError(Exception):
    """Levée quand les données nécessaires ne peuvent pas être obtenues."""


def _telecharger(symbole, debut, fin, tentatives):
    """Télécharge un actif depuis yfinance (prix ajustés des dividendes/splits)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise DataError("yfinance n'est pas installé (pip install -r requirements.txt)") from e

    derniere_erreur = None
    for essai in range(1, tentatives + 1):
        try:
            df = yf.download(symbole, start=debut, end=fin, auto_adjust=True,
                             progress=False, threads=False)
            if df is not None and not df.empty:
                # yfinance récent renvoie des colonnes MultiIndex (champ, ticker)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                manquantes = [c for c in COLONNES if c not in df.columns]
                if manquantes:
                    raise DataError(f"colonnes manquantes pour {symbole} : {manquantes}")
                df = df[COLONNES].dropna(subset=["Close", "High"])
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df.index.name = "Date"
                return df.sort_index()
            derniere_erreur = "réponse vide"
        except DataError:
            raise
        except Exception as e:  # réseau, limite de débit, etc.
            derniere_erreur = str(e)
        if essai < tentatives:
            time.sleep(2 ** essai)  # attente exponentielle : 2 s, 4 s...
    raise DataError(f"Téléchargement de {symbole} impossible ({derniere_erreur})")


def _cache_valide(fichier, age_max_heures):
    """Le cache est frais s'il a été écrit il y a moins de age_max_heures."""
    if not fichier.exists():
        return False
    age = time.time() - fichier.stat().st_mtime
    return age < age_max_heures * 3600


def _lire_cache(fichier):
    df = pd.read_csv(fichier, index_col="Date", parse_dates=True)
    return df.sort_index()


def charger_actif(symbole, cfg, debut=None, fin=None, forcer=False):
    """Renvoie le DataFrame OHLCV d'un actif (cache local ou téléchargement)."""
    d = cfg["donnees"]
    debut = debut or d["debut_historique"]
    dossier = chemin(d["dossier_cache"])
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{symbole}.csv"

    if not forcer and _cache_valide(fichier, d["age_max_heures"]):
        df = _lire_cache(fichier)
        # le cache doit couvrir le début demandé (à une semaine près)
        if not df.empty and df.index[0] <= pd.Timestamp(debut) + timedelta(days=7):
            return df

    try:
        df = _telecharger(symbole, debut, fin, d["tentatives"])
        df.to_csv(fichier)
        return df
    except DataError as e:
        if fichier.exists():
            print(f"[AVERTISSEMENT] {e} -> utilisation du cache existant pour {symbole}")
            return _lire_cache(fichier)
        raise


def charger_univers(cfg, debut=None, fin=None, forcer=False):
    """Charge tous les actifs de l'univers. Renvoie {symbole: DataFrame}.

    Un actif en échec est ignoré avec un avertissement ; si le benchmark ou
    tous les actifs manquent, une DataError est levée.
    """
    donnees, erreurs = {}, {}
    for s in cfg["univers"]:
        try:
            donnees[s] = charger_actif(s, cfg, debut, fin, forcer)
        except DataError as e:
            erreurs[s] = str(e)
            print(f"[ERREUR] {e}")
    if not donnees:
        raise DataError("Aucune donnée disponible. Vérifiez la connexion internet "
                        "(accès à Yahoo Finance) ou le cache local.")
    if cfg["benchmark"] not in donnees:
        raise DataError(f"Le benchmark {cfg['benchmark']} est indisponible : "
                        "comparaison impossible.")
    if erreurs:
        print(f"[AVERTISSEMENT] Actifs ignorés : {', '.join(erreurs)}")
    return donnees


def donnees_synthetiques(symboles, debut="2013-06-01", fin=None, graine=42):
    """Données FICTIVES (marche aléatoire à régimes) pour tester la mécanique
    hors ligne. Les résultats obtenus avec ne reflètent AUCUNE réalité de marché.
    """
    fin = fin or datetime.today().strftime("%Y-%m-%d")
    dates = pd.bdate_range(debut, fin)
    rng = np.random.default_rng(graine)
    n = len(dates)
    # facteur de marché commun + régimes haussiers/baissiers qui durent des mois
    regime = np.repeat(rng.choice([0.0008, -0.0006], size=n // 120 + 1,
                                  p=[0.65, 0.35]), 120)[:n]
    marche = regime + rng.normal(0, 0.009, n)
    out = {}
    for s in symboles:
        beta = rng.uniform(0.3, 1.2)
        r = beta * marche + rng.normal(0.0001, 0.007, n)
        close = 100 * np.exp(np.cumsum(r))
        ouv = close * np.exp(rng.normal(0, 0.003, n))
        amp = np.abs(rng.normal(0.006, 0.003, n))
        haut = np.maximum(close, ouv) * (1 + amp)
        bas = np.minimum(close, ouv) * (1 - amp)
        out[s] = pd.DataFrame({"Open": ouv, "High": haut, "Low": bas,
                               "Close": close, "Volume": 1_000_000},
                              index=pd.DatetimeIndex(dates, name="Date"))
    return out
