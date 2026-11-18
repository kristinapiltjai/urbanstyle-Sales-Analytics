"""transform.py — ETL "T" osa (Transform).

Võtab sisendiks data_fetcher.py poolt laetud DataFrame'id
(sales, customers, products) ja teeb neist nähtavad numbrid:
puhastatud andmed, nädalased koondnäitajad, KPI-d ja liidetud andmestiku.
"""

import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _safe(default):
  """Dekoraator: püüab vea kinni, logib selle ja tagastab vaikeväärtuse.

  Nii ei jookse kogu pipeline kokku, kui üks Transform samm ebaõnnestub
  (nt puudub oodatud veerg). Sama muster nagu W8 töövihiku safe_fetch().

  Args:
    default: funktsioon, mis tagastab vaikeväärtuse (nt pd.DataFrame)
  """
  def decorator(func):
    def wrapper(*args, **kwargs):
      try:
        return func(*args, **kwargs)
      except Exception as e:
        logger.error(f'[TRANSFORM] {func.__name__} ebaõnnestus: {e}')
        return default()
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
  return decorator


EMPTY_KPIS = {
    'period_start': None,
    'period_end': None,
    'total_revenue': 0.0,
    'total_orders': 0,
    'unique_customers': 0,
    'avg_order_value': 0.0,
}

# Võimalikud veerunimed (et kood töötaks ka siis, kui tabelis on veidi
# teistsugused nimed). Esimene leitud veerg võetakse kasutusele.
REVENUE_COLS = ['total_price', 'total_amount', 'revenue', 'amount', 'total']
# invoice_id = üks tellimus (arve); sale_id = üks tellimuse rida
ORDER_ID_COLS = ['invoice_id', 'order_id', 'sale_id', 'id']
DATE_COLS = ['sale_date', 'registration_date', 'created_at', 'date']
# Read, mis ilma kuupäevata kustutatakse (kliendi registreerimiskuupäev võib puududa)
REQUIRED_DATE_COLS = ['sale_date']
# Numbriveerud, mille NULL tähendab 0 (summad/kogused). Nt birth_year jääb NaN.
AMOUNT_COLS = ['quantity', 'unit_price'] + REVENUE_COLS


def _find_col(df, candidates):
  """Tagastab esimese veeru nime, mis DataFrame'is olemas on (või None)."""
  for col in candidates:
    if col in df.columns:
      return col
  return None


def _add_revenue(df):
  """Tagab, et DataFrame'is on veerg 'revenue'.

  Kui tulu veergu pole, arvutatakse see quantity * unit_price põhjal.
  """
  df = df.copy()
  rev_col = _find_col(df, REVENUE_COLS)
  if rev_col:
    df['revenue'] = pd.to_numeric(df[rev_col], errors='coerce').fillna(0)
  elif {'quantity', 'unit_price'}.issubset(df.columns):
    df['revenue'] = (
        pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        * pd.to_numeric(df['unit_price'], errors='coerce').fillna(0)
    )
  else:
    raise KeyError(
        'Tulu veergu ei leitud (oodati nt total_amount või '
        'quantity + unit_price).'
    )
  return df


