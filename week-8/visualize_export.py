"""
visualize_export.py
-------------------
Staatiline nädalaraport (eelmine E–P) Vercelisse.

Voog:  data_fetcher (Supabase)  ->  transform (puhastus + KPI-d)  ->  siin: graafikud + HTML

Tulemus kaustas output/:
  - weekly_report_YYYY-MM-DD.html   (kuupäev = nädala esmaspäev)
  - index.html                      (lingid kõikidele raportitele, uusim üleval)

Käivitamine:
  python3 visualize_export.py                     # eelmine E–P nädal
  python3 visualize_export.py --week 2024-12-23   # konkreetne nädal (mis tahes päev sellest nädalast)

pipeline.py kasutab samme eraldi (extract -> transform -> visualize -> export):
  extract_report_data, transform_report_data, create_report_figures, export_report
Kõik korraga: build_weekly_report()
"""

import argparse
import glob
import logging
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_fetcher import fetch_table_data
from transform import (
    add_store_location,
    calculate_kpis,
    calculate_weekly_aggregates,
    clean_data,
    merge_datasets,
)

logger = logging.getLogger(__name__)  # seadistus (basicConfig) on pipeline.py-s

# ---------------------------------------------------------------------------
# Seaded
# ---------------------------------------------------------------------------
# output/ alati skripti kõrval, sõltumata sellest, kust skripti käivitatakse
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
LOCATIONS = ["Tallinn", "Tartu", "Pärnu", "Online"]
TREND_WEEKS = 12  # mitu nädalat trendigraafikul (koos raporti nädalaga)
REPORT_PREFIX = "weekly_report_"
HTML_SUBDIR = "html"  # output/html/ – nädalaraportid (index.html jääb output/ juurde)
CSV_SUBDIR = "csv"  # output/csv/  – toorandmed (gitignore'd)
WEEKDAYS_ET = ["E", "T", "K", "N", "R", "L", "P"]


# ---------------------------------------------------------------------------
# Abifunktsioonid
# ---------------------------------------------------------------------------
def week_bounds(day):
    """Tagastab (esmaspäev, pühapäev) nädalale, kuhu `day` kuulub."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def previous_week(ref):
    """Tagastab (esmaspäev, pühapäev) nädalale enne `ref` nädalat."""
    return week_bounds(ref - timedelta(days=7))


def fmt_eur(value, decimals=2):
    """12345.6 -> '12 345,60 €' (Eesti vorming)."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + " €"


def fmt_int(value):
    return f"{int(value):,}".replace(",", " ")


def fetch_sales(start, end):
    """Pärib müügid [start, end] + 1 päev, et ka pühapäeva kellaajaga read tuleksid kaasa."""
    return fetch_table_data(
        "sales",
        start_date=start.isoformat(),
        end_date=(end + timedelta(days=1)).isoformat(),
    )


# ---------------------------------------------------------------------------
# 1. Andmed
# ---------------------------------------------------------------------------
def extract_report_data(week=None):
    """EXTRACT: pärib Supabasest raporti nädala + trendiperioodi müügid ja kliendid.

    Kui nädalat pole ette antud ja eelmisel nädalal andmeid pole (nt testandmed
    lõpevad 2024), võetakse viimane täisnädal, mis andmetes olemas on.

    Tagastab (raw_sales, raw_customers, week_start, week_end).
    raw_sales on tühi, kui andmeid pole.
    """
    week_start, week_end = week_bounds(week) if week else previous_week(date.today())
    trend_start = week_start - timedelta(weeks=TREND_WEEKS - 1)
    raw_sales = fetch_sales(trend_start, week_end)

    if raw_sales.empty and week is None:
        logger.warning(
            f"[REPORT] Nädalal {week_start} – {week_end} andmeid pole, "
            "otsin viimase täisnädala andmetes"
        )
        raw_sales = fetch_table_data("sales")
        if not raw_sales.empty:
            last_day = (
                pd.to_datetime(raw_sales["sale_date"], errors="coerce").max().date()
            )
            week_start, week_end = previous_week(last_day + timedelta(days=1))

    if raw_sales.empty:
        return raw_sales, pd.DataFrame(), week_start, week_end
    return raw_sales, fetch_table_data("customers"), week_start, week_end


