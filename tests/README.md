# Tests

Tests isolate SQLite, feedback media, runtime configuration, prompts, and Excel
inside temporary directories. Provider and external-service boundaries are faked
unless a test explicitly targets the running Docker stack.

See [`docs/TESTING.md`](../docs/TESTING.md) for commands and the release gate.
