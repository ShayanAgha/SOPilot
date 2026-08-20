"""
PDF -> chunks -> multilingual-e5 embeddings -> FAISS index.

Phase 2 will port the class `ingest.py` logic here as plain functions
(no Flask/DB imports in this module -- routes call into these functions,
not the other way around, per the assignment's separation-of-concerns
requirement).

Planned public functions:
    ingest_document(document_id: int) -> None
        Loads the PDF at Document.stored_path, chunks it, embeds each
        chunk with the "passage:" E5 prefix, adds vectors to the shared
        FAISS index (via app.rag.store), and updates the Document row's
        status/page_count/chunk_count/ingested_at fields.
        Runs inside a background threading.Thread kicked off from
        app/admin/routes.py (Phase 3) so it never blocks the request.
"""
