# Aureon System Architecture - Complete Guide

**Version**: 2.0  
**Last Updated**: December 2025  
**Status**: Production-Ready

---

## 🏗️ SYSTEM OVERVIEW

**Aureon** is a deterministic settlement engine for post-trade finance operations in India. It automates trade reconciliation, cash ledger matching, and holdings verification using a hybrid architecture: **SQL-based deterministic rules** + **AI reasoning** for edge cases.

### Core Philosophy
- **95% Deterministic**: Fast, auditable SQL rules handle the bulk
- **5% AI-Assisted**: LLM reasoning only for ambiguous breaks
- **Zero Hallucinations**: AI operates in read-only "air-gapped" mode
- **Full Audit Trail**: Every decision is logged and traceable

---

## 📐 ARCHITECTURE LAYERS

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Landing  │  │Dashboard │  │Ingestion │  │Neural   │      │
│  │  Page    │  │  View    │  │  Panel   │  │  Core   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                    HTTP/REST API
                            │
┌─────────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI + SQLAlchemy)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Ingestion   │  │Reconciliation│  │  AI Layer   │        │
│  │   API       │  │     API      │  │   (Agent)   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                   │
│              ┌────────────▼────────────┐                      │
│              │  Rule Engine Core      │                      │
│              │  (Deterministic)       │                      │
│              └────────────┬────────────┘                      │
└───────────────────────────┼───────────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │   PostgreSQL (Neon)      │
              │   - broker_trades        │
              │   - bank_txns            │
              │   - holdings             │
              │   - recon_breaks         │
              │   - recon_proposals      │
              │   - processed_files      │
              │   - recon_locks          │
              └──────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │   External AI Services   │
              │   - OpenAI GPT-4o         │
              │   - Google Gemini 2.0     │
              └───────────────────────────┘
```

---

## 🎨 FRONTEND ARCHITECTURE

### Technology Stack
- **Framework**: React 18+ with Vite
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion
- **Auth**: Clerk (JWT-based)
- **State Management**: React Hooks (useState, useEffect, useCallback)
- **API Client**: Custom hooks (`useAureonApi`) + Fetch API

### Key Components

#### 1. **App.jsx** (Main Application Shell)
- **Purpose**: Root component, manages global state and routing
- **Key State**:
  - `activeTab`: Current view (Dashboard, Ingestion, Neural Core, Settings)
  - `workflowStatus`: Current phase and which button to show
  - `stats`: Dashboard metrics (AUC, pending settlements, etc.)
  - `reconData`: Trade data for display
- **Key Functions**:
  - `fetchWorkflowStatus()`: Polls `/api/v1/recon/workflow-status` to determine current phase
  - `fetchStats()`: Gets dashboard statistics
  - `runSettlementEngine()`: Triggers Phase 2
  - `runAiResolve()`: Triggers Phase 3

#### 2. **Landing.jsx** (Public Landing Page)
- **Purpose**: Marketing/onboarding page with password-protected investor deck
- **Features**:
  - Protocol ticker (SWIFT, NSDL, CDSL, etc.)
  - Technical architecture showcase
  - Investor access modal (password: `aureon2025`)
  - Links to PitchDeck component

#### 3. **Dashboard View** (Main App)
- **Components**:
  - `StatsGrid`: Shows AUC, pending settlements, match rate
  - `DataTable`: Displays trades/holdings/NAV with filtering
  - `BreakDrawer`: Forensic terminal-style break analysis
  - **Workflow Buttons** (dynamically shown based on phase):
    - "Run Settlement Engine" (Phase 1 → Phase 2)
    - "Auto-Resolve (AI)" (Phase 2 → Phase 3)
    - "Commit AI Proposals" (Phase 3 - Air Gap)

#### 4. **Ingestion Panel**
- **Components**:
  - `FileUploader`: Drag-and-drop file upload
  - `IngestionConsole`: Shows upload logs and history
- **Flow**: Upload → SHA256 hash check → Process → Display results

#### 5. **Neural Core (Learner)**
- **Purpose**: View learned patterns from manual resolutions
- **Components**:
  - `PatternList`: Shows learned rules
  - `PatternInspector`: Details of selected pattern
- **API**: `/api/v1/learned-rules`

### Frontend API Integration

**Base URL**: Configured in `config.js` → Always `/api/v1`

**Key Endpoints Used**:
```javascript
// Dashboard
GET  /api/v1/recon/dashboard-stats
GET  /api/v1/recon/workflow-status
GET  /api/v1/recon/trades?page=1&page_size=50

