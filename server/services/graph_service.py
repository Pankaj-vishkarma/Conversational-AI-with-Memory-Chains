from services.llm_service import generate_response
from models.kg_triple import KGTriple
from extensions import db


def extract_triples(text):
    """
    Extract subject-predicate-object triples using LLM
    """

    prompt = [
        {
            "role": "system",
            "content": (
                "Extract relationships as triples. "
                "Return ONLY valid JSON in this format: "
                '{"triples":[{"subject":"","predicate":"","object":""}]}'
            ),
        },
        {"role": "user", "content": text},
    ]

    try:
        # CHANGE: expect_json=True
        data = generate_response(prompt, expect_json=True)

        if not isinstance(data, dict):
            return []

        return data.get("triples", [])

    except Exception as e:
        print(f"[ERROR] extract_triples: {str(e)}")
        return []


def save_triples(conversation_id, triples):
    """
    Save triples to DB
    """

    try:
        for t in triples:
            subject = t.get("subject")
            predicate = t.get("predicate")
            obj = t.get("object")

            if not subject or not predicate or not obj:
                continue

            new_triple = KGTriple(
                subject=subject,
                predicate=predicate,
                object=obj,
                conversation_id=conversation_id,
            )

            db.session.add(new_triple)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] save_triples: {str(e)}")


def get_graph_context(conversation_id):
    """
    Convert triples to prompt text
    """

    try:
        triples = KGTriple.query.filter_by(conversation_id=conversation_id).all()

        return [f"{t.subject} {t.predicate} {t.object}" for t in triples]

    except Exception as e:
        print(f"[ERROR] get_graph_context: {str(e)}")
        return []