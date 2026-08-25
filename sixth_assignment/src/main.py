import os
import json
import time
import random
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from openai import OpenAI
from dotenv import load_dotenv
from src.llm.schema import TriageRequest, TriageResponse

load_dotenv()

app = FastAPI()

# Ensure logs directory exists for quarantine logging[cite: 1]
os.makedirs("logs", exist_ok=True)

# Initialize OpenAI client with strict 30-second timeout[cite: 1]
client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    timeout=120.0 
)

def load_prompt():
    with open("prompts/triage-v1.md", "r") as f:
        return f.read()

def call_llm_with_retries(messages, attempt=1):
    """Handles retries on 429 and 5xx errors with exponential backoff and jitter[cite: 1]. Never retries 4xx auth errors[cite: 1]."""
    max_retries = 3
    try:
        start_time = time.time()
        res = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=messages,
            temperature=0.0 # Low temperature for consistent JSON structure[cite: 1]
        )
        duration = int((time.time() - start_time) * 1000)
        return res, duration
    except Exception as e:
        status_code = getattr(e, "status_code", None)
        
        # Retry only on timeouts, rate limits (429), or server errors (5xx)[cite: 1]
        if status_code in [429, 500, 502, 503, 504] or "timeout" in str(e).lower():
            if attempt <= max_retries:
                # Exponential backoff with jitter: 1s, 2s, 4s + random[cite: 1]
                sleep_time = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(sleep_time)
                return call_llm_with_retries(messages, attempt + 1)
            
            raise HTTPException(status_code=504, detail="LLM request timed out or failed after retries.")
        
        # Never retry 400, 401, 403[cite: 1]
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

def extract_json_from_response(content: str) -> str:
    """Strips markdown code fences that models often add[cite: 1]."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()

def log_cost(input_tokens, output_tokens, duration, repairs):
    """Writes a structured log line per call[cite: 1]."""
    log_entry = {
        "timestamp": time.time(),
        "prompt_version": "v1",
        "model": os.getenv("LLM_MODEL"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration,
        "repairs_needed": repairs
    }
    print(f"COST_LOG: {json.dumps(log_entry)}")

@app.post("/triage")
async def triage_message(request: TriageRequest):
    # 1. Kill Switch Check[cite: 1]
    if os.getenv("LLM_ENABLED", "true").lower() == "false":
        return TriageResponse(
            category="other",
            urgency="normal",
            confidence=1.0,
            reason="LLM integration is currently disabled (fallback)."
        )

    # 2. Stub Mode Check[cite: 1]
    if os.getenv("LLM_STUB", "0") == "1":
        return TriageResponse(
            category="billing",
            urgency="high",
            confidence=0.99,
            reason="Stub mode active, no LLM called."
        )

    system_prompt = load_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        # User input is passed safely as a separate message, never glued into the system prompt[cite: 1]
        {"role": "user", "content": request.text}
    ]

    repair_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration = 0

    # 3. First Attempt
    response_obj, duration = call_llm_with_retries(messages)
    total_duration += duration
    total_input_tokens += response_obj.usage.prompt_tokens if response_obj.usage else 0
    total_output_tokens += response_obj.usage.completion_tokens if response_obj.usage else 0
    
    raw_text = response_obj.choices[0].message.content
    clean_text = extract_json_from_response(raw_text)

    # 4. Parse and Validate[cite: 1]
    try:
        parsed_json = json.loads(clean_text)
        validated_data = TriageResponse.model_validate(parsed_json)
        log_cost(total_input_tokens, total_output_tokens, total_duration, repair_count)
        return validated_data
    except (json.JSONDecodeError, ValidationError) as e:
        # 5. Repair Loop (Exactly Once)[cite: 1]
        repair_count = 1
        repair_message = (
            f"Your previous answer was rejected for this reason:\n{str(e)}\n"
            "Return only corrected JSON matching the schema[cite: 1]."
        )
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({"role": "user", "content": repair_message})

        repair_response_obj, repair_duration = call_llm_with_retries(messages)
        total_duration += repair_duration
        total_input_tokens += repair_response_obj.usage.prompt_tokens if repair_response_obj.usage else 0
        total_output_tokens += repair_response_obj.usage.completion_tokens if repair_response_obj.usage else 0
        
        repaired_raw_text = repair_response_obj.choices[0].message.content
        repaired_clean_text = extract_json_from_response(repaired_raw_text)

        try:
            repaired_parsed_json = json.loads(repaired_clean_text)
            validated_repaired_data = TriageResponse.model_validate(repaired_parsed_json)
            log_cost(total_input_tokens, total_output_tokens, total_duration, repair_count)
            return validated_repaired_data
        except (json.JSONDecodeError, ValidationError) as final_e:
            # 6. Quarantine and Give Up[cite: 1]
            quarantine_data = {
                "timestamp": time.time(),
                "input": request.text,
                "prompt_version": "v1",
                "final_error": str(final_e),
                "raw_output": repaired_raw_text
            }
            with open("logs/quarantine.jsonl", "a") as q_file:
                q_file.write(json.dumps(quarantine_data) + "\n")
            
            # Never return raw model text; return 422[cite: 1]
            raise HTTPException(status_code=422, detail="Failed to generate schema-compliant JSON after repair attempt.")