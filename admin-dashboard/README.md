# Admin dashboard

This dependency-free same-origin application is mounted at `/admin/`.

- `index.html`: accessible shell and navigation
- `assets/app.js`: state, page rendering, API calls, and actions
- `assets/styles.css`: tokens, components, layout, and responsive behavior

Pages cover Overview, Knowledge, Training and live model health, Feedback,
Enrollments and bulk Excel import, Analytics, Activity, and Configuration.

Requests use `/v1/admin` with `X-Admin-Token`. Secrets are never rendered and the
token is stored only in the current browser tab. See
[`docs/ADMIN_OPERATIONS.md`](../docs/ADMIN_OPERATIONS.md).
