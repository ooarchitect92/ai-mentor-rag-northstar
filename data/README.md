# Runtime data

This directory is mounted at `/app/data` and contains local runtime state.

| Path | Purpose |
| --- | --- |
| `runtime-config.json` | Versioned dashboard-editable non-secret configuration |
| `whatsapp_enrollments.xlsx` | Excel enrollment authority when configured |
| `feedback-media/` | Private feedback screenshots |
| `question_answers.txt` | Reusable answer library |
| `sample_docs/` | Bundled non-secret example knowledge |

The SQLite catalog lives at `/app/state/admin.sqlite3` in the stable
`ai-mentor-rag-northstar_admin_storage` named volume so host-side tools cannot interfere with its WAL
files. Database sidecars, feedback media, runtime configuration, and enrollment
files are ignored by Git and excluded from the image. Back up both the named
volume and this directory outside the repository. Never place API keys or
service-account files here.
