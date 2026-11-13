"""Build the capstone research paper as a PDF from the notebook outputs.

Reads only what `work/notebooks/capstone.ipynb` wrote to `work/outputs/capstone/`
(capstone_results.json, tables/*.csv, figures/*.png) — no data access, no model fitting —
so every number in the PDF traces back to the notebook run.

Usage (from the repo root or anywhere):
    python work/build_capstone_pdf.py
    python work/build_capstone_pdf.py --out work/outputs/capstone/capstone_paper.pdf --author "Your Name"
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, ListFlowable, ListItem,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs" / "capstone"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"

REPO_URL = "https://github.com/Thallysson100/FlyRank_AI"
NOTEBOOK_URL = f"{REPO_URL}/blob/main/work/notebooks/capstone.ipynb"
COLAB_URL = ("https://colab.research.google.com/github/Thallysson100/FlyRank_AI/blob/main/"
             "work/notebooks/capstone.ipynb")
SCRIPT_URL = f"{REPO_URL}/blob/main/work/build_capstone_pdf.py"
DATA_URL = "https://huggingface.co/datasets/FlyRank/internship-warehouse"
FLYRANK_URL = "https://flyrank.ai"

# ------------------------------------------------------------------ style
PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 2.0 * cm, 2.0 * cm, 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_X

INK = colors.HexColor("#1F2A33")
MUTED = colors.HexColor("#5F6B73")
ACCENT = colors.HexColor("#2F6DB5")
ACCENT_LIGHT = colors.HexColor("#EAF1FA")
ORANGE = colors.HexColor("#E08A2E")
RULE = colors.HexColor("#D5DCE2")
ZEBRA = colors.HexColor("#F6F8FA")

BODY_FONT, BODY_BOLD, BODY_ITALIC = "Times-Roman", "Times-Bold", "Times-Italic"
SANS, SANS_BOLD = "Helvetica", "Helvetica-Bold"

S = {
    "title": ParagraphStyle("title", fontName=SANS_BOLD, fontSize=19, leading=23, textColor=INK,
                            alignment=TA_CENTER, spaceAfter=8),
    "subtitle": ParagraphStyle("subtitle", fontName=SANS, fontSize=10, leading=13, textColor=MUTED,
                               alignment=TA_CENTER, spaceAfter=2),
    "h1": ParagraphStyle("h1", fontName=SANS_BOLD, fontSize=13.5, leading=17, textColor=ACCENT,
                         spaceBefore=14, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName=SANS_BOLD, fontSize=11, leading=14, textColor=INK,
                         spaceBefore=9, spaceAfter=4),
    "body_left": ParagraphStyle("body_left", fontName=BODY_FONT, fontSize=10.5, leading=14.2, textColor=INK,
                                spaceAfter=6),
    "body": ParagraphStyle("body", fontName=BODY_FONT, fontSize=10.5, leading=14.2, textColor=INK,
                           alignment=TA_JUSTIFY, spaceAfter=6),
    "abstract": ParagraphStyle("abstract", fontName=BODY_FONT, fontSize=10.5, leading=14.5, textColor=INK,
                               alignment=TA_JUSTIFY),
    "bullet": ParagraphStyle("bullet", fontName=BODY_FONT, fontSize=10.5, leading=14, textColor=INK),
    "caption": ParagraphStyle("caption", fontName=SANS, fontSize=8.3, leading=10.5, textColor=MUTED,
                              spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName=SANS, fontSize=8, leading=9.8, textColor=INK),
    "cell_b": ParagraphStyle("cell_b", fontName=SANS_BOLD, fontSize=8, leading=9.8, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.3, leading=10.5, textColor=INK,
                           backColor=ZEBRA, borderPadding=5, spaceBefore=4, spaceAfter=8),
    "note": ParagraphStyle("note", fontName=SANS, fontSize=8.5, leading=11, textColor=MUTED),
}

# The built-in PDF fonts only cover WinAnsi; map the few symbols outside it.
_GLYPHS = {"≥": ">=", "≤": "<=", "→": "to", "−": "-", "≈": "~", "✓": "yes", "★": "*"}


def clean(text: str) -> str:
    for k, v in _GLYPHS.items():
        text = text.replace(k, v)
    return text


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(clean(text), S[style])


def link(url: str, label: str | None = None) -> str:
    return f'<link href="{url}" color="#2F6DB5"><u>{label or url}</u></link>'


def bullets(items: list[str], style: str = "bullet") -> ListFlowable:
    return ListFlowable([ListItem(P(t, style), leftIndent=12, value="circle") for t in items],
                        bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8, spaceBefore=2,
                        spaceAfter=6)


class Group(list):
    """Flowables that must stay on one page. Not a flowable itself: `layout()` turns each group
    (plus a heading before it and a caption after it) into ONE flat KeepTogether — nested
    KeepTogether blocks misbehave in reportlab and leave headings stranded."""


def table(header: list[str], rows: list[list], widths: list[float], highlight_rows: tuple = (),
          keep: bool = True):
    """Styled table. Short tables (keep=True) never split across pages; long ones split with a repeated header."""
    data = [[Paragraph(clean(h), S["cell_b"]) for h in header]]
    for r in rows:
        data.append([c if not isinstance(c, str) else Paragraph(clean(c), S["cell"]) for c in r])
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1, hAlign="LEFT")
    st = [("BACKGROUND", (0, 0), (-1, 0), ACCENT),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    for i in highlight_rows:
        st.append(("BACKGROUND", (0, i + 1), (-1, i + 1), ACCENT_LIGHT))
    t.setStyle(TableStyle(st))
    return Group([t]) if keep else t


def figure(name: str, caption: str, width: float = 1.0) -> "Group":
    path = FIG_DIR / name
    img = Image(str(path))
    w = CONTENT_W * width
    img.drawHeight = img.drawHeight * w / img.drawWidth
    img.drawWidth = w
    return Group([img, P(caption, "caption")])


def callout(text: str) -> Table:
    t = Table([[P(text, "abstract")]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_LIGHT),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def action_label(a: str) -> str:
    return a.replace(" - ", " — ")


def read_csv(name: str) -> list[dict]:
    with open(TAB_DIR / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f3(x) -> str:
    return f"{float(x):.3f}"


def pct(x, d: int = 0) -> str:
    return f"{100 * float(x):.{d}f}%"


def num(x) -> str:
    return f"{int(round(float(x))):,}"


# ------------------------------------------------------------------ content
def build_story(R: dict, author: str) -> list:
    test = {r["model"]: r for r in R["test"]["table"]}
    M, MI = test["model — probability"], test["model — expected impact"]
    B0, B1, B2 = test["B0 volume rule (w04)"], test["B1 momentum rule"], test["B2 site-relative momentum rule"]
    gap, ci = R["test"]["prauc_gap_vs_B2"]["mean"], R["test"]["prauc_gap_vs_B2"]["ci95"]
    rgap, rci = R["test"]["rocauc_gap_vs_B2"]["mean"], R["test"]["rocauc_gap_vs_B2"]["ci95"]
    rob = {r["model"]: r for r in R["robustness"]["table"]}
    unseen = rob["model — probability, unseen clients"]
    nometa = rob["model — probability, no dim_content metadata"]
    L, DC, LK, SP = R["label"], R["data_counts"], R["leakage_checks"], R["split_rows"]
    lim, cfg = R["limitations"], R["config"]
    bt_k = {r["queue_top_k"]: r for r in R["queue_backtest"]["by_k"]}
    bt_a = {r["action"]: r for r in R["queue_backtest"]["by_action"]}
    live = {r["action"]: r for r in R["live_queue"]["action_summary"]}
    base = R["test"]["base_rate"]
    label_rows = read_csv("label_base_rate_by_month.csv")
    abs_rates = [float(r["base_rate_absolute"]) for r in label_rows]
    rel_rates_2026 = [float(r["base_rate_site_relative"]) for r in label_rows if int(r["clients"]) > 1]
    protect_share_pages = bt_a["PROTECT - page-one refresh"]["pages"] / R["test"]["rows"]
    queue_lost = sum(bt_a[a]["share_of_lost_impressions"] for a in bt_a if a not in ("MONITOR", "EXPAND - opportunity"))

    story: list = []

    # ---------------- title + abstract
    story += [
        Spacer(1, 6),
        P("Which pages should an editor review first?", "title"),
        P("A time-aware, site-relative decline-risk queue for content refresh", "subtitle"),
        Spacer(1, 4),
        P(f"{author} &nbsp;·&nbsp; FlyRank ML Internship capstone &nbsp;·&nbsp; Lane: Refresh / Content "
          "Opportunity Scoring", "subtitle"),
        P(f"{date.today():%d %B %Y}", "subtitle"),
        P(f"Data: FlyRank pseudonymized warehouse release <i>{R['release']}</i>", "subtitle"),
        Spacer(1, 12),
        P("Abstract", "h2"),
    ]
    abstract = (
        "Content teams can review only a handful of pages per cycle, so this work asks which visible pages are "
        "most likely to fall clearly behind their own site's search visibility next month. "
        f"Using the FlyRank pseudonymized warehouse release ({DC['fact_daily_rows'] / 1e6:.1f}M daily rows, "
        f"{DC['date_min']} to {DC['date_max']}), I built a page × month-end panel whose features use only the three "
        "months before each decision date, and labelled a page as declining when its next-month daily impressions "
        "fell more than 20% below the median page of the same site — a site-relative label that removes the "
        f"site-wide shocks which made an absolute label {pct(L['test_month_base_rate_absolute'])} positive in the "
        "test month. "
        "A histogram gradient-boosting model was compared with transparent rules on a time-aware split (trained on "
        f"past months, selected on {cfg['val_label_month']}, evaluated once on a sealed {cfg['test_label_month']} "
        "month), with leakage checks and a never-seen-client check. "
        f"On {num(R['test']['rows'])} test pages (base rate {pct(base, 1)}) the model reached PR-AUC {f3(M['PR-AUC'])} "
        f"versus {f3(B2['PR-AUC'])} for the best momentum rule (+{gap:.3f}, 95% client-bootstrap CI +{ci[0]:.3f} to "
        f"+{ci[1]:.3f}), and ordering the same score by visibility at stake covered "
        f"{pct(MI['lost_imp_captured@top10%'])} of site-relative lost impressions in 10% of pages, although the gain "
        f"over the rule shrinks to +{lim['unseen_client_prauc_gap_vs_B2']:.3f} on never-seen clients. "
        "The result is a reason-coded review queue (protect, refresh, metadata, prune/merge, expand, monitor) meant as "
        "decision support for human editors; it does not show that refreshing a page causes recovery."
    )
    story += [callout(abstract), Spacer(1, 10), P("Key findings", "h2"), bullets([
        f"An absolute \"down 20%\" label swings between {pct(min(abs_rates))} and {pct(max(abs_rates))} across months "
        f"with site-wide shocks; the site-relative label stays between {pct(min(rel_rates_2026))} and "
        f"{pct(max(rel_rates_2026))}.",
        f"Sealed test: model PR-AUC {f3(M['PR-AUC'])} / ROC-AUC {f3(M['ROC-AUC'])} vs {f3(B2['PR-AUC'])} / "
        f"{f3(B2['ROC-AUC'])} for the site-relative momentum rule — a modest, bootstrap-verified gain.",
        f"Ordering by expected visibility at stake: the top 10% of pages hold {pct(MI['lost_imp_captured@top10%'])} "
        f"of site-relative lost impressions (volume rule {pct(B0['lost_imp_captured@top10%'])}, momentum rule "
        f"{pct(B2['lost_imp_captured@top10%'])}).",
        f"Honest limit: on clients the model never saw, the gain over the rule is only "
        f"+{lim['unseen_client_prauc_gap_vs_B2']:.3f} PR-AUC.",
        f"Negative result: my earlier volume rule ranks <i>worse than chance</i> for site-relative decline "
        f"(ROC-AUC {f3(B0['ROC-AUC'])}) — big pages are less likely to fall behind their site.",
    ])]

    # ---------------- 1. introduction
    story += [
        P("1. Introduction and problem statement", "h1"),
        P("FlyRank-managed sites publish and maintain many thousands of pages. Every month some of them start losing "
          "search visibility, and an editor has a limited number of review hours to decide which pages to open first "
          "and what to do with them. Reviewing pages in arbitrary order wastes those hours on pages that are fine; "
          "missing a sliding page that still has real demand lets the loss continue."),
        P(f"This work supports one recurring decision: <b>at the end of each month, which visible pages enter next "
          f"month's review queue, in what order, with what suggested action and why.</b> In the final month of the "
          f"panel there are {num(R['split_rows']['live'])} eligible visible pages — far too many to review by hand, which "
          f"is the case for a ranked queue."),
        table(["Design item", "Choice"], [
            ["Unit of analysis", "one content page × one monthly decision date T (last day of a month)"],
            ["Prediction", "P(page's next-month daily impressions fall > 20% below the median page of its own site)"],
            ["Output", "ranked queue + suggested action + reason codes + confidence label"],
            ["Cost of a false positive", "review time spent on a page that was fine"],
            ["Cost of a false negative", "a sliding page with real demand is not reviewed; the loss continues"],
            ["Capacity assumption", "a reviewer handles ~20–2,000 pages per cycle, so precision at the top of the queue matters"],
        ], [0.27, 0.73]),
        Spacer(1, 6),
        P("The output is <b>decision support</b>: a prioritised list for a human reviewer. It is not an automated edit, "
          "it does not claim that a refresh will recover traffic, and it says nothing about how search engines rank "
          "pages."),
    ]

    # ---------------- 2. data
    funnel = {r["step"]: r for r in read_csv("eligibility_funnel.csv")}
    fm = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
    story += [
        P("2. Data", "h1"),
        P(f"<b>Release.</b> FlyRank pseudonymized warehouse release, build <i>{R['release']}</i> "
          f"({link(DATA_URL, 'Hugging Face, gated')}), queried in place with DuckDB over <font face='Courier'>hf://</font> "
          f"Parquet. Daily facts run from {DC['date_min']} to {DC['date_max']}. All identifiers are pseudonymized "
          "hashes; no client names, domains, URLs, titles or queries are present in the release or in this paper.",
          "body_left"),
        table(["Table", "Grain", "Rows", "Used for"], [
            ["dim_clients", "one row per client", num(DC["dim_clients"]), "tracking coverage cross-check"],
            ["dim_content", "one row per content item", num(DC["dim_content"]), "page age, content type, keyword metadata"],
            ["fact_content_daily_performance", "day × client × content (18 monthly partitions)",
             num(DC["fact_daily_rows"]), "all visibility, position, CTR and GA4 features; labels"],
            ["fact_content_query_90d", "client × content × query (fixed 90-day window)", "2,414,248",
             "<b>not used</b> — its window overlaps the test month and exists for one date only"],
        ], [0.31, 0.25, 0.11, 0.33]),
        Spacer(1, 6),
        P("<b>Processing.</b> Each monthly partition was read once and reduced inside DuckDB to one row per page per "
          f"month (2.87M page-month rows), then cached locally. A grain probe on (report_date, content) found "
          f"<b>{num(DC['exact_duplicate_rows_dropped'])} exact duplicate daily rows</b> in the June-2026 partition — the "
          "sealed test month — which were dropped; the cache reconciles exactly with the published row counts. "
          "Position is the impression-weighted average; GA4 metrics are summed only on rows where "
          "<font face='Courier'>ga4_data_available IS TRUE</font>, so zero-filled rows before a client's GA4 start are "
          "never read as \"no engagement\"."),
        P("<b>Exclusions and why.</b> A page enters the panel at a decision date only if every condition below holds; "
          "the table shows how many pages survive each step."),
        bullets([
            f"{R['clients']['with_impressions']} of {DC['dim_clients']} clients ever record a search impression; the others cannot "
            "enter a search study. The client must have impressions in all four months involved (three feature months + "
            "label month), so \"no impressions\" never means \"no tracking\".",
            "Impressions in each of the three feature months (persistence, not a one-off blip).",
            f"At least {cfg['min_impressions_feature_window']} impressions in the feature window (≥ 100 per month), so a "
            "20% drop is not pure noise.",
            f"Page created at least {cfg['min_page_age_days']} days before the decision date (young pages are still ramping up).",
            f"Pages deleted by export time ({pct(L['deleted_share_of_labelled_rows'], 2)} of labelled rows) are removed: "
            "their drop reflects removal, not decay. This is a population definition, never a feature.",
            "Sites with fewer than 20 eligible pages in a month (the site median would be unstable).",
        ]),
        table(["Eligibility step"] + fm[:-1] + ["2026-07 (live)"],
              [[k] + [num(funnel[k][m]) for m in fm] for k in funnel], [0.32] + [0.136] * 5),
        P("Table 1 — Eligibility funnel for the last five decision dates (pages surviving each successive filter, "
          "before the deletion and site-size filters).", "caption"),
        P(f"The panel is unbalanced in time: fewer than 32 clients per month before Nov-2025, and "
          f"{pct(lim['share_training_rows_from_nov2025_on'])} of training rows come from Nov-2025 onward. The final "
          f"modelling set has {num(L['modelling_rows_labelled'])} labelled page × date rows and "
          f"{num(L['live_rows'])} live rows for the July-2026 queue."),
    ]

    # ---------------- 3. methodology
    story += [
        CondPageBreak(6 * cm),
        P("3. Methodology", "h1"),
        P("3.1 Label definition — and why the first version was rejected", "h2"),
        P("For page <i>p</i> and label month <i>L</i>, let <i>r</i> be its label-month daily impressions divided by its "
          "daily average over the three preceding months. The first label, \"declining if <i>r</i> &lt; 0.80\", turned "
          f"out to measure the whole panel rather than the page: panel impressions slid from "
          f"{L['daily_impressions_early_april'] / 1e6:.1f}M/day in early April to {L['daily_impressions_late_june'] / 1e6:.1f}M/day "
          f"in late June 2026 and most large clients dropped together, so {pct(L['test_month_base_rate_absolute'])} of "
          "test-month pages would have been \"declining\". Whether that shock is seasonality, a SERP change or a measurement "
          "change cannot be told from this data — but it is not something a page-level refresh can address."),
        callout("<b>Final label (site-relative decline).</b> A page is labelled <i>declining</i> in month L when "
                "<i>r</i>(p, L) &lt; 0.80 × median of <i>r</i>(q, L) over the eligible pages q of the same site in the "
                "same month. It keeps page-specific movement and removes site-wide and seasonal movement. The label "
                "uses other pages' future outcomes, which is allowed for a label and never for a feature."),
        Spacer(1, 8),
        figure("fig01_label_base_rate.png",
               "Figure 1 — Left: share of eligible pages labelled declining per label month under the rejected absolute "
               "label (grey) and the final site-relative label (blue); shaded: validation and sealed test months. "
               "Right: panel impressions per day, April–June 2026 (7-day mean)."),
        P("3.2 Features", "h2"),
        P("All features are computed from the three months before the decision date. Ratio features are per day so 28- "
          "and 31-day months compare fairly; missing values stay missing (with explicit flags) because missingness "
          "follows content type — feedly articles have no keyword data and about half the rows have no GA4 coverage."),
        table(["Group", "Features", "Why"], [
            ["Visibility level", "log impressions and log clicks over 90 days", "scale of exposure"],
            ["Momentum", "last month ÷ 3-month average; month-over-month ratios; 2nd half of last month ÷ whole last month; "
             "coefficient of variation", "is the page already sliding, and how noisy is it?"],
            ["Position & CTR", "impression-weighted position; position change; CTR; CTR change", "SERP standing, click capture"],
            ["Persistence", "share of days with ≥ 1 impression (last month, 90 days)", "steady vs. intermittent visibility"],
            ["Engagement (GA4)", "has-GA4 flag, sessions/day, engaged-session rate, organic share, any AI-referral sessions",
             "engagement context; NaN when not tracked"],
            ["Site context", "site momentum (last month ÷ 3-month avg, last ÷ first month), page momentum ÷ site momentum, "
             "site size", "separates site-wide from page-specific movement"],
            ["Page metadata", "age, content type, intent, competition level, word count, search volume, CPC, competition, "
             "backlinks, keyword tokens, category count", "page and target-keyword context"],
        ], [0.17, 0.53, 0.30]),
        Spacer(1, 6),
        P("<b>Excluded on purpose:</b> pseudonymous IDs (grouping and splitting only); content update and optimisation "
          "dates (latest value at export, often after the panel ends — future information); deletion and publication "
          "status (export-time); generation provider/model metadata; everything from the query table; anything computed "
          "from the label month."),
        P("3.3 Baselines", "h2"),
        bullets([
            "<b>B0 — volume rule</b> (my week-4 baseline): pages ≥ 90 days old with ≥ 500 impressions last month, ranked by "
            "log impressions.",
            "<b>B1 — momentum rule:</b> rank by how far last month fell below the page's 3-month average.",
            "<b>B2 — site-relative momentum rule:</b> rank by how far the page's momentum lags its own site's. The "
            "strongest simple rule found, and the real bar for the model.",
        ]),
        P("3.4 Models and validation design", "h2"),
        P("Candidates were scikit-learn pipelines fitted on training months only, so no transform ever sees validation "
          "or test rows: an L2 logistic regression (median imputation with missing-indicators, quantile-normal transform, "
          "one-hot categories) and histogram gradient boosting (native missing-value and categorical handling) over a "
          f"small grid. The selection metric was average precision (PR-AUC); selected: <i>{R['model_selection']['selected']}</i>. "
          f"Rows are sorted deterministically and every random component uses seed {R['seed']}, so reruns reproduce the "
          "numbers exactly."),
        table(["Role", "Label months", "Decision dates", "Rows", "Used for"], [
            ["train (selection)", "2025-05 … 2026-04", "≤ 2026-03-31", num(SP["train_selection"]), "fit candidates"],
            ["validation", cfg["val_label_month"], "2026-04-30", num(SP["validation"]), "choose model + settings"],
            ["train (final)", "2025-05 … 2026-05", "≤ 2026-04-30", num(SP["train_final"]), "refit chosen model once"],
            ["sealed test", cfg["test_label_month"], "2026-05-31", num(SP["test"]), "evaluated once"],
            ["live queue", "2026-07 (no outcome yet)", cfg["live_decision_date"], num(SP["live"]), "the recommendations"],
        ], [0.18, 0.22, 0.17, 0.13, 0.30], highlight_rows=(3,)),
        P("Table 2 — Time-aware split: train on the past, test on the future. A stricter check adds 5-fold grouping by "
          "client on top (never-seen sites).", "caption"),
        P("3.5 Leakage checks", "h2"),
        table(["Check", "Result"], [
            ["Forbidden columns (labels, IDs, export-time status, future dates) absent from features", "passed"],
            ["Every feature month precedes its label month", "passed (asserted for all rows)"],
            ["No single feature nearly encodes the label (training rows)",
             f"max single-feature ROC-AUC {LK['max_single_feature_auc']:.3f} ({LK['top_single_feature']}) — a momentum signal"],
            ["Model trained on shuffled labels scores at chance (6 seeds, validation)",
             f"mean ROC-AUC {LK['shuffled_label_val_auc_mean']:.3f} (range {LK['shuffled_label_val_auc_range'][0]:.2f}–"
             f"{LK['shuffled_label_val_auc_range'][1]:.2f})"],
            ["Test month untouched until the end", "selection on validation only; test scored once"],
        ], [0.62, 0.38]),
        Spacer(1, 6),
        P("A lesson carried over from the weekly notebooks: an earlier model used the impression threshold that defined "
          "label eligibility as a feature as well, so it could learn the eligibility rule itself and reported an inflated "
          "ROC-AUC of 0.995. Here eligibility filters the population and is never part of the label."),
    ]

    # ---------------- 4. results
    val = R["model_selection"]["validation_table"]
    val_best = val[0]
    val_logit = next(r for r in val if r["model"] == "logistic regression")
    val_b2 = next(r for r in val if r["model"].startswith("B2"))
    story += [
        P("4. Results", "h1"),
        P("4.1 Model selection (validation month)", "h2"),
        P(f"On {cfg['val_label_month']} all gradient-boosting settings landed within 0.005 PR-AUC of each other, so the "
          f"choice is not fragile. Boosting beat logistic regression ({f3(val_best['PR-AUC'])} vs {f3(val_logit['PR-AUC'])} "
          f"PR-AUC) and the best rule B2 ({f3(val_b2['PR-AUC'])}), so the non-linear model earns its complexity — modestly."),
        P("4.2 Sealed test month: model vs baselines on the same pages", "h2"),
    ]
    order = ["model — probability", "model — expected impact", "B2 site-relative momentum rule", "B1 momentum rule",
             "B0 volume rule (w04)"]
    story += [
        table(["Ranking", "PR-AUC", "ROC-AUC", "Precision in top 10%", "Lift top 10%", "Lost impressions in top 10%",
               "Site top-20 precision"],
              [[n, f3(test[n]["PR-AUC"]), f3(test[n]["ROC-AUC"]), pct(test[n]["P@top10%"], 1),
                f"{test[n]['lift@top10%']:.2f}×", pct(test[n]["lost_imp_captured@top10%"], 1),
                pct(test[n]["site_P@20_mean"], 1)] for n in order],
              [0.27, 0.09, 0.10, 0.14, 0.11, 0.16, 0.13], highlight_rows=(0,)),
        P(f"Table 3 — Sealed test, {cfg['test_label_month']}, {num(R['test']['rows'])} pages, base rate {pct(base, 1)}. "
          "\"Lost impressions\" = impressions lost relative to the site's typical page. Site top-20 precision = mean "
          "precision of each site's own top-20 list.", "caption"),
        P(f"The model's probability ranking reaches PR-AUC <b>{f3(M['PR-AUC'])}</b> and ROC-AUC <b>{f3(M['ROC-AUC'])}</b>, "
          f"against {f3(B2['PR-AUC'])} / {f3(B2['ROC-AUC'])} for B2. A cluster bootstrap over clients (300 resamples of "
          f"whole sites) puts the PR-AUC gap at <b>+{gap:.3f} (95% CI +{ci[0]:.3f} to +{ci[1]:.3f})</b>, positive in "
          f"{pct(R['test']['prauc_gap_vs_B2']['share_positive'])} of resamples; the ROC-AUC gap is +{rgap:.3f} "
          f"(+{rci[0]:.3f} to +{rci[1]:.3f}). Within the top 10% of the queue {pct(M['P@top10%'])} of pages really fell "
          f"behind their site — {M['lift@top10%']:.1f}× the base rate. Precision at very small K is high for every "
          "momentum-aware ranker (the top of any such list is pages already collapsing), so it does not separate the "
          "methods and is not the headline."),
        P(f"The <b>expected-impact</b> ordering (probability × current daily impressions) answers a different question: "
          f"its top 10% holds <b>{pct(MI['lost_imp_captured@top10%'])}</b> of all site-relative lost impressions, at "
          f"lower precision ({pct(MI['P@top10%'])}). Probability of decline and size of the loss are different "
          "questions; the playbook uses both."),
        figure("fig03_test_metrics_bar.png",
               "Figure 2 — Sealed test: model rankings vs transparent baselines on the same pages. Dashed lines: base "
               "rate (precision metrics) and a random reviewer (lost-impression coverage)."),
        figure("fig02_test_ranking_quality.png",
               "Figure 3 — Left: precision–recall curves. Centre: cumulative share of site-relative lost impressions "
               "covered as pages are reviewed in queue order. Right: observed decline rate and mean predicted probability "
               "by score decile."),
        P(f"The decile chart is cleanly monotone ({pct(R['test']['decile_observed_rate'][0], 1)} observed decline in the "
          f"lowest decile, {pct(R['test']['decile_observed_rate'][-1])} in the highest). The probabilities are not perfectly "
          f"calibrated for this month (mean predicted {lim['mean_predicted_vs_observed_test'][0]:.3f} vs observed "
          f"{lim['mean_predicted_vs_observed_test'][1]:.3f}), so the score is used as a ranking, not as a literal probability."),
        P("4.3 Robustness", "h2"),
        table(["Variant (sealed test)", "PR-AUC", "ROC-AUC", "Precision top 10%", "Site top-20 precision"],
              [[r["model"], f3(r["PR-AUC"]), f3(r["ROC-AUC"]), pct(r["P@top10%"], 1), pct(r["site_P@20_mean"], 1)]
               for r in R["robustness"]["table"]], [0.46, 0.12, 0.12, 0.15, 0.15]),
        P("Table 4 — Never-seen clients (5-fold grouping by client on top of the time split) and an ablation without "
          "export-time page metadata.", "caption"),
        bullets([
            f"<b>Never-seen sites:</b> PR-AUC falls from {f3(M['PR-AUC'])} to {f3(unseen['PR-AUC'])} — still above B2, but "
            f"the margin shrinks to +{lim['unseen_client_prauc_gap_vs_B2']:.3f}. Much of the edge comes from having seen "
            "a site's earlier months; for a brand-new client the simple rule is almost as good.",
            f"<b>No snapshot metadata:</b> PR-AUC {f3(M['PR-AUC'])} → {f3(nometa['PR-AUC'])}; the result does not hinge "
            "on export-time page fields.",
        ]),
    ]
    sens = R["sensitivity_threshold"]
    srows = []
    for thr in ["0.7 x site median", "0.8 x site median", "0.9 x site median"]:
        g = {r["model"]: r for r in sens if r["threshold"] == thr}
        srows.append([thr.replace(" x ", " × "), pct(g["model — probability"]["base_rate"], 1),
                      f3(g["model — probability"]["PR-AUC"]), f3(g["B2 site-relative momentum rule"]["PR-AUC"]),
                      f3(g["model — probability"]["ROC-AUC"]), f3(g["B2 site-relative momentum rule"]["ROC-AUC"])])
    story += [
        Group([
            table(["Decline threshold", "Base rate", "PR-AUC model", "PR-AUC B2", "ROC-AUC model", "ROC-AUC B2"], srows,
                  [0.24, 0.13, 0.16, 0.15, 0.16, 0.16], highlight_rows=(1,)),
            P("Table 5 — Sensitivity to the decline threshold (same fitted model and pages; only the label moves).",
              "caption")]),
        figure("fig04_permutation_importance.png",
               "Figure 4 — Permutation importance on the sealed test month (drop in PR-AUC when one feature is shuffled).",
               width=0.62),
        P("The score is overwhelmingly a <b>momentum</b> score: the page's last-month trend relative to its site, and "
          "whether the slide continued into the second half of the last month, dominate; CTR, site trend, persistence and "
          "visibility add small refinements. These are observed associations in this panel — what tends to continue — "
          "not statements about how search engines rank pages."),
    ]
    prof = read_csv("error_profile_top10.csv")
    bands = read_csv("error_by_position_band.csv")
    fp = next(r for r in prof if r[""].startswith("false"))
    tp = next(r for r in prof if r[""].startswith("true"))
    story += [
        P("4.4 Error analysis", "h2"),
        bullets([
            f"<b>Misses at the top.</b> {pct(R['error_analysis']['top10_false_positive_share'])} of the top-10% queue did "
            f"not fall behind ({num(fp['n'])} pages). Before the decision date they look almost identical to the hits "
            f"(same momentum, position, CTR) but recovered within the month (median {float(fp['label_ratio_vs_site (median)']):.2f}× "
            f"their site vs {float(tp['label_ratio_vs_site (median)']):.2f}× for hits) and are younger ({num(fp['age_days'])} vs "
            f"{num(tp['age_days'])} days). A dip followed by a rebound cannot be told apart from the start of a slide with "
            "monthly features — the reason a human stays in the loop.",
            "<b>Where it ranks best:</b> pages already on positions 1–10 — where a loss hurts most — with ROC-AUC "
            + ", ".join(f"{b['avg position band (feature window)']}: {f3(b['ROC-AUC model'])} (B2 {f3(b['ROC-AUC B2'])})"
                        for b in bands) + ". The model beats B2 in every band.",
            f"<b>Unannounced collapses:</b> {pct(R['error_analysis']['largest200_losses_in_bottom_half'])} of the 200 largest "
            "site-relative losses sat in the model's bottom half, with no warning in the feature window (and almost none "
            "were drops to zero, i.e. not removals). A monthly score cannot catch them; a weekly alert would.",
        ]),
    ]

    # ---------------- 5. limitations
    story += [
        P("5. Limitations and honest framing", "h1"),
        P("What this work <b>can</b> say: in this pseudonymized panel, at monthly decision dates, a gradient-boosted score "
          "built only from information available at the decision date <i>ranked</i> next-month site-relative decline "
          "better than transparent rules on a sealed future month, with a client-bootstrap interval that excludes zero. "
          "All claims are <b>observed, measured, directional and decision-support</b>."),
        P("What it <b>cannot</b> say:"),
        bullets([
            "<b>No causality.</b> Nothing here shows that refreshing a flagged page causes recovery; that needs an "
            "experiment (for example, refreshing a random half of flagged pages and comparing).",
            "<b>No claims about search-engine algorithms.</b> The drivers are associations in this data, mostly momentum.",
            f"<b>One test month.</b> {cfg['test_label_month']} is a single month with a strong panel-wide drop; results are "
            "consistent across thresholds and site resamples, but other seasons could differ.",
            f"<b>Unbalanced panel.</b> {lim['clients_in_training']} eligible clients; one client is "
            f"{pct(lim['largest_client_share_of_test_rows'])} of test rows; clients without search data are absent. On "
            f"never-seen sites the model barely beats the rule (+{lim['unseen_client_prauc_gap_vs_B2']:.3f} PR-AUC).",
            "<b>The label is a definition.</b> \"More than 20% behind the site median\" is a policy choice. By design this "
            "queue does not warn about a whole site dropping — that needs a separate site-level monitor.",
            "<b>Snapshot metadata and calibration.</b> Page metadata is as of export (the ablation shows it is not needed); "
            "scores rank well but are not exact probabilities when the base rate shifts.",
            "<b>Look-alikes not fully separated.</b> Consolidation into a sibling URL cannot be checked with the released "
            "fields at page level; seasonality is removed only insofar as it is shared across the site.",
        ]),
    ]

    # ---------------- 6. recommendations
    story += [
        CondPageBreak(8 * cm),
        P("6. Ranked recommendations — the action playbook", "h1"),
        P("<b>Queue policy</b> (fixed before scoring July and back-tested on the sealed June month): pages in the top 30% "
          "of risk score enter the queue (confidence <i>high</i> = top 10%, <i>medium</i> = 10–30%); the queue is ordered "
          "by visibility at stake = risk × current daily impressions; the first matching rule below sets the action."),
        table(["Action", "Rule (pre-decision signals only)", "What the editor checks"], [
            ["PROTECT — page-one refresh", "avg position ≤ 10 and top-quartile visibility",
             "update facts and dates, strengthen the section matching the main intent, check internal links; change little else"],
            ["METADATA REVIEW", "CTR fell while position held or improved", "title / description vs. query intent; snippet competitiveness"],
            ["PRUNE / MERGE REVIEW", "bottom-quartile visibility and avg position > 20", "is there a stronger sibling page? merge or redirect candidate"],
            ["REFRESH — content", "everything else in the queue", "content gaps, outdated sections, depth vs. competing pages"],
            ["EXPAND — opportunity", "outside the risk queue: low risk, growing > 20%, avg position 4–20", "add depth to push a growing page onto page one"],
            ["MONITOR", "everything else", "no action this cycle"],
        ], [0.24, 0.33, 0.43]),
        P("Table 6 — Actions. Reason codes attached to queued pages: SLIDING_VS_SITE, LATE_MONTH_SLIDE, POSITION_WORSENING, "
          "CTR_FALLING, PAGE_ONE, HIGH_VISIBILITY, LOW_VISIBILITY.", "caption"),
        P("6.1 Back-test on the sealed month", "h2"),
        table(["Queue top-K", "Precision", "Lift vs base rate", "Share of all lost impressions"],
              [[num(k), pct(r["precision"], 1), f"{r['lift_vs_base']:.2f}×", pct(r["share_of_all_lost_impressions"], 1)]
               for k, r in sorted(bt_k.items())], [0.25, 0.25, 0.25, 0.25]),
        Spacer(1, 4),
        table(["Action (June back-test)", "Pages", "Observed decline", "Share of lost impressions"],
              [[action_label(a), num(r["pages"]), pct(r["observed_decline"], 1), pct(r["share_of_lost_impressions"], 1)]
               for a, r in sorted(bt_a.items(), key=lambda kv: -kv[1]["share_of_lost_impressions"])],
              [0.4, 0.15, 0.2, 0.25]),
        P("Table 7 — The policy applied unchanged to June 2026 (model fitted on months up to May).", "caption"),
        P(f"The queue (30% of pages) held about <b>{pct(queue_lost)}</b> of all site-relative lost impressions. PROTECT "
          f"pages alone — {pct(protect_share_pages)} of pages — held <b>{pct(bt_a['PROTECT - page-one refresh']['share_of_lost_impressions'])}</b>, "
          f"and {pct(bt_a['PROTECT - page-one refresh']['observed_decline'])} of them really fell behind. Pages tagged EXPAND "
          f"declined only {pct(bt_a['EXPAND - opportunity']['observed_decline'])} of the time versus a {pct(base, 1)} base "
          "rate, so the \"safe to invest\" list is directionally sound. Ordering by visibility at stake trades some "
          f"precision ({pct(bt_k[20]['precision'])} at K = 20, {pct(bt_k[2000]['precision'])} at K = 2,000) for much more impact."),
        P(f"6.2 The live queue (decision date {R['live_queue']['decision_date']}, for July 2026)", "h2"),
        P(f"The chosen model was refit on every labelled month and scored {num(R['live_queue']['pages_scored'])} eligible "
          f"pages; {num(R['live_queue']['pages_in_queue'])} enter the queue."),
        table(["Action", "Pages", "Median risk score", "Median impressions / day", "Share of visibility at stake"],
              [[action_label(a), num(r["pages"]), f"{r['median_risk']:.2f}", f"{r['median_impressions_per_day']:.0f}",
                pct(r["share_of_visibility_at_stake"], 1)] for a, r in live.items()],
              [0.32, 0.12, 0.16, 0.2, 0.2]),
        Spacer(1, 6),
        figure("fig05_live_queue_actions.png",
               "Figure 5 — Live queue: pages per action and share of visibility at stake (risk × impressions per day)."),
    ]
    top20 = read_csv("live_queue_top20.csv")
    story += [
        P("Top of the live queue", "h2"),
        table(["#", "Page ID", "Action", "Confidence", "Risk", "Impr. / day", "Pos.", "Reason codes"],
                  [[num(r["queue_rank"]), r["page"], r["action"].split(" - ")[0], r["confidence"],
                    f"{float(r['p_decline']):.2f}", num(r["imp_per_day_90"]), f"{float(r['pos_90']):.1f}",
                    r["reason_codes"].replace(";", ", ").replace("_", " ").lower()] for r in top20],
              [0.04, 0.12, 0.11, 0.11, 0.06, 0.1, 0.06, 0.40], keep=False),
        P("Table 8 — Top 20 of the July-2026 queue. Shortened pseudonymous page IDs only; no client identifiers.",
          "caption"),
        P(f"The top 20 are all page-one, high-visibility pages that lagged their site in the last month, most with a slide "
          f"that continued into late June. The PROTECT bucket ({num(live['PROTECT - page-one refresh']['pages'])} pages) carries "
          f"{pct(live['PROTECT - page-one refresh']['share_of_visibility_at_stake'])} of all visibility at stake — this is where an "
          "editor's first hours should go."),
        P("The playbook in practice", "h2"),
        bullets([
            "Each month, after the month closes, score every visible page and publish the queue.",
            "Review PROTECT pages first, in queue order: page-one pages losing ground faster than their site. Change as "
            "little as possible; check freshness, intent match and internal links.",
            "Work through REFRESH pages as capacity allows; batch METADATA and PRUNE/MERGE reviews once a month.",
            "Hand EXPAND pages to whoever creates content: growing pages close to page one.",
            "Treat a site-wide drop separately — this queue deliberately ignores it.",
            "Log every change, so a later experiment can measure whether refreshes actually help.",
        ]),
    ]

    # ---------------- 7. reproducibility
    story += [
        P("7. Reproducibility", "h1"),
        bullets([
            f"Repository: {link(REPO_URL)}",
            f"Capstone notebook (mirrors this paper section by section): {link(NOTEBOOK_URL, 'work/notebooks/capstone.ipynb')} "
            f"&nbsp;·&nbsp; {link(COLAB_URL, 'open in Colab')}",
            f"Weekly notebooks it builds on: work/notebooks/w01–w05 in the same repository.",
            f"This PDF: {link(SCRIPT_URL, 'work/build_capstone_pdf.py')}, which reads only the notebook outputs.",
            f"Data: {link(DATA_URL, 'FlyRank/internship-warehouse')} (gated; free read token).",
        ]),
        P("From a fresh clone, with a Hugging Face read token in <font face='Courier'>.env</font> (never committed):"),
        P("python -m venv venv &amp;&amp; venv/bin/pip install -r requirements.txt duckdb ipykernel nbconvert<br/>"
          "venv/bin/jupyter nbconvert --to notebook --execute --inplace work/notebooks/capstone.ipynb<br/>"
          "venv/bin/python work/build_capstone_pdf.py", "code"),
        P(f"The first run scans the 18 monthly partitions once (about ten minutes) and caches them locally; later runs "
          f"read the cache. Seed {R['seed']} throughout; panel rows are sorted deterministically, so reruns give identical "
          "numbers. The sealed-test evidence is checkable from the repository: the notebook cell that builds the June frame, "
          "and <font face='Courier'>work/outputs/capstone/capstone_results.json</font> with the metrics it produced "
          "(<font face='Courier'>\"evaluated_once\": true</font>).", "body_left"),
    ]

    # ---------------- 8. acknowledgments
    story += [
        P("8. Acknowledgments and data credit", "h1"),
        P(f"Built on the {link(FLYRANK_URL, 'FlyRank ML Internship dataset')} ({link(FLYRANK_URL)}). Thanks to FlyRank for "
          "releasing real, pseudonymized search-performance data for research and learning. All identifiers in this "
          "work are pseudonymized; no client names, domains, URLs, page titles or search queries appear anywhere in it.",
          "body_left"),
    ]
    return layout(story)


def _flat(items) -> list:
    out = []
    for f in items:
        out.extend(_flat(f) if isinstance(f, Group) else [f])
    return out


def layout(story: list) -> list:
    """Glue captions to the group before them and headings to the block after them, without nesting."""
    units: list[tuple[bool, list]] = []                # (keep, flowables)
    for f in story:
        if isinstance(f, Group):
            units.append((True, _flat(f)))
        elif isinstance(f, Paragraph) and f.style.name == "caption" and units and units[-1][0]:
            units[-1][1].append(f)
        else:
            units.append((False, [f]))
    out: list = []
    i = 0
    while i < len(units):
        heads = []
        while (i + 1 < len(units) and not units[i][0] and isinstance(units[i][1][0], Paragraph)
               and units[i][1][0].style.name in ("h1", "h2")):
            heads.append(units[i][1][0]); i += 1
        keep, fl = units[i]
        splittable = not keep and isinstance(fl[0], Table)      # long tables flow across pages
        if keep or (heads and not splittable):
            out.append(KeepTogether(heads + fl))
        else:
            out.extend(heads + fl)
        i += 1
    return out


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, MARGIN_BOTTOM - 0.6 * cm, PAGE_W - MARGIN_X, MARGIN_BOTTOM - 0.6 * cm)
    canvas.setFont(SANS, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, MARGIN_BOTTOM - 1.0 * cm,
                      "Which pages should an editor review first? · FlyRank ML Internship capstone")
    canvas.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOTTOM - 1.0 * cm, f"{doc.page}")
    canvas.restoreState()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DIR / "capstone_paper.pdf"))
    ap.add_argument("--author", default="Thallysson100")
    args = ap.parse_args()

    results_path = OUT_DIR / "capstone_results.json"
    if not results_path.exists():
        raise SystemExit(f"{results_path} not found — run work/notebooks/capstone.ipynb first.")
    R = json.loads(results_path.read_text(encoding="utf-8"))
    missing = [p for p in ["fig01_label_base_rate.png", "fig02_test_ranking_quality.png", "fig03_test_metrics_bar.png",
                           "fig04_permutation_importance.png", "fig05_live_queue_actions.png"]
               if not (FIG_DIR / p).exists()]
    if missing:
        raise SystemExit(f"missing figures {missing} — rerun the notebook.")

    doc = BaseDocTemplate(args.out, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP,
                          bottomMargin=MARGIN_BOTTOM, title="Which pages should an editor review first?",
                          author=args.author, subject="FlyRank ML Internship capstone research paper",
                          keywords="content refresh, decline risk, decision support, FlyRank")
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="main")
    doc.addPageTemplates([PageTemplate(id="paper", frames=[frame], onPage=on_page)])
    doc.build(build_story(R, args.author))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
