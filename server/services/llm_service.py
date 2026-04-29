import json
import re
import time
from typing import Any, Dict, List

from config import Config
from groq import Groq

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_groq import ChatGroq

    LANGCHAIN_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    LANGCHAIN_AVAILABLE = False
    AIMessage = HumanMessage = SystemMessage = None  # type: ignore
    ChatGroq = None  # type: ignore


DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 1024
_GROQ_CLIENT = None


def get_llm_unavailable_reason() -> str:
    if Config.GROQ_API_KEY:
        return ""
    if not LANGCHAIN_AVAILABLE:
        return "LangChain packages are not installed in the active Python environment."
    return "No API key configured. Set GROQ_API_KEY in server/.env."


def _get_groq_client():
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None and Config.GROQ_API_KEY:
        _GROQ_CLIENT = Groq(api_key=Config.GROQ_API_KEY)
    return _GROQ_CLIENT


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


def _to_langchain_messages(messages: List[Dict[str, str]]) -> List[Any]:
    converted = []
    for msg in messages or []:
        role = (msg.get("role") or "user").lower()
        content = msg.get("content") or ""
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def get_chat_model(temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS):
    """
    Always return a Groq LangChain model for stability.
    """
    if not LANGCHAIN_AVAILABLE:
        print("LangChain not available")
        return None

    if not Config.GROQ_API_KEY:
        print("GROQ_API_KEY missing")
        return None

    return ChatGroq(
        api_key=Config.GROQ_API_KEY,
        model=DEFAULT_GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _generate_with_groq_sdk(messages):
    client = _get_groq_client()
    if client is None:
        raise RuntimeError("No API key configured. Set GROQ_API_KEY in server/.env.")

    response = client.chat.completions.create(
        model=DEFAULT_GROQ_MODEL,
        messages=messages,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    return response.choices[0].message.content


def generate_response(messages, expect_json=False, retries=2):
    """
    LangChain-backed chat response with retry + safe fallback.
    """
    allowed_retries = max(retries, 2)
    last_error = None

    for attempt in range(allowed_retries + 1):
        try:
            chat_model = get_chat_model()

            if chat_model is not None:
                response = chat_model.invoke(_to_langchain_messages(messages))
                content = getattr(response, "content", "") or ""
            elif Config.GROQ_API_KEY:
                content = _generate_with_groq_sdk(messages) or ""
            else:
                raise RuntimeError(get_llm_unavailable_reason())

            # EMPTY RESPONSE FIX
            if not content or not content.strip():
                print("[WARNING] Empty LLM response")
                if attempt < allowed_retries:
                    time.sleep(1)
                    continue
                return (
                    {"error": "Empty response from AI"}
                    if expect_json
                    else "Please try again"
                )

            # JSON FIX
            if expect_json:
                parsed = safe_parse_json(content)
                if parsed:
                    return parsed

                print("[WARNING] JSON parse failed, retrying...")
                if attempt < allowed_retries:
                    time.sleep(1)
                    continue

                return {"error": "Invalid JSON from AI"}

            return content

        except Exception as e:
            last_error = str(e)
            print(f"[ERROR] Model attempt {attempt+1}: {last_error}")

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