// Ingestion
POST /api/v1/ingestion/upload
GET  /api/v1/ingestion/upload/history

// Reconciliation
POST /api/v1/recon/run-settlement-engine  // Phase 2
POST /api/v1/recon/auto-resolve            // Phase 3
POST /api/v1/recon/proposals/commit        // Air Gap Executor

// Breaks & Analysis
GET  /api/v1/recon/breaks
GET  /api/v1/recon/analyze/{trade_id}
POST /api/v1/recon/resolve-trade/{trade_id}  // Manual resolve

// Neural Core
GET  /api/v1/learned-rules
POST /api/v1/learned-rules/train
```

---

## ⚙️ BACKEND ARCHITECTURE

### Technology Stack
- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL (Neon) via SQLAlchemy ORM
- **AI Services**: OpenAI GPT-4o (primary), Google Gemini 2.0 (fallback)
- **File Processing**: Pandas, pdfplumber, openpyxl
- **Auth**: JWT tokens (Clerk integration)

### API Structure

**Base Path**: `/api/v1`

**Router Organization**:
```
/api/v1/
  ├── /ingestion/          → ingestion_api.py
  │   ├── POST /upload
  │   ├── GET  /upload/history
  │   └── DELETE /upload/{file_id}
  │
  ├── /recon/              → recon_api.py
  │   ├── POST /run-settlement-engine    (Phase 2)
  │   ├── POST /auto-resolve             (Phase 3)
  │   ├── POST /proposals/commit         (Air Gap)
  │   ├── GET  /dashboard-stats
  │   ├── GET  /workflow-status
  │   ├── GET  /trades
  │   ├── GET  /breaks
  │   ├── GET  /analyze/{trade_id}
  │   └── POST /resolve-trade/{trade_id}
  │
  ├── /rules/              → rules_api.py
  │   └── GET  /list
  │
  ├── /learned-rules       → learning_api.py
  │   ├── GET  /
  │   └── POST /train
  │
  └── /system/
      └── POST /reset
