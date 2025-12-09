# backend/ingestion.py
"""
AI-Native Ingestion Pipeline for Aureon.

This module uses Gemini 2.5 Flash Lite for intelligent column mapping,
falling back to deterministic rules when AI is unavailable or fails.
"""
import io
import pandas as pd
import pdfplumber
import zipfile
import numpy as np
import logging
from datetime import datetime
from sqlalchemy import text
from .database import engine
from .ai_schema import get_smart_mapping  # AI-first mapping

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
REQUIRED_COLS = {
    "trade": ["date", "symbol", "side", "quantity", "price"],
    "cash": ["date", "amount"],
    "holding": ["symbol", "quantity"],
    "nav": ["date"],
}

NUMERIC_COLS = [
    "amount", "price", "quantity", "nav_value", 
    "aum", "total_value", "avg_cost", "market_price",
    "val_inr", "mkt_val", "market_val"  # Added common variants
]

# --- ROBUST FALLBACK MAP (Corporate Standard) ---
# Used when AI mapping is unavailable or returns empty
STANDARD_MAP = {
    "date": ["date", "trade_date", "value_date", "txn_date", "time", "timestamp", "dt", "trd_dt", "as_of_date", "asof"],
    "amount": ["amount", "net_amount", "value", "txn_amount", "credit", "debit", "net_val", "total", "val_inr", "mkt_val"],
    "symbol": ["symbol", "ticker", "security", "instrument", "description", "narrative", "details", "scrip", "stock", "security_name", "name"],
    "side": ["side", "buy/sell", "direction", "bs", "txn_type"],
    "price": ["price", "unit_price", "rate", "mkt_price", "market_price", "avg_cost", "avg_price", "nav"],
    "isin": ["isin", "id", "ref", "isin_code", "security_id"],
    "quantity": ["quantity", "qty", "units", "shares", "balance_qty", "closing_qty", "qty_allocated", "holding_qty"],
    "fund_name": ["fund_name", "scheme_name", "fund", "scheme", "portfolio_name"],
    "nav_value": ["nav", "nav_value", "closing_nav", "net_asset_value"],
    "total_value": ["total_value", "market_value", "val_inr", "mkt_val", "portfolio_value", "holding_value"]
}

# -------------------------------------------------------------------
# 1) VALIDATION / CLEANUP
# -------------------------------------------------------------------
def validate_row_integrity(df: pd.DataFrame, file_type: str, logs: list) -> pd.DataFrame:
    """
    Validates and cleans dataframe rows.
    
    AI-native approach: We're more lenient with validation since Gemini
    will have already mapped columns. We only fail on truly critical issues.
    """
    initial_count = len(df)
    required = REQUIRED_COLS.get(file_type, [])
    
    missing = [col for col in required if col not in df.columns]

    if missing:
        if file_type == "trade":
            # For trades, we need at least date and symbol/amount
            critical_missing = [c for c in missing if c in ["date", "symbol"]]
            if critical_missing:
                logs.append(f"[ERROR] Critical: Missing columns for {file_type}: {critical_missing}")
                return pd.DataFrame()
            else:
                logs.append(f"[WARNING] Missing columns for {file_type}: {missing}. Will attempt to fill.")
        elif file_type == "cash":
            # For cash, we need date and amount
            if "amount" in missing and "date" in missing:
                logs.append(f"[ERROR] Critical: Missing both date and amount for cash")
                return pd.DataFrame()
            else:
                logs.append(f"[WARNING] Missing columns for {file_type}: {missing}. Will attempt to fill.")
        elif file_type in ("holding", "nav"):
            # For holdings/NAV, be lenient - AI mapping should have handled most cases
            logs.append(f"[INFO] Missing standard columns for {file_type}: {missing}. Proceeding with available data.")

    # Drop completely empty rows
    df = df.dropna(how="all")
    
    # Drop rows that are likely header duplicates (all string values matching column names)
    if len(df) > 1:
        first_row = df.iloc[0]
        cols_lower = [str(c).lower() for c in df.columns]
        first_vals_lower = [str(v).lower() if pd.notna(v) else "" for v in first_row]
        
        # If first row looks like a duplicate header, drop it
        if sum(1 for a, b in zip(cols_lower, first_vals_lower) if a == b) > len(cols_lower) * 0.5:
            df = df.iloc[1:]
            logs.append("[INFO] Dropped duplicate header row")

    # Validate dates - drop future dates
    if "date" in df.columns:
        try:
            temp = pd.to_datetime(df["date"], errors="coerce")
            future_mask = temp > datetime.now()
            if future_mask.any():
                logs.append(f"[WARNING] Dropped {future_mask.sum()} rows with future dates.")
                df = df[~future_mask]
        except Exception:
            pass  # If date parsing fails entirely, let it through

    final_count = len(df)
    if final_count < initial_count:
        logs.append(f"[INFO] Cleaned {initial_count - final_count} invalid/empty rows.")
    
    logs.append(f"[INFO] Validated {final_count} rows for {file_type}")
    return df