def transform_report_data(raw_sales, raw_customers, week_start, week_end):
    """TRANSFORM: puhastab, liidab kliendid, lisab store_location ja lõikab perioodi.

    Tagastab df-i (trendiperiood kuni raporti nädala lõpuni) või tühja df-i.
    """
    sales = clean_data(raw_sales)
    if sales.empty:
        return pd.DataFrame()
    customers = clean_data(raw_customers)

    # Täpne periood (fetch võtab +1 päeva ja fallback võtab kõik andmed)
    trend_start = week_start - timedelta(weeks=TREND_WEEKS - 1)
    in_period = (sales["sale_date"] >= pd.Timestamp(trend_start)) & (
        sales["sale_date"] < pd.Timestamp(week_end + timedelta(days=1))
    )
    return add_store_location(merge_datasets(sales[in_period], customers), LOCATIONS)


def select_week_raw(raw_sales, week_start, week_end):
    """Raporti nädala (E 00:00 – P 23:59) toorread Supabasest, puhastamata.

    Veerud ja väärtused jäävad täpselt nii, nagu need tabelis on; ainult
    sorteeritakse kuupäeva järgi. Vigase kuupäevaga read jäävad välja,
    sest neid ei saa nädalasse paigutada.
    """
    ts = pd.to_datetime(raw_sales["sale_date"], errors="coerce")
    in_week = (ts >= pd.Timestamp(week_start)) & (
        ts < pd.Timestamp(week_end + timedelta(days=1))
    )
    return (
        raw_sales[in_week]
        .assign(_ts=ts[in_week])
        .sort_values("_ts", kind="stable")
        .drop(columns="_ts")
        .reset_index(drop=True)
    )


def load_report_data(week=None):
    """Extract + transform korraga. Tagastab (df, week_start, week_end) või (tühi df, None, None)."""
    raw_sales, raw_customers, week_start, week_end = extract_report_data(week)
    if raw_sales.empty:
        return pd.DataFrame(), None, None
    df = transform_report_data(raw_sales, raw_customers, week_start, week_end)
    if df.empty:
        return pd.DataFrame(), None, None
    return df, week_start, week_end


# ---------------------------------------------------------------------------
# 2. Graafikud
# ---------------------------------------------------------------------------
def chart_daily_by_location(week_df, week_start):
    """Päevane käive asukohtade lõikes (E–P, puuduvad päevad = 0)."""
    days = pd.date_range(week_start, periods=7, freq="D")
    daily = (
        week_df.assign(day=week_df["sale_date"].dt.normalize())
        .groupby(["day", "store_location"])["total_price"]
        .sum()
        .reindex(
            pd.MultiIndex.from_product(
                [days, LOCATIONS], names=["day", "store_location"]
            ),
            fill_value=0,
        )
        .reset_index(name="käive")
    )
    daily["päev"] = [f"{WEEKDAYS_ET[d.weekday()]} {d:%d.%m}" for d in daily["day"]]

    fig = px.line(
        daily,
        x="päev",
        y="käive",
        color="store_location",
        markers=True,
        category_orders={"store_location": LOCATIONS},
        title="Päevane käive asukohtade lõikes",
        labels={"päev": "Päev", "käive": "Käive (EUR)", "store_location": "Asukoht"},
    )
    fig.update_traces(hovertemplate="%{y:,.2f} €")
    fig.update_layout(hovermode="x unified", yaxis_tickformat=",.0f")
    return fig


def chart_location_totals(summary):
    """Nädala käive asukohtade kaupa (tulpdiagramm)."""
    fig = px.bar(
        summary.reset_index(),
        x="store_location",
        y="käive",
        color="store_location",
        text_auto=",.0f",
        category_orders={"store_location": LOCATIONS},
        title="Nädala käive asukohtade kaupa",
        labels={"store_location": "Asukoht", "käive": "Käive (EUR)"},
    )
    fig.update_layout(showlegend=False, yaxis_tickformat=",.0f")
    return fig


