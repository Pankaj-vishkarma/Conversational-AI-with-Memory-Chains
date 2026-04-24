from groq import Groq
from config import Config
import json
import re
import time

client = Groq(api_key=Config.GROQ_API_KEY)
DEFAULT_MODEL = "llama-3.1-8b-instant"


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


def generate_response(messages, expect_json=False, retries=0):
    """
    Groq response with single-model call and bounded retry.
    """
    allowed_retries = min(max(retries, 0), 1)
    last_error = None

    for attempt in range(allowed_retries + 1):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
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
            print(
                f"[ERROR] Model {DEFAULT_MODEL} attempt {attempt+1}: {last_error}"
            )

            # For rate limit errors, do not keep retrying.
            if "429" in last_error:
                return (
                    {"error": "AI is temporarily busy, please try again."}
                    if expect_json
                    else "AI is temporarily busy, please try again."
                )

            if attempt < allowed_retries:
                time.sleep(1)

    print(f"[FATAL] LLM call failed: {last_error}")
    return (
        {"error": "AI is temporarily busy, please try again."}
        if expect_json
        else "AI is temporarily busy, please try again."
    )
