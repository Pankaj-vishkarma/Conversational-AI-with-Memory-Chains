from services.memory_service import (
    build_buffer_memory,
    get_summary,
    get_user_entities_by_conversation,
    get_user_summaries_by_conversation,
    BUFFER_MESSAGE_LIMIT,
)
from services.entity_service import get_entities
from services.graph_service import get_user_graph_context_by_conversation
from services.llm_service import get_chat_model, generate_response
from services.persona_service import get_persona
from models.conversation import Conversation
import re
import tiktoken

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables import (
        RunnableBranch,
        RunnableLambda,
        RunnableParallel,
        RunnableSequence,
    )

    LCEL_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    AIMessage = HumanMessage = SystemMessage = None  # type: ignore
    StrOutputParser = ChatPromptTemplate = MessagesPlaceholder = None  # type: ignore
    RunnableBranch = RunnableLambda = RunnableParallel = RunnableSequence = None  # type: ignore
    LCEL_AVAILABLE = False

_TOKEN_ENCODER = None
RECENT_MESSAGE_LIMIT = 5
AUTO_SWITCH_THRESHOLD = 15
MAX_CONTEXT_TOKENS = 1800


SELF_QUERY_MARKERS = [
    "my name",
    "what is my name",
    "who am i",
    "where do i work",
    "which company do i work",
    "which company do i work?",
    "what is my company",
    "what is my current company",
    "what is my curent company",
    "current company",
    "company name",
    "employer",
    "work at",
    "i work",
    "my preference",
    "what do i like",
    "my city",
    "where do i live",
    "my birthday",
    "remember my",
    "what do you know about me",
    "do you remember",
    "employee id",
    "emp-",
    "project",
    "what project did i tell you",
]


def classify_intent(user_message):
    """
    Detect intent without extra LLM call (performance-safe)
    """
    text = (user_message or "").lower()
    if any(x in text for x in ["analyze", "analysis", "compare", "why", "explain"]):
        return "analysis"
    if any(x in text for x in ["hi", "hello", "hey", "thanks"]):
        return "smalltalk"
    return "question"


def _is_self_memory_query(user_message):
    text = (user_message or "").strip().lower()
    return any(marker in text for marker in SELF_QUERY_MARKERS)


def _infer_fact_label_value(name, description):
    raw_name = (name or "").strip()
    raw_desc = (description or "").strip()
    combined = f"{raw_name} {raw_desc}".lower()
    generic_type_values = {
        "person",
        "human",
        "individual",
        "company",
        "organization",
        "org",
        "location",
        "city",
        "country",
        "project",
        "role",
        "job",
        "name",
    }

    def _contains_any(text, words):
        return any(word in text for word in words)

    def _first_non_generic(candidates, blocked):
        for candidate in candidates:
            value = (candidate or "").strip()
            if not value:
                continue
            if value.lower() in blocked:
                continue
            return value
        return None

    def _best_fact_value(primary, fallback, blocked=None):
        blocked_values = set(v.lower() for v in (blocked or set()))

        first = (primary or "").strip()
        second = (fallback or "").strip()

        if first and first.lower() not in blocked_values:
            return first
        if second and second.lower() not in blocked_values:
            return second
        return ""

    if _contains_any(combined, ["name", "called", "my name"]):
        if raw_name.lower() in ["name", "user name", "username", "full name"]:
            return "name", raw_desc
        if ":" in raw_desc and "name" in raw_desc.lower():
            value = raw_desc.split(":", 1)[-1].strip()
            return "name", value or raw_name
        return "name", raw_name or raw_desc

    if raw_name and _contains_any(raw_desc.lower(), ["person", "human", "individual"]):
        parts = [p for p in raw_name.replace(".", " ").split() if p]
        if len(parts) >= 2:
            return "name", raw_name

    if _contains_any(combined, ["prefer", "preference", "likes", "favorite"]):
        if raw_name.lower() in ["preference", "preferred language", "preferred stack"]:
            return "preference", raw_desc
        return "preference", raw_desc or raw_name

    if _contains_any(combined, ["language", "python", "javascript", "java", "golang"]):
        value = _best_fact_value(raw_desc, raw_name, generic_type_values)
        return ("preferred_language", value) if value else (None, None)

    if _contains_any(combined, ["city", "country", "location", "live in", "from"]):
        value = _best_fact_value(raw_desc, raw_name, generic_type_values)
        return ("location", value) if value else (None, None)

    if _contains_any(
        combined, ["company", "organization", "org", "employer", "work at", "works at"]
    ):
        value = _best_fact_value(raw_desc, raw_name, generic_type_values)
        return ("company", value) if value else (None, None)

    if _contains_any(
        combined, ["employee id", "emp-", "employee number", "staff id", "id"]
    ):
        emp_match = re.search(r"\bemp[-_\s]?[a-z0-9]+\b", combined, flags=re.IGNORECASE)
        if emp_match:
            return "employee_id", emp_match.group(0).replace(" ", "-").upper()

        blocked = {"employee id", "emp id", "employee number", "staff id", "id"}
        value = _first_non_generic([raw_desc, raw_name], blocked)
        if value:
            return "employee_id", value
        return None, None

    if _contains_any(combined, ["project", "current project", "working on"]):
        blocked = {"project", "current project", "my project"}
        value = _first_non_generic([raw_desc, raw_name], blocked)
        if value:
            return "project", value
        return None, None

    if _contains_any(combined, ["job", "role", "profession", "work as"]):
        value = _best_fact_value(raw_desc, raw_name, generic_type_values)
        return ("role", value) if value else (None, None)

    if _contains_any(combined, ["birthday", "dob"]):
        value = _best_fact_value(raw_desc, raw_name, generic_type_values)
        return ("birthday", value) if value else (None, None)

    return None, None


