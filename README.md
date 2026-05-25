# AI Mentor RAG for CMA / CPA / ACCA / EA Training Institutes

A production-oriented starter project for an AI mentor that teaches students using your own institute content, notes, PDFs, recordings transcripts, FAQs, placement guidance, and course material.

This project is designed for fast responses:
- FastAPI async backend
- Server-Sent Events streaming
- Qdrant vector database
- Redis response cache
- Claude mentor answers through Anthropic Messages API
- Local hash embeddings by default, with optional OpenAI semantic embeddings
- Short prompt context with top-k retrieval
- Admin upload endpoint for adding course content

> Replace the sample NorthStar-style content with your actual licensed study notes, recorded class transcripts, question banks, policy docs, placement guides, and FAQs.

---

## What this AI mentor can do

1. Teach concepts in CMA / CPA / ACCA / EA
2. Answer from your uploaded content using RAG
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
      +-- Redis cache for repeated questions
      |
      +-- Hash/OpenAI embedding for student query
      |
      +-- Qdrant vector search over institute content
      |
      +-- Anthropic Claude Messages API
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
      cache.py
      chunking.py
      documents.py
      embeddings.py
      vector_store.py
      whatsapp.py
      mentor.py
      prompts.py
  frontend/
    index.html
  scripts/
    ingest_directory.py
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
# Add your ANTHROPIC_API_KEY in .env

docker compose up --build
```

Open the chat UI:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

---

## 2. Seed sample knowledge base

After Docker is running:

```bash
docker compose exec api python scripts/seed_sample_docs.py
```

Or ingest your own docs from a directory:

```bash
docker compose exec api python scripts/ingest_directory.py /app/data/my_docs
```

Supported files:
- `.txt`
- `.md`
- `.pdf`
- `.docx`

---

## 3. Add documents through API

```bash
curl -X POST "http://localhost:8000/v1/admin/ingest/files" \
  -H "x-admin-token: change-me" \
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

Conversation flow:

```text
Institute: sends an approved WhatsApp template invite, for example a "Hi" template
Student: replies to that template, or sends hi directly
Bot: shows a WhatsApp program menu with:
     1. CMA
     2. CPA
     3. ACCA
     4. EA
Student: chooses one program
Bot: shows a WhatsApp learning-mode menu with:
     1. Teach
     2. Doubt Solving
     3. Quiz
     4. Revision
     5. Job Hunt
Student: chooses one learning mode
Bot: confirms the selected program + mode and asks for the question
Student: asks the question
Bot: replies with a phone-screen-friendly structured answer from Claude + RAG
```

The bot intentionally limits AI answers to the configured program plus one of these five modes. If a student has not chosen both a program and a mode, the bot asks them to choose from the correct menu first.

Webhook callback URL:

```text
https://your-public-domain.com/v1/whatsapp/webhook
```

Localhost will not receive Meta webhooks directly. Use a public HTTPS deployment or a tunnel such as ngrok for local testing.

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
WHATSAPP_DEFAULT_COURSE=GENERAL
WHATSAPP_DEFAULT_MODE=doubt_solving
WHATSAPP_DEFAULT_LEVEL=beginner
WHATSAPP_START_TEMPLATE_NAME=hello_world
WHATSAPP_START_TEMPLATE_LANGUAGE=en_US
WHATSAPP_USE_MOCK=false
WHATSAPP_TEST_TO=918971392035
```

`WHATSAPP_TOKEN` and `META_APP_SECRET` are accepted because the Cheerio project archive uses those names. `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_APP_SECRET` are the equivalent names in this Python app.

In Meta Developer Console:
- Add the callback URL above.
- Use the same `WHATSAPP_VERIFY_TOKEN`.
- Subscribe the WhatsApp webhook to the `messages` field.
- Send a WhatsApp message to your business/test number.

Run the WhatsApp diagnostics after changing Meta tokens or IDs:

```bash
docker compose exec api python scripts/whatsapp_diagnostics.py
```

All checks should pass before the bot can send or reply through WhatsApp. If `debug_token` passes but `phone_object` fails, the token is valid but is not authorized for the configured `WHATSAPP_PHONE_NUMBER_ID`.

Send the first business-initiated "Hi" message from the app side:

```bash
docker compose exec api python scripts/send_whatsapp_hi.py 9916039894
```

Or call the protected API:

```bash
curl -X POST "http://localhost:8000/v1/admin/whatsapp/send-hi" \
  -H "x-admin-token: change-me" \
  -H "Content-Type: application/json" \
  -d '{"to":"9916039894"}'
```

WhatsApp only allows the business to message first with an approved template. After the student replies, the 24-hour service window opens and the bot can send the program menu, mode menu, and AI answers.

Send the first Program menu from the app side:

```bash
docker compose exec api python scripts/send_whatsapp_program_menu.py 9916039894
```

Or call the protected API:

```bash
curl -X POST "http://localhost:8000/v1/admin/whatsapp/send-program-menu" \
  -H "x-admin-token: change-me" \
  -H "Content-Type: application/json" \
  -d '{"to":"9916039894"}'
```

Students can optionally type a program instead of tapping the list:

```text
CMA
CPA
ACCA
EA
```

Students can change the program or learning mode anytime:

```text
menu
```

---

## 6. Important environment variables

See `.env.example`.

Key settings:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `EMBEDDING_PROVIDER`
- `OPENAI_API_KEY` when `EMBEDDING_PROVIDER=openai`
- `OPENAI_EMBEDDING_MODEL`
- `QDRANT_URL`
- `REDIS_URL`
- `ADMIN_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_APP_SECRET`
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
- Big 4 interview Q&A
- FP&A, audit, taxation, controllership JD mapping
- LinkedIn outreach scripts
- salary and role guidance docs

---

## 8. Production checklist

Before going live:
- Replace `ADMIN_TOKEN`
- Put API behind HTTPS
- Add user login and role-based access
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
- Cache exact normalized questions in Redis.
- Keep embeddings precomputed during ingestion.
- Use Qdrant payload filters for course-specific search.
- Use local hash embeddings by default so Claude-only deployments can run; switch to `text-embedding-3-small` with `EMBEDDING_PROVIDER=openai` for stronger semantic retrieval.
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
