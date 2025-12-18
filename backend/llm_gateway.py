# backend/llm_gateway.py
"""
Production-grade LLM Gateway - Gemini First Architecture.

Architecture:
- Gemini 2.0 Flash Exp: PRIMARY model for parsing AND reasoning.
- GPT-4o: OPTIONAL fallback (only used if configured and Gemini fails).
- Retry logic with exponential backoff.
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
GEMINI_MODEL = getattr(settings, "gemini_model", None) or "gemini-2.0-flash-exp"
OPENAI_MODEL = settings.openai_model

# Gemini supports very large context windows; don't artificially throttle input.
# Keep this as characters (not tokens) since we typically start from raw text.
GEMINI_PARSE_MAX_CHARS = 100_000

logger.info(f"LLM Gateway initialized. Primary: {GEMINI_MODEL}")

# === Configure Gemini (PRIMARY) ===
try:
    genai.configure(api_key=settings.gemini_api_key)
    logger.info(f"✓ Gemini configured successfully as PRIMARY.")
except Exception as e:
    logger.critical(f"✗ Gemini configuration failed: {e}")
    raise RuntimeError(f"Failed to configure Gemini: {e}")

# === Configure OpenAI (OPTIONAL FALLBACK) ===
openai_client: Optional[OpenAI] = None
openai_async_client: Optional[AsyncOpenAI] = None

if settings.openai_api_key:
    try:
        openai_client = OpenAI(api_key=settings.openai_api_key)
        openai_async_client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info(f"✓ OpenAI configured as FALLBACK ({OPENAI_MODEL})")
    except Exception as e:
        logger.warning(f"⚠ OpenAI configuration failed: {e}. Fallback disabled.")
else:
    logger.info("ℹ OpenAI fallback disabled (Key not provided).")


class LLMGateway:
    """
    Gemini-First LLM Gateway.
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
        Parse documents using Gemini (Primary).
        """
        logger.info(f"Parsing document type: {doc_type} (length: {len(content)} chars)")
        
        # Build prompt based on document type
        prompts = {
            "trade": """Extract all trade records. Return JSON: {\"trades\": [...], \"metadata\": {\"total_count\": N}}""",
            "cash": """Extract all cash transactions. Return JSON: {\"transactions\": [...], \"metadata\": {\"total_count\": N}}""",
            "generic": """Parse this financial data. Return structured JSON."""
        }
        
        base_prompt = prompts.get(doc_type, prompts['generic'])
        
        prompt = f"""{base_prompt}

DATA:
{content[:GEMINI_PARSE_MAX_CHARS]}  # Leverage Gemini's large context window

CRITICAL RULES:
1. Dates MUST be in YYYY-MM-DD format
2. Numeric fields MUST be numbers
3. Use null for missing fields
4. Return valid JSON only
"""
        
        try:
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1
                }
            )
            
            response = model.generate_content(prompt)
            result = json.loads(response.text)
            
            logger.info(f"✓ Document parsed successfully using {GEMINI_MODEL}")
            return result
            
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
        AI reasoning for breaks.
        
        STRATEGY:
        1. Attempt Gemini (Primary)
        2. If Gemini fails AND OpenAI is configured -> Fallback to OpenAI
        """
        logger.info(f"Reasoning on discrepancy (context length: {len(context)} chars)")
        
        system_prompt = """You are an expert financial reconciliation analyst.
Analyze the provided trade and cash candidates.
Identify the best match or explain the break.
Return JSON with keys: best_match_id (int|null), confidence (float), action (MATCH|REVIEW|ESCALATE), explanation (str)."""

        full_prompt = f"{system_prompt}\n\n{context}"

        # --- STRATEGY 1: GEMINI (PRIMARY) ---
        try:
            logger.info(f"Attempting reasoning with PRIMARY: {GEMINI_MODEL}")
            
            config = {"temperature": 0.2}
            if use_json:
                config["response_mime_type"] = "application/json"
            
            model = genai.GenerativeModel(GEMINI_MODEL, generation_config=config)
            response = model.generate_content(full_prompt)
            
            logger.info(f"✓ Reasoning complete via Gemini")
            return response.text
            
        except Exception as gemini_err:
            logger.warning(f"⚠ Gemini reasoning failed: {gemini_err}")
            
            # --- STRATEGY 2: OPENAI (FALLBACK) ---
            if openai_client:
                logger.info(f"🔄 Activating FALLBACK: {OPENAI_MODEL}")
                try:
                    kwargs = {
                        "model": OPENAI_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": context}
                        ],
                        "temperature": 0.2
                    }
                    
                    if use_json:
                        kwargs["response_format"] = {"type": "json_object"}
                    
                    response = openai_client.chat.completions.create(**kwargs)
                    result = response.choices[0].message.content
                    logger.info(f"✓ Fallback reasoning successful via OpenAI")
                    return result
                    
                except Exception as openai_err:
                    logger.error(f"✗ Fallback failed: {openai_err}")
                    raise openai_err  # Raise original error if fallback also dies
            
            # If no fallback configured, re-raise Gemini error
            logger.error("✗ No fallback configured. Propagating Gemini error.")
            raise gemini_err

    # === Legacy Methods (Routers) ===
    @staticmethod
    def call_gemini_flash(prompt: str) -> Dict[str, Any]:
        return LLMGateway.parse_document(prompt, doc_type="generic")
    
    @staticmethod
    def call_openai_brain(prompt: str, system_role: str = None) -> Dict[str, Any]:
        context = f"{system_role}\n\n{prompt}" if system_role else prompt
        result = LLMGateway.reason_on_discrepancy(context, use_json=True)
        try:
            return json.loads(result)
        except:
            return {}
    
    @staticmethod
    def get_json(prompt: str) -> Dict[str, Any]:
        return LLMGateway.parse_document(prompt, doc_type="generic")


def call_llm(prompt: str, model: str = None, json_mode: bool = True) -> str:
    return LLMGateway.reason_on_discrepancy(prompt, use_json=json_mode)

__all__ = ["LLMGateway", "call_llm", "GEMINI_MODEL", "OPENAI_MODEL"]
