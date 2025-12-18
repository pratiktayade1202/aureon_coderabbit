# backend/seed_rules.py
"""
Rule definitions seeding module.
Ensures all deterministic rule IDs exist in rule_definitions table.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal
from .models import RuleDefinition, RuleTier
from .rule_engine.core.engine import ReconciliationEngine
from .rule_engine.core.registry import RuleRegistry

logger = logging.getLogger(__name__)


def seed_rule_definitions():
    """
    Seed rule_definitions table with all registered rules.
    
    This function:
    1. Initializes the ReconEngine (registers all rules)
    2. Gets all rules from RuleRegistry
    3. Inserts them into rule_definitions if they don't exist
    4. Is idempotent - safe to run multiple times
    
    Called during application startup to prevent FK violations when
    creating reconciliation breaks.
    """
    db = SessionLocal()
    try:
        logger.info("🌱 Seeding rule definitions...")
        
        # Initialize engine to register all rules
        # This populates RuleRegistry with all rules from all domains
        engine = ReconciliationEngine()
        engine.initialize()
        
        # Get all registered rules
        all_rules = RuleRegistry.get_all()
        
        if not all_rules:
            logger.warning("⚠️ No rules found in RuleRegistry!")
            return
        
        logger.info(f"   Found {len(all_rules)} rules in registry")
        
        # Track seeding stats
        inserted_count = 0
        existing_count = 0
        error_count = 0
        
        for rule in all_rules:
            try:
                # Check if rule already exists
                existing = db.query(RuleDefinition).filter_by(rule_id=rule.rule_id).first()
                
                if existing:
                    existing_count += 1
                    continue
                
                # Determine domain from rule_id prefix
                domain = "UNKNOWN"
                if rule.rule_id.startswith("POS_"):
                    domain = "POSITIONS"
                elif rule.rule_id.startswith("TC_"):
                    domain = "TRADE_CASH"
                elif rule.rule_id.startswith("NAV_"):
                    domain = "NAV"
                elif rule.rule_id.startswith("DQ_"):
                    domain = "DATA_QUALITY"
                elif rule.rule_id.startswith("FX_"):
                    domain = "FX"
                elif rule.rule_id.startswith("CA_"):
                    domain = "CORPORATE_ACTIONS"
                elif rule.rule_id.startswith("FEE_"):
                    domain = "FEES"
                
                # Map severity string to enum-friendly value
                severity_map = {
                    "CRITICAL": "CRITICAL",
                    "HIGH": "HIGH", 
                    "MEDIUM": "MEDIUM",
                    "LOW": "LOW",
                    "INFO": "LOW"  # Map INFO to LOW
                }
                severity_str = getattr(rule, "severity", "MEDIUM").upper()
                severity = severity_map.get(severity_str, "MEDIUM")
                
                # Create new rule definition
                rule_def = RuleDefinition(
                    rule_id=rule.rule_id,
                    name=rule.description[:200] if len(rule.description) > 200 else rule.description,
                    description=rule.description,
                    domain=domain,
                    tier=RuleTier.TIER_1_DETERMINISTIC,
                    is_active=True,
                    tolerance_threshold=getattr(rule, "tolerance_threshold", 0.0)
                )
                
                db.add(rule_def)
                db.flush()  # Flush to catch any errors before committing
                
                inserted_count += 1
                
            except IntegrityError as e:
                # Rule might have been inserted by another process
                db.rollback()
                existing_count += 1
                logger.debug(f"   Rule {rule.rule_id} already exists (race condition)")
                
            except Exception as e:
                error_count += 1
                logger.error(f"   Failed to seed rule {rule.rule_id}: {str(e)}")
                db.rollback()
        
        # Commit all insertions
        db.commit()
        
        logger.info(f"✅ Rule seeding complete:")
        logger.info(f"   - Inserted: {inserted_count}")
        logger.info(f"   - Already existed: {existing_count}")
        if error_count > 0:
            logger.warning(f"   - Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"❌ Rule seeding failed: {str(e)}", exc_info=True)
        db.rollback()
        raise
        
    finally:
        db.close()


def ensure_rule_definitions_exist():
    """
    Public interface for ensuring rule definitions exist.
    Safe to call multiple times (idempotent).
    """
    try:
        seed_rule_definitions()
    except Exception as e:
        logger.error(f"Failed to ensure rule definitions: {str(e)}")
        # Don't crash the application on startup
        # Rules will be seeded on next restart
        pass