def _format_user_facts_for_prompt(facts):
    """
    Convert labeled fact tuples into prompt-safe markdown list.
    """
    if not facts:
        return "None"
    return "\n".join(
        [f"* You told me your {label} is {value}." for label, value in facts]
    )


def _rewrite_identity_confusions(response_text):
    """
    Rewrite accidental first-person user-fact statements into second-person phrasing.
    Keeps response generation flow unchanged while enforcing identity boundaries.
    """
    text = (response_text or "").strip()
    if not text:
        return text

    replacement_rules = [
        (r"\bI currently work at\b", "You currently work at"),
        (r"\bI work at\b", "You work at"),
        (r"\bI am employed at\b", "You are employed at"),
        (r"\bMy company is\b", "Your company is"),
        (r"\bI live in\b", "You live in"),
        (r"\bI am from\b", "You are from"),
        (r"\bMy name is\b", "Your name is"),
        (r"\bI am ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", r"You are \1"),
        (r"\bI like\b", "You like"),
        (r"\bI prefer\b", "You prefer"),
        (r"\bMy birthday is\b", "Your birthday is"),
    ]

    rewritten = text
    for pattern, replacement in replacement_rules:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    return rewritten


def _get_encoder():
    global _TOKEN_ENCODER
    if _TOKEN_ENCODER is None:
        try:
            _TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _TOKEN_ENCODER = False
    return _TOKEN_ENCODER


