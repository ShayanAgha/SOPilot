"""
PDF → chunks → multilingual-e5-base embeddings → FAISS index.

Public API:
    ingest_document(document_id, app)
        Loads the PDF at Document.stored_path, splits into overlapping
        text chunks, embeds each chunk with the "passage:" E5 prefix,
        adds vectors to the shared FAISS index (via app.rag.store), and
        updates the Document row's status/page_count/chunk_count/
        ingested_at fields.

        Designed to run inside a background threading.Thread kicked off
        from app/admin/routes.py — it never blocks the request thread.
        It uses a pushed Flask app context so DB writes work correctly
        from the background thread.
"""
import os
import time
from datetime import datetime

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.rag import store as vector_store

# ---------------------------------------------------------------------------
# Module-level model cache (loaded once, reused across ingestions)
# ---------------------------------------------------------------------------
_model: SentenceTransformer | None = None


def _get_model(model_name: str) -> SentenceTransformer:
    global _model
    if _model is None:
        try:
            _model = SentenceTransformer(
                model_name,
                device="cpu",
                model_kwargs={"low_cpu_mem_usage": False},
            )
        except Exception:
            _model = SentenceTransformer(model_name, device="cpu")
    return _model


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _extract_text_by_page(pdf_path: str) -> list[tuple[int, str]]:
    """Return [(page_number_1_indexed, text), …] for every page in the PDF."""
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append((i, text))
    return pages


def _chunk_text(
    page_num: int,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    """
    Split *text* into overlapping character-level chunks.
    Each chunk dict carries the page number so /chat/ask can cite it.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"page": page_num, "text": chunk_text})
        if end >= len(text):
            break
        start += chunk_size - chunk_overlap
    return chunks


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def ingest_document(document_id: int, app) -> None:
    """
    Run in a background thread.  Push *app*'s context so SQLAlchemy
    sessions work correctly outside the request thread.
    """
    with app.app_context():
        from app.extensions import db
        from app.models import Document

        doc = db.session.get(Document, document_id)
        if doc is None:
            return

        # --- Mark as processing ---
        doc.status = Document.STATUS_PROCESSING
        doc.ingestion_started_at = datetime.utcnow()
        db.session.commit()

        try:
            cfg = app.config
            model = _get_model(cfg["EMBEDDING_MODEL_NAME"])
            chunk_size = cfg["CHUNK_SIZE"]
            chunk_overlap = cfg["CHUNK_OVERLAP"]
            vector_store_dir = cfg["VECTOR_STORE_DIR"]

            # 1. Extract text
            pages = _extract_text_by_page(doc.stored_path)
            if not pages:
                raise ValueError("PDF appears to be empty or image-only (no extractable text).")

            # 2. Chunk
            all_chunks: list[dict] = []
            for page_num, page_text in pages:
                all_chunks.extend(_chunk_text(page_num, page_text, chunk_size, chunk_overlap))

            if not all_chunks:
                raise ValueError("No text chunks produced from PDF.")

            # 3. Embed with "passage:" E5 prefix
            passages = ["passage: " + c["text"] for c in all_chunks]
            embeddings: np.ndarray = model.encode(
                passages,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            ).astype("float32")

            # 4. Attach document metadata to each chunk
            chunk_meta = [
                {
                    "doc_id": doc.id,
                    "filename": doc.filename,
                    "category": doc.category,
                    "page": c["page"],
                    "text": c["text"],
                }
                for c in all_chunks
            ]

            # 5. Merge into existing FAISS index + save + reload
            existing_index, existing_meta = vector_store.get_index()
            new_index, new_meta = vector_store.add_chunks_to_index(
                existing_index, existing_meta, embeddings, chunk_meta
            )
            vector_store.save_index(vector_store_dir, new_index, new_meta)
            vector_store.reload_index(vector_store_dir)

            # 6. Update DB record
            doc.status = Document.STATUS_DONE
            doc.page_count = len(pages)
            doc.chunk_count = len(all_chunks)
            doc.ingested_at = datetime.utcnow()
            db.session.commit()

        except Exception as exc:  # noqa: BLE001
            doc.status = Document.STATUS_FAILED
            doc.error_message = str(exc)[:1000]
            db.session.commit()
