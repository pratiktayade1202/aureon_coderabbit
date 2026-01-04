# Check Current Workflow State

Run these commands to see what's in your database:

## 1. Check Workflow Status
```bash
curl http://localhost:8000/api/v1/recon/workflow-status
```

## 2. Check for Existing RULE Matches
```bash
# This will show if you have trades matched by rules from previous runs
curl http://localhost:8000/api/v1/recon/trades | jq '.data[] | select(.resolution_type == "RESOLVED_RULE")'
```

## 3. Check for AI Matches
```bash
curl http://localhost:8000/api/v1/recon/trades | jq '.data[] | select(.resolution_type == "RESOLVED_AI")'
```

---

## If You Want to Start Fresh (Reset to Phase 1)

```bash
# This will clear all reconciliation data
curl -X POST http://localhost:8000/api/v1/recon/reset-db
```

Then:
1. Re-upload your files
2. Check workflow status - should show "RUN_SETTLEMENT_ENGINE"
3. Click "Run Settlement Engine" → will show "AUTO_RESOLVE"
4. Click "Auto Resolve" → complete

---

## Expected States

### Fresh Upload (Phase 1)
```json
{
  "workflow": {
    "button_to_show": "RUN_SETTLEMENT_ENGINE"
  },
  "statistics": {
    "rule_matched": 0,
    "ai_matched": 0
  }
}
```

### After Settlement (Phase 2)
```json
{
  "workflow": {
    "button_to_show": "AUTO_RESOLVE"
  },
  "statistics": {
    "rule_matched": 7,  // Some matches
    "ai_matched": 0
  }
}
```

### After AI (Phase 3)
```json
{
  "workflow": {
    "button_to_show": null
  },
  "statistics": {
    "rule_matched": 7,
    "ai_matched": 2
  }
}
```

