def create_weekly_chart(df_weekly, highlight_week=None):
    """Joondiagramm nädalasest käibest (calculate_weekly_aggregates väljund).

    df_weekly veerud: week (nädala lõpp, P), revenue, orders, avg_order_value.
    highlight_week: nädala pühapäev (date), mis märgitakse punasega (raporti nädal).
    """
    if df_weekly is None or df_weekly.empty:
        raise ValueError("create_weekly_chart: nädalaandmed on tühjad")

    fig = px.line(
        df_weekly,
        x="week",
        y="revenue",
        markers=True,
        hover_data={"orders": True, "avg_order_value": ":.2f"},
        title=f"Nädalane käive (viimased {len(df_weekly)} nädalat)",
        labels={
            "week": "Nädal (lõpp, P)",
            "revenue": "Käive (EUR)",
            "orders": "Tellimusi",
            "avg_order_value": "Keskmine tellimus (EUR)",
        },
    )
    fig.update_traces(line_color="#1d3557", name="Käive", showlegend=True)

    if highlight_week is not None:
        hl = df_weekly[df_weekly["week"].dt.date == highlight_week]
        if not hl.empty:
            fig.add_scatter(
                x=hl["week"],
                y=hl["revenue"],
                mode="markers",
                name="Raporti nädal",
                marker=dict(color="#e63946", size=14),
                hoverinfo="skip",
            )

    fig.update_layout(
        yaxis_tickformat=",.0f",
        xaxis_tickformat="%d.%m.%y",
        separators=", ",  # Eesti vorming: koma kümnendeks, tühik tuhandeteks
        legend=dict(orientation="h", y=1.1, x=1, xanchor="right"),
    )
    return fig


def create_kpi_summary(kpis):
    """Plotly indicator: 4 peamist KPI-d (calculate_kpis väljund) ühel joonisel."""
    if not kpis:
        raise ValueError("create_kpi_summary: KPI-d puuduvad")

    items = [
        ("Käive", kpis["total_revenue"], ",.2f", " €"),
        ("Tellimusi", kpis["total_orders"], ",.0f", ""),
        ("Keskmine tellimus", kpis["avg_order_value"], ",.2f", " €"),
        ("Unikaalseid kliente", kpis["unique_customers"], ",.0f", ""),
    ]
    fig = go.Figure()
    for i, (label, value, fmt, suffix) in enumerate(items):
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=value,
                title={"text": label, "font": {"size": 16}},
                number={"valueformat": fmt, "suffix": suffix, "font": {"size": 40}},
                domain={"row": 0, "column": i},
            )
        )

    start = date.fromisoformat(kpis["period_start"])
    end = date.fromisoformat(kpis["period_end"])
    fig.update_layout(
        grid={"rows": 1, "columns": len(items), "pattern": "independent"},
        title=f"Peamised KPI-d · {start:%d.%m.%Y} – {end:%d.%m.%Y}",
        separators=", ",
        height=260,
    )
    return fig


# ---------------------------------------------------------------------------
# 3. HTML
# ---------------------------------------------------------------------------
PAGE_CSS = """
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: #f5f6f8; color: #1d2433; }
  main { max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }
  a { color: #e63946; }
  h1 { margin: 0 0 4px; }
  .muted { color: #6b7280; margin: 0 0 24px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px; margin-bottom: 24px; }
  .card { background: #fff; border-radius: 10px; padding: 18px 20px;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .card .label { color: #6b7280; font-size: .9rem; }
  .card .value { font-size: 1.6rem; font-weight: 600; margin-top: 6px; }
  .chart { background: #fff; border-radius: 10px; padding: 8px; margin-bottom: 24px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  table { border-collapse: collapse; width: 100%; background: #fff; }
  th, td { padding: 10px 14px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f9fafb; }
  li { margin: 10px 0; font-size: 1.05rem; }
"""


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="et">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{PAGE_CSS}</style>
</head>
<body><main>
{body}
</main></body>
</html>"""


def build_report_html(kpis, summary, figs, week_start, week_end):
    period = f"{week_start:%d.%m.%Y} – {week_end:%d.%m.%Y}"
    week_no = week_start.isocalendar()[1]

    cards = [
        ("Käive", fmt_eur(kpis["total_revenue"])),
        ("Tellimusi", fmt_int(kpis["total_orders"])),
        ("Keskmine tellimus", fmt_eur(kpis["avg_order_value"])),
        ("Unikaalseid kliente", fmt_int(kpis["unique_customers"])),
    ]
    cards_html = "\n".join(
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in cards
    )

    # Plotly JS laetakse CDN-ist üks kord (esimese graafikuga) -> väike failimaht
    charts_html = "\n".join(
        f'<div class="chart">'
        f'{fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)}'
        f"</div>"
        for i, fig in enumerate(figs)
    )

    table = summary.reset_index().rename(
        columns={
            "store_location": "Asukoht",
            "tellimusi": "Tellimusi",
            "käive": "Käive",
            "keskmine": "Keskmine tellimus",
        }
    )
    table["Tellimusi"] = table["Tellimusi"].map(fmt_int)
    table["Käive"] = table["Käive"].map(fmt_eur)
    table["Keskmine tellimus"] = table["Keskmine tellimus"].map(fmt_eur)

    body = f"""
