# Sequential Button Display - Fixed ✓

## Problem
The frontend was showing both "Run Settlement" and "Auto Resolve" buttons at the same time, or jumping directly to "Auto Resolve" without showing "Run Settlement Engine" first.

## Root Cause
The frontend was using a simple `hasBreaks` boolean to decide which button to show, instead of checking the backend's workflow status.

## Solution
Updated `frontend/src/App.jsx` to:

1. **Fetch workflow status** from backend endpoint `/recon/workflow-status`
2. **Use `button_to_show` field** to conditionally render buttons
3. **Show ONLY ONE button at a time** based on the current phase

---

## Changes Made

### 1. State Management (Lines 48-58)
**BEFORE:**
```javascript
const [hasBreaks, setHasBreaks] = useState(false);
```

**AFTER:**
```javascript
const [workflowStatus, setWorkflowStatus] = useState({
  button_to_show: null,
  current_phase: "PHASE_0_NO_DATA",
  next_action: ""
});
```

### 2. Fetch Workflow Status (Lines 58-76)
**NEW FUNCTION:**
```javascript
const fetchWorkflowStatus = useCallback(async () => {
  try {
    const token = await getToken();
    const res = await fetch(`${API_BASE}/recon/workflow-status`, {
      headers: { Authorization: `Bearer ${token || "dev-token"}` }
    });
    if (res.ok) {
      const data = await res.json();
      setWorkflowStatus({
        button_to_show: data.workflow?.button_to_show || null,
        current_phase: data.workflow?.current_phase || "PHASE_0_NO_DATA",
        next_action: data.workflow?.next_action || ""
      });
    }
  } catch (e) {
    console.error("Failed to fetch workflow status:", e);
  }
}, [getToken]);
```

### 3. Updated Button Rendering (Lines 266-296)
**BEFORE:**
```javascript
{hasBreaks ? (
  <button onClick={runAiResolve}>Auto-Resolve</button>
) : (
  <button onClick={runSettlementEngine}>Run Settlement</button>
)}
```

**AFTER:**
```javascript
{/* PHASE 1 → Show "Run Settlement Engine" */}
{workflowStatus.button_to_show === "RUN_SETTLEMENT_ENGINE" && (
  <button onClick={runSettlementEngine}>
    Run Settlement Engine
  </button>
)}

{/* PHASE 2 → Show "Auto-Resolve (AI)" */}
{workflowStatus.button_to_show === "AUTO_RESOLVE" && (
  <button onClick={runAiResolve}>
    Auto-Resolve (AI)
  </button>
)}

{/* PHASE 3 → Show "Complete" indicator */}
{workflowStatus.button_to_show === null && (
  <div>✓ Reconciliation Complete</div>
)}
```

### 4. Removed Old Logic
- Removed `checkBreaks()` function (no longer needed)
- Removed `hasBreaks` state (replaced with `workflowStatus`)

---

## Expected Flow

### 1️⃣ After File Upload (PHASE 1)
```
Dashboard shows:
- [RUN SETTLEMENT ENGINE] button
- Stats: unsettled trades
```

### 2️⃣ After Clicking "Run Settlement Engine" (PHASE 2)
```
Backend runs deterministic rules
Dashboard shows:
- [AUTO-RESOLVE (AI)] button
- Stats: some matched, some breaks
- Button changes automatically!
```

### 3️⃣ After Clicking "Auto-Resolve (AI)" (PHASE 3)
```
Backend runs AI resolution
Dashboard shows:
- ✓ Reconciliation Complete
- No buttons (workflow complete)
```

---

## Testing Steps

### Start Fresh
```bash
# 1. Reset database
curl -X POST http://localhost:8000/api/v1/recon/reset-db

# 2. Check workflow status (should show no data)
curl http://localhost:8000/api/v1/recon/workflow-status
# Expected: {"workflow": {"button_to_show": null, "current_phase": "PHASE_0_NO_DATA"}}
```

### Upload File
```bash
# 3. Upload a file
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@trades.csv"

# 4. Check workflow status
curl http://localhost:8000/api/v1/recon/workflow-status
# Expected: {"workflow": {"button_to_show": "RUN_SETTLEMENT_ENGINE", "current_phase": "PHASE_1_INGESTION"}}
```

**Frontend should now show:** [RUN SETTLEMENT ENGINE] button

### Run Settlement
```bash
# 5. Run settlement engine
curl -X POST http://localhost:8000/api/v1/recon/run-settlement-engine

# 6. Check workflow status
curl http://localhost:8000/api/v1/recon/workflow-status
# Expected: {"workflow": {"button_to_show": "AUTO_RESOLVE", "current_phase": "PHASE_2_SETTLEMENT_COMPLETE"}}
```

**Frontend should now show:** [AUTO-RESOLVE (AI)] button

### Run AI
```bash
# 7. Run AI auto-resolve
curl -X POST http://localhost:8000/api/v1/recon/auto-resolve

# 8. Check workflow status
curl http://localhost:8000/api/v1/recon/workflow-status
# Expected: {"workflow": {"button_to_show": null, "current_phase": "PHASE_3_COMPLETE"}}
```

**Frontend should now show:** ✓ Reconciliation Complete

---

## Why This Works

1. **Backend is the source of truth**: Frontend asks backend "which button should I show?"
2. **Phase detection is automatic**: Backend counts RULE matches vs AI matches
3. **No frontend logic needed**: Just read `button_to_show` field
4. **Sequential flow enforced**: Only one button visible at a time

---

## Troubleshooting

### If buttons still don't appear correctly:

1. **Check browser console** for errors
2. **Verify API endpoint** is reachable:
   ```bash
   curl http://localhost:8000/api/v1/recon/workflow-status
   ```
3. **Clear browser cache** and refresh (Ctrl+Shift+R)
4. **Check network tab** - make sure frontend is calling `/workflow-status`
5. **Verify backend is running** - check terminal for errors

### If it jumps to AUTO_RESOLVE immediately:

This means you have **existing RULE-matched trades** in the database. Solution:
```bash
curl -X POST http://localhost:8000/api/v1/recon/reset-db
```
Then re-upload files and try again.

---

## Summary

✅ Frontend now fetches workflow status from backend  
✅ Buttons appear **sequentially** based on phase  
✅ Only ONE button visible at a time  
✅ Backend controls the workflow progression  
✅ Frontend is read-only and reactive  

The system now correctly implements the 3-phase workflow with proper UI feedback! 🎉

















