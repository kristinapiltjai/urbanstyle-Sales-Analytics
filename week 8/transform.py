# transform.py — ETL Transform samm
# Sisend: data_fetcher.py DataFrame'id (sales, customers)

import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    weekly = weekly.round(2)

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


# 5. Testimine
if __name__ == '__main__':
  print('=== TESTIME TRANSFORM FUNKTSIOONE ===\n')

  # Näidisandmed (duplikaat, NULL-id, vigane kuupäev)
  sales = pd.DataFrame({
      'sale_id': [1, 2, 2, 3, 4, 5, 6, 7],
      'invoice_id': ['INV-1', 'INV-2', 'INV-2', 'INV-2', 'INV-3', 'INV-4',
                     'INV-5', 'INV-6'],
      'sale_date': ['2026-11-02', '2026-11-03', '2026-11-03', '2026-11-03',
                    '2026-11-10', '2026-11-11', '2026-11-12', 'vigane'],
      'customer_id': [101, 102, 102, 102, 101, 103, None, 104],
      'quantity': [2, 1, 1, 1, 1, 1, 1, 1],
      'unit_price': [50.0, 30.0, 30.0, 20.0, 80.0, 200.0, 30.0, 80.0],
      'total_price': [100.0, 30.0, 30.0, 20.0, None, 200.0, 30.0, 80.0],
  })
  customers = pd.DataFrame({
      'customer_id': [101, 102, 103],
      'first_name': ['Mari', 'Jaan', 'Eha'],
      'city': ['Tallinn', 'Tartu', 'Pärnu'],
      'registration_date': ['2024-02-27', None, '2021-02-03'],
      'loyalty_tier': [None, 'bronze', None],
  })

  # Test 1: clean_data
  clean = clean_data(sales)
  clean_cust = clean_data(customers)
  print('1) clean_data:\n', clean, '\n')
  assert len(clean) == 5  # duplikaat, NULL customer_id, vigane kuupäev välja
  assert clean['total_price'].isna().sum() == 0
  assert len(clean_cust) == 3  # puuduv registration_date ei kustuta klienti

  # Test 2: calculate_weekly_aggregates
  weekly = calculate_weekly_aggregates(clean)
  print('2) calculate_weekly_aggregates:\n', weekly, '\n')
  assert weekly['orders'].tolist() == [2, 2]  # INV-2 (2 rida) = 1 tellimus

  # Test 3: calculate_kpis
  kpis = calculate_kpis(clean)
  print('3) calculate_kpis:', kpis, '\n')
  assert len(kpis) >= 3
  assert kpis['total_revenue'] == 350.0 and kpis['total_orders'] == 4

  # Test 4: merge_datasets
  merged = merge_datasets(clean, clean_cust)
  print('4) merge_datasets:\n', merged, '\n')
  assert len(merged) == len(clean)  # left join ei muuda ridade arvu
  assert 'city' in merged.columns

  print('✅ Kõik testid läbitud!')

  # Päris andmed Supabase'ist
  try:
    from data_fetcher import fetch_table_data

    df_sales = clean_data(fetch_table_data('sales'))
    df_customers = clean_data(fetch_table_data('customers'))
    print('\n=== PÄRIS ANDMED ===')
    print(calculate_kpis(df_sales))
    print(calculate_weekly_aggregates(df_sales).tail())
    print(merge_datasets(df_sales, df_customers).head())
  except ImportError:
    logger.info('data_fetcher.py ei leitud, päris andmetega testi ei tehtud')
