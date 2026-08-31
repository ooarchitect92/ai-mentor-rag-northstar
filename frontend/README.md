# Student frontend

This folder owns the public AI Mentor page and WhatsApp feedback entrypoint.

- `index.html` contains the accessible page, visual system, and lightweight
  browser client for `/v1/chat/stream` and `/v1/public/config`.
- It must use public APIs only and must never receive admin tokens or secrets.
- Admin screens belong in `admin-dashboard/`, not here.

The FastAPI application mounts this folder at `/` and `/static`.
