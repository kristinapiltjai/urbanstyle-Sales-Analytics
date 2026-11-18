import os
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client

# 1. Leiame .env faili otse käesoleva skripti (data_fetcher.py) kaustast
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    supabase = None


# 2. Funktsioon müügiandmete pärimiseks (kuupäevafiltriga)
def fetch_sales(start_date=None, end_date=None):
    if not supabase:
        print("❌ VIGA: Supabase võtmed puuduvad!")
        return pd.DataFrame()

    try:
        all_data = []
        page_size = 1000
        page = 0
        while True:
            query = supabase.table("sales").select("*")
            if start_date:
                query = query.gte("sale_date", start_date)
            if end_date:
                query = query.lte("sale_date", end_date)

            response = query.range(
                page * page_size, (page + 1) * page_size - 1
            ).execute()
            if not response.data:
                break
            all_data.extend(response.data)
            if len(response.data) < page_size:
                break
            page += 1

        return pd.DataFrame(all_data)
    except Exception as e:
        print(f"❌ Viga müügiandmete pärimisel: {e}")
        return pd.DataFrame()


# 3. Funktsioon klientide pärimiseks
def fetch_customers():
    if not supabase:
        return pd.DataFrame()

    try:
        all_data = []
        page_size = 1000
        page = 0
        while True:
            response = (
                supabase.table("customers")
                .select("*")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            if not response.data:
                break
            all_data.extend(response.data)
            if len(response.data) < page_size:
                break
            page += 1
        return pd.DataFrame(all_data)
    except Exception as e:
        print(f"❌ Viga kliendiandmete pärimisel: {e}")
        return pd.DataFrame()


# 4. Funktsioon toodete pärimiseks
def fetch_products():
    if not supabase:
        return pd.DataFrame()

    try:
        all_data = []
        page_size = 1000
        page = 0
        while True:
            response = (
                supabase.table("products")
                .select("*")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            if not response.data:
                break
            all_data.extend(response.data)
            if len(response.data) < page_size:
                break
            page += 1
        return pd.DataFrame(all_data)
    except Exception as e:
        print(f"❌ Viga tooteandmete pärimisel: {e}")
        return pd.DataFrame()


# 5. Koodi testimine otse käivitamisel
if __name__ == "__main__":
    print("=== ALUSTAME TESTIMIST ===\n")

    sales_df = fetch_sales()
    print(f"Müügiandmeid laetud: {len(sales_df)} rida")

    customers_df = fetch_customers()
    print(f"Kliendiandmeid laetud: {len(customers_df)} rida")

    products_df = fetch_products()
    print(f"Tooteandmeid laetud: {len(products_df)} rida")
