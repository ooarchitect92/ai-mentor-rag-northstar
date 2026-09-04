# WhatsApp operations

These tools perform explicit Meta connectivity checks or manual sends.

- `whatsapp_diagnostics.py` validates the direct Ziplin Meta callback, app and
  WABA subscription, token permissions, configured phone, approved start
  template, callback challenge, and public NorthStar readiness. It is read-only
  by default. Add `--send-template --recipient <number>` only for an explicit
  live outbound test to an approved recipient; that send uses NorthStar's
  client so Meta acceptance is recorded in the protected Conversations inbox.
- `send_whatsapp_hi.py` sends the configured approved start template.
- `send_whatsapp_program_menu.py` sends an enrolled-course menu.

They require environment-provided credentials and an explicit approved test
recipient for any live send. They must never contain fallback tokens or phone
numbers. The production callback is
`https://<permanent-host>/v1/whatsapp/ziplin/webhook`; a changing quick-tunnel
hostname is not production routing.
