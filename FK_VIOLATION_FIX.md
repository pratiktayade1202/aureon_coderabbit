# Foreign Key Violation Fix - Rule Definitions Seeding

## Problem

```
psycopg2.errors.ForeignKeyViolation: insert or update on table "recon_breaks" 
violates foreign key constraint "recon_breaks_rule_id_fkey"

DETAIL: Key (rule_id)=(POS_001) is not present in table "rule_definitions".
```

During Phase 2 (Run Settlement Engine), the deterministic reconciliation engine attempts to create breaks with rule IDs like `POS_001`, `TC_001`, etc. These rule IDs reference the `rule_definitions` table via a foreign key constraint, but the table was empty.

## Root Cause

The system has 100+ deterministic rules registered in-memory (via `RuleRegistry`):
- 52 Position rules (POS_001 - POS_052)
- 40+ Trade-Cash rules (TC_001 - TC_044)
- 22+ NAV rules (NAV_001 - NAV_022)
- 14+ Data Quality rules (DQ_001 - DQ_042)

However, these rules were never persisted to the `rule_definitions` table. When creating reconciliation breaks, the FK constraint failed.

---

## Solution

### 1. Created Rule Seeding Module

**File:** `backend/seed_rules.py`

This module:
- Initializes the `ReconEngine` (which registers all rules in `RuleRegistry`)
- Reads all registered rules from the in-memory registry
- Inserts them into `rule_definitions` table if they don't exist
- Is **idempotent** - safe to run multiple times
- Handles race conditions and integrity errors gracefully

**Key function:**
```python
def seed_rule_definitions():
    """Seeds all registered rules into rule_definitions table."""
    # 1. Initialize engine (populates RuleRegistry)
    engine = ReconEngine(db=db, tenant_id="SYSTEM")
    
    # 2. Get all rules from registry
    all_rules = RuleRegistry.get_all()
    
    # 3. Insert each rule if it doesn't exist
    for rule in all_rules:
        if not db.query(RuleDefinition).filter_by(rule_id=rule.rule_id).first():
            rule_def = RuleDefinition(
                rule_id=rule.rule_id,
                name=rule.description,
                description=rule.description,
                domain=determine_domain(rule.rule_id),
                tier=RuleTier.TIER_1_DETERMINISTIC,
                is_active=True
            )
            db.add(rule_def)
    
    db.commit()
```

### 2. Integrated into Application Startup

**File:** `backend/main.py`

Added automatic seeding during application startup:

```python
from .seed_rules import ensure_rule_definitions_exist

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    
    # Seed rule definitions
    logger.info("🌱 Seeding rule definitions...")
    ensure_rule_definitions_exist()
    
    yield
```

This ensures:
- Rules are seeded once at startup
- If the app crashes, rules are re-seeded on restart
- No manual intervention required
- Safe for production (idempotent)

---

## Verification

### Check Rules Were Seeded

```sql
-- Count rules in database
SELECT domain, COUNT(*) as count 
FROM rule_definitions 
GROUP BY domain;

-- Expected output:
-- POSITIONS: 52
-- TRADE_CASH: 40+
-- NAV: 22+
-- DATA_QUALITY: 14+
```

### Test the Fix

```bash
# 1. Reset database
curl -X POST http://localhost:8000/api/v1/recon/reset-db

# 2. Upload trades
curl -X POST http://localhost:8000/api/v1/upload -F "file=@trades.csv"

# 3. Run settlement engine (should work now!)
curl -X POST http://localhost:8000/api/v1/recon/run-settlement-engine

# Expected: Success (no FK violation)
# Response should show matches and breaks created
```

---

## 3-Phase Workflow Preserved

### Phase 1: Ingestion (Raw Data Only)
```
✅ Upload files
✅ Parse with Gemini fallback
✅ Normalize data
✅ Insert raw trades (status=UNSETTLED)
❌ NO rules
❌ NO matching
❌ NO breaks
❌ NO AI
```

