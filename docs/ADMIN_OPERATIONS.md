# Admin dashboard operations

Open `http://localhost:8000/admin/` and authenticate with `ADMIN_TOKEN` from the
deployment environment. The token is held only in the current browser tab.

## Overview

Shows document totals, published documents, open feedback, active indexing jobs,
recent jobs, retrieval state, embedding provider, and feedback-number state.

## Knowledge

Upload one to ten TXT, Markdown, PDF, or DOCX files, then choose a course and
document type. Every file is extracted and validated before the batch is inserted
transactionally. Edit changes title, course, type, or extracted text and creates a
new draft version. The old published revision stays live until replacement
indexing succeeds. Delete removes the editable source and its Qdrant points.

Limits come from `ADMIN_UPLOAD_MAX_FILES`, `ADMIN_UPLOAD_MAX_BYTES`, and the
two-million-character extracted-text ceiling.

## Training

Training means RAG indexing, not base-model fine-tuning. The worker chunks,
embeds, stages, publishes, and then prunes older revisions. Jobs are leased and
recovered after interruption.

- `queued`: waiting for a worker
- `running`: embedding/indexing
- `completed`: every selected document published
- `partial`: some selected documents failed
- `failed`: no document completed or the job failed terminally

Failed and partial jobs expose Retry. Document errors remain visible in Knowledge
and Training. Indexing is blocked while course retrieval is disabled. The model
health panel runs a short live NVIDIA completion and reports its model, answer,
reasoning mode, and end-to-end latency without exposing private reasoning.

## Feedback

Lists immutable WhatsApp reports and protected screenshots. Admins edit only
category, review status, and internal notes. Attachments require admin auth and
use no-store/sandbox response headers. Retention and storage quotas are
environment-controlled.

## Conversations

Shows a view-only timeline of inbound and outbound messages for the configured
Ziplin Phone Number ID. Conversation URLs use internal opaque IDs; list and
thread responses expose only masked phone numbers and sanitized message fields.
Raw webhook payloads, full phone numbers, Meta message/media IDs, filesystem
paths, tokens, and attachments are not available through this view. The active
page refreshes every ten seconds only while the browser tab is visible, and
both the list and thread also provide manual refresh controls.

## Enrollments

Look up a full international number. Save grants a course; the X on a course chip
revokes it. With Excel configured, changes are written synchronously to
`data/whatsapp_enrollments.xlsx` and reopened before success is returned. Google
Sheet authority supports live dashboard grants, revocations, roster viewing,
and Excel bulk imports. Send welcome invokes the approved Meta
template only for enrolled numbers.

The bulk importer accepts `.xlsx` workbooks with `phone_number`, `course`, and
`active` columns plus optional `student_name` and `notes`. Google Sheets must be
shared with the configured service-account email as Editor.

## Direct Ziplin Meta webhook

The production message path is direct and dedicated:

```text
Meta WhatsApp Cloud API
  -> POST https://mentor.example.com/v1/whatsapp/ziplin/webhook
  -> durable NorthStar webhook queue
  -> mentor worker
  -> Meta WhatsApp Cloud API reply
```

Use a permanent HTTPS hostname backed by a named Cloudflare Tunnel or managed
ingress. A `trycloudflare.com` quick-tunnel hostname changes after restart and
is suitable only for temporary development checks.

Configure these values in the deployment secret environment, never in browser
JavaScript or committed files:

```dotenv
WHATSAPP_ACCESS_TOKEN=<system-user-token>
WHATSAPP_PHONE_NUMBER_ID=<ziplin-phone-number-id>
WHATSAPP_BUSINESS_ACCOUNT_ID=<ziplin-waba-id>
META_APP_ID=<ziplin-meta-app-id>
WHATSAPP_APP_SECRET=<ziplin-meta-app-secret>
WHATSAPP_VERIFY_TOKEN=<long-random-verification-secret>
NORTHSTAR_PUBLIC_BASE_URL=https://mentor.example.com
WHATSAPP_WEBHOOK_CALLBACK_URL=https://mentor.example.com/v1/whatsapp/ziplin/webhook
CLOUDFLARE_TUNNEL_TOKEN=<named-tunnel-token-if-used>
```