```

### Core Modules

#### 1. **ingestion.py** (Data Ingestion Engine)
**Purpose**: Parse and normalize raw financial data files

**Flow**:
1. **File Reading**: Supports CSV, Excel, PDF, ZIP
2. **Column Mapping**: 
   - AI-first: Uses Gemini 2.0 Flash to map columns intelligently
   - Fallback: Deterministic pattern matching
3. **Data Quality Checks**:
   - Weekend trading detection
   - Negative price validation
   - Missing identifier checks
4. **Normalization**:
   - Date formats → ISO dates
   - Side values: B/S → BUY/SELL
   - Currency codes
5. **Database Insert**:
   - Routes to appropriate table based on file type:
     - `broker_trades` (trades)
     - `bank_txns` (cash)
     - `holdings` (positions)
     - `nav_logs` (NAV data)
   - **All trades inserted with `status='UNSETTLED'`**
   - **No reconciliation logic runs here**

**Key Functions**:
- `process_file_content()`: Main entry point
- `normalize_columns()`: AI + deterministic column mapping
- `route_and_save()`: Routes data to correct table

#### 2. **recon_api.py** (Reconciliation API)
**Purpose**: Orchestrates the 3-phase reconciliation workflow

**Key Endpoints**:

**Phase 2: `/run-settlement-engine`**
- Calls `ReconOrchestrator.run_trade_recon()`
- Runs **ONLY deterministic rules** (no AI)
- Creates `ReconBreak` records for unmatched trades
- Updates holdings for matched trades
- Sets `bank_ref = "RULE:..."` for matched trades
- Returns: `{phase: "PHASE_2_DETERMINISTIC", matches: N, breaks: M}`

**Phase 3: `/auto-resolve`**
- **Air-Gap Mode**: Creates `ReconProposal` records (doesn't mutate ledger)
- For each open break:
  - Calls `AIAgent.analyze_single_trade()`
  - If confidence ≥ 0.80: Creates proposal
- Returns: `{phase: "PHASE_3_AI_PROPOSAL", proposals_created: N}`

**Air Gap Executor: `/proposals/commit`**
- Applies pending proposals above confidence threshold (default: 0.90)
- Updates trade status to MATCHED
- Updates holdings
- Sets `bank_ref = "AI_COMMIT:..."`

**Workflow Status: `/workflow-status`**
- Determines current phase based on database state:
  - `PHASE_0_NO_DATA`: No trades
  - `PHASE_1_INGESTION`: Trades exist, no rule matches
  - `PHASE_2_SETTLEMENT_COMPLETE`: Rule matches exist, open breaks remain
  - `PHASE_3_PROPOSALS_PENDING`: AI proposals waiting for commit
  - `PHASE_3_COMPLETE`: All reconciled
- Returns which button to show

#### 3. **rule_engine/orchestrator.py** (Deterministic Engine)
**Purpose**: Executes SQL-based matching rules

**Flow**:
1. **Fetch Unsettled Trades**: `WHERE status='UNSETTLED'`
2. **Fetch Unused Cash**: `WHERE status='UNUSED'`
3. **Run Rules** (via `ReconciliationEngine`):
   - **TIER_1_DETERMINISTIC**: Exact amount + date match
   - **TIER_2_TOLERANCE**: Amount within tolerance (e.g., 0.1%)
4. **For Each Match**:
   - Update trade: `status='MATCHED'`, `bank_ref='RULE:...'`
   - Update cash: `status='MATCHED'`, `trade_ref=trade.id`
   - Apply to holdings (BUY increases, SELL decreases)
5. **For Unmatched Trades**:
   - Create `ReconBreak` record
   - Set `status='OPEN'`

**Key Functions**:
- `run_trade_recon()`: Main reconciliation loop
- `_apply_single_trade_to_holdings()`: Updates holdings for matched trade

#### 4. **ai_layer/agent.py** (AI Reasoning Agent)
**Purpose**: Analyzes ambiguous breaks using LLM reasoning

**Flow**:
1. **Fetch Trade**: Get trade details from database
2. **Find Candidates**: Search for cash entries within 1% amount tolerance
3. **If Multiple Candidates or Ambiguous**:
   - Call `LLMGateway.reason_on_discrepancy()`
   - Pass: Trade details, candidate cash entries, context
4. **LLM Gateway** (Model-Agnostic):
   - Tries OpenAI GPT-4o first
   - Falls back to Gemini 2.0 if OpenAI fails
   - Returns: `{best_match_id, confidence, action, explanation}`
5. **Return Analysis**:
   ```python
   {
       "found": True,
       "best_candidate": {...},
       "ai_suggestion": {
           "confidence": 0.92,
           "action": "MATCH",
           "explanation": "Forex adjustment match..."
       }
   }
   ```

**Key Functions**:
- `analyze_single_trade()`: Main analysis function
- Uses `LLMGateway` for all AI calls (vendor-agnostic)

#### 5. **llm_gateway.py** (AI Gateway)
**Purpose**: Unified interface for multiple LLM providers

**Flow**:
1. **Primary**: Attempt OpenAI GPT-4o
2. **Fallback**: If OpenAI fails → Try Gemini 2.0
3. **Returns**: Structured JSON with confidence, explanation, action

**Models**:
- **OpenAI**: `gpt-4o` (temperature: 0.2)
- **Gemini**: `gemini-2.0-flash-exp` (temperature: 0.3)

---

## 🔄 THE COMPLETE DATA FLOW

### Phase 1: INGESTION (Raw Data Load)

```
User Uploads File
    ↓
[ingestion_api.py] POST /api/v1/ingestion/upload
    ↓
1. Acquire Tenant Lock (prevent concurrent uploads)
2. Calculate SHA256 Hash
3. Check ProcessedFile table for duplicates
   → If COMPLETED: Return 409 Conflict
4. Create ProcessedFile record (status=PROCESSING)
    ↓
[ingestion.py] process_file_content()
    ↓
1. Parse File (CSV/Excel/PDF)
   - Chunked reading for large CSVs (5k rows)
   - AI column mapping (Gemini) on first chunk
   - Cached mapping for subsequent chunks
2. Data Quality Checks
   - Weekend trading
   - Negative prices
   - Missing identifiers
3. Normalize Data
   - Dates → ISO format
   - Side: B/S → BUY/SELL
   - Currency codes
4. Route to Database Table
   - broker_trades (status='UNSETTLED')
   - bank_txns (status='UNUSED')
   - holdings (snapshot)
   - nav_logs
    ↓
Update ProcessedFile (status=COMPLETED, rows_processed=N)
    ↓