# 1. Andmete puhastamine
@_safe(pd.DataFrame)
def clean_data(df, date_cols=None):
  """Puhasta DataFrame: duplikaadid, NULL-id, kuupäevad.

  - eemaldab täielikud duplikaadid
  - eemaldab read, kus puudub võtmeväli (customer_id / invoice_id / sale_id)
  - eemaldab müügiread, kus sale_date puudub või on vigane
  - summad/kogused: NULL -> 0; tekst: NULL -> 'Unknown'
  - teisendab kuupäevaveerud datetime formaati

  Args:
    df: toores DataFrame (nt fetch_table_data('sales') väljund)
    date_cols: kuupäevaveergude list (vaikimisi leitakse automaatselt)

  Returns:
    DataFrame: puhastatud koopia (algne df jääb muutmata)
  """
  if df is None or df.empty:
    logger.warning('[TRANSFORM] clean_data: sisend on tühi!')
    return pd.DataFrame() if df is None else df.copy()
  rows_before = len(df)

  if date_cols is None:
    date_cols = [c for c in DATE_COLS if c in df.columns]

  # Võtmeväljad, ilma milleta rida on kasutu
  key_cols = [c for c in ['customer_id'] + ORDER_ID_COLS if c in df.columns]

  df_clean = (
      df.drop_duplicates()
      .dropna(subset=key_cols)
      .reset_index(drop=True)
  )

  # Kuupäevad datetime'iks (vigased väärtused -> NaT, need read eemaldame)
  for col in date_cols:
    df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
  required = [c for c in REQUIRED_DATE_COLS if c in date_cols]
  if required:
    df_clean = df_clean.dropna(subset=required)

  # customer_id täisarvuks (NULL-ide tõttu võib see olla float, nt 2588.0)
  if 'customer_id' in df_clean.columns:
    df_clean['customer_id'] = df_clean['customer_id'].astype('int64')

  # Ülejäänud NULL-id: summad -> 0, tekst -> 'Unknown'
  amount_cols = [c for c in AMOUNT_COLS if c in df_clean.columns]
  df_clean[amount_cols] = df_clean[amount_cols].apply(
      pd.to_numeric, errors='coerce'
  ).fillna(0)
  num_cols = df_clean.select_dtypes(include='number').columns
  obj_cols = [
      c for c in df_clean.columns
      if c not in num_cols and c not in date_cols
      and not pd.api.types.is_datetime64_any_dtype(df_clean[c])
  ]
  df_clean[obj_cols] = df_clean[obj_cols].fillna('Unknown')

  logger.info(
      f'[TRANSFORM] clean_data: {rows_before} -> {len(df_clean)} rida '
      f'({rows_before - len(df_clean)} eemaldatud)'
  )
  return df_clean.reset_index(drop=True)


# 2. Nädalased koondnäitajad
@_safe(lambda: pd.DataFrame(
    columns=['week', 'revenue', 'orders', 'avg_order_value']))
def calculate_weekly_aggregates(df, date_col='sale_date'):
  """Arvuta nädalased koondnäitajad (nädal lõpeb pühapäeval).

  Args:
    df: puhastatud müügi DataFrame
    date_col: kuupäevaveerg, mille järgi grupeerida (vaikimisi 'sale_date')

  Returns:
    DataFrame: veerud week, revenue, orders, avg_order_value
  """
  if df is None or df.empty:
    logger.warning('[TRANSFORM] calculate_weekly_aggregates: sisend on tühi!')
    return pd.DataFrame(
        columns=['week', 'revenue', 'orders', 'avg_order_value']
    )

  df = _add_revenue(df)
  df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
  order_col = _find_col(df, ORDER_ID_COLS) or 'revenue'

  weekly = (
      df.resample('W', on=date_col)
      .agg(revenue=('revenue', 'sum'), orders=(order_col, 'nunique'))
      .reset_index()
      .rename(columns={date_col: 'week'})
  )
  weekly['avg_order_value'] = (
      (weekly['revenue'] / weekly['orders'].replace(0, pd.NA))
      .fillna(0)
      .astype(float)
      .round(2)
  )
  weekly['revenue'] = weekly['revenue'].round(2)
  logger.info(f'[TRANSFORM] calculate_weekly_aggregates: {len(weekly)} nädalat')
  return weekly


