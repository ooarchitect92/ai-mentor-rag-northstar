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

## Existing WhatsApp webhook relay

Keep the callback already registered in Meta. The existing webhook application
must forward each unmodified WhatsApp JSON payload to NorthStar:

```dotenv
WHATSAPP_WEBHOOK_CALLBACK_URL=https://your-existing-service.example/webhooks/whatsapp
```

When this setting is present, `start.bat` verifies both the callback challenge
and Meta's active subscription without changing either. The temporary public
tunnel is disabled.

```text
POST {NORTHSTAR_BASE_URL}/v1/whatsapp/ziplin/relay
Content-Type: application/json
X-Ziplin-Relay-Token: {WHATSAPP_RELAY_TOKEN}
```

Generate a secret once and put the identical value in both deployments. It must
contain at least 32 random characters:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()
```

NorthStar `.env`:

```dotenv
WHATSAPP_RELAY_TOKEN=generated-secret
NORTHSTAR_PUBLIC_BASE_URL=https://mentor.example.com
```

`NORTHSTAR_PUBLIC_BASE_URL` must be a permanent HTTPS origin. Do not save a
`trycloudflare.com` quick-tunnel hostname in Xolox: that hostname changes when
the tunnel restarts and silently disconnects inbound messages.

Python forwarding example (use the raw parsed payload received from Meta):

```python
import httpx

async with httpx.AsyncClient(timeout=10) as client:
    response = await client.post(
        f"{NORTHSTAR_BASE_URL}/v1/whatsapp/ziplin/relay",
        json=meta_payload,
        headers={"X-Ziplin-Relay-Token": NORTHSTAR_RELAY_TOKEN},
    )
    response.raise_for_status()
```

Node/Express forwarding example:

```javascript
const response = await fetch(`${process.env.NORTHSTAR_BASE_URL}/v1/whatsapp/ziplin/relay`, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "x-ziplin-relay-token": process.env.NORTHSTAR_RELAY_TOKEN,
  },
  body: JSON.stringify(req.body),
});
if (!response.ok) throw new Error(`NorthStar relay failed: ${response.status}`);
```

Return `200` to Meta only after the existing application has durably accepted
its own work. A relay failure should be retried internally; do not silently drop
it. Meta message IDs are deduplicated by this service. Forward only payloads for
Ziplin; the service also enforces the configured Phone Number ID before queueing.

The relay solves inbound routing only. NorthStar still needs a current Meta
access token with `whatsapp_business_messaging` for the same Phone Number ID to
send replies. Never place either secret in frontend JavaScript.

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
