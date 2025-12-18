# Three-Phase Reconciliation Pipeline

**Date**: December 9, 2025  
**Status**: ✅ Implemented  
**Architecture**: Strict 3-Phase Sequential Workflow

---

## 🎯 OVERVIEW

The Aureon backend implements a **strict 3-phase reconciliation pipeline** that separates ingestion, deterministic matching, and AI reasoning into distinct, sequential phases with explicit user control.

### The Three Phases

```
PHASE 1: INGESTION (Raw Data Load)
    ↓ All trades UNSETTLED
PHASE 2: RUN SETTLEMENT ENGINE (Deterministic Rules)
    ↓ Trades matched by rules, breaks created
PHASE 3: AUTO RESOLVE (AI/GPT Reasoning)
    ↓ Remaining breaks resolved by AI
```

---

## 📊 PHASE 1: INGESTION (Raw Data Only)

### Purpose
Load and normalize raw data WITHOUT any reconciliation logic.

### Trigger
- User uploads files (CSV, Excel, PDF, ZIP)
- Endpoint: `POST /api/v1/upload`

### What Happens
1. File unzip (if ZIP)
2. Parse data (deterministic + Gemini fallback for complex files)
3. Run Data Quality (DQ) checks
   - Weekend trading detection
   - Negative prices
   - Missing identifiers
   - Suspense transactions
4. Normalize data
   - Side values: B → BUY, S → SELL
   - Dates to YYYY-MM-DD
   - Currency codes
5. Insert raw data into database
6. Write audit log: "INGESTION_SUCCESS"

### What Does NOT Happen
- ❌ NO reconciliation rules
- ❌ NO matching logic
- ❌ NO break creation (reconciliation breaks)
- ❌ NO holdings updates from trades
- ❌ NO settlement status changes
- ❌ NO AI/GPT calls
- ❌ NO resolution_type assignment
- ❌ NO AUC computation from matched trades

### Database State After Phase 1

