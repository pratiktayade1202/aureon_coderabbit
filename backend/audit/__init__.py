# backend/audit/__init__.py
"""
Audit module for immutable logging.
"""
from .append_log import AppendOnlyLog, get_audit_log

__all__ = ["AppendOnlyLog", "get_audit_log"]
