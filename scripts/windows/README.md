# Windows launch helpers

- `register_webhook.ps1` validates the existing callback/relay or registers the
  current direct tunnel callback with Meta.
- `stop_on_close.ps1` is retained only for compatibility with older launchers;
  the current `start.bat` deliberately leaves containers running.

`start.bat` launches detached containers with restart policies. Closing its
window does not stop the application; use `stop.bat` for an intentional stop.
For permanent public WhatsApp delivery, configure a remotely-managed Cloudflare
tunnel token and its published HTTPS base URL in `.env`.
