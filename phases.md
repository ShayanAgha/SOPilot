1. Positioning (what makes it stand out, not just another PDF chatbot)

Elevator pitch for your README/portfolio:

SOPilot is a grounded operational knowledge assistant — it lets any employee ask a plain-English question and get back the exact procedure, cited to the source SOP and page, with zero hallucination risk. Admins upload and manage the procedure library; a live dashboard shows what people are actually asking, which surfaces process gaps and training needs.

Three things that separate SOPilot from a generic RAG demo:

Category-tagged SOPs — HR, Finance, IT/Security, Operations, Compliance. Real companies organize procedures this way; it also gives you a natural filter feature.
"Escalation" on refusal — when SOPilot can't find an answer, instead of just refusing, it creates a lightweight "Needs a documented procedure" ticket the admin sees. This turns your grounding refusal (already required by the rubric) into a feature that improves the knowledge base over time.
Gap analytics — dashboard doesn't just show query volume, it surfaces top refused/low-confidence questions grouped by category = "these are the procedures your company hasn't documented well." That's a genuinely useful business insight, not just a vanity metric.
2. Schema (extends the assignment's minimum, stays lightweight)

Build on the required User / Document / QueryLog tables, with small additions:

Document — add category (enum: HR / Finance / IT-Security / Operations / Compliance / Other), version (int, for re-ingestion history), owner_department (free text)

QueryLog — add category_matched (nullable — which SOP category the top result came from), escalated (bool — true if it was a refusal that got flagged)

New table: Escalation — id, query_log_id (FK), status (open/resolved), resolved_note, created_at, resolved_at
→ This is what makes the "gap analytics" story work in your demo.

3. Routes (on top of the assignment's suggested list)
Method	Route	Role	Purpose
GET	/admin/documents?category=	admin	filter SOP library by category
GET	/admin/escalations	admin	view open "undocumented procedure" tickets
POST	/admin/escalations/<id>/resolve	admin	mark resolved, optionally link a new SOP
GET	/admin/dashboard/gaps	admin	top low-confidence questions grouped by category (JSON, feeds a chart)
GET	/chat?category=	user	optional pre-filter chat by SOP category (e.g. "IT only")

Everything else (auth, upload, ingest, status, logs, chat/ask) stays exactly as in the assignment spec — no need to reinvent that part.

4. UI ideas (what makes the demo look professional, not just functional)
Admin dashboard: top row of stat cards (Total Queries, Today, Avg Latency, % Grounded) → time-series chart of queries/day → new: a bar chart of escalations by category (this is your signature visual, nothing else in the class demo will have it).
Chat UI: category pill filters above the input ("All / HR / Finance / IT-Security / Operations"), each answer rendered as a numbered procedure list with a small "Source: X SOP — Page Y" chip, not just plain text — visually distinguishes grounded answers from generic chatbot replies.
Color/tone: go corporate-neutral (navy/slate + one accent color) rather than a flashy AI-startup gradient — reinforces the "enterprise tool" positioning over "cool AI toy."
5. Phased build plan

Phase 1 — Core skeleton (Day 1)
Flask app factory, models, auth (signup/login/role), seed-admin CLI, base templates/nav.

Phase 2 — RAG port (Day 1–2)
Move your existing ingest.py/query.py into app/rag/, wrap FAISS access with the lock (or reload-after-ingest — pick reload, it's simpler and defensible in the README), test via CLI before wiring routes.

Phase 3 — Admin panel (Day 2–3)
Upload → background thread ingestion → status polling → document list w/ category filter.

Phase 4 — Chat panel (Day 3)
Chat UI, /chat/ask, grounded refusal message, sources rendering, category filter.

Phase 5 — Logging + dashboard (Day 4)
Log every query before responding (per the assignment's hint), stats aggregation queries, charts.

Phase 6 — SOPilot differentiators (Day 4–5)
Escalation table + auto-create on refusal, admin escalation view, gap-analytics chart.

Phase 7 — Polish (Day 5)
README, seed 3–4 realistic SOPs (refund policy, onboarding, incident response, purchase approval) so your demo video has real substance, record demo.

6. README outline (for presentation)
One-paragraph pitch (use the framing above)
Screenshot: admin dashboard with gap chart
Screenshot: chat with a cited answer
Setup instructions (venv, .env, GOOGLE_API_KEY, SECRET_KEY, seed-admin)
Architecture note: background ingestion approach + FAISS concurrency approach (required by rubric §5.2/5.3)
"Why SOPilot" — the escalation/gap-analytics differentiator, 3–4 sentences
Link to demo video