# SOPilot

A grounded operational knowledge assistant. Admins upload an organization's
SOPs (refund policy, onboarding, incident response, purchase approval,
etc.); employees ask plain-English questions and get back the exact
procedure, cited to the source SOP and page — never a hallucinated answer.

Built for the SMIT Generative AI capstone assignment (Flask + FAISS +
multilingual-e5 + Gemini 2.5 Flash), extended with two differentiators:

- **Category-tagged SOPs** (HR / Finance / IT-Security / Operations /
  Compliance) so the library and chat both filter by department.
- **Escalations** — every question SOPilot can't ground in a real
  procedure becomes a tracked "gap" for the admin, turning refusals into
  a signal about what still needs to be documented.

## Project status

This repo is being built in phases. Current state: **Phase 1 — auth &
app skeleton.**

- [x] Phase 1 — Flask app factory, models, auth (signup/login/logout),
      role-protected routing, seed-admin CLI, base UI shell
- [ ] Phase 2 — RAG pipeline ported into `app/rag/` (ingest + query + FAISS store)
- [ ] Phase 3 — Admin: PDF upload, background ingestion, status polling, SOP library
- [ ] Phase 4 — Chat: grounded Q&A, cited sources, refusal handling
- [ ] Phase 5 — Traffic dashboard (counts, latency, top questions, per-day chart)
- [ ] Phase 6 — Escalations: auto-create on refusal, gap-analytics chart
- [ ] Phase 7 — Seed sample SOPs, polish, demo video

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt    # Phase 1 only needs the "Core web app" deps;
                                    # the RAG deps install now too but aren't used until Phase 2.

cp .env.example .env
# Edit .env: set SECRET_KEY to a real random string.
# GOOGLE_API_KEY isn't needed until Phase 2/4.

export FLASK_APP=run.py            # Windows (PowerShell): $env:FLASK_APP="run.py"
```

## Seed the first admin account

Credentials are never hardcoded in the repo — this command prompts for
them interactively:

```bash
flask create-admin --email owner@company.com
```

Regular employees create their own account at `/auth/signup`, which
always creates a `user`-role account. Admin access is only ever granted
via the CLI command above (or by promoting an existing account by
re-running the command with that email).

## Run it

```bash
python run.py
```

Visit `http://localhost:5000`. Log in as the admin you just seeded to
reach `/admin/dashboard`, `/admin/documents`, `/admin/escalations`. Log
in as a regular signed-up user to land on `/chat` — and confirm that
account gets a 403 if it tries to visit `/admin/*` directly.

## Architecture notes

**Background ingestion (§5.2):** not yet implemented (Phase 3). Planned
approach: `threading.Thread` kicked off from the upload route, with the
`Document.status` field polled by the admin UI via `fetch` — per the
assignment's simplest option, since a single-admin classroom deployment
doesn't need Celery/rq. This will be documented in full once built.

**FAISS concurrency (§5.3):** not yet implemented (Phase 2/3). Planned
approach: reload a fresh index snapshot from disk after each ingestion
completes, rather than mutating a live index with a lock — so chat reads
never block on an ingestion write. Final decision and reasoning will be
written up here once built.

## Project structure

```
sopilot/
├── app/
│   ├── __init__.py          # app factory
│   ├── extensions.py        # db, login_manager (avoids circular imports)
│   ├── decorators.py        # @admin_required / @user_required
│   ├── models.py            # User, Document, QueryLog, Escalation
│   ├── auth/routes.py       # signup, login, logout
│   ├── admin/routes.py      # dashboard, SOP library, escalations
│   ├── chat/routes.py       # chat UI, /chat/ask
│   ├── rag/                 # ingest.py, query.py, store.py (Phase 2)
│   ├── templates/
│   └── static/css/style.css
├── uploads/                 # uploaded PDFs (gitignored)
├── vector_store/            # faiss.index + metadata.json (gitignored)
├── instance/                # app.db (gitignored)
├── config.py
├── requirements.txt
└── run.py
```
