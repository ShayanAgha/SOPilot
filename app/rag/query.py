"""
question -> embedding -> FAISS top-K -> threshold check -> Gemini 2.5 Flash
-> grounded answer + cited sources.

Phase 4 will port the class `query.py` logic here. Planned public
function:

    answer_question(question: str, category: str | None = None) -> dict
        Embeds the question with the "query:" E5 prefix, searches the
        shared FAISS index (optionally pre-filtered by SOP category),
        checks the top similarity score against SIMILARITY_THRESHOLD,
        and either:
          - calls Gemini with a strict grounded system prompt and
            returns {"answer": ..., "sources": [...], "grounded": True}
          - or returns the refusal message with "grounded": False
            (app/chat/routes.py then auto-creates an Escalation row).
"""
