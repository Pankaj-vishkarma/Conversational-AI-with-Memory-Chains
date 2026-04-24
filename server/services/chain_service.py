from services.memory_service import build_buffer_memory, get_summary
from services.entity_service import get_entities
from services.graph_service import get_graph_context
from services.llm_service import generate_response
from services.persona_service import get_persona
from models.conversation import Conversation
from models.entity import Entity


def classify_intent(user_message):
    """
    Detect intent
    """

    prompt = [
        {
            "role": "system",
            "content": (
                "Classify intent strictly into one word: "
                "question, analysis, smalltalk"
            ),
        },
        {"role": "user", "content": user_message},
    ]

    try:
        result = generate_response(prompt).lower()

        if "analysis" in result:
            return "analysis"
        elif "small" in result:
            return "smalltalk"
        else:
            return "question"

    except:
        return "question"


def _is_global_entity(name, description):
    """
    Decide if an entity is an important cross-session user fact.
    """
    text = f"{name or ''} {description or ''}".lower()
    global_markers = [
        "name",
        "preference",
        "prefer",
        "likes",
        "dislikes",
        "bio",
        "personal",
        "about me",
        "myself",
        "location",
        "city",
        "country",
        "timezone",
        "language",
        "role",
        "job",
        "birthday",
        "dob",
    ]
    return any(marker in text for marker in global_markers)


def _parse_entity_line(entity_line):
    """
    Parse 'name: description' lines used by entity_service.get_entities.
    """
    if ":" not in entity_line:
        return entity_line.strip(), ""
    name, desc = entity_line.split(":", 1)
    return name.strip(), desc.strip()


def _infer_fact_label_value(name, description):
    """
    Normalize entity data into structured user-fact fields.
    Returns (label, value) or (None, None) if not a user fact.
    """
    raw_name = (name or "").strip()
    raw_desc = (description or "").strip()
    combined = f"{raw_name} {raw_desc}".lower()

    def _contains_any(text, words):
        return any(word in text for word in words)

    if _contains_any(combined, ["name", "called", "my name"]):
        # Prefer explicit "name" labels.
        if raw_name.lower() in ["name", "user name", "username", "full name"]:
            return "name", raw_desc
        if ":" in raw_desc and "name" in raw_desc.lower():
            value = raw_desc.split(":", 1)[-1].strip()
            return "name", value or raw_name
        return "name", raw_name or raw_desc

    if _contains_any(combined, ["prefer", "preference", "likes", "favorite"]):
        if raw_name.lower() in ["preference", "preferred language", "preferred stack"]:
            return "preference", raw_desc
        return "preference", raw_desc or raw_name

    if _contains_any(combined, ["language", "python", "javascript", "java", "golang"]):
        return "preferred_language", raw_desc or raw_name

    if _contains_any(combined, ["city", "country", "location", "live in", "from"]):
        return "location", raw_desc or raw_name

    if _contains_any(combined, ["job", "role", "profession", "work as"]):
        return "role", raw_desc or raw_name

    if _contains_any(combined, ["birthday", "dob"]):
        return "birthday", raw_desc or raw_name

    return None, None


def _format_user_facts_for_prompt(facts):
    """
    Convert labeled fact tuples into prompt-safe markdown list.
    """
    if not facts:
        return "None"
    return "\n".join([f"* {label}: {value}" for label, value in facts])


