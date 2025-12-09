# backend/rule_engine/orchestrator.py
"""
Production-ready reconciliation orchestrator with transaction safety.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from decimal import Decimal
import uuid

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

# Import financial utilities
from ..utils.financial import to_decimal, get_financial_value, calculate_total_value
from ..utils.accessors import get_value, to_date

logger = logging.getLogger(__name__)

class ReconOrchestrator:
    """
    The Bridge between the Database and the Logic.
    Production-ready with transaction safety and proper error handling.
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.engine = ReconciliationEngine()
        self.run_id = str(uuid.uuid4())[:8]  # Unique ID for this reconciliation run
        logger.info(f"Orchestrator initialized for tenant {tenant_id}, run {self.run_id}")

    def _model_to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        Safely convert SQLAlchemy model to dictionary.
        
        Args:
            obj: SQLAlchemy model instance
            
        Returns:
            Dict with model data
        """
        data = {}
        if obj is None:
            return data
        
        for column in obj.__table__.columns:
            try:
                val = getattr(obj, column.name)
                
                # Handle Decimal serialization
                if isinstance(val, Decimal):
                    val = float(val)
                
                # Handle date serialization
                elif isinstance(val, (date, datetime)):
                    val = val.isoformat()
                
                data[column.name] = val
                
                # Add normalized fields for rule engine
                if column.name == 'amount':
                    data['net_amount'] = float(to_decimal(val))
                if column.name == 'date':
                    data['settlement_date'] = val
                    
            except Exception as e:
                logger.warning(f"Error accessing column {column.name}: {str(e)}")
                data[column.name] = None
        
        return data

    def _get_severity_enum(self, severity_str: str) -> BreakSeverity:
        """
        Convert severity string to enum.
        
        Args:
            severity_str: Severity string
            
        Returns:
            BreakSeverity enum
        """
        try:
            return BreakSeverity[severity_str.upper()]
        except (KeyError, AttributeError):
            logger.warning(f"Unknown severity: {severity_str}, defaulting to MEDIUM")
            return BreakSeverity.MEDIUM

    def _log_reconciliation_event(self, event_type: str, details: Dict[str, Any]):
        """
        Log reconciliation event for audit trail.
        
        Args:
            event_type: Type of event
            details: Event details
        """
        try:
            # Use ReconLog model
            from ..models import ReconLog
            log_entry = ReconLog(
                tenant_id=self.tenant_id,
                reason=f"{event_type}: {str(details)}",
                status_before="",
                status_after=event_type
            )
            self.db.add(log_entry)
            self.db.flush()  # Ensure it's written
        except Exception as e:
            logger.error(f"Failed to log event: {str(e)}")

    def run_trade_recon(self, run_date: date = None) -> Dict[str, Any]:
        """  
        Two-Step Reconciliation with transaction safety.
        
        Args:
            run_date: Date to reconcile (defaults to today)
        
        Returns:
            Dict with reconciliation results
        """  
        if run_date is None:
            run_date = date.today()
        
        self._log_reconciliation_event("RECON_STARTED", {"run_date": run_date.isoformat()})
        
        # Use transaction for data integrity
        try:
            # Start a fresh transaction
            self.db.rollback()  # Rollback any previous failed transaction
            
            # --- STEP 1: FETCH DATA (Multi-tenant scoped) ---
            # Include NULL status as UNSETTLED (common after fresh ingestion)
            trades = self.db.query(BrokerTrade).filter(
                BrokerTrade.tenant_id == self.tenant_id,
                BrokerTrade.status.in_([ReconStatus.UNSETTLED, "UNSETTLED", None]) | BrokerTrade.status.is_(None),
                BrokerTrade.date <= run_date
            ).all()
            
            # Also include NULL status for cash transactions
            cash_txns = self.db.query(BankTxn).filter(
                BankTxn.tenant_id == self.tenant_id,
                BankTxn.status.in_(["UNUSED", None]) | BankTxn.status.is_(None),
                BankTxn.date <= run_date
            ).all()
            
            logger.info(f"Reconciling {len(trades)} trades against {len(cash_txns)} cash transactions")
            
            # --- STEP 2: CONVERT TO DICTS ---
            trades_data = [self._model_to_dict(t) for t in trades]
            cash_data = [self._model_to_dict(c) for c in cash_txns]
            
            # Add IDs for tracking
            for i, t in enumerate(trades_data):
                t['id'] = trades[i].id
            for i, c in enumerate(cash_data):
                c['id'] = cash_txns[i].id
            
            # --- STEP 3: RUN RECONCILIATION ENGINE ---
            report = self.engine.run(trades_data, cash_data, metadata={
                "tenant_id": self.tenant_id,
                "run_date": run_date.isoformat(),
                "run_id": self.run_id
            })
            
            # --- STEP 4: APPLY RESULTS TO DATABASE ---
            self._apply_trade_results(report, trades_data, cash_data)
            
            # --- STEP 5: LOG SUCCESS ---
            self._log_reconciliation_event("RECON_COMPLETED", {
                "matches": report.get("matches", 0),
                "breaks": report.get("breaks", 0),
                "run_id": self.run_id
            })
            
            return {
                "status": "success",
                "matches": report.get("matches", 0),
                "breaks": report.get("breaks", 0),
                "run_id": self.run_id,
                "details": report
            }
            
        except Exception as e:
            self.db.rollback()  # Ensure transaction is rolled back on error
            logger.error(f"Reconciliation failed: {str(e)}", exc_info=True)
            self._log_reconciliation_event("RECON_FAILED", {"error": str(e)})
            raise

    def _apply_trade_results(self, report: Dict, trades_data: List[Dict], cash_data: List[Dict]):
        """
        Updates Status in DB based on Engine Results with transaction safety.
        """
        broken_trade_ids = set()
        matched_count = 0
        
        # 1. Process Breaks (Failed Validation)
        for brk in report.get("breaks", []):
            t_id = brk.get("details", {}).get("id")
            if t_id:
                broken_trade_ids.add(t_id)
                self._create_db_break(brk, trade_id=t_id)

        # 2. Process Matches from engine report
        matches = report.get("matches", [])
        if isinstance(matches, list):
            for match in matches:
                t_id = match.get("trade_id")
                c_id = match.get("cash_id")
                
                if t_id and c_id:
                    try:
                        # Update trade status
                        trade = self.db.query(BrokerTrade).filter_by(id=t_id, tenant_id=self.tenant_id).first()
                        if trade:
                            trade.status = "MATCHED"
                            trade.bank_ref = f"Matched to Cash {c_id} (Run: {self.run_id})"
                        
                        # Update cash transaction status
                        cash = self.db.query(BankTxn).filter_by(id=c_id, tenant_id=self.tenant_id).first()
                        if cash:
                            cash.status = "MATCHED"
                            cash.trade_ref = t_id
                        
                        matched_count += 1
                        
                        # Log the match
                        self._log_reconciliation_event("TRADE_MATCHED", {
                            "trade_id": t_id,
                            "cash_id": c_id,
                            "run_id": self.run_id,
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to update match for trade {t_id}: {str(e)}")
        
        # 3. Fallback: Try to match unmatched trades with available cash
        # This handles cases where engine returns just a count instead of match details
        if matched_count == 0 and len(trades_data) > 0 and len(cash_data) > 0:
            for t_data in trades_data:
                t_id = t_data.get('id')
                if t_id in broken_trade_ids:
                    continue
                
                t_amount = float(t_data.get('amount', 0) or t_data.get('net_amount', 0))
                
                # Find matching cash by amount (within tolerance)
                for c_data in cash_data:
                    c_id = c_data.get('id')
                    c_status = c_data.get('status', 'UNUSED')
                    
                    if c_status == 'MATCHED':
                        continue
                    
                    c_amount = abs(float(c_data.get('amount', 0)))
                    
                    # Match within 0.1% tolerance
                    if t_amount > 0 and abs(t_amount - c_amount) / t_amount < 0.001:
                        try:
                            trade = self.db.query(BrokerTrade).filter_by(id=t_id, tenant_id=self.tenant_id).first()
                            if trade and trade.status != "MATCHED":
                                trade.status = "MATCHED"
                                trade.bank_ref = f"Matched to Cash {c_id} (Run: {self.run_id})"
                                
                                cash = self.db.query(BankTxn).filter_by(id=c_id, tenant_id=self.tenant_id).first()
                                if cash:
                                    cash.status = "MATCHED"
                                    cash.trade_ref = t_id
                                
                                matched_count += 1
                                c_data['status'] = 'MATCHED'  # Mark as used in our local copy
                                break
                        except Exception as e:
                            logger.error(f"Fallback match error: {str(e)}")

        # 4. Update holdings based on matched trades
        self._update_holdings_from_matches(broken_trade_ids)
        
        # Commit all changes
        self.db.commit()
        logger.info(f"Applied {matched_count} matches")

    def _create_db_break(self, break_data: Dict, trade_id: int = None, cash_id: int = None):
        """
        Create reconciliation break record.
        """
        # Check if break already exists
        existing = self.db.query(ReconBreak).filter_by(
            rule_id=break_data.get("rule_id"),
            trade_id=trade_id,
            tenant_id=self.tenant_id,
            status="OPEN"
        ).first()

        if existing:
            # Update existing break
            existing.amount_diff = float(break_data.get("amount_diff", 0.0))
            existing.severity = self._get_severity_enum(break_data.get("severity", "MEDIUM"))
            existing.break_type = break_data.get("break_type", "UNKNOWN")
            return

        # Create new break
        sev_enum = self._get_severity_enum(break_data.get("severity", "MEDIUM"))
        
        new_break = ReconBreak(
            tenant_id=self.tenant_id,
            trade_id=trade_id,
            cash_id=cash_id,
            rule_id=break_data.get("rule_id", "UNKNOWN"),
            break_type=break_data.get("break_type", "UNKNOWN"),
            severity=sev_enum,
            amount_diff=float(break_data.get("amount_diff", 0.0)),
            status="OPEN",
            resolution_note=f"AUTO: {break_data.get('message', '')}",
        )
        self.db.add(new_break)
        
        # Log break creation
        self._log_reconciliation_event("BREAK_CREATED", {
            "trade_id": trade_id,
            "rule_id": new_break.rule_id,
            "severity": new_break.severity.value,
        })

    def _update_holdings_from_matches(self, broken_trade_ids: set):
        """
        Update holdings based on matched trades.
        """
        try:
            # Get all matched trades for this tenant
            matched_trades = self.db.query(BrokerTrade).filter(
                BrokerTrade.tenant_id == self.tenant_id,
                BrokerTrade.status == 'MATCHED',
                BrokerTrade.id.notin_(broken_trade_ids) if broken_trade_ids else True
            ).all()
            
            for trade in matched_trades:
                # Calculate position change
                quantity_change = to_decimal(trade.quantity)
                if trade.side in ['SELL', 'S', 'DEBIT', 'DR']:
                    quantity_change = -quantity_change
                
                # Get or create holding (use most recent date)
                holding = self.db.query(Holding).filter(
                    Holding.tenant_id == self.tenant_id,
                    Holding.symbol == trade.symbol
                ).order_by(Holding.date.desc()).first()
                
                if holding:
                    # Update existing holding
                    new_quantity = to_decimal(holding.quantity) + quantity_change
                    
                    # Don't allow negative holdings
                    if new_quantity < Decimal('0'):
                        logger.warning(f"Negative holding prevented for {trade.symbol}")
                        new_quantity = Decimal('0')
                    
                    holding.quantity = float(new_quantity)
                    holding.total_value = float(new_quantity * to_decimal(holding.market_price))
                    holding.date = date.today()  # Update to current date
                else:
                    # Create new holding
                    holding = Holding(
                        tenant_id=self.tenant_id,
                        date=date.today(),
                        symbol=trade.symbol,
                        isin=trade.isin,
                        quantity=float(quantity_change),
                        avg_cost=float(to_decimal(trade.price)),
                        market_price=float(to_decimal(trade.price)),
                        total_value=float(quantity_change * to_decimal(trade.price)),
                        source_file=trade.source_file,
                    )
                    self.db.add(holding)
                    
        except Exception as e:
            logger.error(f"Failed to update holdings: {str(e)}")

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
            display_status = t.status or "UNSETTLED"
            
            # Check if it has an open break
            if t.status == "UNSETTLED":
                has_break = self.db.query(ReconBreak).filter_by(
                    trade_id=t.id, 
                    status="OPEN"
                ).first()
                if has_break:
                    # Return structured data, not emoji string
                    display_status = {
                        "status": "BREAK",
                        "break_type": has_break.break_type,
                        "severity": has_break.severity.value,
                    }
                else:
                    display_status = {"status": "UNSETTLED"}
            else:
                display_status = {"status": t.status}

            results.append({
                "id": t.id,
                "timestamp": t.date.isoformat() if t.date else None,
                "security": t.symbol or "UNKNOWN",
                "side": t.side or "UNKNOWN",
                "quantity": float(to_decimal(t.quantity)),
                "price": float(to_decimal(t.price)),
                "amount": float(to_decimal(t.amount)),
                "status": display_status,  # Now a structured object
                "bank_ref": t.bank_ref,
                "currency": t.currency or "INR",
                "source_file": t.source_file,
            })
        return results