The production callback URL must use the exact
`/v1/whatsapp/ziplin/webhook` path. The generic endpoint remains a served
compatibility alias but is rejected by production readiness and registration
checks. The app secret authenticates POST deliveries with
`X-Hub-Signature-256`; the independently generated verify token is used only
for Meta's GET challenge. The system-user token must have
`whatsapp_business_messaging` and `whatsapp_business_management` for the same
WABA and Phone Number ID.

In the Ziplin Meta app, subscribe the `whatsapp_business_account` object to the
`messages` field, register the callback URL and verification token, and ensure
the app is subscribed to the configured WABA. NorthStar rejects an entire batch
before persistence if any message or status receipt lacks the configured WABA
or Phone Number ID, and checks the number again during message processing.

`start.bat` runs `scripts/windows/register_webhook.ps1`. That registration
script first requires the public `/ready` endpoint and callback challenge to
succeed, then updates and verifies the Meta app subscription. Running it is an
external Meta configuration change. Use the diagnostic command below when a
read-only audit is required.

```powershell
docker compose exec -T api python /app/scripts/whatsapp/whatsapp_diagnostics.py
```

The default diagnostic performs read-only checks of configuration presence,
token permissions, Phone Number ID/WABA ownership, app subscription, approved
template, registered callback, callback challenge, and public
readiness. It does not send a WhatsApp message or change Meta configuration.

An outbound template test is deliberately opt-in and requires an explicit
approved recipient:

```powershell
docker compose exec -T api python /app/scripts/whatsapp/whatsapp_diagnostics.py --send-template --recipient <international-number>
```

The opt-in send uses NorthStar's WhatsApp client, so a Meta-accepted message is
recorded in Conversations immediately; it does not yet prove handset delivery.
Confirm the delivered/read status callback. For a genuine inbound
test, send `Hi` from a test handset, confirm the event completes in the durable
queue, appears once in Conversations, and receives exactly one reply. Never
paste access tokens, app secrets, tunnel tokens, or verification tokens into
chat, screenshots, issue trackers, or command output.

## Analytics

Shows request volume, unique students, success rate, response latency, daily
trend, web/WhatsApp channel mix, course and learning-mode distribution, and a
per-student activity table. Usage events contain operational dimensions only;
student question text and model reasoning are not stored in analytics.

## Activity

Provides searchable, paginated evidence of document, training, feedback,
configuration, and enrollment mutations. It is read-only.

## Configuration

Edits only allowlisted non-secret behavior: provider selection/model names,
bounded generation settings, retrieval controls, WhatsApp defaults, feedback
copy, and the mentor prompt. Credentials appear only as configured/not configured.
Settings and prompt commit together in one atomic versioned record; stale tabs
receive HTTP 409 and must refresh.

## Common failures

- `401`: missing or invalid admin token
- `409`: stale edit, active job conflict, unavailable Google Sheet, or locked Excel file
- `413`: upload or extracted text exceeds a limit
- `415`: unsupported extension
- `422`: invalid field, unreadable document, unsafe setting, or missing provider key
- `503 /ready`: Redis, Qdrant, or SQLite is unavailable/incompatible

## Recovery

- Refresh after a network interruption; server state is authoritative.
- Retry failed/partial indexing from Training.
- Restarting requeues expired leases and reconciles pending deletes.
- Never edit Qdrant directly; re-index from Knowledge.
- Back up the stable `ai-mentor-rag-northstar_admin_storage` volume, `data/`, Excel, Qdrant storage,
  and Redis AOF together. Stop the API or use SQLite's online backup API for a
  consistent catalog copy. Never run `docker compose down -v` without a tested
  backup because it deletes named-volume data.
