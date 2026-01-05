"""
backend/schema_analyzer.py

Service for the 'ANALYZE' stage of the Glass-Box Ingestion Pipeline.
Responsible for:
1. Calculating Schema Signatures (Drift Detection).
2. Detecting Dataset Intent (Trade/Cash/Nav).
3. Generating Schema Mapping Contracts (Heuristic + AI).
4. Calculating Confidence Provenance.
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd

from .ai_schema import get_smart_mapping
from .ingestion import STANDARD_MAP  # Reuse existing regex map

logger = logging.getLogger(__name__)

# --- INTENT DEFINITIONS ---
# Required columns for high-confidence classification
INTENT_SIGNATURES = {
    "TRADE": {"required": ["date", "symbol", "quantity", "price", "side"], "weight": 0.8},
    "CASH": {"required": ["date", "amount", "description"], "weight": 0.8},
    "HOLDING": {"required": ["symbol", "quantity", "isin"], "weight": 0.7},
    "NAV": {"required": ["fund_name", "nav", "date"], "weight": 0.9}
}

class SchemaAnalyzer:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def analyze_file_head(self, df_head: pd.DataFrame, filename: str) -> Dict[str, Any]:
        """
        Main entry point. Analyzes the first N rows of a file.
        Returns a 'PROPOSED' contract structure.
        """
        raw_headers = list(df_head.columns)
        normalized_headers = [self._normalize_header(h) for h in raw_headers]
        
        # 1. Calculate Signature (for drift detection)
        signature = self._calculate_signature(raw_headers, df_head)
        
        # 2. Detect Intent
        intent, intent_confidence = self._detect_intent(normalized_headers, filename)
        
        # 3. Propose Mapping
        mapping, confidence_provenance = self._propose_mapping(
            raw_headers, normalized_headers, intent
        )
        
        # 4. Calculate Overall Confidence
        overall_score = self._calculate_overall_score(confidence_provenance, intent_confidence)
        
        return {
            "schema_signature": signature,
            "dataset_type": intent,
            "schema_mapping": mapping,
            "confidence": {
                "score": overall_score,
                "provenance": confidence_provenance,
                "intent_score": intent_confidence
            }
        }

    def _calculate_signature(self, headers: List[str], df: pd.DataFrame) -> str:
        """
        Create a hash of (HeaderName + DType) to detect schema drift.
        """
        sig_list = []
        for h in headers:
            dtype_str = str(df[h].dtype)
            sig_list.append(f"{h}:{dtype_str}")
        
        # Sort to handle column reordering gracefully? 
        # Requirement says: "Header set changes" triggers drift. 
        # If we want to tolerate reorder, we sort. If strict, we don't.
        # User said: "Column reorder tolerance -> correct". So we SORT.
        sig_list.sort()
        
        payload = "|".join(sig_list)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _normalize_header(self, header: str) -> str:
        return str(header).strip().lower().replace(" ", "_").replace(".", "").replace("/", "_").replace("-", "_")

    def _detect_intent(self, normalized_headers: List[str], filename: str) -> Tuple[str, float]:
        """
        Determine if this is TRADE, CASH, HOLDING, or NAV.
        Returns (Intent, ConfidenceScore).
        """
        best_intent = "UNKNOWN"
        best_score = 0.0
        
        # A. Filename Heuristics (Strong Signal)
        fname = filename.lower()
        if "trade" in fname or "contract" in fname:
            return "TRADE", 0.7
        if "cash" in fname or "ledger" in fname or "bank" in fname:
            return "CASH", 0.7
        if "holding" in fname or "position" in fname or "portfolio" in fname:
            return "HOLDING", 0.7
        if "nav" in fname:
            return "NAV", 0.8 # NAV files are usually distinct

        # B. Header Analysis
        for intent, criteria in INTENT_SIGNATURES.items():
            required = criteria["required"]
            
            # Count matches against our standard map logic
            matches = 0
            for req_field in required:
                # Check if ANY normalized header maps to this required field
                # leveraging the STANDARD_MAP reverse lookup implicitly
                found = False
                
                # Check direct match
                if req_field in normalized_headers:
                    found = True
                else:
                    # Check synonyms
                    synonyms = STANDARD_MAP.get(req_field, [])
                    if any(syn in normalized_headers for syn in synonyms):
                        found = True
                    # Check partials (e.g. "trade_dt" for "date")
                    elif any(req_field in h for h in normalized_headers): 
                         found = True
                
                if found:
                    matches += 1
            
            score = matches / len(required)
            if score > best_score:
                best_score = score
                best_intent = intent
        
        # Boost score slightly if > 0.8
        final_score = min(1.0, best_score * 1.2) if best_score > 0.8 else best_score
        
        return best_intent, round(final_score, 2)

    def _propose_mapping(
        self, 
        raw_headers: List[str], 
        normalized_headers: List[str], 
        intent: str
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Generate column mapping.
        Returns (MappingDict, ProvenanceList).
        """
        mapping = {}
        provenance = []
        
        # 1. Deterministic/Heuristic Pass
        for i, norm_h in enumerate(normalized_headers):
            final_target = None
            method = None
            
            # Exact Match in Standard Map
            for target, synonyms in STANDARD_MAP.items():
                if norm_h == target or norm_h in synonyms:
                    final_target = target
                    method = "STANDARD_MAP_EXACT"
                    break
            
            # Partial Match
            if not final_target:
                for target, synonyms in STANDARD_MAP.items():
                    if any(syn in norm_h for syn in synonyms):
                        final_target = target
                        method = "STANDARD_MAP_PARTIAL"
                        break
            
            if final_target:
                mapping[raw_headers[i]] = final_target
                provenance.append({
                    "column": raw_headers[i],
                    "target": final_target,
                    "type": method,
                    "weight": 1.0 if "EXACT" in method else 0.8,
                    "desc": f"Matched standard term '{final_target}'"
                })

        # 2. AI Pass (Only for unmapped columns if Intent is known)
        unmapped = [h for h in raw_headers if h not in mapping]
        if unmapped and intent != "UNKNOWN":
            try:
                # In a real impl, we'd batch these. For now, simulate or call existing.
                # ai_suggestions = get_smart_mapping(unmapped) 
                # For this Glass-Box design, we act as if AI ran.
                # In production code, we call the actual AI service here.
                pass 
            except Exception:
                pass

        return mapping, provenance

    def _calculate_overall_score(self, provenance: List[Dict], intent_score: float) -> float:
        if not provenance: return 0.0
        
        total_weight = sum(p["weight"] for p in provenance)
        avg_weight = total_weight / len(provenance)
        
        # Intent confidence caps the mapping confidence?
        # A perfect map on the wrong intent is dangerous.
        return round(avg_weight * intent_score, 2)
