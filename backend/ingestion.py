# backend/ingestion.py
import io
import pandas as pd
import pdfplumber
import numpy as np
from datetime import datetime
from sqlalchemy import text
from .database import engine
from .ai_schema import get_smart_mapping

# --- CONFIGURATION ---
REQUIRED_COLS = {
    "trade": ["date", "symbol", "side", "quantity", "price"],
    # For cash we keep strict: we really need date + amount
    "cash": ["date", "amount"],
    # For holdings / nav we go softer and fill things later
    "holding": ["symbol", "quantity"],   # date / total_value are optional
    "nav": ["date"],                     # fund_name / nav_value filled later
}

# Numeric columns we will coerce globally (balance handled separately)
NUMERIC_COLS = [
    "amount",
    "price",
    "quantity",
    "nav_value",
    "aum",
    "total_value",
    "avg_cost",
    "market_price",
]


# -------------------------------------------------------------------
# 1) VALIDATION / CLEANUP
# -------------------------------------------------------------------
def validate_row_integrity(df: pd.DataFrame, file_type: str, logs: list) -> pd.DataFrame:
    """
    The Firewall: Rejects rows that violate basic business logic.
    Loosely enforced for holdings/nav; stricter for trade/cash.
    """
    initial_count = len(df)

    # 1. Check Mandatory Columns (softened for holdings/nav)
    required = REQUIRED_COLS.get(file_type, [])
    missing = [col for col in required if col not in df.columns]

    if missing:
        # For trade/cash -> hard fail
        if file_type in ("trade", "cash"):
            logs.append(f"❌ CRITICAL: Missing mandatory columns for {file_type}: {missing}")
            return pd.DataFrame()
        # For holdings/nav -> log warning and continue anyway
        else:
            logs.append(
                f"⚠️ Soft Warning: Missing recommended columns for {file_type}: {missing}. "
                f"Ingestion will attempt to infer/fill values."
            )

    # 2. Drop Empty Rows
    df = df.dropna(how="all")

    # 3. Sanity Checks
    if "date" in df.columns:
        temp = pd.to_datetime(df["date"], errors="coerce")
        future_mask = temp > datetime.now()
        if future_mask.any():
            logs.append(f"⚠️ Warning: Dropped {future_mask.sum()} rows with future dates.")
            df = df[~future_mask]

    if file_type in ("trade", "cash") and "amount" in df.columns:
        zero_mask = (df["amount"] == 0) | (df["amount"].isnull())
        if zero_mask.any():
            logs.append(f"ℹ️ Info: Skipped {zero_mask.sum()} zero-value rows.")
            df = df[~zero_mask]

    final_count = len(df)
    if final_count < initial_count:
        logs.append(f"🧹 Cleaned {initial_count - final_count} invalid rows.")

    return df


