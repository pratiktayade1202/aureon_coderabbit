# backend/llm_gateway.py
"""
LLM Gateway: Routes AI calls to appropriate models.

- Gemini 1.5 Flash 8B: Lightweight parsing, high throughput (The Eyes)
- OpenAI GPT-4o-mini: Reasoning and decision making (The Brain)
"""
import os
import json
import time
import logging
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)  # Override env vars with .env file values

logger = logging.getLogger(__name__)

# Model configuration - use lighter models for cost efficiency
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-8b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 1. Configure Gemini (The Eyes - for parsing)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info(f"Gemini configured with model: {GEMINI_MODEL}")
    except Exception as e:
        logger.warning(f"Gemini configuration failed: {e}")
else:
    logger.warning("GEMINI_API_KEY not set - Gemini features disabled")

# 2. Configure OpenAI (The Brain - for reasoning)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info(f"OpenAI configured with model: {OPENAI_MODEL}")
    except Exception as e:
        logger.warning(f"OpenAI configuration failed: {e}")
else:
    logger.warning("OPENAI_API_KEY not set - OpenAI features disabled")

class LLMGateway:
    
    @staticmethod
    def call_gemini_flash(prompt):
        """
        THE EYES: Uses Gemini 1.5 Flash 8B for high-throughput parsing.
        8B parameter model = faster, cheaper, better for structured data extraction.
        """
        if not GEMINI_API_KEY:
            logger.warning("Gemini API Key missing. Returning empty dict.")
            return {}

        # Use gemini-1.5-flash-8b - lighter model for parsing tasks
        model = genai.GenerativeModel(
            GEMINI_MODEL, 
            generation_config={"response_mime_type": "application/json"}
        )
        try:
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return {}

    @staticmethod
    def call_openai_brain(prompt, system_role="You are a helpful assistant."):
        """
        THE BRAIN: Uses GPT-4o-mini for reasoning and decision making.
        """
        if not openai_client:
            logger.warning("OpenAI client not configured. Returning empty dict.")
            return {}

        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI Brain Error: {e}")
            return {}

    @staticmethod
    def get_json(prompt):
        return LLMGateway.call_gemini_flash(prompt)

# --- Unified Gateway for Agents ---
def call_llm(prompt: str, model: str = None, json_mode: bool = True) -> str:
    """
    Unified LLM gateway for agent calls.
    Uses configured OPENAI_MODEL by default.
    """
    use_model = model or OPENAI_MODEL
    
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model=use_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"} if json_mode else None
            )
            logger.debug(f"LLM call successful using {use_model}")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"⚠️ LLM Call Failed ({use_model}): {e}. Falling back to simulation.")
    else:
        logger.warning("OpenAI client not available, using simulation fallback")
    
    # Simulation Fallback
    time.sleep(0.8)
    return json.dumps({"decision": "REJECT", "confidence": 0.0})