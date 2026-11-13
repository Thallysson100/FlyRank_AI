"""Build the GitHub Pages version of the capstone paper into docs/.

Reads the notebook outputs in work/outputs/capstone/ (results JSON, tables, figures, PDF) and writes:
    docs/index.html                 the web version of the paper
    docs/capstone_paper.pdf         the full PDF (built by work/build_capstone_pdf.py)
    docs/assets/fig*.png            the figures
    docs/.nojekyll                  serve files as-is (no Jekyll processing)

Usage:
    python work/build_capstone_pdf.py      # first, so the PDF is current
    python work/build_paper_site.py
Then enable Pages: Settings -> Pages -> Deploy from a branch -> main, /docs.
"""
from __future__ import annotations

import csv
import html
import json
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "outputs" / "capstone"
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"

REPO_URL = "https://github.com/Thallysson100/FlyRank_AI"
NOTEBOOK_URL = f"{REPO_URL}/blob/main/work/notebooks/capstone.ipynb"
COLAB_URL = "https://colab.research.google.com/github/Thallysson100/FlyRank_AI/blob/main/work/notebooks/capstone.ipynb"
DATA_URL = "https://huggingface.co/datasets/FlyRank/internship-warehouse"
FLYRANK_URL = "https://flyrank.ai"
FIGS = ["fig01_label_base_rate.png", "fig02_test_ranking_quality.png", "fig03_test_metrics_bar.png",
        "fig04_permutation_importance.png", "fig05_live_queue_actions.png"]


def esc(s) -> str:
    return html.escape(str(s))


def pct(x, d=0) -> str:
    return f"{100 * float(x):.{d}f}%"


def f3(x) -> str:
    return f"{float(x):.3f}"


def num(x) -> str:
    return f"{int(round(float(x))):,}"


def ext(url: str, label: str | None = None) -> str:
    """External link: always opens in a new tab."""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label or url)}</a>'


def table(header: list[str], rows: list[list], highlight: tuple = ()) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in header)
    trs = []
    for i, r in enumerate(rows):
        cls = ' class="hl"' if i in highlight else ""
        trs.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    return f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def fig(name: str, caption: str) -> str:
    return (f'<figure><a href="assets/{name}" target="_blank" rel="noopener"><img src="assets/{name}" '
            f'alt="{esc(caption)}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>')


