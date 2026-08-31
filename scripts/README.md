# Operational scripts

Run Python scripts from the API container so dependencies and paths match
production. Each subfolder has one operational responsibility.

| Folder | Contents |
| --- | --- |
| `knowledge/` | Catalog import, sample seeding, legacy migration, and answer verification |
| `enrollments/` | Excel workbook creation and explicit student-course maintenance |
| `whatsapp/` | Meta connectivity diagnostics and deliberate manual sends |
| `windows/` | Windows startup helpers used by `start.bat` |
| `qa/` | Repeatable browser acceptance checks for dashboard routes and responsive layout |
| `security/` | Secret-safe environment repair and configuration hygiene utilities |
| `archive/` | Unsupported historical utilities; never use against production |

Common commands:

```text
docker compose exec api python scripts/knowledge/seed_sample_docs.py
docker compose exec api python scripts/knowledge/ingest_directory.py /app/data/my_docs CMA
docker compose exec api python scripts/whatsapp/whatsapp_diagnostics.py
docker compose exec api python scripts/enrollments/create_enrollment_workbook.py --help
CHROME_PATH=/path/to/chrome DASHBOARD_ADMIN_TOKEN=... node scripts/qa/dashboard_browser_smoke.mjs
```

Never hard-code real phone numbers or tokens; use environment variables or
explicit command arguments. New scripts must be placed in the matching
responsibility folder and added to this index.
