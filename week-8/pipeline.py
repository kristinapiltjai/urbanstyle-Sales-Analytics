import argparse
import time
import logging
from datetime import date

from visualize_export import (
    OUTPUT_DIR,
    extract_report_data,
    transform_report_data,
    create_report_figures,
    export_report,
    export_results,
    select_week_raw,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def run_pipeline(week=None, output_dir=OUTPUT_DIR):
    """Nädalaraporti pipeline (E–P).

    week:       mis tahes päev soovitud nädalast (date). None = eelmine nädal;
                kui sellel andmeid pole, võetakse viimane täisnädal andmetes.
    output_dir: kuhu raport + index.html kirjutatakse (vaikimisi week-8/output).
                Sama nädala raport kirjutatakse üle.
    """
    logging.info("Pipeline started")

    try:
        # 1. Extract (Roll A)
        logging.info("[EXTRACT] Algus")
        raw_sales, raw_customers, week_start, week_end = extract_report_data(week)
        if raw_sales.empty:
            raise ValueError("Müügiandmed on tühjad, kontrolli Supabase ühendust")
        logging.info(
            f"[EXTRACT] Lõpp: {len(raw_sales)} müügirida, {len(raw_customers)} klienti "
            f"(raporti nädal {week_start} – {week_end})"
        )

        # 2. Transform (Roll B)
        logging.info("[TRANSFORM] Algus")
        sales = transform_report_data(raw_sales, raw_customers, week_start, week_end)
        if sales.empty:
            raise ValueError("Pärast puhastamist andmeid ei jäänud")
        logging.info(f"[TRANSFORM] Lõpp: {len(sales)} rida")

        # 3. Visualize (Roll C): raporti graafikud (sh create_weekly_chart)
        logging.info("[VISUALIZE] Algus")
        report = create_report_figures(sales, week_start, week_end)
        if report is None:
            raise ValueError(f"Nädalal {week_start} – {week_end} müüke pole")
        kpis = report["kpis"]
        weekly = report["weekly"]
        logging.info(
            f"[VISUALIZE] Lõpp: {len(report['figs'])} raporti graafikut, "
            f"{len(weekly)} nädalat trendis"
        )

        # 4. Export (Roll C)
        logging.info("[EXPORT] Algus")
        # a) Raporti nädala toorandmed (puhastamata) CSV-sse, ajatempliga
        raw_week = select_week_raw(raw_sales, week_start, week_end)
        csv_path = export_results(
            raw_week, output_dir, name=f"sales_raw_{week_start:%Y-%m-%d}"
        )
        # b) Nädalaraport + index.html (sama nädal kirjutatakse üle) -> Vercel
        report_path, replaced = export_report(report, week_start, week_end, output_dir)
        status = "uuendatud (vana fail üle kirjutatud)" if replaced else "loodud"
        logging.info(f"[EXPORT] Lõpp: CSV {csv_path} + raport {status}: {report_path}")

        # Kokkuvõte
        logging.info(f"Pipeline complete: {len(sales)} rows processed")
        print(f"\n=== KOKKUVÕTE ({week_start:%d.%m.%Y} – {week_end:%d.%m.%Y}) ===")
        for key, value in kpis.items():
            print(f"  {key}: {value}")
        return True

    except Exception as e:
        logging.error(f"PIPELINE FAILED: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Urbanstyle nädalaraporti pipeline")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        help="Mis tahes päev soovitud nädalast, nt 2024-12-23 (vaikimisi eelmine nädal)",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help="Väljundkaust (vaikimisi output/ skripti kõrval)",
    )
    args = parser.parse_args()

    start_time = time.time()
    success = run_pipeline(args.week, args.output_dir)
    elapsed = time.time() - start_time
    print(
        f'\n{"✅ Õnnestus" if success else "❌ Ebaõnnestus"} ({elapsed:.1f} sekundit)'
    )