| Entity | State |
|--------|-------|
| **Trades** | All `status='UNSETTLED'` |
| **Cash** | All `status='UNUSED'` |
| **Holdings** | Raw snapshot from holdings file (if uploaded) |
| **Breaks** | None (reconciliation hasn't run) |
| **Resolution Metadata** | All NULL (resolution_type, resolution_note, bank_ref) |

### Dashboard View After Phase 1

```json
{
  "trades": [
    {
      "id": 123,
      "symbol": "RELIANCE",
      "side": "BUY",
      "amount": 50000.00,
      "status": {"status": "UNSETTLED"},
      "resolution_type": null,
      "resolution_note": null,
      "bank_ref": null
    }
  ],
  "breaks": [],
  "pending_settlements": 10,
  "button_displayed": "RUN SETTLEMENT ENGINE"
}
```

### Code Location
- `backend/ingestion.py` - Main ingestion pipeline
- `backend/ingestion_api.py` - Upload endpoint

---

## 🔧 PHASE 2: RUN SETTLEMENT ENGINE (Deterministic Rules Only)

### Purpose
Apply deterministic rule-based reconciliation WITHOUT AI.

### Trigger
- User clicks "RUN SETTLEMENT ENGINE" button
- Endpoint: `POST /api/v1/recon/run-settlement-engine`

### What Happens
1. **Run Deterministic Rules** via `ReconOrchestrator`
   - Trade-cash amount matching (1% tolerance)
   - Date alignment (T+0, T+1, T+2)
   - Currency matching
   - Direction sanity checks
2. **Update Settlement Statuses**
   - Matched trades: `UNSETTLED → MATCHED`
   - Matched cash: `UNUSED → MATCHED`
   - Unmatched trades: Remain `UNSETTLED`
3. **Set Resolution Metadata** for matched trades
   - `bank_ref = "RULE:Matched to Cash {cash_id} (Run: {run_id})"`
   - Frontend extracts: `resolution_type = "RULE"`
4. **Create Reconciliation Breaks**
   - For trades that failed matching rules
   - Break types: `NO_MATCH_FOUND`, `AMOUNT_MISMATCH`, `DATE_MISMATCH`, etc.
   - Severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
5. **Update Holdings and AUC**
   - For EACH newly matched trade:
     - BUY: Increase holdings quantity/value
     - SELL: Decrease holdings quantity/value
   - Recalculate Assets Under Custody (AUC)
6. **Write Audit Events**
   - "RECON_STARTED"
   - "TRADE_MATCHED" (for each match)
   - "BREAK_CREATED" (for each break)
   - "HOLDINGS_UPDATED"
   - "RECON_COMPLETED"

### What Does NOT Happen
- ❌ NO AI/GPT calls
- ❌ NO OpenAI reasoning
- ❌ NO Gemini reasoning (unless for ingestion fallback, not reconciliation)

### Database State After Phase 2

| Entity | State |
|--------|-------|
| **Trades** | `MATCHED` (if rule-matched) or `UNSETTLED` (if no match) |
| **Cash** | `MATCHED` (if used) or `UNUSED` (if available) |
| **Holdings** | Updated from matched trades |
| **Breaks** | Created for unmatched trades (status=`OPEN`) |
| **Resolution Metadata** | Populated for MATCHED trades: `resolution_type=RULE`, `resolution_note` |

### Dashboard View After Phase 2

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
      "status": {"status": "BREAK", "break_type": "NO_MATCH_FOUND", "severity": "MEDIUM"},
      "resolution_type": null,
      "resolution_note": null
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
  "pending_settlements": 3,
  "button_displayed": "AUTO RESOLVE"
}
```

### Response Format

```json
{
  "status": "success",
  "message": "Settlement engine completed - deterministic rules applied",
  "phase": "PHASE_2_DETERMINISTIC",
  "run_id": "abc123",
  "deterministic_results": {
    "matches": 7,
    "breaks_created": 3,
    "resolution_type": "RULE"
  },
  "next_step": "Click AUTO RESOLVE to apply AI reasoning to remaining breaks"
}
```

### Code Location
- `backend/recon_api.py` - `/run-settlement-engine` endpoint
- `backend/rule_engine/orchestrator.py` - `ReconOrchestrator.run_trade_recon()`
- `backend/rule_engine/core/engine.py` - Rule execution engine
- `backend/rule_engine/domains/` - Domain-specific rules

---

## 🤖 PHASE 3: AUTO RESOLVE (AI/GPT Only)

### Purpose
Use AI/GPT to resolve remaining ambiguous breaks.

### Trigger
- User clicks "AUTO RESOLVE" button
- Endpoint: `POST /api/v1/recon/auto-resolve`

### What Happens
1. **Fetch Remaining Open Breaks**
   - Query: `WHERE status='OPEN' AND tenant_id=user_id`
   - These are trades that deterministic rules couldn't match
2. **AI Analysis via GPT** for EACH open break
   - Call `AIAgent.analyze_single_trade(trade_id)`
   - Agent finds candidate cash entries (amount within 1% tolerance)
   - Calls `LLMGateway.reason_on_discrepancy()` with:
     - Trade details (symbol, amount, date, side)
     - Candidate cash entries
     - Context about reconciliation scenario
   - **LLM Gateway Flow**:
     - Tries **OpenAI/GPT** first (default: `gpt-4o`)
     - Falls back to **Gemini 2.5 Pro** if OpenAI fails
     - Returns structured JSON with:
       - `best_match_id`: Cash entry ID
       - `confidence`: 0.0 to 1.0
       - `action`: MATCH, REVIEW, or ESCALATE
       - `explanation`: AI reasoning
3. **Auto-Resolve High-Confidence Matches**
   - Threshold: confidence ≥ 0.85 (configurable)
   - For matches above threshold:
     - Update trade status: `UNSETTLED → MATCHED`
     - Set `bank_ref = "AI:{explanation}"`
     - Frontend extracts: `resolution_type = "AI"`
     - Update cash status: `UNUSED → MATCHED`
     - Close the break: `status = "RESOLVED"`
4. **Update Holdings and AUC**
   - For EACH AI-resolved trade:
     - BUY: Increase holdings
     - SELL: Decrease holdings
   - Recalculate AUC
5. **Write Audit Events**
   - "AI_ANALYSIS" (for each trade analyzed)
   - "AI_RESOLVED" (for each auto-resolved trade)
   - "HOLDINGS_UPDATED"

### What Does NOT Happen
- ❌ Does NOT re-run deterministic rules (already done in Phase 2)
- ❌ Does NOT match trades that Phase 2 already matched

### AI/GPT Configuration

**Primary Model**: OpenAI GPT-4o
- Model: `gpt-4o` (configured in `OPENAI_MODEL` env var)
- Temperature: 0.2 (low for consistency)
- Response format: JSON

**Fallback Model**: Gemini 2.5 Pro
- Model: `gemini-2.5-pro` (configured in `GEMINI_MODEL` env var)
- Used if OpenAI fails or is unavailable

**Environment Variables**:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o  # Default
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-pro  # Default
```

### Confidence Thresholds

