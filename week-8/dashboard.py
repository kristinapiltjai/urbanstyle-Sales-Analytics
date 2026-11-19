"""
dashboard.py
------------
Streamlit dashboard — Urbanstyle müügikäive asukohtade lõikes.

Run with:
    streamlit run dashboard.py

Requires data_fetcher.py in the same folder and a valid .env with
SUPABASE_URL and SUPABASE_KEY.
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date, timedelta

from data_fetcher import fetch_table_data
from transform import add_store_location, calculate_kpis, clean_data, merge_datasets

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOCATIONS = ["Tallinn", "Tartu", "Pärnu", "Online"]

st.set_page_config(
    page_title="Urbanstyle müügikäive",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Urbanstyle müügikäive")
st.caption("Päevane käive asukohtade lõikes")


# ---------------------------------------------------------------------------
# Helper: previous Mon–Sun week
# ---------------------------------------------------------------------------
def previous_week_range():
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = prev_monday + timedelta(days=6)
    return prev_monday, prev_sunday


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

# Default period: last week of 2023 (Mon 25.12 – Sun 31.12)
default_start = date(2023, 12, 25)
default_end = date(2023, 12, 31)

st.sidebar.header("Filtrid")

prev_mon, prev_sun = previous_week_range()

start_date = st.sidebar.date_input(
    "Alguskuupäev",
    value=prev_mon,
    help="Eelmine esmaspäev vaikimisi",
)
end_date = st.sidebar.date_input(
    "Lõppkuupäev",
    value=prev_sun,
    help="Eelmine pühapäev vaikimisi",
)

selected_locations = st.sidebar.multiselect(
    "Asukohad",
    options=LOCATIONS,
    default=LOCATIONS,
)

if start_date > end_date:
    st.sidebar.error("Alguskuupäev peab olema enne lõppkuupäeva.")
    st.stop()

if not selected_locations:
    st.sidebar.warning("Vali vähemalt üks asukoht.")
    st.stop()


# ---------------------------------------------------------------------------
# Data — cached so Supabase isn't re-queried on every widget interaction.
# Cache expires after 10 minutes.
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="Laen andmeid Supabase'ist…")
def load_data(start: date, end: date):
    # +1 day so sales with a time on the end date are included
    raw_sales = fetch_table_data(
        "sales",
        start_date=start.isoformat(),
        end_date=(end + timedelta(days=1)).isoformat(),
    )
    sales = clean_data(raw_sales)
    if sales.empty:
        return pd.DataFrame()

    sales = sales[sales["sale_date"] < pd.Timestamp(end + timedelta(days=1))]
    customers = clean_data(fetch_table_data("customers"))

    df = add_store_location(merge_datasets(sales, customers), LOCATIONS)
    if not df.empty:
        df["day"] = df["sale_date"].dt.normalize()
    return df


df = load_data(start_date, end_date)

if df.empty:
    st.warning("Valitud perioodil andmed puuduvad.")
    st.stop()

# Apply location filter
df = df[df["store_location"].isin(selected_locations)]

if df.empty:
    st.warning("Valitud asukohti ei leitud andmetes.")
    st.stop()


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
daily = (
    df.groupby(["day", "store_location"])["total_price"]
    .sum()
    .reset_index(name="käive")
    .sort_values("day")
)

# One invoice = one order (same rule as transform.calculate_kpis)
summary = (
    df.groupby("store_location")
    .agg(tellimusi=("invoice_id", "nunique"), käive=("total_price", "sum"))
    .sort_values("käive", ascending=False)
)
summary["keskmine"] = summary["käive"] / summary["tellimusi"]
summary = summary.round(0).astype(int)


# ---------------------------------------------------------------------------
# KPI strip (from transform.calculate_kpis)
# ---------------------------------------------------------------------------
kpis = calculate_kpis(df)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Kokku käive", f"{kpis['total_revenue']:,.0f} EUR")
k2.metric("Tellimusi", f"{kpis['total_orders']:,}")
k3.metric("Keskmine tellimus", f"{kpis['avg_order_value']:,.2f} EUR")
k4.metric("Unikaalseid kliente", f"{kpis['unique_customers']:,}")

st.divider()


# ---------------------------------------------------------------------------
# Line chart — daily revenue per location
# ---------------------------------------------------------------------------
fig = px.line(
    daily,
    x="day",
    y="käive",
    color="store_location",
    markers=True,
    category_orders={"store_location": LOCATIONS},
    title=f"Päevane käive asukohtade lõikes ({start_date:%d.%m.%Y} – {end_date:%d.%m.%Y})",
    labels={
        "day": "Kuupäev",
        "käive": "Käive (EUR)",
        "store_location": "Asukoht",
    },
)
fig.update_layout(
    hovermode="x unified",
    yaxis_tickformat=",.0f",
    legend_title_text="Asukoht",
)
fig.update_traces(hovertemplate="%{y:,.0f} EUR")

st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
st.subheader("Kokkuvõte asukohtade lõikes")
st.dataframe(
    summary.rename(
        columns={
            "tellimusi": "Tellimusi",
            "käive": "Käive (EUR)",
            "keskmine": "Keskmine (EUR)",
        }
    ),
    use_container_width=True,
)

st.caption(f"Andmed uuendatud: {date.today():%d.%m.%Y} | Allikas: Supabase")