def run_data_quality_checks(df: pd.DataFrame, file_type: str, logs: list) -> pd.DataFrame:
    """
    AI-Native Data Quality Checks.
    
    Detects stress test issues:
    - Weekend trading
    - Negative prices
    - Missing identifiers
    - Suspense transactions
    - NAV spikes
    """
    issues_found = []
    
    # 1. WEEKEND TRADING DETECTION
    if "date" in df.columns:
        try:
            dates = pd.to_datetime(df["date"], errors="coerce")
            # weekday() returns 5 for Saturday, 6 for Sunday
            weekend_mask = dates.dt.weekday.isin([5, 6])
            weekend_count = weekend_mask.sum()
            
            if weekend_count > 0:
                weekend_dates = dates[weekend_mask].dt.strftime("%Y-%m-%d (%A)").unique()[:3]
                issues_found.append(f"🚨 WEEKEND TRADING: {weekend_count} trades on market closed days: {list(weekend_dates)}")
                df.loc[weekend_mask, "_dq_flag"] = "WEEKEND_TRADE"
        except Exception as e:
            logger.debug(f"Weekend check failed: {e}")
    
    # 2. NEGATIVE PRICE DETECTION
    if "price" in df.columns:
        price_col = pd.to_numeric(df["price"], errors="coerce")
        negative_mask = price_col < 0
        negative_count = negative_mask.sum()
        
        if negative_count > 0:
            symbols = df.loc[negative_mask, "symbol"].unique()[:3] if "symbol" in df.columns else ["?"]
            issues_found.append(f"🚨 NEGATIVE PRICES: {negative_count} rows with negative prices: {list(symbols)}")
            df.loc[negative_mask, "_dq_flag"] = "NEGATIVE_PRICE"
    
    # 3. EXTREME PRICE OUTLIER DETECTION
    if "price" in df.columns:
        price_col = pd.to_numeric(df["price"], errors="coerce")
        # Flag prices > 50,000 as potential errors (unusual for Indian equities)
        extreme_mask = price_col > 50000
        extreme_count = extreme_mask.sum()
        
        if extreme_count > 0:
            symbols = df.loc[extreme_mask, "symbol"].unique()[:3] if "symbol" in df.columns else ["?"]
            prices = df.loc[extreme_mask, "price"].unique()[:3]
            issues_found.append(f"⚠️ PRICE OUTLIER: {extreme_count} rows with extreme prices (>50000): {list(symbols)} @ {list(prices)}")
    
    # 4. MISSING IDENTIFIER DETECTION
    if file_type in ("trade", "holding"):
        symbol_missing = df["symbol"].isna() | (df["symbol"].astype(str).str.strip() == "") if "symbol" in df.columns else pd.Series([True] * len(df))
        isin_missing = df["isin"].isna() | (df["isin"].astype(str).str.strip() == "") if "isin" in df.columns else pd.Series([True] * len(df))
        
        no_id_mask = symbol_missing & isin_missing
        no_id_count = no_id_mask.sum()
        
        if no_id_count > 0:
            issues_found.append(f"🚨 MISSING IDENTIFIER: {no_id_count} rows with no symbol or ISIN")
            df.loc[no_id_mask, "_dq_flag"] = "MISSING_ID"
    
    # 5. SUSPENSE TRANSACTION DETECTION (for cash/bank files)
    if file_type == "cash" and "description" in df.columns:
        desc_upper = df["description"].astype(str).str.upper()
        suspense_keywords = ["SUSPENSE", "UNIDENTIFIED", "UNKNOWN", "PENDING INVESTIGATION"]
        
        suspense_mask = desc_upper.str.contains("|".join(suspense_keywords), na=False)
        suspense_count = suspense_mask.sum()
        
        if suspense_count > 0:
            amounts = df.loc[suspense_mask, "amount"].sum() if "amount" in df.columns else 0
            issues_found.append(f"🚨 SUSPENSE TRANSACTIONS: {suspense_count} suspicious entries totaling ₹{amounts:,.2f}")
            df.loc[suspense_mask, "_dq_flag"] = "SUSPENSE"
    
    # 6. NAV SPIKE DETECTION (for NAV files)
    if file_type == "nav" and "nav_value" in df.columns:
        nav_col = pd.to_numeric(df["nav_value"], errors="coerce")
        
        # Flag NAVs > 10,000 as potential glitches
        spike_mask = nav_col > 10000
        spike_count = spike_mask.sum()
        
        if spike_count > 0:
            funds = df.loc[spike_mask, "fund_name"].unique()[:3] if "fund_name" in df.columns else ["?"]
            nav_vals = df.loc[spike_mask, "nav_value"].unique()[:3]
            issues_found.append(f"🚨 NAV GLITCH: {spike_count} records with abnormal NAV (>10000): {list(funds)} @ {list(nav_vals)}")
            df.loc[spike_mask, "_dq_flag"] = "NAV_SPIKE"
    
    # 7. LARGE WITHDRAWAL DETECTION
    if file_type == "cash" and "amount" in df.columns:
        amount_col = pd.to_numeric(df["amount"], errors="coerce")
        large_debit_mask = amount_col < -500000  # Large debits
        large_count = large_debit_mask.sum()
        
        if large_count > 0:
            amounts = df.loc[large_debit_mask, "amount"].tolist()[:3]
            issues_found.append(f"⚠️ LARGE WITHDRAWALS: {large_count} debits exceeding ₹500,000: {amounts}")
    
    # Log all issues found
    if issues_found:
        logs.append(f"[DQ] 🔍 Data Quality Analysis for {file_type}:")
        for issue in issues_found:
            logs.append(f"[DQ] {issue}")
        logs.append(f"[DQ] Total issues: {len(issues_found)} categories flagged")
    else:
        logs.append(f"[DQ] ✅ No major data quality issues detected for {file_type}")
    
    return df