| Confidence | Action | Description |
|------------|--------|-------------|
| ≥ 0.85 | AUTO_MATCH | High confidence - auto-resolve |
| 0.70-0.85 | REVIEW | Medium confidence - log but don't auto-resolve |
| < 0.70 | ESCALATE | Low confidence - manual review required |

### Database State After Phase 3

| Entity | State |
|--------|-------|
| **Trades** | All resolved (MATCHED) or remaining breaks |
| **Cash** | MATCHED or UNUSED |
| **Holdings** | Finalized with all matched trades applied |
| **Breaks** | RESOLVED (if AI matched) or OPEN (if below threshold) |
| **Resolution Metadata** | AI-resolved trades: `resolution_type=AI`, `resolution_note=<GPT explanation>` |

### Dashboard View After Phase 3

```json
{
  "trades": [
    {
      "id": 124,
      "symbol": "INFY",
      "side": "SELL",
      "amount": 75000.00,
      "status": {"status": "MATCHED", "resolution_type": "RESOLVED_AI"},
      "resolution_type": "RESOLVED_AI",
      "resolution_note": "AI matched based on amount similarity and date proximity. Confidence: 0.87",
      "bank_ref": "AI:AI matched based on amount similarity and date proximity. Confidence: 0.87"
    }
  ],
  "breaks": [],
  "pending_settlements": 0,
  "reconciliation_complete": true
}
```

### Response Format

```json
{
  "status": "success",
  "message": "Auto Resolve (AI) completed successfully",
  "phase": "PHASE_3_AI",
  "ai_results": {
    "breaks_analyzed": 3,
    "resolved": 2,
    "threshold": 0.85,
    "resolution_type": "AI"
  },
  "final_state": "Reconciliation complete - check dashboard for final results"
}
```

### Code Location
- `backend/recon_api.py` - `/auto-resolve` endpoint
- `backend/ai_layer/agent.py` - `AIAgent` class
- `backend/llm_gateway.py` - `LLMGateway.reason_on_discrepancy()`

---

## 🔄 COMPLETE WORKFLOW EXAMPLE

### Scenario: Upload trades + cash → Run settlement → Auto resolve

```
1️⃣ PHASE 1: INGESTION
   User uploads: trades.csv (10 trades), cash.csv (8 entries)
   
   Result:
   - 10 trades inserted (all UNSETTLED)
   - 8 cash entries inserted (all UNUSED)
   - Dashboard shows: "RUN SETTLEMENT ENGINE" button
   
2️⃣ PHASE 2: RUN SETTLEMENT ENGINE
   User clicks "RUN SETTLEMENT ENGINE"
   
   Result:
   - 7 trades matched by rules → MATCHED (resolution_type=RULE)
   - 3 trades unmatched → 3 breaks created
   - Holdings updated (7 trades applied)
   - AUC recalculated
   - Dashboard shows: "AUTO RESOLVE" button
   
3️⃣ PHASE 3: AUTO RESOLVE
   User clicks "AUTO RESOLVE"
   
   GPT analyzes 3 remaining breaks:
   - Break 1: Confidence 0.88 → AUTO RESOLVED (resolution_type=AI)
   - Break 2: Confidence 0.91 → AUTO RESOLVED (resolution_type=AI)
   - Break 3: Confidence 0.65 → REMAINS OPEN (manual review needed)
   
   Result:
   - 9 total resolved (7 RULE + 2 AI)
   - 1 remaining break (low confidence)
   - Holdings updated (2 more trades applied)
   - AUC finalized
   - Dashboard shows: 1 open break for analyst review
```

---

## 📋 API ENDPOINTS SUMMARY

| Endpoint | Phase | Purpose | AI Used? |
|----------|-------|---------|----------|
| `POST /upload` | 1 | Upload files | ❌ No |
| `POST /run-settlement-engine` | 2 | Deterministic rules | ❌ No |
| `POST /auto-resolve` | 3 | AI reasoning | ✅ Yes (GPT/Gemini) |
| `POST /resolve-trade/{id}` | Manual | Analyst override | ❌ No |
| `GET /trades` | Any | View trades | ❌ No (read-only) |
| `GET /breaks` | Any | View breaks | ❌ No (read-only) |

---

## 🧪 TESTING CHECKLIST

### Test Phase 1: Ingestion
- [ ] Upload trades.csv
- [ ] Verify all trades show `status=UNSETTLED`
- [ ] Verify `resolution_type=null`, `resolution_note=null`
- [ ] Verify no reconciliation breaks created
- [ ] Verify holdings NOT updated (unless holdings file uploaded)
- [ ] Verify dashboard button shows "RUN SETTLEMENT ENGINE"

