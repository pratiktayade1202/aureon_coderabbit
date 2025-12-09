# backend/llm_gateway.py
"""
Production-grade LLM Gateway with retry logic and failover.

Architecture:
- Gemini 2.5 Pro: Primary model for parsing and reasoning (paid tier with credits)
- GPT-4o: Secondary/fallback for reasoning tasks
- No simulation mode - all failures are logged and propagated
- Retry logic with exponential backoff for transient failures
"""
import json
import logging
import google.generativeai as genai
from openai import AsyncOpenAI, OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from typing import Optional, Dict, Any

from .config import settings

logger = logging.getLogger(__name__)

# === Model Configuration ===
GEMINI_MODEL = getattr(settings, "gemini_model", None) or "gemini-2.5-pro"
OPENAI_MODEL = settings.openai_model

logger.info(f"LLM Gateway initialized with Gemini: {GEMINI_MODEL}, OpenAI: {OPENAI_MODEL}")

# === Configure Gemini (Primary for parsing and reasoning) ===
try:
    genai.configure(api_key=settings.gemini_api_key)
    logger.info(f"✓ Gemini configured successfully with model: {GEMINI_MODEL}")
except Exception as e:
    logger.error(f"✗ Gemini configuration failed: {e}")
    raise RuntimeError(f"Failed to configure Gemini: {e}")

# === Configure OpenAI (Secondary for reasoning, fallback) ===
openai_client: Optional[OpenAI] = None
openai_async_client: Optional[AsyncOpenAI] = None

try:
    openai_client = OpenAI(api_key=settings.openai_api_key)
    openai_async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    logger.info(f"✓ OpenAI configured successfully with model: {OPENAI_MODEL}")
except Exception as e:
    logger.warning(f"⚠ OpenAI configuration failed: {e}. Fallback disabled.")