def get_merged_entities(conversation_id):
    """
    Fetch conversation entities + cross-session global entities for the same user.
    Deduplicate by normalized entity name and keep the latest update.
    """
    merged = {}

    try:
        # (a) Current conversation entities (existing behavior preserved)
        current_entities = get_entities(conversation_id)
        for item in current_entities:
            name, desc = _parse_entity_line(item)
            key = name.lower()
            if key:
                merged[key] = {
                    "name": name,
                    "description": desc,
                    "updated_at": None,
                    "is_global": _is_global_entity(name, desc),
                }

        # (b) Global entities from user's other conversations
        conversation = Conversation.query.filter_by(id=conversation_id).first()
        if not conversation:
            return [], current_entities

        user_conversation_ids = [
            c.id
            for c in Conversation.query.filter_by(user_id=conversation.user_id).all()
            if c.id != conversation_id
        ]

        if not user_conversation_ids:
            global_entities = []
        else:
            global_entities = (
                Entity.query.filter(Entity.conversation_id.in_(user_conversation_ids))
                .order_by(Entity.updated_at.desc())
                .all()
            )

        for entity in global_entities:
            if not _is_global_entity(entity.name, entity.description):
                continue

            key = (entity.name or "").strip().lower()
            if not key:
                continue

            existing = merged.get(key)
            if not existing:
                merged[key] = {
                    "name": entity.name.strip(),
                    "description": (entity.description or "").strip(),
                    "updated_at": entity.updated_at,
                    "is_global": True,
                }
                continue

            # Prioritize latest information for duplicate entities.
            existing_ts = existing.get("updated_at")
            entity_ts = entity.updated_at
            if existing_ts is None or (entity_ts and entity_ts > existing_ts):
                merged[key] = {
                    "name": entity.name.strip(),
                    "description": (entity.description or "").strip(),
                    "updated_at": entity.updated_at,
                    "is_global": True,
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
                # Latest value wins for each labeled field.
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

        # Keep deterministic output.
        user_facts = [
            (label, payload["value"])
            for label, payload in sorted(
                labeled_user_facts.items(), key=lambda x: x[0].lower()
            )
        ]
        conversation_context.sort(key=lambda x: x.lower())
        return user_facts, conversation_context

    except Exception:
        # Safe fallback to previous behavior
        fallback = get_entities(conversation_id)
        return [], fallback


def build_context(conversation_id, intent):
    """
    Build context dynamically based on intent
    """

    context = []

    # 1. SUMMARY (for analysis-heavy queries)
    if intent == "analysis":
        summary = get_summary(conversation_id)
        if summary:
            context.append(
                {"role": "system", "content": f"Conversation summary:\n{summary}"}
            )

    # 2. ENTITY (for factual questions)
    if intent == "question":
        user_facts, conversation_entities = get_merged_entities(conversation_id)
        combined = []
        if user_facts:
            combined.append("User Facts:\n" + _format_user_facts_for_prompt(user_facts))
        if conversation_entities:
            combined.append(
                "Conversation Context:\n" + "\n".join(conversation_entities)
            )

        if combined:
            context.append({"role": "system", "content": "\n\n".join(combined)})

    # 3. GRAPH (optional for deeper reasoning)
    if intent in ["analysis", "question"]:
        graph = get_graph_context(conversation_id)
        if graph:
            context.append(
                {"role": "system", "content": "Relationships:\n" + "\n".join(graph)}
            )

    # 4. SMALLTALK → minimal context

    # 5. Recent messages always add
    history = build_buffer_memory(conversation_id)[-5:]
    context.extend(history)

    return context


def run_conversation_chain(conversation_id, user_message):
    """
    Branching chain:
    classify → route → build context → generate
    """

    # Step 0: Load conversation + persona
    conversation = Conversation.query.filter_by(id=conversation_id).first()

    persona_name = None

    if conversation and conversation.persona_id:
        persona = get_persona(conversation.persona_id)
        if persona:
            persona_name = persona.name

    # Step 1: classify intent
    intent = classify_intent(user_message)

    # Step 2: system prompt (persona override)
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

    system_prompt = None

    if persona_name:
        system_prompt = persona_prompts.get(persona_name.lower())

    if not persona_name or not system_prompt:
        if intent == "analysis":
            system_prompt = (
                "You are an expert analyst. Give deep, structured explanations."
            )
        elif intent == "smalltalk":
            system_prompt = "You are a friendly casual assistant."
        else:
            system_prompt = "You are a precise assistant. Answer clearly and concisely."

    user_facts, _ = get_merged_entities(conversation_id)
    entity_context = _format_user_facts_for_prompt(user_facts)

    system_prompt = f"""{system_prompt}

User Facts:
{entity_context}

Instructions:
* These are facts about the user.
* If user asks about themselves (name, preferences, etc.), ALWAYS use this information.
* Do NOT say "I don't know" if the answer exists above.
* Answer confidently using this data.
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Step 3: dynamic context
    context = build_context(conversation_id, intent)
    messages.extend(context)

    # Step 4: user input
    messages.append({"role": "user", "content": user_message})

    # Step 5: generate response
    response = generate_response(messages)

    return response
