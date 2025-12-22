# Frontend Integration - 3-Phase Workflow

**Date**: December 9, 2025  
**Purpose**: Guide for updating frontend to show correct buttons

---

## 🎯 PROBLEM

Frontend is showing "AUTO RESOLVE" button immediately after ingestion.

It should show:
1. After ingestion → **"RUN SETTLEMENT ENGINE"**
2. After settlement → **"AUTO RESOLVE"**
3. After AI resolve → No button (complete)

---

## ✅ SOLUTION

The backend now provides workflow status via two endpoints:

### Option 1: Use Dedicated Workflow Endpoint (RECOMMENDED)

```javascript
// Call this to determine which button to show
GET /api/v1/recon/workflow-status

// Response:
{
  "status": "success",
  "workflow": {
    "current_phase": "PHASE_1_INGESTION",
    "button_to_show": "RUN_SETTLEMENT_ENGINE",  // or "AUTO_RESOLVE" or null
    "next_action": "Run deterministic settlement engine to match trades",
    "can_run_settlement_engine": true,
    "can_run_auto_resolve": false
  },
  "statistics": {
    "total_trades": 10,
    "unsettled_trades": 10,
    "rule_matched": 0,
    "ai_matched": 0,
    "open_breaks": 0
  }
}
```

### Option 2: Use Dashboard Stats (Already Called)

```javascript
// Dashboard stats now includes workflow info
GET /api/v1/recon/dashboard-stats

// Response includes new 'workflow' section:
{
  "status": "success",
  "workflow": {
    "current_phase": "PHASE_1_INGESTION",
    "button_to_show": "RUN_SETTLEMENT_ENGINE",
    "next_action": "Run deterministic settlement engine",
    "phase_progress": {
      "ingestion": true,
      "settlement_engine": false,
      "auto_resolve": false
    }
  },
  "trades": { ... },
  "cash": { ... },
  // ... rest of dashboard data
}
```

---

## 🔧 FRONTEND CHANGES NEEDED

### Step 1: Update Button Logic

```javascript
// In your reconciliation dashboard component
const [workflowStatus, setWorkflowStatus] = useState(null);

// Fetch workflow status
useEffect(() => {
  fetch('/api/v1/recon/workflow-status')
    .then(res => res.json())
    .then(data => setWorkflowStatus(data.workflow));
}, []);

// Render correct button
function renderReconciliationButton() {
  if (!workflowStatus) return null;
  
  const { button_to_show, next_action } = workflowStatus;
  
  if (button_to_show === 'RUN_SETTLEMENT_ENGINE') {
    return (
      <Button onClick={handleRunSettlement}>
        Run Settlement Engine
      </Button>
    );
  }
  
  if (button_to_show === 'AUTO_RESOLVE') {
    return (
      <Button onClick={handleAutoResolve}>
        Auto Resolve (AI)
      </Button>
    );
  }
  
  // No button - reconciliation complete
  return <div>Reconciliation Complete</div>;
}
```

### Step 2: Update Button Handlers

```javascript
// Handler for Phase 2 button
async function handleRunSettlement() {
  try {
    const response = await fetch('/api/v1/recon/run-settlement-engine', {
      method: 'POST'
    });
    const data = await response.json();
    
    console.log('Settlement engine complete:', data);
    // Refresh dashboard and workflow status
    refreshDashboard();
  } catch (error) {
    console.error('Settlement engine failed:', error);
  }
}

// Handler for Phase 3 button
async function handleAutoResolve() {
  try {
    const response = await fetch('/api/v1/recon/auto-resolve', {
      method: 'POST'
    });
    const data = await response.json();
    
    console.log('Auto resolve complete:', data);
    // Refresh dashboard and workflow status
    refreshDashboard();
  } catch (error) {
    console.error('Auto resolve failed:', error);
  }
}
```

### Step 3: Show Phase Progress (Optional)

```javascript
function PhaseIndicator({ workflow }) {
  const phases = [
    { id: 'ingestion', label: 'Data Loaded', complete: workflow.phase_progress.ingestion },
    { id: 'settlement', label: 'Rules Applied', complete: workflow.phase_progress.settlement_engine },
    { id: 'ai', label: 'AI Resolved', complete: workflow.phase_progress.auto_resolve }
  ];
  
  return (
    <div className="phase-progress">
      {phases.map(phase => (
        <div key={phase.id} className={phase.complete ? 'complete' : 'pending'}>
          {phase.label} {phase.complete && '✓'}
        </div>
      ))}
    </div>
  );
}
```

