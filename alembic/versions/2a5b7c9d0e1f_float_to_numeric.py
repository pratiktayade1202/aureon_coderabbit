"""Add Float to Numeric migration and indexes

Revision ID: 2a5b7c9d0e1f
Revises: 1d4eef084a0e
Create Date: 2026-01-05

This migration:
1. Converts Float columns to Numeric for financial precision
2. Adds composite indexes for query performance
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Numeric


# revision identifiers
revision = '2a5b7c9d0e1f'
down_revision = '1d4eef084a0e'
branch_labels = None
depends_on = None


def upgrade():
    # === BROKER_TRADES: Float -> Numeric ===
    op.alter_column('broker_trades', 'quantity',
                    type_=Numeric(15, 4),
                    postgresql_using='quantity::numeric(15,4)')
    op.alter_column('broker_trades', 'price',
                    type_=Numeric(15, 4),
                    postgresql_using='price::numeric(15,4)')
    op.alter_column('broker_trades', 'amount',
                    type_=Numeric(15, 2),
                    postgresql_using='amount::numeric(15,2)')
    
    # Add composite indexes
    op.create_index('idx_broker_tenant_status_date', 'broker_trades', 
                    ['tenant_id', 'status', 'date'])
    op.create_index('idx_broker_tenant_symbol', 'broker_trades', 
                    ['tenant_id', 'symbol'])
    
    # === BANK_TXNS: Float -> Numeric ===
    op.alter_column('bank_txns', 'amount',
                    type_=Numeric(15, 2),
                    postgresql_using='amount::numeric(15,2)')
    op.alter_column('bank_txns', 'balance',
                    type_=Numeric(15, 2),
                    postgresql_using='balance::numeric(15,2)')
    
    # Add composite indexes
    op.create_index('idx_bank_tenant_status', 'bank_txns', 
                    ['tenant_id', 'status'])
    op.create_index('idx_bank_tenant_date', 'bank_txns', 
                    ['tenant_id', 'date'])
    
    # === HOLDINGS: Float -> Numeric ===
    op.alter_column('holdings', 'quantity',
                    type_=Numeric(15, 4),
                    postgresql_using='quantity::numeric(15,4)')
    op.alter_column('holdings', 'total_value',
                    type_=Numeric(15, 2),
                    postgresql_using='total_value::numeric(15,2)')
    op.alter_column('holdings', 'avg_cost',
                    type_=Numeric(15, 4),
                    postgresql_using='avg_cost::numeric(15,4)')
    op.alter_column('holdings', 'market_price',
                    type_=Numeric(15, 4),
                    postgresql_using='market_price::numeric(15,4)')
    
    # === NAV_LOGS: Float -> Numeric ===
    op.alter_column('nav_logs', 'nav_value',
                    type_=Numeric(15, 4),
                    postgresql_using='nav_value::numeric(15,4)')
    op.alter_column('nav_logs', 'aum',
                    type_=Numeric(15, 2),
                    postgresql_using='aum::numeric(15,2)')


def downgrade():
    # Reverse Float -> Numeric changes (not recommended in production)
    # Indexes
    op.drop_index('idx_broker_tenant_status_date', 'broker_trades')
    op.drop_index('idx_broker_tenant_symbol', 'broker_trades')
    op.drop_index('idx_bank_tenant_status', 'bank_txns')
    op.drop_index('idx_bank_tenant_date', 'bank_txns')
    
    # broker_trades
    op.alter_column('broker_trades', 'quantity', type_=sa.Float())
    op.alter_column('broker_trades', 'price', type_=sa.Float())
    op.alter_column('broker_trades', 'amount', type_=sa.Float())
    
    # bank_txns
    op.alter_column('bank_txns', 'amount', type_=sa.Float())
    op.alter_column('bank_txns', 'balance', type_=sa.Float())
    
    # holdings
    op.alter_column('holdings', 'quantity', type_=sa.Float())
    op.alter_column('holdings', 'total_value', type_=sa.Float())
    op.alter_column('holdings', 'avg_cost', type_=sa.Float())
    op.alter_column('holdings', 'market_price', type_=sa.Float())
    
    # nav_logs
    op.alter_column('nav_logs', 'nav_value', type_=sa.Float())
    op.alter_column('nav_logs', 'aum', type_=sa.Float())