def normalize_columns(df: pd.DataFrame, logs: list) -> pd.DataFrame:
    """
    AI-FIRST column normalization.
    
    Strategy:
    1. First ask Gemini 2.5 Flash Lite for intelligent mapping
    2. Fall back to deterministic rules if AI fails
    3. Apply critical logic patches for edge cases
    """
    original_headers = [str(c).strip() for c in df.columns]
    
    # --- STEP 1: Standardize column names (lowercase, underscores) ---
    def std(x: str) -> str:
        return str(x).strip().lower().replace(" ", "_").replace(".", "").replace("/", "_").replace("-", "_")
    
    df.columns = [std(c) for c in df.columns]
    standardized_headers = list(df.columns)
    
    # --- STEP 2: AI-FIRST MAPPING (Gemini 2.5 Flash Lite) ---
    ai_map = {}
    try:
        logs.append(f"[AI] 🤖 Analyzing {len(original_headers)} columns with Gemini...")
        ai_map = get_smart_mapping(original_headers)
        
        if ai_map:
            # Convert AI map keys to standardized format for matching
            clean_map = {}
            seen_targets = set()
            
            for source, target in ai_map.items():
                # Standardize the source key to match our column names
                std_source = std(source)
                
                # Only map if we haven't already mapped to this target
                if target not in seen_targets and std_source in df.columns:
                    clean_map[std_source] = target
                    seen_targets.add(target)
            
            if clean_map:
                logs.append(f"[AI] ✅ Gemini Mappings Applied: {clean_map}")
                df = df.rename(columns=clean_map)
        else:
            logs.append("[AI] ⚠️ Gemini returned empty mapping, using deterministic fallback")
            
    except Exception as e:
        logs.append(f"[AI] ⚠️ Gemini unavailable ({str(e)[:50]}), using deterministic fallback")
    
    # --- STEP 3: DETERMINISTIC FALLBACK (fill gaps AI didn't cover) ---
    rename_map = {}
    for standard_col, candidates in STANDARD_MAP.items():
        # Skip if AI already mapped this column
        if standard_col in df.columns:
            continue
        
        for col in df.columns:
            # Skip columns that are already standard
            if col in STANDARD_MAP:
                continue
                
            # Match if column name is in candidates or contains a candidate substring
            if col in candidates or any(c in col for c in candidates if len(c) > 2):
                rename_map[col] = standard_col
                break
    
    if rename_map:
        logs.append(f"[FALLBACK] Applied Deterministic Map: {rename_map}")
        df = df.rename(columns=rename_map)
    
    # --- STEP 4: Critical Logic Patches ---
    # Symbol fallbacks
    if "symbol" not in df.columns:
        if "isin" in df.columns:
            df["symbol"] = df["isin"]
            logs.append("[PATCH] Created 'symbol' from 'isin'")
        elif "security_name" in df.columns:
            df["symbol"] = df["security_name"]
            logs.append("[PATCH] Created 'symbol' from 'security_name'")
    
    # Amount fallbacks
    if "amount" not in df.columns:
        if "net_amount" in df.columns:
            df["amount"] = df["net_amount"]
            logs.append("[PATCH] Created 'amount' from 'net_amount'")
        elif "val_inr" in df.columns:
            df["amount"] = df["val_inr"]
            logs.append("[PATCH] Created 'amount' from 'val_inr'")
        elif "mkt_val" in df.columns:
            df["amount"] = df["mkt_val"]
            logs.append("[PATCH] Created 'amount' from 'mkt_val'")
    
    # Total value for holdings (critical for AUC)
    if "total_value" not in df.columns:
        if "val_inr" in df.columns:
            df["total_value"] = df["val_inr"]
            logs.append("[PATCH] Created 'total_value' from 'val_inr'")
        elif "mkt_val" in df.columns:
            df["total_value"] = df["mkt_val"]
            logs.append("[PATCH] Created 'total_value' from 'mkt_val'")
        elif "market_value" in df.columns:
            df["total_value"] = df["market_value"]
            logs.append("[PATCH] Created 'total_value' from 'market_value'")
    
    # Description fallback
    if "description" not in df.columns:
        if "narrative" in df.columns:
            df["description"] = df["narrative"]
        elif "details" in df.columns:
            df["description"] = df["details"]
        elif "symbol" in df.columns:
            df["description"] = df["symbol"]
    
    # NAV value fallback
    if "nav_value" not in df.columns and "nav" in df.columns:
        df["nav_value"] = df["nav"]
        logs.append("[PATCH] Created 'nav_value' from 'nav'")
    
    logs.append(f"[INFO] Final columns: {list(df.columns)}")
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

    # --- DETERMINE FILE TYPE FOR DQ CHECKS ---
    if "nav" in filename:
        file_type = "nav"
    elif any(x in filename for x in ["holding", "portfolio", "position", "dp_", "nsdl", "cdsl"]):
        file_type = "holding"
    elif any(x in filename for x in ["cash", "ledger", "bank", "txn"]):
        file_type = "cash"
    else:
        file_type = "trade"
    
    # --- RUN DATA QUALITY CHECKS ---
    df = run_data_quality_checks(df, file_type, logs)

    try:
        # A. NAV (Fund NAV reports)
        if "nav" in filename:
            df = validate_row_integrity(df, "nav", logs)
            if df.empty: 
                logs.append("[ERROR] NAV validation failed - check required columns")
                return "Failed Validation"
            
            logs.append(f"[DEBUG] Available columns for NAV: {list(df.columns)}")
            
            # Map nav_value from various sources
            if "nav_value" not in df.columns:
                nav_sources = ["nav", "closing_nav", "net_asset_value", "unit_nav"]
                for source in nav_sources:
                    if source in df.columns:
                        df["nav_value"] = df[source]
                        logs.append(f"[PATCH] Created 'nav_value' from '{source}'")
                        break
            
            # Map fund_name from various sources
            if "fund_name" not in df.columns:
                fund_sources = ["scheme_name", "scheme", "fund", "portfolio", "mf_name"]
                for source in fund_sources:
                    if source in df.columns:
                        df["fund_name"] = df[source]
                        logs.append(f"[PATCH] Created 'fund_name' from '{source}'")
                        break
            
            # Ensure all columns exist
            cols = ["isin", "date", "nav_value", "fund_name", "aum", "source_file"]
            for c in cols:
                if c not in df.columns:
                    df[c] = 0.0 if c in NUMERIC_COLS else ""
            
            # Clean and validate NAV values
            df["nav_value"] = pd.to_numeric(df["nav_value"], errors="coerce").fillna(0.0)
            df["aum"] = pd.to_numeric(df["aum"], errors="coerce").fillna(0.0)
            
            df["tenant_id"] = user_id
            
            # Filter out rows with zero NAV (likely header rows or invalid data)
            valid_nav = df[df["nav_value"] > 0]
            
            if valid_nav.empty:
                logs.append("[WARNING] No valid NAV values found after filtering")
                # Still save all rows for audit trail
                df[cols + ["tenant_id"]].to_sql("nav_logs", sync_engine, if_exists="append", index=False)
            else:
                valid_nav[cols + ["tenant_id"]].to_sql("nav_logs", sync_engine, if_exists="append", index=False)
            
            nav_count = len(valid_nav) if not valid_nav.empty else len(df)
            total_aum = df["aum"].sum()
            logs.append(f"[SUCCESS] NAV Data Committed: {nav_count} records, Total AUM: {total_aum:,.2f}")
            return "NAV Logs"

        # B. HOLDINGS (Critical for AUC calculation)
        elif any(x in filename for x in ["holding", "portfolio", "position", "dp_", "nsdl", "cdsl"]):
            df = validate_row_integrity(df, "holding", logs)
            if df.empty: 
                logs.append("[ERROR] Holdings validation failed - check required columns")
                return "Failed Validation"

            # --- COMPREHENSIVE VALUE MAPPING FOR AUC ---
            logs.append(f"[DEBUG] Available columns for holdings: {list(df.columns)}")
            
            # 1. Try multiple sources for total_value (in priority order)
            value_sources = ["total_value", "val_inr", "mkt_val", "market_value", 
                           "amount", "value", "portfolio_value", "holding_value"]
            
            if "total_value" not in df.columns:
                for source in value_sources:
                    if source in df.columns:
                        df["total_value"] = df[source]
                        logs.append(f"[PATCH] Created 'total_value' from '{source}'")
                        break
            
            # 2. Try multiple sources for market_price
            price_sources = ["market_price", "mkt_price", "price", "ltp", "last_price", "current_price"]
            if "market_price" not in df.columns:
                for source in price_sources:
                    if source in df.columns:
                        df["market_price"] = df[source]
                        logs.append(f"[PATCH] Created 'market_price' from '{source}'")
                        break
            
            # 3. Calculate total_value if still missing but we have qty and price
            if "total_value" not in df.columns or df["total_value"].sum() == 0:
                qty_col = df.get("quantity", pd.Series([0.0]))
                price_col = df.get("market_price", pd.Series([0.0]))
                
                if qty_col.sum() > 0 and price_col.sum() > 0:
                    df["total_value"] = qty_col * price_col
                    logs.append(f"[CALC] Computed total_value = quantity × market_price")
            
            # 4. Ensure total_value column exists with at least zeros
            if "total_value" not in df.columns:
                df["total_value"] = 0.0
                logs.append("[WARNING] No value source found - total_value set to 0")
            
            # Log summary for debugging
            total_auc = df["total_value"].sum() if "total_value" in df.columns else 0
            logs.append(f"[INFO] Holdings total value (AUC contribution): {total_auc:,.2f}")
            
            mode = decide_holdings_mode(df, filename, user_id, logs)
            logs.append(f"[INFO] Merging Positions with mode = {mode.upper()}")

            rows_inserted = 0
            with sync_engine.begin() as conn:
                if mode == "overwrite":
                    conn.execute(text("DELETE FROM holdings WHERE tenant_id = :tid"), {"tid": user_id})
                    logs.append("[INFO] Cleared existing holdings for overwrite")
                
                for _, row in df.iterrows():
                    symbol = row.get("symbol", "")
                    if not symbol or symbol == "":
                        symbol = row.get("isin", "UNKNOWN")
                    
                    qty = float(row.get("quantity", 0) or 0)
                    val = float(row.get("total_value", 0) or 0)
                    
                    # Skip rows with no meaningful data
                    if qty == 0 and val == 0:
                        continue
                    
                    conn.execute(text("""
                        INSERT INTO holdings (date, isin, symbol, quantity, avg_cost, market_price, total_value, source_file, tenant_id)
                        VALUES (:date, :isin, :symbol, :qty, :cost, :price, :val, :src, :tid)
                        ON CONFLICT (symbol, tenant_id) DO UPDATE SET
                            quantity = CASE WHEN :mode = 'overwrite' THEN EXCLUDED.quantity ELSE holdings.quantity + EXCLUDED.quantity END,
                            total_value = CASE WHEN :mode = 'overwrite' THEN EXCLUDED.total_value ELSE holdings.total_value + EXCLUDED.total_value END,
                            market_price = EXCLUDED.market_price,
                            date = EXCLUDED.date
                    """), {
                        "date": row.get("date") or datetime.now().date(),
                        "isin": str(row.get("isin", "") or ""),
                        "symbol": symbol,
                        "qty": qty,
                        "cost": float(row.get("avg_cost", 0) or 0),
                        "price": float(row.get("market_price", 0) or 0),
                        "val": val,
                        "src": filename,
                        "tid": user_id,
                        "mode": mode
                    })
                    rows_inserted += 1
            
            logs.append(f"[SUCCESS] Holdings Merge Complete: {rows_inserted} positions saved")
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

            cols = ["date", "settlement_date", "symbol", "amount", "price", "quantity", "side", "isin", "currency", "source_file", "status"]
            for c in cols:
                if c not in df.columns:
                    if c == "status":
                        df[c] = "UNSETTLED"  # Default status for new trades
                    else:
                        df[c] = 0.0 if c in NUMERIC_COLS else (None if "date" in c else "")

            df["tenant_id"] = user_id
            
            # Ensure status is set for reconciliation
            df["status"] = df.get("status", "UNSETTLED").fillna("UNSETTLED")
            
            trade_count = len(df)
            df[cols + ["tenant_id"]].to_sql("broker_trades", sync_engine, if_exists="append", index=False)
            logs.append(f"[SUCCESS] Trade Blotter Imported: {trade_count} trades with UNSETTLED status")
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