Frontend: Shows success message, refreshes dashboard
```

**Database State After Phase 1**:
- All trades: `status='UNSETTLED'`
- All cash: `status='UNUSED'`
- No breaks created
- No reconciliation metadata

---

### Phase 2: SETTLEMENT ENGINE (Deterministic Rules)

```
User Clicks "Run Settlement Engine"
    ↓
[recon_api.py] POST /api/v1/recon/run-settlement-engine
    ↓
1. Acquire Tenant Lock
2. Create ReconOrchestrator instance
    ↓
[orchestrator.py] run_trade_recon()
    ↓
1. Fetch Unsettled Trades
   SELECT * FROM broker_trades 
   WHERE tenant_id=X AND status='UNSETTLED'
    ↓
2. Fetch Unused Cash
   SELECT * FROM bank_txns 
   WHERE tenant_id=X AND status='UNUSED'
    ↓
3. Run ReconciliationEngine
   - TIER_1: Exact amount + date match
   - TIER_2: Amount within tolerance
    ↓
4. For Each Match:
   - Update trade: status='MATCHED', bank_ref='RULE:...'
   - Update cash: status='MATCHED', trade_ref=trade.id
   - Apply to holdings (BUY/SELL logic)
   - Create ReconLog (audit trail)
    ↓
5. For Unmatched Trades:
   - Create ReconBreak (status='OPEN')
    ↓
Return: {matches: N, breaks: M}
    ↓
Frontend: Updates dashboard, shows "AUTO RESOLVE" button
```

**Database State After Phase 2**:
- Some trades: `status='MATCHED'`, `bank_ref='RULE:...'`
- Some trades: `status='UNSETTLED'` + `ReconBreak` record
- Holdings updated for matched trades
- Breaks created for unmatched trades

---

### Phase 3: AUTO RESOLVE (AI Reasoning)

```
User Clicks "Auto-Resolve (AI)"
    ↓
[recon_api.py] POST /api/v1/recon/auto-resolve
    ↓
1. Acquire Tenant Lock
2. Fetch Open Breaks
   SELECT * FROM recon_breaks 
   WHERE tenant_id=X AND status='OPEN'
    ↓
3. For Each Break:
   [ai_layer/agent.py] analyze_single_trade(trade_id)
       ↓
   a. Fetch trade details
   b. Find candidate cash entries (within 1% tolerance)
   c. If ambiguous → Call LLM Gateway
       ↓
   [llm_gateway.py] reason_on_discrepancy()
       ↓
   - Try OpenAI GPT-4o
   - Fallback to Gemini 2.0
   - Return: {confidence, explanation, best_match_id}
       ↓
   d. If confidence ≥ 0.80:
      - Create ReconProposal (status='PENDING')
      - Store: trade_id, cash_id, confidence, explanation
    ↓
4. Return: {proposals_created: N}
    ↓
Frontend: Shows "Commit AI Proposals" button
```

**Database State After Phase 3 (Before Commit)**:
- `ReconProposal` records created (status='PENDING')
- Trades still `status='UNSETTLED'`
- **No ledger mutations yet** (Air Gap)

---

### Phase 3 (Continued): COMMIT PROPOSALS (Air Gap Executor)

```
User Clicks "Commit AI Proposals"
    ↓
[recon_api.py] POST /api/v1/recon/proposals/commit
    ↓
1. Acquire Tenant Lock
2. Fetch Pending Proposals
   SELECT * FROM recon_proposals 
   WHERE tenant_id=X AND status='PENDING' AND confidence >= 0.90
    ↓
3. For Each Proposal:
   - Update trade: status='MATCHED', bank_ref='AI_COMMIT:...'
   - Update cash: status='MATCHED'
   - Close break: status='RESOLVED'
   - Apply to holdings
   - Update proposal: status='APPROVED'
   - Create ReconLog (audit)
    ↓
4. Return: {committed: N}
    ↓
