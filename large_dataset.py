#!/usr/bin/env python3
"""
Generate a LARGE synthetic "Why The World Needs Aureon" dataset.

This script is meant to be shown to YC reviewers and used as a brutal
stress test for Aureon's ingestion + reconciliation + AI audit engine.

It creates ~85–90k rows of deliberately messy, multi-source financial
data that mimics real-world chaos:

- Inconsistent headers and schemas across brokers
- Ghost trades, weekend trades, negative prices, fat-finger NAVs
- Cash ledgers that don't tie to trades
- NSDL/CDSL holdings that disagree with each other AND with trades
- Corporate actions that explain (or don't explain) quantity jumps
- PII-heavy client master that MUST go through a privacy layer
- An XLSX file with mixed asset classes and inconsistent date formats

OUTPUT:

  large_stress_data/
    01_broker_trades_flat.csv
    02_broker_trades_weird_headers.csv
    03_broker_trades_duplicates.csv
    04_bank_ledger_primary.csv
    05_bank_ledger_missing.csv
    06_dp_nsdl_positions.csv
    07_dp_cdsl_positions_typo.csv
    08_nav_history_glitchy.csv
    09_corp_actions_stream.csv
    10_mixed_multi_asset.xlsx

Then zipped into:

  Large_Stress_Test_Bundle_v1.zip

USAGE:
  python large_dataset.py

REQUIRES:
  pip install pandas openpyxl
"""

import os
import random
import string
import zipfile
from datetime import datetime, timedelta

import pandas as pd


# -----------------------
# CONFIG
# -----------------------

OUTPUT_DIR = "large_stress_data"
ZIP_NAME = "Large_Stress_Test_Bundle_v1.zip"

# We'll roughly target ~85–90k rows across all files
ROW_COUNTS = {
    "broker_flat": 20000,
    "broker_weird": 15000,
    "broker_dupes": 12000,
    "bank_primary": 8000,
    "bank_missing": 6000,
    "nsdl": 6000,
    "cdsl": 6000,
    "nav": 5000,
    "corp": 4000,
    "mixed_xlsx_total": 5000,  # spread across sheets
}

TRADE_START_DATE = datetime(2025, 11, 20)
TRADE_END_DATE = datetime(2025, 11, 26)

SYMBOLS = [
    "RELIANCE",
    "HDFC",
    "INFY",
    "ITC",
    "TATAMOTORS",
    "AXISBANK",
    "SBIN",
    "ICICIBANK",
    "KOTAKBANK",
    "LT"
]

BROKERS = ["ALPHA_SEC", "BETA_INVEST", "OMEGA_BROKING", "DELTA_TRADES"]

FUND_NAMES = [
    "Alpha Equity Fund - Regular", "Balanced Advantage Fund",
    "Short Term Debt Fund", "Liquid Ultra Fund", "Overnight Fund",
    "Arbitrage Edge Fund", "Dynamic Asset Allocator"
]

ISIN_BASE = {
    "RELIANCE": "INE002A01018",
    "HDFC": "INE001A01036",
    "INFY": "INE009A01021",
    "ITC": "INE154A01025",
    "TATAMOTORS": "INE155A01022",
    "AXISBANK": "INE238A01026",
    "SBIN": "INE062A01020",
    "ICICIBANK": "INE090A01021",
    "KOTAKBANK": "INE237A01028",
    "LT": "INE018A01030",
}


# -----------------------
# HELPERS
# -----------------------

def ensure_output_dir(dirname: str) -> str:
    os.makedirs(dirname, exist_ok=True)
    return dirname


def random_date_between(start: datetime, end: datetime) -> datetime:
    delta_days = (end - start).days
    offset = random.randint(0, delta_days)
    return start + timedelta(days=offset)


def random_client_code() -> str:
    return "CL" + "".join(random.choices(string.digits, k=6))


def random_pan() -> str:
    # Fake-ish PAN format: 5 letters + 4 digits + 1 letter
    letters = "".join(random.choices(string.ascii_uppercase, k=5))
    digits = "".join(random.choices(string.digits, k=4))
    last = random.choice(string.ascii_uppercase)
    return letters + digits + last


