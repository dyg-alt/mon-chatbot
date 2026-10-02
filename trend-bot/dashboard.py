"""Génération du tableau de bord HTML (fichier autonome, graphiques en SVG)."""
import json
from html import escape

import journal
from backtest import calculer_metriques
from config import charger_config, chemin

LARG, HAUT, MARGE = 760, 300, {"g": 62, "d": 12, "h": 14, "b": 28}


def _courbe_svg(series):
    """Graphique linéaire SVG. `series` = [(nom, classe_css, [[date, valeur], ...])]."""
    tous = [v for _, _, pts in series for _, v in pts]
    if not tous:
        return "<p class='muted'>Pas de données.</p>"
    vmin, vmax = min(tous), max(tous)
    marge_v = (vmax - vmin) * 0.05 or 1
    vmin, vmax = vmin - marge_v, vmax + marge_v
    dates = [d for d in sorted({d for _, _, pts in series for d, _ in pts})]
    idx = {d: i for i, d in enumerate(dates)}
    w = LARG - MARGE["g"] - MARGE["d"]
    h = HAUT - MARGE["h"] - MARGE["b"]

    def x(d):
        return MARGE["g"] + w * idx[d] / max(len(dates) - 1, 1)

    def y(v):
        return MARGE["h"] + h * (1 - (v - vmin) / (vmax - vmin))

    out = [f"<svg viewBox='0 0 {LARG} {HAUT}' role='img' class='chart'>"]
    for i in range(5):  # graduations horizontales
        v = vmin + (vmax - vmin) * i / 4
        out.append(f"<line class='grid' x1='{MARGE['g']}' x2='{LARG - MARGE['d']}' "
                   f"y1='{y(v):.1f}' y2='{y(v):.1f}'/>"
                   f"<text class='tick' x='{MARGE['g'] - 6}' y='{y(v) + 4:.1f}' "
                   f"text-anchor='end'>{v:,.0f}</text>")
    annee_prec = None
    for d in dates:  # une graduation par année
        if d[:4] != annee_prec:
            annee_prec = d[:4]
            out.append(f"<text class='tick' x='{x(d):.1f}' y='{HAUT - 8}'>{d[:4]}</text>")
    for _, cls, pts in series:
        chemin_svg = " ".join(f"{x(d):.1f},{y(v):.1f}" for d, v in pts)
        out.append(f"<polyline class='ligne {cls}' points='{chemin_svg}'/>")
    out.append("</svg>")
    legende = "".join(f"<span class='leg'><i class='pastille {c}'></i>{escape(n)}</span>"
                      for n, c, _ in series)
    return "".join(out) + f"<div class='legende'>{legende}</div>"


def _pct(x):
    return f"{x * 100:+.2f} %"


def _tableau_metriques(r):
    m, b = r["metriques"], r["metriques_benchmark"]
    rg = m["ratio_gain_perte"]
    lignes = [
        ("Capital final", f"{m['capital_final']:,.0f} $", f"{b['capital_final']:,.0f} $"),
        ("Rendement total", _pct(m["rendement_total"]), _pct(b["rendement_total"])),
        ("Rendement annualisé", _pct(m["rendement_annualise"]), _pct(b["rendement_annualise"])),
        ("Drawdown maximum", _pct(m["drawdown_max"]), _pct(b["drawdown_max"])),
        ("Nombre de trades", str(m["nb_trades"]), "—"),
        ("Taux de réussite", f"{m['taux_reussite'] * 100:.1f} %", "—"),
        ("Gain moyen", f"{m['gain_moyen']:,.0f} $", "—"),
        ("Perte moyenne", f"{m['perte_moyenne']:,.0f} $", "—"),
        ("Ratio gain/perte", "n/a" if rg is None else f"{rg:.2f}", "—"),
    ]
    corps = "".join(f"<tr><th>{a}</th><td>{b_}</td><td>{c}</td></tr>" for a, b_, c in lignes)
    return ("<table><thead><tr><th></th><th>Trend-bot</th><th>SPY achat-conservation</th>"
            f"</tr></thead><tbody>{corps}</tbody></table>")


