import pandas as pd
import numpy as np
from datetime import timedelta
from sqlalchemy import text
from .database import engine

def run_recon_engine():
    try:
        # Load Data
        trades = pd.read_sql("SELECT * FROM broker_trades", engine)
        cash = pd.read_sql("SELECT * FROM bank_txns", engine)
        holdings = pd.read_sql("SELECT * FROM holdings", engine)
        nav = pd.read_sql("SELECT * FROM nav_logs", engine)
    except Exception as e:
        print("Recon DB error:", e)
        return []

    # --- PRE-PROCESSING FOR SPEED ---
    # Convert dates once (expensive operation)
    trades['date_dt'] = pd.to_datetime(trades['date'], errors='coerce')
    cash['date_dt'] = pd.to_datetime(cash['date'], errors='coerce')
    
    # Ensure floats
    trades['amount'] = pd.to_numeric(trades['amount'], errors='coerce').fillna(0)
    cash['amount'] = pd.to_numeric(cash['amount'], errors='coerce').fillna(0)

    # SORT CASH BY AMOUNT (Crucial for Binary Search)
    cash = cash.sort_values(by='amount').reset_index(drop=True)
    cash_amounts = cash['amount'].values # numpy array for speed

    matches = []
    matched_cash_indices = set() # To prevent double-spending cash

    # --- 1. LIGHTNING FAST TRADES RECON ---
    if not trades.empty and not cash.empty:
        for i, t_row in trades.iterrows():
            target_amt = t_row['amount']
            if target_amt == 0: continue

            # Define Tolerance (1%)
            min_amt = target_amt * 0.99
            max_amt = target_amt * 1.01

            # BINARY SEARCH: Find the range of indices in 'cash' that match the amount
            # This replaces the slow "cash[...]" filter
            start_idx = np.searchsorted(cash_amounts, min_amt, side='left')
            end_idx = np.searchsorted(cash_amounts, max_amt, side='right')

            # Only check the small slice of candidates
            found_match = False
            
            # Iterate through potential candidates (usually just 1 or 2 rows)
            for cash_idx in range(start_idx, end_idx):
                if cash_idx in matched_cash_indices:
                    continue # Already used

                c_row = cash.iloc[cash_idx]
                
                # Check Date Match (Exact or T+2)
                date_diff = abs((c_row['date_dt'] - t_row['date_dt']).days)
                
                if date_diff <= 2:
                    # MATCH FOUND
                    status = "✅ SETTLED" if date_diff == 0 else f"⚠️ T+{date_diff} SETTLED"
                    matches.append({
                        "id": f"tr_{i}",
                        "timestamp": str(t_row["date"]),
                        "security": t_row["symbol"],
                        "bank_ref": c_row["description"],
                        "amount": t_row["amount"],
                        "status": status,
                    })
                    matched_cash_indices.add(cash_idx)
                    found_match = True
                    break # Stop looking for this trade
            
            if not found_match:
                matches.append({
                    "id": f"tr_{i}",
                    "timestamp": str(t_row["date"]),
                    "security": t_row["symbol"],
                    "bank_ref": "NO CASH ENTRY",
                    "amount": t_row["amount"],
                    "status": "❌ UNSETTLED",
                })

    # --- 2. HOLDINGS CHECK (Vectorized) ---
    if not holdings.empty:
        # Create a set of valid symbols for O(1) lookup
        valid_symbols = set(trades['symbol'].unique()) if not trades.empty else set()
        
        for i, row in holdings.iterrows():
            status = "✅ VERIFIED" if row["symbol"] in valid_symbols else "⚠️ LEGACY POS"
            matches.append({
                "id": f"hld_{i}",
                "timestamp": "PORTFOLIO",
                "security": row["symbol"],
                "bank_ref": f"Qty: {row['quantity']}",
                "amount": row["total_value"],
                "status": status,
            })

    # --- 3. NAV AUDIT ---
    if not nav.empty and not holdings.empty:
        # Merge logic is faster than looping
        merged = pd.merge(nav, holdings, on='isin', how='inner', suffixes=('_nav', '_hld'))
        
        for i, row in merged.iterrows():
            qty = float(row['quantity'] or 0)
            nav_val = float(row['nav_value'] or 0)
            calc_val = qty * nav_val
            
            matches.append({
                "id": f"nav_{i}",
                "timestamp": str(row["date_nav"]),
                "security": f"NAV CHECK: {row['isin']}",
                "bank_ref": f"NAV: {nav_val}",
                "amount": calc_val,
                "status": "✅ NAV MATCH",
            })

    return matches