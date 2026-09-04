# AI Mentor for CMA / CPA / CFA / ACCA / CS / EA

A production-oriented starter project for an AI mentor that teaches students using your own institute content, notes, PDFs, recordings transcripts, FAQs, placement guidance, and course material.

## Documentation map

- [Current architecture and SaaS hardening](docs/ARCHITECTURE_AND_SAAS_HARDENING.md) — runtime topology, data flows, Ziplin state, target design, and migration gates
- [Project structure](docs/PROJECT_STRUCTURE.md) — ownership and persistence boundaries
- [Admin operations](docs/ADMIN_OPERATIONS.md) — every dashboard page and workflow
- [Testing and release checks](docs/TESTING.md) — coverage and deployment gate
- [Backend](backend/README.md), [dashboard](admin-dashboard/README.md), [scripts](scripts/README.md), and [tests](tests/README.md) folder notes

This README and `docs/` are authoritative. Superseded one-off WhatsApp guides
and manual utilities are isolated under `docs/archive/legacy-whatsapp/` and
`scripts/archive/legacy-whatsapp/`; they are reference material, not supported
production instructions.

This project is designed for fast responses:
- FastAPI async backend
- Server-Sent Events streaming
- Qdrant vector database
- Persistent `.txt` question-and-answer library plus Redis repetition state
- NVIDIA Nemotron mentor answers with automatic Gemini fallback
- Local hash embeddings by default, with optional OpenAI semantic embeddings
- Short prompt context with top-k retrieval
- Separate admin control center for editable content, RAG indexing, feedback, enrollments, and safe runtime settings
- WhatsApp-only change/error feedback with optional JPG/PNG screenshots

> Replace the sample NorthStar-style content with your actual licensed study notes, recorded class transcripts, question banks, policy docs, placement guides, and FAQs.

---

## What this AI mentor can do

1. Teach concepts in CMA / CPA / CFA / ACCA / CS / EA
2. Classify each question against the student's active course
3. Ask Socratic follow-up questions
4. Generate practice questions and quizzes
5. Explain weak areas
6. Give study plans
7. Help with job-hunt preparation, resume pointers, interview Q&A, and role mapping
8. Capture leads or escalate to a human counselor where needed

---

## Architecture

```
Student Web Chat / WhatsApp
      |
      v
FastAPI API
      |
      +-- Redis per-student repetition and clarification state

      +-- data/question_answers.txt reusable answer library
      |
      +-- Hash/OpenAI embedding for student query
      |
      +-- Qdrant vector search over institute content
      |
      +-- SQLite admin catalog, training jobs, feedback, and audit events
      |
      +-- NVIDIA NIM Nemotron (primary) / Gemini (fallback)
      |
      v
SSE tokens to browser or WhatsApp reply via Meta Graph API
```

---

## Folder structure

```
ai-mentor-rag-northstar/
  backend/
    app/
      main.py
      config.py
      schemas.py
      auth.py
      admin_api.py
      admin_store.py
      cache.py
      chunking.py
      documents.py
      embeddings.py
      vector_store.py
      nvidia.py
      question_history.py
      training.py
      webhook_queue.py
      whatsapp.py
      mentor.py
      prompts.py
  frontend/
    index.html
  admin-dashboard/
    index.html
    assets/
      app.js
      styles.css
  scripts/
    ingest_directory.py
    migrate_legacy_knowledge.py
    seed_sample_docs.py
  data/
    sample_docs/
      northstar_cma_sample.md
      cma_demo_lesson.md
      job_hunt_guide.md
  docker-compose.yml
  Dockerfile
  requirements.txt
  .env.example
```

---

## 1. Setup

```bash
cp .env.example .env
# Add provider credentials and generate a long random ADMIN_TOKEN in .env

docker compose up --build
```

On Windows, `start.bat` does all of this in one step: it checks Docker, starts the
stack, re-registers the WhatsApp webhook against the current tunnel URL, and then
streams the container logs. Stop it by closing the window or pressing Ctrl+C —
either way the containers are shut down. Use `stop.bat` if a stack is ever left
running after a crash.

Open the chat UI:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

Admin control center:

```text
http://localhost:8000/admin/
```

The admin token is retained only in the current browser tab. Provider keys,
WhatsApp tokens, database URLs, and other deployment secrets are never returned
to the dashboard and remain environment-managed.

---

## 2. Manage and train the knowledge base

