# WhatsApp operations

These tools perform explicit Meta connectivity checks or manual sends.

- `whatsapp_diagnostics.py` validates Meta objects, the Xolox callback, the
  approved start template, and the stable public Ziplin relay. It is read-only
  by default. Add `--probe-relay` for a harmless status-only queue probe, or
  `--send-template --recipient <number>` for an explicit live send.
- `send_whatsapp_hi.py` sends the configured approved start template.
- `send_whatsapp_program_menu.py` sends an enrolled-course menu.

They require environment-provided credentials and an explicit approved test
recipient. They must never contain fallback tokens or phone numbers.
