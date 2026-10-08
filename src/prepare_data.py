"""Prepare the DataDNA "Sunrise Coffee Chain" tables for Tableau.

Reads the five raw challenge files from data/raw/ and writes four analysis-ready
CSVs to data/prepared/:

    stores.csv        60 rows    one row per store (dimension)
    monthly_pnl.csv   1,440 rows one row per store-month (P&L, loyalty, footfall)
    daily_sales.csv   8,910 rows one row per store-day (duplicates averaged)
    pnl_lines.csv     8,640 rows monthly P&L in long format, for the waterfall

Usage:
    python src/prepare_data.py                     # default folders
    python src/prepare_data.py --raw path/to/raw --out path/to/prepared
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

WEEKDAY_ORDER = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4,
                 'Friday': 5, 'Saturday': 6, 'Sunday': 7}

# Daily measures that are averaged when the same store-day appears more than once
DAILY_MEASURES = ['total_revenue_gbp', 'total_transactions', 'loyalty_transactions',
                  'loyalty_redemption_cost_gbp', 'footfall', 'espresso_revenue_gbp',
                  'filter_revenue_gbp', 'food_revenue_gbp', 'retail_beans_revenue_gbp',
                  'daily_gross_profit_gbp', 'staff_count', 'total_staff_hours']

# (line item, display order, source column, sign) for the P&L waterfall
PNL_LINES = [('Revenue', 1, 'total_monthly_revenue_gbp', 1),
             ('COGS', 2, 'total_monthly_cogs_gbp', -1),
             ('Rent', 3, 'monthly_rent_gbp', -1),
             ('Labour', 4, 'monthly_staffing_cost_gbp', -1),
             ('Loyalty', 5, 'loyalty_redemption_cost_gbp', -1),
             ('Net Profit', 6, None, 0)]   # Tableau computes the closing bar as a running sum


def tidy(s: pd.Series) -> pd.Series:
    """'Suburban-High-Street' -> 'Suburban High Street'."""
    return s.str.replace('-', ' ', regex=False)


def month_start(month_id: pd.Series) -> pd.Series:
    """'2023-01' -> '2023-01-01'."""
    return pd.to_datetime(month_id + '-01').dt.strftime('%Y-%m-%d')


def build_stores(store: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        'Store ID': store.store_id,
        'Store': store.store_name.str.replace('Sunrise Coffee ', '', regex=False),
        'Format': store.store_format,
        'Location Type': tidy(store.location_type),
        'City': store.city,
        'Region': tidy(store.region).str.replace(' and ', ' & ', regex=False),
        'London vs Rest': np.where(store.region == 'London', 'London', 'Rest of UK'),
        'Store Status': tidy(store.store_status),
        'Staff Headcount': store.staff_headcount,
        'Loyalty Adoption Rate': store.loyalty_adoption_rate,
        'Seating Capacity': store.seating_capacity,
        'Opening Year': store.opening_year,
    })


def build_monthly(mp: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        'Monthly ID': mp.monthly_profit_id,
        # distinct name so Tableau's relationship to stores.csv is unambiguous
        'Store ID (Monthly)': mp.store_id,
        'Month': month_start(mp.month_id),
        'Revenue': mp.total_monthly_revenue_gbp,
        'COGS': mp.total_monthly_cogs_gbp,
        'Rent': mp.monthly_rent_gbp,
        'Labour Cost': mp.monthly_staffing_cost_gbp,
        'Loyalty Cost': mp.loyalty_redemption_cost_gbp,
        'Net Profit': mp.net_profit_gbp,
        'Member Spend': mp.loyalty_member_spend_gbp,
        'Non-Member Spend': mp.non_member_spend_gbp,
        'Avg Daily Footfall': mp.avg_daily_footfall,
        'Revenue per SqFt': mp.revenue_per_sqft_gbp,
        'Avg Dwell Minutes': mp.avg_dwell_time_minutes,
        'Rent Band': mp.rent_band,
        # kept for reference only: 42% of these labels contradict their own definitions,
        # so the dashboard recomputes status from net margin
        'Status (Original Label)': tidy(mp.profitability_status),
    })


def build_daily(ds: pd.DataFrame, date: pd.DataFrame) -> pd.DataFrame:
    # 1,006 store-days appear more than once (1,090 extra rows) with conflicting
    # totals and a different "top product"; collapse each to one row by averaging.
    g = ds.groupby(['store_id', 'date_id'])
    d = g[DAILY_MEASURES].mean().round(2).reset_index()
    d['Source Rows'] = g.size().values
    d = d.merge(date, on='date_id')
    return pd.DataFrame({
        'Store ID': d.store_id,
        'Date': d.full_date.dt.strftime('%Y-%m-%d'),
        'Weekday': d.day_of_week,
        'Weekday Order': d.day_of_week.map(WEEKDAY_ORDER),
        'Day Type': np.where(d.is_weekend, 'Weekend', 'Weekday'),
        'Trading Calendar': tidy(d.uk_trading_calendar),
        'Daily Revenue': d.total_revenue_gbp,
        'Daily Transactions': d.total_transactions,
        'Daily Loyalty Transactions': d.loyalty_transactions,
        'Daily Loyalty Cost': d.loyalty_redemption_cost_gbp,
        'Daily Footfall': d.footfall,
        'Espresso Revenue': d.espresso_revenue_gbp,
        'Filter Revenue': d.filter_revenue_gbp,
        'Food Revenue': d.food_revenue_gbp,
        'Retail Beans Revenue': d.retail_beans_revenue_gbp,
        'Daily Gross Profit': d.daily_gross_profit_gbp,
        'Staff on Shift': d.staff_count,
        'Staff Hours': d.total_staff_hours,
        'Source Rows': d['Source Rows'],
    })


def build_pnl_lines(mp: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for name, order, col, sign in PNL_LINES:
        parts.append(pd.DataFrame({
            'Store ID': mp.store_id,
            'P&L Month': month_start(mp.month_id),
            'Line Item': name,
            'Line Order': order,
            'Amount': mp[col] * sign if col else 0.0,
        }))
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--raw', type=Path, default=ROOT / 'data' / 'raw')
    ap.add_argument('--out', type=Path, default=ROOT / 'data' / 'prepared')
    args = ap.parse_args()

    date = pd.read_csv(args.raw / 'dim_date.csv', parse_dates=['full_date'])
    store = pd.read_csv(args.raw / 'dim_store.csv')
    ds = pd.read_csv(args.raw / 'fact_daily_sales.csv')
    mp = pd.read_csv(args.raw / 'fact_store_monthly_profitability.csv')

    outputs = {
        'stores.csv': build_stores(store),
        'monthly_pnl.csv': build_monthly(mp),
        'daily_sales.csv': build_daily(ds, date),
        'pnl_lines.csv': build_pnl_lines(mp),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(args.out / name, index=False)
        print(f'{name:<16} {len(df):>6,} rows')

    # sanity check: the long P&L lines add back up to reported net profit
    pnl = outputs['pnl_lines.csv']
    assert abs(pnl.Amount.sum() - mp.net_profit_gbp.sum()) < 1, 'P&L lines do not reconcile'


if __name__ == '__main__':
    main()
