# Testing and release checks

## Automated suite

```powershell
$env:PYTHONPATH='backend'
python -m pytest -q
node --check admin-dashboard/assets/app.js
docker compose config --quiet
git diff --check
```

With `uv`-managed Python:

```powershell
$env:PYTHONPATH='backend'
uv run --python 3.12 --with-requirements requirements.txt --with pytest python -m pytest -q
```

Coverage includes admin auth/assets/readiness; transactional uploads; edit/delete
conflicts; training leases, recovery, publication, success, failure, and retry;
feedback media/sessions/quotas/retries; Excel writes and Redis migration; atomic
configuration; writable Google Sheet batches; enrollment bulk import; usage
analytics; model-health contracts; mentor scope/provider fallback; chunking;
and WhatsApp menus.

## Release gate

All commands above must pass. Then rebuild and verify the immutable image:

```powershell
docker compose up -d --build api
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`/ready` must report Redis, Qdrant, and SQLite as `ok`. Finally authenticate to
every dashboard page and run a disposable upload → edit → index → delete workflow.
