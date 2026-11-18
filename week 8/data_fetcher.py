import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# 1. Leiame .env faili asukohad os.path.join abil
script_dir = os.path.dirname(os.path.abspath(__file__))

possible_env_paths = [
    os.path.join(script_dir, '.env'),  # 1. Praegusest kaustast (nt week 8)
    os.path.join(
        script_dir, '..', 'week 7', '.env'
    ),  # 2. Otse week 7 kaustast
    os.path.join(script_dir, '..', '.env'),  # 3. Peakaustast
]

# Laeme esimese olemasoleva .env faili
for env_path in possible_env_paths:
  if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    break

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if supabase_url and supabase_key:
  supabase = create_client(supabase_url, supabase_key)
else:
  print('❌ VIGA: SUPABASE_URL või SUPABASE_KEY puudub!')
  supabase = None


# 2. Üks üldine funktsioon tabelite pärimiseks Supabase'ist
def fetch_table_data(
    table_name, start_date=None, end_date=None, date_col='sale_date'
):
  """Pärib andmed Supabase API-st tabeli nime järgi.

  Toetab kuupäevafiltreid ja automaatset pagineerimist.
  """
  if not supabase:
    print('❌ VIGA: Supabase ühendus puudub!')
    return pd.DataFrame()

  try:
    all_data = []
    page_size = 1000
    page = 0

    while True:
      query = supabase.table(table_name).select('*')

      # Kuupäevafiltrid (kui need on määramisel kaasa antud)
      if start_date:
        query = query.gte(date_col, start_date)
      if end_date:
        query = query.lte(date_col, end_date)

      # Pagineerimine (1000 rida sammuga)
      response = (
          query.range(page * page_size, (page + 1) * page_size - 1).execute()
      )

      if not response.data:
        break

      all_data.extend(response.data)

      if len(response.data) < page_size:
        break
      page += 1

    return pd.DataFrame(all_data)

  except Exception as e:
    print(f"❌ Viga tabeli '{table_name}' pärimisel: {e}")
    return pd.DataFrame()


# 3. Testimine
if __name__ == '__main__':
  print('=== ALUSTAME TESTIMIST ===\n')

  tables = ['sales', 'customers', 'products']

  for table in tables:
    df = fetch_table_data(table)
    print(f"Tabel '{table}' laetud: {len(df)} rida")