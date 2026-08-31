# Backend

The FastAPI application lives in `app/`. See
[`docs/PROJECT_STRUCTURE.md`](../docs/PROJECT_STRUCTURE.md) for module ownership and
[`docs/ADMIN_OPERATIONS.md`](../docs/ADMIN_OPERATIONS.md) for workflow behavior.

Run locally with `PYTHONPATH=backend` and `uvicorn app.main:app`. All mutations
must flow through backend services; browser code never accesses stores directly.
