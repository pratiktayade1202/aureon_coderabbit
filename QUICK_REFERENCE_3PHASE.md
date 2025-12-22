# 3-Phase Reconciliation - Quick Reference Card

---

## 🚀 THE THREE PHASES

```
1️⃣ INGESTION
   POST /upload
   → Raw data only
   → All UNSETTLED
   → Button: RUN SETTLEMENT ENGINE

2️⃣ SETTLEMENT ENGINE  
   POST /run-settlement-engine
   → Deterministic rules ONLY
   → Creates breaks
   → resolution_type = RULE
   → Button: AUTO RESOLVE

3️⃣ AUTO RESOLVE
   POST /auto-resolve
   → AI/GPT ONLY
   → Resolves breaks
   → resolution_type = AI
   → Button: None (complete)
```

---

## 📋 QUICK TESTS

### Phase 1
```bash
# Upload
curl -X POST .../upload -F "file=@trades.csv"

# Verify
curl .../recon/trades
# ✅ status: UNSETTLED
# ✅ resolution_type: null
```

### Phase 2
```bash
# Run rules
curl -X POST .../recon/run-settlement-engine

# Verify
curl .../recon/trades
# ✅ status: MATCHED (some)
# ✅ resolution_type: RULE
# ✅ breaks created
```

### Phase 3
```bash
# Run AI
curl -X POST .../recon/auto-resolve

# Verify
curl .../recon/trades
# ✅ resolution_type: AI (for AI-resolved)
# ✅ resolution_note: <GPT explanation>
```

---

## 🔍 VERIFY GPT IS WORKING

```bash
# Check logs during Phase 3
docker logs aureon_backend | grep "OpenAI"

# Should see:
# "Attempting reasoning with OpenAI (gpt-4o)"
# "✓ Reasoning completed successfully using OpenAI"
```

---

## ⚠️ COMMON ISSUES

| Issue | Cause | Fix |
|-------|-------|-----|
| GPT called in Phase 2 | Wrong endpoint | Use `/run-settlement-engine` not `/auto-resolve` |
| No AI in Phase 3 | No breaks exist | Run Phase 2 first |
| GPT not called | Bad API key | Check `OPENAI_API_KEY` env var |

---

## 📊 EXPECTED WORKFLOW

```
User uploads files
    ↓ (Phase 1)
10 trades UNSETTLED
    ↓ User clicks "RUN SETTLEMENT ENGINE"
    ↓ (Phase 2 - Rules)
7 matched (RULE), 3 breaks created
    ↓ User clicks "AUTO RESOLVE"
    ↓ (Phase 3 - AI)
2 AI-resolved (AI), 1 needs manual review
    ↓
9 total reconciled, 1 open break
```

---

## 🎯 SUCCESS CHECKLIST

- [ ] Phase 1: All trades UNSETTLED after upload
- [ ] Phase 2: Some matched with resolution_type=RULE
- [ ] Phase 3: AI-resolved with resolution_type=AI
- [ ] Logs show "Attempting reasoning with OpenAI"
- [ ] Holdings updated after Phase 2 and Phase 3
- [ ] Audit trail shows all phases

---

## 📚 FULL DOCS

- **Complete Guide**: `THREE_PHASE_RECONCILIATION.md`
- **Implementation**: `THREE_PHASE_IMPLEMENTATION_SUMMARY.md`
- **Architecture**: `PHASE_SEPARATION.md`

---

**Quick Ref v1.0** | Dec 9, 2025