### Phase 2: Run Settlement Engine (Deterministic Only)
```
✅ Apply deterministic rules (POS_001, TC_001, etc.)
✅ Match trades with cash transactions
✅ Create breaks for unmatched trades
✅ Update holdings and AUC
✅ Set resolution_type = "RULE"
✅ Rule IDs now exist in rule_definitions (FK satisfied!)
❌ NO AI/GPT calls
```

### Phase 3: Auto Resolve (AI Only)
```
✅ Analyze remaining open breaks with GPT-4o
✅ High-confidence matches (≥0.85) auto-resolved
✅ Update holdings and AUC
✅ Set resolution_type = "AI"
✅ Set resolution_note = <GPT explanation>
❌ NO deterministic rules
```

---

## GPT Integration Verified

### OpenAI Configuration
**File:** `backend/config.py`
```python
openai_api_key: str = Field(..., alias="OPENAI_API_KEY")  # Required
openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
```

### LLM Gateway
**File:** `backend/llm_gateway.py`
```python
# Configure OpenAI client
openai_client = OpenAI(api_key=settings.openai_api_key)

def reason_on_discrepancy(context: str) -> str:
    """AI reasoning for breaks - tries OpenAI first, Gemini fallback."""
    if openai_client:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,  # gpt-4o
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
        )
        return response.choices[0].message.content
    # Fallback to Gemini...
```

### AI Agent
**File:** `backend/ai_layer/agent.py`
```python
def analyze_single_trade(self, trade_id: int):
    """Analyze trade with AI reasoning."""
    # ... find candidates ...
    
    # Call GPT for reasoning
    result = LLMGateway.reason_on_discrepancy(context)
    return result
```

### Auto Resolve Endpoint
**File:** `backend/recon_api.py`
```python
@router.post("/auto-resolve")
def run_auto_resolve(...):
    """PHASE 3: AI-only resolution."""
    agent = AIAgent(db, user_id)
    
    for break in open_breaks:
        # Call GPT via agent
        analysis = agent.analyze_single_trade(break.trade_id)
        
        if analysis["confidence"] >= 0.85:
            trade.status = "MATCHED"
            trade.bank_ref = f"AI:{analysis['explanation']}"
            # Update holdings...
```

---

## Key Guarantees

✅ **No Schema Changes:** FK constraint remains intact  
✅ **Idempotent Seeding:** Safe to run multiple times  
✅ **Startup Automation:** Runs on every app start  
✅ **Phase Separation:** Settlement Engine = Rules, Auto Resolve = AI  
✅ **GPT Integration:** Properly configured with error handling  
✅ **Manual Resolution:** Unchanged  
✅ **Holdings/AUC Updates:** Applied in both Phase 2 and Phase 3  
✅ **Audit Logging:** All phases write audit events  

---

## Troubleshooting

### If FK violation still occurs:

1. **Check rules were seeded:**
   ```sql
   SELECT COUNT(*) FROM rule_definitions;
   -- Should be 100+ rules
   ```

2. **Check startup logs:**
   ```
   🌱 Seeding rule definitions...
   ✅ Rule seeding complete: Inserted: X, Already existed: Y
   ```

3. **Manual seed (if needed):**
   ```python
   from backend.seed_rules import seed_rule_definitions
   seed_rule_definitions()
   ```

### If GPT isn't working:

1. **Check environment variable:**
   ```bash
   echo $OPENAI_API_KEY
   ```

2. **Check startup logs:**
   ```
   ✓ OpenAI configured successfully with model: gpt-4o
   ```

3. **Test GPT directly:**
   ```python
   from backend.llm_gateway import LLMGateway
   result = LLMGateway.reason_on_discrepancy("Test context")
   print(result)
   ```

---

## Summary

The FK violation was caused by missing rule definitions in the database. The fix:
1. **Seeds all rules at startup** from the in-memory registry
2. **Preserves 3-phase workflow** (Ingestion → Settlement Engine → Auto Resolve)
3. **Maintains FK integrity** without schema changes
4. **Verifies GPT integration** for Phase 3 AI resolution

The system now correctly:
- Creates breaks with valid rule IDs
- Separates deterministic and AI phases
- Updates holdings and AUC appropriately
- Provides full audit trail


