# 3. KPI-d
@_safe(lambda: dict(EMPTY_KPIS))
def calculate_kpis(df, date_col='sale_date'):
  """Arvuta peamised KPI-d Marko jaoks.

  Args:
    df: puhastatud müügi DataFrame
    date_col: kuupäevaveerg perioodi määramiseks (vaikimisi 'sale_date')

  Returns:
    dict: period_start, period_end, total_revenue, total_orders,
      unique_customers, avg_order_value
  """
  if df is None or df.empty:
    logger.warning('[TRANSFORM] calculate_kpis: sisend on tühi!')
    return dict(EMPTY_KPIS)

  df = _add_revenue(df)
  order_col = _find_col(df, ORDER_ID_COLS)
  total_orders = df[order_col].nunique() if order_col else len(df)
  total_revenue = float(df['revenue'].sum())

  dates = (
      pd.to_datetime(df[date_col], errors='coerce')
      if date_col in df else pd.Series(dtype='datetime64[ns]')
  )
  kpis = {
      'period_start': (
          dates.min().strftime('%Y-%m-%d') if dates.notna().any() else None
      ),
      'period_end': (
          dates.max().strftime('%Y-%m-%d') if dates.notna().any() else None
      ),
      'total_revenue': round(total_revenue, 2),
      'total_orders': int(total_orders),
      'unique_customers': (
          int(df['customer_id'].nunique()) if 'customer_id' in df else 0
      ),
      'avg_order_value': (
          round(total_revenue / total_orders, 2) if total_orders else 0.0
      ),
  }
  logger.info(f'[TRANSFORM] calculate_kpis: {kpis}')
  return kpis


# 4. Andmestike liitmine
@_safe(pd.DataFrame)
def merge_datasets(df_sales, df_customers, how='left'):
  """Liida müügi- ja kliendiandmed customer_id järgi.

  Args:
    df_sales: puhastatud müügi DataFrame
    df_customers: puhastatud kliendi DataFrame
    how: join tüüp (vaikimisi 'left' — ükski müük ei kao; kui klienti
      kliendi tabelis pole, on kliendi väljad NaN)

  Returns:
    DataFrame: müügiread koos kliendi andmetega (sama ridade arv kui df_sales)
  """
  if df_sales is None or df_sales.empty:
    logger.warning('[TRANSFORM] merge_datasets: müügiandmed on tühjad!')
    return pd.DataFrame()
  if df_customers is None or df_customers.empty:
    logger.warning(
        '[TRANSFORM] merge_datasets: kliendiandmed on tühjad, '
        'tagastan ainult müügid'
    )
    return df_sales.copy()

  # Kliendi tabelis peab customer_id olema unikaalne, muidu müügiread dubleeruvad
  customers = df_customers.drop_duplicates(subset='customer_id')

  merged = pd.merge(
      df_sales,
      customers,
      on='customer_id',
      how=how,
      suffixes=('', '_customer'),
      validate='many_to_one',
  )
  if 'first_name' in merged.columns:
    unmatched = int(merged['first_name'].isna().sum())
    if unmatched:
      logger.warning(
          f'[TRANSFORM] merge_datasets: {unmatched} müügirida ilma '
          'vastava kliendita'
      )
  logger.info(f'[TRANSFORM] merge_datasets: {len(merged)} rida')
  return merged


