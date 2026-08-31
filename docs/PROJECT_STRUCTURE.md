# Project structure

This is the authoritative map of the NorthStar AI Mentor repository. The API
owns business rules and persistence, the web folders contain static clients,
and operational scripts reuse backend services.

## Top-level layout

```text
ai-mentor-rag-northstar/
├── backend/app/          FastAPI application and domain services
├── admin-dashboard/     Protected operations dashboard
├── frontend/            Public mentor and WhatsApp-feedback page
├── data/                Runtime data mounted into the API container
├── docs/                Current architecture and operating documentation
├── scripts/             Explicit maintenance and deployment utilities
├── secrets/             Local credentials; ignored by Git and mounted read-only
├── tests/               Unit, API, workflow, and recovery coverage
├── Dockerfile           Production API image
├── docker-compose.yml   API, Redis, Qdrant, and optional tunnel
├── start.bat            Windows build/start/webhook registration entry point
└── stop.bat             Windows shutdown entry point
```

Only true project entrypoints and build configuration belong at repository
root. Folder-specific `README.md` files explain ownership and placement rules.
Archived files are deliberately excluded from current operating instructions.

## Backend ownership

| File | Owns |
| --- | --- |
| `main.py` | Lifecycle, public/chat/WhatsApp routes, enrollments, readiness, static mounts |
| `admin_api.py` | Knowledge, training, feedback, activity, and configuration admin APIs |
| `admin_store.py` | SQLite schema and durable document/job/feedback/audit state |
| `training.py` | RAG indexing worker, leases, recovery, and publication |
| `vector_store.py` | Qdrant validation, indexing, revision filtering, deletion |
| `documents.py` / `chunking.py` | File extraction and deterministic chunks |
| `embeddings.py` | Hash/OpenAI embedding boundary |
| `mentor.py` / `llm.py` | Retrieval, policy, provider routing, and answer orchestration |
| `nvidia.py`, `gemini.py`, `claude.py` | Provider-specific clients |
| `whatsapp.py` | Meta parsing, menus, enrollments, feedback, and media |
| `webhook_queue.py` | Durable webhook queue, leases, retries, and ordering |
| `config.py` | Environment settings and atomic safe runtime configuration |
| `auth.py` / `schemas.py` | Admin authorization and shared validation |

## Persistence boundaries

| Store | Source of truth for | Never use it for |
| --- | --- | --- |
| SQLite (`/app/state/admin.sqlite3` in the stable `ai-mentor-rag-northstar_admin_storage` volume) | Knowledge text, versions, jobs, feedback, webhooks, audit | Similarity search |
| Qdrant | Derived embeddings for published revisions | Editing or publication authority |
| Redis | Caches, sessions, dedupe locks, fallback enrollments | Knowledge or feedback durability |
| Excel (`data/whatsapp_enrollments.xlsx`) | Enrollments when the workbook is configured | Mentor content or secrets |
| Google Sheets | Live enrollment authority when configured | Mentor content or secrets |
| Runtime JSON (`data/runtime-config.json`) | Versioned safe settings and mentor prompt | Secrets or infrastructure URLs |
| Feedback media directory | Immutable JPG/PNG feedback attachments | Public static serving |

Enrollment authority order is Google Sheet, Excel, then Redis/environment. A
configured authority never silently falls through to a weaker store.

## Web applications

- `frontend/index.html` calls only public/chat APIs.
- `admin-dashboard/index.html` contains the accessible dashboard shell.
- `admin-dashboard/assets/app.js` owns routing, rendering, and admin API calls.
- `admin-dashboard/assets/styles.css` owns dashboard design and responsive layout.

Dashboard pages are Overview, Knowledge, Training, Feedback, Enrollments,
Activity, and Configuration. The browser never talks directly to persistence.

## Change placement rules

1. Put validation and authority decisions in backend services, not browser code.
2. Persist editable source data before updating derived stores.
3. Add a schema migration whenever an existing SQLite installation changes.
4. Keep credentials and infrastructure settings environment-managed.
5. Add API/workflow tests with every admin mutation.
6. Keep dashboard code under `admin-dashboard/` and public UI under `frontend/`.
7. Make destructive script behavior explicit and opt-in.
