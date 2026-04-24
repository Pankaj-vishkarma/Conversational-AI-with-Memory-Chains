from groq import Groq
from config import Config
import json
import re
import time

client = Groq(api_key=Config.GROQ_API_KEY)


def safe_parse_json(text):
    """
    Extract JSON safely from LLM response
    """
    try:
        return json.loads(text)
    except:
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
    return None


def generate_response(messages, expect_json=False, retries=2):
    """
    Groq response with multi-model fallback (FREE tier safe)
    """

    # UPDATED WORKING MODELS (priority order)
    models = [
        "llama-3.3-70b-versatile",  # primary supported model
        "llama-3.1-8b-instant",  # fast supported fallback
        "openai/gpt-oss-20b",  # lightweight supported fallback
    ]

    last_error = None

    for model in models:
        for attempt in range(retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                    max_tokens=1024,
                )

                content = response.choices[0].message.content

                # JSON safe handling
                if expect_json:
                    parsed = safe_parse_json(content)
                    if parsed:
                        return parsed

                return content

            except Exception as e:
                last_error = str(e)
                print(f"[ERROR] Model {model} attempt {attempt+1}: {last_error}")

                # retry only for same model
                if attempt < retries:
                    time.sleep(1.5)
                else:
                    break  # switch to next model

    # All models failed
    print(f"[FATAL] All models failed: {last_error}")

    return (
        {"error": "LLM failed"}
        if expect_json
        else "Sorry, AI is busy. Please try again."
    )