# 5. Testimine näidisandmetega
if __name__ == '__main__':
  print('=== TESTIME TRANSFORM FUNKTSIOONE ===\n')

  sales = pd.DataFrame({
      'sale_id': [1, 2, 2, 3, 4, 5, 6, 7],
      'invoice_id': [
          'INV-1', 'INV-2', 'INV-2', 'INV-2', 'INV-3', 'INV-4', 'INV-5',
          'INV-6',
      ],
      'sale_date': [
          '2026-11-02', '2026-11-03', '2026-11-03', '2026-11-03',
          '2026-11-10', '2026-11-11', '2026-11-12', 'vigane',
      ],
      'customer_id': [101, 102, 102, 102, 101, 103, None, 104],
      'product_id': [1, 2, 2, 3, 1, 3, 2, 1],
      'quantity': [2, 1, 1, 1, 1, 1, 1, 1],
      'unit_price': [50.0, 30.0, 30.0, 20.0, 80.0, 200.0, 30.0, 80.0],
      'total_price': [100.0, 30.0, 30.0, 20.0, None, 200.0, 30.0, 80.0],
      'channel': ['pood', 'e-pood', 'e-pood', 'e-pood', 'pood', None,
                  'pood', 'pood'],
  })
  customers = pd.DataFrame({
      'customer_id': [101, 102, 103],
      'first_name': ['Mari', 'Jaan', 'Eha'],
      'last_name': ['Tamm', 'Kask', 'Aas'],
      'email': ['mari@ee.ee', 'jaan@ee.ee', None],
      'city': ['Tallinn', 'Tartu', 'Pärnu'],
      'registration_date': ['2024-02-27', None, '2021-02-03'],
      'loyalty_tier': [None, 'bronze', None],
      'birth_year': [1973, None, 1999],
  })

  # Test 1: clean_data
  clean = clean_data(sales)
  print('1) clean_data:', len(sales), '->', len(clean), 'rida')
  assert len(clean) == 5, 'Duplikaat, NULL customer_id ja vigane kuupäev peavad kaduma'
  assert clean['total_price'].isna().sum() == 0, 'NULL-id peavad olema täidetud'
  assert pd.api.types.is_datetime64_any_dtype(clean['sale_date'])
  print(clean, '\n')

  # Test 2: calculate_weekly_aggregates
  weekly = calculate_weekly_aggregates(clean)
  print('2) calculate_weekly_aggregates:')
  print(weekly, '\n')
  assert weekly['revenue'].sum() == clean['total_price'].sum()
  assert weekly['orders'].tolist() == [2, 2], 'INV-2 (2 rida) = 1 tellimus'

  # Test 3: calculate_kpis
  kpis = calculate_kpis(clean)
  print('3) calculate_kpis:', kpis, '\n')
  assert isinstance(kpis, dict) and len(kpis) >= 3
  assert kpis['total_revenue'] == 350.0 and kpis['unique_customers'] == 3
  assert kpis['total_orders'] == 4

  # Test 4: merge_datasets
  merged = merge_datasets(clean, clean_data(customers))
  print('4) merge_datasets:')
  print(merged, '\n')
  assert len(merged) == len(clean), 'Left join ei tohi ridu juurde/vähemaks teha'
  assert 'city' in merged.columns
  clean_cust = clean_data(customers)
  assert len(clean_cust) == 3, 'Puuduv registration_date ei tohi klienti kustutada'
  assert clean_cust['birth_year'].isna().sum() == 1, 'birth_year NULL ei tohi saada 0-ks'

  # Test 2. sisendiga: tühi DataFrame (nt kui Extract ebaõnnestub)
  print('5) Tühi sisend:')
  empty = pd.DataFrame()
  assert clean_data(empty).empty
  assert calculate_weekly_aggregates(empty).empty
  assert calculate_kpis(empty)['total_revenue'] == 0.0
  assert merge_datasets(empty, customers).empty
  print('   tühi sisend ei tekita viga\n')

  # Test 3. sisendiga: vale struktuur (tulu veerg puudub) -> logib vea, ei krahhi
  print('6) Vigane sisend:')
  bad = pd.DataFrame({'sale_date': ['2026-11-02'], 'customer_id': [1]})
  assert calculate_kpis(bad)['total_revenue'] == 0.0
  assert calculate_weekly_aggregates(bad).empty
  print('   viga logiti, programm jätkas\n')

  print('✅ Kõik testid läbitud!')

  # Valikuline: päris andmetega (kui data_fetcher.py ja .env on olemas)
  try:
    from data_fetcher import fetch_table_data

    df_sales = clean_data(fetch_table_data('sales'))
    df_customers = clean_data(fetch_table_data('customers'))
    if not df_sales.empty:
      print('\n=== PÄRIS ANDMED ===')
      print(calculate_kpis(df_sales))
      print(calculate_weekly_aggregates(df_sales).tail())
      print(merge_datasets(df_sales, df_customers).head())
  except ImportError:
    logger.info('data_fetcher.py ei leitud — päris andmetega testi ei tehtud')
  except Exception as e:
    logger.error(f'Päris andmetega test ebaõnnestus: {e}')