Frontend: Shows reconciliation complete
```

**Database State After Commit**:
- AI-resolved trades: `status='MATCHED'`, `bank_ref='AI_COMMIT:...'`
- Proposals: `status='APPROVED'`
- Breaks: `status='RESOLVED'`
- Holdings updated

---

## 🗄️ DATABASE SCHEMA

### Core Data Tables

**broker_trades**
- Stores trade data from broker contract notes
- Key fields: `symbol`, `side`, `quantity`, `price`, `amount`, `date`
- Status: `UNSETTLED` → `MATCHED`
- Resolution tracking: `bank_ref` (contains "RULE:..." or "AI_COMMIT:...")

**bank_txns**
- Stores cash ledger entries from bank statements
- Key fields: `date`, `amount`, `description`, `value_date`
- Status: `UNUSED` → `MATCHED`
- Links to trade via `trade_ref` (FK to broker_trades.id)

**holdings**
- Stores portfolio positions (Assets Under Custody)
- Key fields: `symbol`, `quantity`, `total_value`, `market_price`
- Updated when trades are matched (BUY increases, SELL decreases)
- Unique constraint: `(symbol, tenant_id)`

**nav_logs**
- Stores NAV (Net Asset Value) history
- Key fields: `date`, `nav_value`, `aum` (Assets Under Management)

### Reconciliation Tables

**recon_breaks**
- Created when trades can't be matched
- Key fields: `trade_id`, `cash_id`, `break_type`, `severity`, `status`
- Status: `OPEN` → `RESOLVED`

**recon_proposals**
- **Air Gap Table**: AI suggestions before commit
- Key fields: `trade_id`, `cash_id`, `confidence`, `explanation`, `status`
- Status: `PENDING` → `APPROVED` / `REJECTED`
- Only proposals with `confidence >= 0.90` are auto-committed

**recon_logs**
- Full audit trail of all reconciliation actions
- Records: Who, What, When, Why for every match/resolution

### Safety & Isolation Tables

**processed_files**
- **Phase 2: Ingestion Safety**
- Tracks all uploaded files with SHA256 hash
- Prevents duplicate uploads (409 Conflict if hash exists)
- Status: `PROCESSING` → `COMPLETED` / `FAILED`
- Unique constraint: `(tenant_id, file_hash)`

**recon_locks**
- **Phase 3: Tenant Isolation**
- Mutex lock to prevent concurrent heavy operations
- One lock per tenant (primary key: `tenant_id`)
- Fields: `locked_until`, `process_name`
- Prevents: Upload + Settlement running simultaneously

**learning_events**
- Stores manual resolutions for Neural Core training
- Source: `HUMAN_MANUAL` (when analyst manually resolves)
- Used by `learner.py` to learn new patterns

**rule_memory**
- Stores learned rules from Neural Core
- Pattern-based matching rules learned from manual resolutions

---

## 🔒 SECURITY & SAFETY FEATURES

### 1. **Ingestion Safety (Phase 2)**
- **SHA256 Hashing**: Every file is hashed before processing
- **Duplicate Detection**: Blocks duplicate uploads (409 Conflict)
- **State Tracking**: PROCESSING → COMPLETED/FAILED
- **Transaction Safety**: Rollback on failure

### 2. **Tenant Isolation (Phase 3)**
- **Database Mutex**: `ReconLock` table prevents concurrent operations
- **Lock Timeout**: 5 minutes (configurable)
- **Protected Operations**:
  - File upload
  - Settlement engine
  - AI auto-resolve
  - Proposal commit
- **Error**: 409 Conflict if system is busy

### 3. **AI Safety (Air Gap)**
- **Proposal System**: AI creates proposals, doesn't mutate ledger
- **Human Review**: Proposals require explicit commit
- **Confidence Threshold**: Only high-confidence proposals (≥0.90) auto-commit
- **Audit Trail**: Every AI decision is logged

### 4. **Data Integrity**
- **Idempotent Ingestion**: Same file hash = same result
- **Transaction Safety**: All operations wrapped in DB transactions
- **Rollback on Error**: Failed operations don't leave partial state

---

## 🤖 AI INTEGRATION

### Model Selection Strategy

**Primary**: OpenAI GPT-4o
- **When**: All AI reasoning calls
- **Why**: Best reasoning capability
- **Fallback**: If OpenAI fails → Gemini 2.0 Flash

**Fallback**: Google Gemini 2.0 Flash
- **When**: OpenAI API unavailable or errors
- **Why**: Cost-effective, fast inference

### AI Usage Points

1. **Column Mapping** (Ingestion):
   - Uses Gemini 2.0 Flash to map CSV/Excel columns
   - Caches mapping after first chunk
   - Falls back to deterministic patterns

2. **Break Analysis** (Phase 3):
   - Uses GPT-4o (primary) or Gemini (fallback)
   - Analyzes ambiguous trade-cash matches
   - Returns confidence score + explanation

3. **Neural Core Training** (Learner):
   - Analyzes manual resolution patterns
   - Learns new matching rules
   - Stores in `rule_memory` table

### Air Gap Architecture

**Critical Design**: AI never directly mutates the ledger

```
AI Analysis
    ↓
