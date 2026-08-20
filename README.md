# SOPilot

**SOPilot** is a grounded operational knowledge assistant — it lets any employee ask a plain-English question and get back the exact procedure, cited to the source SOP and page, with zero hallucination risk. Admins upload and manage the procedure library; a live dashboard shows what people are actually asking, which surfaces process gaps and training needs.

---

## Why SOPilot?

Three things that separate SOPilot from a generic RAG demo:

1. **Category-tagged SOPs** — HR, Finance, IT/Security, Operations, Compliance. Real companies organize procedures this way; it also gives you a natural filter on the chat UI.
2. **Escalation on refusal** — when SOPilot can't find an answer, instead of just refusing, it creates a lightweight *"Needs a documented procedure"* ticket the admin sees. This turns grounding refusals into a feature that improves the knowledge base over time.
3. **Gap analytics** — the dashboard surfaces top refused/low-confidence questions grouped by category = *"these are the procedures your company hasn't documented well."* That's a genuinely useful business insight, not just a vanity metric.

---

## Screenshots

| Admin Dashboard | SOP Library | Chat UI |
|---|---|---|
| Stat cards, query-per-day chart, escalations by category | Upload form, category filter, live ingestion status | Category pills, numbered procedure answers, source chips |

---

## Architecture

```
Browser
  │
  ├─ GET/POST /auth/*        ← signup, login, logout
  ├─ GET/POST /admin/*       ← dashboard, SOP library, escalations
  │     └─ POST /upload → threading.Thread → ingest_document()
  │                                              ├─ extract PDF pages
  │                                              ├─ chunk text
  │                                              ├─ embed (multilingual-e5-base)
  │                                              └─ FAISS index → disk → reload
  └─ POST /chat/ask          ← embed question → FAISS search → Gemini 2.5 Flash
        ├─ writes QueryLog row BEFORE responding
        └─ if not grounded → auto-creates Escalation row
```

### FAISS Concurrency (§5.3)

Background ingestion uses a **reload-after-ingest** strategy:

- After each ingestion completes, `store.reload_index()` atomically replaces the module-level index reference with a fresh snapshot loaded from disk.
- Chat reads always call `store.get_index()` which returns the current snapshot — they never block on a write lock mid-search.
- A `threading.Lock` serialises concurrent reloads (two uploads completing simultaneously), not reads.

This is simpler and more defensible than a reader-writer lock: readers always see a consistent, immutable snapshot.

---

## Setup

### Prerequisites

- Python 3.10+
- A Google AI API key ([get one here](https://aistudio.google.com/app/apikey))

### Installation

```bash
git clone https://github.com/ShayanAgha/SOPilot.git
cd SOPilot
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required:
```ini
SECRET_KEY=<random-secret-key>
GOOGLE_API_KEY=<your-gemini-api-key>
```

Optional (defaults shown):
```ini
FLASK_ENV=development
GEMINI_MODEL_NAME=gemini-2.5-flash
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-base
TOP_K=10
SIMILARITY_THRESHOLD=0.72
CHUNK_SIZE=800
CHUNK_OVERLAP=120
```

### Run

```bash
python run.py
```

App starts at **http://127.0.0.1:5000**.

### Seed an Admin Account

```bash
flask create-admin --email admin@company.com
# (prompts for password)
```

### Seed Demo SOPs (optional)

Generate and upload 4 realistic SOP PDFs (Customer Refund, Employee Onboarding, Incident Response, Purchase Approval):

```bash
ADMIN_EMAIL=admin@company.com ADMIN_PASSWORD=yourpassword python seed_sops.py
```

---

## Project Structure

```
sopilot/
├── app/
│   ├── __init__.py          # app factory + CLI commands
│   ├── extensions.py        # db, login_manager
│   ├── decorators.py        # @admin_required / @user_required
│   ├── models.py            # User, Document, QueryLog, Escalation
│   ├── auth/routes.py       # signup, login, logout
│   ├── admin/routes.py      # dashboard, SOP library, escalations, gaps JSON
│   ├── chat/routes.py       # chat UI, /chat/ask (full RAG pipeline)
│   ├── rag/
│   │   ├── store.py         # FAISS thread-safe store (reload-after-ingest)
│   │   ├── ingest.py        # PDF → chunks → embeddings → FAISS
│   │   └── query.py         # question → FAISS → threshold → Gemini
│   ├── templates/
│   └── static/css/style.css # design system (IBM Plex, navy/slate)
├── uploads/                 # uploaded PDFs (gitignored)
├── vector_store/            # faiss.index + metadata.json (gitignored)
├── instance/                # app.db (gitignored)
├── seed_sops.py             # generates 4 demo SOP PDFs and uploads them
├── config.py
├── requirements.txt
└── run.py
```

---

## Data Model

| Table | Key fields |
|---|---|
| `users` | email, password_hash, role (admin/user) |
| `documents` | filename, category, status, page_count, chunk_count, version |
| `query_logs` | question, answer, was_grounded, top_score, category_matched, latency_ms |
| `escalations` | query_log_id (FK), status (open/resolved), resolved_note |

---

## Key Design Decisions

- **Grounding refusal as a feature**: SOPilot never guesses. When `top_score < SIMILARITY_THRESHOLD`, it returns a fixed refusal message and creates an Escalation ticket. Admins see a live list of undocumented procedures.
- **Background ingestion**: `threading.Thread` so PDF upload never blocks the request. The status endpoint (`/admin/documents/<id>/status`) is polled by the UI every 2.5 seconds.
- **QueryLog written before response**: Following the assignment hint — the record exists even if Gemini times out or the client disconnects.
- **Strict system prompt**: Gemini is instructed to answer *only* from provided excerpts, never from parametric knowledge. Sources are always listed at the end of grounded answers.

---

## License

MIT