class LLMGateway:
    """
    Production LLM Gateway with retry logic, failover, and structured error handling.
    """
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def parse_document(
        content: str,
        doc_type: str = "generic",
        response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse and extract structure from documents using Gemini 2.5 Pro.
        
        Optimized for:
        - PDF/CSV/Excel parsing
        - Extracting trades, cash transactions, holdings, NAV data
        - Normalizing dates to YYYY-MM-DD
        - Converting monetary fields to numeric
        
        Args:
            content: Document content (text, CSV, or JSON string)
            doc_type: Type of document (trade, cash, holding, nav, generic)
            response_schema: Optional JSON schema to enforce structure
            
        Returns:
            Dict with parsed structured data
            
        Raises:
            Exception: If parsing fails after retries
        """
        logger.info(f"Parsing document type: {doc_type} (length: {len(content)} chars)")
        
        # Build prompt based on document type
        prompts = {
            "trade": """Extract all trade records from this data. For each trade:
- date: Trade date in YYYY-MM-DD format
- settlement_date: Settlement date in YYYY-MM-DD format (if present)
- symbol: Security symbol/ticker
- isin: ISIN code (if present)
- side: BUY or SELL
- quantity: Number of shares/units (numeric)
- price: Price per unit (numeric)
- amount: Total amount (numeric)
- currency: Currency code (default INR)

Return as JSON: {"trades": [...], "metadata": {"total_count": N}}
Use null for missing fields. Do not invent data.""",
            
            "cash": """Extract all cash transactions from this data. For each transaction:
- date: Transaction date in YYYY-MM-DD format
- value_date: Value date in YYYY-MM-DD format (if present)
- description: Transaction description
- amount: Transaction amount (numeric, positive for credit, negative for debit)
- balance: Running balance (numeric, if present)

Return as JSON: {"transactions": [...], "metadata": {"total_count": N}}
Use null for missing fields. Do not invent data.""",
            
            "holding": """Extract all position holdings from this data. For each holding:
- date: Holding date in YYYY-MM-DD format
- symbol: Security symbol
- isin: ISIN code (if present)
- quantity: Current quantity held (numeric)
- avg_cost: Average cost per unit (numeric)
- market_price: Current market price (numeric)
- total_value: Total market value (numeric)

Return as JSON: {"holdings": [...], "metadata": {"total_count": N}}
Use null for missing fields. Do not invent data.""",
            
            "nav": """Extract NAV data from this document. For each NAV record:
- date: NAV date in YYYY-MM-DD format
- fund_name: Fund name
- isin: ISIN code
- nav_value: NAV per unit (numeric)
- aum: Assets Under Management (numeric)

Return as JSON: {"nav_records": [...], "metadata": {"total_count": N}}
Use null for missing fields. Do not invent data.""",
            
            "generic": """Parse this financial data and extract structured information.
Normalize dates to YYYY-MM-DD format.
Convert all monetary fields to numeric values.
Use null for missing/unavailable fields.
Do not hallucinate data that doesn't exist in the source.

Return as JSON with appropriate structure."""
        }
        
        prompt = f"""{prompts.get(doc_type, prompts['generic'])}

DATA:
{content[:8000]}  # Limit to 8K chars to avoid token limits

CRITICAL RULES:
1. Dates MUST be in YYYY-MM-DD format
2. Numeric fields MUST be numbers (not strings)
3. Use null (not empty string) for missing fields
4. Do not invent or hallucinate records
5. Return valid JSON only
"""
        
        try:
            # Use Gemini 2.5 Pro with JSON response mode
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1  # Low temperature for consistency
                }
            )
            
            response = model.generate_content(prompt)
            result = json.loads(response.text)
            
            logger.info(f"✓ Document parsed successfully using {GEMINI_MODEL}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"✗ JSON decode error from Gemini: {e}")
            logger.error(f"Raw response: {response.text[:500]}")
            raise ValueError(f"Failed to parse JSON response from Gemini: {e}")
            
        except Exception as e:
            logger.error(f"✗ Gemini parsing failed: {e}")
            raise
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def reason_on_discrepancy(context: str, use_json: bool = True) -> str:
        """
        AI reasoning for breaks, discrepancies, and ambiguous cases.
        
        This is the ONLY public reasoning entrypoint for the agent layer.
        
        Strategy:
        1. Try OpenAI first (GPT-4o or o1-*) - optimized for reasoning
        2. Fall back to Gemini 2.5 Pro if OpenAI unavailable/fails
        
        Args:
            context: Detailed context about the discrepancy (trade, break, amounts, etc.)
            use_json: Whether to enforce JSON response format
            
        Returns:
            AI reasoning response (JSON string if use_json=True, else text)
            
        Raises:
            Exception: If all models fail after retries
        """
        logger.info(f"Reasoning on discrepancy (context length: {len(context)} chars)")
        
        system_prompt = """You are an expert financial reconciliation analyst with deep knowledge of:
- Trade settlement cycles (T+0, T+1, T+2)
- Cash management and timing differences
- Corporate actions (dividends, splits, mergers)
- FX settlements and currency conversions
- Break analysis and root cause determination

When analyzing discrepancies:
1. Think step-by-step through the data
2. Consider timing differences and settlement cycles
3. Look for corporate actions or FX impacts
4. Provide specific, actionable recommendations
5. Express confidence levels (0.0 to 1.0)

Be concise but thorough. Focus on root cause and resolution."""

        # Try OpenAI first (optimized for reasoning)
        if openai_client:
            try:
                logger.info(f"Attempting reasoning with OpenAI ({OPENAI_MODEL})")
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ]
                
                kwargs = {
                    "model": OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0.2  # Low but not zero for reasoning
                }
                
                if use_json:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = openai_client.chat.completions.create(**kwargs)
                result = response.choices[0].message.content
                
                logger.info(f"✓ Reasoning completed successfully using OpenAI ({OPENAI_MODEL})")
                return result
                
            except Exception as e:
                logger.warning(f"⚠ OpenAI reasoning failed: {e}. Falling back to Gemini.")
        
        # Fallback to Gemini 2.5 Pro
        try:
            logger.info(f"Attempting reasoning with Gemini ({GEMINI_MODEL})")
            
            config = {"temperature": 0.2}
            if use_json:
                config["response_mime_type"] = "application/json"
            
            model = genai.GenerativeModel(GEMINI_MODEL, generation_config=config)
            
            full_prompt = f"{system_prompt}\n\n{context}"
            response = model.generate_content(full_prompt)
            
            logger.info(f"✓ Reasoning completed successfully using Gemini ({GEMINI_MODEL})")
            return response.text
            
        except Exception as e:
            logger.error(f"✗ Gemini reasoning failed: {e}")
            raise
    
    @staticmethod
    def call_gemini_flash(prompt: str) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Routes to parse_document with generic type.
        """
        logger.warning("call_gemini_flash is deprecated. Use parse_document instead.")
        return LLMGateway.parse_document(prompt, doc_type="generic")
    
    @staticmethod
    def call_openai_brain(prompt: str, system_role: str = None) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Routes to reason_on_discrepancy.
        """
        logger.warning("call_openai_brain is deprecated. Use reason_on_discrepancy instead.")
        
        if system_role:
            context = f"{system_role}\n\n{prompt}"
        else:
            context = prompt
        
        result = LLMGateway.reason_on_discrepancy(context, use_json=True)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from legacy call, returning empty dict")
            return {}
    
    @staticmethod
    def get_json(prompt: str) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Routes to parse_document.
        """
        logger.warning("get_json is deprecated. Use parse_document instead.")
        return LLMGateway.parse_document(prompt, doc_type="generic")


# === Convenience Functions for Direct Use ===

def call_llm(prompt: str, model: str = None, json_mode: bool = True) -> str:
    """
    Unified LLM call for agent/reasoning tasks.
    
    This is a thin wrapper around reason_on_discrepancy for backward compatibility.
    New code should use LLMGateway.reason_on_discrepancy directly.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model name (ignored, uses configured models)
        json_mode: Whether to request JSON response
        
    Returns:
        LLM response as string
    """
    logger.debug("call_llm invoked (routes to reason_on_discrepancy)")
    return LLMGateway.reason_on_discrepancy(prompt, use_json=json_mode)


# === Export Public API ===
__all__ = [
    "LLMGateway",
    "call_llm",
    "GEMINI_MODEL",
    "OPENAI_MODEL"
]
