# trend-bot — paper trading de suivi de tendance

Bot de **paper trading** (ordres fictifs, aucun argent réel) sur ETF, en timeframe journalier.
Il ne passe jamais d'ordre réel : il n'est connecté à aucun courtier.

## Stratégie

| Élément | Règle |
|---|---|
| Univers | SPY, QQQ, EWL, EEM, GLD, TLT, IWM, EFA |
| Filtre | acheter seulement si clôture > moyenne mobile 200 jours |
| Entrée | clôture > plus haut des 20 jours précédents |
| Stop initial | prix d'entrée − 2 × ATR(14) |
| Stop suiveur | plus haut depuis l'entrée − 3 × ATR(14), ne peut que monter |
| Stop actif | le plus élevé des deux |
| Sortie | clôture sous le stop actif |
| Taille | (capital × 1 %) / (2 × ATR), arrondie à l'unité inférieure, plafonnée à 25 % du capital |
| Limites | 5 positions maximum ; si trop de signaux, priorité à la plus forte hausse sur 3 mois |
| Coûts | 0,1 % de frais par ordre + 0,05 % de slippage |

**Hypothèses d'exécution** : le signal est calculé avec la clôture du jour et l'ordre est exécuté
à cette clôture, corrigée du slippage. Le stop actif du jour J est celui calculé le jour J−1 ; il est
mis à jour après le test de sortie. Le « capital actuel » est la valeur totale (cash + positions
valorisées au marché). Les prix sont ajustés des dividendes et splits.

## Installation

```bash
cd trend-bot
pip install -r requirements.txt
```

Tous les paramètres (capital, univers, frais, risque, périodes…) sont dans **`config.yaml`**.

## Lancer le backtest

```bash
python backtest.py            # entraînement 2015-2022 + validation 2023-aujourd'hui
python backtest.py --refresh  # force le re-téléchargement des données
```

Affiche, pour chaque période, les performances du bot comparées à l'achat-conservation de SPY
(chaque période repart de 100 000 USD), écrit les journaux de trades
(`output/journal_backtest_*.csv`) et génère le tableau de bord. Les données sont mises en cache
dans `data_cache/` (rafraîchies après 12 h).

`python backtest.py --synthetic` utilise des données **fictives** hors ligne : uniquement pour
vérifier que le code tourne. Ces chiffres n'ont aucune valeur financière, et le tableau de bord
l'indique en rouge.

## Lancer le paper trading quotidien

```bash
python paper_trader.py
```

À lancer **une fois par jour de bourse, après la clôture US** (ex. 22 h 30 heure suisse en hiver).
Le script : télécharge les données, rattrape les jours manquants s'il y en a, applique les stops,
passe les ordres fictifs, sauvegarde l'état dans `output/etat_portefeuille.json`, ajoute les trades
clôturés à `output/journal_paper.csv` et régénère le tableau de bord. Le relancer le même jour ne
change rien. Au premier lancement, le portefeuille démarre aujourd'hui (le passé n'est pas rejoué).
Pour repartir de zéro, supprimez `output/etat_portefeuille.json`.

Exemple cron (lundi-vendredi, 22 h 30) :

```
30 22 * * 1-5  cd /chemin/vers/trend-bot && python paper_trader.py >> output/cron.log 2>&1
```

## Tableau de bord

`output/dashboard.html` (fichier autonome, s'ouvre dans le navigateur), régénérable avec
`python dashboard.py`. Il affiche la courbe de capital du bot vs SPY, les rendements total et
annualisé, le drawdown maximum, le taux de réussite, gain/perte moyens et leur ratio, le nombre de
trades, les positions ouvertes avec leur stop, et les 20 derniers trades.

## Fichiers

| Fichier | Rôle |
|---|---|
| `data.py` | téléchargement yfinance + cache CSV, gestion des erreurs |
| `strategy.py` | indicateurs, signaux, taille de position |
| `backtest.py` | portefeuille (frais, slippage, stops) et simulation |
| `paper_trader.py` | exécution quotidienne + état JSON |
| `journal.py` | journal CSV des trades |
| `dashboard.py` | tableau de bord HTML |
| `tests/` | `python -m pytest` |

## Gestion des erreurs

Si un téléchargement échoue, il est retenté puis on utilise le cache existant (avec avertissement).
Sans cache, l'actif est ignoré ; si le benchmark ou tous les actifs manquent, le programme s'arrête
avec un message clair et **sans modifier l'état du paper trading**.

## Avertissement

Les performances passées ne garantissent pas les performances futures. Un backtest est
optimiste par nature (pas de liquidité réelle, exécution idéale à la clôture).
