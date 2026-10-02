"""Chargement de la configuration (config.yaml)."""
from pathlib import Path

import yaml

# Dossier du projet : tous les chemins relatifs du YAML partent de là
RACINE = Path(__file__).resolve().parent


def charger_config(chemin=None):
    """Lit config.yaml et renvoie un dictionnaire."""
    chemin = Path(chemin) if chemin else RACINE / "config.yaml"
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable : {chemin}")
    with open(chemin, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def chemin(cfg_chemin):
    """Transforme un chemin relatif de la config en chemin absolu."""
    p = Path(cfg_chemin)
    return p if p.is_absolute() else RACINE / p
