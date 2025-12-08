# backend/ingestion.py
import io
import pandas as pd
import pdfplumber
import zipfile
import numpy as np
import logging
from datetime import datetime
from sqlalchemy import text
from .database import engine

# --- CONFIGURATION ---
REQUIRED_COLS = {
    "trade": ["date", "symbol", "side", "quantity", "price"],
    "cash": ["date", "amount"],
    "holding": ["symbol", "quantity"],
    "nav": ["date"],
}

NUMERIC_COLS = [
    "amount", "price", "quantity", "nav_value", 
    "aum", "total_value", "avg_cost", "market_price"
]

# --- ROBUST FALLBACK MAP (Corporate Standard) ---
STANDARD_MAP = {
    "date": ["date", "trade_date", "value_date", "txn_date", "time", "timestamp", "dt", "trd_dt"],
    "amount": ["amount", "net_amount", "value", "txn_amount", "credit", "debit", "qty", "quantity", "net_val", "total"],
    "symbol": ["symbol", "ticker", "security", "instrument", "description", "narrative", "details", "scrip", "stock", "security_name"],
    "side": ["side", "buy/sell", "direction", "type", "bs"],
    "price": ["price", "unit_price", "rate", "mkt_price", "market_price", "avg_cost", "avg_price"],
    "isin": ["isin", "id", "ref", "isin_code"],
    "quantity": ["quantity", "qty", "units", "shares", "balance_qty", "closing_qty"],
    "fund_name": ["fund_name", "scheme_name", "fund", "scheme"],
    "nav_value": ["nav", "nav_value", "closing_nav", "net_asset_value"]
}

# -------------------------------------------------------------------
# 1) VALIDATION / CLEANUP
# -------------------------------------------------------------------
def validate_row_integrity(df: pd.DataFrame, file_type: str, logs: list) -> pd.DataFrame:
    initial_count = len(df)
    required = REQUIRED_COLS.get(file_type, [])
    
    missing = [col for col in required if col not in df.columns]

    if missing:
        if file_type in ("trade", "cash"):
            logs.append(f"[ERROR] Critical: Missing columns for {file_type}: {missing}")
            return pd.DataFrame() 
        else:
            logs.append(f"[WARNING] Missing columns for {file_type}: {missing}. Attempting to fill.")

    df = df.dropna(how="all")

    if "date" in df.columns:
        temp = pd.to_datetime(df["date"], errors="coerce")
        future_mask = temp > datetime.now()
        if future_mask.any():
            logs.append(f"[WARNING] Dropped {future_mask.sum()} rows with future dates.")
            df = df[~future_mask]

    final_count = len(df)
    if final_count < initial_count:
        logs.append(f"[INFO] Cleaned {initial_count - final_count} invalid rows.")

    return df


