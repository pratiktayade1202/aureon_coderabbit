# backend/llm_gateway.py
import os
import json
import time
import random
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 1. Configure Gemini (The Eyes)
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Warning: Gemini Key missing: {e}")

# 2. Configure OpenAI (The Brain)
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"Warning: OpenAI Key missing: {e}")
    openai_client = None

class LLMGateway:
    
    @staticmethod
    def call_gemini_flash(prompt):
        """
        THE EYES: Uses Gemini Flash Lite for higher RPM limits.
        """
        if not os.getenv("GEMINI_API_KEY"):
            print("Gemini API Key missing. Returning empty dict.")
            return {}

        # --- REVERTED TO LITE MODEL ---
        # Using 'gemini-2.5-flash-lite' as requested for higher throughput
        model = genai.GenerativeModel('gemini-2.5-flash-lite', 
            generation_config={"response_mime_type": "application/json"}
        )
        try:
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini Ingestion Error: {e}")
            return {}

    @staticmethod
    def call_openai_brain(prompt, system_role="You are a helpful assistant."):
        """
        THE BRAIN: Uses GPT-4o-mini.
        """
        if not openai_client:
            return {}

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"OpenAI Brain Error: {e}")
            return {}

    @staticmethod
    def get_json(prompt):
        return LLMGateway.call_gemini_flash(prompt)

# --- Unified Gateway for Agents ---
def call_llm(prompt: str, model: str = "gpt-4o", json_mode: bool = True) -> str:
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"} if json_mode else None
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ LLM Call Failed: {e}. Falling back to simulation.")
    
    # Simulation Fallback
    time.sleep(0.8)
    return json.dumps({"decision": "REJECT", "confidence": 0.0})