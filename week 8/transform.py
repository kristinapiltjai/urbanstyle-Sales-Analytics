import pandas as pd
import logging

logger = logging.getLogger(__name__)  # seadistus (basicConfig) on pipeline.py-s


# 1. Puhastamine: duplikaadid, NULL-id, kuupäevad
def clean_data(df):
  if df.empty:
    logger.warning('[TRANSFORM] clean_data: sisend on tühi!')
    return df

  try:
    rows_before = len(df)
    df_clean = df.drop_duplicates().dropna(subset=['customer_id']).copy()
    df_clean['customer_id'] = df_clean['customer_id'].astype('int64')

    # Müügiandmed: vigane kuupäev välja, puuduv summa -> 0
    if 'sale_date' in df_clean.columns:
      df_clean['sale_date'] = pd.to_datetime(df_clean['sale_date'], errors='coerce')
      df_clean = df_clean.dropna(subset=['sale_date', 'invoice_id'])
      df_clean[['quantity', 'unit_price', 'total_price']] = (
          df_clean[['quantity', 'unit_price', 'total_price']].fillna(0)
      )

    # Kliendiandmed: kuupäev datetime'iks, puuduv tase -> 'none'
    if 'registration_date' in df_clean.columns:
      df_clean['registration_date'] = pd.to_datetime(
          df_clean['registration_date'], errors='coerce'
      )
      df_clean['loyalty_tier'] = df_clean['loyalty_tier'].fillna('none')

    logger.info(f'[TRANSFORM] clean_data: {rows_before} -> {len(df_clean)} rida')
    return df_clean.reset_index(drop=True)

  except Exception as e:
    logger.error(f'[TRANSFORM] clean_data ebaõnnestus: {e}')
    return pd.DataFrame()


# 2. Nädalased näitajad: tulu, tellimuste arv, keskmine tellimus
def calculate_weekly_aggregates(df):
  if df.empty:
    logger.warning('[TRANSFORM] calculate_weekly_aggregates: sisend on tühi!')
    return pd.DataFrame()

  try:
    weekly = (
        df.resample('W', on='sale_date')  # nädal lõpeb pühapäeval
        .agg(revenue=('total_price', 'sum'), orders=('invoice_id', 'nunique'))
        .reset_index()
        .rename(columns={'sale_date': 'week'})
    )
    weekly['avg_order_value'] = (weekly['revenue'] / weekly['orders']).fillna(0)
    weekly[['revenue', 'avg_order_value']] = weekly[['revenue', 'avg_order_value']].round(2)

    logger.info(f'[TRANSFORM] calculate_weekly_aggregates: {len(weekly)} nädalat')
    return weekly

  except Exception as e:
    logger.error(f'[TRANSFORM] calculate_weekly_aggregates ebaõnnestus: {e}')
    return pd.DataFrame()


# 3. KPI-d dict'ina
def calculate_kpis(df):
  if df.empty:
    logger.warning('[TRANSFORM] calculate_kpis: sisend on tühi!')
    return {}

  try:
    total_revenue = df['total_price'].sum()
    total_orders = df['invoice_id'].nunique()  # üks arve = üks tellimus

    kpis = {
        'period_start': df['sale_date'].min().strftime('%Y-%m-%d'),
        'period_end': df['sale_date'].max().strftime('%Y-%m-%d'),
        'total_revenue': round(float(total_revenue), 2),
        'total_orders': int(total_orders),
        'unique_customers': int(df['customer_id'].nunique()),
        'avg_order_value': round(float(total_revenue / total_orders), 2),
    }
    logger.info(f'[TRANSFORM] calculate_kpis: {kpis}')
    return kpis

  except Exception as e:
    logger.error(f'[TRANSFORM] calculate_kpis ebaõnnestus: {e}')
    return {}


# 4. Müük + kliendid customer_id järgi (left join, ükski müük ei kao)
def merge_datasets(df_sales, df_customers):
  if df_sales.empty or df_customers.empty:
    logger.warning('[TRANSFORM] merge_datasets: sisend on tühi!')
    return df_sales

  try:
    merged = pd.merge(df_sales, df_customers, on='customer_id', how='left')

    unmatched = merged['first_name'].isna().sum()
    if unmatched:
      logger.warning(f'[TRANSFORM] merge_datasets: {unmatched} rida ilma kliendita')

    logger.info(f'[TRANSFORM] merge_datasets: {len(merged)} rida')
    return merged

  except Exception as e:
    logger.error(f'[TRANSFORM] merge_datasets ebaõnnestus: {e}')
    return pd.DataFrame()


# 5. Testimine Supabase'i päris andmetega
if __name__ == '__main__':
  from data_fetcher import fetch_table_data

  logging.basicConfig(level=logging.INFO)  # et logid testis näha oleks

  print('=== TESTIME TRANSFORM FUNKTSIOONE ===\n')
  # Näidisandmed = üks kuu päris müüke Supabase'ist
  raw_sales = fetch_table_data('sales', start_date='2023-01-01', end_date='2023-01-31')
  raw_customers = fetch_table_data('customers')
  print(f'Laaditud: {len(raw_sales)} müüki, {len(raw_customers)} klienti\n')

  # Test 1: clean_data
  sales = clean_data(raw_sales)
  customers = clean_data(raw_customers)
  print('1) clean_data:\n', sales.head(), '\n')
  assert not sales.duplicated().any()
  assert sales['total_price'].isna().sum() == 0
  assert sales['sale_date'].dtype.kind == 'M'  # datetime

  # Test 2: calculate_weekly_aggregates
  weekly = calculate_weekly_aggregates(sales)
  print('2) calculate_weekly_aggregates:\n', weekly.tail(), '\n')
  assert round(weekly['revenue'].sum(), 2) == round(sales['total_price'].sum(), 2)

  # Test 3: calculate_kpis
  kpis = calculate_kpis(sales)
  print('3) calculate_kpis:', kpis, '\n')
  assert len(kpis) >= 3

  # Test 4: merge_datasets
  merged = merge_datasets(sales, customers)
  print('4) merge_datasets:\n', merged.head(), '\n')
  assert len(merged) == len(sales)  # left join ei muuda ridade arvu

  print('✅ Kõik testid läbitud!')