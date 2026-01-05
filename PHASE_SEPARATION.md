# Aureon Backend - Phase Separation Architecture

**Last Updated**: December 9, 2025  
**Status**: ✅ Implemented

---

## 🎯 OVERVIEW

The Aureon backend enforces a **strict two-phase architecture** that separates data ingestion from reconciliation:

1. **INGESTION PHASE**: Load and normalize raw data (NO reconciliation)
2. **AUTO RESOLVE PHASE**: Perform reconciliation (rules + matching + AI)

This separation ensures:
- ✅ Clear data lineage (raw → reconciled)
- ✅ Explicit user control over reconciliation timing
- ✅ No accidental/premature reconciliation
- ✅ Proper audit trail of when reconciliation occurred

---

## 📊 PHASE 1: INGESTION (Raw Data Load)

### What It Does
- Accepts file uploads (CSV, Excel, PDF, ZIP)
- Parses and normalizes data using deterministic parsers + Gemini fallback
- Runs data quality checks (weekend trades, negative prices, etc.)
- Inserts raw data into database

### What It Does NOT Do
- ❌ Does NOT run rule engine
- ❌ Does NOT perform matching
- ❌ Does NOT create reconciliation breaks
- ❌ Does NOT update holdings based on matched trades
- ❌ Does NOT populate resolution_type or resolution_note
- ❌ Does NOT change trade status from UNSETTLED

### Database State After Ingestion