### Test Phase 2: Settlement Engine
- [ ] Click "RUN SETTLEMENT ENGINE"
- [ ] Verify deterministic rules executed
- [ ] Verify matched trades have `resolution_type=RULE`
- [ ] Verify unmatched trades have breaks created
- [ ] Verify holdings updated for matched trades
- [ ] Verify AUC recalculated
- [ ] Verify NO GPT/AI calls made
- [ ] Verify dashboard button shows "AUTO RESOLVE"

### Test Phase 3: Auto Resolve
- [ ] Click "AUTO RESOLVE"
- [ ] Verify GPT/OpenAI called for remaining breaks
- [ ] Verify high-confidence matches auto-resolved
- [ ] Verify AI-resolved trades have `resolution_type=AI`
- [ ] Verify `resolution_note` contains GPT explanation
- [ ] Verify holdings updated for AI-resolved trades
- [ ] Verify AUC finalized
- [ ] Verify audit logs show AI decisions

### Test GPT Integration
- [ ] Check backend logs for "Attempting reasoning with OpenAI"
- [ ] Verify OpenAI API key is valid (`OPENAI_API_KEY` env var)
- [ ] Test with invalid API key (should fall back to Gemini)
- [ ] Verify AI explanations are meaningful and specific

---

## 🔍 TROUBLESHOOTING

### Issue: Trades reconciling during ingestion
**Problem**: Trades show MATCHED immediately after upload

**Solution**: Check `ingestion.py` for any `ReconOrchestrator` calls - should be NONE

---

### Issue: Settlement engine calling AI
**Problem**: GPT/OpenAI logs appear during Phase 2

**Solution**: Verify `/run-settlement-engine` does NOT call `AIAgent`

---

### Issue: Auto Resolve running rules again
**Problem**: Phase 3 re-matches already matched trades

**Solution**: Verify `/auto-resolve` ONLY queries open breaks, not all unsettled trades

---

### Issue: GPT not being called
**Problem**: No OpenAI logs during Phase 3

**Diagnosis**:
1. Check `OPENAI_API_KEY` environment variable
2. Check backend logs for "Attempting reasoning with OpenAI"
3. Verify `openai_client` is initialized in `llm_gateway.py`

**Solution**: 
- Set valid OpenAI API key
- Restart backend
- Check logs for initialization message

---

### Issue: AI confidence always low
**Problem**: No trades auto-resolved even with good matches

**Diagnosis**:
1. Check AI threshold (default: 0.85)
2. Review GPT responses in logs
3. Check if candidate cash entries exist

**Solution**:
- Lower threshold temporarily for testing
- Improve prompt in `AIAgent._get_ai_reasoning()`
- Ensure cash entries have good descriptions

---

## ✅ SUCCESS CRITERIA

### Phase 1 Complete When:
- [x] Ingestion loads raw data only
- [x] No reconciliation calls
- [x] All trades UNSETTLED
- [x] Button shows "RUN SETTLEMENT ENGINE"

### Phase 2 Complete When:
- [x] Deterministic rules executed
- [x] Matched trades have resolution_type=RULE
- [x] Breaks created for unmatched
- [x] Holdings updated
- [x] NO AI calls
- [x] Button shows "AUTO RESOLVE"

### Phase 3 Complete When:
- [x] GPT/OpenAI called for remaining breaks
- [x] AI-resolved trades have resolution_type=AI
- [x] AI explanations in resolution_note
- [x] Holdings finalized
- [x] Audit trail complete

---

## 🎉 BENEFITS OF 3-PHASE ARCHITECTURE

1. **Clear Separation**: Each phase has distinct responsibility
2. **User Control**: Analysts control when each phase runs
3. **Debuggability**: Easy to identify which phase has issues
4. **Cost Efficiency**: AI only used when needed (Phase 3)
5. **Transparency**: Clear distinction between rule-based and AI decisions
6. **Audit Trail**: Complete record of how each trade was resolved

---

## 📞 SUPPORT

### Documentation References
- This file: Complete 3-phase workflow
- `PHASE_SEPARATION.md`: General architecture principles
- `FIXES_APPLIED.md`: All fixes and changes

### Code References
- Ingestion: `backend/ingestion.py`
- Phase 2: `backend/recon_api.py::run_settlement_engine()`
- Phase 3: `backend/recon_api.py::run_auto_resolve()`
- AI Agent: `backend/ai_layer/agent.py`
- LLM Gateway: `backend/llm_gateway.py`

---

**Implementation Complete**: December 9, 2025  
**Architecture**: 3-Phase Sequential Pipeline  
**AI Integration**: OpenAI GPT-4o (primary) + Gemini 2.5 Pro (fallback)