def _section_periode(titre, r):
    series = [("Trend-bot", "bot", r["courbe"]), ("SPY", "spy", r["courbe_benchmark"])]
    return (f"<section><h2>{escape(titre)} <span class='muted'>({r['debut']} → {r['fin']})"
            f"</span></h2>{_courbe_svg(series)}{_tableau_metriques(r)}</section>")


def _section_positions(cfg):
    f = chemin(cfg["sortie"]["etat_portefeuille"])
    if not f.exists():
        return ("<section><h2>Positions ouvertes (paper trading)</h2><p class='muted'>"
                "Aucun état de paper trading : lancez <code>python paper_trader.py</code>."
                "</p></section>")
    with open(f, encoding="utf-8") as fh:
        etat = json.load(fh)
    pos = etat["positions"]
    val = etat["cash"] + sum(p["quantite"] * p["dernier_prix"] for p in pos.values())
    if pos:
        lignes = ""
        for s, p in pos.items():
            lat = (p["dernier_prix"] - p["prix_entree"]) * p["quantite"]
            cls = "gain" if lat >= 0 else "perte"
            lignes += (f"<tr><th>{escape(s)}</th><td>{p['date_entree']}</td>"
                       f"<td>{p['quantite']}</td><td>{p['prix_entree']:.2f}</td>"
                       f"<td>{p['dernier_prix']:.2f}</td><td><b>{p['stop']:.2f}</b> "
                       f"<span class='muted'>({p['type_stop'].replace('_', ' ')})</span></td>"
                       f"<td class='{cls}'>{lat:+,.0f} $</td></tr>")
        tab = ("<table><thead><tr><th>Actif</th><th>Entrée</th><th>Qté</th><th>Prix entrée</th>"
               "<th>Dernier</th><th>Stop actif</th><th>Latent</th></tr></thead>"
               f"<tbody>{lignes}</tbody></table>")
    else:
        tab = "<p class='muted'>Aucune position ouverte.</p>"
    return (f"<section><h2>Positions ouvertes (paper trading)</h2>"
            f"<p>Capital : <b>{val:,.2f} $</b> · cash {etat['cash']:,.2f} $ · "
            f"dernière mise à jour : {etat['derniere_date']}</p>{tab}</section>")


def _section_journal(cfg):
    paper = journal.lire(chemin(cfg["sortie"]["journal_paper"]))
    source = "paper trading"
    if not paper:
        paper = journal.lire(chemin(cfg["sortie"]["dossier"]) / "journal_backtest_validation.csv")
        source = "backtest de validation (aucun trade en paper trading)"
    derniers = paper[-20:][::-1]
    if not derniers:
        return "<section><h2>20 derniers trades</h2><p class='muted'>Aucun trade.</p></section>"
    lignes = ""
    for t in derniers:
        g = float(t["gain_perte"])
        lignes += (f"<tr><td>{t['date_sortie']}</td><td>{escape(t['actif'])}</td>"
                   f"<td>{t['date_entree']}</td><td>{float(t['prix_entree']):.2f}</td>"
                   f"<td>{float(t['prix_sortie']):.2f}</td><td>{t['quantite']}</td>"
                   f"<td>{t['raison_sortie'].replace('_', ' ')}</td>"
                   f"<td class='{'gain' if g >= 0 else 'perte'}'>{g:+,.0f} $</td></tr>")
    return (f"<section><h2>20 derniers trades <span class='muted'>({source})</span></h2>"
            "<table><thead><tr><th>Sortie</th><th>Actif</th><th>Entrée</th><th>Prix entrée</th>"
            "<th>Prix sortie</th><th>Qté</th><th>Raison</th><th>Gain/perte</th></tr></thead>"
            f"<tbody>{lignes}</tbody></table></section>")


