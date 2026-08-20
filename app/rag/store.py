"""
FAISS index load/save helpers + thread-safety wrapper (§5.3).

Decision (documented here and in README.md once made): ingestion
writes and chat reads can happen concurrently in a multi-user app.
Plan is to reload a fresh, immutable index snapshot after each
ingestion completes rather than mutating a live index in place --
readers always get a consistent index and never block on a write lock
mid-search. Final approach gets written up in Phase 2/3.
"""
