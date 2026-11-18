import time
import logging

from data_fetcher import fetch_table_data
from transform import clean_data, calculate_weekly_aggregates, calculate_kpis
from visualize_export import create_weekly_chart, create_kpi_summary, export_results

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


def run_pipeline(start_date=None, end_date=None, output_dir='output'):
  logging.info('Pipeline started')

  try:
    # 1. Extract (Roll A)
    logging.info('[EXTRACT] Algus')
    raw_sales = fetch_table_data('sales', start_date, end_date)
    if raw_sales.empty:
      raise ValueError('Müügiandmed on tühjad, kontrolli Supabase ühendust')
    logging.info(f'[EXTRACT] Lõpp: {len(raw_sales)} rida')

    # 2. Transform (Roll B)
    logging.info('[TRANSFORM] Algus')
    sales = clean_data(raw_sales)
    weekly = calculate_weekly_aggregates(sales)
    kpis = calculate_kpis(sales)
    logging.info(f'[TRANSFORM] Lõpp: {len(weekly)} nädalat')

    # 3. Visualize (Roll C)
    logging.info('[VISUALIZE] Algus')
    create_weekly_chart(weekly)
    create_kpi_summary(kpis)
    logging.info('[VISUALIZE] Lõpp')

    # 4. Export (Roll C)
    logging.info('[EXPORT] Algus')
    export_results(weekly, output_dir)
    logging.info(f'[EXPORT] Lõpp: failid kaustas {output_dir}/')

    # Kokkuvõte
    logging.info(f'Pipeline complete: {len(sales)} rows processed')
    print('\n=== KOKKUVÕTE ===')
    for key, value in kpis.items():
      print(f'  {key}: {value}')
    return True

  except Exception as e:
    logging.error(f'PIPELINE FAILED: {e}')
    return False


if __name__ == '__main__':
  start_time = time.time()
  success = run_pipeline()
  elapsed = time.time() - start_time
  print(f'\n{"✅ Õnnestus" if success else "❌ Ebaõnnestus"} ({elapsed:.1f} sekundit)')