def random_account_number() -> str:
    return "".join(random.choices(string.digits, k=12))


def maybe_weekend_date() -> datetime:
    """
    Randomly (small probability) force a weekend date,
    to test weekend/holiday anomaly rules.
    """
    if random.random() < 0.1:  # 10% weekend anomaly
        # Force Sunday (weekday() == 6) or Saturday (5)
        base = random_date_between(TRADE_START_DATE, TRADE_END_DATE)
        while base.weekday() not in (5, 6):
            base += timedelta(days=1)
        return base
    return random_date_between(TRADE_START_DATE, TRADE_END_DATE)


def to_str_date_random_format(dt: datetime) -> str:
    """
    Intentionally randomize date format:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - DD-MMM-YY
    - MM-DD-YYYY
    """
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%y", "%m-%d-%Y"]
    fmt = random.choice(formats)
    return dt.strftime(fmt)


# -----------------------
# FILE GENERATORS
# -----------------------

def generate_broker_trades_flat(path: str, n_rows: int):
    """
    File 1: 01_broker_trades_flat.csv
    "Clean-ish" broker trades but with realistic noise:
      - Mixed BUY/SELL
      - Occasional negative price or quantity = 0
      - Weekend trades
      - Ghost trades (qty=0, amount>0) sprinkled in
    Columns:
      TradeDate, Broker, ClientCode, Symbol, Side, Qty, Price, GrossAmount, ExchangeTradeID
    """
    rows = []
    for i in range(n_rows):
        dt = maybe_weekend_date()
        broker = random.choice(BROKERS)
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        side = random.choice(["BUY", "SELL"])

        # Basic quantity and price
        qty = random.randint(1, 500)
        price = round(random.uniform(100, 3000), 2)

        # Insert some anomalies
        r = random.random()
        if r < 0.01:
            # Ghost trade: qty 0 but non-zero amount
            qty = 0
        elif r < 0.02:
            # Negative price anomaly
            price = -abs(price)

        gross = round(qty * price, 2)
        # ExchangeTradeID: random-ish
        trade_id = f"EX{dt.strftime('%Y%m%d')}{i:06d}"

        rows.append({
            "TradeDate": dt.strftime("%Y-%m-%d"),
            "Broker": broker,
            "ClientCode": client,
            "Symbol": symbol,
            "Side": side,
            "Qty": qty,
            "Price": price,
            "GrossAmount": gross,
            "ExchangeTradeID": trade_id,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_broker_trades_weird_headers(path: str, n_rows: int):
    """
    File 2: 02_broker_trades_weird_headers.csv

    Same logical content as trades, but:
      - Different header names
      - Random date formats
      - Amount column sometimes missing or inconsistent
      - Mixed case + underscores
    Columns:
      txn_dt, brkr_id, cli_id, scrip, direction, units, rate_inr, net_val_inr
    """
    rows = []
    for i in range(n_rows):
        dt = maybe_weekend_date()
        broker = random.choice(BROKERS)
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        side = random.choice(["B", "S"])  # direction flag
        qty = random.randint(1, 400)
        rate = round(random.uniform(100, 2800), 2)

        # Inconsistencies in net value
        r = random.random()
        if r < 0.02:
            # Make net_val incorrect intentionally
            net_val = round(qty * rate * random.uniform(0.5, 1.5), 2)
        elif r < 0.04:
            # Keep it blank (missing)
            net_val = ""
        else:
            net_val = round(qty * rate, 2)

        rows.append({
            "txn_dt": to_str_date_random_format(dt),
            "brkr_id": broker,
            "cli_id": client,
            "scrip": symbol,
            "direction": side,
            "units": qty,
            "rate_inr": rate,
            "net_val_inr": net_val,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_broker_trades_duplicates(path: str, n_rows: int):
    """
    File 3: 03_broker_trades_duplicates.csv

    This file introduces:
      - Duplicated trades
      - Slightly changed quantities (near-duplicates)
      - Overlapping client codes with previous files

    Columns:
      trade_date, broker_code, client, ticker, side, quantity, price, amt
    """
    rows = []
    base_n = int(n_rows * 0.7)
    dup_n = n_rows - base_n

    # Base trades
    base_trades = []
    for i in range(base_n):
        dt = random_date_between(TRADE_START_DATE, TRADE_END_DATE)
        broker = random.choice(BROKERS)
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        side = random.choice(["BUY", "SELL"])
        qty = random.randint(1, 300)
        price = round(random.uniform(120, 2500), 2)
        amt = round(qty * price, 2)
        trade = {
            "trade_date": dt.strftime("%Y-%m-%d"),
            "broker_code": broker,
            "client": client,
            "ticker": symbol,
            "side": side,
            "quantity": qty,
            "price": price,
            "amt": amt,
        }
        base_trades.append(trade)
        rows.append(trade)

    # Duplicate / altered trades
    for i in range(dup_n):
        original = random.choice(base_trades)
        dup = original.copy()
        # Sometimes change quantity slightly
        if random.random() < 0.5:
            dup["quantity"] = max(0, dup["quantity"] + random.randint(-5, 5))
            dup["amt"] = round(dup["quantity"] * dup["price"], 2)
        # Mark duplicates by subtle changes or same everything
        rows.append(dup)

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_bank_ledger_primary(path: str, n_rows: int):
    """
    File 4: 04_bank_ledger_primary.csv

    A large bank ledger with:
      - Cash in / out
      - RTGS/NEFT, brokerage debits, DP charges
      - Some entries that SHOULD match trades, some that don't

    Columns:
      TxnDate, ValueDate, Description, Debit, Credit, Balance, RefNo
    """
    rows = []
    balance = 2_000_000.0

    for i in range(n_rows):
        # Spread dates over a slightly wider window
        dt = random_date_between(TRADE_START_DATE - timedelta(days=5),
                                 TRADE_END_DATE + timedelta(days=3))
        value_date = dt + timedelta(days=random.choice([0, 0, 1, 2]))
        desc_type = random.choice(["FUNDING", "BROKER_DEBIT", "PAYOUT", "CHARGES", "MISC"])
        ref = f"TXN-{i:07d}"

        debit = 0.0
        credit = 0.0

        if desc_type == "FUNDING":
            credit = random.randint(50_000, 300_000)
            description = "CLIENT FUNDING - RTGS"
        elif desc_type == "PAYOUT":
            debit = random.randint(20_000, 200_000)
            description = "PAYOUT TO CLIENT"
        elif desc_type == "BROKER_DEBIT":
            debit = random.randint(10_000, 150_000)
            description = "BROKERAGE / TRADE SETTLEMENT"
        elif desc_type == "CHARGES":
            debit = random.randint(100, 2_000)
            description = "BANK / DP CHARGES"
        else:
            # Misc entry
            if random.random() < 0.5:
                credit = random.randint(5_000, 50_000)
            else:
                debit = random.randint(5_000, 50_000)
            description = "MISC ADJUSTMENT"

        balance = balance + credit - debit

        rows.append({
            "TxnDate": dt.strftime("%Y-%m-%d"),
            "ValueDate": value_date.strftime("%Y-%m-%d"),
            "Description": description,
            "Debit": round(debit, 2) if debit else "",
            "Credit": round(credit, 2) if credit else "",
            "Balance": round(balance, 2),
            "RefNo": ref,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_bank_ledger_missing(path: str, n_rows: int):
    """
    File 5: 05_bank_ledger_missing.csv

    A "parallel" ledger that:
      - Has some overlapping RefNo
      - Has a few very large unexplained outflows
      - Has missing ValueDate or Description in some rows

    Columns:
      TxnDate, ValueDate, Narration, Amount, RefNo
    """
    rows = []
    for i in range(n_rows):
        dt = random_date_between(TRADE_START_DATE - timedelta(days=3),
                                 TRADE_END_DATE + timedelta(days=5))
        # Sometimes omit value date
        if random.random() < 0.1:
            value_date = ""
        else:
            value_date = (dt + timedelta(days=random.choice([0, 1, 2]))).strftime("%Y-%m-%d")

        # Some huge suspicious transactions
        if random.random() < 0.02:
            amt = -random.randint(500_000, 2_000_000)
            narration = "SUSPICIOUS BULK WITHDRAWAL"
        else:
            amt = random.randint(-200_000, 200_000)
            narration = random.choice([
                "AUTO SWEEP", "ATM WDL", "IMPS", "UPI", "BROKER PAYIN", "BROKER PAYOUT"
            ])

        # Occasionally blank narration
        if random.random() < 0.03:
            narration = ""

        ref = f"LED-{i:06d}"

        rows.append({
            "TxnDate": dt.strftime("%Y-%m-%d"),
            "ValueDate": value_date,
            "Narration": narration,
            "Amount": amt,
            "RefNo": ref,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_nsdl_positions(path: str, n_rows: int):
    """
    File 6: 06_dp_nsdl_positions.csv

    NSDL-style holdings:
      - Position by ISIN + client
      - Free / Locked / Total
      - Some quantities misaligned with trades
    Columns:
      ClientID, ISIN, SecurityName, FreeQty, LockedQty, TotalQty, Valuation
    """
    rows = []
    for i in range(n_rows):
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        isin = ISIN_BASE[symbol]
        free = random.randint(0, 3000)
        locked = random.randint(0, 300) if random.random() < 0.2 else 0
        total = free + locked
        price = random.uniform(100, 3000)
        val = round(total * price, 2)

        rows.append({
            "ClientID": client,
            "ISIN": isin,
            "SecurityName": symbol,
            "FreeQty": free,
            "LockedQty": locked,
            "TotalQty": total,
            "Valuation": val,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_cdsl_positions_typo(path: str, n_rows: int):
    """
    File 7: 07_dp_cdsl_positions_typo.csv

    CDSL-style holdings with:
      - Slightly different security descriptions
      - Typos, DVR variations, EQ suffixes
      - Quantities that sometimes disagree with NSDL

    Columns:
      DP_Client_ID, ISIN_Code, Security_Desc, Holding, Pledge_Qty, MktPrice, HoldingValue
    """
    def security_desc_for(symbol: str) -> str:
        base = {
            "RELIANCE": "RELIANCE INDS LTD EQ",
            "HDFC": "HDFC BANK LTD",
            "INFY": "INFOSYS LTD",
            "ITC": "ITC LTD EQ",
            "TATAMOTORS": "TATA MOTORS LTD",
            "AXISBANK": "AXIS BANK LTD EQ",
            "SBIN": "STATE BANK OF INDIA",
            "ICICIBANK": "ICICI BANK LTD",
            "KOTAKBANK": "KOTAK MAHINDRA BANK",
            "LT": "LARSEN AND TOUBRO",
        }[symbol]
        # Introduce typos / DVR variants
        if random.random() < 0.1:
            return base.replace("LTD", "LTD DVR")
        if random.random() < 0.1:
            return base.replace("BANK", "BNK")
        return base

    rows = []
    for i in range(n_rows):
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        isin = ISIN_BASE[symbol]
        desc = security_desc_for(symbol)
        holding = random.randint(0, 3500)
        pledge = random.randint(0, min(holding, 500)) if random.random() < 0.15 else 0
        mkt_price = round(random.uniform(100, 3000), 2)
        val = round(holding * mkt_price, 2)

        rows.append({
            "DP_Client_ID": client,
            "ISIN_Code": isin,
            "Security_Desc": desc,
            "Holding": holding,
            "Pledge_Qty": pledge,
            "MktPrice": mkt_price,
            "HoldingValue": val,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_nav_history_glitch(path: str, n_rows: int):
    """
    File 8: 08_nav_history_glitchy.csv

    NAV history with:
      - Reasonable NAVs for most days
      - Some fat-finger NAVs (50,000 etc.)
      - Different schemes
    Columns:
      ValuationDate, SchemeName, ISIN, NAV, AUM_Cr
    """
    rows = []
    for i in range(n_rows):
        dt = random_date_between(TRADE_START_DATE - timedelta(days=30),
                                 TRADE_END_DATE)
        scheme = random.choice(FUND_NAMES)
        # fake ISIN for funds
        isin = f"INF{random.randint(100000, 999999)}0{i % 10}"

        nav = random.uniform(10, 2000)
        if random.random() < 0.01:
            nav = random.uniform(20000, 60000)  # fat-finger

        aum = random.uniform(50, 5000)

        rows.append({
            "ValuationDate": dt.strftime("%Y-%m-%d"),
            "SchemeName": scheme,
            "ISIN": isin,
            "NAV": round(nav, 4),
            "AUM_Cr": round(aum, 2),
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_corp_actions_stream(path: str, n_rows: int):
    """
    File 9: 09_corp_actions_stream.csv

    Stream of corporate action events:
      - Bonus, Split, Dividend, Rights
      - Some that correspond to held ISINs, some noise
    Columns:
      RecordDate, ExDate, ISIN, Symbol, CA_Type, Ratio, AmountPerShare, Source
    """
    ca_types = ["BONUS", "SPLIT", "DIVIDEND", "RIGHTS", "MERGER"]
    rows = []
    for i in range(n_rows):
        symbol = random.choice(SYMBOLS)
        isin = ISIN_BASE[symbol]
        rec_date = random_date_between(TRADE_START_DATE - timedelta(days=60),
                                       TRADE_END_DATE + timedelta(days=30))
        ex_date = rec_date - timedelta(days=random.randint(1, 10))
        ca = random.choice(ca_types)
        ratio = ""
        amount = ""

        if ca in ("BONUS", "SPLIT", "RIGHTS"):
            ratio = random.choice(["1:1", "1:2", "2:3", "3:5"])
        if ca == "DIVIDEND":
            amount = round(random.uniform(1.0, 20.0), 2)

        rows.append({
            "RecordDate": rec_date.strftime("%Y-%m-%d"),
            "ExDate": ex_date.strftime("%Y-%m-%d"),
            "ISIN": isin,
            "Symbol": symbol,
            "CA_Type": ca,
            "Ratio": ratio,
            "AmountPerShare": amount,
            "Source": random.choice(["NSE", "BSE", "RTA"]),
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def generate_client_master_and_trades_xlsx(path: str, total_rows: int):
    """
    File 10: 10_mixed_multi_asset.xlsx

    XLSX with multiple sheets:
      - Sheet1: Client Master with PII
      - Sheet2: Additional Trades with crazy date formats
      - Sheet3: Holdings snapshot
      - Sheet4: Synthetic "Error Log" output from a legacy system

    Total rows across sheets ~ total_rows.
    """

    # Split rows across sheets
    cm_rows = int(total_rows * 0.25)
    tr_rows = int(total_rows * 0.35)
    hold_rows = int(total_rows * 0.25)
    err_rows = total_rows - (cm_rows + tr_rows + hold_rows)

    # Sheet 1: Client Master
    cm_data = []
    for i in range(cm_rows):
        client = random_client_code()
        name = f"Client {i}"
        pan = random_pan()
        account = random_account_number()
        email = f"client{i}@example.com"
        phone = "".join(random.choices(string.digits, k=10))
        city = random.choice(["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad"])
        cm_data.append({
            "ClientCode": client,
            "ClientName": name,
            "PAN": pan,
            "AccountNo": account,
            "Email": email,
            "Mobile": phone,
            "City": city,
        })
    df_cm = pd.DataFrame(cm_data)

    # Sheet 2: Additional trades with inconsistent date formats
    tr_data = []
    for i in range(tr_rows):
        dt = maybe_weekend_date()
        symbol = random.choice(SYMBOLS)
        side = random.choice(["BUY", "SELL"])
        qty = random.randint(1, 1000)
        price = round(random.uniform(50, 2500), 2)
        val = round(qty * price, 2)
        # Mixed date formats for maximum pain
        dt_str = to_str_date_random_format(dt)
        tr_data.append({
            "Dt": dt_str,
            "Sym": symbol,
            "Side": side,
            "Qty": qty,
            "Px": price,
            "Val": val,
        })
    df_tr = pd.DataFrame(tr_data)

    # Sheet 3: Holdings Snapshot
    hold_data = []
    for i in range(hold_rows):
        client = random_client_code()
        symbol = random.choice(SYMBOLS)
        isin = ISIN_BASE[symbol]
        qty = random.randint(0, 4000)
        avg_price = round(random.uniform(100, 2000), 2)
        mkt_price = round(avg_price * random.uniform(0.7, 1.3), 2)
        val = round(qty * mkt_price, 2)
        hold_data.append({
            "ClientCode": client,
            "ISIN": isin,
            "Symbol": symbol,
            "Qty": qty,
            "AvgPx": avg_price,
            "MktPx": mkt_price,
            "Value": val,
        })
    df_hold = pd.DataFrame(hold_data)

    # Sheet 4: Error Log (legacy system)
    err_data = []
    for i in range(err_rows):
        ts = datetime(2025, 11, 20) + timedelta(minutes=i)
        err_code = random.choice(["E001", "E002", "E003", "WARN01", "INFO01"])
        msg = random.choice([
            "SCHEMA_MISMATCH",
            "UNMAPPED_COLUMN",
            "FAILED_PARSING_PDF",
            "UNKNOWN_CLIENT_CODE",
            "NAV_SPIKE_DETECTED",
            "WEEKEND_TRADE"
        ])
        severity = "ERROR" if err_code.startswith("E") else (
            "WARN" if err_code.startswith("WARN") else "INFO"
        )
        err_data.append({
            "Timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "Code": err_code,
            "Severity": severity,
            "Message": msg,
        })
    df_err = pd.DataFrame(err_data)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_cm.to_excel(writer, index=False, sheet_name="ClientMaster")
        df_tr.to_excel(writer, index=False, sheet_name="Trades")
        df_hold.to_excel(writer, index=False, sheet_name="Holdings")
        df_err.to_excel(writer, index=False, sheet_name="LegacyErrorLog")


# -----------------------
# MAIN
# -----------------------

def main():
    out_dir = ensure_output_dir(OUTPUT_DIR)

    file1 = os.path.join(out_dir, "01_broker_trades_flat.csv")
    file2 = os.path.join(out_dir, "02_broker_trades_weird_headers.csv")
    file3 = os.path.join(out_dir, "03_broker_trades_duplicates.csv")
    file4 = os.path.join(out_dir, "04_bank_ledger_primary.csv")
    file5 = os.path.join(out_dir, "05_bank_ledger_missing.csv")
    file6 = os.path.join(out_dir, "06_dp_nsdl_positions.csv")
    file7 = os.path.join(out_dir, "07_dp_cdsl_positions_typo.csv")
    file8 = os.path.join(out_dir, "08_nav_history_glitchy.csv")
    file9 = os.path.join(out_dir, "09_corp_actions_stream.csv")
    file10 = os.path.join(out_dir, "10_mixed_multi_asset.xlsx")

    # Generate all files
    generate_broker_trades_flat(file1, ROW_COUNTS["broker_flat"])
    generate_broker_trades_weird_headers(file2, ROW_COUNTS["broker_weird"])
    generate_broker_trades_duplicates(file3, ROW_COUNTS["broker_dupes"])
    generate_bank_ledger_primary(file4, ROW_COUNTS["bank_primary"])
    generate_bank_ledger_missing(file5, ROW_COUNTS["bank_missing"])
    generate_nsdl_positions(file6, ROW_COUNTS["nsdl"])
    generate_cdsl_positions_typo(file7, ROW_COUNTS["cdsl"])
    generate_nav_history_glitch(file8, ROW_COUNTS["nav"])
    generate_corp_actions_stream(file9, ROW_COUNTS["corp"])
    generate_client_master_and_trades_xlsx(file10, ROW_COUNTS["mixed_xlsx_total"])

    # Zip into one bundle
    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(out_dir):
            full_path = os.path.join(out_dir, fname)
            arcname = os.path.join(OUTPUT_DIR, fname)
            zf.write(full_path, arcname=arcname)

    print(f"Generated LARGE stress test bundle: {ZIP_NAME}")


if __name__ == "__main__":
    main()
