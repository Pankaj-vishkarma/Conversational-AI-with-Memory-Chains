from services.memory_service import build_buffer_memory, get_summary
from services.entity_service import get_entities
from services.graph_service import get_graph_context
from services.llm_service import generate_response
from services.persona_service import get_persona 
from models.conversation import Conversation 


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
        entities = get_entities(conversation_id)
        if entities:
            context.append(
                {"role": "system", "content": "Known facts:\n" + "\n".join(entities)}
            )

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

    messages = [{"role": "system", "content": system_prompt}]

    # Step 3: dynamic context
    context = build_context(conversation_id, intent)
    messages.extend(context)

    # Step 4: user input
    messages.append({"role": "user", "content": user_message})

    # Step 5: generate response
    response = generate_response(messages)

    return response