---

## 📊 WORKFLOW STATES

| Phase | button_to_show | Endpoint to Call |
|-------|----------------|------------------|
| Phase 1: After Ingestion | `RUN_SETTLEMENT_ENGINE` | `POST /run-settlement-engine` |
| Phase 2: After Settlement | `AUTO_RESOLVE` | `POST /auto-resolve` |
| Phase 3: Complete | `null` | None |

---

## 🧪 TESTING

### Test 1: After Ingestion
```bash
# Upload files
curl -X POST /upload -F "file=@trades.csv"

# Check workflow status
curl /api/v1/recon/workflow-status

# Should return:
{
  "workflow": {
    "button_to_show": "RUN_SETTLEMENT_ENGINE"
  }
}
```

### Test 2: After Settlement Engine
```bash
# Run settlement
curl -X POST /api/v1/recon/run-settlement-engine

# Check workflow status
curl /api/v1/recon/workflow-status

# Should return:
{
  "workflow": {
    "button_to_show": "AUTO_RESOLVE"
  }
}
```

### Test 3: After Auto Resolve
```bash
# Run AI
curl -X POST /api/v1/recon/auto-resolve

# Check workflow status
curl /api/v1/recon/workflow-status

# Should return:
{
  "workflow": {
    "button_to_show": null  // No button, complete
  }
}
```

---

## 🎨 UI MOCKUP

```
┌─────────────────────────────────────┐
│  Reconciliation Dashboard           │
├─────────────────────────────────────┤
│                                     │
│  Phase Progress:                    │
│  [✓] Data Loaded                    │
│  [ ] Rules Applied                  │
│  [ ] AI Resolved                    │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  RUN SETTLEMENT ENGINE  ◄───┼─── Show this button first
│  └─────────────────────────────┘   │
│                                     │
│  Pending Trades: 10                 │
│  Matched: 0                         │
│  Breaks: 0                          │
└─────────────────────────────────────┘

After clicking "RUN SETTLEMENT ENGINE":

┌─────────────────────────────────────┐
│  Reconciliation Dashboard           │
├─────────────────────────────────────┤
│                                     │
│  Phase Progress:                    │
│  [✓] Data Loaded                    │
│  [✓] Rules Applied                  │
│  [ ] AI Resolved                    │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  AUTO RESOLVE (AI)      ◄───┼─── Show this button second
│  └─────────────────────────────┘   │
│                                     │
│  Pending Trades: 3                  │
│  Matched (Rules): 7                 │
│  Breaks: 3                          │
└─────────────────────────────────────┘
```

---

## 🔍 DEBUGGING

If wrong button shows:

1. **Check workflow status endpoint**:
   ```bash
   curl /api/v1/recon/workflow-status
   ```

2. **Check for RULE matches**:
   ```sql
   SELECT COUNT(*) FROM broker_trades 
   WHERE bank_ref LIKE 'RULE:%';
   ```

3. **Check for AI matches**:
   ```sql
   SELECT COUNT(*) FROM broker_trades 
   WHERE bank_ref LIKE 'AI:%';
   ```

4. **Reset workflow** (if needed):
   ```bash
   # This clears all data and resets to Phase 1
   curl -X POST /api/v1/recon/reset-db
   ```

---

## ✅ QUICK FIX

If you can't update frontend code immediately, you can test by calling endpoints directly:

```bash
# After upload, manually call:
curl -X POST /api/v1/recon/run-settlement-engine

# Then call:
curl -X POST /api/v1/recon/auto-resolve
```

This bypasses the UI but proves the backend workflow works correctly.

---

## 📞 SUPPORT

### Backend Endpoints
- `/workflow-status` - Get current phase and button
- `/dashboard-stats` - Get stats with workflow info
- `/run-settlement-engine` - Phase 2 (rules)
- `/auto-resolve` - Phase 3 (AI)

### Documentation
- `THREE_PHASE_RECONCILIATION.md` - Complete workflow guide
- `QUICK_REFERENCE_3PHASE.md` - Quick testing commands

---

**Integration Complete**: Backend ready  
**Frontend Updates**: See code samples above  
**Testing**: Use `/workflow-status` endpoint









