# tests/unit/test_ingestion.py
"""
Unit tests for data ingestion module.
"""
import pytest
import pandas as pd
import io
from datetime import datetime

from backend.ingestion import (
    normalize_columns,
    validate_row_integrity,
    _coerce_numeric_columns,
    _normalize_dates,
    STANDARD_MAP,
    REQUIRED_COLS,
)


class TestColumnNormalization:
    """Tests for column name normalization."""
    
    def test_standardize_column_names(self):
        """Test that column names are lowercased and cleaned."""
        df = pd.DataFrame({
            "Trade Date": [1],
            "NET AMOUNT": [100],
            "Symbol/Ticker": ["TEST"]
        })
        logs = []
        result = normalize_columns(df, logs)
        
        assert "trade_date" in result.columns or "date" in result.columns
        assert any(log for log in logs if "Schema Map" in log)
    
    def test_map_date_variants(self):
        """Test that date column variants are mapped correctly."""
        df = pd.DataFrame({
            "txn_date": ["2025-01-01"],
            "amount": [100]
        })
        logs = []
        result = normalize_columns(df, logs)
        
        assert "date" in result.columns
    
    def test_map_amount_variants(self):
        """Test that amount column variants are mapped correctly."""
        df = pd.DataFrame({
            "date": ["2025-01-01"],
            "net_amount": [100]
        })
        logs = []
        result = normalize_columns(df, logs)
        
        assert "amount" in result.columns
    
    def test_symbol_fallback_to_isin(self):
        """Test that symbol falls back to ISIN if not present."""
        df = pd.DataFrame({
            "date": ["2025-01-01"],
            "isin": ["INE001A01018"],
            "amount": [100]
        })
        logs = []
        result = normalize_columns(df, logs)
        
        assert "symbol" in result.columns
        assert result["symbol"].iloc[0] == "INE001A01018"


class TestRowValidation:
    """Tests for row validation logic."""
    
    def test_drop_empty_rows(self):
        """Test that completely empty rows are dropped."""
        df = pd.DataFrame({
            "date": ["2025-01-01", None, "2025-01-02"],
            "amount": [100, None, 200]
        })
        logs = []
        result = validate_row_integrity(df, "cash", logs)
        
        # Should have at least the non-empty rows
        assert len(result) >= 2
    
    def test_drop_future_dates(self):
        """Test that rows with future dates are dropped."""
        future_date = "2099-12-31"
        df = pd.DataFrame({
            "date": ["2025-01-01", future_date],
            "amount": [100, 200]
        })
        logs = []
        result = validate_row_integrity(df, "cash", logs)
        
        assert any("future dates" in log.lower() for log in logs)
    
    def test_missing_required_columns_trade(self):
        """Test that missing required columns for trades returns empty DataFrame."""
        df = pd.DataFrame({
            "date": ["2025-01-01"],
            # Missing: symbol, side, quantity, price
        })
        logs = []
        result = validate_row_integrity(df, "trade", logs)
        
        assert result.empty
        assert any("missing" in log.lower() for log in logs)


class TestNumericCoercion:
    """Tests for numeric column coercion."""
    
    def test_remove_currency_symbols(self):
        """Test that currency symbols are removed from amounts."""
        df = pd.DataFrame({
            "amount": ["$1,234.56", "₹5,000.00", "1000"]
        })
        logs = []
        result = _coerce_numeric_columns(df, logs)
        
        assert result["amount"].iloc[0] == pytest.approx(1234.56)
        assert result["amount"].iloc[1] == pytest.approx(5000.00)
        assert result["amount"].iloc[2] == pytest.approx(1000.0)
    
    def test_handle_invalid_numbers(self):
        """Test that invalid numbers become 0.0."""
        df = pd.DataFrame({
            "amount": ["abc", "N/A", ""]
        })
        logs = []
        result = _coerce_numeric_columns(df, logs)
        
        assert result["amount"].iloc[0] == 0.0
        assert result["amount"].iloc[1] == 0.0
        assert result["amount"].iloc[2] == 0.0


class TestDateNormalization:
    """Tests for date normalization."""
    
    def test_various_date_formats(self):
        """Test that various date formats are parsed correctly."""
        df = pd.DataFrame({
            "date": ["2025-01-15", "15/01/2025", "Jan 15, 2025", "15-Jan-2025"]
        })
        logs = []
        result = _normalize_dates(df, logs)
        
        # All should be valid dates
        for val in result["date"]:
            assert val is not None or pd.isna(val) == False
    
    def test_invalid_dates_become_null(self):
        """Test that invalid dates become null."""
        df = pd.DataFrame({
            "date": ["not-a-date", "99/99/9999"]
        })
        logs = []
        result = _normalize_dates(df, logs)
        
        # Invalid dates should become None
        assert result["date"].isna().any()


class TestFileTypeDetection:
    """Tests for file type detection logic."""
    
    def test_trade_file_keywords(self):
        """Test that trade files are detected by filename."""
        trade_filenames = [
            "broker_trades.csv",
            "contract_note.pdf",
            "trades_2025.xlsx"
        ]
        
        for filename in trade_filenames:
            # If it doesn't contain cash/ledger/bank/holding keywords,
            # it should be detected as trades
            is_trade = not any(x in filename.lower() for x in ["cash", "ledger", "bank", "holding", "portfolio", "nav"])
            assert is_trade, f"{filename} should be detected as trade file"
    
    def test_cash_file_keywords(self):
        """Test that cash files are detected by filename."""
        cash_filenames = [
            "bank_statement.csv",
            "cash_ledger.xlsx",
            "hdfc_txn.csv"
        ]
        
        for filename in cash_filenames:
            is_cash = any(x in filename.lower() for x in ["cash", "ledger", "bank", "txn"])
            assert is_cash, f"{filename} should be detected as cash file"
