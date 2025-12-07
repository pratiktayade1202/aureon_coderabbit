#!/usr/bin/env python3
"""
Generate synthetic "Stress Test ZIP" data for an AI Custody System.

Creates:
  stress_test_data/
    01_trades_standard.csv
    02_trades_messy_headers.csv
    03_trades_weekend_error.csv
    04_cash_ledger_hdfc.csv
    05_cash_ledger_missing.csv
    06_holdings_nsdl.pdf
    07_holdings_cdsl_typo.csv
    08_corp_action_dividend.csv
    09_nav_report_glitch.csv
    10_mixed_chaos.xlsx

Then zips them into:
  Stress_Test_Bundle_v1.zip
"""

import os
import csv
import zipfile

from datetime import datetime, timedelta

import pandas as pd

# PDF generation (install via: pip install reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors


def ensure_output_dir(dirname: str) -> str:
    os.makedirs(dirname, exist_ok=True)
    return dirname


def generate_file_1_trades_standard(path: str):
    """
    File 1: 01_trades_standard.csv (The Control)
    Headers: Trade Date, Symbol, Side, Qty, Price, Net Amount, ISIN
    - 5 valid trades for high-cap Indian stocks (RELIANCE, HDFC, INFY, ITC, TATA MOTORS)
    - No anomalies.
    """
    isin_map = {
        "RELIANCE": "INE002A01018",
        "HDFC": "INE001A01036",
        "INFY": "INE009A01021",
        "ITC": "INE154A01025",
        "TATA MOTORS": "INE155A01022",
    }

    trades = [
        {"Trade Date": "2025-11-20", "Symbol": "RELIANCE",     "Side": "BUY", "Qty": 100, "Price": 2500.0},
        {"Trade Date": "2025-11-21", "Symbol": "HDFC",         "Side": "BUY", "Qty": 50,  "Price": 1600.0},
        {"Trade Date": "2025-11-22", "Symbol": "INFY",         "Side": "BUY", "Qty": 60,  "Price": 1500.0},
        {"Trade Date": "2025-11-24", "Symbol": "ITC",          "Side": "BUY", "Qty": 200, "Price": 450.0},
        {"Trade Date": "2025-11-24", "Symbol": "TATA MOTORS",  "Side": "BUY", "Qty": 80,  "Price": 900.0},
    ]

    rows = []
    for t in trades:
        net_amount = t["Qty"] * t["Price"]
        rows.append({
            "Trade Date": t["Trade Date"],
            "Symbol": t["Symbol"],
            "Side": t["Side"],
            "Qty": t["Qty"],
            "Price": t["Price"],
            "Net Amount": net_amount,
            "ISIN": isin_map[t["Symbol"]],
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_2_trades_messy_headers(path: str):
    """
    File 2: 02_trades_messy_headers.csv (Schema Stress)
    Headers: Txn_Dt_Exec, Scrip_ID_Final, Direction_Flag, Units_Allocated,
             Rate_Per_Unit_INR, Total_Consideration_Val, ISIN_Tag
    - 5 trades.
    - Anomaly: one trade with Quantity = 0 but Amount = 50000 (Ghost Trade).
    """
    isin_map = {
        "RELIANCE": "INE002A01018",
        "HDFC": "INE001A01036",
        "INFY": "INE009A01021",
        "ITC": "INE154A01025",
        "TATA MOTORS": "INE155A01022",
    }

    trades = [
        # Normal-ish trades
        ("2025-11-20", "RELIANCE",    "B",  25, 2495.0),
        ("2025-11-21", "HDFC",        "S",  10, 1610.5),
        ("2025-11-22", "INFY",        "B",  15, 1490.0),
        ("2025-11-24", "ITC",         "B",  50, 452.0),
        # Ghost trade anomaly: Qty = 0 but non-zero Amount
        ("2025-11-25", "TATA MOTORS", "B",  0,  50000.0),  # Rate doesn't matter; we'll override consideration
    ]

    rows = []
    for date, sym, side, qty, rate in trades:
        if date == "2025-11-25":  # ghost trade row
            total = 50000.0
        else:
            total = qty * rate

        rows.append({
            "Txn_Dt_Exec": date,
            "Scrip_ID_Final": sym,
            "Direction_Flag": side,
            "Units_Allocated": qty,
            "Rate_Per_Unit_INR": rate,
            "Total_Consideration_Val": total,
            "ISIN_Tag": isin_map.get(sym, ""),
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_3_trades_weekend_error(path: str):
    """
    File 3: 03_trades_weekend_error.csv (Logic Stress)
    Headers: Date, Ticker, Type, Volume, Rate, Value
    - 5 trades.
    - Anomaly: Use date 2025-11-23 (Sunday) for 3 trades.
    """
    trades = [
        # Weekend trades (anomaly)
        {"Date": "2025-11-23", "Ticker": "RELIANCE", "Type": "BUY",  "Volume": 40, "Rate": 2490.0},
        {"Date": "2025-11-23", "Ticker": "HDFC",     "Type": "SELL", "Volume": 20, "Rate": 1620.0},
        {"Date": "2025-11-23", "Ticker": "INFY",     "Type": "BUY",  "Volume": 30, "Rate": 1510.0},
        # Weekday trades
        {"Date": "2025-11-20", "Ticker": "ITC",      "Type": "BUY",  "Volume": 100, "Rate": 448.0},
        {"Date": "2025-11-24", "Ticker": "TATA MOTORS", "Type": "SELL", "Volume": 50, "Rate": 905.0},
    ]

    for t in trades:
        t["Value"] = t["Volume"] * t["Rate"]

    df = pd.DataFrame(trades)
    df.to_csv(path, index=False)


def generate_file_4_cash_ledger_hdfc(path: str):
    """
    File 4: 04_cash_ledger_hdfc.csv (Recon Stress - T+2)
    Headers: Value Date, Description, Debit, Credit, Balance
    - Cash entries corresponding to File 1.
    - Anomaly: For one trade in File 1, make the cash settle 3 days later (T+3).
    """

    # File 1 trade details (must stay consistent with generate_file_1_trades_standard)
    trades = [
        {"trade_date": "2025-11-20", "symbol": "RELIANCE",    "qty": 100, "price": 2500.0, "amount": 100 * 2500.0},
        {"trade_date": "2025-11-21", "symbol": "HDFC",        "qty": 50,  "price": 1600.0, "amount": 50 * 1600.0},
        {"trade_date": "2025-11-22", "symbol": "INFY",        "qty": 60,  "price": 1500.0, "amount": 60 * 1500.0},
        {"trade_date": "2025-11-24", "symbol": "ITC",         "qty": 200, "price": 450.0,  "amount": 200 * 450.0},
        {"trade_date": "2025-11-24", "symbol": "TATA MOTORS", "qty": 80,  "price": 900.0,  "amount": 80 * 900.0},
    ]

    opening_balance = 1_000_000.0
    rows = []

    # Opening Balance
    rows.append({
        "Value Date": "2025-11-20",
        "Description": "Opening Balance",
        "Debit": "",
        "Credit": "",
        "Balance": opening_balance,
    })

    balance = opening_balance

    for t in trades:
        td = datetime.strptime(t["trade_date"], "%Y-%m-%d")

        # Default T+2; INFY trade will be T+3 anomaly
        if t["symbol"] == "INFY":
            vd = td + timedelta(days=3)  # T+3 anomaly, i.e. 2025-11-25
        else:
            vd = td + timedelta(days=2)  # T+2 normal case

        value_date_str = vd.strftime("%Y-%m-%d")
        amount = t["amount"]

        # All File 1 trades are BUYs → cash outflow (Debit)
        balance -= amount

        rows.append({
            "Value Date": value_date_str,
            "Description": f"BUY {t['symbol']} {t['qty']} @ {t['price']} (Trade Date {t['trade_date']})",
            "Debit": amount,
            "Credit": "",
            "Balance": balance,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_5_cash_ledger_missing(path: str):
    """
    File 5: 05_cash_ledger_missing.csv (Recon Stress - Break)
    Headers: TxnDate, Narration, Amt, Ref_No
    - 5 entries.
    - Anomaly: Include a large cash outflow (10 Lakhs) with no corresponding trade.
      Narration: "SUSPENSE WITHDRAWAL".
    """
    rows = [
        {"TxnDate": "2025-11-20", "Narration": "Client Funding",          "Amt": 250000.00,  "Ref_No": "CLFUND-001"},
        {"TxnDate": "2025-11-21", "Narration": "Brokerage Charges",      "Amt": -1500.00,   "Ref_No": "BROKER-CHG-01"},
        {"TxnDate": "2025-11-22", "Narration": "RTGS INWARD - CLIENT",   "Amt": 500000.00,  "Ref_No": "RTGSIN-9821"},
        # Anomaly: huge unexplained outflow
        {"TxnDate": "2025-11-23", "Narration": "SUSPENSE WITHDRAWAL",    "Amt": -1000000.0, "Ref_No": "SUSP-OUT-001"},
        {"TxnDate": "2025-11-25", "Narration": "DP CHARGES",             "Amt": -350.00,    "Ref_No": "DPCHG-774"},
    ]

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_6_holdings_nsdl_pdf(path: str):
    """
    File 6: 06_holdings_nsdl.pdf (Depository Check)
    Headers: ISIN, Company Name, Free Balance, Locked Balance, Total Qty, Valuation
    - 5 rows matching the stocks in File 1: RELIANCE, HDFC, INFY, ITC, TATA MOTORS
    - Anomaly: For INFY, Total Qty exactly double what it should be (based on File 1).
    File 1 quantities:
      RELIANCE: 100
      HDFC: 50
      INFY: 60  -> should be 60; we set 120
      ITC: 200
      TATA MOTORS: 80
    """

    # Expected holdings from File 1
    expected_qty = {
        "RELIANCE": 100,
        "HDFC": 50,
        "INFY": 60,
        "ITC": 200,
        "TATA MOTORS": 80,
    }

    isin_map = {
        "RELIANCE": "INE002A01018",
        "HDFC": "INE001A01036",
        "INFY": "INE009A01021",
        "ITC": "INE154A01025",
        "TATA MOTORS": "INE155A01022",
    }

    prices = {
        "RELIANCE": 2500.0,
        "HDFC": 1600.0,
        "INFY": 1500.0,
        "ITC": 450.0,
        "TATA MOTORS": 900.0,
    }

    rows = []
    for company in ["RELIANCE", "HDFC", "INFY", "ITC", "TATA MOTORS"]:
        correct_qty = expected_qty[company]
        if company == "INFY":
            total_qty = correct_qty * 2  # anomaly
        else:
            total_qty = correct_qty

        # Simple assumption: all free, none locked
        free_balance = total_qty
        locked_balance = 0
        valuation = total_qty * prices[company]

        rows.append([
            isin_map[company],
            company,
            free_balance,
            locked_balance,
            total_qty,
            f"{valuation:.2f}",
        ])

    # Build PDF table
    doc = SimpleDocTemplate(path, pagesize=A4)
    elements = []

    data = [["ISIN", "Company Name", "Free Balance", "Locked Balance", "Total Qty", "Valuation (INR)"]]
    data.extend(rows)

    table = Table(data, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.black),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
    ])
    table.setStyle(style)

    elements.append(table)
    doc.build(elements)


def generate_file_7_holdings_cdsl_typo(path: str):
    """
    File 7: 07_holdings_cdsl_typo.csv (Entity Resolution)
    Headers: ISIN_Code, Security_Desc, Units_Held, Mkt_Price, Val_INR
    - 3 rows.
    - Anomaly:
        * Misspell "RELIANCE" as "RELIANCE INDS LTD EQ" (valid variation).
        * "TATA MOTORS" as "TATA MTRS DVR" (different asset class).
    """
    rows = [
        {
            "ISIN_Code": "INE002A01018",
            "Security_Desc": "RELIANCE INDS LTD EQ",
            "Units_Held": 100,
            "Mkt_Price": 2498.0,
            "Val_INR": 100 * 2498.0,
        },
        {
            "ISIN_Code": "INE155A01022-DVR",
            "Security_Desc": "TATA MTRS DVR",
            "Units_Held": 50,
            "Mkt_Price": 300.0,
            "Val_INR": 50 * 300.0,
        },
        {
            "ISIN_Code": "INE009A01021",
            "Security_Desc": "INFOSYS LTD",
            "Units_Held": 60,
            "Mkt_Price": 1515.0,
            "Val_INR": 60 * 1515.0,
        },
    ]

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_8_corp_action_dividend(path: str):
    """
    File 8: 08_corp_action_dividend.csv (Routing Test)
    Headers: Record_Dt, Ex_Dt, Scrip, CA_Type, Ratio, Amt_Per_Share
    Content:
      INFY | Bonus | 1:1 (explains double quantity in holdings PDF)
      ITC  | Dividend | 5.00
    """
    rows = [
        {
            "Record_Dt": "2025-11-21",
            "Ex_Dt": "2025-11-20",
            "Scrip": "INFY",
            "CA_Type": "Bonus",
            "Ratio": "1:1",
            "Amt_Per_Share": "",
        },
        {
            "Record_Dt": "2025-11-24",
            "Ex_Dt": "2025-11-25",
            "Scrip": "ITC",
            "CA_Type": "Dividend",
            "Ratio": "",
            "Amt_Per_Share": 5.00,
        },
    ]

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_9_nav_report_glitch(path: str):
    """
    File 9: 09_nav_report_glitch.csv (Price Anomaly)
    Headers: Valuation_Date, Scheme_Name, ISIN, NAV_Per_Unit, AUM_Cr
    - 5 rows.
    - Anomaly: One liquid fund has NAV = 50000 (fat-finger).
    """
    rows = [
        {
            "Valuation_Date": "2025-11-20",
            "Scheme_Name": "Alpha Equity Fund - Regular",
            "ISIN": "INF000000101",
            "NAV_Per_Unit": 102.56,
            "AUM_Cr": 1350.25,
        },
        {
            "Valuation_Date": "2025-11-21",
            "Scheme_Name": "Balanced Advantage Fund",
            "ISIN": "INF000000102",
            "NAV_Per_Unit": 28.34,
            "AUM_Cr": 980.12,
        },
        {
            "Valuation_Date": "2025-11-22",
            "Scheme_Name": "Short Term Debt Fund",
            "ISIN": "INF000000103",
            "NAV_Per_Unit": 1025.90,
            "AUM_Cr": 420.78,
        },
        {
            "Valuation_Date": "2025-11-23",
            "Scheme_Name": "Liquid Ultra Fund - Daily",
            "ISIN": "INF000000104",
            # Fat-finger anomaly
            "NAV_Per_Unit": 50000.00,
            "AUM_Cr": 150.50,
        },
        {
            "Valuation_Date": "2025-11-24",
            "Scheme_Name": "Overnight Liquid Fund",
            "ISIN": "INF000000105",
            "NAV_Per_Unit": 1001.10,
            "AUM_Cr": 75.25,
        },
    ]

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_file_10_mixed_chaos_xlsx(path: str):
    """
    File 10: 10_mixed_chaos.xlsx (The Ultimate Test)
    Headers: Dt, Sym, Q, P, Val, BuySell
    - 3 rows.
    Anomalies:
      * Date format: 23-Nov-25 (DD-MMM-YY).
      * Price is negative (-500).
      * Symbol is NULL (blank).
    """
    rows = [
        # Anomaly 1: date format string
        {
            "Dt": "23-Nov-25",
            "Sym": "RELIANCE",
            "Q": 100,
            "P": 2500.0,
            "Val": 100 * 2500.0,
            "BuySell": "BUY",
        },
        # Anomaly 2: negative price
        {
            "Dt": "24-Nov-25",
            "Sym": "INFY",
            "Q": 50,
            "P": -500.0,  # negative
            "Val": 50 * -500.0,
            "BuySell": "SELL",
        },
        # Anomaly 3: NULL symbol
        {
            "Dt": "25-Nov-25",
            "Sym": None,  # will appear blank/NaN
            "Q": 75,
            "P": 1000.0,
            "Val": 75 * 1000.0,
            "BuySell": "BUY",
        },
    ]

    df = pd.DataFrame(rows)
    # Write as xlsx
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def main():
    out_dir = ensure_output_dir("stress_test_data")

    # 1–5, 7–9: CSV
    file1 = os.path.join(out_dir, "01_trades_standard.csv")
    file2 = os.path.join(out_dir, "02_trades_messy_headers.csv")
    file3 = os.path.join(out_dir, "03_trades_weekend_error.csv")
    file4 = os.path.join(out_dir, "04_cash_ledger_hdfc.csv")
    file5 = os.path.join(out_dir, "05_cash_ledger_missing.csv")
    file7 = os.path.join(out_dir, "07_holdings_cdsl_typo.csv")
    file8 = os.path.join(out_dir, "08_corp_action_dividend.csv")
    file9 = os.path.join(out_dir, "09_nav_report_glitch.csv")

    # 6: PDF
    file6 = os.path.join(out_dir, "06_holdings_nsdl.pdf")

    # 10: XLSX
    file10 = os.path.join(out_dir, "10_mixed_chaos.xlsx")

    # Generate files
    generate_file_1_trades_standard(file1)
    generate_file_2_trades_messy_headers(file2)
    generate_file_3_trades_weekend_error(file3)
    generate_file_4_cash_ledger_hdfc(file4)
    generate_file_5_cash_ledger_missing(file5)
    generate_file_6_holdings_nsdl_pdf(file6)
    generate_file_7_holdings_cdsl_typo(file7)
    generate_file_8_corp_action_dividend(file8)
    generate_file_9_nav_report_glitch(file9)
    generate_file_10_mixed_chaos_xlsx(file10)

    # Zip everything into Stress_Test_Bundle_v1.zip
    zip_name = "Stress_Test_Bundle_v1.zip"
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(out_dir):
            full_path = os.path.join(out_dir, fname)
            # Store with folder structure inside zip
            arcname = os.path.join("stress_test_data", fname)
            zf.write(full_path, arcname=arcname)

    print(f"Generated stress test bundle: {zip_name}")


if __name__ == "__main__":
    main()