def _count_tokens(text):
    if not text:
        return 0
    encoder = _get_encoder()
    if not encoder:
        return max(1, len(text) // 4)
    try:
        return len(encoder.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _fit_recent_messages(
    history, max_tokens=MAX_CONTEXT_TOKENS, max_messages=RECENT_MESSAGE_LIMIT
):
    selected = []
    used = 0
    for msg in reversed(history or []):
        content = msg.get("content") or ""
        cost = _count_tokens(content)
        if selected and (used + cost > max_tokens or len(selected) >= max_messages):
            break
        selected.append(msg)
        used += cost
    return list(reversed(selected))


def get_merged_entities(conversation_id):
    """
    Fetch conversation entities + cross-session global entities for the same user.
    Deduplicate by normalized entity name and keep the latest update.
    """
    merged = {}

    try:
        conversation = Conversation.query.filter_by(id=conversation_id).first()
        if not conversation:
            fallback = get_entities(conversation_id)
            return [], fallback

        all_entities = get_user_entities_by_conversation(conversation_id)

        for entity in all_entities:
            is_current_conversation = entity.conversation_id == conversation_id

            key = (entity.name or "").strip().lower()
            if not key:
                continue

            existing = merged.get(key)
            if not existing:
                merged[key] = {
                    "name": entity.name.strip(),
                    "description": (entity.description or "").strip(),
                    "updated_at": entity.created_at,
                    "is_global": not is_current_conversation,
                }
                continue

            existing_ts = existing.get("updated_at")
            entity_ts = entity.created_at
            if existing_ts is None or (entity_ts and entity_ts > existing_ts):
                merged[key] = {
                    "name": entity.name.strip(),
                    "description": (entity.description or "").strip(),
                    "updated_at": entity.created_at,
                    "is_global": not is_current_conversation,
                }

        labeled_user_facts = {}
        conversation_context = []
        for item in merged.values():
            raw_name = item["name"]
            raw_desc = item["description"]
            line = f"{raw_name}: {raw_desc}"

            label, value = _infer_fact_label_value(raw_name, raw_desc)
            if item["is_global"] and label and value:
                existing = labeled_user_facts.get(label)
                if (
                    not existing
                    or existing["updated_at"] is None
                    or (
                        item["updated_at"] is not None
                        and item["updated_at"] > existing["updated_at"]
                    )
                ):
                    labeled_user_facts[label] = {
                        "value": value,
                        "updated_at": item["updated_at"],
                    }
                continue

            conversation_context.append(line)

        user_facts = [
            (label, payload["value"])
            for label, payload in sorted(
                labeled_user_facts.items(), key=lambda x: x[0].lower()
            )
        ]
        conversation_context.sort(key=lambda x: x.lower())
        return user_facts, conversation_context

    except Exception:
        fallback = get_entities(conversation_id)
        return [], fallback


def _get_cross_session_summary(conversation_id, limit=3):
    summaries = get_user_summaries_by_conversation(conversation_id)
    if not summaries:
        return ""

    blocks = []
    for item in summaries[:limit]:
        if item.content:
            blocks.append(item.content.strip())
    return "\n\n".join(blocks)


def build_context(conversation_id, intent, user_message):
    """
    Build context dynamically based on intent.
    Kept for compatibility and fallback use.
    """
    context = []

    effective_memory = _resolve_memory_strategy(conversation_id, intent, user_message)

    if intent == "analysis" or effective_memory in {"summary", "hybrid"}:
        summary = get_summary(conversation_id) or _get_cross_session_summary(
            conversation_id
        )
        if summary:
            context.append(
                {"role": "system", "content": f"Conversation summary:\n{summary}"}
            )

    if effective_memory in {"entity", "hybrid"} or (
        intent == "question" and _is_self_memory_query(user_message)
    ):
        user_facts, conversation_entities = get_merged_entities(conversation_id)
        combined = []
        if user_facts:
            combined.append("User Facts:\n" + _format_user_facts_for_prompt(user_facts))
        if conversation_entities:
            combined.append(
                "Conversation Context:\n"
                + "\n".join(
                    [f"* You told me: {item}" for item in conversation_entities]
                )
            )

        if combined:
            context.append({"role": "system", "content": "\n\n".join(combined)})

    if effective_memory in {"kg", "hybrid"} or intent in ["analysis", "question"]:
        graph = get_user_graph_context_by_conversation(conversation_id)
        if graph:
            context.append(
                {"role": "system", "content": "Relationships:\n" + "\n".join(graph)}
            )

    history = _fit_recent_messages(
        build_buffer_memory(conversation_id, max_messages=BUFFER_MESSAGE_LIMIT)
    )
    context.extend(history)
    return context


def _resolve_memory_strategy(conversation_id, intent, user_message):
    conversation = Conversation.query.filter_by(id=conversation_id).first()
    configured = (
        (conversation.memory_type if conversation else "buffer") or "buffer"
    ).lower()
    history = build_buffer_memory(conversation_id, max_messages=0)

    if configured == "hybrid":
        return "hybrid"
    if configured == "buffer" and len(history) >= AUTO_SWITCH_THRESHOLD:
        return "hybrid"
    if configured == "buffer" and intent == "analysis":
        return "summary"
    if configured == "buffer" and _is_self_memory_query(user_message):
        return "entity"
    return configured


def _memory_flags(conversation, intent, user_message):
    conversation_id = conversation.id if conversation else None
    memory_type = (
        _resolve_memory_strategy(conversation_id, intent, user_message)
        if conversation_id
        else "buffer"
    )

    flags = {
        "use_summary": memory_type in {"summary", "hybrid"},
        "use_entities": memory_type in {"entity", "hybrid"},
        "use_graph": memory_type in {"kg", "hybrid"},
    }

    if intent == "analysis":
        flags["use_summary"] = True

    if intent in {"analysis", "question"} and memory_type in {"buffer", "kg", "hybrid"}:
        flags["use_graph"] = True

    if _is_self_memory_query(user_message):
        flags["use_entities"] = True

    return flags


def _resolve_persona_prompt(conversation, intent):
    persona_name = None

    if conversation and conversation.persona_id:
        persona = get_persona(conversation.persona_id)
        if persona:
            persona_name = persona.name
            if persona.system_prompt:
                return persona.system_prompt

    persona_prompts = {
        "assistant": (
            "You are a helpful assistant. Respond directly, clearly, and practically. "
            "Do not mention internal context or memory unless the user asks."
        ),
        "summarizer": (
            "You are the Summarizer persona. You MUST respond in short, concise form. "
            "Use a maximum of 3 lines. Focus only on the essential answer. "
            "Do not provide long explanations, examples, or extra detail unless explicitly asked."
        ),
        "research helper": (
            "You are the Research Helper persona. You MUST provide detailed, structured, "
            "research-level answers. Use clear sections, explain reasoning, include relevant "
            "context, and give actionable conclusions. Avoid overly brief responses."
        ),
    }

    if persona_name:
        prompt = persona_prompts.get(persona_name.lower())
        if prompt:
            return prompt

    if intent == "analysis":
        return "You are an expert analyst. Give deep, structured explanations."
    if intent == "smalltalk":
        return "You are a friendly casual assistant."
    return "You are a precise assistant. Answer clearly and concisely."


def _build_system_prompt(payload):
    identity_guard = """
Identity Rules:
* You are the assistant, not the user.
* Treat memory and entities as user-provided facts.
* Refer to those facts naturally as remembered user statements, e.g. "You told me you work at Google."
* Prefer current-state phrasing when applicable, e.g. "You currently work at Microsoft."
* Never claim user facts as your own (do not say "I work at Google") unless persona explicitly defines that as assistant identity.
* Always refer to the user as "you" when using memory facts.
* Never use first-person ("I", "my", "me") to describe user facts.
"""
    base_prompt = f"{payload['persona_prompt']}\n\n{identity_guard}"

    if payload.get("self_facts"):
        return f"""{base_prompt}

User Facts:
{payload["self_facts"]}

Instructions:
* Use persona style.
* Use memory only for user-related questions.
* If user-specific fact is missing, say: "I don't have that information yet".
* Keep assistant and user identity separate. User facts must be referenced as user facts.
* When citing remembered facts, use second-person phrasing ("you/your"), never first-person ("I/my").
* Otherwise answer normally.
"""

    return base_prompt


def _build_prompt_values(payload):
    return {
        "system_prompt": _build_system_prompt(payload),
        "summary": payload.get("summary") or "None",
        "entities": payload.get("entities") or "None",
        "graph_context": payload.get("graph_context") or "None",
        "recent_messages": payload.get("recent_messages") or [],
        "user_input": payload["user_message"],
    }


def _to_prompt_messages(messages):
    if not LCEL_AVAILABLE:
        return messages

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


def run_conversation_chain(conversation_id, user_message):
    """
    LCEL conversation chain:
    classify -> branch -> parallel memory load -> prompt -> model -> normalize
    """
    conversation = Conversation.query.filter_by(id=conversation_id).first()
    chat_model = get_chat_model()

    if LCEL_AVAILABLE:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "{system_prompt}\n\n"
                    "Conversation Summary:\n{summary}\n\n"
                    "Entities:\n{entities}\n\n"
                    "Knowledge Graph Context:\n{graph_context}",
                ),
                MessagesPlaceholder("recent_messages"),
                ("human", "{user_input}"),
            ]
        )
    else:
        prompt = None

    # MAIN LCEL FLOW
    if chat_model is not None and LCEL_AVAILABLE:

        def _seed_payload(_):
            return {
                "conversation_id": conversation_id,
                "conversation": conversation,
                "user_message": user_message,
            }

        def _classify(payload):
            payload["intent"] = classify_intent(payload["user_message"])
            payload["memory_flags"] = _memory_flags(
                payload["conversation"], payload["intent"], payload["user_message"]
            )
            return payload

        def _prepare_branch(payload, branch_name):
            payload["branch"] = branch_name
            return payload

        branch = RunnableBranch(
            (
                lambda payload: payload["intent"] == "analysis",
                RunnableLambda(lambda payload: _prepare_branch(payload, "analysis")),
            ),
            (
                lambda payload: payload["intent"] == "smalltalk",
                RunnableLambda(lambda payload: _prepare_branch(payload, "smalltalk")),
            ),
            RunnableLambda(lambda payload: _prepare_branch(payload, "question")),
        )

        parallel_context = RunnableParallel(
            conversation_id=RunnableLambda(lambda payload: payload["conversation_id"]),
            conversation=RunnableLambda(lambda payload: payload["conversation"]),
            user_message=RunnableLambda(lambda payload: payload["user_message"]),
            intent=RunnableLambda(lambda payload: payload["intent"]),
            branch=RunnableLambda(lambda payload: payload["branch"]),
            persona_prompt=RunnableLambda(
                lambda payload: _resolve_persona_prompt(
                    payload["conversation"], payload["intent"]
                )
            ),
            summary=RunnableLambda(
                lambda payload: (
                    get_summary(payload["conversation_id"])
                    or _get_cross_session_summary(payload["conversation_id"])
                    if payload["memory_flags"]["use_summary"]
                    else ""
                )
            ),
            entities=RunnableLambda(
                lambda payload: (
                    "\n".join(get_merged_entities(payload["conversation_id"])[1])
                    if payload["memory_flags"]["use_entities"]
                    else ""
                )
            ),
            graph_context=RunnableLambda(
                lambda payload: (
                    "\n".join(
                        get_user_graph_context_by_conversation(
                            payload["conversation_id"]
                        )
                    )
                    if payload["memory_flags"]["use_graph"]
                    else ""
                )
            ),
            recent_messages=RunnableLambda(
                lambda payload: _to_prompt_messages(
                    _fit_recent_messages(
                        build_buffer_memory(
                            payload["conversation_id"],
                            max_messages=BUFFER_MESSAGE_LIMIT,
                        )
                    )
                )
            ),
            self_facts=RunnableLambda(
                lambda payload: (
                    _format_user_facts_for_prompt(
                        get_merged_entities(payload["conversation_id"])[0]
                    )
                    if _is_self_memory_query(payload["user_message"])
                    else ""
                )
            ),
        )

        chain = RunnableSequence(
            first=RunnableLambda(_seed_payload),
            middle=[
                RunnableLambda(_classify),
                branch,
                parallel_context,
                RunnableLambda(_build_prompt_values),
                prompt,
                chat_model,
                StrOutputParser(),
            ],
            last=RunnableLambda(_rewrite_identity_confusions),
        )

        # CRITICAL FIX (TRY-CATCH ADDED)
        try:
            return chain.invoke(None)
        except Exception as e:
            print("[CHAIN ERROR]:", str(e))

    # FALLBACK FLOW (UNCHANGED LOGIC)
    intent = classify_intent(user_message)

    fallback_messages = [
        {
            "role": "system",
            "content": _build_system_prompt(
                {
                    "persona_prompt": _resolve_persona_prompt(conversation, intent),
                    "self_facts": (
                        _format_user_facts_for_prompt(
                            get_merged_entities(conversation_id)[0]
                        )
                        if _is_self_memory_query(user_message)
                        else ""
                    ),
                }
            ),
        }
    ]

    fallback_messages.extend(build_context(conversation_id, intent, user_message))
    fallback_messages.append({"role": "user", "content": user_message})

    response = generate_response(fallback_messages)
    return _rewrite_identity_confusions(response)
