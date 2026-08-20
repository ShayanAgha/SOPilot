"""
FAISS index load/save helpers + thread-safety wrapper (§5.3).

Thread-safety strategy: reload-after-ingest.
  - After each ingestion completes, the background thread writes a fresh
    index to disk and calls `reload_index()` which atomically replaces the
    module-level reference.
  - Chat reads always call `get_index()` which returns the current snapshot.
  - No reader ever blocks on a write lock mid-search; they simply see the
    previous snapshot until the reload is done.
  - A threading.Lock serializes concurrent *reloads* (two uploads finishing
    at the same moment) but not reads.
"""
import json
import os
import threading
from typing import Optional

import faiss
import numpy as np

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_index: Optional[faiss.Index] = None       # FAISS flat index
_metadata: list[dict] = []                  # parallel list of chunk dicts
_reload_lock = threading.Lock()             # serialises concurrent reloads

INDEX_FILE = "faiss.index"
META_FILE = "metadata.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_index():
    """Return the current (index, metadata) pair.  May be (None, []) if no
    documents have been ingested yet."""
    return _index, _metadata


def reload_index(vector_store_dir: str) -> None:
    """
    Load the index and metadata from *vector_store_dir* and atomically
    replace the module-level references.  Called by ingest.py after a
    successful ingestion write.
    """
    global _index, _metadata

    index_path = os.path.join(vector_store_dir, INDEX_FILE)
    meta_path = os.path.join(vector_store_dir, META_FILE)

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        return  # nothing on disk yet

    with _reload_lock:
        new_index = faiss.read_index(index_path)
        with open(meta_path, "r", encoding="utf-8") as fh:
            new_meta = json.load(fh)
        _index = new_index
        _metadata = new_meta


def save_index(vector_store_dir: str, index: faiss.Index, metadata: list[dict]) -> None:
    """
    Persist index + metadata to disk.  Called by ingest.py once the new
    vectors are ready.  After saving, call `reload_index()` to swap in the
    new snapshot for readers.
    """
    os.makedirs(vector_store_dir, exist_ok=True)
    index_path = os.path.join(vector_store_dir, INDEX_FILE)
    meta_path = os.path.join(vector_store_dir, META_FILE)

    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False)


def add_chunks_to_index(
    existing_index: Optional[faiss.Index],
    existing_meta: list[dict],
    embeddings: np.ndarray,
    chunk_meta: list[dict],
) -> tuple[faiss.Index, list[dict]]:
    """
    Merge new embeddings into (a copy of) the existing index and return
    the updated (index, metadata) pair.  The caller is responsible for
    calling save_index() + reload_index() afterwards.
    """
    dim = embeddings.shape[1]

    if existing_index is None or existing_index.ntotal == 0:
        index = faiss.IndexFlatIP(dim)   # inner-product (cosine after L2-norm)
    else:
        # Reconstruct a new flat index from the existing vectors so we never
        # mutate the live snapshot.
        index = faiss.IndexFlatIP(dim)
        stored = faiss.rev_swig_ptr(existing_index.get_xb(), existing_index.ntotal * dim)
        stored = stored.reshape(existing_index.ntotal, dim).copy()
        index.add(stored)

    # L2-normalise so inner-product == cosine similarity
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    new_meta = existing_meta + chunk_meta
    return index, new_meta