Creates ReconProposal (status='PENDING')
    ↓
Human Reviews (or auto-commit if confidence ≥ 0.90)
    ↓
Executor Applies Proposal
    ↓
Ledger Updated
```

This ensures:
- **Zero Hallucination Risk**: AI can't make mistakes that aren't caught
- **Full Audit Trail**: Every AI decision is recorded before execution
- **Human Override**: Analysts can reject AI proposals

---

## 📊 WORKFLOW STATE MACHINE

```
PHASE_0_NO_DATA
    ↓ (User uploads file)
PHASE_1_INGESTION
    ↓ (User clicks "Run Settlement Engine")
PHASE_2_SETTLEMENT_COMPLETE
    ↓ (User clicks "Auto-Resolve")
PHASE_3_PROPOSALS_PENDING
    ↓ (User clicks "Commit Proposals")
PHASE_3_COMPLETE
```

**Button Logic** (from `/workflow-status`):
- `PHASE_1`: Show "RUN SETTLEMENT ENGINE"
- `PHASE_2`: Show "AUTO RESOLVE"
- `PHASE_3_PROPOSALS_PENDING`: Show "COMMIT AI PROPOSALS"
- `PHASE_3_COMPLETE`: No button (all done)

---

## 🔄 TYPICAL USER JOURNEY

1. **Analyst logs in** → Clerk authentication → JWT token
2. **Uploads trade file** → SHA256 hash → Duplicate check → Process → Insert trades (UNSETTLED)
3. **Uploads cash ledger** → Process → Insert cash (UNUSED)
4. **Clicks "Run Settlement Engine"** → Deterministic rules match 95% of trades → Breaks created for 5%
5. **Clicks "Auto-Resolve"** → AI analyzes breaks → Creates proposals
6. **Clicks "Commit Proposals"** → High-confidence proposals applied → Holdings updated
7. **Reviews remaining breaks** → Opens BreakDrawer → Sees AI reasoning → Manually resolves if needed
8. **Exports report** → CSV download with full audit trail

---

## 🎯 KEY DESIGN DECISIONS

### Why 3-Phase Separation?
- **Clarity**: Each phase has a single, clear purpose
- **Performance**: Deterministic rules are fast (no LLM calls)
- **Cost**: AI only used for edge cases (5% of trades)
- **Auditability**: Clear separation of rule-based vs AI-based matches

### Why Air Gap for AI?
- **Safety**: Prevents AI hallucinations from corrupting data
- **Transparency**: Analysts see AI reasoning before commit
- **Compliance**: Full audit trail of AI decisions

### Why Tenant Isolation?
- **Scale**: Prevents database deadlocks
- **User Experience**: Clear error messages ("System busy")
- **Reliability**: One operation per tenant at a time

### Why SHA256 Hashing?
- **Idempotency**: Same file = same result
- **Deduplication**: Prevents accidental re-processing
- **Audit**: Track which files were processed

---

## 🚀 DEPLOYMENT ARCHITECTURE

**Frontend**: Vercel (React/Vite)
- Environment: `VITE_API_URL` points to backend
- Build: Static assets served via CDN

**Backend**: Vercel Serverless Functions (FastAPI)
- Environment: `DATABASE_URL` (Neon Postgres)
- Environment: `GEMINI_API_KEY`, `OPENAI_API_KEY`
- Auto-scaling based on traffic

**Database**: Neon Postgres
- Serverless Postgres with connection pooling
- SSL required (handled in `database.py`)
- Auto-creates tables on first deployment

**AI Services**: External APIs
- OpenAI: `api.openai.com`
- Google: `generativelanguage.googleapis.com`

---

## 📈 METRICS & MONITORING

**Key Metrics Tracked**:
- Match rate (rule-based vs AI-based)
- Processing time per phase
- Break resolution rate
- AI confidence distribution
- Tenant lock conflicts

**Audit Trail**:
- Every action logged in `recon_logs`
- File processing tracked in `processed_files`
- AI proposals in `recon_proposals`
- Manual resolutions in `learning_events`

---

This architecture ensures **deterministic, auditable, and safe** reconciliation at scale.