Open `/admin/`, upload TXT/Markdown/PDF/DOCX source files, edit their extracted
text and metadata, select the documents, and choose **Start RAG indexing**.
“Training” in this application means chunking, embedding, and publishing content
to the retrieval index; it does not fine-tune the NVIDIA, Gemini, or Anthropic
foundation model. Published revisions remain available if a replacement upload
fails, and edits use document versions to prevent accidental overwrites.

Retrieval is constrained to the revision currently published in the SQLite
catalog. If upgrading a deployment that already contains vectors created by the
older ingestion scripts, inventory and adopt them before going live:

```bash
docker compose exec api python scripts/knowledge/migrate_legacy_knowledge.py
docker compose exec api python scripts/knowledge/migrate_legacy_knowledge.py --apply
```

The first command is read-only. The second reconstructs editable source records
and publishes new versioned vectors; legacy points remain invisible and may be
removed later during a Qdrant maintenance window.

`COURSE_RETRIEVAL_ENABLED=true` must remain enabled for indexed material to be
used in mentor answers. The dashboard blocks indexing and shows a warning if it
is disabled.

### Seed or import from the command line

After Docker is running:

```bash
docker compose exec api python scripts/knowledge/seed_sample_docs.py
```

Or ingest your own docs from a directory:

```bash
docker compose exec api python scripts/knowledge/ingest_directory.py /app/data/my_docs CMA
```

Supported files:
- `.txt`
- `.md`
- `.pdf`
- `.docx`

---

## 3. Add documents through the compatibility API

```bash
curl -X POST "http://localhost:8000/v1/admin/ingest/files" \
  -H "x-admin-token: $ADMIN_TOKEN" \
  -F "course=CMA" \
  -F "doc_type=lesson" \
  -F "files=@your-notes.pdf"
```

---

## 4. Chat streaming API

```bash
curl -N -X POST "http://localhost:8000/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "student_123",
    "course": "CMA",
    "message": "Explain variance analysis like a mentor and give me 2 practice questions"
  }'
```

---

## 5. WhatsApp bot API

The bot uses the official Meta WhatsApp Cloud API webhook flow.

Ziplin uses direct Meta delivery; no third-party inbox or webhook relay is part
of the production path. Publish NorthStar on a permanent HTTPS hostname and set:

```dotenv
NORTHSTAR_PUBLIC_BASE_URL=https://mentor.example.com
WHATSAPP_WEBHOOK_CALLBACK_URL=https://mentor.example.com/v1/whatsapp/ziplin/webhook
WHATSAPP_APP_SECRET=<Meta App Secret stored only in the deployment secret store>
```

`start.bat` validates the callback, registers it on the Ziplin Meta app, checks
the active subscription, and separately checks the system-user token used for
outbound replies. A temporary Cloudflare quick tunnel is for non-production
testing only; its hostname changes after a restart.

Every signed batch is checked against `WHATSAPP_BUSINESS_ACCOUNT_ID` and
`WHATSAPP_PHONE_NUMBER_ID` before any part enters the durable queue; the phone
ID is checked again before message processing. A payload addressed to another
WABA or number is acknowledged as `ignored` and can never produce an outbound
reply. Outbound messages are always sent through the configured Phone Number ID.
Register the dedicated callback only on the Ziplin Meta app.

The dashboard includes a read-only Conversations inbox plus a WhatsApp
operations panel. It shows
non-sensitive webhook, phone, account, enrollment-source, and durable-queue
status. Its master switch changes `whatsapp_messaging_enabled` immediately.
When paused, webhook verification remains available, student messages are
acknowledged without being queued, delivery/read receipts keep the inbox
current, public feedback links are disabled, and all outbound WhatsApp sends
are blocked. Access tokens and application secrets are never returned to the
browser.

Conversation flow:

```text
Any WhatsApp user: sends Hi, a CMA question, or a clear CMA-question image
Bot: opens CMA and selects Teach automatically
Bot: shows the WhatsApp learning-mode menu with:
     1. Teach
     2. Doubt Solving
     3. Quiz
     4. Revision
     5. Job Hunt
Student: can ask immediately, or choose another learning mode first
Bot: verifies that the question belongs to CMA, then sends a descriptive answer
```

With `WHATSAPP_OPEN_CMA_ACCESS=true`, CMA is available to every inbound number and is not written to the enrollment workbook. Sending `Hi` resets that conversation to `CMA | Teach`; a first-message text question or image is also handled as CMA Teach. Existing enrollment records can still grant additional courses. Set the flag to `false` to restore enrollment-only access.

The mentor is not limited to uploaded knowledge. NorthStar Academy material can improve an answer, but any valid question within the active CMA, CPA, CFA, ACCA, CS, or EA course can be answered using the model's course knowledge. Questions outside the active course are refused. Student-facing replies never include citations or source lists.