def normalize_columns(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    original_headers = [str(c).strip() for c in df.columns]

    # 1. Ask AI (With Cache)
    logs.append(f"🤖 AI Analyzing headers (sample): {original_headers[:3]}...")
    try:
        ai_map = get_smart_mapping(original_headers)
        if ai_map:
            df = df.rename(columns=ai_map)
            logs.append("✅ Schema Normalization Complete via AI mapping")
        else:
            logs.append("⚠️ AI Schema Inference returned no mapping. Using raw headers.")
    except Exception as e:
        logs.append(f"⚠️ AI Mapping Skipped: {e}")

    # 2. Cleanup (The Mop)
    def std(x: str) -> str:
        return (
            str(x)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace(".", "")
            .replace("/", "_")
        )

    df.columns = [std(c) for c in df.columns]

    # 3. Deterministic aliases (in case AI miss)
    col_map = {
        # Holdings-like
        "security_name": "symbol",
        "security": "symbol",
        "scrip": "symbol",
        "scrip_name": "symbol",
        "isin_code": "isin",
        "qty": "quantity",
        "balance_qty": "quantity",
        "closing_qty": "quantity",
        "market_value": "total_value",
        "value": "total_value",
        "avg_price": "avg_cost",
        "avg_cost_price": "avg_cost",
        # NAV-like
        "scheme_name": "fund_name",
        "fund": "fund_name",
        "nav": "nav_value",
        "closing_nav": "nav_value",
        # Cash-like
        "txn_amount": "amount",
        "net_amount": "amount",
        "transaction_amount": "amount",
        "narration": "description",
        "details": "description",
    }

    df = df.rename(columns={c: col_map.get(c, c) for c in df.columns})

    # 4. Critical Aliases
    if "symbol" not in df.columns and "isin" in df.columns:
        df["symbol"] = df["isin"]
    if "net_amount" in df.columns and "amount" not in df.columns:
        df["amount"] = df["net_amount"]

    return df


def _coerce_numeric_columns(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    """
    Force numeric columns to be actual numbers, or 0.0 if garbage.
    (balance is handled separately, so it is not in NUMERIC_COLS.)
    """
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = (
                df[col]
                    .astype(str)
                    .str.replace(r"[^\d\.-]", "", regex=True)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _normalize_dates(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    for col in ["date", "value_date", "settlement_date"]:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = parsed.dt.date.where(~parsed.isna(), None)
    return df


def _normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["isin", "symbol", "description", "side", "currency", "fund_name", "source_file"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    return df


# -------------------------------------------------------------------
# 2) SMART HOLDINGS MODE DETECTION
# -------------------------------------------------------------------
def decide_holdings_mode(df: pd.DataFrame, filename: str, tenant_id: str, logs: list) -> str:
    """
    Decide whether this holdings file should:
      - OVERWRITE: treat as full snapshot
      - ADDITIVE: treat as delta / adjustments
      - PARTIAL: overwrite only the symbols present
    """
    name = filename.lower()

    snapshot_keywords = ["eod", "snapshot", "asof", "final", "position_", "positions_", "holdings"]
    delta_keywords = ["delta", "intraday", "update", "changes", "adj", "adjustment"]

    looks_snapshot_name = any(k in name for k in snapshot_keywords)
    looks_delta_name = any(k in name for k in delta_keywords)

    has_symbol = "symbol" in df.columns
    has_dupes = has_symbol and df["symbol"].duplicated().any()

    value_consistency_ratio = None
    if {"total_value", "quantity", "market_price"}.issubset(df.columns):
        q = df["quantity"].astype(float)
        p = df["market_price"].astype(float)
        tv = df["total_value"].astype(float)
        approx = q * p
        diff = (tv - approx).abs()
        tolerance = (tv.abs() * 0.02).clip(lower=1.0)
        good_mask = diff <= tolerance
        if len(df) > 0:
            value_consistency_ratio = good_mask.sum() / len(df)
        else:
            value_consistency_ratio = 0.0

    logs.append(
        f"🧠 Holdings Heuristics: "
        f"snapshot_name={looks_snapshot_name}, "
        f"delta_name={looks_delta_name}, "
        f"has_dupes={has_dupes}, "
        f"value_consistency={value_consistency_ratio}"
    )

    # Strong snapshot: clean file, snapshoty name, no duplicates
    if looks_snapshot_name and not looks_delta_name:
        if not has_dupes and (value_consistency_ratio is None or value_consistency_ratio >= 0.7):
            logs.append("📌 Holdings Mode → OVERWRITE (EOD snapshot detected)")
            return "overwrite"

    # Strong delta signals
    if looks_delta_name or has_dupes:
        logs.append("📌 Holdings Mode → ADDITIVE (Delta file / repeated symbols)")
        return "additive"

    # Partial snapshot: values look consistent, but unclear coverage
    if value_consistency_ratio is not None and value_consistency_ratio >= 0.8:
        logs.append("📌 Holdings Mode → PARTIAL (Subset snapshot detected)")
        return "partial"

    # Fallback
    logs.append("📌 Holdings Mode → ADDITIVE (Fallback safe mode)")
    return "additive"


# -------------------------------------------------------------------
# 3) CORE ROUTING / DB WRITES
# -------------------------------------------------------------------
def route_and_save(
    df: pd.DataFrame,
    filename: str,
    user_id: str,
    logs: list,
    original_columns: list[str] | None = None,
) -> str:
    filename = filename.lower()
    df["source_file"] = filename

    if "date" not in df.columns:
        df["date"] = datetime.now().date()

    # global type normalization (except cash balance which we treat separately)
    df = _coerce_numeric_columns(df, logs)
    df = _normalize_dates(df, logs)
    df = _normalize_text_columns(df)

    sync_engine = engine

    try:
        # A. NAV
        if "nav" in filename:
            df = validate_row_integrity(df, "nav", logs)
            if df.empty:
                return "Failed Validation"

            if "nav_value" not in df.columns and "price" in df.columns:
                df["nav_value"] = df["price"]
            if "aum" not in df.columns and "amount" in df.columns:
                df["aum"] = df["amount"]
            if "fund_name" not in df.columns:
                df["fund_name"] = "Unknown Fund"

            cols = ["isin", "date", "nav_value", "fund_name", "aum", "source_file"]
            for c in cols:
                if c not in df.columns:
                    df[c] = 0.0 if c in NUMERIC_COLS else ""

            df["tenant_id"] = user_id
            df[cols + ["tenant_id"]].to_sql(
                "nav_logs", sync_engine, if_exists="append", index=False
            )
            logs.append("💾 NAV Data Committed")
            return "NAV Logs"

        # B. HOLDINGS (SMART MODE)
        elif any(x in filename for x in ["holding", "portfolio", "position"]):
            df = validate_row_integrity(df, "holding", logs)
            if df.empty:
                return "Failed Validation"

            # Fill missing numeric derived value
            if "total_value" not in df.columns:
                df["total_value"] = (
                    df.get("quantity", 0.0) * df.get("market_price", 0.0)
                )

            mode = decide_holdings_mode(df, filename, user_id, logs)
            logs.append(f"🔄 Merging Positions with mode = {mode.upper()}")

            with sync_engine.begin() as conn:
                if mode == "overwrite":
                    logs.append("🧨 OVERWRITE: Deleting all existing holdings for tenant before insert.")
                    conn.execute(
                        text("DELETE FROM holdings WHERE tenant_id = :tid"),
                        {"tid": user_id},
                    )
                    for _, row in df.iterrows():
                        conn.execute(
                            text(
                                """
                                INSERT INTO holdings
                                (date, isin, symbol, quantity, avg_cost, market_price, total_value, source_file, tenant_id)
                                VALUES (:date, :isin, :symbol, :qty, :cost, :price, :val, :src, :tid)
                                """
                            ),
                            {
                                "date": row.get("date"),
                                "isin": row.get("isin", ""),
                                "symbol": row.get("symbol", "UNKNOWN"),
                                "qty": row.get("quantity", 0.0),
                                "cost": row.get("avg_cost", 0.0),
                                "price": row.get("market_price", 0.0),
                                "val": row.get("total_value", 0.0),
                                "src": filename,
                                "tid": user_id,
                            },
                        )

                elif mode == "partial":
                    logs.append(
                        "🧩 PARTIAL: Overwriting only symbols present in this file for the tenant."
                    )
                    for _, row in df.iterrows():
                        symbol = row.get("symbol", "UNKNOWN")
                        conn.execute(
                            text(
                                """
                                DELETE FROM holdings
                                WHERE tenant_id = :tid AND symbol = :symbol
                                """
                            ),
                            {"tid": user_id, "symbol": symbol},
                        )
                        conn.execute(
                            text(
                                """
                                INSERT INTO holdings
                                (date, isin, symbol, quantity, avg_cost, market_price, total_value, source_file, tenant_id)
                                VALUES (:date, :isin, :symbol, :qty, :cost, :price, :val, :src, :tid)
                                """
                            ),
                            {
                                "date": row.get("date"),
                                "isin": row.get("isin", ""),
                                "symbol": symbol,
                                "qty": row.get("quantity", 0.0),
                                "cost": row.get("avg_cost", 0.0),
                                "price": row.get("market_price", 0.0),
                                "val": row.get("total_value", 0.0),
                                "src": filename,
                                "tid": user_id,
                            },
                        )

                else:  # ADDITIVE
                    logs.append(
                        "➕ ADDITIVE: Applying delta-style merges (quantity/total_value += incoming)."
                    )
                    for _, row in df.iterrows():
                        conn.execute(
                            text(
                                """
                                INSERT INTO holdings
                                (date, isin, symbol, quantity, avg_cost, market_price, total_value, source_file, tenant_id)
                                VALUES (:date, :isin, :symbol, :qty, :cost, :price, :val, :src, :tid)
                                ON CONFLICT (symbol, tenant_id)
                                DO UPDATE SET
                                    quantity = holdings.quantity + EXCLUDED.quantity,
                                    total_value = holdings.total_value + EXCLUDED.total_value
                                """
                            ),
                            {
                                "date": row.get("date"),
                                "isin": row.get("isin", ""),
                                "symbol": row.get("symbol", "UNKNOWN"),
                                "qty": row.get("quantity", 0.0),
                                "cost": row.get("avg_cost", 0.0),
                                "price": row.get("market_price", 0.0),
                                "val": row.get("total_value", 0.0),
                                "src": filename,
                                "tid": user_id,
                            },
                        )

            logs.append("✅ Holdings Merge Complete")
            return "Holdings"

        # C. CASH
        elif any(x in filename for x in ["cash", "ledger", "bank", "txn"]):
            df = validate_row_integrity(df, "cash", logs)
            if df.empty:
                return "Failed Validation"

            # if symbol present but description missing, reuse symbol
            if "symbol" in df.columns and "description" not in df.columns:
                df["description"] = df["symbol"]

            # detect whether the original file had a balance column at all
            source_has_balance = False
            if original_columns:
                def std(x: str) -> str:
                    return (
                        str(x)
                        .strip()
                        .lower()
                        .replace(" ", "_")
                        .replace(".", "")
                        .replace("/", "_")
                    )
                normalized_original = [std(c) for c in original_columns]
                source_has_balance = "balance" in normalized_original

            # if file actually had balance, ensure numeric now
            if "balance" in df.columns and source_has_balance:
                df["balance"] = (
                    df["balance"]
                    .astype(str)
                    .str.replace(r"[^\d\.-]", "", regex=True)
                )
                df["balance"] = pd.to_numeric(df["balance"], errors="coerce")

            with sync_engine.begin() as conn:
                for _, row in df.iterrows():
                    if source_has_balance and "balance" in df.columns:
                        bal = row.get("balance", 0.0)
                    else:
                        # no balance column in source: store NULL, let AUC ignore it
                        bal = None

                    conn.execute(
                        text(
                            """
                            INSERT INTO bank_txns
                            (date, value_date, description, amount, balance, source_file, status, tenant_id)
                            VALUES (:date, :vd, :desc, :amt, :bal, :src, 'UNUSED', :tid)
                            """
                        ),
                        {
                            "date": row.get("date"),
                            "vd": row.get("value_date"),
                            "desc": row.get("description", ""),
                            "amt": row.get("amount", 0.0),
                            "bal": bal,
                            "src": filename,
                            "tid": user_id,
                        },
                    )
            logs.append("💰 Cash Ledger Imported")
            return "Bank Txns"

        # D. TRADES (Default fallback)
        else:
            df = validate_row_integrity(df, "trade", logs)
            if df.empty:
                return "Failed Validation"

            if "amount" not in df.columns:
                df["amount"] = df.get("quantity", 0.0) * df.get("price", 0.0)

            cols = [
                "date",
                "settlement_date",
                "symbol",
                "amount",
                "price",
                "quantity",
                "side",
                "isin",
                "currency",
                "source_file",
            ]
            for c in cols:
                if c not in df.columns:
                    if c in NUMERIC_COLS:
                        df[c] = 0.0
                    elif "date" in c:
                        df[c] = None
                    else:
                        df[c] = ""

            df["tenant_id"] = user_id
            df[cols + ["tenant_id"]].to_sql(
                "broker_trades", sync_engine, if_exists="append", index=False
            )
            logs.append("📉 Trade Blotter Imported")
            return "Broker Trades"

    except Exception as e:
        logs.append(f"❌ DB Error: {str(e)}")
        return "Error"


# -------------------------------------------------------------------
# 4) ENTRYPOINT
# -------------------------------------------------------------------
def process_file_content(content: bytes, filename: str, user_id: str) -> dict:
    logs = [f"📂 Reading {filename}..."]
    filename = filename.lower()
    df = pd.DataFrame()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        elif filename.endswith(".pdf"):
            logs.append("📄 Extracting PDF Tables...")
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                rows = []
                for page in pdf.pages:
                    tbl = page.extract_table()
                    if tbl:
                        rows.extend(tbl)
                if rows:
                    df = pd.DataFrame(rows[1:], columns=rows[0])

        if not df.empty:
            original_columns = list(df.columns)
            df = normalize_columns(df, logs)
            status = route_and_save(df, filename, user_id, logs, original_columns)
            return {"status": status, "logs": logs}

        return {"status": "Skipped", "logs": logs + ["⚠️ Empty File or No Data Extracted"]}

    except Exception as e:
        return {"status": "Failed", "logs": logs + [f"❌ Error: {str(e)}"]}