def normalize_columns(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    """
    Standardizes column names using strict keyword matching.
    """
    # 1. Standardize Keys
    def std(x: str) -> str:
        return str(x).strip().lower().replace(" ", "_").replace(".", "").replace("/", "_")

    df.columns = [std(c) for c in df.columns]

    # 2. Apply Deterministic Map
    rename_map = {}
    for standard_col, candidates in STANDARD_MAP.items():
        if standard_col in df.columns: continue 
        
        for col in df.columns:
            # Matches "trade_date" -> "date"
            if col in candidates or any(c in col for c in candidates if len(c) > 2):
                rename_map[col] = standard_col
                break 
    
    if rename_map:
        logs.append(f"[INFO] Applied Schema Map: {rename_map}")
        df = df.rename(columns=rename_map)

    # 3. Critical Logic Patches
    if "symbol" not in df.columns and "isin" in df.columns:
        df["symbol"] = df["isin"]
    if "net_amount" in df.columns and "amount" not in df.columns:
        df["amount"] = df["net_amount"]
    
    # 4. Description Fallback
    if "description" not in df.columns:
        if "narrative" in df.columns: df["description"] = df["narrative"]
        elif "details" in df.columns: df["description"] = df["details"]
        elif "symbol" in df.columns: df["description"] = df["symbol"]

    return df


def _coerce_numeric_columns(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    for col in NUMERIC_COLS:
        if col in df.columns:
            # Remove currency symbols and commas
            df[col] = df[col].astype(str).str.replace(r"[^\d\.-]", "", regex=True)
            # Force numeric, invalid becomes 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _normalize_dates(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    for col in ["date", "value_date", "settlement_date"]:
        if col in df.columns:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            except:
                parsed = pd.to_datetime(df[col], errors="coerce")
            
            df[col] = parsed.dt.date.where(~parsed.isna(), None)
    return df


def _normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["isin", "symbol", "description", "side", "currency", "fund_name", "source_file"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    return df


# -------------------------------------------------------------------
# 2) HOLDINGS LOGIC
# -------------------------------------------------------------------
def decide_holdings_mode(df: pd.DataFrame, filename: str, tenant_id: str, logs: list) -> str:
    name = filename.lower()
    snapshot_keywords = ["eod", "snapshot", "asof", "final", "position", "holding"]
    delta_keywords = ["delta", "change", "adj"]

    looks_snapshot = any(k in name for k in snapshot_keywords)
    looks_delta = any(k in name for k in delta_keywords)
    has_dupes = "symbol" in df.columns and df["symbol"].duplicated().any()

    logs.append(f"[INFO] Mode Analysis: Snapshot={looks_snapshot}, Delta={looks_delta}, Dupes={has_dupes}")

    if looks_snapshot and not looks_delta and not has_dupes:
        return "overwrite"
    return "additive"


# -------------------------------------------------------------------
# 3) DB WRITES
# -------------------------------------------------------------------
def route_and_save(df: pd.DataFrame, filename: str, user_id: str, logs: list, original_columns: list[str] | None = None) -> str:
    filename = filename.lower()
    df["source_file"] = filename

    if "date" not in df.columns:
        df["date"] = datetime.now().date()

    df = _coerce_numeric_columns(df, logs)
    df = _normalize_dates(df, logs)
    df = _normalize_text_columns(df)

    sync_engine = engine

    try:
        # A. NAV
        if "nav" in filename:
            df = validate_row_integrity(df, "nav", logs)
            if df.empty: return "Failed Validation"

            cols = ["isin", "date", "nav_value", "fund_name", "aum", "source_file"]
            for c in cols:
                if c not in df.columns: df[c] = 0.0 if c in NUMERIC_COLS else ""
            
            df["tenant_id"] = user_id
            df[cols + ["tenant_id"]].to_sql("nav_logs", sync_engine, if_exists="append", index=False)
            logs.append("[SUCCESS] NAV Data Committed")
            return "NAV Logs"

        # B. HOLDINGS
        elif any(x in filename for x in ["holding", "portfolio", "position"]):
            df = validate_row_integrity(df, "holding", logs)
            if df.empty: return "Failed Validation"

            # --- CRITICAL FIX FOR ZERO AUC ---
            # 1. Map 'total_value' from 'amount' if available (common in CSVs)
            if "total_value" not in df.columns and "amount" in df.columns:
                df["total_value"] = df["amount"]
            
            # 2. Map 'market_price' from 'price' if available
            if "market_price" not in df.columns and "price" in df.columns:
                df["market_price"] = df["price"]

            # 3. Calculate if still missing
            if "total_value" not in df.columns:
                qty = df.get("quantity", 0.0)
                price = df.get("market_price", 0.0)
                df["total_value"] = qty * price
            # ---------------------------------

            mode = decide_holdings_mode(df, filename, user_id, logs)
            logs.append(f"[INFO] Merging Positions with mode = {mode.upper()}")

            with sync_engine.begin() as conn:
                if mode == "overwrite":
                    conn.execute(text("DELETE FROM holdings WHERE tenant_id = :tid"), {"tid": user_id})
                
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO holdings (date, isin, symbol, quantity, avg_cost, market_price, total_value, source_file, tenant_id)
                        VALUES (:date, :isin, :symbol, :qty, :cost, :price, :val, :src, :tid)
                        ON CONFLICT (symbol, tenant_id) DO UPDATE SET
                            quantity = CASE WHEN :mode = 'overwrite' THEN EXCLUDED.quantity ELSE holdings.quantity + EXCLUDED.quantity END,
                            total_value = CASE WHEN :mode = 'overwrite' THEN EXCLUDED.total_value ELSE holdings.total_value + EXCLUDED.total_value END
                    """), {
                        "date": row.get("date"), "isin": row.get("isin", ""), "symbol": row.get("symbol", "UNKNOWN"),
                        "qty": row.get("quantity", 0.0), "cost": row.get("avg_cost", 0.0), "price": row.get("market_price", 0.0),
                        "val": row.get("total_value", 0.0), "src": filename, "tid": user_id, "mode": mode
                    })
            
            logs.append("[SUCCESS] Holdings Merge Complete")
            return "Holdings"

        # C. CASH
        elif any(x in filename for x in ["cash", "ledger", "bank", "txn"]):
            df = validate_row_integrity(df, "cash", logs)
            if df.empty: return "Failed Validation"

            if "symbol" in df.columns and "description" not in df.columns:
                df["description"] = df["symbol"]

            with sync_engine.begin() as conn:
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO bank_txns (date, value_date, description, amount, source_file, status, tenant_id)
                        VALUES (:date, :vd, :desc, :amt, :src, 'UNUSED', :tid)
                    """), {
                        "date": row.get("date"), "vd": row.get("value_date"), "desc": row.get("description", ""),
                        "amt": row.get("amount", 0.0), "src": filename, "tid": user_id
                    })
            logs.append("[SUCCESS] Cash Ledger Imported")
            return "Bank Txns"

        # D. TRADES
        else:
            df = validate_row_integrity(df, "trade", logs)
            if df.empty: return "Failed Validation"

            if "amount" not in df.columns:
                df["amount"] = df.get("quantity", 0.0) * df.get("price", 0.0)

            cols = ["date", "settlement_date", "symbol", "amount", "price", "quantity", "side", "isin", "currency", "source_file"]
            for c in cols:
                if c not in df.columns:
                    df[c] = 0.0 if c in NUMERIC_COLS else (None if "date" in c else "")

            df["tenant_id"] = user_id
            df[cols + ["tenant_id"]].to_sql("broker_trades", sync_engine, if_exists="append", index=False)
            logs.append("[SUCCESS] Trade Blotter Imported")
            return "Broker Trades"

    except Exception as e:
        logs.append(f"[ERROR] DB Error: {str(e)}")
        return "Error"


# -------------------------------------------------------------------
# 4) INTERNAL PROCESSING
# -------------------------------------------------------------------
def _process_single_stream(content: bytes, filename: str, user_id: str, logs: list) -> str:
    logs.append(f"[INFO] Reading: {filename}")
    filename = filename.lower()
    df = pd.DataFrame()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        elif filename.endswith(".pdf"):
            logs.append("[INFO] Parsing PDF...")
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                rows = []
                for page in pdf.pages:
                    tbl = page.extract_table()
                    if tbl: rows.extend(tbl)
                if rows: df = pd.DataFrame(rows[1:], columns=rows[0])
        
        if not df.empty:
            df = normalize_columns(df, logs)
            status = route_and_save(df, filename, user_id, logs)
            logs.append(f"[SUCCESS] {filename} -> {status}")
            return status

        logs.append(f"[WARNING] Empty/Unreadable: {filename}")
        return "Skipped"

    except Exception as e:
        logs.append(f"[ERROR] Processing {filename}: {str(e)}")
        return "Failed"


# -------------------------------------------------------------------
# 5) MAIN ENTRYPOINT
# -------------------------------------------------------------------
def process_file_content(content: bytes, filename: str, user_id: str) -> dict:
    logs = [f"[INFO] Starting Ingestion: {filename}"]
    processed_count = 0
    
    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                file_list = [f for f in z.namelist() if not f.startswith("__MACOSX") and not f.endswith("/")]
                for member in file_list:
                    if member.endswith(('.csv', '.xlsx', '.xls', '.pdf')):
                        with z.open(member) as f:
                            _process_single_stream(f.read(), member, user_id, logs)
                            processed_count += 1
        elif filename.endswith(('.csv', '.xlsx', '.xls', '.pdf')):
            _process_single_stream(content, filename, user_id, logs)
            processed_count = 1
        else:
            logs.append("[ERROR] Invalid Format. Use CSV, Excel, PDF, or ZIP.")
            return {"status": "Failed", "logs": logs}

        if processed_count == 0:
            logs.append("[WARNING] No valid data found.")
            return {"status": "Failed", "logs": logs}
            
        logs.append("[INFO] Batch Complete.")
        return {"status": "Completed", "logs": logs}

    except Exception as e:
        logs.append(f"[ERROR] Critical Error: {str(e)}")
        return {"status": "Failed", "logs": logs}