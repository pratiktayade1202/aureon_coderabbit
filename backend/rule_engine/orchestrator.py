# backend/rule_engine/orchestrator.py

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date

# Import the Generic Engine
from .core.engine import ReconciliationEngine

# Import your Specific Database Models
from ..models import (
    BrokerTrade, 
    BankTxn, 
    Holding, 
    ReconBreak, 
    ReconStatus, 
    BreakSeverity
)

class ReconOrchestrator:
    """
    The Bridge between the Database and the Logic.
    NOW INCLUDES: Phase 1 (Heuristic Matching) -> Phase 2 (Rule Validation).
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.engine = ReconciliationEngine() 

    def _model_to_dict(self, obj: Any) -> Dict[str, Any]:
        data = {}
        for column in obj.__table__.columns:
            val = getattr(obj, column.name)
            # Normalize common fields for rules
            if column.name == 'amount': 
                data['net_amount'] = float(val or 0)
            if column.name == 'date': 
                data['settlement_date'] = val
            data[column.name] = val
        return data

    def _get_severity_enum(self, severity_str: str) -> BreakSeverity:
        try:
            return BreakSeverity[severity_str.upper()]
        except (KeyError, AttributeError):
            return BreakSeverity.MEDIUM

    def run_trade_recon(self, run_date: date = None) -> Dict[str, Any]:
        """
        Two-Step Reconciliation:
        1. Heuristic Matching (Pandas/NumPy) -> Aligns Trades to Cash
        2. Rule Validation (Aureon Engine) -> Checks strict compliance
        """
        # --- STEP 1: FETCH DATA (Multi-tenant scoped) ---
        trades = self.db.query(BrokerTrade).filter(
            BrokerTrade.tenant_id == self.tenant_id,
            BrokerTrade.status.in_([ReconStatus.UNSETTLED, "UNSETTLED", None])
        ).all()
        
        bank_txns = self.db.query(BankTxn).filter(
            BankTxn.tenant_id == self.tenant_id,
            BankTxn.status.in_(["UNUSED", None])
        ).all()

        if not trades:
            return {"status": "SKIPPED", "message": "No trades to reconcile"}

        logging.info(f"Orchestrator: Processing {len(trades)} trades and {len(bank_txns)} cash entries.")

        # --- STEP 2: HEURISTIC ALIGNMENT (The "Matcher" from v0) ---
        aligned_trades = []
        aligned_cash = []
        matched_cash_ids = set()

        # Prepare Cash Dataframe for Binary Search
        if bank_txns:
            df_cash = pd.DataFrame([b.__dict__ for b in bank_txns])
            # Handle SQLAlchemy state object if present
            if '_sa_instance_state' in df_cash.columns:
                del df_cash['_sa_instance_state']
                
            df_cash['amount'] = pd.to_numeric(df_cash['amount'], errors='coerce').fillna(0)
            df_cash = df_cash.sort_values(by='amount') # Crucial for binary search
            
            cash_amounts = df_cash['amount'].values
            cash_objs = df_cash.to_dict('records') # List of dicts
        else:
            cash_amounts = np.array([])
            cash_objs = []

        # Iterate Trades and Find Best Candidate
        for trade in trades:
            t_data = self._model_to_dict(trade)
            target = abs(float(t_data.get('amount') or 0))
            
            match_found = None
            
            if len(cash_amounts) > 0 and target > 0:
                # 1% Tolerance Search Window
                idx_start = np.searchsorted(cash_amounts, target * 0.99, side='left')
                idx_end = np.searchsorted(cash_amounts, target * 1.01, side='right')
                
                # Check candidates in the window
                for i in range(idx_start, idx_end):
                    c_data = cash_objs[i]
                    c_id = c_data.get('id')
                    
                    if c_id in matched_cash_ids:
                        continue
                        
                    # Loose Date Check (Allow T+3 for Candidate Selection)
                    match_found = c_data
                    matched_cash_ids.add(c_id)
                    break
            
            # Align the data
            aligned_trades.append(t_data)
            aligned_cash.append(match_found if match_found else {}) 

        # --- STEP 3: RUN THE RULE ENGINE (The "Validator") ---
        report = self.engine.run(
            dataset_a=aligned_trades, 
            dataset_b=aligned_cash, 
            metadata={
                "tenant_id": self.tenant_id,
                "domain": "TRADE_CASH"
            }
        )

        # --- STEP 4: APPLY RESULTS ---
        self._apply_trade_results(report, aligned_trades, aligned_cash)
        
        return report

    def _apply_trade_results(self, report: Dict, trades_data: List[Dict], cash_data: List[Dict]):
        """
        Updates Status in DB based on Engine Results.
        """
        broken_trade_ids = set()
        
        # 1. Process Breaks (Failed Validation)
        for brk in report["breaks"]:
            t_id = brk.get("details", {}).get("id")
            if t_id:
                broken_trade_ids.add(t_id)
                self._create_db_break(brk, trade_id=t_id)

        # 2. Process Matches (Passed Validation)
        for i, t_data in enumerate(trades_data):
            t_id = t_data.get('id')
            c_data = cash_data[i]
            c_id = c_data.get('id') if c_data else None
            
            if t_id and t_id not in broken_trade_ids:
                if c_id:
                    # PERFECT MATCH
                    self.db.execute(
                        text("UPDATE broker_trades SET status = 'MATCHED', bank_ref = :ref WHERE id = :id"),
                        {"ref": f"Matched to Cash {c_id}", "id": t_id}
                    )
                    self.db.execute(
                        text("UPDATE bank_txns SET status = 'MATCHED' WHERE id = :id"),
                        {"id": c_id}
                    )
                else:
                    # No Cash Candidate was found (Missing Cash)
                    pass

        self.db.commit()

    def _create_db_break(self, break_data: Dict, trade_id: int = None, cash_id: int = None):
        existing = self.db.query(ReconBreak).filter_by(
            rule_id=break_data["rule_id"],
            trade_id=trade_id,
            tenant_id=self.tenant_id,
            status="OPEN"
        ).first()

        if existing: return

        sev_enum = self._get_severity_enum(break_data.get("severity", "MEDIUM"))

        new_break = ReconBreak(
            tenant_id=self.tenant_id,
            trade_id=trade_id,
            cash_id=cash_id,
            rule_id=break_data["rule_id"],
            break_type=break_data.get("break_type", "UNKNOWN"),
            severity=sev_enum,
            amount_diff=break_data.get("amount_diff", 0.0),
            status="OPEN",
            resolution_note=f"AUTO: {break_data.get('message', '')}"
        )
        self.db.add(new_break)

    def get_frontend_trade_view(self) -> List[Dict]:
        """
        CRITICAL: Maps DB models to the specific JSON shape 
        expected by frontend/src/components/DataTable.jsx
        """
        trades = self.db.query(BrokerTrade).filter(
            BrokerTrade.tenant_id == self.tenant_id
        ).order_by(BrokerTrade.date.desc()).all()

        results = []
        for t in trades:
            # STATUS MAPPING for Badge Colors
            display_status = t.status
            if t.status == "UNSETTLED":
                # Check if it has an open break
                has_break = self.db.query(ReconBreak).filter_by(trade_id=t.id, status="OPEN").first()
                if has_break:
                    display_status = f"❌ {has_break.break_type}"

            results.append({
                "id": t.id,
                "timestamp": str(t.date),  # DataTable expects "timestamp" for Date
                "security": t.symbol,      # DataTable expects "security"
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "amount": t.amount,
                "status": display_status,
                "bank_ref": t.bank_ref
            })
        return results