<p><a href="../index.html">← Kõik raportid</a></p>
<h1>🛍️ Urbanstyle nädalaraport – nädal {week_no}</h1>
<p class="muted">{period} · genereeritud {datetime.now():%d.%m.%Y %H:%M}</p>
<div class="kpis">{cards_html}</div>
{charts_html}
<h2>Kokkuvõte asukohtade lõikes</h2>
{table.to_html(index=False, border=0)}
"""
    return page(f"Urbanstyle nädalaraport {period}", body)


def write_file(path, write_fn, label):
    """Kirjutab faili turvaliselt üle: kõigepealt ajutisse faili, siis os.replace.

    Kui kirjutamine katkeb, jääb vana fail alles (pooleli faili ei teki).
    `write_fn(tmp_path)` kirjutab sisu. Tagastab True, kui fail oli juba olemas.
    """
    existed = os.path.exists(path)
    folder, name = os.path.split(path)
    tmp_path = os.path.join(folder, f".{name}.tmp")  # peidetud -> glob ei leia
    try:
        write_fn(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if existed:
        logger.info(f"[REPORT] {label} oli juba olemas -> üle kirjutatud: {path}")
    else:
        logger.info(f"[REPORT] {label} loodud: {path}")
    return existed


def write_text(path, text, label):
    def _write(tmp):
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)

    return write_file(path, _write, label)


# Ainult täpselt sellised nimed (nt "weekly_report_2024-12-23 (1).html" jääb välja)
REPORT_NAME_RE = re.compile(rf"^{REPORT_PREFIX}(\d{{4}}-\d{{2}}-\d{{2}})\.html$")


def write_index(output_dir=OUTPUT_DIR):
    """Koostab index.html uuesti kõikide output/html/ kaustas olevate raportite põhjal.

    Ehitatakse alati nullist, seega üle kirjutatud nädal on loendis üks kord
    ja näitab uut "uuendatud" aega. index.html jääb output/ juurkausta.
    """
    reports_dir = os.path.join(output_dir, HTML_SUBDIR)
    reports = {}  # nädala esmaspäev -> (failinimi, muutmisaeg)
    for path in glob.glob(os.path.join(reports_dir, f"{REPORT_PREFIX}*.html")):
        name = os.path.basename(path)
        match = REPORT_NAME_RE.match(name)
        if not match:
            logger.warning(f"[REPORT] index.html: jätan vahele tundmatu faili {name}")
            continue
        start = date.fromisoformat(match.group(1))
        reports[start] = (name, datetime.fromtimestamp(os.path.getmtime(path)))

    items = []
    for start in sorted(reports, reverse=True):
        name, updated = reports[start]
        end = start + timedelta(days=6)
        items.append(
            f'<li><a href="{HTML_SUBDIR}/{name}">Nädal {start.isocalendar()[1]}: '
            f"{start:%d.%m.%Y} – {end:%d.%m.%Y}</a> "
            f'<span class="muted">· uuendatud {updated:%d.%m.%Y %H:%M}</span></li>'
        )

    body = f"""
