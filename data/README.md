# Data

The raw data is the **Sunrise Coffee Chain** dataset from the DataDNA Dataset Challenge
(Onyx Data, October 2026). It isn't stored in this repository.

1. Download the dataset from the DataDNA challenge page.
2. Put these five files in `data/raw/`:
   - `dim_store.csv` (60 stores)
   - `dim_date.csv` (730 days, 2023-01-01 to 2024-12-31)
   - `dim_product.csv` (40 products)
   - `fact_daily_sales.csv` (10,000 rows)
   - `fact_store_monthly_profitability.csv` (1,440 rows)
3. Run `python src/prepare_data.py` to create the four tables the dashboard uses in `data/prepared/`.

| Prepared file | Rows | Grain |
|---|---|---|
| `stores.csv` | 60 | store |
| `monthly_pnl.csv` | 1,440 | store × month |
| `daily_sales.csv` | 8,910 | store × day (duplicates averaged) |
| `pnl_lines.csv` | 8,640 | store × month × P&L line |