def read_csv(name: str) -> list[dict]:
    with open(SRC / "tables" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_html(R: dict) -> str:
    test = {r["model"]: r for r in R["test"]["table"]}
    M, MI = test["model — probability"], test["model — expected impact"]
    B0, B2 = test["B0 volume rule (w04)"], test["B2 site-relative momentum rule"]
    gap, ci = R["test"]["prauc_gap_vs_B2"]["mean"], R["test"]["prauc_gap_vs_B2"]["ci95"]
    rob = {r["model"]: r for r in R["robustness"]["table"]}
    L, DC, LK, SP, lim, cfg = R["label"], R["data_counts"], R["leakage_checks"], R["split_rows"], R["limitations"], R["config"]
    base = R["test"]["base_rate"]
    bt_a = {r["action"]: r for r in R["queue_backtest"]["by_action"]}
    live = R["live_queue"]
    label_rows = read_csv("label_base_rate_by_month.csv")
    abs_rates = [float(r["base_rate_absolute"]) for r in label_rows]
    rel_rates = [float(r["base_rate_site_relative"]) for r in label_rows if int(r["clients"]) > 1]
    queue_lost = sum(r["share_of_lost_impressions"] for a, r in bt_a.items() if a not in ("MONITOR", "EXPAND - opportunity"))

    abstract = (
        "Content teams can review only a handful of pages per cycle, so this work asks which visible pages are most "
        "likely to fall clearly behind their own site's search visibility next month. "
        f"Using the FlyRank pseudonymized warehouse release ({DC['fact_daily_rows'] / 1e6:.1f}M daily rows, "
        f"{DC['date_min']} to {DC['date_max']}), I built a page × month-end panel whose features use only the three months "
        "before each decision date, and labelled a page as declining when its next-month daily impressions fell more than "
        "20% below the median page of the same site — a site-relative label that removes the site-wide shocks which made an "
        f"absolute label {pct(L['test_month_base_rate_absolute'])} positive in the test month. "
        "A histogram gradient-boosting model was compared with transparent rules on a time-aware split (trained on past "
        f"months, selected on {cfg['val_label_month']}, evaluated once on a sealed {cfg['test_label_month']} month), with "
        "leakage checks and a never-seen-client check. "
        f"On {num(R['test']['rows'])} test pages (base rate {pct(base, 1)}) the model reached PR-AUC {f3(M['PR-AUC'])} versus "
        f"{f3(B2['PR-AUC'])} for the best momentum rule (+{gap:.3f}, 95% client-bootstrap CI +{ci[0]:.3f} to +{ci[1]:.3f}), "
        f"and ordering the same score by visibility at stake covered {pct(MI['lost_imp_captured@top10%'])} of site-relative "
        f"lost impressions in 10% of pages, although the gain over the rule shrinks to "
        f"+{lim['unseen_client_prauc_gap_vs_B2']:.3f} on never-seen clients. "
        "The result is a reason-coded review queue (protect, refresh, metadata, prune/merge, expand, monitor) meant as "
        "decision support for human editors; it does not show that refreshing a page causes recovery."
    )

    order = ["model — probability", "model — expected impact", "B2 site-relative momentum rule", "B1 momentum rule",
             "B0 volume rule (w04)"]
    results_tbl = table(
        ["Ranking", "PR-AUC", "ROC-AUC", "Precision in top 10%", "Lift top 10%", "Lost impressions in top 10%"],
        [[esc(n), f3(test[n]["PR-AUC"]), f3(test[n]["ROC-AUC"]), pct(test[n]["P@top10%"], 1),
          f"{test[n]['lift@top10%']:.2f}×", pct(test[n]["lost_imp_captured@top10%"], 1)] for n in order], highlight=(0,))
    robust_tbl = table(["Variant (sealed test)", "PR-AUC", "ROC-AUC", "Precision top 10%"],
                       [[esc(r["model"]), f3(r["PR-AUC"]), f3(r["ROC-AUC"]), pct(r["P@top10%"], 1)]
                        for r in R["robustness"]["table"]])
    split_tbl = table(["Role", "Label months", "Rows", "Used for"], [
        ["train (selection)", "2025-05 … 2026-04", num(SP["train_selection"]), "fit candidates"],
        ["validation", cfg["val_label_month"], num(SP["validation"]), "choose model + settings"],
        ["train (final)", "2025-05 … 2026-05", num(SP["train_final"]), "refit chosen model once"],
        ["sealed test", cfg["test_label_month"], num(SP["test"]), "evaluated once"],
        ["live queue", "2026-07 (no outcome yet)", num(SP["live"]), "the recommendations"]], highlight=(3,))
    action_tbl = table(["Action", "Rule (pre-decision signals only)", "What the editor checks"], [
        ["<b>PROTECT</b> — page-one refresh", "avg position ≤ 10 and top-quartile visibility",
         "update facts and dates, strengthen the section matching the intent, check internal links; change little else"],
        ["<b>METADATA REVIEW</b>", "CTR fell while position held or improved", "title / description vs. query intent"],
        ["<b>PRUNE / MERGE REVIEW</b>", "bottom-quartile visibility and avg position &gt; 20", "stronger sibling page? merge or redirect"],
        ["<b>REFRESH</b> — content", "everything else in the queue", "content gaps, outdated sections, depth"],
        ["<b>EXPAND</b> — opportunity", "low risk, growing &gt; 20%, avg position 4–20", "add depth to reach page one"],
        ["<b>MONITOR</b>", "everything else", "no action this cycle"]])
    live_tbl = table(["Action", "Pages", "Median risk", "Median impressions/day", "Share of visibility at stake"],
                     [[esc(r["action"].replace(" - ", " — ")), num(r["pages"]), f"{r['median_risk']:.2f}",
                       f"{r['median_impressions_per_day']:.0f}", pct(r["share_of_visibility_at_stake"], 1)]
                      for r in live["action_summary"]])
    top = read_csv("live_queue_top20.csv")[:10]
    top_tbl = table(["#", "Page ID", "Action", "Risk", "Impr./day", "Pos.", "Reason codes"],
                    [[num(r["queue_rank"]), esc(r["page"]), esc(r["action"].split(" - ")[0]), f"{float(r['p_decline']):.2f}",
                      num(r["imp_per_day_90"]), f"{float(r['pos_90']):.1f}",
                      esc(r["reason_codes"].replace(";", ", ").replace("_", " ").lower())] for r in top])
    protect = bt_a["PROTECT - page-one refresh"]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Which pages should an editor review first?</title>
<meta name="description" content="FlyRank ML Internship capstone: a time-aware, site-relative decline-risk queue for content refresh.">
<style>
:root {{ --ink:#1f2a33; --muted:#5f6b73; --accent:#2f6db5; --accent-soft:#eaf1fa; --rule:#d5dce2; --zebra:#f6f8fa;
         --bg:#ffffff; --card:#ffffff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ink:#e6ebef; --muted:#9aa7b0; --accent:#7fb0ec; --accent-soft:#1c2a3a; --rule:#33404a; --zebra:#1a2229;
           --bg:#11171c; --card:#f4f6f8; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:17px/1.65 Georgia, "Times New Roman", serif; }}
main {{ max-width:880px; margin:0 auto; padding:40px 16px 64px; }}
h1, h2, h3, .meta, table, figcaption, .btn, .kpi, nav {{ font-family:-apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }}
h1 {{ font-size:2.1rem; line-height:1.2; margin:0 0 6px; }}
.sub {{ font-size:1.15rem; color:var(--muted); margin:0 0 14px; font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
.meta {{ color:var(--muted); font-size:.85rem; }}
h2 {{ color:var(--accent); font-size:1.35rem; margin:44px 0 10px; padding-top:8px; border-top:1px solid var(--rule); }}
h3 {{ font-size:1.05rem; margin:24px 0 6px; }}
a {{ color:var(--accent); }}
.abstract {{ background:var(--accent-soft); border-left:4px solid var(--accent); padding:16px 20px; border-radius:4px; }}
.btns {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 6px; }}
.btn {{ display:inline-block; padding:9px 16px; border-radius:6px; border:1px solid var(--accent); text-decoration:none;
        font-size:.9rem; font-weight:600; }}
.btn.primary {{ background:var(--accent); color:var(--bg); }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:12px; margin:22px 0; }}
.kpi {{ border:1px solid var(--rule); border-radius:8px; padding:12px 14px; }}
.kpi b {{ display:block; font-size:1.55rem; color:var(--accent); }}
.kpi span {{ font-size:.8rem; color:var(--muted); line-height:1.35; display:block; }}
.tbl {{ overflow-x:auto; margin:12px 0 18px; }}
table {{ border-collapse:collapse; width:100%; font-size:.82rem; line-height:1.4; }}
th {{ background:var(--accent); color:var(--bg); text-align:left; padding:6px 8px; white-space:nowrap; }}
td {{ padding:5px 8px; border-bottom:1px solid var(--rule); vertical-align:top; }}
tbody tr:nth-child(even) td {{ background:var(--zebra); }}
tr.hl td {{ background:var(--accent-soft) !important; font-weight:600; }}
figure {{ margin:22px 0; }}
figure img {{ width:100%; height:auto; background:var(--card); border:1px solid var(--rule); border-radius:4px; padding:6px; }}
figcaption {{ font-size:.8rem; color:var(--muted); margin-top:6px; line-height:1.45; }}
nav {{ font-size:.85rem; margin:18px 0; color:var(--muted); }}
nav a {{ margin-right:12px; white-space:nowrap; }}
.pdf {{ width:100%; height:80vh; border:1px solid var(--rule); border-radius:4px; }}
ul {{ padding-left:22px; }} li {{ margin:4px 0; }}
code {{ font-size:.85em; }}
pre {{ background:var(--zebra); padding:12px; border-radius:4px; overflow-x:auto; font-size:.8rem; line-height:1.5; }}
footer {{ margin-top:48px; font-size:.8rem; color:var(--muted); font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
@media (max-width:600px) {{ body {{ font-size:16px; }} h1 {{ font-size:1.6rem; }} }}
</style>
</head>
<body>
<main>
<header>
  <h1>Which pages should an editor review first?</h1>
  <p class="sub">A time-aware, site-relative decline-risk queue for content refresh</p>
  <p class="meta">FlyRank ML Internship capstone · Lane: Refresh / Content Opportunity Scoring · {date.today():%B %Y}</p>
  <div class="btns">
    <a class="btn primary" href="capstone_paper.pdf" target="_blank" rel="noopener">Read the full paper (PDF)</a>
    {ext(NOTEBOOK_URL, "Notebook").replace("<a ", '<a class="btn" ')}
    {ext(REPO_URL, "Repository").replace("<a ", '<a class="btn" ')}
  </div>
  <nav><a href="#abstract">Abstract</a><a href="#intro">Problem</a><a href="#data">Data</a><a href="#method">Methodology</a><a href="#results">Results</a><a href="#limits">Limitations</a><a href="#recs">Recommendations</a><a href="#repro">Reproducibility</a><a href="#ack">Data credit</a></nav>
</header>

<section id="abstract">
  <h2>Abstract</h2>
  <div class="abstract">{esc(abstract)}</div>
  <div class="kpis">
    <div class="kpi"><b>{f3(M['PR-AUC'])}</b><span>model PR-AUC on the sealed month (best rule: {f3(B2['PR-AUC'])})</span></div>
    <div class="kpi"><b>+{gap:.3f}</b><span>gap over the rule, 95% CI +{ci[0]:.3f} to +{ci[1]:.3f}</span></div>
    <div class="kpi"><b>{pct(MI['lost_imp_captured@top10%'])}</b><span>of lost impressions found in the top 10% of pages (impact ordering)</span></div>
    <div class="kpi"><b>+{lim['unseen_client_prauc_gap_vs_B2']:.3f}</b><span>gap on never-seen clients — the honest limit</span></div>
  </div>
</section>

<section id="intro">
  <h2>1. Introduction and problem statement</h2>
  <p>Every month some pages start losing search visibility, and an editor has a limited number of review hours. Reviewing in
  arbitrary order wastes hours on pages that are fine; missing a sliding page with real demand lets the loss continue. This work
  supports one recurring decision: <b>at the end of each month, which visible pages enter next month's review queue, in what
  order, with what suggested action and why.</b> In the last month of the panel there are {num(SP['live'])} eligible visible
  pages — far too many to review by hand.</p>
  <p>The unit of analysis is one page × one monthly decision date. The output is <b>decision support</b> for a human reviewer:
  not an automated edit, not a promise that a refresh recovers traffic, and not a statement about how search engines rank pages.</p>
</section>

<section id="data">
  <h2>2. Data</h2>
  <p>FlyRank pseudonymized warehouse release <i>{esc(R['release'])}</i> ({ext(DATA_URL, 'Hugging Face, gated')}), queried in place
  with DuckDB. Tables used: <code>dim_clients</code> ({num(DC['dim_clients'])} rows), <code>dim_content</code>
  ({num(DC['dim_content'])}) and <code>fact_content_daily_performance</code> ({num(DC['fact_daily_rows'])} daily rows,
  {DC['date_min']} → {DC['date_max']}), reduced once to 2.87M page-month rows. The query table was <b>not</b> used: its fixed
  window overlaps the test month. A grain probe found <b>{num(DC['exact_duplicate_rows_dropped'])} exact duplicate rows</b> in the
  June-2026 partition (the test month); they were dropped.</p>
  <p><b>Exclusions, and why:</b></p>
  <ul>
    <li>Only {R['clients']['with_impressions']} of {DC['dim_clients']} clients ever record a search impression; the client must be tracked in all four months involved, so "no impressions" never means "no tracking".</li>
    <li>Impressions in each of the three feature months, and ≥ {cfg['min_impressions_feature_window']} in total (≥ 100/month), so a 20% drop is not noise.</li>
    <li>Pages at least {cfg['min_page_age_days']} days old (young pages are still ramping up).</li>
    <li>Pages deleted by export time ({pct(L['deleted_share_of_labelled_rows'], 2)} of labelled rows): their drop is removal, not decay.</li>
    <li>Sites with fewer than 20 eligible pages in a month (the site median would be unstable).</li>
  </ul>
  <p>All identifiers are pseudonymized; no client names, domains, URLs, titles or queries appear anywhere in this work.</p>
</section>

<section id="method">
  <h2>3. Methodology</h2>
  <h3>Label: site-relative decline</h3>
  <p>The first label — "next-month daily impressions more than 20% below the page's 3-month average" — measured the whole panel,
  not the page: panel impressions slid from {L['daily_impressions_early_april'] / 1e6:.1f}M/day (early April) to
  {L['daily_impressions_late_june'] / 1e6:.1f}M/day (late June 2026), so {pct(L['test_month_base_rate_absolute'])} of test pages
  would have "declined". The final label marks a page as declining when its ratio is <b>below 0.80 × the median ratio of the
  eligible pages of the same site in the same month</b>. Across months the absolute label swings between {pct(min(abs_rates))}
  and {pct(max(abs_rates))}; the site-relative label stays between {pct(min(rel_rates))} and {pct(max(rel_rates))}.</p>
  {fig(FIGS[0], "Figure 1 — Left: share of eligible pages labelled declining per month (grey: rejected absolute label; blue: final site-relative label). Right: panel impressions per day, April–June 2026.")}
  <h3>Features, baselines and models</h3>
  <p>Features use only the three months before the decision date: visibility level, momentum (last month vs. 3-month average,
  month-over-month, second half vs. whole last month, volatility), position and CTR (level and change), persistence, GA4
  engagement (only where GA4 data is available), site context (site momentum, page momentum relative to its site) and page
  metadata. Excluded on purpose: pseudonymous IDs, update/optimisation dates (export-time, often after the panel), deletion
  status, generation metadata and anything from the label month.</p>
  <p>Baselines: <b>B0</b> my week-4 volume rule; <b>B1</b> page momentum; <b>B2</b> page momentum relative to its site — the
  strongest simple rule. Models: logistic regression and histogram gradient boosting in scikit-learn pipelines fitted on training
  months only; selected: <i>{esc(R['model_selection']['selected'])}</i>. Seed {R['seed']}; reruns are bit-identical.</p>
  <h3>Validation design</h3>
  {split_tbl}
  <p><b>Leakage checks</b> (all passed): forbidden columns absent; every feature month precedes its label month; the strongest
  single feature reaches ROC-AUC {LK['max_single_feature_auc']:.3f} alone ({esc(LK['top_single_feature'])}, a momentum signal);
  models trained on shuffled labels score {LK['shuffled_label_val_auc_mean']:.3f} on average (chance). A stricter check groups
  by client on top of the time split to test never-seen sites.</p>
</section>

<section id="results">
  <h2>4. Results</h2>
  <p>Sealed test, {cfg['test_label_month']}: {num(R['test']['rows'])} pages, base rate {pct(base, 1)}, same pages for every ranking.</p>
  {results_tbl}
  <p>The model's probability ranking reaches PR-AUC <b>{f3(M['PR-AUC'])}</b> / ROC-AUC <b>{f3(M['ROC-AUC'])}</b> vs
  {f3(B2['PR-AUC'])} / {f3(B2['ROC-AUC'])} for B2: a gap of <b>+{gap:.3f} (95% client-bootstrap CI +{ci[0]:.3f} to +{ci[1]:.3f})</b>,
  positive in every resample. Ordering the same score by visibility at stake puts {pct(MI['lost_imp_captured@top10%'])} of all
  site-relative lost impressions in the top 10% of pages. My earlier volume rule ranks worse than chance for site-relative decline
  (ROC-AUC {f3(B0['ROC-AUC'])}) — big pages are less likely to fall behind their site — yet it still finds high-stake pages.</p>
  {fig(FIGS[2], "Figure 2 — Sealed test: model rankings vs transparent baselines on the same pages.")}
  {fig(FIGS[1], "Figure 3 — Precision–recall curves; share of lost impressions covered as pages are reviewed in queue order; observed decline by score decile.")}
  <h3>Robustness</h3>
  {robust_tbl}
  <p>On never-seen clients the gain over B2 shrinks to +{lim['unseen_client_prauc_gap_vs_B2']:.3f}: much of the edge comes from
  having seen a site's earlier months. Without export-time page metadata the result barely moves. The model beats B2 at every
  decline threshold tested (0.7×, 0.8×, 0.9× the site median).</p>
  {fig(FIGS[3], "Figure 4 — Permutation importance on the sealed month: the score is mostly a momentum score (page vs. site trend, late-month slide). Observed associations, not ranking factors.")}
</section>

<section id="limits">
  <h2>5. Limitations and honest framing</h2>
  <p>All claims here are <b>observed, measured, directional and decision-support</b>. What this work cannot say:</p>
  <ul>
    <li><b>No causality:</b> nothing shows that refreshing a flagged page causes recovery — that needs an experiment.</li>
    <li><b>No search-engine claims:</b> the drivers are associations in this data, mostly momentum.</li>
    <li><b>One test month</b> with a strong panel-wide drop; other seasons could differ.</li>
    <li><b>Unbalanced panel:</b> {lim['clients_in_training']} eligible clients, one of them {pct(lim['largest_client_share_of_test_rows'])} of test rows; on never-seen sites the model barely beats the rule.</li>
    <li><b>The label is a definition</b> and ignores site-wide drops by design — those need a separate site-level monitor.</li>
    <li><b>Calibration:</b> scores rank well but are not exact probabilities when the base rate shifts.</li>
    <li><b>Sudden collapses</b> with no warning in the feature window ({pct(R['error_analysis']['largest200_losses_in_bottom_half'])} of the 200 largest losses) cannot be caught by a monthly score.</li>
  </ul>
</section>

<section id="recs">
  <h2>6. Ranked recommendations — the action playbook</h2>
  <p>Pages in the top 30% of risk enter the queue (confidence <i>high</i> = top 10%), ordered by visibility at stake
  (risk × daily impressions); the first matching rule sets the action.</p>
  {action_tbl}
  <p><b>Back-test on the sealed month:</b> the queue (30% of pages) held about {pct(queue_lost)} of all site-relative lost
  impressions; PROTECT pages alone held {pct(protect['share_of_lost_impressions'])}, and {pct(protect['observed_decline'])} of them
  really fell behind. Pages tagged EXPAND declined only {pct(bt_a['EXPAND - opportunity']['observed_decline'])} of the time.</p>
  <h3>The live queue (decision date {esc(live['decision_date'])}, for July 2026)</h3>
  {live_tbl}
  {fig(FIGS[4], "Figure 5 — Live queue: pages per action and share of visibility at stake.")}
  {top_tbl}
  <p class="meta">Top 10 of {num(live['pages_in_queue'])} queued pages. Shortened pseudonymous page IDs only; no client identifiers.</p>
  <ul>
    <li>Each month, score every visible page and publish the queue.</li>
    <li>Review PROTECT pages first: page-one pages losing ground faster than their site. Change as little as possible.</li>
    <li>Work through REFRESH pages as capacity allows; batch METADATA and PRUNE/MERGE reviews monthly.</li>
    <li>Hand EXPAND pages to content creators; treat site-wide drops separately.</li>
    <li>Log every change, so a later experiment can measure whether refreshes actually help.</li>
  </ul>
</section>

<section id="repro">
  <h2>7. Reproducibility</h2>
  <ul>
    <li>Repository: {ext(REPO_URL)}</li>
    <li>Capstone notebook: {ext(NOTEBOOK_URL, 'work/notebooks/capstone.ipynb')} · {ext(COLAB_URL, 'open in Colab')}</li>
    <li>Weekly notebooks it builds on: <code>work/notebooks/w01–w05</code></li>
    <li>Paper builders: <code>work/build_capstone_pdf.py</code> (PDF) and <code>work/build_paper_site.py</code> (this page)</li>
    <li>Full paper: <a href="capstone_paper.pdf" target="_blank" rel="noopener">capstone_paper.pdf</a></li>
  </ul>
<pre>python -m venv venv &amp;&amp; venv/bin/pip install -r requirements.txt duckdb ipykernel nbconvert
echo "HF_TOKEN=&lt;your read token&gt;" &gt; .env        # never committed
venv/bin/jupyter nbconvert --to notebook --execute --inplace work/notebooks/capstone.ipynb
venv/bin/python work/build_capstone_pdf.py &amp;&amp; venv/bin/python work/build_paper_site.py</pre>
  <p>Seed {R['seed']}; deterministic row order; the sealed-test metrics are committed in
  <code>work/outputs/capstone/capstone_results.json</code>.</p>
</section>

<section id="ack">
  <h2>8. Acknowledgments and data credit</h2>
  <p>Built on the {ext(FLYRANK_URL, 'FlyRank ML Internship dataset')}. Thanks to FlyRank for releasing real, pseudonymized
  search-performance data for research and learning.</p>
</section>

<footer>FlyRank ML Internship capstone · built from <code>work/outputs/capstone/</code> · {ext(FLYRANK_URL, 'flyrank.ai')}</footer>
</main>
</body>
</html>
"""


def main() -> None:
    R = json.loads((SRC / "capstone_results.json").read_text(encoding="utf-8"))
    pdf = SRC / "capstone_paper.pdf"
    if not pdf.exists():
        raise SystemExit("capstone_paper.pdf not found — run work/build_capstone_pdf.py first.")
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in FIGS:
        shutil.copy2(SRC / "figures" / name, ASSETS / name)
    shutil.copy2(pdf, DOCS / "capstone_paper.pdf")
    (DOCS / ".nojekyll").touch()
    (DOCS / "index.html").write_text(build_html(R), encoding="utf-8")
    print(f"wrote {DOCS / 'index.html'} (+ PDF, {len(FIGS)} figures, .nojekyll)")


if __name__ == "__main__":
    main()
