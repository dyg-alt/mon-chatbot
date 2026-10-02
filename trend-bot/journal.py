"""Journal des trades : un enregistrement CSV par trade clôturé."""
import csv
from pathlib import Path

COLONNES = ["date_entree", "date_sortie", "actif", "prix_entree", "prix_sortie",
            "quantite", "raison_sortie", "frais", "gain_perte"]


def enregistrer(fichier, trades):
    """Ajoute des trades (liste de dicts) au CSV, en créant l'en-tête si besoin."""
    if not trades:
        return
    fichier = Path(fichier)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not fichier.exists() or fichier.stat().st_size == 0
    with open(fichier, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        if nouveau:
            w.writeheader()
        for t in trades:
            w.writerow({c: t[c] for c in COLONNES})


def ecrire_tout(fichier, trades):
    """Réécrit entièrement le journal (utilisé par le backtest)."""
    fichier = Path(fichier)
    if fichier.exists():
        fichier.unlink()
    if not trades:  # fichier vide avec en-tête, pour rester lisible
        fichier.parent.mkdir(parents=True, exist_ok=True)
        with open(fichier, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLONNES).writeheader()
        return
    enregistrer(fichier, trades)


def lire(fichier):
    """Lit le journal et renvoie une liste de dicts (vide si absent)."""
    fichier = Path(fichier)
    if not fichier.exists():
        return []
    with open(fichier, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