def _section_paper_perf(cfg):
    """Performance du paper trading (si au moins 2 points de courbe)."""
    f = chemin(cfg["sortie"]["etat_portefeuille"])
    if not f.exists():
        return ""
    with open(f, encoding="utf-8") as fh:
        etat = json.load(fh)
    if len(etat["courbe"]) < 2:
        return ""
    trades = [{"gain_perte": float(t["gain_perte"])}
              for t in journal.lire(chemin(cfg["sortie"]["journal_paper"]))]
    m = calculer_metriques(etat["courbe"], trades, etat["capital_initial"])
    return (f"<section><h2>Paper trading en cours</h2>{_courbe_svg([('Trend-bot (paper)', 'bot', etat['courbe'])])}"
            f"<p>Rendement : <b>{_pct(m['rendement_total'])}</b> · drawdown max : "
            f"<b>{_pct(m['drawdown_max'])}</b> · trades clôturés : {m['nb_trades']}</p></section>")


CSS = """
:root{--fond:#fff;--texte:#1a1d23;--doux:#6b7280;--bord:#e3e6ec;--carte:#f7f8fa;
--bot:#2563eb;--spy:#d97706;--gain:#15803d;--perte:#b91c1c;}
@media (prefers-color-scheme:dark){:root{--fond:#0f1218;--texte:#e6e8ee;--doux:#9aa3b2;
--bord:#2a303c;--carte:#171b24;--bot:#60a5fa;--spy:#fbbf24;--gain:#4ade80;--perte:#f87171;}}
body{margin:0;background:var(--fond);color:var(--texte);font:15px/1.5 system-ui,sans-serif}
main{max-width:820px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:8px 0}h2{font-size:1.1rem;margin:0 0 10px}
section{background:var(--carte);border:1px solid var(--bord);border-radius:10px;
padding:16px;margin:16px 0;overflow-x:auto}
.muted{color:var(--doux);font-weight:400}
.avert{border:1px solid var(--perte);color:var(--perte);padding:10px;border-radius:8px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--bord);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}tbody th{font-weight:600;text-align:left}
.chart{width:100%;height:auto}.grid{stroke:var(--bord)}.tick{fill:var(--doux);font-size:11px}
.ligne{fill:none;stroke-width:2}.ligne.bot{stroke:var(--bot)}.ligne.spy{stroke:var(--spy)}
.legende{display:flex;gap:16px;margin:4px 0 12px}.pastille{display:inline-block;width:10px;
height:10px;border-radius:50%;margin-right:6px}.pastille.bot{background:var(--bot)}
.pastille.spy{background:var(--spy)}.gain{color:var(--gain)}.perte{color:var(--perte)}
"""


def generer(cfg=None):
    """Construit le fichier HTML à partir des résultats de backtest et de l'état."""
    cfg = cfg or charger_config()
    parties = []
    f = chemin(cfg["sortie"]["resultats_backtest"])
    avert = ""
    if f.exists():
        with open(f, encoding="utf-8") as fh:
            res = json.load(fh)
        if res.get("synthetique"):
            avert = ("<p class='avert'><b>Attention :</b> ce backtest utilise des données "
                     "synthétiques (test technique). Ces chiffres n'ont aucune valeur "
                     "financière.</p>")
        noms = {"entrainement": "Entraînement", "validation": "Validation (période non vue)"}
        for cle, r in res["periodes"].items():
            parties.append(_section_periode(noms.get(cle, cle), r))
        gen = f"Backtest généré le {res['genere_le']}"
    else:
        parties.append("<section><p class='muted'>Aucun backtest : lancez "
                       "<code>python backtest.py</code>.</p></section>")
        gen = "Pas de backtest"
    corps = (_section_paper_perf(cfg) + _section_positions(cfg) + "".join(parties)
             + _section_journal(cfg))
    html = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Trend-bot Dashboard</title><style>{CSS}</style></head><body><main>"
            f"<h1>Trend-bot <span class='muted'>· paper trading</span></h1>"
            f"<p class='muted'>{gen}</p>{avert}{corps}</main></body></html>")
    sortie = chemin(cfg["sortie"]["dashboard"])
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(html, encoding="utf-8")
    return sortie


if __name__ == "__main__":
    print(f"Tableau de bord généré : {generer()}")