### WhatsApp-only feedback and screenshots

The web application’s feedback button opens the configured WhatsApp business
number with an explicit `FEEDBACK` marker. A student can either send a written
change/error report or attach a JPG/PNG screenshot and put the description in
its caption. Feedback is routed before the course-question flow, stored in the
admin database, and appears in `/admin/` for review. The raw message and image
remain immutable; admins edit only category, review status, and internal notes.

Configure the public display number separately from Meta’s phone-number ID:

```bash
WHATSAPP_FEEDBACK_NUMBER=919999999999
WHATSAPP_FEEDBACK_PREFILL="FEEDBACK\nPlease describe the change or error. You can also attach a screenshot."
WHATSAPP_MAX_MEDIA_BYTES=5242880
```

The button is enabled only when the feedback number, Cloud API token,
phone-number ID, permanent direct callback, verification token, and Meta App
Secret are configured. Browsers cannot pre-attach a local screenshot to a
`wa.me` link; the student attaches it inside WhatsApp before sending.

Feedback is accepted before tutoring enrollment checks so a visitor can report a
broken experience, but per-number daily quotas and a global screenshot-storage
cap are enforced. Raw reports are retained for `FEEDBACK_RETENTION_DAYS` (365 by
default), after which the database record and screenshot are purged.

Signed Meta webhook payloads are durably queued in SQLite before the API returns
success. A leased, heartbeat-driven worker retries transient failures, preserves
feedback-message order, and dead-letters events after the configured attempt cap.

### Manage WhatsApp access from the live Excel workbook

Open CMA access is independent of the workbook: while `WHATSAPP_OPEN_CMA_ACCESS=true`, removing or revoking a CMA row does not block CMA because CMA is intentionally public. The workbook controls additional courses and becomes the complete access authority again when open CMA access is disabled.

By default, the dashboard writes enrollment changes to
`data/whatsapp_enrollments.xlsx` on the host. Docker Compose mounts that same
file location as `/app/data/whatsapp_enrollments.xlsx`, which is the value of
`WHATSAPP_ENROLLMENTS_FILE` inside the API container. **Save enrollment** writes
`YES`; revoking a course writes `NO`. The API completes only after the workbook
has been saved atomically and reopened successfully, so the next dashboard or
WhatsApp lookup sees the change immediately.

Use the `Enrollments` tab with these required columns:

| phone_number | course | active | student_name | notes |
| --- | --- | --- | --- | --- |
| 9876543210 | CMA | YES | Student name | Optional note |

- `course` must be `CMA`, `CPA`, `CFA`, `ACCA`, `CS`, or `EA`.
- For a new valid phone number, a blank `course` defaults to `CMA` and a blank
  `active` value defaults to `YES`, so adding the number alone grants CMA access.
- Repeat a phone number on separate rows to grant multiple courses.
- `active=YES` grants access; `active=NO` revokes it.
- Existing `student_name`, `notes`, formatting, and unrelated rows are preserved.
- Direct edits made to the workbook are picked up automatically; press
  **Refresh** in the dashboard to update the visible card.

Excel Desktop does not automatically redraw an already-open workbook after
another process replaces it on disk. Close and reopen the workbook, or use
Excel's refresh/reload option, to see a dashboard change. If Excel locks the
file, the dashboard shows a conflict instead of claiming that the enrollment
was saved; close the workbook and retry.

To use the private Google Sheet integration instead, configure a Sheet ID. When
enabled, Google Sheets becomes the sole access authority and the dashboard can
view, grant, revoke, and bulk-import enrollment state. A missing, inactive, or invalid row is
denied and cannot fall back to Excel, Redis, or `.env`. The bot refreshes the
private Sheet every 60 seconds and uses the last valid copy during a temporary
Google outage.

For a private Sheet, create a Google Cloud service account with Sheets API access, share the Sheet with its service-account email as **Editor**, and save its JSON key as `secrets/google-service-account.json`. Then configure:

```bash
WHATSAPP_ENROLLMENTS_GOOGLE_SHEET_ID=your-spreadsheet-id
WHATSAPP_ENROLLMENTS_GOOGLE_SHEET_RANGE=Enrollments!A:E
WHATSAPP_ENROLLMENTS_GOOGLE_REFRESH_SECONDS=60
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/google-service-account.json
```

The `secrets` directory is mounted read-only and ignored by Git. Do not publish the Sheet to the web because it contains student phone numbers.

Webhook callback URL:

```text
https://your-public-domain.com/v1/whatsapp/ziplin/webhook
```

Localhost will not receive Meta webhooks directly. The `public-tunnel` service is
opt-in through the Compose `tunnel` profile (`docker compose --profile tunnel up`).
It runs a cloudflared quick tunnel, but Cloudflare
assigns it a **new random hostname on every start**, so the callback URL Meta has
on file goes dead after each restart.

`start.bat` handles that by running `scripts/windows/register_webhook.ps1` on every
launch: it reads the tunnel URL out of the `public-tunnel` logs, waits until the
API answers `/ready` through it, then re-registers it on the app subscription
with `object=whatsapp_business_account` and the required `messages` field. Run
it by hand any time with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_webhook.ps1
```

Because this repoints a live business number's webhook at your machine, incoming
customer messages only reach the bot while the stack is running. For a URL that
does not change, use a Cloudflare named tunnel or a public HTTPS deployment.

Set these values in `.env`:

```bash
WHATSAPP_VERIFY_TOKEN=choose-a-secret-token
WHATSAPP_ACCESS_TOKEN=your-meta-whatsapp-access-token
WHATSAPP_TOKEN=your-meta-whatsapp-access-token
WHATSAPP_PHONE_NUMBER_ID=your-meta-phone-number-id
WHATSAPP_APP_SECRET=your-meta-app-secret
META_APP_SECRET=your-meta-app-secret
META_APP_ID=your-meta-app-id
FACEBOOK_APP_ID=your-meta-app-id
WHATSAPP_GRAPH_API_VERSION=v25.0
WHATSAPP_GRAPH_BASE=https://graph.facebook.com/v25.0
WHATSAPP_BUSINESS_ACCOUNT_ID=your-whatsapp-business-account-id
WHATSAPP_OPEN_CMA_ACCESS=true
WHATSAPP_DEFAULT_COURSE=CMA
WHATSAPP_DEFAULT_MODE=teach
WHATSAPP_DEFAULT_LEVEL=beginner
WHATSAPP_MAX_MEDIA_BYTES=5242880
WHATSAPP_FEEDBACK_NUMBER=919999999999
WHATSAPP_START_TEMPLATE_NAME=hello_world
WHATSAPP_START_TEMPLATE_LANGUAGE=en_US
WHATSAPP_USE_MOCK=false
WHATSAPP_TEST_TO=
WHATSAPP_ENROLLMENTS=919999999999:CMA
```

`WHATSAPP_TOKEN` and `META_APP_SECRET` remain backward-compatible aliases.
Prefer `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_APP_SECRET` for new deployments.

Assign or change one student's enrolled course through the protected backend API:

```bash
curl -X PUT "http://localhost:8000/v1/admin/whatsapp/enrollments/919999999999" \
  -H "x-admin-token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"course":"CMA"}'
```

In Meta Developer Console:
- Add the callback URL above.
- Use the same `WHATSAPP_VERIFY_TOKEN`.
- Subscribe the WhatsApp webhook to the `messages` field.
- Send a WhatsApp message to your business/test number.

Run the WhatsApp diagnostics after changing Meta tokens or IDs:

```bash
docker compose exec api python scripts/whatsapp/whatsapp_diagnostics.py
```

All checks should pass before the bot can send or reply through WhatsApp. If
the permission check passes but the configured-phone check fails, the token is
not authorized for that `WHATSAPP_PHONE_NUMBER_ID`.

Send the first business-initiated "Hi" message from the app side:

```bash
docker compose exec api python scripts/whatsapp/send_whatsapp_hi.py "$WHATSAPP_TEST_TO"
```

Or call the protected API:

```bash
curl -X POST "http://localhost:8000/v1/admin/whatsapp/send-hi" \
  -H "x-admin-token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"919999999999"}'
```

WhatsApp only allows the business to message first with an approved template. After the user replies, the 24-hour service window opens and the bot can send the CMA Teach menu and AI answers. The admin-initiated template/menu endpoints still require an enrollment record; open CMA access applies to users who initiate inbound conversations.

Send the enrolled-course mode menu from the app side:

```bash
docker compose exec api python scripts/whatsapp/send_whatsapp_program_menu.py "$WHATSAPP_TEST_TO"
```

Or call the protected API:

```bash
curl -X POST "http://localhost:8000/v1/admin/whatsapp/send-program-menu" \
  -H "x-admin-token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"919999999999"}'