| Entity | State |
|--------|-------|
| **Trades** | All inserted with `status='UNSETTLED'` |
| **Cash** | All inserted with `status='UNUSED'` |
| **Holdings** | Raw snapshot from file (if holdings file uploaded) |
| **Breaks** | None created (reconciliation hasn't run yet) |
| **Audit Logs** | Ingestion events only (file received, parsed, DQ checks) |

### Dashboard View After Ingestion

```json
{
  "trades": [
    {
      "id": 123,
      "symbol": "RELIANCE",
      "side": "BUY",  // Normalized
      "amount": 50000.00,
      "status": {"status": "UNSETTLED"},  // Raw state
      "resolution_type": null,  // No resolution yet
      "resolution_note": null,
      "bank_ref": null
    }
  ],
  "breaks": [],  // Empty - no reconciliation yet
  "holdings": [...],  // Raw snapshot from file
  "auc": 1500000.00  // From raw holdings snapshot
}
```

### Code Files Involved
- `backend/ingestion.py` - Main ingestion pipeline
- `backend/ingestion_api.py` - Upload endpoint
- Database inserts only (no reconciliation logic)

---

## 🔄 PHASE 2: AUTO RESOLVE (Reconciliation)

### Trigger
**User explicitly clicks "Auto Resolve" button in frontend**

This triggers: `POST /api/v1/recon/auto-resolve`

### What It Does (Full Reconciliation Pipeline)

#### Step 1: Deterministic Rule Engine
- Runs trade-cash matching rules
- Validates amounts, dates, currencies
- Updates trade status: `UNSETTLED → MATCHED`
- Updates cash status: `UNUSED → MATCHED`
- Populates `bank_ref` with format: `RULE:Matched to Cash {id} (Run: {run_id})`
- Creates reconciliation breaks for failed matches

#### Step 2: Holdings Update
- For each newly matched trade:
  - BUY trades: Increase holdings quantity/value
  - SELL trades: Decrease holdings quantity/value
- Recalculates AUC (Assets Under Custody)
- Updates `holdings` table with reconciliation-based changes

#### Step 3: AI Reasoning (Optional)
- Analyzes remaining open breaks
- For high-confidence matches (≥ 0.85):
  - Auto-resolves the break
  - Updates trade status to MATCHED
  - Populates `bank_ref` with format: `AI:{explanation}`
  - Updates holdings

#### Step 4: Audit Logging
- Logs reconciliation start/completion
- Logs each match (trade_id, cash_id, rule_id)
- Logs holdings updates
- Logs AI decisions

### Database State After Auto Resolve

| Entity | State |
|--------|-------|
| **Trades** | `MATCHED` (if reconciled) or `UNSETTLED` (if break created) |
| **Cash** | `MATCHED` (if matched) or `UNUSED` (still available) |
| **Holdings** | Updated based on matched trades |
| **Breaks** | Created for unmatched trades (status=`OPEN`) |
| **Audit Logs** | Full reconciliation trail |

### Dashboard View After Auto Resolve

```json
{
  "trades": [
    {
      "id": 123,
      "symbol": "RELIANCE",
      "side": "BUY",
      "amount": 50000.00,
      "status": {"status": "MATCHED", "resolution_type": "RESOLVED_RULE"},
      "resolution_type": "RESOLVED_RULE",
      "resolution_note": "Matched to Cash 456 (Run: abc123)",
      "bank_ref": "RULE:Matched to Cash 456 (Run: abc123)"
    },
    {
      "id": 124,
      "symbol": "INFY",
      "side": "SELL",
      "amount": 75000.00,
      "status": {"status": "BREAK", "break_type": "NO_MATCH_FOUND", "severity": "MEDIUM", "break_id": 42},
      "resolution_type": null,
      "resolution_note": null,
      "bank_ref": null
    }
  ],
  "breaks": [
    {
      "id": 42,
      "trade_id": 124,
      "break_type": "NO_MATCH_FOUND",
      "severity": "MEDIUM",
      "status": "OPEN"
    }
  ],
  "holdings": [...],  // Updated from matched trades
  "auc": 1550000.00  // Recalculated after reconciliation
}
```

### Code Files Involved
- `backend/recon_api.py` - `/auto-resolve` endpoint
- `backend/rule_engine/orchestrator.py` - Main reconciliation logic
- `backend/rule_engine/core/engine.py` - Rule execution
- `backend/ai_layer/agent.py` - AI reasoning
- Database updates (trades, cash, holdings, breaks, audit logs)

---

## 🔑 KEY ARCHITECTURAL POINTS

### 1. Single Entry Point for Reconciliation
- **ONLY** `/auto-resolve` triggers reconciliation
- No other endpoint runs matching or updates holdings
- Frontend MUST call this explicitly

### 2. Resolution Type Tracking
Trades that are reconciled get `bank_ref` populated with a prefix:

| Prefix | Meaning |
|--------|---------|
| `RULE:` | Matched by deterministic rule engine |
| `AI:` | Matched by AI agent |
| `MANUAL:` | Manually resolved by analyst |

The `_get_resolution_type()` function parses this to return:
- `RESOLVED_RULE`
- `RESOLVED_AI`
- `RESOLVED_MANUAL`

### 3. Holdings Update Timing

| Event | Holdings Update? |
|-------|------------------|
| Ingestion of holdings file | ✅ YES (raw snapshot inserted) |
| Ingestion of trade file | ❌ NO (trades not reconciled yet) |
| Auto Resolve (trade matched) | ✅ YES (updated based on trade) |
| Manual Resolve | ✅ YES (updated based on trade) |

**CRITICAL**: Holdings are updated ONLY when trades are reconciled, not during ingestion.

### 4. Dashboard State Reflection

The dashboard endpoints (`/trades`, `/breaks`, `/dashboard-stats`) are **READ-ONLY**.

They return:
- **Before Auto Resolve**: Raw ingested state (UNSETTLED, no breaks, no resolution metadata)
- **After Auto Resolve**: Reconciled state (MATCHED/BREAK, resolution metadata populated)

They do NOT trigger reconciliation themselves.

---

## 🔄 WORKFLOW EXAMPLE

### Scenario: Upload trades + cash → Auto Resolve → Manual fix

```
1. User uploads trades.csv (10 trades)
   → Ingestion: 10 trades inserted with status=UNSETTLED
   → Dashboard shows: 10 UNSETTLED trades, 0 breaks
   
2. User uploads cash_ledger.csv (8 cash entries)
   → Ingestion: 8 cash entries inserted with status=UNUSED
   → Dashboard shows: 10 UNSETTLED trades, 8 UNUSED cash, 0 breaks
   
3. User clicks "Auto Resolve"
   → Reconciliation runs:
      - 7 trades matched (status → MATCHED)
      - 3 trades unmatched (breaks created)
   → Dashboard shows: 
      - 7 MATCHED trades (resolution_type=RESOLVED_RULE)
      - 3 UNSETTLED trades with BREAK status
      - 3 open breaks
      - Holdings updated (7 trades applied)
      - AUC recalculated
      
4. Analyst manually resolves 1 break
   → Manual resolution endpoint:
      - Trade status → MATCHED
      - bank_ref = "MANUAL:{analyst note}"
      - Break status → RESOLVED
      - Holdings updated
   → Dashboard shows:
      - 8 MATCHED trades (7 RULE, 1 MANUAL)
      - 2 UNSETTLED trades with BREAK status
      - 2 open breaks
```

---

## 🚫 COMMON MISTAKES TO AVOID

### ❌ DON'T: Trigger Reconciliation During Ingestion
```python
# WRONG - DO NOT DO THIS
def process_file_content(content, filename, user_id):
    df = parse_file(content)
    route_and_save(df, filename, user_id)
    
    # ❌ WRONG: Do not run reconciliation here!
    orchestrator = ReconOrchestrator(db, user_id)
    orchestrator.run_trade_recon()  # ❌ NO!
```

### ✅ DO: Keep Ingestion Pure
```python
# CORRECT
def process_file_content(content, filename, user_id):
    df = parse_file(content)
    route_and_save(df, filename, user_id)  # Just insert raw data
    log_ingestion_event("FILE_PROCESSED", filename)
    # That's it! No reconciliation.
```

### ❌ DON'T: Update Holdings During Ingestion
```python
# WRONG - DO NOT DO THIS
def route_and_save(df, filename, user_id):
    # Save trades
    save_trades(df, user_id)
    
    # ❌ WRONG: Do not update holdings here!
    update_holdings_from_trades(user_id)  # ❌ NO!
```

### ✅ DO: Update Holdings ONLY During Reconciliation
```python
# CORRECT
def _apply_trade_results(self, report, trades_data, cash_data):
    # Apply matches from reconciliation
    for match in report["matches"]:
        update_trade_status(match["trade_id"], "MATCHED")
        newly_matched_trade_ids.add(match["trade_id"])
    
    # Update holdings ONLY for newly matched trades
    self._update_holdings_from_matches(newly_matched_trade_ids)
```

---

## 📝 API ENDPOINT SUMMARY

| Endpoint | Phase | Purpose | Reconciliation? |
|----------|-------|---------|-----------------|
| `POST /upload` | Ingestion | Upload files | ❌ NO |
| `GET /trades` | Both | View trades | ❌ NO (read-only) |
| `GET /breaks` | Both | View breaks | ❌ NO (read-only) |
| `GET /dashboard-stats` | Both | View stats | ❌ NO (read-only) |
| `POST /auto-resolve` | Reconciliation | **Trigger reconciliation** | ✅ YES |
| `POST /resolve-trade/{id}` | Reconciliation | Manual resolution | ✅ YES (holdings update) |
| `POST /run` | Legacy | Redirect to /auto-resolve | ✅ YES |
| `POST /ai-resolve` | Deprecated | Use /auto-resolve instead | ❌ Deprecated |

---

## 🧪 TESTING CHECKLIST

### Test 1: Ingestion Does Not Reconcile
- [ ] Upload trades.csv
- [ ] Verify all trades show status=UNSETTLED
- [ ] Verify no breaks created
- [ ] Verify no resolution_type or resolution_note
- [ ] Verify holdings NOT updated (if no holdings file uploaded)

### Test 2: Auto Resolve Performs Full Reconciliation
- [ ] Click "Auto Resolve"
- [ ] Verify trades matched have status=MATCHED
- [ ] Verify resolution_type populated (RESOLVED_RULE or RESOLVED_AI)
- [ ] Verify resolution_note populated
- [ ] Verify breaks created for unmatched trades
- [ ] Verify holdings updated
- [ ] Verify AUC recalculated
- [ ] Verify audit logs created

### Test 3: Dashboard Respects Phase Separation
- [ ] After ingestion: Dashboard shows raw state
- [ ] After auto resolve: Dashboard shows reconciled state
- [ ] GET endpoints do not trigger reconciliation

### Test 4: Manual Resolution Works
- [ ] Manually resolve a break
- [ ] Verify trade status → MATCHED
- [ ] Verify resolution_type = RESOLVED_MANUAL
- [ ] Verify holdings updated
- [ ] Verify learning event created

---

## 🔧 MAINTENANCE NOTES

### Adding New Ingestion Logic
When adding new parsers or data quality checks:
- ✅ Add to `ingestion.py`
- ✅ Ensure NO reconciliation calls
- ✅ Log ingestion events only
- ✅ Insert raw data with UNSETTLED/UNUSED status

### Adding New Reconciliation Logic
When adding new matching rules or AI models:
- ✅ Add to rule engine or AI agent
- ✅ Ensure called ONLY from `/auto-resolve`
- ✅ Update holdings if trade matched
- ✅ Log reconciliation events

### Troubleshooting
If reconciliation happens unexpectedly during ingestion:
1. Check for `ReconOrchestrator` calls in `ingestion.py` → Remove them
2. Check for holdings updates during ingestion → Move to Auto Resolve
3. Check for status changes from UNSETTLED during ingestion → Remove them

---

## ✅ BENEFITS OF THIS ARCHITECTURE

1. **Clear Separation of Concerns**
   - Ingestion = ETL (Extract, Transform, Load)
   - Reconciliation = Business logic (matching, rules, AI)

2. **User Control**
   - User decides when to reconcile
   - Can review raw data before reconciling
   - Can re-run reconciliation if needed

3. **Debuggability**
   - Easy to identify if issue is in ingestion vs reconciliation
   - Can inspect raw data before reconciliation
   - Clear audit trail of when reconciliation occurred

4. **Performance**
   - Ingestion is fast (no expensive reconciliation)
   - Reconciliation is explicit and logged
   - Can batch reconciliation for efficiency

5. **Maintainability**
   - New ingestion logic doesn't affect reconciliation
   - New reconciliation logic doesn't affect ingestion
   - Easy to test each phase independently

---

**End of Document**