<h1>🛍️ Urbanstyle müügiraportid</h1>
<p class="muted">Nädalaraportid (E–P), uusim üleval</p>
<ul>{''.join(items) or '<li>Raporteid veel pole.</li>'}</ul>
"""
    index_path = os.path.join(output_dir, "index.html")
    write_text(index_path, page("Urbanstyle müügiraportid", body), "index.html")
    logger.info(f"[REPORT] index.html: {len(items)} raportit")
    return index_path


# ---------------------------------------------------------------------------
# 4. Põhifunktsioon
# ---------------------------------------------------------------------------
def create_report_figures(df, week_start, week_end):
    """VISUALIZE: arvutab nädala KPI-d, asukohtade kokkuvõtte ja 3 graafikut.

    Tagastab dict'i {kpis, summary, figs, weekly} või None, kui nädalal müüke pole.
    """
    week_df = df[df["sale_date"] >= pd.Timestamp(week_start)]
    if week_df.empty:
        logger.error(f"[REPORT] Nädalal {week_start} – {week_end} müüke pole")
        return None

    weekly = calculate_weekly_aggregates(df)
    summary = (
        week_df.groupby("store_location")
        .agg(tellimusi=("invoice_id", "nunique"), käive=("total_price", "sum"))
        .sort_values("käive", ascending=False)
    )
    summary["keskmine"] = summary["käive"] / summary["tellimusi"]

    return {
        "kpis": calculate_kpis(week_df),
        "summary": summary,
        "weekly": weekly,
        # nädalaraporti HTML-i graafikud (KPI-d on seal kaartidena)
        "figs": [
            chart_daily_by_location(week_df, week_start),
            chart_location_totals(summary),
            create_weekly_chart(weekly, highlight_week=week_end),
        ],
    }


def export_results(df, output_dir=OUTPUT_DIR, name="sales_raw"):
    """Salvestab DataFrame'i CSV-sse output/csv/ alamkausta, ajatempliga failinimega.

    df:     salvestatav DataFrame (pipeline'is raporti nädala toorandmed)
    Fail:   output/csv/<name>_YYYYMMDD_HHMMSS.csv
    Tagastab loodud faili tee.
    """
    csv_dir = os.path.join(output_dir, CSV_SUBDIR)
    os.makedirs(csv_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(csv_dir, f"{name}_{ts}.csv")
    df.to_csv(
        csv_path, index=False, encoding="utf-8-sig"
    )  # utf-8-sig: Excel + täpitähed
    logger.info(f"[EXPORT] CSV salvestatud: {csv_path} ({len(df)} rida)")
    return csv_path


def export_report(report, week_start, week_end, output_dir=OUTPUT_DIR):
    """EXPORT: salvestab raporti HTML-i output/html/ alamkausta ja ehitab index.html uuesti.

    Sama nädala fail kirjutatakse üle (failinimi = nädala esmaspäev).
    Tagastab (report_path, replaced).
    """
    reports_dir = os.path.join(output_dir, HTML_SUBDIR)
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"{REPORT_PREFIX}{week_start}.html")
    replaced = write_text(
        report_path,
        build_report_html(
            report["kpis"], report["summary"], report["figs"], week_start, week_end
        ),
        "Raport",
    )
    write_index(output_dir)
    return report_path, replaced


def build_weekly_report(week=None, output_dir=OUTPUT_DIR):
    """Kõik sammud korraga: extract -> transform -> visualize -> export.

    Kui selle nädala fail on juba olemas, kirjutatakse see üle ja index.html
    ehitatakse uuesti (nädal on loendis ikka üks kord, uue uuendamise ajaga).

    Tagastab dict'i {html, replaced, csv, kpis, week_start, week_end} või None.
    """
    # [EXTRACT] vajame raw_sales CSV jaoks, seepärast kutsume otse extract_report_data
    raw_sales, raw_customers, week_start, week_end = extract_report_data(week)
    if raw_sales.empty:
        logger.error("[REPORT] Andmed puuduvad, raportit ei koostatud")
        return None

    # [TRANSFORM]
    df = transform_report_data(raw_sales, raw_customers, week_start, week_end)
    if df.empty:
        logger.error("[REPORT] Transform tagastas tühja df-i, raportit ei koostatud")
        return None

    # [EXPORT CSV] nädala toorandmed output/csv/ kausta
    raw_week = select_week_raw(raw_sales, week_start, week_end)
    csv_path = export_results(
        raw_week, output_dir, name=f"sales_raw_{week_start:%Y-%m-%d}"
    )

    # [VISUALIZE + EXPORT HTML]
    report = create_report_figures(df, week_start, week_end)
    if report is None:
        return None

    report_path, replaced = export_report(report, week_start, week_end, output_dir)
    return {
        "html": report_path,
        "csv": csv_path,
        "replaced": replaced,
        "kpis": report["kpis"],
        "week_start": week_start,
        "week_end": week_end,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Urbanstyle nädalaraport (E–P)")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        help="Mis tahes päev soovitud nädalast, nt 2024-12-23 (vaikimisi eelmine nädal)",
    )
    args = parser.parse_args()

    result = build_weekly_report(args.week)
    if result:
        status = (
            "uuendatud (vana fail üle kirjutatud)" if result["replaced"] else "loodud"
        )
        print(f"✅ Raport {status}: {result['html']}")
        print(f"📄 CSV salvestatud: {result['csv']}")
    else:
        print("❌ Raportit ei koostatud (vaata logi)")