```

Students can change the CMA learning mode anytime:

```text
menu
```

---

## 6. Important environment variables

See `.env.example`.

Key settings:
- `MENTOR_PROVIDER`
- `MENTOR_FALLBACK_PROVIDER`
- `MENTOR_POLICY_PROVIDER`
- `NVIDIA_API_KEY`
- `NVIDIA_MODEL`
- `NVIDIA_MAX_TOKENS`
- `NVIDIA_REASONING_BUDGET`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `EMBEDDING_PROVIDER`
- `OPENAI_API_KEY` when `EMBEDDING_PROVIDER=openai`
- `OPENAI_EMBEDDING_MODEL`
- `QDRANT_URL`
- `REDIS_URL`
- `QUESTION_ANSWER_FILE`
- `QUESTION_REPEAT_TTL_SECONDS`
- `COURSE_RETRIEVAL_ENABLED`
- `ADMIN_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_APP_SECRET`
- `META_APP_ID`
- `WHATSAPP_WEBHOOK_CALLBACK_URL`
- `NORTHSTAR_PUBLIC_BASE_URL`
- `WHATSAPP_OPEN_CMA_ACCESS`
- `MAX_CONTEXT_CHARS`
- `TOP_K`

---

## 7. How to make it genuinely useful for your institute

Upload these content sets:

### Course learning content
- CMA Part 1 and Part 2 notes
- CPA FAR/AUD/REG/BAR/TCP/ISC notes
- ACCA papers notes
- EA Part 1/2/3 notes
- recorded class transcripts
- revision notes
- topic-wise examples

### Practice and assessment
- MCQ question bank
- solved examples
- wrong-answer explanations
- mock exam explanations
- formulas and memorization aids

### Student operations
- batch schedules
- exam eligibility FAQs
- refund policy
- counseling FAQ
- placement process

### Job hunt material
- finance resume templates
- finance interview Q&A
- FP&A, audit, taxation, controllership JD mapping
- professional networking outreach scripts
- salary and role guidance docs

---

## 8. Production checklist

Before going live:
- Set `APP_ENVIRONMENT=production` and generate a long random `ADMIN_TOKEN`; the known example/empty value is rejected
- Put API behind HTTPS
- Put `/admin/` behind your identity-aware access gateway; add user login/RBAC when multiple administrators need individual accountability
- Do not use the quick-tunnel profile as a permanent public deployment
- Keep Redis and Qdrant on a private network (the development Compose ports bind only to localhost)
- The API container runs as UID/GID `1000`, with a read-only root filesystem and dropped Linux capabilities; ensure the host `data/` directory is writable by that UID on Linux
- Back up the stable `ai-mentor-rag-northstar_admin_storage` volume, `data/feedback-media`, the runtime config/prompt files, and Qdrant together; `docker compose down -v` deletes named-volume data
- Use PostgreSQL/object storage plus a durable worker queue before scaling the API beyond a single node
- Add content-level permissions by course
- Store chat history in Postgres
- Add moderation and PII redaction
- Add analytics: retrieval hit rate, unanswered questions, token cost
- Add evaluation set for each course
- Add human handoff for admissions, fees, legal, and refund questions
- Use Qdrant Cloud or managed Kubernetes deployment for scale
- Add Celery/RQ ingestion worker for large PDFs and transcripts
- Add a reranker if retrieval quality matters more than speed
- Use a permanent Meta access token, not a temporary setup token
- Keep `WHATSAPP_APP_SECRET` set in production so webhook signatures are verified
- Use approved WhatsApp templates for business-initiated messages outside the 24-hour customer-service window

---

## 9. Design choices for speed

- Stream answers immediately using SSE.
- Use a compact retrieval context rather than sending full documents to the model.
- Reuse an approved stage-one answer from `data/question_answers.txt` when another student asks the same normalized course question.
- Generate fresh, progressively deeper answers on the same student's second and third requests; ask for a precise clarification on the fourth.
- Keep repetition counters and pending clarification state in Redis without writing student identifiers to the answer file.
- Keep embeddings precomputed during ingestion.
- Use Qdrant payload filters for course-specific search.
- Use local hash embeddings to run without an embedding API; switch to `text-embedding-3-small` with `EMBEDDING_PROVIDER=openai` for stronger semantic retrieval.
- Keep top-k low by default; increase only after measuring retrieval misses.

---

## 10. Safety and academic integrity

The mentor should teach, explain, quiz, and coach. It should not:
- impersonate a human faculty member
- fabricate institute policy
- guarantee exam success or placement
- provide cheating assistance
- answer outside your knowledge base when the answer requires official policy

The default prompt already follows these rules, but you should adapt it to your institute policies.

---

## License

Starter code for your internal project use. Review and adapt before production.
